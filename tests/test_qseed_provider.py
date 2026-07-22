"""Tests for QSeedProvider."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from quantpilot.datasource.metadata_manager import MetadataManager
from quantpilot.exceptions import DataNotAvailableError, SymbolNotFoundError
from quantpilot.providers.qseed_provider import QSeedProvider


def _setup_qseed_tree(tmp_path: Path) -> tuple[Path, MetadataManager]:
    data_path = tmp_path / "data"
    data_log = data_path / "data_log"
    data_log.mkdir(parents=True)
    (data_log / "krx_list.csv").write_text(
        "Ticker,Market\nTEST.KS,KOSPI\n",
        encoding="utf-8",
    )
    (data_log / "last_date.txt").write_text("2023-04-30\n", encoding="utf-8")
    return data_path, MetadataManager(data_log)


def test_qseed_provider_reads_parquet_shard(
    tmp_path: Path, sample_parquet_path: Path
) -> None:
    data_path, metadata = _setup_qseed_tree(tmp_path)
    target = data_path / "stocks_0001.parquet"
    target.write_bytes(sample_parquet_path.read_bytes())

    provider = QSeedProvider(data_path, metadata, cache_path=tmp_path / "cache")
    result = provider.get_price("TEST.KS", date(2023, 1, 1), date(2023, 4, 30))

    assert not result.is_empty()
    assert set(result.columns) == {
        "symbol",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "market",
    }
    assert result["symbol"][0] == "TEST.KS"


def test_qseed_provider_unknown_symbol(tmp_path: Path) -> None:
    data_path, metadata = _setup_qseed_tree(tmp_path)
    provider = QSeedProvider(data_path, metadata, cache_path=tmp_path / "cache")

    with pytest.raises(SymbolNotFoundError):
        provider.get_price("UNKNOWN.KS", date(2023, 1, 1), date(2023, 1, 31))


def test_qseed_provider_empty_range(tmp_path: Path, sample_parquet_path: Path) -> None:
    data_path, metadata = _setup_qseed_tree(tmp_path)
    target = data_path / "stocks_0001.parquet"
    target.write_bytes(sample_parquet_path.read_bytes())

    provider = QSeedProvider(data_path, metadata, cache_path=tmp_path / "cache")
    with pytest.raises(DataNotAvailableError):
        provider.get_price("TEST.KS", date(2025, 1, 1), date(2025, 1, 31))


@pytest.mark.integration
def test_qseed_provider_integration() -> None:
    from quantpilot.config import get_settings
    from quantpilot.factory import create_datasource_manager

    settings = get_settings()
    if not settings.qseed_data_path.exists():
        pytest.skip("Q-SEED data path not mounted")

    manager = create_datasource_manager(settings)
    prices = manager.get_price("005930.KS", date(2023, 1, 1), date(2023, 12, 31))
    assert not prices.is_empty()
    assert prices["symbol"].unique().to_list() == ["005930.KS"]
