import asyncio
import logging

from .config import settings
from .data_service import process_excel_and_refresh_database
from .database import SessionLocal
from .dropbox_client import download_latest_file_from_dropbox
from .models import FactUnidadeMensal, Metadata

logger = logging.getLogger(__name__)


async def run_sync_loop():
    await asyncio.sleep(30)
    while True:
        db = SessionLocal()
        try:
            file_info = download_latest_file_from_dropbox()
            metadata = db.get(Metadata, 1)
            has_operational_data = db.query(FactUnidadeMensal.id).first() is not None
            should_process = (
                not metadata
                or metadata.source_file_rev != file_info["file_rev"]
                or not has_operational_data
            )
            if should_process:
                process_excel_and_refresh_database(
                    db,
                    excel_path=file_info["local_path"],
                    source_file_name=file_info["file_name"],
                    source_file_rev=file_info["file_rev"],
                )
                logger.info("Dados atualizados com sucesso: %s", file_info["file_name"])
            else:
                logger.info("Sem mudanças no arquivo do Dropbox.")
        except Exception as exc:
            logger.exception("Erro no job de sincronização: %s", exc)
        finally:
            db.close()

        await asyncio.sleep(settings.update_interval_minutes * 60)
