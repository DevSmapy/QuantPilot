"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_settings: Settings | None = None

_DOCKER_OLLAMA_HOSTS = frozenset(
    {
        "http://ollama:11434",
        "http://ollama:11434/",
    }
)


def running_in_docker() -> bool:
    """Return True when the process is inside a Docker container."""
    return Path("/.dockerenv").exists() or os.environ.get("QUANTPILOT_IN_DOCKER") == "1"


class Settings(BaseSettings):
    """QuantPilot runtime settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    qseed_data_path: Path = Path("/data/qseed")
    qseed_host_path: Path | None = None
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2"
    # Informational DOCKER= env flag only. Path/URL resolution uses
    # ``running_in_docker()`` (/.dockerenv or QUANTPILOT_IN_DOCKER), not this field.
    docker: bool = False

    @model_validator(mode="after")
    def resolve_local_overrides(self) -> Self:
        """Prefer host paths/URLs when running outside Docker.

        One .env can serve both Docker Compose and local ``uv run`` on Mac/Windows:
        - ``QSEED_HOST_PATH`` = real host data directory
        - ``QSEED_DATA_PATH=/data/qseed`` = container mount (used when it exists)
        - ``OLLAMA_BASE_URL=http://ollama:11434`` rewritten to localhost on host

        Resolution keys off ``running_in_docker()``, not the ``docker`` setting.
        """
        if not running_in_docker():
            if not self.qseed_data_path.exists() and self.qseed_host_path is not None:
                if self.qseed_host_path.exists():
                    object.__setattr__(self, "qseed_data_path", self.qseed_host_path)

            if self.ollama_base_url.rstrip("/") in {
                u.rstrip("/") for u in _DOCKER_OLLAMA_HOSTS
            }:
                object.__setattr__(self, "ollama_base_url", "http://localhost:11434")

        return self

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
