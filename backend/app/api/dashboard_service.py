from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import FactFinanceiroMensal, FactFiscalMensal, FactProducaoProfissionalMensal, FactUnidadeMensal, Metadata


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
    receita_bruta, receita_liquida, ebitda, margem_ebitda, lucro_liquido, margem_liquida = db.execute(q_fin).one()

    q_fiscal = select(func.coalesce(func.avg(FactFiscalMensal.percentual_nf), 0))
    q_fiscal = _apply_filters(q_fiscal, FactFiscalMensal, filters)
    percentual_nf = db.scalar(q_fiscal) or 0

    return {
        "funil": {
            "leads": float(leads),
            "consultas": float(consultas),
            "cirurgias": float(cirurgias),
            "conv_lead_consulta": float((consultas / leads) if leads else 0),
            "conv_consulta_cirurgia": float((cirurgias / consultas) if consultas else 0),
        },
        "eficiencia": {
            "receita_por_lead": float((receita_operacional / leads) if leads else 0),
            "receita_por_consulta": float((receita_operacional / consultas) if consultas else 0),
            "cirurgias_por_consulta": float((cirurgias / consultas) if consultas else 0),
            "ticket_medio_cirurgia": float((receita_operacional / cirurgias) if cirurgias else 0),
        },
        "operacional": {"receita_operacional": float(receita_operacional)},
        "financeiro": {
            "receita_bruta": float(receita_bruta),
            "receita_liquida": float(receita_liquida),
            "ebitda": float(ebitda),
            "margem_ebitda": float(margem_ebitda),
            "lucro_liquido": float(lucro_liquido),
            "margem_liquida": float(margem_liquida),
        },
        "fiscal": {"percentual_nf": float(percentual_nf)},
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
    rows = db.execute(q.order_by(func.sum(FactUnidadeMensal.receita_operacional).desc())).all()

    result = []
    for unidade, receita, leads, consultas, cirurgias, mes_incompleto, inconsistente in rows:
        result.append(
            {
                "unidade": unidade,
                "receita_operacional": float(receita or 0),
                "leads": float(leads or 0),
                "consultas_totais": float(consultas or 0),
                "cirurgias": float(cirurgias or 0),
                "ticket_medio_cirurgia": float((receita or 0) / cirurgias) if cirurgias else 0,
                "conv_consulta_cirurgia": float((cirurgias or 0) / consultas) if consultas else 0,
                "receita_por_consulta": float((receita or 0) / consultas) if consultas else 0,
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
    if filters.get("profissionais"):
        q = q.where(FactProducaoProfissionalMensal.profissional.in_(filters["profissionais"]))

    rows = db.execute(q.order_by(func.sum(FactProducaoProfissionalMensal.cirurgias).desc())).all()
    return [
        {
            "profissional": p,
            "unidade": u,
            "consultas_totais": float(c or 0),
            "retornos_totais": float(r or 0),
            "cirurgias": float(s or 0),
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
    series = [{"competencia": c, "ebitda": float(e or 0), "lucro_liquido": float(l or 0)} for c, e, l in db.execute(q).all()]
    return {"serie": series}


def get_fiscal_dashboard(db: Session, filters: dict) -> dict:
    q = select(FactFiscalMensal.competencia, func.avg(FactFiscalMensal.percentual_nf)).group_by(FactFiscalMensal.competencia).order_by(FactFiscalMensal.competencia)
    q = _apply_filters(q, FactFiscalMensal, filters)
    series = [{"competencia": c, "percentual_nf": float(p or 0)} for c, p in db.execute(q).all()]
    return {"serie": series}
