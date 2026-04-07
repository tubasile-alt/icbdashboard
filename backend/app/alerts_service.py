from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .alerts_catalog import get_catalog, get_catalog_index
from .models import FactFinanceiroMensal, FactFiscalMensal, FactUnidadeMensal


@dataclass
class Alerta:
    nivel: str
    categoria: str
    titulo: str
    detalhe: str
    unidades: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "nivel": self.nivel,
            "categoria": self.categoria,
            "titulo": self.titulo,
            "detalhe": self.detalhe,
            "unidades": self.unidades,
        }


@dataclass
class AlertaItem:
    alert_id: int
    categoria: str
    nivel: str
    titulo: str
    detalhe: str
    threshold: str
    impacto: str
    dado_base: str
    competencia_ref: str | None
    unidades: list[str] = field(default_factory=list)
    metricas: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "categoria": self.categoria,
            "nivel": self.nivel,
            "titulo": self.titulo,
            "detalhe": self.detalhe,
            "threshold": self.threshold,
            "impacto": self.impacto,
            "dado_base": self.dado_base,
            "competencia_ref": self.competencia_ref,
            "unidades": self.unidades,
            "metricas": self.metricas,
        }


def build_alerts(db: Session) -> dict:
    catalog = get_catalog()
    catalog_idx = get_catalog_index()

    items: list[AlertaItem] = []
    items += _alerta_3_ebitda_negativo_2m(db, catalog_idx)
    items += _alerta_5_cirurgia_zero_mes_fechado(db, catalog_idx)
    items += _alerta_9_nf_abaixo_65(db, catalog_idx)
    items += _alerta_10_nf_acima_100(db, catalog_idx)
    items += _alerta_13_saiu_do_vermelho(db, catalog_idx)

    ordem = {"critico": 0, "atencao": 1, "info": 2, "positivo": 3}
    items.sort(key=lambda a: (ordem.get(a.nivel, 9), a.alert_id))

    legacy_alertas = [
        Alerta(
            nivel=i.nivel,
            categoria=i.categoria,
            titulo=i.titulo,
            detalhe=i.detalhe,
            unidades=i.unidades,
        ).to_dict()
        for i in items
    ]

    summary = {
        "critico": sum(1 for i in items if i.nivel == "critico"),
        "atencao": sum(1 for i in items if i.nivel == "atencao"),
        "info": sum(1 for i in items if i.nivel == "info" and i.categoria != "positivo"),
        "positivo": sum(1 for i in items if i.categoria == "positivo"),
    }

    return {
        "alertas": legacy_alertas,
        "summary": summary,
        "items": [i.to_dict() for i in items],
        "catalogo": [
            {
                "id": c["id"],
                "categoria": c["categoria"],
                "nivel": c["nivel"],
                "titulo": c["titulo"],
                "ativo_no_sistema": c["ativo_no_sistema"],
            }
            for c in catalog
        ],
    }


def _competencia_to_key(competencia: str) -> tuple[int, int]:
    ano_str, mes_str = str(competencia).split("-")
    return int(ano_str), int(mes_str)


def _previous_competencia(competencia: str) -> str:
    ano, mes = _competencia_to_key(competencia)
    if mes == 1:
        return f"{ano - 1}-12"
    return f"{ano}-{mes - 1:02d}"


def _latest_closed_operational_competencia(db: Session) -> str | None:
    rows = db.execute(
        select(FactUnidadeMensal.competencia, FactUnidadeMensal.mes_incompleto)
        .order_by(FactUnidadeMensal.ano.desc(), FactUnidadeMensal.mes.desc())
    ).all()
    for competencia, mes_incompleto in rows:
        if not mes_incompleto:
            return str(competencia)
    return None


