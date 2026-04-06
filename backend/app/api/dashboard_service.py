from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..alerts_service import build_alerts
from ..services.unidade_status_service import get_unidades_ativas_para_metricas
from ..models import FactFinanceiroMensal, FactFiscalMensal, FactProducaoProfissionalMensal, FactUnidadeMensal, Metadata


def _safe_float(value, default: float = 0.0) -> float:
    try:
        v = float(value)
        return default if (math.isnan(v) or math.isinf(v)) else v
    except (TypeError, ValueError):
        return default


def _status_from_timestamp(last_update: datetime | None, stale_threshold_hours: int) -> str:
    if not last_update:
        return "desatualizado"
    elapsed_hours = (datetime.now(timezone.utc) - last_update.replace(tzinfo=timezone.utc)).total_seconds() / 3600
    if elapsed_hours < 1:
        return "atualizado"
    if elapsed_hours <= stale_threshold_hours:
        return "atencao"
    return "desatualizado"


def _apply_filters(query, model, filters: dict):
    if filters.get("anos"):
        query = query.where(model.ano.in_(filters["anos"]))
    if filters.get("meses"):
        query = query.where(model.mes.in_(filters["meses"]))
    if filters.get("competencias"):
        query = query.where(model.competencia.in_(filters["competencias"]))
    if filters.get("unidades") and hasattr(model, "unidade"):
        query = query.where(model.unidade.in_(filters["unidades"]))
    return query

def _apply_metric_units_scope(query, db: Session, unidade_field):
    unidades_ativas = get_unidades_ativas_para_metricas(db)
    if not unidades_ativas:
        return query
    return query.where(unidade_field.in_(unidades_ativas))




def get_last_update_status(db: Session, stale_threshold_hours: int) -> dict:
    metadata = db.get(Metadata, 1)
    if not metadata:
        return {"last_update": None, "status": "desatualizado", "source_file_name": None, "source_file_last_modified": None}
    return {
        "last_update": metadata.dashboard_last_update.isoformat(),
        "status": _status_from_timestamp(metadata.dashboard_last_update, stale_threshold_hours),
        "source_file_name": metadata.source_file_name,
        "source_file_last_modified": metadata.source_file_last_modified,
    }


def get_dashboard_summary(db: Session, filters: dict) -> dict:
    q_oper = select(
        func.coalesce(func.sum(FactUnidadeMensal.receita_operacional), 0),
        func.coalesce(func.sum(FactUnidadeMensal.leads), 0),
        func.coalesce(func.sum(FactUnidadeMensal.consultas_totais), 0),
        func.coalesce(func.sum(FactUnidadeMensal.cirurgias), 0),
    )
    q_oper = _apply_filters(q_oper, FactUnidadeMensal, filters)
    q_oper = _apply_metric_units_scope(q_oper, db, FactUnidadeMensal.unidade)
    receita_operacional, leads, consultas, cirurgias = db.execute(q_oper).one()

    q_fin = select(
        func.coalesce(func.sum(FactFinanceiroMensal.receita_bruta), 0),
        func.coalesce(func.sum(FactFinanceiroMensal.receita_liquida), 0),
        func.coalesce(func.sum(FactFinanceiroMensal.ebitda), 0),
        func.coalesce(func.avg(FactFinanceiroMensal.margem_ebitda), 0),
        func.coalesce(func.sum(FactFinanceiroMensal.lucro_liquido), 0),
        func.coalesce(func.avg(FactFinanceiroMensal.margem_liquida), 0),
    )
    q_fin = _apply_filters(q_fin, FactFinanceiroMensal, filters)
    q_fin = q_fin.where(FactFinanceiroMensal.unidade_ref != "__CONSOLIDADO__")
    q_fin = _apply_metric_units_scope(q_fin, db, FactFinanceiroMensal.unidade_ref)
    receita_bruta, receita_liquida, ebitda, margem_ebitda, lucro_liquido, margem_liquida = db.execute(q_fin).one()

    q_fiscal = select(func.coalesce(func.avg(FactFiscalMensal.percentual_nf), 0))
    q_fiscal = _apply_filters(q_fiscal, FactFiscalMensal, filters)
    percentual_nf = db.scalar(q_fiscal) or 0

    leads_f = _safe_float(leads)
    consultas_f = _safe_float(consultas)
    cirurgias_f = _safe_float(cirurgias)
    receita_f = _safe_float(receita_operacional)

    return {
        "funil": {
            "leads": leads_f,
            "consultas": consultas_f,
            "cirurgias": cirurgias_f,
            "conv_lead_consulta": _safe_float(consultas_f / leads_f if leads_f else 0),
            "conv_consulta_cirurgia": _safe_float(cirurgias_f / consultas_f if consultas_f else 0),
        },
        "eficiencia": {
            "receita_por_lead": _safe_float(receita_f / leads_f if leads_f else 0),
            "receita_por_consulta": _safe_float(receita_f / consultas_f if consultas_f else 0),
            "cirurgias_por_consulta": _safe_float(cirurgias_f / consultas_f if consultas_f else 0),
            "ticket_medio_cirurgia": _safe_float(receita_f / cirurgias_f if cirurgias_f else 0),
        },
        "operacional": {"receita_operacional": receita_f},
        "financeiro": {
            "receita_bruta": _safe_float(receita_bruta),
            "receita_liquida": _safe_float(receita_liquida),
            "ebitda": _safe_float(ebitda),
            "margem_ebitda": _safe_float(margem_ebitda),
            "lucro_liquido": _safe_float(lucro_liquido),
            "margem_liquida": _safe_float(margem_liquida),
        },
        "fiscal": {"percentual_nf": _safe_float(percentual_nf)},
    }


