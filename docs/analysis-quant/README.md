# Analysis Quant (single-asset MVP+)

`feat/analysis-quant` extends the QuantPilot vertical slice into a **swappable
strategy → backtest → metrics** pipeline for one symbol at a time.

## Pipeline

```
DataSourceManager.get_price
        ↓
Strategy.run  →  signal ∈ {-1, 0, 1}
        ↓
BacktestEngine.run(+ TradingCosts)
        ↓
BacktestResult (return / CAGR / MDD / Sharpe / Sortino / PF / win rate /
                equity_curve / trade_pnls)
```

Optional: `run_walk_forward` rolls fixed-parameter out-of-sample windows
(train dates are metadata only; no optimization).

## Signal contract

Event signals (not a continuous position target):

| signal | meaning |
|--------|---------|
| `1` | enter long (flat → long) |
| `-1` | exit long (long → flat) |
| `0` | hold |

Look-ahead rule: the signal on bar `t` is executed when forming bar `t+1`
returns (same as the original MVP engine).

The engine only **enters when flat** and **exits when long**. Repeated `1`
while already long (or `-1` while flat) is ignored — so raw signal counts are
not the same as fills / round-trips.

## Costs (honest limits)

`TradingCosts` applies a **proportional equity haircut** on entry and exit:

`commission_rate + slippage_bps / 10_000`

This is **not** share-level fill simulation (see agent `PaperBroker` for that).
Treat it as a research haircut, not a broker model.

## Strategies

| CLI `--strategy` | Class | Notes |
|------------------|-------|-------|
| `sma_cross` | `SMACrossStrategy` | fast/slow SMA **crossover events** (uses `indicators.sma`) |
| `rsi_reversion` | `RSIReversionStrategy` | RSI &lt; 30 → `1`, RSI &gt; 70 → `-1` **for every bar in zone** |

`RSIReversionStrategy` is zone-level, not crossover-only: it emits `1`/`-1` on
every bar that remains oversold/overbought. Combined with the engine’s
flat/long gate, many RSI signal bars produce no new trade.

## Metrics notes

- `trades_count` increments on **each entry and each exit** (two increments per
  completed round-trip).
- `trade_pnls`, `win_rate`, and `profit_factor` use **completed round-trips
  only**. An open long at the end of the series is excluded from PF / win rate
  (and does not append to `trade_pnls`).

## Walk-forward notes

`run_walk_forward` runs `strategy.run` on the **test slice only**. Train date
ranges are recorded as metadata (no parameter optimization, no warm-up history
passed into the strategy). Long indicator windows (e.g. SMA 60) are therefore
**cold at the start of each fold**. Warm-up across the train/test boundary is
out of scope for this MVP+.

## Known limitations (review)

1. **RSI signals ≠ fills** — zone-level `1`/`-1` every bar in oversold/overbought;
   engine enters only when flat / exits only when long.
2. **Walk-forward cold start** — indicators computed on the test slice alone;
   train bars are metadata only.
3. **`trades_count` vs PF/win rate** — count includes entries+exits; PF/win rate
   use completed round-trip `trade_pnls` only (open end positions excluded).
4. **Costs are haircuts** — proportional equity haircut, not `PaperBroker`
   share fills.

## Cloud vs local testing

| Where | Data | Who |
|-------|------|-----|
| Cursor Cloud / CI | Synthetic `sample_prices` + literal fixtures | Agent (`pytest -m "not integration"`) |
| Your machine | Real Q-SEED via `QSEED_HOST_PATH` | You (smoke after pull) |

Lint note: `ruff check .` may still fail on pre-existing E501 in agent/streamlit
paths; the analysis-quant changed paths are kept clean.

## Local Q-SEED smoke checklist

1. Fetch and check out `feat/analysis-quant`.
2. Set `QSEED_HOST_PATH` in `.env` to your Q-SEED `data` absolute path.
3. Re-run the synthetic gate locally:

```bash
uv run pytest -m "not integration"
```

4. Smoke against real prices:

```bash
uv run python scripts/run_mvp.py --symbol 005930.KS --skip-ai \
  --strategy sma_cross --commission-rate 0.00015 --slippage-bps 5

uv run python scripts/run_mvp.py --symbol 005930.KS --skip-ai \
  --strategy rsi_reversion
```

5. Check: row count loaded, buy/sell signal counts, return/CAGR/MDD/Sharpe/Sortino/trades,
   and that costs produce worse equity than a zero-cost run on the same inputs.
   Remember signal counts for `rsi_reversion` can exceed trade fills (see above).

Optional:

```bash
uv run pytest -m integration
```

## Out of scope (follow-up)

EMA/MACD/Bollinger/ATR library expansion, `feature_engineering`, monthly returns,
parameter grids, portfolio backtests, Streamlit analytics, RSI redesign as
crossover-only events, walk-forward indicator warm-up.
