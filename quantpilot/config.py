"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_settings: Settings | None = None


class Settings(BaseSettings):
    """QuantPilot runtime settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    qseed_data_path: Path = Path("/data/qseed")
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2"
    docker: bool = False

    @property
    def data_log_path(self) -> Path:
        """Path to Q-SEED data_log directory."""
        return self.qseed_data_path / "data_log"

    @property
    def parquet_glob(self) -> str:
        """Glob pattern for Q-SEED stock parquet shards."""
        return str(self.qseed_data_path / "stocks_*.parquet")

    @property
    def stocks_db_path(self) -> Path:
        """Path to Q-SEED DuckDB catalog file."""
        return self.qseed_data_path / "stocks.db"


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Clear the cached Settings instance. Intended for tests."""
    global _settings
    _settings = None
