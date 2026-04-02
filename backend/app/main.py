import asyncio

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .data_service import get_dashboard_payload, get_last_update_status
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/last-update", response_model=LastUpdateResponse)
def last_update(db: Session = Depends(get_db)):
    return get_last_update_status(db, settings.stale_threshold_hours)


@app.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    return get_dashboard_payload(db, settings.stale_threshold_hours)
