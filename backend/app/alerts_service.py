from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import FactFinanceiroMensal, FactUnidadeMensal
from .services.unidade_status_service import get_unidades_ativas_para_metricas

MARGEM_CRITICA = -0.05
YOY_QUEDA_CRITICA = -0.20
YOY_QUEDA_ATENCAO = -0.10
CONV_THRESHOLD = 0.35
VOLUME_MINIMO_CONSULTAS = 20


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


def build_alerts(db: Session) -> list[dict]:
    alertas: list[Alerta] = []
    alertas += _alerta_financeiro_consolidado(db)
    alertas += _alertas_yoy_unidade(db)
    alertas += _alertas_conversao(db)
    alertas += _alertas_mes_incompleto(db)

    ordem = {"critico": 0, "atencao": 1, "info": 2}
    alertas.sort(key=lambda a: ordem.get(a.nivel, 9))
    return [a.to_dict() for a in alertas]


def _alerta_financeiro_consolidado(db: Session) -> list[Alerta]:
    rows = db.execute(
        select(
            FactFinanceiroMensal.competencia,
            FactFinanceiroMensal.receita_liquida,
            FactFinanceiroMensal.lucro_liquido,
        ).order_by(FactFinanceiroMensal.competencia.desc())
    ).all()
    if not rows:
        return []

    atual = rows[0]
    receita = float(atual.receita_liquida or 0)
    lucro = float(atual.lucro_liquido or 0)
    margem = (lucro / receita) if receita > 0 else 0.0

    if margem < MARGEM_CRITICA:
        return [
            Alerta(
                nivel="critico",
                categoria="financeiro",
                titulo=f"Margem líquida consolidada negativa em {atual.competencia}",
                detalhe=(
                    f"Receita líquida de R$ {receita:,.0f} com lucro líquido de R$ {lucro:,.0f} "
                    f"(margem {margem * 100:.1f}%). Revisar custos e composição de receita no período."
                ),
                unidades=[],
            )
        ]

    return []


def _alertas_yoy_unidade(db: Session) -> list[Alerta]:
    max_periodo = db.execute(
        select(FactUnidadeMensal.ano, FactUnidadeMensal.mes)
        .order_by(FactUnidadeMensal.ano.desc(), FactUnidadeMensal.mes.desc())
        .limit(1)
    ).first()
    if not max_periodo:
        return []

    ano_atual, mes_atual = max_periodo
    ano_anterior = ano_atual - 1

    unidades_ativas = get_unidades_ativas_para_metricas(db)

    atual = {
        unidade: float(receita or 0)
        for unidade, receita in db.execute(
            select(FactUnidadeMensal.unidade, func.sum(FactUnidadeMensal.receita_operacional))
            .where(FactUnidadeMensal.ano == ano_atual, FactUnidadeMensal.mes <= mes_atual)
            .group_by(FactUnidadeMensal.unidade)
        ).all()
        if not unidades_ativas or unidade in unidades_ativas
    }
    anterior = {
        unidade: float(receita or 0)
        for unidade, receita in db.execute(
            select(FactUnidadeMensal.unidade, func.sum(FactUnidadeMensal.receita_operacional))
            .where(FactUnidadeMensal.ano == ano_anterior, FactUnidadeMensal.mes <= mes_atual)
            .group_by(FactUnidadeMensal.unidade)
        ).all()
        if not unidades_ativas or unidade in unidades_ativas
    }

    variacoes: list[tuple[str, float]] = []
    for unidade, receita_anterior in anterior.items():
        if receita_anterior <= 0:
            continue
        var = (atual.get(unidade, 0.0) - receita_anterior) / receita_anterior
        variacoes.append((unidade, var))

    criticas = [item for item in variacoes if item[1] < YOY_QUEDA_CRITICA]
    atencao = [item for item in variacoes if YOY_QUEDA_CRITICA <= item[1] < YOY_QUEDA_ATENCAO]

    alertas: list[Alerta] = []
    if criticas:
        criticas.sort(key=lambda i: i[1])
        pior_nome, pior_var = criticas[0]
        alertas.append(
            Alerta(
                nivel="critico",
                categoria="financeiro",
                titulo=f"{len(criticas)} unidade(s) com queda YoY acima de {int(abs(YOY_QUEDA_CRITICA) * 100)}%",
                detalhe=(
                    f"Comparação {ano_atual} vs {ano_anterior} até mês {mes_atual:02d}. "
                    f"Maior queda: {pior_nome} ({pior_var * 100:.1f}%)."
                ),
                unidades=[u for u, _ in criticas],
            )
        )

    if atencao:
        atencao.sort(key=lambda i: i[1])
        alertas.append(
            Alerta(
                nivel="atencao",
                categoria="financeiro",
                titulo="Unidades com receita abaixo do ano anterior",
                detalhe=(
                    f"{len(atencao)} unidade(s) com queda entre "
                    f"{int(abs(YOY_QUEDA_ATENCAO) * 100)}% e {int(abs(YOY_QUEDA_CRITICA) * 100)}% no acumulado."
                ),
                unidades=[u for u, _ in atencao],
            )
        )

    return alertas


