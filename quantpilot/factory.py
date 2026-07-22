"""Factory helpers for wiring QuantPilot components."""

from __future__ import annotations

from pathlib import Path

from quantpilot.ai.ollama_provider import OllamaProvider
from quantpilot.config import Settings, get_settings
from quantpilot.datasource.datasource_manager import DataSourceManager
from quantpilot.datasource.metadata_manager import MetadataManager
from quantpilot.providers.qseed_provider import QSeedProvider


def create_datasource_manager(
    settings: Settings | None = None,
    cache_path: Path | None = None,
) -> DataSourceManager:
    """Build a DataSourceManager with Q-SEED as the primary provider."""
    cfg = settings or get_settings()
    metadata = MetadataManager(cfg.data_log_path)
    cache = cache_path or Path("storage/metadata")
    qseed = QSeedProvider(cfg.qseed_data_path, metadata, cache_path=cache)
    return DataSourceManager([qseed])


def create_ollama_provider(settings: Settings | None = None) -> OllamaProvider:
    """Build an OllamaProvider from application settings."""
    cfg = settings or get_settings()
    return OllamaProvider(base_url=cfg.ollama_base_url, model=cfg.ollama_model)
