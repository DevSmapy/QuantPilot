# Analysis Quant (single-asset MVP+)

`feat/analysis-quant` extends the QuantPilot vertical slice into a **swappable
strategy → backtest → metrics** pipeline for one symbol at a time.

MVP+ In scope is **complete**. Further Phase 2 expansions (indicators, features,
monthly returns, param grid, AnalysisBrief) land as commits on this branch;
later split targets are listed in [`PLAN.md`](PLAN.md).

## Pipeline

```text
DataSourceManager.get_price
        ↓
Strategy.run  →  signal ∈ {-1, 0, 1}
        ↓
BacktestEngine.run(+ TradingCosts)
        ↓
BacktestResult (return / CAGR / MDD / Sharpe / Sortino / PF / win rate /
                equity_curve / trade_pnls)
        ↓ (optional)
AnalysisBrief JSON  →  later: LLM prompt context
```

Optional: `run_walk_forward` rolls fixed-parameter out-of-sample windows
(train dates are metadata only; no optimization). Signals use train+test
context for indicator warm-up, then only the test period is backtested.

## Signal contract

Event signals (not a continuous position target):

| signal | meaning |
|--------|---------|
| `1` | enter long (flat → long) |
| `-1` | exit long (long → flat) |
| `0` | hold |

Look-ahead rule: the signal on bar `t` is executed when forming bar `t+1`
returns (same as the original MVP engine).

## Costs (honest limits)

`TradingCosts` applies a **proportional equity haircut** on entry and exit:

`commission_rate + slippage_bps / 10_000`

This is not share-level fill simulation (see agent `PaperBroker` for that).

## Strategies

| CLI `--strategy` | Class | Notes |
|------------------|-------|-------|
| `sma_cross` | `SMACrossStrategy` | fast/slow SMA cross events (uses `indicators.sma`) |
| `rsi_reversion` | `RSIReversionStrategy` | Edge into oversold (`1`) / overbought (`-1`); hold while regime persists |

## Cloud vs local testing

| Where | Data | Who |
|-------|------|-----|
| Cursor Cloud / CI | Synthetic `sample_prices` + literal fixtures | Agent (`pytest -m "not integration"`) |
| Your machine | Real Q-SEED via `QSEED_HOST_PATH` | You (smoke on this branch) |

## Local Q-SEED smoke checklist

Validate on **`feat/analysis-quant`** (local checkout of this branch).

1. Ensure you are on `feat/analysis-quant`.
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

5. Optional brief export:

```bash
uv run python scripts/run_mvp.py --symbol 005930.KS --skip-ai \
  --emit-brief brief.json
```

6. Check: row count loaded, buy/sell signal counts, return/CAGR/MDD/Sharpe/Sortino/trades,
   and that costs produce worse equity than a zero-cost run on the same inputs.

Optional:

```bash
uv run pytest -m integration
```

## Out of scope (follow-up branches)

See the roadmap table in [`PLAN.md`](PLAN.md). Notably deferred:

- Agent prompt injection (`feat/agent-research-context`)
- Portfolio backtests, Streamlit analytics, live trading, vectorbt
