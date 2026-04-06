from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..models import FactUnidadeMensal, UnidadeStatus

STATUS_ATIVA = "ativa"
STATUS_ENCERRADA = "encerrada"
STATUS_SUSPENSA = "suspensa"
STATUS_REESTRUTURACAO = "em_reestruturacao"

STATUS_VALIDOS = {
    STATUS_ATIVA,
    STATUS_ENCERRADA,
    STATUS_SUSPENSA,
    STATUS_REESTRUTURACAO,
}


@dataclass(frozen=True)
class UnidadeStatusSeed:
    unidade: str
    status: str
    excluir_de_medias: bool
    data_encerramento: date | None = None
    motivo: str | None = None


SEED_UNIDADES_STATUS: tuple[UnidadeStatusSeed, ...] = (
    UnidadeStatusSeed("João Pessoa", STATUS_ENCERRADA, True, date(2024, 6, 1), "Sem atividade após Mai/2024. Último registro: 3 cirurgias, R$ 13.990."),
    UnidadeStatusSeed("Londrina", STATUS_ENCERRADA, True, date(2024, 9, 1), "Queda abrupta de volume. Último mês: 1 cirurgia, R$ 13.740."),
    UnidadeStatusSeed("Joinville", STATUS_ENCERRADA, True, date(2024, 11, 1), "Último mês: 0 consultas, 3 cirurgias, R$ 36k. Encerramento após Out/2024."),
    UnidadeStatusSeed("Vitória", STATUS_ENCERRADA, True, date(2024, 11, 1), "Queda de R$ 163k (Ago/24) para R$ 14k (Out/24). Encerramento imediato."),
    UnidadeStatusSeed("São Luís", STATUS_ENCERRADA, True, date(2025, 1, 1), "Sem atividade após Dez/2024."),
    UnidadeStatusSeed("Cuiabá", STATUS_ENCERRADA, True, date(2025, 2, 1), "Margem LL -94% no acumulado 2025. Sem atividade após Jan/2025."),
    UnidadeStatusSeed("Barra-RJ", STATUS_ENCERRADA, True, date(2025, 7, 1), "Volume muito baixo nos últimos meses. Sem atividade após Jun/2025."),
    UnidadeStatusSeed("Manaus", STATUS_ENCERRADA, True, date(2025, 8, 1), "Último dado: Jul/2025 (6 cirurgias, R$ 83.800). Sem atividade após."),
    UnidadeStatusSeed("Fortaleza", STATUS_SUSPENSA, False, None, "Último dado Jan/2026. Sem registros Fev/Mar 2026. Confirmar status com gestão."),
    UnidadeStatusSeed("Florianópolis", STATUS_REESTRUTURACAO, False, None, "Margem LL -108% em Q1/2026. Receita caiu 61% YoY."),
    UnidadeStatusSeed("Rio de Janeiro", STATUS_REESTRUTURACAO, False, None, "Margem LL -6,9% em Q1/2026. Custos superam receita líquida."),
    UnidadeStatusSeed("Ribeirão Preto", STATUS_ATIVA, False, None, None),
    UnidadeStatusSeed("Brasília", STATUS_ATIVA, False, None, None),
    UnidadeStatusSeed("Campinas", STATUS_ATIVA, False, None, None),
    UnidadeStatusSeed("Belo Horizonte", STATUS_ATIVA, False, None, None),
    UnidadeStatusSeed("Itaim Bibi", STATUS_ATIVA, False, None, None),
    UnidadeStatusSeed("Goiânia", STATUS_ATIVA, False, None, None),
    UnidadeStatusSeed("ABC", STATUS_ATIVA, False, None, None),
)


def normalize_unidade_name(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "")).strip()
    return normalized


def _default_excluir_de_medias(status: str, excluir_de_medias: bool | None) -> bool:
    if excluir_de_medias is not None:
        return bool(excluir_de_medias)
    if status == STATUS_ENCERRADA:
        return True
    return False


def _to_dict(item: UnidadeStatus) -> dict[str, Any]:
    return {
        "unidade": item.unidade,
        "status": item.status,
        "data_abertura": item.data_abertura,
        "data_encerramento": item.data_encerramento,
        "motivo": item.motivo,
        "observacao": item.observacao,
        "excluir_de_medias": item.excluir_de_medias,
        "atualizado_em": item.atualizado_em,
    }


def seed_unidade_status(db: Session, force: bool = False) -> int:
    if force:
        db.query(UnidadeStatus).delete()
        db.flush()

    created = 0
    for seed in SEED_UNIDADES_STATUS:
        unidade = normalize_unidade_name(seed.unidade)
        existing = db.execute(select(UnidadeStatus).where(UnidadeStatus.unidade == unidade)).scalar_one_or_none()
        if existing:
            continue

        db.add(
            UnidadeStatus(
                unidade=unidade,
                status=seed.status,
                data_abertura=None,
                data_encerramento=seed.data_encerramento,
                motivo=seed.motivo,
                observacao=None,
                excluir_de_medias=seed.excluir_de_medias,
                atualizado_em=datetime.now(timezone.utc),
            )
        )
        created += 1

    if created > 0 or force:
        db.commit()
    return created


