"""Tests for PaperBroker fill timing and sell cash realization."""

from __future__ import annotations

from datetime import date

from quantpilot.environment.broker import PaperBroker


def test_buy_then_sell_realizes_cash() -> None:
    broker = PaperBroker(10_000.0)
    assert broker.queue("buy", 1.0, "enter", date(2024, 1, 1)).accepted
    fill_buy = broker.fill_pending(100.0, date(2024, 1, 2))
    assert fill_buy.fill is not None
    assert fill_buy.fill.qty == 100
    assert broker.qty == 100
    assert broker.cash == 0.0

    equity = broker.mark_to_market(110.0)
    assert equity == 11_000.0

    assert broker.queue("sell", 1.0, "take profit", date(2024, 1, 2)).accepted
    fill_sell = broker.fill_pending(110.0, date(2024, 1, 3))
    assert fill_sell.fill is not None
    assert broker.qty == 0
    assert broker.cash == 11_000.0
    assert broker.mark_to_market(120.0) == 11_000.0


def test_same_day_queue_not_filled() -> None:
    broker = PaperBroker(10_000.0)
    broker.queue("buy", 1.0, "enter", date(2024, 1, 1))
    assert broker.pending is not None
    assert broker.qty == 0
    assert broker.cash == 10_000.0


def test_discard_pending_returns_order() -> None:
    broker = PaperBroker(10_000.0)
    broker.queue("buy", 1.0, "enter", date(2024, 1, 1))
    discarded = broker.discard_pending()
    assert discarded is not None
    assert discarded.action == "buy"
    assert broker.pending is None
    assert broker.fill_pending(100.0, date(2024, 1, 2)).fill is None


def test_sell_requires_reason_at_broker() -> None:
    broker = PaperBroker(10_000.0)
    broker.queue("buy", 1.0, "enter", date(2024, 1, 1))
    broker.fill_pending(100.0, date(2024, 1, 2))
    result = broker.queue("sell", 1.0, "  ", date(2024, 1, 2))
    assert not result.accepted
    assert result.message == "sell_requires_reason"
    assert broker.pending is None


def test_sell_with_zero_qty_rejected() -> None:
    broker = PaperBroker(10_000.0)
    result = broker.queue("sell", 1.0, "oops", date(2024, 1, 1))
    assert not result.accepted
    assert result.message == "sell_zero_qty"


def test_fill_zero_shares_reports_reject() -> None:
    broker = PaperBroker(50.0)
    broker.queue("buy", 1.0, "enter", date(2024, 1, 1))
    result = broker.fill_pending(100.0, date(2024, 1, 2))
    assert result.fill is None
    assert result.rejected_reason == "zero_shares"
    assert broker.pending is None
