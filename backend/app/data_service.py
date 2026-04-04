"""Compat layer: mantém imports antigos apontando para os novos módulos."""

from .api.dashboard_service import (  # noqa: F401
    get_dashboard_summary,
    get_financeiro_dashboard,
    get_fiscal_dashboard,
    get_last_update_status,
    get_profissionais_dashboard,
    get_unidades_dashboard,
)
from .etl.excel_pipeline import process_excel_full_refresh  # noqa: F401
