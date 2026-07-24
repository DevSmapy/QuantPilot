# feat/analysis-quant — single-asset analysis MVP+

> Extend the Q-SEED → strategy → backtest slice so strategies are swappable and
> metrics/costs are usable for local research. Not a full Phase 2 completion.

See also: [`README.md`](README.md) (usage + local Q-SEED checklist).

---

## Goal

`DataSourceManager` → `Strategy` → `BacktestEngine` (+ `TradingCosts`) → richer
`BacktestResult`, with CLI flags and synthetic unit tests in cloud; real Q-SEED
smoke on the user's machine.

---

## In scope (this branch)

- `Strategy` protocol + `SMACrossStrategy` + `RSIReversionStrategy`
- Metrics: Sortino, Profit Factor, Win Rate, equity_curve, trade_pnls
- Proportional cost haircut via existing `TradingCosts`
- Rolling OOS helper (`run_walk_forward`, train metadata only)
- `scripts/run_mvp.py` strategy/cost flags
- Docs + local Q-SEED checklist

## Out of scope (follow-up)

- New indicator files (EMA/MACD/BB/ATR)
- `feature_engineering/`
- `monthly_returns`
- Parameter optimization / grids
- Portfolio / live trading / Streamlit analytics dashboard
- vectorbt / Backtrader

---

## Contracts

**Signals:** event `{-1,0,1}` — enter / exit / hold (not a position series).

**Look-ahead:** signal on bar `t` applies to bar `t+1` close-to-close return.

**Costs:** `commission_rate + slippage_bps/1e4` equity haircut on entry and exit.

**Metrics:** MDD `<= 0`; Sharpe/Sortino annualized with `√252`; PF from
completed round-trip `trade_pnls`.

---

## Acceptance

**Cloud (agent):** unit tests + ruff + black + mypy green on synthetic data.

**Local (user):** Q-SEED smoke via README checklist after pulling this branch.
