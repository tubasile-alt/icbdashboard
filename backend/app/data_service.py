from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import FactFinanceiro, FactProducaoProfissional, FactUnidadeMensal, Metadata


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
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


def process_excel_and_refresh_database(db: Session, excel_path: str, source_file_name: str, source_file_rev: str):
    all_sheets = pd.read_excel(excel_path, sheet_name=None)
    dfs = []
    
    for sheet_name, raw_df in all_sheets.items():
        raw_df = raw_df.dropna(axis=1, how="all")
        df = _normalize_columns(raw_df).fillna(0)
        
        # Só processar abas que têm as colunas essenciais
        has_unidade = any(col in df.columns for col in ["unidade", "clinica", "filial"])
        has_date_or_period = "data" in df.columns or ("ano" in df.columns and ("mes" in df.columns or "mes" in df.columns))
        
        if len(df) > 0 and has_unidade and has_date_or_period:
            dfs.append(df)
    
    if not dfs:
        raise RuntimeError("Nenhuma aba com dados válidos encontrada no arquivo Excel.")
    
    df = pd.concat(dfs, ignore_index=True)

    unidade_col = _pick_col(df, ["unidade", "clinica", "filial"])
    
    data_col = _pick_col(df, ["data"], required=False)
    if data_col:
        df['ano'] = pd.to_datetime(df[data_col], errors='coerce').dt.year
        df['mes'] = pd.to_datetime(df[data_col], errors='coerce').dt.month
        ano_col = 'ano'
        mes_col = 'mes'
    else:
        ano_col = _pick_col(df, ["ano"])
        mes_col = _pick_col(df, ["mes", "mes"])
    
    receita_col = _pick_col(df, ["valor_dos_servicos", "receita", "receita_base", "faturamento"], required=False)
    leads_col = _pick_col(df, ["leads"], required=False)
    consultas_col = _pick_col(df, ["consultas", "consultas_online"], required=False)
    cirurgias_col = _pick_col(df, ["cirurgias", "cirurgias_realizadas_no_cc"], required=False)

    profissional_col = _pick_col(df, ["profissional", "medico"], required=False)
    retornos_col = _pick_col(df, ["retornos", "retornos_online"], required=False)

    competencia_col = _pick_col(df, ["competencia", "competencia"], required=False)
    receita_liquida_col = _pick_col(df, ["receita_liquida", "dre_receita_liquida"], required=False)
    ebitda_col = _pick_col(df, ["ebitda", "dre_ebitda"], required=False)
    lucro_col = _pick_col(df, ["lucro_liquido", "dre_lucro_liquido"], required=False)

    # Estratégia de update completo
    db.execute(delete(FactUnidadeMensal))
    db.execute(delete(FactProducaoProfissional))
    db.execute(delete(FactFinanceiro))

    # Linha com receita entra em fact_unidade_mensal
    if receita_col:
        unidade_df = df[df[receita_col] != 0].copy()
    else:
        unidade_df = df.copy()

    for _, row in unidade_df.iterrows():
        receita = max(float(row.get(receita_col, 0) or 0), 0)
        consultas = max(float(row.get(consultas_col, 0) or 0), 0)
        cirurgias = max(float(row.get(cirurgias_col, 0) or 0), 0)
        item = FactUnidadeMensal(
            unidade=str(row.get(unidade_col, "")).strip(),
            ano=_to_int(row.get(ano_col)),
            mes=_to_int(row.get(mes_col)),
            receita=receita,
            leads=max(float(row.get(leads_col, 0) or 0), 0),
            consultas=consultas,
            cirurgias=cirurgias,
            mes_incompleto=datetime.now(UTC).month == _to_int(row.get(mes_col)),
            dados_inconsistentes=consultas == 0 and receita > 0,
        )
        db.add(item)

    # Linha com produção entra em fact_producao_profissional
    if profissional_col:
        prof_df = df[df[profissional_col].astype(str).str.strip() != "0"].copy()
        prof_df = prof_df[prof_df[profissional_col].astype(str).str.strip() != ""]
        for _, row in prof_df.iterrows():
            consultas = max(float(row.get(consultas_col, 0) or 0), 0)
            item = FactProducaoProfissional(
                profissional=str(row.get(profissional_col, "")).strip(),
                unidade=str(row.get(unidade_col, "")).strip(),
                ano=_to_int(row.get(ano_col)),
                mes=_to_int(row.get(mes_col)),
                consultas=consultas,
                retornos=max(float(row.get(retornos_col, 0) or 0), 0),
                cirurgias=max(float(row.get(cirurgias_col, 0) or 0), 0),
                mes_incompleto=datetime.now(UTC).month == _to_int(row.get(mes_col)),
                dados_inconsistentes=consultas == 0 and float(row.get(cirurgias_col, 0) or 0) > 0,
            )
            db.add(item)

    # Financeiro separado (nunca misturar com base operacional)
    if competencia_col and receita_liquida_col:
        fin_df = df[df[receita_liquida_col] != 0].copy()
        for _, row in fin_df.iterrows():
            db.add(
                FactFinanceiro(
                    competencia=str(row.get(competencia_col, "")).strip(),
                    receita_liquida=max(float(row.get(receita_liquida_col, 0) or 0), 0),
                    ebitda=float(row.get(ebitda_col, 0) or 0),
                    lucro_liquido=float(row.get(lucro_col, 0) or 0),
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
