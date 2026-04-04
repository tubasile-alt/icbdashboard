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


def _sheet_or_empty(sheets: dict[str, pd.DataFrame], sheet_name: str) -> tuple[pd.DataFrame, int]:
    if sheet_name not in sheets:
        return pd.DataFrame(), 0
    raw = sheets[sheet_name]
    empty_count = int(raw.isna().all(axis=0).sum())
    clean = raw.dropna(axis=1, how="all")
    return _normalize_columns(clean), empty_count


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

    out["ano"] = _to_number(out.get("ano", 0)).astype(int)
    out["mes"] = _to_number(out.get("mes", 0)).astype(int)
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
    dre_df, empty_dre = _sheet_or_empty(sheets, "Despesas 2026")
    fiscal_df, empty_fiscal = _sheet_or_empty(sheets, "% Notas fiscais")

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

    # Despesas 2026 (financeiro)
    if not dre_df.empty:
        dre_df = _derive_period(dre_df)
        processed_rows += len(dre_df)
        unidade_fin_col = _pick(dre_df, ["unidade", "clinica", "filial"])

        for col in ["receita_bruta", "impostos", "receita_liquida", "custos", "despesas", "ebitda", "margem_ebitda", "lucro_liquido", "margem_liquida"]:
            dre_df[col] = _to_number(dre_df[col]) if col in dre_df.columns else 0

        group_keys = ["competencia", "ano", "mes"] + ([unidade_fin_col] if unidade_fin_col else [])
        fin_month = dre_df.groupby(group_keys, as_index=False).agg(
            {
                "receita_bruta": "sum",
                "impostos": "sum",
                "receita_liquida": "sum",
                "custos": "sum",
                "despesas": "sum",
                "ebitda": "sum",
                "margem_ebitda": "mean",
                "lucro_liquido": "sum",
                "margem_liquida": "mean",
            }
        )

        for _, row in fin_month.iterrows():
            db.add(
                FactFinanceiroMensal(
                    ano=int(row["ano"]),
                    mes=int(row["mes"]),
                    competencia=row["competencia"],
                    unidade=row[unidade_fin_col] if unidade_fin_col else None,
                    unidade_ref=str(row[unidade_fin_col]).strip() if unidade_fin_col else "__CONSOLIDADO__",
                    receita_bruta=float(row["receita_bruta"]),
                    impostos=float(row["impostos"]),
                    receita_liquida=float(row["receita_liquida"]),
                    custos=float(row["custos"]),
                    despesas=float(row["despesas"]),
                    ebitda=float(row["ebitda"]),
                    margem_ebitda=float(row["margem_ebitda"]),
                    lucro_liquido=float(row["lucro_liquido"]),
                    margem_liquida=float(row["margem_liquida"]),
                )
            )

    # % Notas fiscais (fiscal)
    if not fiscal_df.empty:
        fiscal_df = _derive_period(fiscal_df)
        processed_rows += len(fiscal_df)
        unidade_fiscal_col = _pick(fiscal_df, ["unidade", "clinica", "filial"])
        percentual_nf_col = _pick(fiscal_df, ["percentual_nf", "percentual_notas_fiscais", "_notas_fiscais"])

        fiscal_df["percentual_nf"] = _to_number(fiscal_df[percentual_nf_col]) if percentual_nf_col else 0
        fiscal_df["receita_com_nf"] = _to_number(fiscal_df["receita_com_nf"]) if "receita_com_nf" in fiscal_df.columns else 0
        fiscal_df["receita_sem_nf"] = _to_number(fiscal_df["receita_sem_nf"]) if "receita_sem_nf" in fiscal_df.columns else 0

        group_keys = ["competencia", "ano", "mes"] + ([unidade_fiscal_col] if unidade_fiscal_col else [])
        fiscal_month = fiscal_df.groupby(group_keys, as_index=False).agg(
            {"percentual_nf": "mean", "receita_com_nf": "sum", "receita_sem_nf": "sum"}
        )

        for _, row in fiscal_month.iterrows():
            db.add(
                FactFiscalMensal(
                    ano=int(row["ano"]),
                    mes=int(row["mes"]),
                    competencia=row["competencia"],
                    unidade=row[unidade_fiscal_col] if unidade_fiscal_col else None,
                    unidade_ref=str(row[unidade_fiscal_col]).strip() if unidade_fiscal_col else "__CONSOLIDADO__",
                    percentual_nf=float(row["percentual_nf"]),
                    receita_com_nf=float(row["receita_com_nf"]),
                    receita_sem_nf=float(row["receita_sem_nf"]),
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
