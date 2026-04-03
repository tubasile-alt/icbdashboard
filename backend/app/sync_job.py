import asyncio
import logging

from .config import settings
from .data_service import process_excel_and_refresh_database
from .database import SessionLocal
from .dropbox_client import download_latest_file_from_dropbox
from .models import Metadata, FactUnidadeMensal

logger = logging.getLogger(__name__)


async def run_sync_loop():
    await asyncio.sleep(30)
    while True:
        db = SessionLocal()
        try:
            print(f"[SYNC] Iniciando sincronização...", flush=True)
            file_info = download_latest_file_from_dropbox()
            metadata = db.get(Metadata, 1)
            
            has_operational_data = False
            if metadata and metadata.source_file_rev == file_info["file_rev"]:
                print(f"[SYNC] Verificando se há dados operacionais no banco...", flush=True)
                from sqlalchemy import func
                count = db.query(func.count(FactUnidadeMensal.id)).scalar() or 0
                print(f"[SYNC] Registros operacionais encontrados: {count}", flush=True)
                if count > 0:
                    has_operational_data = True
            
            if not has_operational_data:
                print(f"[SYNC] Processando arquivo: {file_info['file_name']}", flush=True)
                process_excel_and_refresh_database(
                    db,
                    excel_path=file_info["local_path"],
                    source_file_name=file_info["file_name"],
                    source_file_rev=file_info["file_rev"],
                )
                print(f"[SYNC] Dados atualizados com sucesso: {file_info['file_name']}", flush=True)
                logger.info("Dados atualizados com sucesso: %s", file_info["file_name"])
            else:
                print(f"[SYNC] Dados já processados, sem mudanças", flush=True)
                logger.info("Sem mudanças no arquivo do Dropbox.")
        except Exception as exc:
            print(f"[SYNC] ERRO: {exc}", flush=True)
            logger.exception("Erro no job de sincronização: %s", exc)
        finally:
            db.close()

        await asyncio.sleep(settings.update_interval_minutes * 60)
