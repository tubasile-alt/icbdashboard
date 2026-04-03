import json
from pathlib import Path

import requests

from .config import settings

API_URL = "https://api.dropboxapi.com/2/files/list_folder"
DOWNLOAD_URL = "https://content.dropboxapi.com/2/files/download"


def download_latest_file_from_dropbox(download_dir: str = "./tmp") -> dict:
    if not settings.dropbox_access_token:
        raise RuntimeError("DROPBOX_ACCESS_TOKEN não configurado.")

    headers = {
        "Authorization": f"Bearer {settings.dropbox_access_token}",
        "Content-Type": "application/json",
    }
    is_recursive = not settings.dropbox_folder_path
    payload = {"path": settings.dropbox_folder_path, "recursive": is_recursive, "include_deleted": False}
    response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
    
    if response.status_code != 200:
        error_msg = response.text
        try:
            error_json = response.json()
            error_msg = error_json.get("error_summary", error_msg)
        except:
            pass
        raise RuntimeError(f"Dropbox API Error ({response.status_code}): {error_msg}")
    
    response.raise_for_status()

    entries = response.json().get("entries", [])
    files = [
        f for f in entries if f.get(".tag") == "file" and f.get("name", "").lower().endswith(settings.dropbox_file_extension)
    ]
    if not files:
        raise RuntimeError("Nenhum arquivo Excel encontrado no caminho do Dropbox.")

    latest_file = sorted(files, key=lambda item: item.get("server_modified", ""), reverse=True)[0]

    Path(download_dir).mkdir(parents=True, exist_ok=True)
    local_path = Path(download_dir) / latest_file["name"]

    download_headers = {
        "Authorization": f"Bearer {settings.dropbox_access_token}",
        "Dropbox-API-Arg": json.dumps({"path": latest_file["path_lower"]}),
    }
    dl_response = requests.post(DOWNLOAD_URL, headers=download_headers, timeout=60)
    dl_response.raise_for_status()

    local_path.write_bytes(dl_response.content)
    return {
        "local_path": str(local_path),
        "file_name": latest_file["name"],
        "file_rev": latest_file.get("rev", latest_file.get("id", "unknown")),
        "server_modified": latest_file.get("server_modified"),
    }
