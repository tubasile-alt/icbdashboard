from __future__ import annotations

from datetime import datetime, timezone
import re
import unicodedata
from uuid import uuid4

import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import (
    FactFinanceiroMensal,
    FactFiscalMensal,
    FactProducaoProfissionalMensal,
    FactUnidadeMensal,
    IngestionQualityReport,
    Metadata,
)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    def norm(value: str) -> str:
        value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
        value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
        return re.sub(r"_+", "_", value).strip("_")

    normalized = df.copy()
    normalized.columns = [norm(c) for c in normalized.columns]
    column_alias = {
        "valor_dos_servicos": "valor_dos_servicos",
        "valor_servicos": "valor_dos_servicos",
        "consultas_online": "consultas_online",
        "consultas_on_line": "consultas_online",
        "retornos_online": "retornos_online",
        "retornos_on_line": "retornos_online",
        "receita_bruta_r": "receita_bruta",
    }
    normalized = normalized.rename(columns=column_alias)
    return normalized


_MES_MAP = {
    "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12,
}


def _sheet_or_empty(sheets: dict[str, pd.DataFrame], sheet_name: str) -> tuple[pd.DataFrame, int]:
    if sheet_name not in sheets:
        return pd.DataFrame(), 0
    raw = sheets[sheet_name]
    empty_count = int(raw.isna().all(axis=0).sum())
    clean = raw.dropna(axis=1, how="all")
    return _normalize_columns(clean), empty_count


def _parse_dre_sheets(sheets: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, int]:
    """
    Extrai dados financeiros das abas mensais de despesa.
    Padrão de nome: 'Despesas [MES] [ANO]'  (ex: 'Despesas JAN 2026')
    Estrutura: linha 0 vazia, linha 1 = header, linhas 2+ = dados por unidade.
    Mapeamento de colunas:
      UNIDADE -> unidade
      RECEITA BRUTA -> receita_bruta
      ISS/PIS/COFINS | Imposto -> impostos
      DEVOLUÇÕES -> devolucoes (ignorado)
      RECEITA LIQUIDA -> receita_liquida
      CUSTOS / DESPESAS -> despesas
      EBITDA -> ebitda
      MARGEM EBITDA -> margem_ebitda
      IRPJ/CSLL -> irpj (ignorado)
      LL -> lucro_liquido
      MARGEM LIQUIDA -> margem_liquida
    """
    col_map = {
        "unidade": "unidade",
        "receita_bruta": "receita_bruta",
        "iss_pis_cofins": "impostos",
        "impostos": "impostos",
        "receita_liquida": "receita_liquida",
        "receita_liq": "receita_liquida",
        "custos_despesas": "despesas",
        "custos_despesas_com_impostos": "despesas",
        "despesas": "despesas",
        "ebitda": "ebitda",
        "margem_ebitda": "margem_ebitda",
        "ll": "lucro_liquido",
        "lucro_liquido": "lucro_liquido",
        "margem_liquida": "margem_liquida",
        "margem_liq": "margem_liquida",
    }

    rows: list[dict] = []
    empty_count = 0

    for sheet_name, raw in sheets.items():
        match = re.match(r"Despesas\s+([A-Z]{3})\s+(\d{4})\s*$", sheet_name.strip(), re.IGNORECASE)
        if not match:
            continue

        mes = _MES_MAP.get(match.group(1).upper())
        ano = int(match.group(2))
        if not mes:
            continue

        competencia = f"{ano}-{mes:02d}"

        clean = raw.dropna(axis=1, how="all").dropna(axis=0, how="all")
        empty_count += int(raw.isna().all(axis=0).sum())

        if len(clean) < 2:
            continue

        header_row_idx = None
        for i, row in clean.iterrows():
            row_vals = [str(v).strip().upper() for v in row.values if pd.notna(v) and str(v).strip()]
            if any("UNIDADE" in v or "RECEITA" in v for v in row_vals):
                header_row_idx = i
                break

        if header_row_idx is None:
            clean.columns = range(len(clean.columns))
            header_row_idx = 0

        headers = clean.loc[header_row_idx]
        data = clean.loc[header_row_idx + 1:].copy()
        data.columns = [str(h) for h in headers]
        data = _normalize_columns(data)
        data = data.rename(columns=col_map)
        data = data.dropna(subset=["unidade"])
        data = data[data["unidade"].astype(str).str.strip().ne("")]
        data = data[~data["unidade"].astype(str).str.upper().isin(["UNIDADE", "TOTAL", "NAN"])]

        for _, r in data.iterrows():
            unidade = str(r.get("unidade", "")).strip()
            if not unidade:
                continue
            rows.append({
                "ano": ano,
                "mes": mes,
                "competencia": competencia,
                "unidade": unidade,
                "receita_bruta": pd.to_numeric(r.get("receita_bruta", 0), errors="coerce") or 0,
                "impostos": pd.to_numeric(r.get("impostos", 0), errors="coerce") or 0,
                "receita_liquida": pd.to_numeric(r.get("receita_liquida", 0), errors="coerce") or 0,
                "despesas": pd.to_numeric(r.get("despesas", 0), errors="coerce") or 0,
                "ebitda": pd.to_numeric(r.get("ebitda", 0), errors="coerce") or 0,
                "margem_ebitda": pd.to_numeric(r.get("margem_ebitda", 0), errors="coerce") or 0,
                "lucro_liquido": pd.to_numeric(r.get("lucro_liquido", 0), errors="coerce") or 0,
                "margem_liquida": pd.to_numeric(r.get("margem_liquida", 0), errors="coerce") or 0,
            })

    if not rows:
        return pd.DataFrame(), empty_count

    df = pd.DataFrame(rows)
    df = df[df["receita_bruta"].abs() + df["receita_liquida"].abs() + df["lucro_liquido"].abs() > 0]
    return df, empty_count


