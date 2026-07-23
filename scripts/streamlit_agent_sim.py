#!/usr/bin/env python3
"""Streamlit UI for agent paper-trading equity and trade markers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import cast

import plotly.graph_objects as go
import streamlit as st

from quantpilot.agent.hold import HoldAgent
from quantpilot.agent.llm import LlmTradingAgent
from quantpilot.console import configure_stdio
from quantpilot.environment.costs import TradingCosts
from quantpilot.environment.market import HistoricalMarket, intersect_session_dates
from quantpilot.environment.types import Fill
from quantpilot.factory import create_datasource_manager, create_ollama_provider
from quantpilot.simulation.result import SimResult
from quantpilot.simulation.session import ProgressEvent, SimulationSession

DEFAULT_LOOKBACK = 60


@dataclass
class _TradeMarker:
    day: str
    equity: float
    price: float
    text: str
    symbol: str


@dataclass
class _LiveChartState:
    """Growing equity / price / trade series while a session runs."""

    dates: list[str] = field(default_factory=list)
    equities: list[float] = field(default_factory=list)
    closes: list[float] = field(default_factory=list)
    buys: list[_TradeMarker] = field(default_factory=list)
    sells: list[_TradeMarker] = field(default_factory=list)
    day_index: int = 0

    def observe(
        self,
        event: ProgressEvent,
        *,
        close_price: float,
    ) -> None:
        if event.discarded_pending:
            return
        self.day_index += 1
        day = event.date.isoformat()
        self.dates.append(day)
        self.equities.append(event.equity)
        self.closes.append(close_price)
        if event.fill is not None:
            self._record_fill(event.fill, event.equity)

    def _record_fill(self, fill: Fill, equity: float) -> None:
        marker = _TradeMarker(
            day=fill.date.isoformat(),
            equity=equity,
            price=fill.price,
            text=f"{fill.symbol} {fill.qty}@{fill.price:.2f}",
            symbol=fill.symbol,
        )
        if fill.action == "buy":
            self.buys.append(marker)
        elif fill.action == "sell":
            self.sells.append(marker)


def _parse_symbols(raw: str) -> list[str]:
    symbols = [s.strip() for s in raw.split(",") if s.strip()]
    if not symbols:
        raise ValueError("Enter at least one symbol")
    return symbols


def _load_markets(
    symbols: list[str],
    start: date,
    end: date,
    lookback_sessions: int,
) -> dict[str, HistoricalMarket]:
    load_start = start - timedelta(days=max(lookback_sessions * 3, 90))
    manager = create_datasource_manager()
    return {
        symbol: HistoricalMarket(manager.get_price(symbol, load_start, end))
        for symbol in symbols
    }


def _session_close(market: HistoricalMarket, on: date) -> float:
    return float(cast(float, market.bar(on)["close"]))


def _add_trade_markers(
    fig: go.Figure,
    *,
    buys: list[_TradeMarker],
    sells: list[_TradeMarker],
    y_attr: str,
    symbol_filter: str | None = None,
) -> None:
    buy_pts = [m for m in buys if symbol_filter is None or m.symbol == symbol_filter]
    sell_pts = [m for m in sells if symbol_filter is None or m.symbol == symbol_filter]
    if buy_pts:
        fig.add_trace(
            go.Scatter(
                x=[m.day for m in buy_pts],
                y=[getattr(m, y_attr) for m in buy_pts],
                mode="markers",
                name="Buy",
                marker={"symbol": "triangle-up", "size": 11, "color": "green"},
                text=[m.text for m in buy_pts],
                hovertemplate="%{text}<extra></extra>",
            )
        )
    if sell_pts:
        fig.add_trace(
            go.Scatter(
                x=[m.day for m in sell_pts],
                y=[getattr(m, y_attr) for m in sell_pts],
                mode="markers",
                name="Sell",
                marker={"symbol": "triangle-down", "size": 11, "color": "red"},
                text=[m.text for m in sell_pts],
                hovertemplate="%{text}<extra></extra>",
            )
        )


def _build_equity_figure(
    *,
    dates: list[str],
    equities: list[float],
    buys: list[_TradeMarker],
    sells: list[_TradeMarker],
    buy_and_hold_equity: float | None = None,
    title: str = "Portfolio equity",
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=equities, mode="lines", name="Agent equity"))
    if buy_and_hold_equity is not None and dates:
        fig.add_hline(
            y=buy_and_hold_equity,
            line_dash="dash",
            annotation_text="Buy&Hold final",
        )
    _add_trade_markers(fig, buys=buys, sells=sells, y_attr="equity")
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Equity",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )
    return fig


def _build_price_figure(
    *,
    dates: list[str],
    closes: list[float],
    buys: list[_TradeMarker],
    sells: list[_TradeMarker],
    price_symbol: str,
    title: str | None = None,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=dates, y=closes, mode="lines", name=f"{price_symbol} close")
    )
    _add_trade_markers(
        fig,
        buys=buys,
        sells=sells,
        y_attr="price",
        symbol_filter=price_symbol,
    )
    fig.update_layout(
        title=title or f"Price — {price_symbol}",
        xaxis_title="Date",
        yaxis_title="Price",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )
    return fig


def _markers_from_result(result: SimResult) -> tuple[list[_TradeMarker], list[_TradeMarker]]:
    equity_by_date = {p.date: p.equity for p in result.equity_curve}
    buys: list[_TradeMarker] = []
    sells: list[_TradeMarker] = []
    for fill in result.fills:
        marker = _TradeMarker(
            day=fill.date.isoformat(),
            equity=equity_by_date.get(fill.date, result.final_equity),
            price=fill.price,
            text=f"{fill.symbol} {fill.qty}@{fill.price:.2f}",
            symbol=fill.symbol,
        )
        if fill.action == "buy":
            buys.append(marker)
        elif fill.action == "sell":
            sells.append(marker)
    return buys, sells


def _closes_for_dates(
    market: HistoricalMarket,
    dates: list[date],
) -> list[float]:
    return [_session_close(market, on) for on in dates]


def _should_redraw(event: ProgressEvent, day_index: int, total_days: int) -> bool:
    """Redraw often enough to feel live without Plotly thrash on every quiet day."""
    if event.fill is not None or event.decision is not None:
        return True
    if day_index == 1 or day_index >= total_days:
        return True
    return day_index % 5 == 0


def _render_charts(
    *,
    equity_box: object,
    price_box: object,
    dates: list[str],
    equities: list[float],
    closes: list[float],
    buys: list[_TradeMarker],
    sells: list[_TradeMarker],
    price_symbol: str,
    buy_and_hold_equity: float | None = None,
    live: bool = False,
    as_of: date | None = None,
) -> None:
    equity_title = "Portfolio equity"
    price_title = f"Price — {price_symbol}"
    if live and as_of is not None:
        equity_title = f"Portfolio equity (live) — {as_of}"
        price_title = f"Price — {price_symbol} (live) — {as_of}"
    with equity_box.container():
        st.plotly_chart(
            _build_equity_figure(
                dates=dates,
                equities=equities,
                buys=buys,
                sells=sells,
                buy_and_hold_equity=buy_and_hold_equity,
                title=equity_title,
            ),
            width="stretch",
        )
    with price_box.container():
        st.plotly_chart(
            _build_price_figure(
                dates=dates,
                closes=closes,
                buys=buys,
                sells=sells,
                price_symbol=price_symbol,
                title=price_title,
            ),
            width="stretch",
        )


def main() -> None:
    configure_stdio()
    st.set_page_config(page_title="QuantPilot Agent Sim", layout="wide")
    st.title("QuantPilot Agent Simulation")

    with st.sidebar:
        symbols_raw = st.text_input("Symbols (comma-separated)", "005930.KS")
        start = st.date_input("Start", value=date(2024, 1, 2))
        period_days = st.number_input("Period days", min_value=1, value=90)
        capital = st.number_input("Capital", min_value=1.0, value=10_000_000.0, step=100_000.0)
        target = st.number_input("Target", min_value=1.0, value=12_000_000.0, step=100_000.0)
        decision_every = st.number_input("Decision every N sessions", min_value=1, value=5)
        commission_rate = st.number_input(
            "Commission rate", min_value=0.0, value=0.0, format="%.6f"
        )
        slippage_bps = st.number_input("Slippage bps", min_value=0.0, value=0.0)
        hold_only = st.checkbox("Hold only (no LLM)", value=True)
        run = st.button("Run simulation", type="primary")

    if not run:
        st.info("Configure parameters and click Run simulation.")
        return

    status_box = st.empty()
    progress_bar = st.progress(0.0, text="Starting simulation…")
    metrics_box = st.empty()
    equity_box = st.empty()
    price_box = st.empty()
    caption_box = st.empty()

    try:
        symbols = _parse_symbols(symbols_raw)
        start_d = start if isinstance(start, date) else start
        end = start_d + timedelta(days=int(period_days))
        markets = _load_markets(symbols, start_d, end, DEFAULT_LOOKBACK)
        for symbol, market in markets.items():
            prior = market.prior_session_count(start_d)
            if prior < DEFAULT_LOOKBACK:
                st.error(
                    f"Need {DEFAULT_LOOKBACK} lookback sessions for {symbol}, found {prior}."
                )
                return
        sessions = intersect_session_dates(markets, start_d, end)
        if not sessions:
            st.error("No overlapping trading sessions in the window.")
            return

        price_symbol = symbols[0]
        price_market = markets[price_symbol]

        agent: HoldAgent | LlmTradingAgent
        if hold_only:
            agent = HoldAgent()
        else:
            agent = LlmTradingAgent(create_ollama_provider())

        live = _LiveChartState()
        total_days = len(sessions)

        def on_progress(event: ProgressEvent) -> None:
            close_px = _session_close(price_market, event.date)
            live.observe(event, close_price=close_px)
            if event.discarded_pending:
                status_box.warning("Last-day pending order discarded (no next open).")
                return

            frac = live.day_index / total_days if total_days else 1.0
            detail = f"{event.date} · equity={event.equity:,.0f} · cash={event.cash:,.0f}"
            if event.fill is not None:
                detail += (
                    f" · fill={event.fill.symbol}:{event.fill.action}"
                    f":{event.fill.qty}@{event.fill.price:.2f}"
                )
            if event.decision is not None:
                detail += f" · action={event.decision.action}"
            progress_bar.progress(
                min(frac, 1.0),
                text=f"Simulating {live.day_index}/{total_days}: {detail}",
            )
            status_box.info(f"In progress — {detail}")

            if _should_redraw(event, live.day_index, total_days):
                _render_charts(
                    equity_box=equity_box,
                    price_box=price_box,
                    dates=live.dates,
                    equities=live.equities,
                    closes=live.closes,
                    buys=live.buys,
                    sells=live.sells,
                    price_symbol=price_symbol,
                    live=True,
                    as_of=event.date,
                )

        result = SimulationSession(
            markets=markets,
            agent=agent,
            symbols=symbols,
            capital=float(capital),
            target=float(target),
            decision_every=int(decision_every),
            costs=TradingCosts(
                commission_rate=float(commission_rate),
                slippage_bps=float(slippage_bps),
            ),
            on_progress=on_progress,
        ).run(start_d, end)
    except Exception as exc:
        progress_bar.empty()
        status_box.empty()
        st.exception(exc)
        return

    progress_bar.progress(1.0, text="Simulation complete")
    status_box.success(
        f"Done — {result.start} ~ {result.end} · "
        f"final equity={result.final_equity:,.0f}"
    )

    with metrics_box.container():
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Final equity", f"{result.final_equity:,.0f}")
        c2.metric("Return", f"{result.total_return:+.2%}")
        c3.metric("Total fees", f"{result.total_fees:,.0f}")
        c4.metric("Hit target", str(result.hit_target))
        bah = result.buy_and_hold_equity
        c5.metric("Buy&Hold", f"{bah:,.0f}" if bah is not None else "n/a")

    buys, sells = _markers_from_result(result)
    curve_dates = [p.date for p in result.equity_curve]
    _render_charts(
        equity_box=equity_box,
        price_box=price_box,
        dates=[d.isoformat() for d in curve_dates],
        equities=[p.equity for p in result.equity_curve],
        closes=_closes_for_dates(price_market, curve_dates),
        buys=buys,
        sells=sells,
        price_symbol=price_symbol,
        buy_and_hold_equity=result.buy_and_hold_equity,
    )
    note = ""
    if len(result.symbols) > 1:
        note = f" Price panel shows {price_symbol} (first symbol); markers there are for that ticker only."
    caption_box.caption(
        f"Symbols: {', '.join(result.symbols)} | "
        f"{result.start} ~ {result.end} | "
        f"fills={len(result.fills)} decisions={len(result.decisions)}."
        f"{note}"
    )


if __name__ == "__main__":
    main()
