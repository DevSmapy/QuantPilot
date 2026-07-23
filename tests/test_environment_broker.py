"""Tests for PaperBroker fill timing, costs, and multi-symbol positions."""

from __future__ import annotations

from datetime import date

import pytest

from quantpilot.environment.broker import PaperBroker
from quantpilot.environment.costs import TradingCosts


def test_buy_then_sell_realizes_cash() -> None:
    broker = PaperBroker(10_000.0)
    assert broker.queue(
        "buy", 1.0, "enter", date(2024, 1, 1), symbol="A.KS"
    ).accepted
    fill_buy = broker.fill_pending(100.0, date(2024, 1, 2))
    assert fill_buy.fill is not None
    assert fill_buy.fill.qty == 100
    assert fill_buy.fill.symbol == "A.KS"
    assert fill_buy.fill.fee == 0.0
    assert broker.qty("A.KS") == 100
    assert broker.cash == 0.0

    equity = broker.mark_to_market({"A.KS": 110.0})
    assert equity == 11_000.0

    assert broker.queue(
        "sell", 1.0, "take profit", date(2024, 1, 2), symbol="A.KS"
    ).accepted
    fill_sell = broker.fill_pending(110.0, date(2024, 1, 3))
    assert fill_sell.fill is not None
    assert broker.qty("A.KS") == 0
    assert broker.cash == 11_000.0
    assert broker.mark_to_market({"A.KS": 120.0}) == 11_000.0


def test_same_day_queue_not_filled() -> None:
    broker = PaperBroker(10_000.0)
    broker.queue("buy", 1.0, "enter", date(2024, 1, 1), symbol="A.KS")
    assert broker.pending is not None
    assert broker.qty("A.KS") == 0
    assert broker.cash == 10_000.0


def test_discard_pending_returns_order() -> None:
    broker = PaperBroker(10_000.0)
    broker.queue("buy", 1.0, "enter", date(2024, 1, 1), symbol="A.KS")
    discarded = broker.discard_pending()
    assert discarded is not None
    assert discarded.action == "buy"
    assert discarded.symbol == "A.KS"
    assert broker.pending is None
    assert broker.fill_pending(100.0, date(2024, 1, 2)).fill is None


def test_sell_requires_reason_at_broker() -> None:
    broker = PaperBroker(10_000.0)
    broker.queue("buy", 1.0, "enter", date(2024, 1, 1), symbol="A.KS")
    broker.fill_pending(100.0, date(2024, 1, 2))
    result = broker.queue("sell", 1.0, "  ", date(2024, 1, 2), symbol="A.KS")
    assert not result.accepted
    assert result.message == "sell_requires_reason"
    assert broker.pending is None


def test_sell_with_zero_qty_rejected() -> None:
    broker = PaperBroker(10_000.0)
    result = broker.queue("sell", 1.0, "oops", date(2024, 1, 1), symbol="A.KS")
    assert not result.accepted
    assert result.message == "sell_zero_qty"


def test_fill_zero_shares_reports_reject() -> None:
    broker = PaperBroker(50.0)
    broker.queue("buy", 1.0, "enter", date(2024, 1, 1), symbol="A.KS")
    result = broker.fill_pending(100.0, date(2024, 1, 2))
    assert result.fill is None
    assert result.rejected_reason == "zero_shares"
    assert broker.pending is None


def test_commission_fee_matches_notional() -> None:
    costs = TradingCosts(commission_rate=0.01, slippage_bps=0.0)
    broker = PaperBroker(10_100.0, costs=costs)
    broker.queue("buy", 1.0, "enter", date(2024, 1, 1), symbol="A.KS")
    fill = broker.fill_pending(100.0, date(2024, 1, 2))
    assert fill.fill is not None
    assert fill.fill.qty == 100
    assert fill.fill.fee == 100.0
    assert broker.cash == pytest.approx(0.0)
    assert broker.total_fees == 100.0


def test_slippage_changes_exec_price() -> None:
    costs = TradingCosts(commission_rate=0.0, slippage_bps=100.0)
    broker = PaperBroker(10_100.0, costs=costs)
    broker.queue("buy", 1.0, "enter", date(2024, 1, 1), symbol="A.KS")
    fill_buy = broker.fill_pending(100.0, date(2024, 1, 2))
    assert fill_buy.fill is not None
    assert fill_buy.fill.price == 101.0
    assert fill_buy.fill.qty == 100

    broker.queue("sell", 1.0, "exit", date(2024, 1, 2), symbol="A.KS")
    fill_sell = broker.fill_pending(100.0, date(2024, 1, 3))
    assert fill_sell.fill is not None
    assert fill_sell.fill.price == 99.0
    assert fill_sell.fill.qty == 100
    assert broker.cash == pytest.approx(100 * 99.0)


def test_multi_symbol_positions_independent() -> None:
    broker = PaperBroker(20_000.0)
    broker.queue("buy", 0.5, "a", date(2024, 1, 1), symbol="A.KS")
    broker.fill_pending(100.0, date(2024, 1, 2))
    broker.queue("buy", 1.0, "b", date(2024, 1, 2), symbol="B.KS")
    broker.fill_pending(50.0, date(2024, 1, 3))
    assert broker.qty("A.KS") == 100
    assert broker.qty("B.KS") == 200
    snap = broker.snapshot({"A.KS": 110.0, "B.KS": 55.0})
    assert snap.holdings == {"A.KS": 100, "B.KS": 200}
    assert snap.equity == broker.cash + 100 * 110.0 + 200 * 55.0
