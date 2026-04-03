from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import FactFinanceiro, FactProducaoProfissional, FactUnidadeMensal, Metadata


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    normalized_columns = [
        str(col)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("ç", "c")
        .replace("ã", "a")
        .replace("á", "a")
        .replace("ê", "e")
        for col in df.columns
    ]
    df.columns = normalized_columns
    invalid_columns = [col for col in df.columns if col in {"", "nan"} or col.startswith("unnamed:")]
    if invalid_columns:
        df = df.drop(columns=invalid_columns)
    return df


def _pick_col(df: pd.DataFrame, options: list[str], required: bool = True) -> str | None:
    for col in options:
        if col in df.columns:
            return col
    if required:
        raise ValueError(f"Coluna obrigatória ausente. Opções aceitas: {options}")
    return None


def _to_int(value) -> int:
    if pd.isna(value):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_float(value) -> float:
    if pd.isna(value):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_monthly_columns(df: pd.DataFrame) -> tuple[str, str] | None:
    data_col = _pick_col(df, ["data"], required=False)
    if data_col:
        df["ano"] = pd.to_datetime(df[data_col], errors="coerce").dt.year.fillna(0).astype(int)
        df["mes"] = pd.to_datetime(df[data_col], errors="coerce").dt.month.fillna(0).astype(int)
        return "ano", "mes"

    ano_col = _pick_col(df, ["ano"], required=False)
    mes_col = _pick_col(df, ["mes"], required=False)
    if not ano_col or not mes_col:
        return None
    return ano_col, mes_col


