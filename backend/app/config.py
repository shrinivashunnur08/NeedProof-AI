
from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_cloud_project: str = ""
    google_cloud_location: str = "global"
    gemini_model: str = "gemini-2.5-flash"
    ai_mode: str = "LIVE_VERTEX"
    maps_api_key: str = ""
    assurance_operator_key: str = ""

    # Chunk 3: Operational database
    database_backend: Literal["sqlite", "cloud_sql"] = "sqlite"
    database_url: str = "sqlite:///./needproof_dev.db"

    # Future Cloud SQL configuration
    cloud_sql_instance: str = ""
    cloud_sql_ip_type: Literal["PUBLIC", "PRIVATE"] = "PUBLIC"
    db_user: str = ""
    db_password: str = ""
    db_name: str = "needproof"

    environment: Literal["development", "production"] = "development"
    demo_write_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
