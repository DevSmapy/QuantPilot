#!/usr/bin/env python3
"""Run the AI agent paper-trading simulation MVP."""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from quantpilot.agent.hold import HoldAgent
from quantpilot.agent.llm import LlmTradingAgent
from quantpilot.console import configure_stdio
from quantpilot.environment.costs import TradingCosts
from quantpilot.environment.market import HistoricalMarket, intersect_session_dates
from quantpilot.factory import create_datasource_manager, create_ollama_provider
from quantpilot.simulation.result import SimResult
from quantpilot.simulation.session import ProgressEvent, SimulationSession

DEFAULT_LOOKBACK_SESSIONS = 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="QuantPilot agent paper-trading simulation",
    )
    parser.add_argument("--symbol", default="005930.KS", help="Ticker symbol")
    parser.add_argument(
        "--symbols",
        default=None,
        help="Comma-separated tickers (overrides --symbol)",
    )
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        required=True,
        help="Simulation start date YYYY-MM-DD",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=10_000_000.0,
        help="Starting cash",
    )
    parser.add_argument(
        "--target",
        type=float,
        required=True,
        help="Target equity",
    )
    parser.add_argument(
        "--period-days",
        type=int,
        default=90,
        help="Calendar days for the simulation window",
    )
    parser.add_argument(
        "--decision-every",
        type=int,
        default=5,
        help="Decide every N trading sessions (1 = daily)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of sequential runs (default 1)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Ollama model name (defaults to settings)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Ollama sampling temperature (multi-run variance)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Base Ollama seed; run i uses seed+i-1 when set",
    )
    parser.add_argument(
        "--hold-only",
        action="store_true",
        help="Use HoldAgent instead of LLM (no Ollama calls)",
    )
    parser.add_argument(
        "--lookback-sessions",
        type=int,
        default=DEFAULT_LOOKBACK_SESSIONS,
        help="Required trading days of history before start for indicators",
    )
    parser.add_argument(
        "--commission-rate",
        type=float,
        default=0.0,
        help="Commission as a fraction of notional (e.g. 0.00015)",
    )
    parser.add_argument(
        "--slippage-bps",
        type=float,
        default=0.0,
        help="Slippage in basis points applied to the open",
    )
    return parser.parse_args()


def _parse_symbols(args: argparse.Namespace) -> list[str]:
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
        if not symbols:
            raise SystemExit("--symbols must list at least one ticker")
        return symbols
    return [args.symbol]


def _progress(event: ProgressEvent) -> None:
    holdings = (
        ",".join(f"{s}:{q}" for s, q in sorted(event.holdings.items())) or "(none)"
    )
    parts = [
        f"[{event.date}] cash={event.cash:,.0f} equity={event.equity:,.0f} "
        f"total_shares={event.qty} holdings={holdings}"
    ]
    if event.equity_after_fill is not None:
        parts.append(f"equity_after_fill={event.equity_after_fill:,.0f}")
    if event.fill is not None:
        parts.append(
            f"fill={event.fill.symbol}:{event.fill.action}:"
            f"{event.fill.qty}@{event.fill.price:.2f}"
        )
    if event.fill_rejected:
        parts.append(f"fill_rejected={event.fill_rejected}")
    if event.decision is not None:
        sym = event.decision.symbol or ""
        parts.append(
            f"action={event.decision.action} symbol={sym} "
            f"size={event.decision.size:.2f} reason={event.decision.reason!r}"
        )
    if event.discarded_pending:
        parts.append("discarded_pending=True")
    if event.fill is not None or event.decision is not None or event.discarded_pending:
        print(" ".join(parts))


def _load_markets(
    symbols: list[str],
    start: date,
    end: date,
    lookback_sessions: int,
) -> dict[str, HistoricalMarket]:
    load_start = start - timedelta(days=max(lookback_sessions * 3, 90))
    manager = create_datasource_manager()
    markets: dict[str, HistoricalMarket] = {}
    for symbol in symbols:
        prices = manager.get_price(symbol, load_start, end)
        markets[symbol] = HistoricalMarket(prices)
    return markets


