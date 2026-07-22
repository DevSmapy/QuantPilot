"""Shared pytest fixtures."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import polars as pl
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_prices() -> pl.DataFrame:
    """Synthetic OHLCV data for unit tests."""
    start = date(2023, 1, 1)
    rows: list[dict[str, object]] = []
    price = 100.0
    for i in range(120):
        current = start + timedelta(days=i)
        price += (i % 7 - 3) * 0.5
        rows.append(
            {
                "symbol": "TEST.KS",
                "date": current,
                "open": price - 0.5,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price,
                "volume": 1000 + i,
                "market": "KOSPI",
            }
        )
    return pl.DataFrame(rows).with_columns(
        pl.col("symbol").cast(pl.Utf8),
        pl.col("market").cast(pl.Utf8),
        pl.col("date").cast(pl.Date),
        pl.col("volume").cast(pl.Int64),
    )


@pytest.fixture
def sample_parquet_path(tmp_path: Path, sample_prices: pl.DataFrame) -> Path:
    """Write synthetic OHLCV parquet in Q-SEED-compatible column names."""
    qseed_frame = sample_prices.rename(
        {
            "symbol": "Ticker",
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "market": "Market",
        }
    ).with_columns(pl.col("Date").cast(pl.Datetime))
    path = tmp_path / "stocks_0001.parquet"
    qseed_frame.write_parquet(path)
    return path