def get_unidades_dashboard(db: Session, filters: dict) -> list[dict]:
    q = select(
        FactUnidadeMensal.unidade,
        func.sum(FactUnidadeMensal.receita_operacional),
        func.sum(FactUnidadeMensal.leads),
        func.sum(FactUnidadeMensal.consultas_totais),
        func.sum(FactUnidadeMensal.cirurgias),
        func.bool_or(FactUnidadeMensal.mes_incompleto),
        func.bool_or(FactUnidadeMensal.dados_inconsistentes),
    ).group_by(FactUnidadeMensal.unidade)
    q = _apply_filters(q, FactUnidadeMensal, filters)
    q = _apply_metric_units_scope(q, db, FactUnidadeMensal.unidade)
    rows = db.execute(q.order_by(func.sum(FactUnidadeMensal.receita_operacional).desc())).all()

    result = []
    for unidade, receita, leads, consultas, cirurgias, mes_incompleto, inconsistente in rows:
        result.append(
            {
                "unidade": unidade,
                "receita_operacional": _safe_float(receita),
                "leads": _safe_float(leads),
                "consultas_totais": _safe_float(consultas),
                "cirurgias": _safe_float(cirurgias),
                "ticket_medio_cirurgia": _safe_float(_safe_float(receita) / _safe_float(cirurgias)) if cirurgias else 0,
                "conv_consulta_cirurgia": _safe_float(_safe_float(cirurgias) / _safe_float(consultas)) if consultas else 0,
                "receita_por_consulta": _safe_float(_safe_float(receita) / _safe_float(consultas)) if consultas else 0,
                "mes_incompleto": bool(mes_incompleto),
                "dados_inconsistentes": bool(inconsistente),
            }
        )
    return result