def _alerta_3_ebitda_negativo_2m(db: Session, catalog_idx: dict) -> list[AlertaItem]:
    meta = catalog_idx[3]

    rows = db.execute(
        select(
            FactFinanceiroMensal.unidade_ref,
            FactFinanceiroMensal.competencia,
            FactFinanceiroMensal.ebitda,
            FactFinanceiroMensal.margem_ebitda,
        )
        .where(FactFinanceiroMensal.unidade_ref != "__CONSOLIDADO__")
        .order_by(FactFinanceiroMensal.unidade_ref, FactFinanceiroMensal.ano, FactFinanceiroMensal.mes)
    ).all()
    if not rows:
        return []

    by_unidade: dict[str, list[tuple[str, float, float]]] = {}
    for unidade, competencia, ebitda, margem in rows:
        by_unidade.setdefault(str(unidade), []).append((str(competencia), float(ebitda or 0), float(margem or 0)))

    afetadas: list[str] = []
    competencia_ref = None
    valores: list[float] = []

    for unidade, serie in by_unidade.items():
        if len(serie) < 2:
            continue
        penult = serie[-2]
        atual = serie[-1]
        neg_penult = penult[1] < 0 or penult[2] < 0
        neg_atual = atual[1] < 0 or atual[2] < 0
        if neg_penult and neg_atual:
            afetadas.append(unidade)
            competencia_ref = atual[0]
            valores.append(atual[1])

    if not afetadas:
        return []

    return [
        AlertaItem(
            alert_id=3,
            categoria=meta.categoria,
            nivel=meta.nivel,
            titulo=meta.titulo,
            detalhe=(
                f"{len(afetadas)} unidade(s) com dois meses seguidos de EBITDA/margem EBITDA negativos "
                f"na competência mais recente disponível."
            ),
            threshold=meta.threshold,
            impacto=meta.impacto,
            dado_base=meta.dado_base,
            competencia_ref=competencia_ref,
            unidades=sorted(afetadas),
            metricas={
                "valor_atual": min(valores) if valores else None,
                "valor_referencia": 0,
                "variacao": None,
            },
        )
    ]


def _alerta_5_cirurgia_zero_mes_fechado(db: Session, catalog_idx: dict) -> list[AlertaItem]:
    meta = catalog_idx[5]

    competencia_ref = _latest_closed_operational_competencia(db)
    if not competencia_ref:
        return []

    ano_ref, mes_ref = _competencia_to_key(competencia_ref)
    prev_comp = _previous_competencia(competencia_ref)
    ano_prev, mes_prev = _competencia_to_key(prev_comp)

    rows_atual = db.execute(
        select(
            FactUnidadeMensal.unidade,
            FactUnidadeMensal.cirurgias,
            FactUnidadeMensal.consultas_totais,
            FactUnidadeMensal.receita_operacional,
        ).where(
            and_(
                FactUnidadeMensal.ano == ano_ref,
                FactUnidadeMensal.mes == mes_ref,
                FactUnidadeMensal.mes_incompleto.is_(False),
            )
        )
    ).all()
    if not rows_atual:
        return []

    historico_prev = db.execute(
        select(
            FactUnidadeMensal.unidade,
            FactUnidadeMensal.cirurgias,
            FactUnidadeMensal.consultas_totais,
            FactUnidadeMensal.receita_operacional,
        ).where(
            (FactUnidadeMensal.ano < ano_ref)
            | and_(FactUnidadeMensal.ano == ano_ref, FactUnidadeMensal.mes < mes_ref)
            | and_(FactUnidadeMensal.ano == ano_prev, FactUnidadeMensal.mes == mes_prev)
        )
    ).all()

    teve_operacao: set[str] = set()
    for unidade, cirurgias, consultas, receita in historico_prev:
        if float(cirurgias or 0) > 0 or float(consultas or 0) > 0 or float(receita or 0) > 0:
            teve_operacao.add(str(unidade))

    afetadas: list[str] = []
    for unidade, cirurgias, consultas, receita in rows_atual:
        unidade_nome = str(unidade)
        if unidade_nome not in teve_operacao:
            continue
        if float(cirurgias or 0) == 0 and (float(consultas or 0) > 0 or float(receita or 0) > 0):
            afetadas.append(unidade_nome)

    if not afetadas:
        return []

    return [
        AlertaItem(
            alert_id=5,
            categoria=meta.categoria,
            nivel=meta.nivel,
            titulo=meta.titulo,
            detalhe=(
                f"{len(afetadas)} unidade(s) zeraram cirurgias em {competencia_ref} "
                "apesar de histórico prévio de operação e mês fechado."
            ),
            threshold=meta.threshold,
            impacto=meta.impacto,
            dado_base=meta.dado_base,
            competencia_ref=competencia_ref,
            unidades=sorted(afetadas),
            metricas={
                "valor_atual": 0,
                "valor_referencia": 1,
                "variacao": None,
            },
        )
    ]


