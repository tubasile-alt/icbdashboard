from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.etl.excel_pipeline import _clean_text_series, _normalize_columns, process_excel_full_refresh
from app.models import FactUnidadeMensal, IngestionQualityReport


def _build_test_excel(tmp_path: Path) -> Path:
    file_path = tmp_path / "input.xlsx"

    base_df = pd.DataFrame(
        {
            "Data": ["2026-03-10", "2026-03-11", "2026-04-01"],
            "Unidade": [" A\nCentro ", "A\tCentro", "B Centro"],
            "Profissional": ["Dra. A", "", "Dr. B"],
            "Leads": [0, -2, 10],
            "Consultas": [0, 1, 5],
            "Consultas Online": [0, 0, 1],
            "Retornos": [0, 0, 2],
            "Retornos Online": [0, 0, 0],
            "Cirurgias": [0, 2, 1],
            "Valor dos Serviços": [1000, 2000, 5000],
            "Coluna Vazia": [None, None, None],
        }
    )

    dre_df = pd.DataFrame(
        {
            "Data": ["2026-03-01", "2026-04-01"],
            "Receita Bruta": [10000, 15000],
            "Impostos": [1000, 1500],
            "Receita Líquida": [9000, 13500],
            "EBITDA": [3000, 4000],
            "Lucro Líquido": [1000, 1500],
        }
    )

    fiscal_df = pd.DataFrame(
        {
            "Data": ["2026-03-01", "2026-04-01"],
            "% Notas Fiscais": [0.8, 0.9],
        }
    )

    with pd.ExcelWriter(file_path) as writer:
        base_df.to_excel(writer, sheet_name="Base Dados", index=False)
        dre_df.to_excel(writer, sheet_name="Despesas 2026", index=False)
        fiscal_df.to_excel(writer, sheet_name="% Notas fiscais", index=False)

    return file_path


def test_clean_text_series_removes_breaks():
    s = pd.Series([" A\nB ", "C\t\tD", "  E   F "])
    cleaned = _clean_text_series(s)
    assert cleaned.tolist() == ["A B", "C D", "E F"]


def test_normalize_columns_maps_aliases():
    df = pd.DataFrame({"Valor Serviços": [1], "Consultas On Line": [2]})
    normalized = _normalize_columns(df)
    assert "valor_dos_servicos" in normalized.columns
    assert "consultas_online" in normalized.columns


def test_etl_flags_inconsistency_and_reports_quality(tmp_path: Path):
    excel_path = _build_test_excel(tmp_path)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        process_excel_full_refresh(
            db=db,
            excel_path=str(excel_path),
            source_file_name="input.xlsx",
            source_file_rev="r1",
            source_file_last_modified="2026-04-04T00:00:00Z",
            stale_threshold_hours=6,
        )

        unidades = db.execute(select(FactUnidadeMensal)).scalars().all()
        assert len(unidades) >= 2

        has_incomplete = any(u.competencia == "2026-03" and u.mes_incompleto for u in unidades)
        has_inconsistent = any(u.dados_inconsistentes for u in unidades)

        assert has_incomplete is True
        assert has_inconsistent is True

        quality = db.execute(select(IngestionQualityReport)).scalars().first()
        assert quality is not None
        assert quality.processed_rows > 0
        assert quality.empty_columns_removed > 0
