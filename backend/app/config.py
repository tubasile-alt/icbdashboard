from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ICB Performance Dashboard API"
    database_url: str = "sqlite:///./icb_dashboard.db"

    dropbox_app_key: str = ""
    dropbox_app_secret: str = ""
    dropbox_refresh_token: str = ""
    dropbox_folder_path: str = "/"
    dropbox_file_extension: str = ".xlsx"

    update_interval_minutes: int = 5
    stale_threshold_hours: int = 6
    frontend_base_url: str = "http://localhost:5173"
    pdf_render_timeout_ms: int = 120000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
