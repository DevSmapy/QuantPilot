#!/usr/bin/env python3
"""Streamlit UI for agent paper-trading equity and trade markers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

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
class _LiveChartState:
    """Growing equity / trade series while a session runs."""

    dates: list[str] = field(default_factory=list)
    equities: list[float] = field(default_factory=list)
    buy_dates: list[str] = field(default_factory=list)
    buy_equities: list[float] = field(default_factory=list)
    buy_text: list[str] = field(default_factory=list)
    sell_dates: list[str] = field(default_factory=list)
    sell_equities: list[float] = field(default_factory=list)
    sell_text: list[str] = field(default_factory=list)
    day_index: int = 0

    def observe(self, event: ProgressEvent) -> None:
        if event.discarded_pending:
            return
        self.day_index += 1
        day = event.date.isoformat()
        self.dates.append(day)
        self.equities.append(event.equity)
        if event.fill is not None:
            self._record_fill(event.fill, event.equity)

    def _record_fill(self, fill: Fill, equity: float) -> None:
        day = fill.date.isoformat()
        label = f"{fill.symbol} {fill.qty}@{fill.price:.2f}"
        if fill.action == "buy":
            self.buy_dates.append(day)
            self.buy_equities.append(equity)
            self.buy_text.append(label)
        elif fill.action == "sell":
            self.sell_dates.append(day)
            self.sell_equities.append(equity)
            self.sell_text.append(label)


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


def _build_figure(
    *,
    dates: list[str],
    equities: list[float],
    buy_dates: list[str] | None = None,
    buy_equities: list[float] | None = None,
    buy_text: list[str] | None = None,
    sell_dates: list[str] | None = None,
    sell_equities: list[float] | None = None,
    sell_text: list[str] | None = None,
    buy_and_hold_equity: float | None = None,
    title: str = "Equity and trade markers",
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=equities, mode="lines", name="Agent equity"))

    if buy_and_hold_equity is not None and dates:
        fig.add_hline(
            y=buy_and_hold_equity,
            line_dash="dash",
            annotation_text="Buy&Hold final",
        )

    if buy_dates and buy_equities:
        fig.add_trace(
            go.Scatter(
                x=buy_dates,
                y=buy_equities,
                mode="markers",
                name="Buy",
                marker={"symbol": "triangle-up", "size": 10, "color": "green"},
                text=buy_text or None,
                hovertemplate="%{text}<extra></extra>",
            )
        )
    if sell_dates and sell_equities:
        fig.add_trace(
            go.Scatter(
                x=sell_dates,
                y=sell_equities,
                mode="markers",
                name="Sell",
                marker={"symbol": "triangle-down", "size": 10, "color": "red"},
                text=sell_text or None,
                hovertemplate="%{text}<extra></extra>",
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Equity",
        hovermode="x unified",
    )
    return fig


def _figure_from_result(result: SimResult) -> go.Figure:
    equity_by_date = {p.date: p.equity for p in result.equity_curve}
    buys = [f for f in result.fills if f.action == "buy"]
    sells = [f for f in result.fills if f.action == "sell"]
    return _build_figure(
        dates=[p.date.isoformat() for p in result.equity_curve],
        equities=[p.equity for p in result.equity_curve],
        buy_dates=[f.date.isoformat() for f in buys],
        buy_equities=[equity_by_date.get(f.date, result.final_equity) for f in buys],
        buy_text=[f"{f.symbol} {f.qty}@{f.price:.2f}" for f in buys],
        sell_dates=[f.date.isoformat() for f in sells],
        sell_equities=[equity_by_date.get(f.date, result.final_equity) for f in sells],
        sell_text=[f"{f.symbol} {f.qty}@{f.price:.2f}" for f in sells],
        buy_and_hold_equity=result.buy_and_hold_equity,
    )


def _should_redraw(event: ProgressEvent, day_index: int, total_days: int) -> bool:
    """Redraw often enough to feel live without Plotly thrash on every quiet day."""
    if event.fill is not None or event.decision is not None:
        return True
    if day_index == 1 or day_index >= total_days:
        return True
    return day_index % 5 == 0


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
    chart_box = st.empty()
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

        agent: HoldAgent | LlmTradingAgent
        if hold_only:
            agent = HoldAgent()
        else:
            agent = LlmTradingAgent(create_ollama_provider())

        live = _LiveChartState()
        total_days = len(sessions)

        def on_progress(event: ProgressEvent) -> None:
            live.observe(event)
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
                chart_box.plotly_chart(
                    _build_figure(
                        dates=live.dates,
                        equities=live.equities,
                        buy_dates=live.buy_dates,
                        buy_equities=live.buy_equities,
                        buy_text=live.buy_text,
                        sell_dates=live.sell_dates,
                        sell_equities=live.sell_equities,
                        sell_text=live.sell_text,
                        title=f"Equity (live) — {event.date}",
                    ),
                    width="stretch",
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

    chart_box.plotly_chart(_figure_from_result(result), width="stretch")
    caption_box.caption(
        f"Symbols: {', '.join(result.symbols)} | "
        f"{result.start} ~ {result.end} | "
        f"fills={len(result.fills)} decisions={len(result.decisions)}"
    )


if __name__ == "__main__":
    main()
