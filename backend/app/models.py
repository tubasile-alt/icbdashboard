from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class FactUnidadeMensal(Base):
    __tablename__ = "fact_unidade_mensal"
    __table_args__ = (UniqueConstraint("unidade", "ano", "mes", name="uq_unidade_ano_mes"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unidade: Mapped[str] = mapped_column(String(120), nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    competencia: Mapped[str] = mapped_column(String(7), nullable=False)
    leads: Mapped[float] = mapped_column(Float, default=0)
    consultas_presenciais: Mapped[float] = mapped_column(Float, default=0)
    consultas_online: Mapped[float] = mapped_column(Float, default=0)
    consultas_totais: Mapped[float] = mapped_column(Float, default=0)
    retornos_presenciais: Mapped[float] = mapped_column(Float, default=0)
    retornos_online: Mapped[float] = mapped_column(Float, default=0)
    retornos_totais: Mapped[float] = mapped_column(Float, default=0)
    cirurgias: Mapped[float] = mapped_column(Float, default=0)
    receita_operacional: Mapped[float] = mapped_column(Float, default=0)
    ticket_medio_cirurgia: Mapped[float] = mapped_column(Float, default=0)
    conv_lead_consulta: Mapped[float] = mapped_column(Float, default=0)
    conv_consulta_cirurgia: Mapped[float] = mapped_column(Float, default=0)
    receita_por_lead: Mapped[float] = mapped_column(Float, default=0)
    receita_por_consulta: Mapped[float] = mapped_column(Float, default=0)
    cirurgias_por_consulta: Mapped[float] = mapped_column(Float, default=0)
    mes_incompleto: Mapped[bool] = mapped_column(Boolean, default=False)
    dados_inconsistentes: Mapped[bool] = mapped_column(Boolean, default=False)


class FactProducaoProfissionalMensal(Base):
    __tablename__ = "fact_producao_profissional_mensal"
    __table_args__ = (
        UniqueConstraint("profissional", "unidade", "ano", "mes", name="uq_prof_unidade_ano_mes"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profissional: Mapped[str] = mapped_column(String(150), nullable=False)
    unidade: Mapped[str] = mapped_column(String(120), nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    competencia: Mapped[str] = mapped_column(String(7), nullable=False)
    consultas_presenciais: Mapped[float] = mapped_column(Float, default=0)
    consultas_online: Mapped[float] = mapped_column(Float, default=0)
    consultas_totais: Mapped[float] = mapped_column(Float, default=0)
    retornos_presenciais: Mapped[float] = mapped_column(Float, default=0)
    retornos_online: Mapped[float] = mapped_column(Float, default=0)
    retornos_totais: Mapped[float] = mapped_column(Float, default=0)
    cirurgias: Mapped[float] = mapped_column(Float, default=0)
    mes_incompleto: Mapped[bool] = mapped_column(Boolean, default=False)
    dados_inconsistentes: Mapped[bool] = mapped_column(Boolean, default=False)


class FactFinanceiroMensal(Base):
    __tablename__ = "fact_financeiro_mensal"
    __table_args__ = (UniqueConstraint("unidade_ref", "competencia", name="uq_fin_unidaderef_comp"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    competencia: Mapped[str] = mapped_column(String(7), nullable=False)
    unidade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unidade_ref: Mapped[str] = mapped_column(String(120), nullable=False, default="__CONSOLIDADO__")
    receita_bruta: Mapped[float] = mapped_column(Float, default=0)
    impostos: Mapped[float] = mapped_column(Float, default=0)
    receita_liquida: Mapped[float] = mapped_column(Float, default=0)
    custos: Mapped[float] = mapped_column(Float, default=0)
    despesas: Mapped[float] = mapped_column(Float, default=0)
    ebitda: Mapped[float] = mapped_column(Float, default=0)
    margem_ebitda: Mapped[float] = mapped_column(Float, default=0)
    lucro_liquido: Mapped[float] = mapped_column(Float, default=0)
    margem_liquida: Mapped[float] = mapped_column(Float, default=0)


class FactFiscalMensal(Base):
    __tablename__ = "fact_fiscal_mensal"
    __table_args__ = (UniqueConstraint("unidade_ref", "competencia", name="uq_fiscal_unidaderef_comp"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    competencia: Mapped[str] = mapped_column(String(7), nullable=False)
    unidade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unidade_ref: Mapped[str] = mapped_column(String(120), nullable=False, default="__CONSOLIDADO__")
    percentual_nf: Mapped[float] = mapped_column(Float, default=0)
    receita_com_nf: Mapped[float] = mapped_column(Float, default=0)
    receita_sem_nf: Mapped[float] = mapped_column(Float, default=0)


class UnidadeStatus(Base):
    __tablename__ = "unidade_status"
    __table_args__ = (UniqueConstraint("unidade", name="uq_unidade_status"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unidade: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ativa")
    data_abertura: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_encerramento: Mapped[date | None] = mapped_column(Date, nullable=True)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    excluir_de_medias: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Metadata(Base):
    __tablename__ = "metadata"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    source_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_last_modified: Mapped[str] = mapped_column(String(64), nullable=False)
    source_file_rev: Mapped[str] = mapped_column(String(255), nullable=False)
    last_ingestion_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_ingestion_finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    dashboard_last_update: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    update_status: Mapped[str] = mapped_column(String(20), nullable=False, default="updated")


class IngestionQualityReport(Base):
    __tablename__ = "ingestion_quality_report"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    inconsistent_rows: Mapped[int] = mapped_column(Integer, default=0)
    empty_columns_removed: Mapped[int] = mapped_column(Integer, default=0)
    incomplete_months_detected: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