def get_profissionais_dashboard(db: Session, filters: dict) -> list[dict]:
    q = select(
        FactProducaoProfissionalMensal.profissional,
        FactProducaoProfissionalMensal.unidade,
        func.sum(FactProducaoProfissionalMensal.consultas_totais),
        func.sum(FactProducaoProfissionalMensal.retornos_totais),
        func.sum(FactProducaoProfissionalMensal.cirurgias),
        func.bool_or(FactProducaoProfissionalMensal.mes_incompleto),
        func.bool_or(FactProducaoProfissionalMensal.dados_inconsistentes),
    ).group_by(FactProducaoProfissionalMensal.profissional, FactProducaoProfissionalMensal.unidade)

    q = _apply_filters(q, FactProducaoProfissionalMensal, filters)
    q = _apply_metric_units_scope(q, db, FactProducaoProfissionalMensal.unidade)
    if filters.get("profissionais"):
        q = q.where(FactProducaoProfissionalMensal.profissional.in_(filters["profissionais"]))

    rows = db.execute(q.order_by(func.sum(FactProducaoProfissionalMensal.cirurgias).desc())).all()
    return [
        {
            "profissional": p,
            "unidade": u,
            "consultas_totais": _safe_float(c),
            "retornos_totais": _safe_float(r),
            "cirurgias": _safe_float(s),
            "mes_incompleto": bool(mi),
            "dados_inconsistentes": bool(di),
        }
        for p, u, c, r, s, mi, di in rows
    ]


def get_financeiro_dashboard(db: Session, filters: dict) -> dict:
    q = select(
        FactFinanceiroMensal.competencia,
        func.sum(FactFinanceiroMensal.ebitda),
        func.sum(FactFinanceiroMensal.lucro_liquido),
    ).group_by(FactFinanceiroMensal.competencia).order_by(FactFinanceiroMensal.competencia)

    q = _apply_filters(q, FactFinanceiroMensal, filters)
    series = [{"competencia": c, "ebitda": _safe_float(e), "lucro_liquido": _safe_float(l)} for c, e, l in db.execute(q).all()]
    return {"serie": series}


def get_fiscal_dashboard(db: Session, filters: dict) -> dict:
    q = select(FactFiscalMensal.competencia, func.avg(FactFiscalMensal.percentual_nf)).group_by(FactFiscalMensal.competencia).order_by(FactFiscalMensal.competencia)
    q = _apply_filters(q, FactFiscalMensal, filters)
    series = [{"competencia": c, "percentual_nf": _safe_float(p)} for c, p in db.execute(q).all()]
    return {"serie": series}


def get_alertas_dashboard(db: Session, filters: dict) -> list[dict]:
    del filters
    return build_alerts(db)


def get_filter_options(db: Session) -> dict:
    anos_op = [int(r[0]) for r in db.execute(select(FactUnidadeMensal.ano).distinct().order_by(FactUnidadeMensal.ano)).all()]
    meses_op = [int(r[0]) for r in db.execute(select(FactUnidadeMensal.mes).distinct().order_by(FactUnidadeMensal.mes)).all()]
    competencias_op = [r[0] for r in db.execute(select(FactUnidadeMensal.competencia).distinct().order_by(FactUnidadeMensal.competencia)).all()]
    competencias_fin = [r[0] for r in db.execute(select(FactFinanceiroMensal.competencia).distinct().order_by(FactFinanceiroMensal.competencia)).all()]
    competencias_fisc = [r[0] for r in db.execute(select(FactFiscalMensal.competencia).distinct().order_by(FactFiscalMensal.competencia)).all()]

    all_competencias = sorted(set(competencias_op + competencias_fin + competencias_fisc))
    all_anos: set[int] = set(anos_op)
    all_meses: set[int] = set(meses_op)
    for comp in all_competencias:
        parts = str(comp).split("-")
        if len(parts) == 2:
            try:
                all_anos.add(int(parts[0]))
                all_meses.add(int(parts[1]))
            except ValueError:
                pass

    unidades = [r[0] for r in db.execute(select(FactUnidadeMensal.unidade).distinct().order_by(FactUnidadeMensal.unidade)).all()]
    profissionais = [r[0] for r in db.execute(select(FactProducaoProfissionalMensal.profissional).distinct().order_by(FactProducaoProfissionalMensal.profissional)).all()]

    return {
        "anos": sorted(all_anos),
        "meses": sorted(all_meses),
        "competencias": all_competencias,
        "unidades": unidades,
        "profissionais": profissionais,
    }