def process_excel_and_refresh_database(db: Session, excel_path: str, source_file_name: str, source_file_rev: str):
    all_sheets = pd.read_excel(excel_path, sheet_name=None)
    unidade_frames: list[pd.DataFrame] = []
    profissional_frames: list[pd.DataFrame] = []
    financeiro_frames: list[pd.DataFrame] = []

    for _, raw_df in all_sheets.items():
        if raw_df is None or raw_df.empty:
            continue

        raw_df = raw_df.dropna(axis=1, how="all")
        if raw_df.empty:
            continue
        df = _normalize_columns(raw_df).fillna(0)

        competencia_col = _pick_col(df, ["competencia"], required=False)
        receita_liquida_col = _pick_col(df, ["receita_liquida", "dre_receita_liquida"], required=False)
        ebitda_col = _pick_col(df, ["ebitda", "dre_ebitda"], required=False)
        lucro_col = _pick_col(df, ["lucro_liquido", "dre_lucro_liquido"], required=False)
        if competencia_col and receita_liquida_col:
            fin_df = df[df[receita_liquida_col] != 0].copy()
            if not fin_df.empty:
                fin_df["competencia"] = fin_df[competencia_col].astype(str).str.strip()
                fin_df["receita_liquida"] = fin_df[receita_liquida_col].apply(_to_float).clip(lower=0)
                fin_df["ebitda"] = fin_df[ebitda_col].apply(_to_float) if ebitda_col else 0.0
                fin_df["lucro_liquido"] = fin_df[lucro_col].apply(_to_float) if lucro_col else 0.0
                financeiro_frames.append(fin_df[["competencia", "receita_liquida", "ebitda", "lucro_liquido"]])

        unidade_col = _pick_col(df, ["unidade", "clinica", "filial"], required=False)
        monthly_cols = _extract_monthly_columns(df)
        if not unidade_col or not monthly_cols:
            continue
        ano_col, mes_col = monthly_cols

        receita_col = _pick_col(df, ["valor_dos_servicos", "receita", "receita_base", "faturamento"], required=False)
        leads_col = _pick_col(df, ["leads"], required=False)
        consultas_col = _pick_col(df, ["consultas", "consultas_online"], required=False)
        cirurgias_col = _pick_col(df, ["cirurgias", "cirurgias_realizadas_no_cc"], required=False)
        if receita_col:
            unidade_df = df[df[receita_col] != 0].copy()
            unidade_df["receita"] = unidade_df[receita_col].apply(_to_float).clip(lower=0)
            unidade_df["leads"] = unidade_df[leads_col].apply(_to_float).clip(lower=0) if leads_col else 0.0
            unidade_df["consultas"] = unidade_df[consultas_col].apply(_to_float).clip(lower=0) if consultas_col else 0.0
            unidade_df["cirurgias"] = unidade_df[cirurgias_col].apply(_to_float).clip(lower=0) if cirurgias_col else 0.0
            unidade_df["unidade"] = unidade_df[unidade_col].astype(str).str.strip()
            unidade_df["ano"] = unidade_df[ano_col].apply(_to_int)
            unidade_df["mes"] = unidade_df[mes_col].apply(_to_int)
            unidade_frames.append(unidade_df[["unidade", "ano", "mes", "receita", "leads", "consultas", "cirurgias"]])

        profissional_col = _pick_col(df, ["profissional", "medico"], required=False)
        retornos_col = _pick_col(df, ["retornos", "retornos_online"], required=False)
        if profissional_col:
            prof_df = df[df[profissional_col].astype(str).str.strip() != "0"].copy()
            prof_df = prof_df[prof_df[profissional_col].astype(str).str.strip() != ""]
            if not prof_df.empty:
                prof_df["profissional"] = prof_df[profissional_col].astype(str).str.strip()
                prof_df["unidade"] = prof_df[unidade_col].astype(str).str.strip()
                prof_df["ano"] = prof_df[ano_col].apply(_to_int)
                prof_df["mes"] = prof_df[mes_col].apply(_to_int)
                prof_df["consultas"] = prof_df[consultas_col].apply(_to_float).clip(lower=0) if consultas_col else 0.0
                prof_df["retornos"] = prof_df[retornos_col].apply(_to_float).clip(lower=0) if retornos_col else 0.0
                prof_df["cirurgias"] = prof_df[cirurgias_col].apply(_to_float).clip(lower=0) if cirurgias_col else 0.0
                profissional_frames.append(
                    prof_df[["profissional", "unidade", "ano", "mes", "consultas", "retornos", "cirurgias"]]
                )

    db.execute(delete(FactUnidadeMensal))
    db.execute(delete(FactProducaoProfissional))
    db.execute(delete(FactFinanceiro))

    if unidade_frames:
        unidade_df = pd.concat(unidade_frames, ignore_index=True)
        unidade_df = unidade_df[(unidade_df["unidade"] != "") & (unidade_df["ano"] > 0) & (unidade_df["mes"] > 0)]
        unidade_df = (
            unidade_df.groupby(["unidade", "ano", "mes"], as_index=False)[["receita", "leads", "consultas", "cirurgias"]]
            .sum()
        )
        for _, row in unidade_df.iterrows():
            consultas = _to_float(row["consultas"])
            receita = _to_float(row["receita"])
            db.add(
                FactUnidadeMensal(
                    unidade=str(row["unidade"]).strip(),
                    ano=_to_int(row["ano"]),
                    mes=_to_int(row["mes"]),
                    receita=receita,
                    leads=_to_float(row["leads"]),
                    consultas=consultas,
                    cirurgias=_to_float(row["cirurgias"]),
                    mes_incompleto=datetime.now(UTC).month == _to_int(row["mes"]),
                    dados_inconsistentes=consultas == 0 and receita > 0,
                )
            )

    if profissional_frames:
        prof_df = pd.concat(profissional_frames, ignore_index=True)
        prof_df = prof_df[
            (prof_df["profissional"] != "")
            & (prof_df["unidade"] != "")
            & (prof_df["ano"] > 0)
            & (prof_df["mes"] > 0)
        ]
        prof_df = (
            prof_df.groupby(["profissional", "unidade", "ano", "mes"], as_index=False)[
                ["consultas", "retornos", "cirurgias"]
            ].sum()
        )
        for _, row in prof_df.iterrows():
            consultas = _to_float(row["consultas"])
            db.add(
                FactProducaoProfissional(
                    profissional=str(row["profissional"]).strip(),
                    unidade=str(row["unidade"]).strip(),
                    ano=_to_int(row["ano"]),
                    mes=_to_int(row["mes"]),
                    consultas=consultas,
                    retornos=_to_float(row["retornos"]),
                    cirurgias=_to_float(row["cirurgias"]),
                    mes_incompleto=datetime.now(UTC).month == _to_int(row["mes"]),
                    dados_inconsistentes=consultas == 0 and _to_float(row["cirurgias"]) > 0,
                )
            )

    if financeiro_frames:
        fin_df = pd.concat(financeiro_frames, ignore_index=True)
        fin_df = fin_df[fin_df["competencia"] != ""]
        fin_df = fin_df.groupby(["competencia"], as_index=False)[["receita_liquida", "ebitda", "lucro_liquido"]].sum()
        for _, row in fin_df.iterrows():
            db.add(
                FactFinanceiro(
                    competencia=str(row["competencia"]).strip(),
                    receita_liquida=_to_float(row["receita_liquida"]),
                    ebitda=_to_float(row["ebitda"]),
                    lucro_liquido=_to_float(row["lucro_liquido"]),
                )
            )

    existing_metadata = db.get(Metadata, 1)
    if existing_metadata:
        existing_metadata.last_update_timestamp = datetime.now(UTC)
        existing_metadata.source_file_name = source_file_name
        existing_metadata.source_file_rev = source_file_rev
    else:
        db.add(
            Metadata(
                id=1,
                last_update_timestamp=datetime.now(UTC),
                source_file_name=source_file_name,
                source_file_rev=source_file_rev,
            )
        )

    db.commit()