def _make_agent(
    args: argparse.Namespace,
    *,
    run_idx: int,
) -> HoldAgent | LlmTradingAgent:
    if args.hold_only:
        return HoldAgent()
    llm = create_ollama_provider()
    if args.model:
        llm.model = args.model
    options: dict[str, float | int] = {"temperature": args.temperature}
    if args.seed is not None:
        options["seed"] = args.seed + run_idx - 1
    return LlmTradingAgent(llm, options=options)


def _print_result(result: SimResult, run_idx: int, runs: int) -> None:
    prefix = f"Run {run_idx}/{runs}" if runs > 1 else "Result"
    print("\n" + prefix)
    print("-" * 60)
    print(f"Symbols      : {', '.join(result.symbols)}")
    print(f"Period       : {result.start} ~ {result.end}")
    print(f"Final equity : {result.final_equity:,.0f}")
    print(f"Target       : {result.target:,.0f} (hit={result.hit_target})")
    print(f"Total return : {result.total_return:+.2%}")
    print(f"Total fees   : {result.total_fees:,.0f}")
    if result.buy_and_hold_equity is not None:
        bah_ret = (result.buy_and_hold_equity / result.capital) - 1.0
        print(
            f"Buy&Hold     : {result.buy_and_hold_equity:,.0f} ({bah_ret:+.2%}) "
            f"[same costs as agent]"
        )
    print(f"Decisions    : {len(result.decisions)}")
    print(f"Fills        : {len(result.fills)}")
    if result.fill_rejects:
        print(f"Fill rejects : {len(result.fill_rejects)}")
    if result.discarded_pending is not None:
        print(
            f"Discarded    : {result.discarded_pending.action} "
            f"symbol={result.discarded_pending.symbol} "
            f"size={result.discarded_pending.size}"
        )


def main() -> None:
    configure_stdio()
    args = parse_args()
    if args.period_days < 1:
        raise SystemExit("--period-days must be >= 1")
    if args.decision_every < 1:
        raise SystemExit("--decision-every must be >= 1")
    if args.runs < 1:
        raise SystemExit("--runs must be >= 1")
    if args.lookback_sessions < 1:
        raise SystemExit("--lookback-sessions must be >= 1")
    if args.commission_rate < 0:
        raise SystemExit("--commission-rate must be >= 0")
    if args.commission_rate >= 1.0:
        raise SystemExit("--commission-rate must be < 1")
    if args.slippage_bps < 0:
        raise SystemExit("--slippage-bps must be >= 0")

    symbols = _parse_symbols(args)
    end = args.start + timedelta(days=args.period_days)
    label = ",".join(symbols)
    print(
        f"QuantPilot Agent Sim — {label} "
        f"({args.start} ~ {end}, calendar {args.period_days}d)"
    )
    print("=" * 60)

    markets = _load_markets(symbols, args.start, end, args.lookback_sessions)
    for symbol, market in markets.items():
        prior = market.prior_session_count(args.start)
        if prior < args.lookback_sessions:
            raise SystemExit(
                f"Need at least {args.lookback_sessions} trading days before "
                f"{args.start} for {symbol}, found {prior}."
            )

    sessions = intersect_session_dates(markets, args.start, end)
    priors = min(m.prior_session_count(args.start) for m in markets.values())
    print(f"Trading sessions in window: {len(sessions)}")
    print(f"Lookback sessions before start: {priors}")
    if not sessions:
        raise SystemExit("No trading sessions in the requested window")

    costs = TradingCosts(
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
    )
    results: list[SimResult] = []
    for run_idx in range(1, args.runs + 1):
        if args.runs > 1:
            print(f"\n=== Run {run_idx}/{args.runs} ===")
        agent = _make_agent(args, run_idx=run_idx)
        session = SimulationSession(
            markets=markets,
            agent=agent,
            symbols=symbols,
            capital=args.capital,
            target=args.target,
            decision_every=args.decision_every,
            costs=costs,
            on_progress=_progress,
        )
        result = session.run(args.start, end)
        results.append(result)
        _print_result(result, run_idx, args.runs)

    if args.runs > 1:
        finals = [r.final_equity for r in results]
        hits = sum(1 for r in results if r.hit_target)
        print("\nMulti-run summary")
        print("-" * 60)
        print(f"Finals : {[round(x, 2) for x in finals]}")
        print(f"Mean   : {sum(finals) / len(finals):,.0f}")
        print(f"Hits   : {hits}/{len(results)}")


if __name__ == "__main__":
    main()
