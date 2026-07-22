"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    """Return cached settings instance."""
    return Settings()
