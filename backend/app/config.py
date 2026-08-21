from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loaded from environment / .env. Nothing here is required at import time —
    each secret is validated lazily, at the point it's actually used, so the app
    can boot and serve /health before Firebase or Gemini credentials exist."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    firebase_service_account_path: str = "serviceAccountKey.json"
    cors_allow_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