def _parse_fiscal_sheet(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Extrai dados da aba '% Notas fiscais'.
    Estrutura: blocos lado a lado por ano, sem coluna de unidade.
    Linha 0: ano (ex: 2025, 2026)
    Linha 1: Mês | Vendas | NF | %  (repetido para cada ano)
    Linhas 2+: JAN | valor | valor | valor
    """
    raw = sheets.get("% Notas fiscais")
    if raw is None or raw.empty:
        return pd.DataFrame()

    clean = raw.dropna(axis=1, how="all")
    rows: list[dict] = []

    ano_row = clean.iloc[0]
    header_row = clean.iloc[1]

    block_start = None
    block_ano = None

    for col_idx, (ano_val, hdr_val) in enumerate(zip(ano_row, header_row)):
        ano_str = str(ano_val).strip()
        hdr_str = str(hdr_val).strip().upper()

        if re.match(r"^\d{4}$", ano_str):
            block_start = col_idx
            block_ano = int(ano_str)

        if block_start is not None and block_ano is not None and "MÊS" in hdr_str or "MES" in hdr_str:
            data_rows = clean.iloc[2:]
            mes_col = col_idx
            vendas_col = col_idx + 1
            nf_col = col_idx + 2
            pct_col = col_idx + 3

            for _, data_row in data_rows.iterrows():
                mes_str = str(data_row.iloc[mes_col] if mes_col < len(data_row) else "").strip().upper()
                mes_num = _MES_MAP.get(mes_str)
                if not mes_num:
                    continue

                vendas = pd.to_numeric(data_row.iloc[vendas_col] if vendas_col < len(data_row) else 0, errors="coerce") or 0
                nf = pd.to_numeric(data_row.iloc[nf_col] if nf_col < len(data_row) else 0, errors="coerce") or 0
                pct_nf = pd.to_numeric(data_row.iloc[pct_col] if pct_col < len(data_row) else 0, errors="coerce") or 0

                rows.append({
                    "ano": block_ano,
                    "mes": mes_num,
                    "competencia": f"{block_ano}-{mes_num:02d}",
                    "unidade": None,
                    "unidade_ref": "__CONSOLIDADO__",
                    "receita_com_nf": float(nf),
                    "receita_sem_nf": float(vendas - nf) if vendas >= nf else 0.0,
                    "percentual_nf": float(pct_nf),
                })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _pick(df: pd.DataFrame, options: list[str], required: bool = False) -> str | None:
    for name in options:
        if name in df.columns:
            return name
    if required:
        raise ValueError(f"Coluna obrigatória ausente. Opções: {options}")
    return None


def _to_number(series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _clean_text_series(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace(r"[\r\n\t]+", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def _derive_period(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    data_col = _pick(out, ["data", "date", "dt"])
    if data_col:
        parsed = pd.to_datetime(out[data_col], errors="coerce")
        out["ano"] = parsed.dt.year
        out["mes"] = parsed.dt.month

    if "ano" in out.columns:
        out["ano"] = _to_number(out["ano"]).astype(int)
    else:
        out["ano"] = 0
    
    if "mes" in out.columns:
        out["mes"] = _to_number(out["mes"]).astype(int)
    else:
        out["mes"] = 0
    out = out[(out["ano"] > 0) & (out["mes"] >= 1) & (out["mes"] <= 12)].copy()
    out["competencia"] = out["ano"].astype(str) + "-" + out["mes"].astype(str).str.zfill(2)
    out["trimestre"] = ((out["mes"] - 1) // 3 + 1).astype(int)
    return out


def _status_from_timestamp(last_update: datetime, stale_threshold_hours: int) -> str:
    elapsed_hours = (datetime.now(timezone.utc) - last_update).total_seconds() / 3600
    if elapsed_hours < 1:
        return "atualizado"
    if elapsed_hours <= stale_threshold_hours:
        return "atencao"
    return "desatualizado"


def process_excel_full_refresh(
    db: Session,
    excel_path: str,
    source_file_name: str,
    source_file_rev: str,
    source_file_last_modified: str,
    stale_threshold_hours: int,
) -> None:
    started_at = datetime.now(timezone.utc)
    run_id = f"{started_at.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"

    sheets = pd.read_excel(excel_path, sheet_name=None)
    base_df, empty_base = _sheet_or_empty(sheets, "Base Dados")
    dre_df, empty_dre = _parse_dre_sheets(sheets)
    fiscal_df = _parse_fiscal_sheet(sheets)
    empty_fiscal = 0

    if base_df.empty:
        raise RuntimeError("A aba 'Base Dados' está ausente ou vazia.")

    db.execute(delete(FactUnidadeMensal))
    db.execute(delete(FactProducaoProfissionalMensal))
    db.execute(delete(FactFinanceiroMensal))
    db.execute(delete(FactFiscalMensal))

    processed_rows = 0
    inconsistent_rows = 0
    incomplete_competencias: set[str] = set()

    # Base Dados (operacional)
    base_df = _derive_period(base_df)
    processed_rows += len(base_df)

    unidade_col = _pick(base_df, ["unidade", "clinica", "filial"], required=True)
    profissional_col = _pick(base_df, ["profissional", "medico"]) or "profissional"
    if profissional_col not in base_df.columns:
        base_df[profissional_col] = ""

    measures = {
        "leads": ["leads"],
        "consultas_presenciais": ["consultas"],
        "consultas_online": ["consultas_online"],
        "retornos_presenciais": ["retornos"],
        "retornos_online": ["retornos_online"],
        "cirurgias": ["cirurgias"],
        "receita_operacional": ["valor_dos_servicos", "valor_servicos", "receita"],
    }

    for target, options in measures.items():
        source = _pick(base_df, options)
        base_df[target] = _to_number(base_df[source]) if source else 0

    base_df[unidade_col] = base_df[unidade_col].astype(str).str.strip()
    base_df[profissional_col] = _clean_text_series(base_df[profissional_col])
    base_df[unidade_col] = _clean_text_series(base_df[unidade_col])

    for c in ["leads", "consultas_presenciais", "consultas_online", "retornos_presenciais", "retornos_online", "cirurgias", "receita_operacional"]:
        base_df[f"neg_{c}"] = base_df[c] < 0

    unidade_month = base_df.groupby([unidade_col, "ano", "mes", "competencia"], as_index=False).agg(
        {
            "leads": "sum",
            "consultas_presenciais": "sum",
            "consultas_online": "sum",
            "retornos_presenciais": "sum",
            "retornos_online": "sum",
            "cirurgias": "sum",
            "receita_operacional": "sum",
            "neg_leads": "max",
            "neg_consultas_presenciais": "max",
            "neg_consultas_online": "max",
            "neg_cirurgias": "max",
            "neg_receita_operacional": "max",
        }
    ).rename(columns={unidade_col: "unidade"})

    for _, row in unidade_month.iterrows():
        consultas_totais = max(float(row["consultas_presenciais"] + row["consultas_online"]), 0)
        retornos_totais = max(float(row["retornos_presenciais"] + row["retornos_online"]), 0)
        leads = max(float(row["leads"]), 0)
        cirurgias = max(float(row["cirurgias"]), 0)
        receita = max(float(row["receita_operacional"]), 0)

        inconsistente = bool(
            row["neg_leads"]
            or row["neg_consultas_presenciais"]
            or row["neg_consultas_online"]
            or row["neg_cirurgias"]
            or row["neg_receita_operacional"]
            or (receita > 0 and consultas_totais == 0 and cirurgias == 0)
            or (cirurgias > consultas_totais and consultas_totais > 0)
            or (consultas_totais > 0 and leads == 0)
        )
        if inconsistente:
            inconsistent_rows += 1

        mes_incompleto = bool((receita > 0 and consultas_totais == 0 and retornos_totais == 0) or row["competencia"] == "2026-03")
        if mes_incompleto:
            incomplete_competencias.add(row["competencia"])

        db.add(
            FactUnidadeMensal(
                unidade=row["unidade"],
                ano=int(row["ano"]),
                mes=int(row["mes"]),
                competencia=row["competencia"],
                leads=leads,
                consultas_presenciais=max(float(row["consultas_presenciais"]), 0),
                consultas_online=max(float(row["consultas_online"]), 0),
                consultas_totais=consultas_totais,
                retornos_presenciais=max(float(row["retornos_presenciais"]), 0),
                retornos_online=max(float(row["retornos_online"]), 0),
                retornos_totais=retornos_totais,
                cirurgias=cirurgias,
                receita_operacional=receita,
                ticket_medio_cirurgia=(receita / cirurgias) if cirurgias > 0 else 0,
                conv_lead_consulta=(consultas_totais / leads) if leads > 0 else 0,
                conv_consulta_cirurgia=(cirurgias / consultas_totais) if consultas_totais > 0 else 0,
                receita_por_lead=(receita / leads) if leads > 0 else 0,
                receita_por_consulta=(receita / consultas_totais) if consultas_totais > 0 else 0,
                cirurgias_por_consulta=(cirurgias / consultas_totais) if consultas_totais > 0 else 0,
                mes_incompleto=mes_incompleto,
                dados_inconsistentes=inconsistente,
            )
        )

    profissional_base = base_df[base_df[profissional_col].ne("") & base_df[profissional_col].ne("0")].copy()
    if not profissional_base.empty:
        prof_month = profissional_base.groupby([profissional_col, unidade_col, "ano", "mes", "competencia"], as_index=False).agg(
            {
                "consultas_presenciais": "sum",
                "consultas_online": "sum",
                "retornos_presenciais": "sum",
                "retornos_online": "sum",
                "cirurgias": "sum",
            }
        ).rename(columns={profissional_col: "profissional", unidade_col: "unidade"})

        for _, row in prof_month.iterrows():
            consultas_totais = max(float(row["consultas_presenciais"] + row["consultas_online"]), 0)
            retornos_totais = max(float(row["retornos_presenciais"] + row["retornos_online"]), 0)
            cirurgias = max(float(row["cirurgias"]), 0)
            inconsistente = bool(cirurgias > consultas_totais and consultas_totais > 0)
            db.add(
                FactProducaoProfissionalMensal(
                    profissional=row["profissional"],
                    unidade=row["unidade"],
                    ano=int(row["ano"]),
                    mes=int(row["mes"]),
                    competencia=row["competencia"],
                    consultas_presenciais=max(float(row["consultas_presenciais"]), 0),
                    consultas_online=max(float(row["consultas_online"]), 0),
                    consultas_totais=consultas_totais,
                    retornos_presenciais=max(float(row["retornos_presenciais"]), 0),
                    retornos_online=max(float(row["retornos_online"]), 0),
                    retornos_totais=retornos_totais,
                    cirurgias=cirurgias,
                    mes_incompleto=row["competencia"] in incomplete_competencias,
                    dados_inconsistentes=inconsistente,
                )
            )

    # DRE: abas mensais "Despesas JAN 2026", "Despesas FEV 2026" etc.
    if not dre_df.empty:
        processed_rows += len(dre_df)
        for _, row in dre_df.iterrows():
            unidade = str(row.get("unidade") or "").strip() or None
            db.add(
                FactFinanceiroMensal(
                    ano=int(row["ano"]),
                    mes=int(row["mes"]),
                    competencia=row["competencia"],
                    unidade=unidade,
                    unidade_ref=unidade if unidade else "__CONSOLIDADO__",
                    receita_bruta=float(row.get("receita_bruta") or 0),
                    impostos=float(row.get("impostos") or 0),
                    receita_liquida=float(row.get("receita_liquida") or 0),
                    custos=0.0,
                    despesas=float(row.get("despesas") or 0),
                    ebitda=float(row.get("ebitda") or 0),
                    margem_ebitda=float(row.get("margem_ebitda") or 0),
                    lucro_liquido=float(row.get("lucro_liquido") or 0),
                    margem_liquida=float(row.get("margem_liquida") or 0),
                )
            )

    # Fiscal: aba "% Notas fiscais"
    if not fiscal_df.empty:
        processed_rows += len(fiscal_df)
        for _, row in fiscal_df.iterrows():
            db.add(
                FactFiscalMensal(
                    ano=int(row["ano"]),
                    mes=int(row["mes"]),
                    competencia=row["competencia"],
                    unidade=row.get("unidade"),
                    unidade_ref=str(row.get("unidade_ref") or "__CONSOLIDADO__"),
                    percentual_nf=float(row.get("percentual_nf") or 0),
                    receita_com_nf=float(row.get("receita_com_nf") or 0),
                    receita_sem_nf=float(row.get("receita_sem_nf") or 0),
                )
            )

    finished_at = datetime.now(timezone.utc)
    metadata = db.get(Metadata, 1)
    status = _status_from_timestamp(finished_at, stale_threshold_hours)
    if metadata:
        metadata.source_file_name = source_file_name
        metadata.source_file_last_modified = source_file_last_modified
        metadata.source_file_rev = source_file_rev
        metadata.last_ingestion_started_at = started_at
        metadata.last_ingestion_finished_at = finished_at
        metadata.dashboard_last_update = finished_at
        metadata.update_status = status
    else:
        db.add(
            Metadata(
                id=1,
                source_file_name=source_file_name,
                source_file_last_modified=source_file_last_modified,
                source_file_rev=source_file_rev,
                last_ingestion_started_at=started_at,
                last_ingestion_finished_at=finished_at,
                dashboard_last_update=finished_at,
                update_status=status,
            )
        )

    db.add(
        IngestionQualityReport(
            run_id=run_id,
            processed_rows=processed_rows,
            inconsistent_rows=inconsistent_rows,
            empty_columns_removed=empty_base + empty_dre + empty_fiscal,
            incomplete_months_detected=len(incomplete_competencias),
            started_at=started_at,
            finished_at=finished_at,
        )
    )
    db.commit()