def _status_priority_expr():
    return case(
        (UnidadeStatus.status == STATUS_ATIVA, 1),
        (UnidadeStatus.status == STATUS_REESTRUTURACAO, 2),
        (UnidadeStatus.status == STATUS_SUSPENSA, 3),
        (UnidadeStatus.status == STATUS_ENCERRADA, 4),
        else_=5,
    )


def _ensure_operational_units_have_status(db: Session) -> int:
    unidades_operacionais = {
        normalize_unidade_name(row[0])
        for row in db.execute(select(FactUnidadeMensal.unidade).distinct()).all()
        if row[0]
    }
    if not unidades_operacionais:
        return 0

    existentes = {
        normalize_unidade_name(row[0])
        for row in db.execute(select(UnidadeStatus.unidade).distinct()).all()
        if row[0]
    }

    faltantes = [u for u in unidades_operacionais if u not in existentes]
    for unidade in faltantes:
        db.add(
            UnidadeStatus(
                unidade=unidade,
                status=STATUS_ATIVA,
                excluir_de_medias=False,
                atualizado_em=datetime.now(timezone.utc),
            )
        )

    if faltantes:
        db.commit()
    return len(faltantes)


def list_unidades_status(db: Session) -> dict[str, Any]:
    _ensure_operational_units_have_status(db)

    prioridade = _status_priority_expr()
    rows = db.execute(select(UnidadeStatus).order_by(prioridade, func.lower(UnidadeStatus.unidade))).scalars().all()
    items = [_to_dict(row) for row in rows]

    summary = {
        STATUS_ATIVA: sum(1 for row in items if row["status"] == STATUS_ATIVA),
        STATUS_REESTRUTURACAO: sum(1 for row in items if row["status"] == STATUS_REESTRUTURACAO),
        STATUS_SUSPENSA: sum(1 for row in items if row["status"] == STATUS_SUSPENSA),
        STATUS_ENCERRADA: sum(1 for row in items if row["status"] == STATUS_ENCERRADA),
    }

    encerradas = [row for row in items if row["status"] == STATUS_ENCERRADA]
    encerradas.sort(key=lambda row: (row["data_encerramento"] is None, row["data_encerramento"] or date.max, row["unidade"].lower()))

    suspensas = sorted(
        [row for row in items if row["status"] == STATUS_SUSPENSA],
        key=lambda row: row["unidade"].lower(),
    )

    timeline = [
        {
            "unidade": row["unidade"],
            "status": row["status"],
            "data_encerramento": row["data_encerramento"],
            "motivo": row["motivo"],
            "tipo": "fechamento",
        }
        for row in encerradas
    ] + [
        {
            "unidade": row["unidade"],
            "status": row["status"],
            "data_encerramento": None,
            "motivo": row["motivo"],
            "tipo": "status_incerto",
        }
        for row in suspensas
    ]

    return {"summary": summary, "items": items, "timeline": timeline}


def _unit_exists_in_operational_data(db: Session, unidade: str) -> bool:
    return (
        db.execute(select(FactUnidadeMensal.id).where(FactUnidadeMensal.unidade == unidade).limit(1)).scalar_one_or_none()
        is not None
    )


def update_unidade_status_manual(
    db: Session,
    unidade: str,
    *,
    status: str | None,
    data_abertura: date | None,
    data_encerramento: date | None,
    motivo: str | None,
    observacao: str | None,
    excluir_de_medias: bool | None,
) -> dict[str, Any]:
    unidade_norm = normalize_unidade_name(unidade)

    if not _unit_exists_in_operational_data(db, unidade_norm):
        raise HTTPException(status_code=404, detail=f"Unidade '{unidade_norm}' não encontrada na base operacional")

    existing = db.execute(select(UnidadeStatus).where(UnidadeStatus.unidade == unidade_norm)).scalar_one_or_none()
    if not existing:
        existing = UnidadeStatus(unidade=unidade_norm, status=STATUS_ATIVA, excluir_de_medias=False)
        db.add(existing)

    if status is not None:
        if status not in STATUS_VALIDOS:
            raise HTTPException(status_code=422, detail="status inválido")
        existing.status = status

    status_final = existing.status
    if status_final not in STATUS_VALIDOS:
        raise HTTPException(status_code=422, detail="status inválido")

    if data_abertura is not None:
        existing.data_abertura = data_abertura
    if data_encerramento is not None:
        existing.data_encerramento = data_encerramento
    if motivo is not None:
        existing.motivo = motivo
    if observacao is not None:
        existing.observacao = observacao

    existing.excluir_de_medias = _default_excluir_de_medias(status_final, excluir_de_medias)
    existing.atualizado_em = datetime.now(timezone.utc)

    db.commit()
    db.refresh(existing)
    return _to_dict(existing)


def get_unidades_ativas_para_metricas(db: Session) -> set[str]:
    unidades_operacionais = {
        row[0]
        for row in db.execute(select(FactUnidadeMensal.unidade).distinct()).all()
        if row[0]
    }
    if not unidades_operacionais:
        return set()

    unidades_excluidas = {
        row[0]
        for row in db.execute(
            select(UnidadeStatus.unidade).where(UnidadeStatus.excluir_de_medias.is_(True))
        ).all()
        if row[0]
    }

    return {u for u in unidades_operacionais if u not in unidades_excluidas}
