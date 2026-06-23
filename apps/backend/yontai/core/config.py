from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YONTAI_", env_file=".env", extra="ignore")

    env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8765
    database_url: str = "sqlite:///./yontai.db"
    app_data_dir: Path = Field(default=Path("../../"))
    mlflow_tracking_dir: Path = Field(default=Path("../../runs/mlflow"))
    ollama_host: str = "http://127.0.0.1:11434"
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:1420",
            "http://127.0.0.1:1420",
            "tauri://localhost",
            "http://tauri.localhost",
            "https://tauri.localhost"
        ]
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
