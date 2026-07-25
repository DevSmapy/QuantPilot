#!/usr/bin/env python3
"""Run the QuantPilot MVP vertical slice demo."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any

from quantpilot.analysis.build_brief import build_analysis_brief
from quantpilot.backtest.engine import BacktestEngine
from quantpilot.console import configure_stdio
from quantpilot.environment.costs import TradingCosts
from quantpilot.factory import create_datasource_manager, create_ollama_provider
from quantpilot.strategy.base import Strategy
from quantpilot.strategy.rsi_reversion import RSIReversionStrategy
from quantpilot.strategy.sma_cross import SMACrossStrategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QuantPilot MVP demo")
    parser.add_argument("--symbol", default="005930.KS", help="Ticker symbol")
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=date.fromisoformat("2023-01-01"),
        help="Start date YYYY-MM-DD",
    )
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=date.fromisoformat("2025-12-31"),
        help="End date YYYY-MM-DD",
    )
    parser.add_argument(
        "--strategy",
        choices=("sma_cross", "rsi_reversion"),
        default="sma_cross",
        help="Strategy to run",
    )
    parser.add_argument(
        "--commission-rate",
        type=float,
        default=0.0,
        help="Commission as a fraction of notional (equity haircut)",
    )
    parser.add_argument(
        "--slippage-bps",
        type=float,
        default=0.0,
        help="Slippage in basis points (equity haircut)",
    )
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Skip Ollama strategy review",
    )
    parser.add_argument(
        "--emit-brief",
        nargs="?",
        const="-",
        default=None,
        metavar="PATH",
        help="Write AnalysisBrief JSON to PATH (or stdout if '-' / flag only)",
    )
    return parser.parse_args()


def build_strategy(name: str) -> tuple[Strategy, str, dict[str, Any]]:
    if name == "sma_cross":
        strategy = SMACrossStrategy(fast_window=20, slow_window=60)
        return (
            strategy,
            "SMA Cross (20/60)",
            {"fast": strategy.fast_window, "slow": strategy.slow_window},
        )
    strategy = RSIReversionStrategy()
    return (
        strategy,
        "RSI Reversion (14, 30/70)",
        {
            "window": strategy.window,
            "oversold": strategy.oversold,
            "overbought": strategy.overbought,
        },
    )


def main() -> None:
    configure_stdio()
    args = parse_args()
    strategy, strategy_label, strategy_params = build_strategy(args.strategy)
    costs = TradingCosts(
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
    )

    print(f"QuantPilot MVP — {args.symbol} ({args.start} ~ {args.end})")
    print(f"Strategy: {strategy_label}")
    print("=" * 60)

    manager = create_datasource_manager()
    prices = manager.get_price(args.symbol, args.start, args.end)
    print(f"Loaded {prices.height} rows from Q-SEED")

    signals = strategy.run(prices)
    buy_signals = signals.filter(signals["signal"] == 1).height
    sell_signals = signals.filter(signals["signal"] == -1).height
    print(f"Signals: buy={buy_signals}, sell={sell_signals}")

    result = BacktestEngine().run(prices, signals, costs=costs)

    print("\nBacktest Results")
    print("-" * 60)
    print(f"Total Return : {result.total_return:+.2%}")
    print(f"CAGR         : {result.cagr:+.2%}")
    print(f"MDD          : {result.mdd:+.2%}")
    print(f"Sharpe       : {result.sharpe:.2f}")
    print(f"Sortino      : {result.sortino:.2f}")
    print(f"Profit Factor: {result.profit_factor:.2f}")
    print(f"Win Rate     : {result.win_rate:.2%}")
    print(f"Trades       : {result.trades_count}")
    print(f"Period       : {result.start_date} ~ {result.end_date}")

    if args.emit_brief is not None:
        brief = build_analysis_brief(
            prices=prices,
            signals=signals,
            result=result,
            strategy_name=args.strategy,
            strategy_params=strategy_params,
            symbol=args.symbol,
        )
        payload = brief.to_json()
        if args.emit_brief in ("-", ""):
            print("\nAnalysisBrief JSON")
            print("-" * 60)
            print(payload)
        else:
            path = Path(args.emit_brief)
            path.write_text(payload + "\n", encoding="utf-8")
            print(f"\nWrote AnalysisBrief to {path}")

    if args.skip_ai:
        print("\nAI review skipped (--skip-ai)")
        return

    print("\nAI Strategy Review")
    print("-" * 60)
    llm = create_ollama_provider()
    review = llm.review_strategy(
        strategy_name=strategy_label,
        metrics={
            "total_return": f"{result.total_return:.2%}",
            "cagr": f"{result.cagr:.2%}",
            "mdd": f"{result.mdd:.2%}",
            "sharpe": f"{result.sharpe:.2f}",
            "sortino": f"{result.sortino:.2f}",
<<<<<<< HEAD
<<<<<<< HEAD
            "profit_factor": f"{result.profit_factor:.2f}",
            "win_rate": f"{result.win_rate:.2%}",
=======
>>>>>>> 74fa7f9 (docs(analysis-quant): CLI flags and local Q-SEED checklist)
=======
            "profit_factor": f"{result.profit_factor:.2f}",
            "win_rate": f"{result.win_rate:.2%}",
>>>>>>> 3e97d89 (fix(analysis-quant): address PR review findings)
            "trades": result.trades_count,
        },
        summary=f"Long-only {strategy_label} backtest on {args.symbol}.",
    )
    print(review)


if __name__ == "__main__":
    main()
