#!/usr/bin/env python3
"""Streamlit UI for agent paper-trading equity and trade markers."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal, cast

import plotly.graph_objects as go
import streamlit as st

from quantpilot.agent.base import TradingAgent
from quantpilot.agent.decision import TradeDecision
from quantpilot.agent.hold import HoldAgent
from quantpilot.agent.llm import LlmTradingAgent
from quantpilot.console import configure_stdio
from quantpilot.environment.costs import TradingCosts
from quantpilot.environment.market import HistoricalMarket, intersect_session_dates
from quantpilot.environment.observation import AgentObservation
from quantpilot.environment.types import Fill
from quantpilot.factory import create_datasource_manager, create_ollama_provider
from quantpilot.simulation.result import SimResult
from quantpilot.simulation.session import ProgressEvent, SimulationSession

DEFAULT_LOOKBACK = 60
PriceChartType = Literal["Close line", "Candlestick"]


@dataclass
class _TradeMarker:
    day: str
    equity: float
    exec_price: float
    close_price: float
    text: str
    symbol: str


@dataclass
class _OhlcBar:
    day: str
    open: float
    high: float
    low: float
    close: float


@dataclass
class _TradeLogRow:
    """One executed fill for the Streamlit trade log."""

    date: str
    action: str
    symbol: str
    qty: int
    price: float
    fee: float
    reason: str


@dataclass
class _LiveChartState:
    """Growing equity / price / trade series while a session runs."""

    dates: list[str] = field(default_factory=list)
    equities: list[float] = field(default_factory=list)
    closes: list[float] = field(default_factory=list)
    avg_costs: list[float | None] = field(default_factory=list)
    ohlc: list[_OhlcBar] = field(default_factory=list)
    buys: list[_TradeMarker] = field(default_factory=list)
    sells: list[_TradeMarker] = field(default_factory=list)
    trade_rows: list[_TradeLogRow] = field(default_factory=list)
    day_index: int = 0

    def observe(
        self,
        event: ProgressEvent,
        *,
        price_symbol: str,
        ohlc: _OhlcBar,
    ) -> None:
        if event.discarded_pending:
            return
        self.day_index += 1
        day = event.date.isoformat()
        self.dates.append(day)
        self.equities.append(event.equity)
        self.closes.append(ohlc.close)
        self.ohlc.append(ohlc)
        qty = event.holdings.get(price_symbol, 0)
        avg = event.avg_costs.get(price_symbol)
        self.avg_costs.append(avg if qty > 0 and avg is not None else None)
        if event.fill is not None:
            self._record_fill(event.fill, event.equity, ohlc.close)

    def _record_fill(self, fill: Fill, equity: float, close_price: float) -> None:
        marker = _TradeMarker(
            day=fill.date.isoformat(),
            equity=equity,
            exec_price=fill.price,
            close_price=close_price,
            text=f"{fill.symbol} {fill.qty}@{fill.price:.2f}",
            symbol=fill.symbol,
        )
        if fill.action == "buy":
            self.buys.append(marker)
        elif fill.action == "sell":
            self.sells.append(marker)
        # Sell requires a reason by rule; buy reason is optional and omitted in the log.
        reason = fill.reason.strip() if fill.action == "sell" else ""
        self.trade_rows.append(
            _TradeLogRow(
                date=fill.date.isoformat(),
                action=fill.action,
                symbol=fill.symbol,
                qty=fill.qty,
                price=fill.price,
                fee=fill.fee,
                reason=reason,
            )
        )


class _StatusLlmAgent(TradingAgent):
    """Show a waiting banner before each LLM decide() call."""

    def __init__(self, inner: TradingAgent, status_box: object) -> None:
        self._inner = inner
        self._status_box = status_box

    def decide(self, observation: AgentObservation) -> TradeDecision:
        self._status_box.info("Waiting for Ollama…")
        return self._inner.decide(observation)


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


def _bar_ohlc(market: HistoricalMarket, on: date) -> _OhlcBar:
    bar = market.bar(on)
    return _OhlcBar(
        day=on.isoformat(),
        open=float(cast(float, bar["open"])),
        high=float(cast(float, bar["high"])),
        low=float(cast(float, bar["low"])),
        close=float(cast(float, bar["close"])),
    )


def _markers_for_price(
    markers: list[_TradeMarker],
    *,
    price_symbol: str,
    mode: PriceChartType,
) -> tuple[list[_TradeMarker], list[float], list[str]]:
    filtered = [m for m in markers if m.symbol == price_symbol]
    if mode == "Close line":
        ys = [m.close_price for m in filtered]
    else:
        ys = [m.exec_price for m in filtered]
    texts = [m.text for m in filtered]
    return filtered, ys, texts


def _avg_cost_trace(dates: list[str], avg_costs: list[float | None]) -> go.Scatter:
    return go.Scatter(
        x=dates,
        y=avg_costs,
        mode="lines",
        name="Avg cost",
        line={"dash": "dot", "width": 2, "color": "#888"},
        connectgaps=False,
    )


def _build_equity_figure(
    *,
    dates: list[str],
    equities: list[float],
    buys: list[_TradeMarker],
    sells: list[_TradeMarker],
    target: float | None = None,
    buy_and_hold_equity: float | None = None,
    title: str = "Portfolio equity",
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=equities, mode="lines", name="Agent equity"))
    if target is not None and dates:
        fig.add_hline(y=target, line_dash="dash", annotation_text="Target")
    if buy_and_hold_equity is not None and dates:
        fig.add_hline(
            y=buy_and_hold_equity,
            line_dash="dash",
            annotation_text="Buy&Hold final",
        )
    if buys:
        fig.add_trace(
            go.Scatter(
                x=[m.day for m in buys],
                y=[m.equity for m in buys],
                mode="markers",
                name="Buy",
                marker={"symbol": "triangle-up", "size": 11, "color": "green"},
                text=[m.text for m in buys],
                hovertemplate="%{text}<extra></extra>",
            )
        )
    if sells:
        fig.add_trace(
            go.Scatter(
                x=[m.day for m in sells],
                y=[m.equity for m in sells],
                mode="markers",
                name="Sell",
                marker={"symbol": "triangle-down", "size": 11, "color": "red"},
                text=[m.text for m in sells],
                hovertemplate="%{text}<extra></extra>",
            )
        )
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
    ohlc: list[_OhlcBar],
    avg_costs: list[float | None],
    buys: list[_TradeMarker],
    sells: list[_TradeMarker],
    price_symbol: str,
    chart_type: PriceChartType,
    title: str | None = None,
) -> go.Figure:
    fig = go.Figure()
    if chart_type == "Candlestick":
        fig.add_trace(
            go.Candlestick(
                x=[b.day for b in ohlc],
                open=[b.open for b in ohlc],
                high=[b.high for b in ohlc],
                low=[b.low for b in ohlc],
                close=[b.close for b in ohlc],
                name=f"{price_symbol} OHLC",
            )
        )
    else:
        fig.add_trace(
            go.Scatter(x=dates, y=closes, mode="lines", name=f"{price_symbol} close")
        )

    fig.add_trace(_avg_cost_trace(dates, avg_costs))

    buy_f, buy_ys, buy_text = _markers_for_price(
        buys, price_symbol=price_symbol, mode=chart_type
    )
    sell_f, sell_ys, sell_text = _markers_for_price(
        sells, price_symbol=price_symbol, mode=chart_type
    )
    if buy_f:
        fig.add_trace(
            go.Scatter(
                x=[m.day for m in buy_f],
                y=buy_ys,
                mode="markers",
                name="Buy",
                marker={"symbol": "triangle-up", "size": 11, "color": "green"},
                text=buy_text,
                hovertemplate="%{text}<extra></extra>",
            )
        )
    if sell_f:
        fig.add_trace(
            go.Scatter(
                x=[m.day for m in sell_f],
                y=sell_ys,
                mode="markers",
                name="Sell",
                marker={"symbol": "triangle-down", "size": 11, "color": "red"},
                text=sell_text,
                hovertemplate="%{text}<extra></extra>",
            )
        )

    fig.update_layout(
        title=title or f"Price — {price_symbol}",
        xaxis_title="Date",
        yaxis_title="Price",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
        xaxis_rangeslider_visible=False,
    )
    return fig


def _markers_from_result(
    result: SimResult,
    *,
    closes_by_date: dict[date, float],
) -> tuple[list[_TradeMarker], list[_TradeMarker]]:
    equity_by_date = {p.date: p.equity for p in result.equity_curve}
    buys: list[_TradeMarker] = []
    sells: list[_TradeMarker] = []
    for fill in result.fills:
        marker = _TradeMarker(
            day=fill.date.isoformat(),
            equity=equity_by_date.get(fill.date, result.final_equity),
            exec_price=fill.price,
            close_price=closes_by_date.get(fill.date, fill.price),
            text=f"{fill.symbol} {fill.qty}@{fill.price:.2f}",
            symbol=fill.symbol,
        )
        if fill.action == "buy":
            buys.append(marker)
        elif fill.action == "sell":
            sells.append(marker)
    return buys, sells


def _avg_costs_from_result(
    result: SimResult,
    price_symbol: str,
) -> list[float | None]:
    """Rebuild avg-cost series by replaying fills for the price symbol."""
    qty = 0
    avg = 0.0
    by_date: dict[date, float | None] = {}
    fills = sorted(
        (f for f in result.fills if f.symbol == price_symbol),
        key=lambda f: f.date,
    )
    fill_i = 0
    for point in result.equity_curve:
        while fill_i < len(fills) and fills[fill_i].date == point.date:
            f = fills[fill_i]
            if f.action == "buy":
                new_qty = qty + f.qty
                avg = ((qty * avg) + f.qty * f.price) / new_qty if new_qty else 0.0
                qty = new_qty
            else:
                qty = max(0, qty - f.qty)
                if qty == 0:
                    avg = 0.0
            fill_i += 1
        by_date[point.date] = avg if qty > 0 else None
    return [by_date.get(p.date) for p in result.equity_curve]


def _ohlc_for_dates(market: HistoricalMarket, dates: list[date]) -> list[_OhlcBar]:
    return [_bar_ohlc(market, on) for on in dates]


def _should_redraw(event: ProgressEvent, day_index: int, total_days: int) -> bool:
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
    ohlc: list[_OhlcBar],
    avg_costs: list[float | None],
    buys: list[_TradeMarker],
    sells: list[_TradeMarker],
    price_symbol: str,
    chart_type: PriceChartType,
    target: float | None = None,
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
                target=target,
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
                ohlc=ohlc,
                avg_costs=avg_costs,
                buys=buys,
                sells=sells,
                price_symbol=price_symbol,
                chart_type=chart_type,
                title=price_title,
            ),
            width="stretch",
        )


def _trade_log_dataframe(rows: list[_TradeLogRow]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for r in rows:
        notional = r.qty * r.price
        reason = r.reason if r.action == "sell" else (r.reason or "—")
        out.append(
            {
                "date": r.date,
                "action": r.action,
                "symbol": r.symbol,
                "qty": r.qty,
                "price": round(r.price, 2),
                "notional": round(notional, 2),
                "fee": round(r.fee, 2),
                "reason": reason,
            }
        )
    return out


def _trade_rows_from_fills(fills: list[Fill]) -> list[_TradeLogRow]:
    rows: list[_TradeLogRow] = []
    for fill in fills:
        reason = fill.reason.strip() if fill.action == "sell" else ""
        rows.append(
            _TradeLogRow(
                date=fill.date.isoformat(),
                action=fill.action,
                symbol=fill.symbol,
                qty=fill.qty,
                price=fill.price,
                fee=fill.fee,
                reason=reason,
            )
        )
    return rows


def _equity_csv(result: SimResult) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "equity", "cash", "qty"])
    for p in result.equity_curve:
        writer.writerow([p.date.isoformat(), p.equity, p.cash, p.qty])
    return buf.getvalue()


def _fills_csv(result: SimResult) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "symbol", "action", "qty", "price", "fee", "reason"])
    for f in result.fills:
        writer.writerow(
            [
                f.date.isoformat(),
                f.symbol,
                f.action,
                f.qty,
                f.price,
                f.fee,
                f.reason,
            ]
        )
    return buf.getvalue()


def main() -> None:
    configure_stdio()
    st.set_page_config(page_title="QuantPilot Agent Sim", layout="wide")
    st.title("QuantPilot Agent Simulation")

    with st.sidebar:
        symbols_raw = st.text_input("Symbols (comma-separated)", "005930.KS")
        try:
            parsed_symbols = _parse_symbols(symbols_raw)
        except ValueError:
            parsed_symbols = ["005930.KS"]
        price_symbol = st.selectbox("Price chart symbol", parsed_symbols, index=0)
        chart_type = st.selectbox(
            "Price chart type",
            ["Close line", "Candlestick"],
            index=0,
        )
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
    log_box = st.empty()
    download_box = st.empty()
    caption_box = st.empty()

    try:
        symbols = _parse_symbols(symbols_raw)
        if price_symbol not in symbols:
            price_symbol = symbols[0]
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

        price_market = markets[price_symbol]
        chart_mode: PriceChartType = (
            "Candlestick" if chart_type == "Candlestick" else "Close line"
        )

        if hold_only:
            agent: TradingAgent = HoldAgent()
        else:
            agent = _StatusLlmAgent(
                LlmTradingAgent(create_ollama_provider()),
                status_box,
            )

        live = _LiveChartState()
        total_days = len(sessions)
        target_f = float(target)

        def on_progress(event: ProgressEvent) -> None:
            ohlc = _bar_ohlc(price_market, event.date)
            live.observe(event, price_symbol=price_symbol, ohlc=ohlc)
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

            with log_box.container():
                st.subheader("Trade log")
                if live.trade_rows:
                    st.dataframe(
                        _trade_log_dataframe(live.trade_rows),
                        width="stretch",
                    )
                else:
                    st.caption("No fills yet — trades appear here after next-open execution.")

            if _should_redraw(event, live.day_index, total_days):
                _render_charts(
                    equity_box=equity_box,
                    price_box=price_box,
                    dates=live.dates,
                    equities=live.equities,
                    closes=live.closes,
                    ohlc=live.ohlc,
                    avg_costs=live.avg_costs,
                    buys=live.buys,
                    sells=live.sells,
                    price_symbol=price_symbol,
                    chart_type=chart_mode,
                    target=target_f,
                    live=True,
                    as_of=event.date,
                )

        result = SimulationSession(
            markets=markets,
            agent=agent,
            symbols=symbols,
            capital=float(capital),
            target=target_f,
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

    curve_dates = [p.date for p in result.equity_curve]
    ohlc = _ohlc_for_dates(price_market, curve_dates)
    closes_map = {d: _bar_ohlc(price_market, d).close for d in curve_dates}
    buys, sells = _markers_from_result(result, closes_by_date=closes_map)
    avg_costs = live.avg_costs if live.avg_costs else _avg_costs_from_result(
        result, price_symbol
    )
    # Prefer live OHLC/closes when lengths match
    if len(live.dates) == len(result.equity_curve):
        dates_s = live.dates
        closes = live.closes
        ohlc_final = live.ohlc
        avg_final = live.avg_costs
        buys_final, sells_final = live.buys, live.sells
        trade_rows = live.trade_rows
    else:
        dates_s = [d.isoformat() for d in curve_dates]
        closes = [closes_map[d] for d in curve_dates]
        ohlc_final = ohlc
        avg_final = avg_costs
        buys_final, sells_final = buys, sells
        trade_rows = _trade_rows_from_fills(result.fills)

    _render_charts(
        equity_box=equity_box,
        price_box=price_box,
        dates=dates_s,
        equities=[p.equity for p in result.equity_curve],
        closes=closes,
        ohlc=ohlc_final,
        avg_costs=avg_final,
        buys=buys_final,
        sells=sells_final,
        price_symbol=price_symbol,
        chart_type=chart_mode,
        target=float(target),
        buy_and_hold_equity=result.buy_and_hold_equity,
    )

    with log_box.container():
        st.subheader("Trade log")
        if trade_rows:
            st.dataframe(_trade_log_dataframe(trade_rows), width="stretch")
        else:
            st.caption("No fills in this run.")

    with download_box.container():
        d1, d2 = st.columns(2)
        d1.download_button(
            "Download equity CSV",
            data=_equity_csv(result),
            file_name="agent_equity.csv",
            mime="text/csv",
        )
        d2.download_button(
            "Download fills CSV",
            data=_fills_csv(result),
            file_name="agent_fills.csv",
            mime="text/csv",
        )

    note = ""
    if chart_mode == "Close line":
        note = " Close-line markers sit on close; hover shows fill price."
    else:
        note = " Candlestick markers use execution (fill) price."
    caption_box.caption(
        f"Symbols: {', '.join(result.symbols)} | price={price_symbol} | "
        f"{result.start} ~ {result.end} | "
        f"fills={len(result.fills)} decisions={len(result.decisions)}."
        f"{note}"
    )


if __name__ == "__main__":
    main()
