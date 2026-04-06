from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class LastUpdateResponse(BaseModel):
    last_update: str | None
    status: str
    source_file_name: str | None = None
    source_file_last_modified: str | None = None


class UnidadeStatusResponse(BaseModel):
    unidade: str
    status: str
    data_abertura: date | None = None
    data_encerramento: date | None = None
    motivo: str | None = None
    observacao: str | None = None
    excluir_de_medias: bool
    atualizado_em: datetime | None = None


class UnidadeStatusTimelineItem(BaseModel):
    unidade: str
    status: str
    data_encerramento: date | None = None
    motivo: str | None = None
    tipo: str


class UnidadeStatusListResponse(BaseModel):
    summary: dict[str, int]
    items: list[UnidadeStatusResponse]
    timeline: list[UnidadeStatusTimelineItem]


class UnidadeStatusPatchRequest(BaseModel):
    status: str | None = None
    data_abertura: date | None = None
    data_encerramento: date | None = None
    motivo: str | None = None
    observacao: str | None = None
    excluir_de_medias: bool | None = Field(default=None)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = {"ativa", "encerrada", "suspensa", "em_reestruturacao"}
        if value not in allowed:
            raise ValueError("status inválido")
        return value