def _alerta_9_nf_abaixo_65(db: Session, catalog_idx: dict) -> list[AlertaItem]:
    meta = catalog_idx[9]

    rows = db.execute(
        select(
            FactFiscalMensal.competencia,
            FactFiscalMensal.unidade_ref,
            FactFiscalMensal.percentual_nf,
        ).order_by(FactFiscalMensal.ano.desc(), FactFiscalMensal.mes.desc())
    ).all()
    if not rows:
        return []

    comp_ref = str(rows[0][0])
    alvo = [r for r in rows if str(r[0]) == comp_ref]

    afetadas = [
        str(unidade_ref if unidade_ref != "__CONSOLIDADO__" else "Consolidado")
        for _, unidade_ref, percentual in alvo
        if float(percentual or 0) < 65
    ]

    if not afetadas:
        return []

    min_pct = min(float(percentual or 0) for _, _, percentual in alvo)
    return [
        AlertaItem(
            alert_id=9,
            categoria=meta.categoria,
            nivel=meta.nivel,
            titulo=meta.titulo,
            detalhe=f"{len(afetadas)} registro(s) com percentual NF abaixo de 65% em {comp_ref}.",
            threshold=meta.threshold,
            impacto=meta.impacto,
            dado_base=meta.dado_base,
            competencia_ref=comp_ref,
            unidades=sorted(afetadas),
            metricas={
                "valor_atual": min_pct,
                "valor_referencia": 65,
                "variacao": min_pct - 65,
            },
        )
    ]


def _alerta_10_nf_acima_100(db: Session, catalog_idx: dict) -> list[AlertaItem]:
    meta = catalog_idx[10]

    rows = db.execute(
        select(
            FactFiscalMensal.competencia,
            FactFiscalMensal.unidade_ref,
            FactFiscalMensal.percentual_nf,
        ).order_by(FactFiscalMensal.ano.desc(), FactFiscalMensal.mes.desc())
    ).all()
    if not rows:
        return []

    comp_ref = str(rows[0][0])
    alvo = [r for r in rows if str(r[0]) == comp_ref]

    afetadas = [
        str(unidade_ref if unidade_ref != "__CONSOLIDADO__" else "Consolidado")
        for _, unidade_ref, percentual in alvo
        if float(percentual or 0) > 100
    ]
    if not afetadas:
        return []

    max_pct = max(float(percentual or 0) for _, _, percentual in alvo)
    return [
        AlertaItem(
            alert_id=10,
            categoria=meta.categoria,
            nivel=meta.nivel,
            titulo=meta.titulo,
            detalhe=f"{len(afetadas)} registro(s) com percentual NF acima de 100% em {comp_ref}.",
            threshold=meta.threshold,
            impacto=meta.impacto,
            dado_base=meta.dado_base,
            competencia_ref=comp_ref,
            unidades=sorted(afetadas),
            metricas={
                "valor_atual": max_pct,
                "valor_referencia": 100,
                "variacao": max_pct - 100,
            },
        )
    ]


def _alerta_13_saiu_do_vermelho(db: Session, catalog_idx: dict) -> list[AlertaItem]:
    meta = catalog_idx[13]

    rows = db.execute(
        select(
            FactFinanceiroMensal.unidade_ref,
            FactFinanceiroMensal.competencia,
            FactFinanceiroMensal.ebitda,
            FactFinanceiroMensal.margem_ebitda,
        )
        .where(FactFinanceiroMensal.unidade_ref != "__CONSOLIDADO__")
        .order_by(FactFinanceiroMensal.unidade_ref, FactFinanceiroMensal.ano, FactFinanceiroMensal.mes)
    ).all()
    if not rows:
        return []

    by_unidade: dict[str, list[tuple[str, float, float]]] = {}
    for unidade, competencia, ebitda, margem in rows:
        by_unidade.setdefault(str(unidade), []).append((str(competencia), float(ebitda or 0), float(margem or 0)))

    recuperadas: list[str] = []
    competencia_ref = None

    for unidade, serie in by_unidade.items():
        if len(serie) < 2:
            continue

        anterior = serie[-2]
        atual = serie[-1]
        anterior_neg = anterior[1] < 0 or anterior[2] < 0
        atual_pos = atual[1] > 0 or atual[2] > 0
        if anterior_neg and atual_pos:
            recuperadas.append(unidade)
            competencia_ref = atual[0]

    if not recuperadas:
        return []

    return [
        AlertaItem(
            alert_id=13,
            categoria=meta.categoria,
            nivel=meta.nivel,
            titulo=meta.titulo,
            detalhe=(
                f"{len(recuperadas)} unidade(s) voltaram para EBITDA/margem EBITDA positivos "
                "na competência mais recente."
            ),
            threshold=meta.threshold,
            impacto=meta.impacto,
            dado_base=meta.dado_base,
            competencia_ref=competencia_ref,
            unidades=sorted(recuperadas),
            metricas={
                "valor_atual": None,
                "valor_referencia": 0,
                "variacao": None,
            },
        )
    ]
