from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class FactUnidadeMensal(Base):
    __tablename__ = "fact_unidade_mensal"
    __table_args__ = (UniqueConstraint("unidade", "ano", "mes", name="uq_unidade_ano_mes"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unidade: Mapped[str] = mapped_column(String(120), nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    receita: Mapped[float] = mapped_column(Float, default=0)
    leads: Mapped[float] = mapped_column(Float, default=0)
    consultas: Mapped[float] = mapped_column(Float, default=0)
    cirurgias: Mapped[float] = mapped_column(Float, default=0)
    mes_incompleto: Mapped[bool] = mapped_column(default=False)
    dados_inconsistentes: Mapped[bool] = mapped_column(default=False)


class FactProducaoProfissional(Base):
    __tablename__ = "fact_producao_profissional"
    __table_args__ = (
        UniqueConstraint("profissional", "unidade", "ano", "mes", name="uq_prof_unidade_ano_mes"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profissional: Mapped[str] = mapped_column(String(150), nullable=False)
    unidade: Mapped[str] = mapped_column(String(120), nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    consultas: Mapped[float] = mapped_column(Float, default=0)
    retornos: Mapped[float] = mapped_column(Float, default=0)
    cirurgias: Mapped[float] = mapped_column(Float, default=0)
    mes_incompleto: Mapped[bool] = mapped_column(default=False)
    dados_inconsistentes: Mapped[bool] = mapped_column(default=False)


class FactFinanceiro(Base):
    __tablename__ = "fact_financeiro"

    competencia: Mapped[str] = mapped_column(String(20), primary_key=True)
    receita_liquida: Mapped[float] = mapped_column(Float, default=0)
    ebitda: Mapped[float] = mapped_column(Float, default=0)
    lucro_liquido: Mapped[float] = mapped_column(Float, default=0)


class Metadata(Base):
    __tablename__ = "metadata"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    last_update_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_rev: Mapped[str] = mapped_column(String(255), nullable=False)
