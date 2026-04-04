from datetime import UTC, datetime
import re
import unicodedata

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .alerts_service import build_alerts
from .models import FactFinanceiro, FactProducaoProfissional, FactUnidadeMensal, Metadata


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    def _normalize_col_name(col_name: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(col_name)).encode("ascii", "ignore").decode("ascii")
        normalized = normalized.strip().lower().replace("-", "_")
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized

    df = df.copy()
    df.columns = [_normalize_col_name(col) for col in df.columns]
    return df


def _pick_col(
    df: pd.DataFrame,
    options: list[str],
    required: bool = True,
    contains_any: list[str] | None = None,
) -> str | None:
    for col in options:
        if col in df.columns:
            return col

    if contains_any:
        for existing_col in df.columns:
            if any(keyword in existing_col for keyword in contains_any):
                return existing_col

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


def _extract_financial_from_sheets(all_sheets: dict) -> pd.DataFrame:
    """Extrai dados financeiros de abas tipo 'Despesas MÊS ANO' e 'Despesas Totais XXXX'."""
    financial_rows = []
    
    for sheet_name, raw_df in all_sheets.items():
        sheet_lower = sheet_name.lower()
        
        # Processa apenas abas de despesa
        if "despesa" not in sheet_lower:
            continue
        
        # Pular abas vazias
        if len(raw_df) < 3:
            continue
        
        # Tentar extrair competencia do nome da aba
        import re
        match = re.search(r'(\d{4})-?(\d{2})|([A-Z]{3})\s*(\d{4})', sheet_name)
        competencia = None
        if match:
            if match.group(1):  # Formato XXXX-MM
                competencia = f"{match.group(1)}-{match.group(2)}"
            else:  # Formato MÊS XXXX
                month_map = {'JAN': '01', 'FEV': '02', 'MAR': '03', 'ABR': '04', 'MAI': '05',
                            'JUN': '06', 'JUL': '07', 'AGO': '08', 'SET': '09', 'OUT': '10',
                            'NOV': '11', 'DEZ': '12'}
                mes = month_map.get(match.group(3))
                if mes:
                    competencia = f"{match.group(4)}-{mes}"
        
        # Se não extraiu competencia, usar nome da aba como fallback
        if not competencia:
            competencia = sheet_name
        
        # Encontrar linha de header (procura por "Unidade" ou "UNIDADE")
        header_row = None
        for idx, row in raw_df.iterrows():
            row_str = str(row).lower()
            if 'unidade' in row_str or 'faturamento' in row_str or 'ebitda' in row_str:
                header_row = idx
                break
        
        if header_row is None or header_row >= len(raw_df) - 1:
            continue
        
        # Re-ler a aba com header correto
        df = raw_df.iloc[header_row:].copy()
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
        df = _normalize_columns(df)
        
        # Procurar colunas financeiras
        receita_liquida_col = _pick_col(df, ["receita_liquida", "receita liquida"], required=False)
        ebitda_col = _pick_col(df, ["ebitda"], required=False)
        lucro_col = _pick_col(df, ["lucro_liquido", "ll", "lucro liquido"], required=False)
        
        if receita_liquida_col or ebitda_col or lucro_col:
            for _, row in df.iterrows():
                receita_liquida = pd.to_numeric(row.get(receita_liquida_col) if receita_liquida_col else 0, errors='coerce') or 0
                ebitda = pd.to_numeric(row.get(ebitda_col) if ebitda_col else 0, errors='coerce') or 0
                lucro = pd.to_numeric(row.get(lucro_col) if lucro_col else 0, errors='coerce') or 0
                
                if max(receita_liquida, ebitda, lucro) > 0:
                    financial_rows.append({
                        'competencia': competencia,
                        'receita_liquida': receita_liquida,
                        'ebitda': ebitda,
                        'lucro_liquido': lucro,
                    })
    
    return pd.DataFrame(financial_rows) if financial_rows else pd.DataFrame()


