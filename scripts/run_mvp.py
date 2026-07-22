#!/usr/bin/env python3
"""Run the QuantPilot MVP vertical slice demo."""

from __future__ import annotations

import argparse
from datetime import date

from quantpilot.backtest.engine import BacktestEngine
from quantpilot.factory import create_datasource_manager, create_ollama_provider
from quantpilot.strategy.sma_cross import SMACrossStrategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QuantPilot MVP demo")
    parser.add_argument("--symbol", default="005930.KS", help="Ticker symbol")
    parser.add_argument("--start", default="2023-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default="2025-12-31", help="End date YYYY-MM-DD")
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Skip Ollama strategy review",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    print(f"QuantPilot MVP — {args.symbol} ({start} ~ {end})")
    print("=" * 60)

    manager = create_datasource_manager()
    prices = manager.get_price(args.symbol, start, end)
    print(f"Loaded {prices.height} rows from Q-SEED")

    strategy = SMACrossStrategy(fast_window=20, slow_window=60)
    signals = strategy.run(prices)
    buy_signals = signals.filter(signals["signal"] == 1).height
    sell_signals = signals.filter(signals["signal"] == -1).height
    print(f"Signals: buy={buy_signals}, sell={sell_signals}")

    engine = BacktestEngine()
    result = engine.run(prices, signals)

    print("\nBacktest Results")
    print("-" * 60)
    print(f"Total Return : {result.total_return:+.2%}")
    print(f"CAGR         : {result.cagr:+.2%}")
    print(f"MDD          : {result.mdd:+.2%}")
    print(f"Sharpe       : {result.sharpe:.2f}")
    print(f"Trades       : {result.trades_count}")
    print(f"Period       : {result.start_date} ~ {result.end_date}")

    if args.skip_ai:
        print("\nAI review skipped (--skip-ai)")
        return

    print("\nAI Strategy Review")
    print("-" * 60)
    llm = create_ollama_provider()
    review = llm.review_strategy(
        strategy_name="SMA Cross (20/60)",
        metrics={
            "total_return": f"{result.total_return:.2%}",
            "cagr": f"{result.cagr:.2%}",
            "mdd": f"{result.mdd:.2%}",
            "sharpe": f"{result.sharpe:.2f}",
            "trades": result.trades_count,
        },
        summary=f"Long-only SMA crossover backtest on {args.symbol}.",
    )
    print(review)


if __name__ == "__main__":
    main()
