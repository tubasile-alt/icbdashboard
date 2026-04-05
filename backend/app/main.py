import asyncio
import logging

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .api.dashboard_service import (
    get_dashboard_summary,
    get_financeiro_dashboard,
    get_fiscal_dashboard,
    get_last_update_status,
    get_alertas_dashboard,
    get_profissionais_dashboard,
    get_unidades_dashboard,
)
from .database import Base, engine, get_db
from .schemas import LastUpdateResponse
from .services.dropbox_service import init_dropbox
from .sync_job import run_sync_loop

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    try:
        init_dropbox(
            app_key=settings.dropbox_app_key,
            app_secret=settings.dropbox_app_secret,
            refresh_token=settings.dropbox_refresh_token,
        )
        logger.info("Dropbox OAuth inicializado com sucesso")
    except RuntimeError as e:
        logger.error(f"Erro ao inicializar Dropbox OAuth: {e}")
        logger.warning("Sincronização do Dropbox será desativada")

    asyncio.create_task(run_sync_loop())


def _filters(
    anos: list[int] = Query(default=[]),
    meses: list[int] = Query(default=[]),
    competencias: list[str] = Query(default=[]),
    unidades: list[str] = Query(default=[]),
    profissionais: list[str] = Query(default=[]),
):
    return {
        "anos": anos,
        "meses": meses,
        "competencias": competencias,
        "unidades": unidades,
        "profissionais": profissionais,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/last-update", response_model=LastUpdateResponse)
def last_update(db: Session = Depends(get_db)):
    return get_last_update_status(db, settings.stale_threshold_hours)


@app.get("/dashboard/summary")
def dashboard_summary(filters: dict = Depends(_filters), db: Session = Depends(get_db)):
    return get_dashboard_summary(db, filters)


@app.get("/dashboard/unidades")
def dashboard_unidades(filters: dict = Depends(_filters), db: Session = Depends(get_db)):
    return get_unidades_dashboard(db, filters)


@app.get("/dashboard/profissionais")
def dashboard_profissionais(filters: dict = Depends(_filters), db: Session = Depends(get_db)):
    return get_profissionais_dashboard(db, filters)


@app.get("/dashboard/financeiro")
def dashboard_financeiro(filters: dict = Depends(_filters), db: Session = Depends(get_db)):
    return get_financeiro_dashboard(db, filters)


@app.get("/dashboard/fiscal")
def dashboard_fiscal(filters: dict = Depends(_filters), db: Session = Depends(get_db)):
    return get_fiscal_dashboard(db, filters)


@app.get("/dashboard/alertas")
def dashboard_alertas(filters: dict = Depends(_filters), db: Session = Depends(get_db)):
    return get_alertas_dashboard(db, filters)


@app.get("/dropbox/test")
def test_dropbox_connection():
    """Testa a conexão com Dropbox usando OAuth 2.0."""
    from .services.dropbox_service import get_dropbox_manager

    try:
        manager = get_dropbox_manager()
        result = manager.verify_connection()
        return {
            "status": "success",
            "message": "Conexão com Dropbox validada",
            **result,
        }
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}