def process_excel_and_refresh_database(db: Session, excel_path: str, source_file_name: str, source_file_rev: str):
    all_sheets = pd.read_excel(excel_path, sheet_name=None)
    dfs = []
    
    for sheet_name, raw_df in all_sheets.items():
        raw_df = raw_df.dropna(axis=1, how="all")
        df = _normalize_columns(raw_df).fillna(0)
        
        # Só processar abas que têm as colunas essenciais
        has_unidade = any(col in df.columns for col in ["unidade", "clinica", "filial"])
        has_date_or_period = "data" in df.columns or ("ano" in df.columns and "mes" in df.columns)
        
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
    cirurgias_col = _pick_col(
        df,
        ["cirurgias", "cirurgias_realizadas_no_cc"],
        required=False,
        contains_any=["cirurg", "procedimento"],
    )

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

    # === FACT_UNIDADE_MENSAL: agregar por (unidade, ano, mes) ===
    unidade_df = df.copy()

    if len(unidade_df) > 0:
        unidade_df['ano'] = unidade_df[ano_col].apply(_to_int)
        unidade_df['mes'] = unidade_df[mes_col].apply(_to_int)
        unidade_df['unidade_clean'] = unidade_df[unidade_col].astype(str).str.strip()
        unidade_df['receita'] = pd.to_numeric(unidade_df[receita_col], errors='coerce').fillna(0) if receita_col else 0
        unidade_df['leads'] = pd.to_numeric(unidade_df[leads_col], errors='coerce').fillna(0) if leads_col else 0
        unidade_df['consultas'] = pd.to_numeric(unidade_df[consultas_col], errors='coerce').fillna(0) if consultas_col else 0
        unidade_df['cirurgias'] = pd.to_numeric(unidade_df[cirurgias_col], errors='coerce').fillna(0) if cirurgias_col else 0

        # Agregar por chave única
        agg_dict = {
            'receita': 'sum',
            'leads': 'sum',
            'consultas': 'sum',
            'cirurgias': 'sum',
        }
        grouped = unidade_df.groupby(['unidade_clean', 'ano', 'mes'], as_index=False).agg(agg_dict)
        
        for _, row in grouped.iterrows():
            consultas = max(row['consultas'], 0)
            receita = max(row['receita'], 0)
            item = FactUnidadeMensal(
                unidade=row['unidade_clean'],
                ano=int(row['ano']),
                mes=int(row['mes']),
                receita=receita,
                leads=max(row['leads'], 0),
                consultas=consultas,
                cirurgias=max(row['cirurgias'], 0),
                mes_incompleto=datetime.now(UTC).month == int(row['mes']),
                dados_inconsistentes=consultas == 0 and receita > 0,
            )
            db.add(item)

    # === FACT_PRODUCAO_PROFISSIONAL: agregar por (profissional, unidade, ano, mes) ===
    if profissional_col:
        prof_df = df[df[profissional_col].astype(str).str.strip() != ""].copy()
        prof_df = prof_df[prof_df[profissional_col].astype(str).str.strip() != "0"].copy()
        
        if len(prof_df) > 0:
            prof_df['profissional_clean'] = prof_df[profissional_col].astype(str).str.strip()
            prof_df['unidade_clean'] = prof_df[unidade_col].astype(str).str.strip()
            prof_df['ano'] = prof_df[ano_col].apply(_to_int)
            prof_df['mes'] = prof_df[mes_col].apply(_to_int)
            prof_df['consultas'] = pd.to_numeric(prof_df[consultas_col], errors='coerce').fillna(0) if consultas_col else 0
            prof_df['retornos'] = pd.to_numeric(prof_df[retornos_col], errors='coerce').fillna(0) if retornos_col else 0
            prof_df['cirurgias'] = pd.to_numeric(prof_df[cirurgias_col], errors='coerce').fillna(0) if cirurgias_col else 0

            # Agregar por chave única
            agg_dict = {
                'consultas': 'sum',
                'retornos': 'sum',
                'cirurgias': 'sum',
            }
            grouped = prof_df.groupby(['profissional_clean', 'unidade_clean', 'ano', 'mes'], as_index=False).agg(agg_dict)
            
            for _, row in grouped.iterrows():
                consultas = max(row['consultas'], 0)
                item = FactProducaoProfissional(
                    profissional=row['profissional_clean'],
                    unidade=row['unidade_clean'],
                    ano=int(row['ano']),
                    mes=int(row['mes']),
                    consultas=consultas,
                    retornos=max(row['retornos'], 0),
                    cirurgias=max(row['cirurgias'], 0),
                    mes_incompleto=datetime.now(UTC).month == int(row['mes']),
                    dados_inconsistentes=consultas == 0 and row['cirurgias'] > 0,
                )
                db.add(item)

    # === FACT_FINANCEIRO: de abas operacionais + abas de despesa ===
    fin_df_operational = pd.DataFrame()
    
    # De abas operacionais (se houver competencia + receita_liquida)
    if competencia_col and receita_liquida_col and receita_liquida_col in df.columns:
        fin_df_operational = df[df[receita_liquida_col] != 0].copy()
        if len(fin_df_operational) > 0:
            fin_df_operational['competencia_clean'] = fin_df_operational[competencia_col].astype(str).str.strip()
            fin_df_operational['receita_liquida'] = pd.to_numeric(fin_df_operational[receita_liquida_col], errors='coerce').fillna(0)
            fin_df_operational['ebitda'] = pd.to_numeric(fin_df_operational[ebitda_col], errors='coerce').fillna(0) if ebitda_col else 0
            fin_df_operational['lucro_liquido'] = pd.to_numeric(fin_df_operational[lucro_col], errors='coerce').fillna(0) if lucro_col else 0
            fin_df_operational = fin_df_operational[['competencia_clean', 'receita_liquida', 'ebitda', 'lucro_liquido']]
    
    # De abas de despesa
    fin_df_despesas = _extract_financial_from_sheets(all_sheets)
    
    # Combinar ambas
    if len(fin_df_operational) > 0:
        fin_df_operational.columns = ['competencia', 'receita_liquida', 'ebitda', 'lucro_liquido']
        fin_df_despesas = pd.concat([fin_df_despesas, fin_df_operational], ignore_index=True)
    
    # Agregar por competencia
    if len(fin_df_despesas) > 0:
        grouped = fin_df_despesas.groupby('competencia', as_index=False).agg({
            'receita_liquida': 'sum',
            'ebitda': 'sum',
            'lucro_liquido': 'sum',
        })
        
        for _, row in grouped.iterrows():
            db.add(
                FactFinanceiro(
                    competencia=row['competencia'],
                    receita_liquida=max(row['receita_liquida'], 0),
                    ebitda=row['ebitda'],
                    lucro_liquido=row['lucro_liquido'],
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

    alerts = build_alerts(db)

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
        "alertas": alerts,
    }
