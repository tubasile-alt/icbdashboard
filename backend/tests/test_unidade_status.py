from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.etl.excel_pipeline import process_excel_full_refresh
from app.api.dashboard_service import get_dashboard_summary, get_filter_options
from app.main import patch_unidade_status, unidades_status
from app.models import Base, FactFinanceiroMensal, FactUnidadeMensal, UnidadeStatus
from app.schemas import UnidadeStatusPatchRequest
from app.services.unidade_status_service import get_unidades_ativas_para_metricas, seed_unidade_status


def _build_etl_excel(tmp_path: Path) -> Path:
    file_path = tmp_path / "sync.xlsx"

    base_df = pd.DataFrame(
        {
            "Data": ["2026-03-01", "2026-03-02"],
            "Unidade": ["Ativa", "Fechada"],
            "Profissional": ["Dr A", "Dr B"],
            "Leads": [10, 10],
            "Consultas": [10, 10],
            "Consultas Online": [0, 0],
            "Retornos": [0, 0],
            "Retornos Online": [0, 0],
            "Cirurgias": [3, 9],
            "Valor dos Serviços": [30000, 90000],
        }
    )

    with pd.ExcelWriter(file_path) as writer:
        base_df.to_excel(writer, sheet_name="Base Dados", index=False)

    return file_path


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal


def test_seed_idempotent_and_endpoint_functions_and_metric_filters(tmp_path: Path):
    SessionLocal = _make_session()

    with SessionLocal() as db:
        created1 = seed_unidade_status(db)
        created2 = seed_unidade_status(db)
        total_seed = db.execute(select(UnidadeStatus)).scalars().all()

        assert created1 > 0
        assert created2 == 0
        assert len(total_seed) == created1

        db.add_all(
            [
                FactUnidadeMensal(
                    unidade="Ativa",
                    ano=2026,
                    mes=3,
                    competencia="2026-03",
                    leads=20,
                    consultas_totais=20,
                    cirurgias=4,
                    receita_operacional=40000,
                ),
                FactUnidadeMensal(
                    unidade="Fechada",
                    ano=2026,
                    mes=3,
                    competencia="2026-03",
                    leads=100,
                    consultas_totais=100,
                    cirurgias=50,
                    receita_operacional=500000,
                ),
                FactUnidadeMensal(
                    unidade="Fechada",
                    ano=2025,
                    mes=12,
                    competencia="2025-12",
                    leads=10,
                    consultas_totais=10,
                    cirurgias=5,
                    receita_operacional=50000,
                ),
                FactFinanceiroMensal(
                    ano=2026,
                    mes=3,
                    competencia="2026-03",
                    unidade="Ativa",
                    unidade_ref="Ativa",
                    receita_bruta=100,
                    receita_liquida=100,
                    ebitda=10,
                    margem_ebitda=0.1,
                    lucro_liquido=8,
                    margem_liquida=0.08,
                    impostos=0,
                    custos=0,
                    despesas=0,
                ),
                FactFinanceiroMensal(
                    ano=2026,
                    mes=3,
                    competencia="2026-03",
                    unidade="Fechada",
                    unidade_ref="Fechada",
                    receita_bruta=100,
                    receita_liquida=100,
                    ebitda=-90,
                    margem_ebitda=-0.9,
                    lucro_liquido=-95,
                    margem_liquida=-0.95,
                    impostos=0,
                    custos=0,
                    despesas=0,
                ),
            ]
        )
        db.add(
            UnidadeStatus(
                unidade="Fechada",
                status="encerrada",
                excluir_de_medias=True,
            )
        )
        db.commit()

        status_payload = unidades_status(db)
        status_rows = status_payload["items"]
        assert status_payload["summary"]["encerrada"] >= 1
        assert any(item["tipo"] == "status_incerto" for item in status_payload["timeline"])

        assert status_rows == sorted(
            status_rows,
            key=lambda r: (
                {"ativa": 1, "em_reestruturacao": 2, "suspensa": 3, "encerrada": 4}.get(r["status"], 99),
                r["unidade"].lower(),
            ),
        )

        updated = patch_unidade_status(
            unidade="Ativa",
            payload=UnidadeStatusPatchRequest(status="encerrada", motivo="Encerrada para teste", excluir_de_medias=True),
            db=db,
        )
        assert updated["status"] == "encerrada"
        assert updated["excluir_de_medias"] is True
        assert updated["atualizado_em"] is not None

        try:
            patch_unidade_status(
                unidade="Unidade Inexistente",
                payload=UnidadeStatusPatchRequest(status="ativa"),
                db=db,
            )
            assert False, "Era esperado HTTPException 404"
        except HTTPException as exc:
            assert exc.status_code == 404

        # Reativa a unidade Ativa e valida benchmark/média/ranking sem unidade encerrada
        patch_unidade_status(
            unidade="Ativa",
            payload=UnidadeStatusPatchRequest(status="ativa", excluir_de_medias=False),
            db=db,
        )

        unidades_ativas_metricas = get_unidades_ativas_para_metricas(db)
        assert "Ativa" in unidades_ativas_metricas
        assert "Fechada" not in unidades_ativas_metricas

        summary = get_dashboard_summary(db, {"competencias": ["2026-03"]})
        assert summary["funil"]["consultas"] == 20
        assert round(summary["financeiro"]["margem_ebitda"], 2) == 0.1

        # Histórico preservado em opções de filtros
        options = get_filter_options(db)
        assert "Fechada" in options["unidades"]
        assert any(row["unidade"] == "Rio de Janeiro" for row in status_rows)


def test_sync_refresh_nao_apaga_tabela_unidade_status(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    excel_path = _build_etl_excel(tmp_path)

    with Session(engine) as db:
        db.add(UnidadeStatus(unidade="Fechada", status="encerrada", excluir_de_medias=True))
        db.commit()

        process_excel_full_refresh(
            db=db,
            excel_path=str(excel_path),
            source_file_name="sync.xlsx",
            source_file_rev="r1",
            source_file_last_modified="2026-04-06T00:00:00Z",
            stale_threshold_hours=6,
        )

        status_rows = db.execute(select(UnidadeStatus)).scalars().all()
        assert len(status_rows) == 1
        assert status_rows[0].unidade == "Fechada"