def _alertas_conversao(db: Session) -> list[Alerta]:
    periodo_ref = db.execute(
        select(FactUnidadeMensal.ano, FactUnidadeMensal.mes)
        .order_by(FactUnidadeMensal.ano.desc(), FactUnidadeMensal.mes.desc())
        .limit(1)
    ).first()
    if not periodo_ref:
        return []

    ano_ref, mes_ref = periodo_ref
    rows = db.execute(
        select(
            FactUnidadeMensal.unidade,
            func.sum(FactUnidadeMensal.cirurgias),
            func.sum(FactUnidadeMensal.consultas_totais),
        )
        .where(
            FactUnidadeMensal.ano == ano_ref,
            FactUnidadeMensal.mes <= mes_ref,
        )
        .group_by(FactUnidadeMensal.unidade)
    ).all()

    unidades_ativas = get_unidades_ativas_para_metricas(db)
    if unidades_ativas:
        rows = [r for r in rows if r[0] in unidades_ativas]

    baixas: list[tuple[str, float, float, float]] = []
    for unidade, cirurgias, consultas in rows:
        total_consultas = float(consultas or 0)
        total_cirurgias = float(cirurgias or 0)
        if total_consultas < VOLUME_MINIMO_CONSULTAS:
            continue
        taxa = total_cirurgias / total_consultas if total_consultas else 0.0
        if taxa < CONV_THRESHOLD:
            baixas.append((unidade, taxa, total_cirurgias, total_consultas))

    if not baixas:
        return []

    baixas.sort(key=lambda i: i[1])
    pior = baixas[0]
    return [
        Alerta(
            nivel="atencao",
            categoria="operacional",
            titulo=(
                f"{len(baixas)} unidade(s) com conversão abaixo de {int(CONV_THRESHOLD * 100)}% "
                f"({ano_ref} YTD)"
            ),
            detalhe=(
                f"Acumulado até {ano_ref}-{mes_ref:02d}. "
                f"Pior caso: {pior[0]} com {pior[1] * 100:.1f}% "
                f"({int(pior[2])} cirurgias / {int(pior[3])} consultas)."
            ),
            unidades=[u for u, *_ in baixas],
        )
    ]


def _alertas_mes_incompleto(db: Session) -> list[Alerta]:
    rows = db.execute(
        select(FactUnidadeMensal.unidade)
        .where(FactUnidadeMensal.mes_incompleto.is_(True))
        .distinct()
        .order_by(FactUnidadeMensal.unidade)
    ).all()

    if not rows:
        return []

    nomes = [r[0] for r in rows]
    return [
        Alerta(
            nivel="info",
            categoria="operacional",
            titulo="Mês atual com dados incompletos",
            detalhe=(
                f"{len(nomes)} unidade(s) com competência corrente ainda aberta. "
                "Indicadores podem variar até o fechamento."
            ),
            unidades=nomes,
        )
    ]
