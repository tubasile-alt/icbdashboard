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
    data_encerramento: date | None
    motivo: str
    excluir_de_medias: bool


SEED_UNIDADES_STATUS: tuple[UnidadeStatusSeed, ...] = (
    UnidadeStatusSeed("João Pessoa", STATUS_ENCERRADA, date(2024, 6, 1), "Sem atividade após Mai/2024.", True),
    UnidadeStatusSeed("Londrina", STATUS_ENCERRADA, date(2024, 9, 1), "Sem atividade após Ago/2024. Queda abrupta para 1 cirurgia.", True),
    UnidadeStatusSeed("Joinville", STATUS_ENCERRADA, date(2024, 11, 1), "Sem atividade após Out/2024. Último mês com 0 consultas.", True),
    UnidadeStatusSeed("Vitória", STATUS_ENCERRADA, date(2024, 11, 1), "Sem atividade após Out/2024. Receita caiu de R$ 163k para R$ 14k.", True),
    UnidadeStatusSeed("São Luís", STATUS_ENCERRADA, date(2025, 1, 1), "Sem atividade após Dez/2024.", True),
    UnidadeStatusSeed("Cuiabá", STATUS_ENCERRADA, date(2025, 2, 1), "Margem -94% e sem atividade após Jan/2025.", True),
    UnidadeStatusSeed("Barra-RJ", STATUS_ENCERRADA, date(2025, 7, 1), "Volume muito baixo e sem atividade após Jun/2025.", True),
    UnidadeStatusSeed("Manaus", STATUS_ENCERRADA, date(2025, 8, 1), "Sem atividade após Jul/2025.", True),
    UnidadeStatusSeed("Fortaleza", STATUS_SUSPENSA, None, "Último dado em Jan/2026. Sem Fev/Mar de 2026, confirmar status.", False),
    UnidadeStatusSeed("Florianópolis", STATUS_REESTRUTURACAO, None, "Margem muito negativa e queda forte de receita.", False),
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


def list_unidades_status(db: Session) -> list[dict[str, Any]]:
    prioridade = case(
        (UnidadeStatus.status == STATUS_ATIVA, 1),
        (UnidadeStatus.status == STATUS_REESTRUTURACAO, 2),
        (UnidadeStatus.status == STATUS_SUSPENSA, 3),
        (UnidadeStatus.status == STATUS_ENCERRADA, 4),
        else_=5,
    )
    rows = db.execute(select(UnidadeStatus).order_by(prioridade, func.lower(UnidadeStatus.unidade))).scalars().all()
    return [_to_dict(row) for row in rows]


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
