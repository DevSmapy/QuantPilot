"""Tests for expanded technical indicators."""

from __future__ import annotations

import math

import polars as pl
import pytest

from quantpilot.indicators.atr import atr
from quantpilot.indicators.bollinger import bollinger
from quantpilot.indicators.ema import ema
from quantpilot.indicators.macd import macd


def test_ema_matches_manual_span(sample_prices: pl.DataFrame) -> None:
    values = ema(sample_prices["close"], 5)
    assert values.len() == sample_prices.height
    assert values[0] == pytest.approx(float(sample_prices["close"][0]))
    assert math.isfinite(float(values[-1]))


def test_ema_rejects_invalid_window() -> None:
    with pytest.raises(ValueError):
        ema(pl.Series([1.0, 2.0]), 0)


def test_macd_shape_and_histogram(sample_prices: pl.DataFrame) -> None:
    frame = macd(sample_prices["close"], fast=5, slow=10, signal=3)
    assert frame.columns == ["macd", "signal", "histogram"]
    assert frame.height == sample_prices.height
    last = frame.tail(1)
    assert float(last["histogram"][0]) == pytest.approx(
        float(last["macd"][0]) - float(last["signal"][0])
    )


def test_macd_rejects_fast_ge_slow() -> None:
    with pytest.raises(ValueError):
        macd(pl.Series([1.0, 2.0, 3.0]), fast=10, slow=5)


def test_bollinger_bands_order(sample_prices: pl.DataFrame) -> None:
    frame = bollinger(sample_prices["close"], window=10, num_std=2.0)
    assert frame.columns == ["mid", "upper", "lower"]
    # After warm-up, upper >= mid >= lower when std is defined.
    row = frame.row(-1, named=True)
    assert row["upper"] >= row["mid"] >= row["lower"]


def test_atr_non_negative(sample_prices: pl.DataFrame) -> None:
    values = atr(
        sample_prices["high"],
        sample_prices["low"],
        sample_prices["close"],
        window=5,
    )
    assert values.len() == sample_prices.height
    assert float(values[-1]) >= 0.0


def test_atr_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError, match="same length"):
        atr(pl.Series([1.0, 2.0]), pl.Series([1.0]), pl.Series([1.0, 2.0]))