def get_last_update_status(db: Session, stale_threshold_hours: int) -> dict:
    metadata = db.get(Metadata, 1)
    if not metadata:
        return {"last_update": None, "status": "stale"}

    elapsed_hours = (datetime.now(UTC) - metadata.last_update_timestamp.replace(tzinfo=UTC)).total_seconds() / 3600
    status = "updated" if elapsed_hours <= stale_threshold_hours else "stale"
    return {"last_update": metadata.last_update_timestamp.strftime("%Y-%m-%d %H:%M:%S"), "status": status}


def get_dashboard_payload(db: Session, stale_threshold_hours: int) -> dict:
    last = get_last_update_status(db, stale_threshold_hours)

    receita_total = db.scalar(select(func.coalesce(func.sum(FactUnidadeMensal.receita), 0))) or 0
    cirurgias_total = db.scalar(select(func.coalesce(func.sum(FactUnidadeMensal.cirurgias), 0))) or 0

    financeiro = db.execute(
        select(
            func.coalesce(func.sum(FactFinanceiro.ebitda), 0),
            func.coalesce(func.sum(FactFinanceiro.lucro_liquido), 0),
            func.coalesce(func.sum(FactFinanceiro.receita_liquida), 0),
        )
    ).one()

    receita_por_mes = [
        {"competencia": f"{ano}-{mes:02d}", "receita": receita}
        for ano, mes, receita in db.execute(
            select(FactUnidadeMensal.ano, FactUnidadeMensal.mes, func.sum(FactUnidadeMensal.receita))
            .group_by(FactUnidadeMensal.ano, FactUnidadeMensal.mes)
            .order_by(FactUnidadeMensal.ano, FactUnidadeMensal.mes)
        ).all()
    ]

    cirurgias_por_mes = [
        {"competencia": f"{ano}-{mes:02d}", "cirurgias": cirurgias}
        for ano, mes, cirurgias in db.execute(
            select(FactUnidadeMensal.ano, FactUnidadeMensal.mes, func.sum(FactUnidadeMensal.cirurgias))
            .group_by(FactUnidadeMensal.ano, FactUnidadeMensal.mes)
            .order_by(FactUnidadeMensal.ano, FactUnidadeMensal.mes)
        ).all()
    ]

    receita_por_unidade = [
        {"unidade": unidade, "receita": receita}
        for unidade, receita in db.execute(
            select(FactUnidadeMensal.unidade, func.sum(FactUnidadeMensal.receita))
            .group_by(FactUnidadeMensal.unidade)
            .order_by(func.sum(FactUnidadeMensal.receita).desc())
        ).all()
    ]

    unidades = []
    for unidade, receita, cirurgias, consultas in db.execute(
        select(
            FactUnidadeMensal.unidade,
            func.sum(FactUnidadeMensal.receita),
            func.sum(FactUnidadeMensal.cirurgias),
            func.sum(FactUnidadeMensal.consultas),
        )
        .group_by(FactUnidadeMensal.unidade)
        .order_by(func.sum(FactUnidadeMensal.receita).desc())
    ).all():
        ticket_medio = float(receita or 0) / float(cirurgias or 1)
        eficiencia = (float(cirurgias or 0) / float(consultas or 1)) * 100
        unidades.append(
            {
                "unidade": unidade,
                "receita": float(receita or 0),
                "cirurgias": float(cirurgias or 0),
                "ticket_medio": ticket_medio,
                "eficiencia": eficiencia,
            }
        )

    return {
        "last_update": last["last_update"],
        "status": last["status"],
        "summary": {
            "receita_total": float(receita_total),
            "ebitda": float(financeiro[0] or 0),
            "lucro_liquido": float(financeiro[1] or 0),
            "cirurgias": float(cirurgias_total),
            "ticket_medio": float(receita_total) / float(cirurgias_total or 1),
            "receita_financeira": float(financeiro[2] or 0),
        },
        "receita_por_mes": receita_por_mes,
        "cirurgias_por_mes": cirurgias_por_mes,
        "receita_por_unidade": receita_por_unidade,
        "unidades": unidades,
    }
