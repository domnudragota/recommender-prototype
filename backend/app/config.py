from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "WebMediaRecommender"
    app_env: str = "dev"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./data/app.db"
    cors_origins: List[str] = []

settings = Settings()
