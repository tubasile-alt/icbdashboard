from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..alerts_service import build_alerts
from ..services.unidade_status_service import get_unidades_ativas_para_metricas
from ..models import FactFinanceiroMensal, FactFiscalMensal, FactProducaoProfissionalMensal, FactUnidadeMensal, Metadata, UnidadeStatus


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
    q_fiscal = q_fiscal.where(FactFiscalMensal.unidade_ref != "__CONSOLIDADO__")
    q_fiscal = _apply_metric_units_scope(q_fiscal, db, FactFiscalMensal.unidade_ref)
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


def _parse_competencia(comp: str | None) -> tuple[int, int] | None:
    if not comp:
        return None
    parts = str(comp).split("-")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _shift_competencia(comp: str, months_delta: int) -> str | None:
    parsed = _parse_competencia(comp)
    if not parsed:
        return None
    ano, mes = parsed
    idx = ano * 12 + (mes - 1) + months_delta
    if idx < 0:
        return None
    target_ano = idx // 12
    target_mes = idx % 12 + 1
    return f"{target_ano}-{target_mes:02d}"


def _format_period_label(comp: str | None) -> str:
    if not comp:
        return "Período indisponível"
    parsed = _parse_competencia(comp)
    if not parsed:
        return str(comp)
    ano, mes = parsed
    quarter = ((mes - 1) // 3) + 1
    return f"Q{quarter} {ano}"


def _fin_dict_from_row(row) -> dict:
    if not row:
        return {
            "receita_bruta": None,
            "receita_liquida": None,
            "custos_despesas": None,
            "ebitda": None,
            "lucro_liquido": None,
        }
    receita_bruta = _safe_float(getattr(row, "receita_bruta", 0))
    receita_liquida = _safe_float(getattr(row, "receita_liquida", 0))
    custos = _safe_float(getattr(row, "custos", 0))
    despesas = _safe_float(getattr(row, "despesas", 0))
    ebitda = _safe_float(getattr(row, "ebitda", 0))
    ll = _safe_float(getattr(row, "lucro_liquido", 0))
    return {
        "receita_bruta": receita_bruta,
        "receita_liquida": receita_liquida,
        "custos_despesas": custos + despesas,
        "ebitda": ebitda,
        "lucro_liquido": ll,
    }


def _variation(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return _safe_float((current - previous) / abs(previous))


def get_executive_report(db: Session, filters: dict, stale_threshold_hours: int) -> dict:
    summary = get_dashboard_summary(db, filters)
    alertas = build_alerts(db)
    unidades_dashboard = get_unidades_dashboard(db, filters)
    last_update = get_last_update_status(db, stale_threshold_hours)
    unidades_status = list(db.execute(select(UnidadeStatus)).scalars().all())

    q_latest_comp = select(func.max(FactFinanceiroMensal.competencia))
    q_latest_comp = _apply_filters(q_latest_comp, FactFinanceiroMensal, filters)
    q_latest_comp = q_latest_comp.where(FactFinanceiroMensal.unidade_ref == "__CONSOLIDADO__")
    latest_comp = db.scalar(q_latest_comp)

    period_title = _format_period_label(latest_comp)
    qoq_comp = _shift_competencia(latest_comp, -3) if latest_comp else None
    yoy_comp = _shift_competencia(latest_comp, -12) if latest_comp else None

    def _get_financial_for_comp(comp: str | None):
        if not comp:
            return None
        q = select(
            func.sum(FactFinanceiroMensal.receita_bruta).label("receita_bruta"),
            func.sum(FactFinanceiroMensal.receita_liquida).label("receita_liquida"),
            func.sum(FactFinanceiroMensal.custos).label("custos"),
            func.sum(FactFinanceiroMensal.despesas).label("despesas"),
            func.sum(FactFinanceiroMensal.ebitda).label("ebitda"),
            func.sum(FactFinanceiroMensal.lucro_liquido).label("lucro_liquido"),
        ).where(
            and_(
                FactFinanceiroMensal.competencia == comp,
                FactFinanceiroMensal.unidade_ref == "__CONSOLIDADO__",
            )
        )
        return db.execute(q).one()

    fin_current = _fin_dict_from_row(_get_financial_for_comp(latest_comp))
    fin_qoq = _fin_dict_from_row(_get_financial_for_comp(qoq_comp))
    fin_yoy = _fin_dict_from_row(_get_financial_for_comp(yoy_comp))

    dre_rows = []
    for key, label in (
        ("receita_liquida", "Receita Líquida"),
        ("custos_despesas", "Custos & Despesas"),
        ("ebitda", "EBITDA"),
        ("lucro_liquido", "Lucro Líquido"),
    ):
        current_value = fin_current[key]
        qoq_value = _variation(current_value, fin_qoq[key])
        yoy_value = _variation(current_value, fin_yoy[key])
        dre_rows.append(
            {
                "linha": label,
                "valor_atual": current_value,
                "variacao_qoq": qoq_value,
                "variacao_yoy": yoy_value,
                "tem_qoq": qoq_value is not None,
                "tem_yoy": yoy_value is not None,
            }
        )

    status_map = {item.unidade: item for item in unidades_status}
    risco_counts = {"saudaveis": 0, "atencao": 0, "risco": 0, "encerradas": 0}
    avaliacao_fechamento: list[dict] = []

    q_fin_unidade = select(
        FactFinanceiroMensal.unidade_ref,
        func.sum(FactFinanceiroMensal.receita_bruta).label("receita_bruta"),
        func.sum(FactFinanceiroMensal.ebitda).label("ebitda"),
        func.sum(FactFinanceiroMensal.lucro_liquido).label("lucro_liquido"),
    ).where(FactFinanceiroMensal.unidade_ref != "__CONSOLIDADO__")
    q_fin_unidade = _apply_filters(q_fin_unidade, FactFinanceiroMensal, filters).group_by(FactFinanceiroMensal.unidade_ref)
    rows_fin_unidade = db.execute(q_fin_unidade).all()
    fin_by_unit = {
        str(row.unidade_ref): {
            "receita_bruta": _safe_float(row.receita_bruta),
            "ebitda": _safe_float(row.ebitda),
            "lucro_liquido": _safe_float(row.lucro_liquido),
            "margem_estimada": _safe_float(row.lucro_liquido) / _safe_float(row.receita_bruta) if _safe_float(row.receita_bruta) else None,
        }
        for row in rows_fin_unidade
    }
    critical_units = set()
    for item in alertas.get("items", []):
        if item.get("nivel") == "critico":
            for unidade in item.get("unidades", []):
                critical_units.add(unidade)

    for unidade_row in unidades_dashboard:
        unidade = unidade_row.get("unidade")
        status_item = status_map.get(unidade)
        status = status_item.status if status_item else "ativa"
        fin = fin_by_unit.get(unidade, {})
        margem = fin.get("margem_estimada")
        has_critical = unidade in critical_units
        if status == "encerrada":
            risco_counts["encerradas"] += 1
            continue
        if has_critical or (margem is not None and margem < 0):
            bucket = "risco"
        elif status in {"suspensa", "em_reestruturacao"}:
            bucket = "atencao"
        else:
            bucket = "saudaveis"
        risco_counts[bucket] += 1

        low_revenue = fin.get("receita_bruta", 0) < 50000 if fin else False
        recurrent_negative = fin.get("ebitda", 0) < 0 if fin else False
        if status in {"suspensa", "em_reestruturacao"} or low_revenue or recurrent_negative or has_critical:
            avaliacao_fechamento.append(
                {
                    "unidade": unidade,
                    "status": status,
                    "ebitda": fin.get("ebitda"),
                    "receita_bruta": fin.get("receita_bruta"),
                    "motivo": "Status sensível ou performance financeira crítica",
                }
            )

    filtered_unidades = [u for u in unidades_dashboard if u.get("unidade") in get_unidades_ativas_para_metricas(db)]
    ranking_source = []
    for unidade_row in filtered_unidades:
        unidade = unidade_row.get("unidade")
        fin = fin_by_unit.get(unidade, {})
        ebitda = fin.get("ebitda")
        ll = fin.get("lucro_liquido")
        receita = fin.get("receita_bruta")
        if ebitda is not None and abs(ebitda) > 0:
            principal = ebitda
            metrica = "ebitda"
        elif ll is not None and abs(ll) > 0:
            principal = ll
            metrica = "lucro_liquido"
        else:
            principal = receita if receita is not None else unidade_row.get("receita_operacional", 0)
            metrica = "receita_bruta" if receita is not None else "receita_operacional"
        ranking_source.append(
            {
                "unidade": unidade,
                "valor": _safe_float(principal),
                "metrica": metrica,
            }
        )
    ranking_sorted = sorted(ranking_source, key=lambda item: item["valor"], reverse=True)

    conversion_rows = [u for u in filtered_unidades if _safe_float(u.get("conv_consulta_cirurgia", 0)) > 0]
    conversao_media = (
        _safe_float(sum(_safe_float(u.get("conv_consulta_cirurgia", 0)) for u in conversion_rows) / len(conversion_rows))
        if conversion_rows
        else 0
    )
    unidade_critica_conv = min(conversion_rows, key=lambda u: _safe_float(u.get("conv_consulta_cirurgia", 0)), default=None)
    ticket_rows = [u for u in filtered_unidades if _safe_float(u.get("ticket_medio_cirurgia", 0)) > 0]
    ticket_medio = (
        _safe_float(sum(_safe_float(u.get("ticket_medio_cirurgia", 0)) for u in ticket_rows) / len(ticket_rows))
        if ticket_rows
        else 0
    )
    unidade_ticket_abaixo = min(ticket_rows, key=lambda u: _safe_float(u.get("ticket_medio_cirurgia", 0)), default=None)

    data_quality_flags = []
    if any(u.get("mes_incompleto") for u in unidades_dashboard):
        data_quality_flags.append("Há unidades com mês incompleto na visão selecionada.")
    if any(u.get("dados_inconsistentes") for u in unidades_dashboard):
        data_quality_flags.append("Há registros com inconsistência detectada no ETL.")
    if not latest_comp:
        data_quality_flags.append("Base financeira indisponível para o período selecionado.")

    return {
        "header": {
            "title": f"Painel Executivo — {period_title}",
            "subtitle": "Uso interno · Confidencial",
            "last_update": last_update.get("last_update"),
            "status": last_update.get("status"),
            "periodo_referencia": latest_comp,
        },
        "resumo_executivo": {
            "receita_bruta": summary["financeiro"]["receita_bruta"],
            "ebitda": summary["financeiro"]["ebitda"],
            "lucro_liquido": summary["financeiro"]["lucro_liquido"],
            "saude_rede": risco_counts,
            "variacao_qoq": {
                "receita_bruta": _variation(summary["financeiro"]["receita_bruta"], fin_qoq.get("receita_bruta")),
                "ebitda": _variation(summary["financeiro"]["ebitda"], fin_qoq.get("ebitda")),
                "lucro_liquido": _variation(summary["financeiro"]["lucro_liquido"], fin_qoq.get("lucro_liquido")),
            },
            "variacao_yoy": {
                "receita_bruta": _variation(summary["financeiro"]["receita_bruta"], fin_yoy.get("receita_bruta")),
                "ebitda": _variation(summary["financeiro"]["ebitda"], fin_yoy.get("ebitda")),
                "lucro_liquido": _variation(summary["financeiro"]["lucro_liquido"], fin_yoy.get("lucro_liquido")),
            },
        },
        "alertas": {
            "summary": alertas.get("summary", {}),
            "items": alertas.get("items", []),
            "avaliacao_fechamento": sorted(avaliacao_fechamento, key=lambda x: x.get("ebitda", 0))[:8],
        },
        "dre_consolidada": {
            "competencia_atual": latest_comp,
            "competencia_qoq": qoq_comp,
            "competencia_yoy": yoy_comp,
            "linhas": dre_rows,
        },
        "ranking": {
            "top_5": ranking_sorted[:5],
            "bottom_5": list(reversed(ranking_sorted[-5:])),
            "regra_fallback": "Ranking usa EBITDA; se indisponível/zero usa Lucro Líquido; por último Receita Operacional.",
        },
        "pipeline_financeiro": {
            "leads_ativos": summary["funil"]["leads"],
            "cirurgias_esperadas": summary["funil"]["cirurgias"],
            "potencial_receita": summary["operacional"]["receita_operacional"],
            "metodo": "Provisório: inferido dos dados operacionais agregados (leads/cirurgias/receita operacional).",
        },
        "indicadores_operacionais": {
            "conversao_media_rede": conversao_media,
            "unidade_critica_conversao": {
                "unidade": unidade_critica_conv.get("unidade") if unidade_critica_conv else None,
                "valor": unidade_critica_conv.get("conv_consulta_cirurgia") if unidade_critica_conv else None,
            },
            "ticket_medio_rede": ticket_medio,
            "unidade_ticket_abaixo": {
                "unidade": unidade_ticket_abaixo.get("unidade") if unidade_ticket_abaixo else None,
                "valor": unidade_ticket_abaixo.get("ticket_medio_cirurgia") if unidade_ticket_abaixo else None,
            },
        },
        "qualidade_dados": {
            "flags": data_quality_flags,
            "fonte": {
                "source_file_name": last_update.get("source_file_name"),
                "source_file_last_modified": last_update.get("source_file_last_modified"),
            },
            "observacoes": [
                "Comparativos QoQ/YoY exibem 'n/d' quando não há histórico suficiente.",
                "Rankings excluem unidades marcadas com excluir_de_medias=True.",
            ],
        },
    }
