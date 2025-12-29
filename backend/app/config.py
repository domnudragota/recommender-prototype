from typing import List
import json

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # read raw string from env (works with comma-separated values)
    cors_origins: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        s = (self.cors_origins or "").strip()
        if not s:
            return []
        if s.startswith("["):
            # also accept JSON list
            return [str(x) for x in json.loads(s)]
        return [part.strip() for part in s.split(",") if part.strip()]


settings = Settings()
