"""Tests for AnalysisBrief schema and builder."""

from __future__ import annotations

import json
from datetime import date

import polars as pl
import pytest

from quantpilot.analysis.brief import brief_to_prompt_block, json_safe_float
from quantpilot.analysis.build_brief import build_analysis_brief
from quantpilot.backtest.engine import BacktestEngine, BacktestResult
from quantpilot.strategy.sma_cross import SMACrossStrategy


def test_json_safe_float_maps_inf_to_none() -> None:
    assert json_safe_float(float("inf")) is None
    assert json_safe_float(float("nan")) is None
    assert json_safe_float(1.5) == 1.5


def test_build_analysis_brief_round_trips_json(sample_prices: pl.DataFrame) -> None:
    strategy = SMACrossStrategy(fast_window=5, slow_window=20)
    signals = strategy.run(sample_prices)
    result = BacktestEngine().run(sample_prices, signals)
    brief = build_analysis_brief(
        prices=sample_prices,
        signals=signals,
        result=result,
        strategy_name="sma_cross",
        strategy_params={"fast_window": 5, "slow_window": 20},
        symbol="TEST.KS",
    )
    payload = brief.to_dict()
    assert payload["schema_version"] == "1"
    assert payload["symbol"] == "TEST.KS"
    assert payload["strategy"]["name"] == "sma_cross"
    assert payload["strategy"]["params"]["fast_window"] == 5
    assert payload["metrics"]["trades_count"] == result.trades_count
    assert "sma_20" in payload["indicators_snapshot"]
    assert "rsi_14" in payload["indicators_snapshot"]
    raw = brief.to_json()
    loaded = json.loads(raw)
    assert loaded["as_of"] == result.end_date
    assert "```json" in brief_to_prompt_block(brief)
    assert isinstance(brief.notes, tuple)


def test_build_analysis_brief_as_of_truncates_metrics(
    sample_prices: pl.DataFrame,
) -> None:
    strategy = SMACrossStrategy(fast_window=5, slow_window=20)
    signals = strategy.run(sample_prices)
    result = BacktestEngine().run(sample_prices, signals)
    as_of = date(2023, 2, 1)
    brief = build_analysis_brief(
        prices=sample_prices,
        signals=signals,
        result=result,
        strategy_name="sma_cross",
        as_of=as_of,
        symbol="TEST.KS",
    )
    assert brief.as_of == "2023-02-01"
    assert brief.window.end == "2023-02-01"
    truncated = BacktestEngine().run(
        sample_prices.filter(pl.col("date") <= as_of),
        signals.filter(pl.col("date") <= as_of),
    )
    assert brief.metrics.total_return == pytest.approx(truncated.total_return)
    assert brief.metrics.trades_count == truncated.trades_count
    assert brief.signals_summary.buy_count <= int(
        signals.filter(pl.col("date") <= as_of)["signal"].eq(1).sum()
    )


def test_build_analysis_brief_rejects_multi_symbol_without_symbol() -> None:
    result = BacktestResult(
        total_return=0.0,
        cagr=0.0,
        mdd=0.0,
        sharpe=0.0,
        sortino=0.0,
        profit_factor=0.0,
        win_rate=0.0,
        trades_count=0,
        start_date="2024-01-01",
        end_date="2024-01-02",
        equity_curve=[1.0, 1.0],
    )
    prices = pl.DataFrame(
        {
            "date": [date(2024, 1, 1), date(2024, 1, 2)],
            "close": [100.0, 101.0],
            "symbol": ["A.KS", "B.KS"],
        }
    )
    signals = pl.DataFrame(
        {"date": [date(2024, 1, 1), date(2024, 1, 2)], "signal": [0, 0]}
    )
    with pytest.raises(ValueError, match="multiple symbols"):
        build_analysis_brief(
            prices=prices,
            signals=signals,
            result=result,
            strategy_name="x",
        )


def test_infinite_profit_factor_becomes_null() -> None:
    result = BacktestResult(
        total_return=0.1,
        cagr=0.1,
        mdd=-0.01,
        sharpe=1.0,
        sortino=1.2,
        profit_factor=float("inf"),
        win_rate=1.0,
        trades_count=2,
        start_date="2024-01-01",
        end_date="2024-01-10",
        equity_curve=[1.0, 1.1],
        trade_pnls=[0.1],
    )
    prices = pl.DataFrame(
        {
            "date": [date(2024, 1, 1), date(2024, 1, 10)],
            "close": [100.0, 110.0],
            "symbol": ["X.KS", "X.KS"],
        }
    )
    signals = pl.DataFrame(
        {
            "date": [date(2024, 1, 1), date(2024, 1, 10)],
            "signal": [1, -1],
        }
    )
    brief = build_analysis_brief(
        prices=prices,
        signals=signals,
        result=result,
        strategy_name="sma_cross",
        symbol="X.KS",
    )
    assert brief.metrics.profit_factor is None
    assert any("infinite" in n.lower() for n in brief.notes)
    json.loads(brief.to_json())


def test_brief_rejects_missing_columns() -> None:
    result = BacktestResult(
        total_return=0.0,
        cagr=0.0,
        mdd=0.0,
        sharpe=0.0,
        sortino=0.0,
        profit_factor=0.0,
        win_rate=0.0,
        trades_count=0,
        start_date="2024-01-01",
        end_date="2024-01-02",
    )
    with pytest.raises(ValueError, match="prices must contain"):
        build_analysis_brief(
            prices=pl.DataFrame({"close": [1.0]}),
            signals=pl.DataFrame({"date": [date(2024, 1, 1)], "signal": [0]}),
            result=result,
            strategy_name="x",
        )
