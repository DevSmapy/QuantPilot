#!/usr/bin/env python3
"""Streamlit UI for agent paper-trading equity and trade markers."""

from __future__ import annotations

from datetime import date, timedelta

import plotly.graph_objects as go
import streamlit as st

from quantpilot.agent.hold import HoldAgent
from quantpilot.agent.llm import LlmTradingAgent
from quantpilot.console import configure_stdio
from quantpilot.environment.costs import TradingCosts
from quantpilot.environment.market import HistoricalMarket, intersect_session_dates
from quantpilot.factory import create_datasource_manager, create_ollama_provider
from quantpilot.simulation.result import SimResult
from quantpilot.simulation.session import SimulationSession

DEFAULT_LOOKBACK = 60


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


def _build_figure(result: SimResult) -> go.Figure:
    fig = go.Figure()
    xs = [p.date.isoformat() for p in result.equity_curve]
    ys = [p.equity for p in result.equity_curve]
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name="Agent equity"))

    if result.buy_and_hold_equity is not None and xs:
        fig.add_hline(
            y=result.buy_and_hold_equity,
            line_dash="dash",
            annotation_text="Buy&Hold final",
        )

    buys = [f for f in result.fills if f.action == "buy"]
    sells = [f for f in result.fills if f.action == "sell"]
    if buys:
        fig.add_trace(
            go.Scatter(
                x=[f.date.isoformat() for f in buys],
                y=[_equity_on(result, f.date) for f in buys],
                mode="markers",
                name="Buy",
                marker={"symbol": "triangle-up", "size": 10, "color": "green"},
                text=[f"{f.symbol} {f.qty}@{f.price:.2f}" for f in buys],
                hovertemplate="%{text}<extra></extra>",
            )
        )
    if sells:
        fig.add_trace(
            go.Scatter(
                x=[f.date.isoformat() for f in sells],
                y=[_equity_on(result, f.date) for f in sells],
                mode="markers",
                name="Sell",
                marker={"symbol": "triangle-down", "size": 10, "color": "red"},
                text=[f"{f.symbol} {f.qty}@{f.price:.2f}" for f in sells],
                hovertemplate="%{text}<extra></extra>",
            )
        )
    fig.update_layout(
        title="Equity and trade markers",
        xaxis_title="Date",
        yaxis_title="Equity",
        hovermode="x unified",
    )
    return fig


def _equity_on(result: SimResult, on: date) -> float:
    for point in result.equity_curve:
        if point.date == on:
            return point.equity
    return result.final_equity


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
        ).run(start_d, end)
    except Exception as exc:
        st.exception(exc)
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Final equity", f"{result.final_equity:,.0f}")
    c2.metric("Return", f"{result.total_return:+.2%}")
    c3.metric("Total fees", f"{result.total_fees:,.0f}")
    c4.metric("Hit target", str(result.hit_target))
    bah = result.buy_and_hold_equity
    c5.metric("Buy&Hold", f"{bah:,.0f}" if bah is not None else "n/a")

    st.plotly_chart(_build_figure(result), use_container_width=True)
    st.caption(
        f"Symbols: {', '.join(result.symbols)} | "
        f"{result.start} ~ {result.end} | "
        f"fills={len(result.fills)} decisions={len(result.decisions)}"
    )


if __name__ == "__main__":
    main()
