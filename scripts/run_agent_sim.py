#!/usr/bin/env python3
"""Run the AI agent paper-trading simulation MVP."""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from quantpilot.agent.hold import HoldAgent
from quantpilot.agent.llm import LlmTradingAgent
from quantpilot.console import configure_stdio
from quantpilot.environment.market import HistoricalMarket
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
    return parser.parse_args()


def _progress(event: ProgressEvent) -> None:
    parts = [f"[{event.date}] cash={event.cash:,.0f} equity={event.equity:,.0f} qty={event.qty}"]
    if event.fill is not None:
        parts.append(
            f"fill={event.fill.action}:{event.fill.qty}@{event.fill.price:.2f}"
        )
    if event.fill_rejected:
        parts.append(f"fill_rejected={event.fill_rejected}")
    if event.decision is not None:
        parts.append(
            f"action={event.decision.action} size={event.decision.size:.2f} "
            f"reason={event.decision.reason!r}"
        )
    if event.discarded_pending:
        parts.append("discarded_pending=True")
    if event.fill is not None or event.decision is not None or event.discarded_pending:
        print(" ".join(parts))


def _load_market(
    symbol: str,
    start: date,
    end: date,
    lookback_sessions: int,
) -> HistoricalMarket:
    # Calendar buffer so we have enough trading days before start.
    load_start = start - timedelta(days=max(lookback_sessions * 3, 90))
    manager = create_datasource_manager()
    prices = manager.get_price(symbol, load_start, end)
    return HistoricalMarket(prices)


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
    print(f"Period       : {result.start} ~ {result.end}")
    print(f"Final equity : {result.final_equity:,.0f}")
    print(f"Target       : {result.target:,.0f} (hit={result.hit_target})")
    print(f"Total return : {result.total_return:+.2%}")
    if result.buy_and_hold_equity is not None:
        bah_ret = (result.buy_and_hold_equity / result.capital) - 1.0
        print(
            f"Buy&Hold     : {result.buy_and_hold_equity:,.0f} ({bah_ret:+.2%})"
        )
    print(f"Decisions    : {len(result.decisions)}")
    print(f"Fills        : {len(result.fills)}")
    if result.fill_rejects:
        print(f"Fill rejects : {len(result.fill_rejects)}")
    if result.discarded_pending is not None:
        print(
            f"Discarded    : {result.discarded_pending.action} "
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

    end = args.start + timedelta(days=args.period_days)
    print(
        f"QuantPilot Agent Sim — {args.symbol} "
        f"({args.start} ~ {end}, calendar {args.period_days}d)"
    )
    print("=" * 60)

    market = _load_market(
        args.symbol, args.start, end, args.lookback_sessions
    )
    prior = market.prior_session_count(args.start)
    if prior < args.lookback_sessions:
        raise SystemExit(
            f"Need at least {args.lookback_sessions} trading days before "
            f"{args.start}, found {prior}. Choose a later --start or "
            f"lower --lookback-sessions."
        )

    sessions = market.session_dates(args.start, end)
    print(f"Trading sessions in window: {len(sessions)}")
    print(f"Lookback sessions before start: {prior}")
    if not sessions:
        raise SystemExit("No trading sessions in the requested window")

    results: list[SimResult] = []
    for run_idx in range(1, args.runs + 1):
        if args.runs > 1:
            print(f"\n=== Run {run_idx}/{args.runs} ===")
        agent = _make_agent(args, run_idx=run_idx)
        session = SimulationSession(
            market=market,
            agent=agent,
            symbol=args.symbol,
            capital=args.capital,
            target=args.target,
            decision_every=args.decision_every,
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
