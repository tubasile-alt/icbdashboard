from datetime import datetime

from pydantic import BaseModel


class Alerta(BaseModel):
    nivel: str
    categoria: str
    titulo: str
    detalhe: str
    unidades: list[str]


class LastUpdateResponse(BaseModel):
    last_update: str | None
    status: str


class DashboardResponse(BaseModel):
    last_update: datetime | None
    status: str
    summary: dict
    receita_por_mes: list[dict]
    cirurgias_por_mes: list[dict]
    receita_por_unidade: list[dict]
    unidades: list[dict]
    alertas: list[Alerta]
