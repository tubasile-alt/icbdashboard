import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DROPBOX_AUTH_URL = "https://api.dropboxapi.com/oauth2/token"
DROPBOX_LIST_FOLDER_URL = "https://api.dropboxapi.com/2/files/list_folder"
DROPBOX_DOWNLOAD_URL = "https://content.dropboxapi.com/2/files/download"


class DropboxOAuthManager:
    """Gerencia autenticação OAuth 2.0 com refresh token do Dropbox."""

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        refresh_token: str,
    ):
        self.app_key = app_key
        self.app_secret = app_secret
        self.refresh_token = refresh_token

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

        if not all([app_key, app_secret, refresh_token]):
            raise RuntimeError(
                "DROPBOX_APP_KEY, DROPBOX_APP_SECRET e DROPBOX_REFRESH_TOKEN são obrigatórios"
            )

    def get_valid_access_token(self) -> str:
        """
        Retorna um access token válido.
        Se o token atual expirou, renova automaticamente.
        """
        current_time = time.time()

        if self._access_token and current_time < self._token_expires_at:
            logger.debug("Usando access token em cache")
            return self._access_token

        logger.info("Renovando access token do Dropbox...")
        self._refresh_access_token()
        
        if not self._access_token:
            raise RuntimeError("Falha ao obter access token")
        
        return self._access_token

    def _refresh_access_token(self) -> None:
        """Obtém um novo access token usando refresh token."""
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.app_key,
            "client_secret": self.app_secret,
        }

        try:
            response = requests.post(DROPBOX_AUTH_URL, data=payload, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Erro ao renovar token Dropbox: {e}")
            raise RuntimeError(f"Falha ao renovar access token: {e}")

        data = response.json()

        if "error" in data:
            error_desc = data.get("error_description", data.get("error"))
            logger.error(f"Erro OAuth Dropbox: {error_desc}")
            raise RuntimeError(
                f"Erro na renovação do token: {error_desc}. "
                f"Verifique DROPBOX_APP_KEY, DROPBOX_APP_SECRET e DROPBOX_REFRESH_TOKEN."
            )

        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = time.time() + (expires_in - 60)

        logger.info(f"Access token renovado (expira em {expires_in}s)")

    def verify_connection(self) -> dict:
        """Testa a conexão com Dropbox listando a raiz."""
        token = self.get_valid_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {"path": "", "recursive": False, "include_deleted": False}

        try:
            response = requests.post(
                DROPBOX_LIST_FOLDER_URL, headers=headers, json=payload, timeout=10
            )
            response.raise_for_status()
            entries = response.json().get("entries", [])
            return {
                "status": "success",
                "message": f"Conexão validada. {len(entries)} itens na raiz.",
                "entries_count": len(entries),
            }
        except requests.RequestException as e:
            logger.error(f"Erro ao verificar conexão Dropbox: {e}")
            raise RuntimeError(f"Falha ao verificar conexão: {e}")

    def list_folder(self, path: str = "/", recursive: bool = False) -> dict:
        """Lista arquivos em um caminho do Dropbox."""
        token = self.get_valid_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {"path": path, "recursive": recursive, "include_deleted": False}

        response = requests.post(
            DROPBOX_LIST_FOLDER_URL, headers=headers, json=payload, timeout=30
        )

        if response.status_code != 200:
            error_msg = response.text
            try:
                error_json = response.json()
                error_msg = error_json.get("error_summary", error_msg)
            except Exception:
                pass
            raise RuntimeError(f"Dropbox API Error ({response.status_code}): {error_msg}")

        return response.json()

    def download_file(self, dropbox_path: str) -> bytes:
        """Baixa um arquivo do Dropbox."""
        token = self.get_valid_access_token()
        import json

        headers = {
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": json.dumps({"path": dropbox_path}),
        }

        response = requests.post(DROPBOX_DOWNLOAD_URL, headers=headers, timeout=60)
        response.raise_for_status()
        return response.content


# Instância global (será inicializada na startup)
_dropbox_manager: Optional[DropboxOAuthManager] = None


def init_dropbox(app_key: str, app_secret: str, refresh_token: str) -> DropboxOAuthManager:
    """Inicializa o gerenciador Dropbox com credenciais."""
    global _dropbox_manager
    _dropbox_manager = DropboxOAuthManager(app_key, app_secret, refresh_token)
    logger.info("DropboxOAuthManager inicializado")
    return _dropbox_manager


def get_dropbox_manager() -> DropboxOAuthManager:
    """Retorna a instância global do gerenciador Dropbox."""
    if _dropbox_manager is None:
        raise RuntimeError("DropboxOAuthManager não foi inicializado. Chame init_dropbox() primeiro.")
    return _dropbox_manager
