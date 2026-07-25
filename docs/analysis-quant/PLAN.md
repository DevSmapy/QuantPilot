# feat/analysis-quant — single-asset analysis MVP+

> Extend the Q-SEED → strategy → backtest slice so strategies are swappable and
> metrics/costs are usable for local research. Not a full Phase 2 completion.

See also: [`README.md`](README.md) (usage + local Q-SEED checklist).

---

## Goal

`DataSourceManager` → `Strategy` → `BacktestEngine` (+ `TradingCosts`) → richer
`BacktestResult`, with CLI flags and synthetic unit tests in cloud; real Q-SEED
smoke on the user's machine.

Downstream consumer of research output is **`LlmTradingAgent`**: analysis emits an
**AnalysisBrief** JSON that can later be injected into the simulation decision
prompt. Wiring into `SimulationSession` / `_build_prompt` is a follow-up branch
(see roadmap below).

---

## In scope (MVP+)

**Status: complete** on `feat/analysis-quant`.

- `Strategy` protocol + `SMACrossStrategy` + `RSIReversionStrategy`
- Metrics: Sortino, Profit Factor, Win Rate, equity_curve, trade_pnls
- Proportional cost haircut via existing `TradingCosts`
- Rolling OOS helper (`run_walk_forward`, train metadata only)
- `scripts/run_mvp.py` strategy/cost flags
- Docs + local Q-SEED checklist

---

## Current branch: ahead-of-roadmap commits on `feat/analysis-quant`

These items are also implemented as sequential local commits on
`feat/analysis-quant` (roadmap branch names below are for later split only):

| Area | Deliverable |
|------|-------------|
| AnalysisBrief | Schema, builder, `brief_to_prompt_block`, `--emit-brief` CLI |
| Indicators | `ema` / `macd` / `bollinger` / `atr` |
| Features | `simple_returns` / `log_returns` / `rolling_volatility` |
| Metrics | `monthly_returns` + result + CLI |
| Param grid | Small fixed parameter grid helper (not an optimizer) |

---

## Follow-up branch roadmap

| 후속 브랜치 (예정) | 목적 | 주요 산출물 | 의존 |
|--------------------|------|-------------|------|
| `feat/indicators-expand` | 지표 라이브러리 | `ema`/`macd`/`bollinger`/`atr`, 테스트 | 없음 |
| `feat/feature-engineering` | 수익률·변동성 헬퍼 | `simple_returns`/`log_returns`/`rolling_volatility` | 없음 |
| `feat/monthly-returns` | 월별 성과 | `monthly_returns` 메트릭 + CLI | metrics |
| `feat/param-grid` | 고정 파라미터 그리드 | 소규모 grid runner (optimizer 아님) | strategy + engine |
| `feat/analysis-brief` | Agent용 분석 팩 | `AnalysisBrief` JSON 스키마·빌더 | backtest + indicators |
| `feat/agent-research-context` | 시뮬에 Brief 주입 | `ObservationBuilder`/`_build_prompt`에 brief 섹션, look-ahead 안전 규칙 | analysis-brief + agent |
| `feat/portfolio-backtest` | 다종목 백테스트 | Phase 4 | engine |
| `feat/dashboard-analytics` | Streamlit 분석 UI | Phase 6 | brief/metrics |

Roadmap branch names are labels for later separation — do not create them while
working on this branch.

### Explicitly deferred (not in this branch)

- `feat/agent-research-context` — prompt injection into the agent session
- Portfolio / live trading / Streamlit analytics / vectorbt / Backtrader

---

## Contracts

**Signals:** event `{-1,0,1}` — enter / exit / hold (not a position series).

**Look-ahead:** signal on bar `t` applies to bar `t+1` close-to-close return.

**Costs:** `commission_rate + slippage_bps/1e4` equity haircut on entry and exit.

**Metrics:** MDD `<= 0`; Sharpe/Sortino annualized with `√252`; PF from
completed round-trip `trade_pnls`.

**AnalysisBrief:** flat JSON for LLM context. When ``as_of`` is before the
backtest end, metrics / monthly returns / window are recomputed on data through
``as_of`` (no future performance). Indicator snapshots are as-of only.
``monthly_returns`` only emits consecutive calendar months (gaps skipped).
``atr_14`` uses Wilder RMA.

---

## Acceptance

**CI / agent:** unit tests + ruff + black + mypy green on synthetic data
(`pytest -m "not integration"`).

**Local (user):** Q-SEED smoke via README checklist on `feat/analysis-quant`.
