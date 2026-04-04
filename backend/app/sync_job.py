import asyncio
import logging

from sqlalchemy import func

from .config import settings
from .etl.excel_pipeline import process_excel_full_refresh
from .database import SessionLocal
from .dropbox_client import download_latest_file_from_dropbox
from .models import FactUnidadeMensal, Metadata

logger = logging.getLogger(__name__)


async def run_sync_loop():
    await asyncio.sleep(5)
    while True:
        db = SessionLocal()
        try:
            file_info = download_latest_file_from_dropbox()
            metadata = db.get(Metadata, 1)

            has_operational_data = False
            if metadata and metadata.source_file_rev == file_info["file_rev"]:
                count = db.query(func.count(FactUnidadeMensal.id)).scalar() or 0
                has_operational_data = count > 0

            if not has_operational_data:
                process_excel_full_refresh(
                    db,
                    excel_path=file_info["local_path"],
                    source_file_name=file_info["file_name"],
                    source_file_rev=file_info["file_rev"],
                    source_file_last_modified=file_info.get("server_modified", ""),
                    stale_threshold_hours=settings.stale_threshold_hours,
                )
                logger.info("Dados atualizados com sucesso: %s", file_info["file_name"])
            else:
                logger.info("Sem mudanças no arquivo do Dropbox.")
        except Exception as exc:
            logger.exception("Erro no job de sincronização: %s", exc)
        finally:
            db.close()

        await asyncio.sleep(settings.update_interval_minutes * 60)
