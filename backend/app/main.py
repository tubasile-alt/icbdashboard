import asyncio

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .api.dashboard_service import (
    get_dashboard_summary,
    get_financeiro_dashboard,
    get_fiscal_dashboard,
    get_last_update_status,
    get_profissionais_dashboard,
    get_unidades_dashboard,
)
from .database import Base, engine, get_db
from .schemas import LastUpdateResponse
from .sync_job import run_sync_loop

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
