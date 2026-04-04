from pathlib import Path

from .config import settings
from .services.dropbox_service import get_dropbox_manager


def download_latest_file_from_dropbox(download_dir: str = "./tmp") -> dict:
    """
    Baixa o arquivo Excel mais recente do Dropbox.
    Usa OAuth 2.0 com refresh token para autenticação.
    """
    manager = get_dropbox_manager()

    is_recursive = not settings.dropbox_folder_path
    folder_data = manager.list_folder(settings.dropbox_folder_path, recursive=is_recursive)

    entries = folder_data.get("entries", [])
    files = [
        f
        for f in entries
        if f.get(".tag") == "file" and f.get("name", "").lower().endswith(settings.dropbox_file_extension)
    ]
    if not files:
        raise RuntimeError("Nenhum arquivo Excel encontrado no caminho do Dropbox.")

    latest_file = sorted(files, key=lambda item: item.get("server_modified", ""), reverse=True)[0]

    Path(download_dir).mkdir(parents=True, exist_ok=True)
    local_path = Path(download_dir) / latest_file["name"]

    file_content = manager.download_file(latest_file["path_lower"])
    local_path.write_bytes(file_content)

    return {
        "local_path": str(local_path),
        "file_name": latest_file["name"],
        "file_rev": latest_file.get("rev", latest_file.get("id", "unknown")),
        "server_modified": latest_file.get("server_modified"),
    }
