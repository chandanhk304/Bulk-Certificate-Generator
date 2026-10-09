"""Application settings, overridable via environment variables or a .env file."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./certificates.db"
    storage_dir: Path = Path("storage/certificates")
    max_recipients_per_job: int = 1000


settings = Settings()
