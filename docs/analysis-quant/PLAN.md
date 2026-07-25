<<<<<<< HEAD
<<<<<<< HEAD
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

**AnalysisBrief:** flat JSON for LLM context; `as_of` is look-ahead-safe (backtest
end or a specified date); indicator snapshot values are as-of only (no future).

---

## Acceptance

**CI / agent:** unit tests + ruff + black + mypy green on synthetic data
(`pytest -m "not integration"`).

<<<<<<< HEAD
**Local (user):** Q-SEED smoke via README checklist after pulling this branch.
=======
# feat/analysis-quant — Quant Analysis Engine 작업 계획
=======
# feat/analysis-quant — single-asset analysis MVP+
>>>>>>> 74fa7f9 (docs(analysis-quant): CLI flags and local Q-SEED checklist)

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

<<<<<<< HEAD
설계 원칙:

- 전략은 `DataFrame(date, OHLCV…)` → `DataFrame(date, signal∈{-1,0,1}, …)`
- 백테스트는 **직전 바 시그널**로 체결 (기존 look-ahead 방지 유지)
- 지표는 Polars `Series`/`DataFrame` 입력·출력, 부작용 없음

---

## 5. 작업 단계

### Step 0 — 계약(API) 고정

- `Strategy` protocol: `run(prices: pl.DataFrame) -> pl.DataFrame`
- `BacktestResult` 확장: equity curve, trade log, 추가 메트릭
- 시그널 컬럼 규약: `signal` ∈ {-1, 0, 1}, 날짜 키 = `QP_DATE`

### Step 1 — Metrics 모듈

`backtest/metrics.py`로 분리:

- 기존: total_return, CAGR, MDD, Sharpe
- 추가: Sortino, Profit Factor, Win Rate, Annual/Monthly Return 요약
- 순수 함수 + 단위 테스트 (결정적 fixture)

### Step 2 — Indicators 확장

우선순위:

1. EMA
2. MACD
3. Bollinger Bands
4. ATR

각 지표에 null/윈도우 검증 테스트.

### Step 3 — Strategy base + 예시 전략

- `strategy/base.py` (Protocol 또는 ABC)
- `SMACrossStrategy`가 지표 모듈(`sma`)을 재사용하도록 정리
- `RSIReversionStrategy` (과매수/과매도) 추가 — 인터페이스 검증용

### Step 4 — Backtest 엔진 고도화

- `TradingCosts` 연동 (또는 backtest 전용 costs dataclass)
- equity curve / trade list 반환
- cash·position 추적 (현재는 단순 배율 모델)
- 빈 데이터·단일 바·시그널 없음 edge case

### Step 5 — Walk Forward / Rolling

- `walk_forward.py`: in-sample / out-of-sample 구간 분할
- 구간별 `BacktestResult` + 집계 요약
- MVP: 파라미터 최적화는 수동(고정 파라미터 전달), 자동 그리드서치는 옵션

### Step 6 — Feature engineering (최소)

- simple/log returns
- rolling volatility
- 전략·지표가 공유하는 헬퍼만 (과한 프레임워크 금지)

### Step 7 — CLI / Docs

- `scripts/run_mvp.py` 또는 `scripts/run_backtest.py`: 전략·비용·기간 플래그
- `docs/analysis-quant/README.md`: 사용법, 시그널 규약, look-ahead 규칙
- README 로드맵 Phase 2 상태 갱신

### Step 8 — 품질 게이트

```bash
uv run pytest -m "not integration"
uv run ruff check .
uv run black --check .
uv run mypy quantpilot
```

---

## 6. 의존성·리스크

| 리스크 | 대응 |
|--------|------|
| Agent sim의 `TradingCosts`와 중복 | 공통 모듈로 승격할지, backtest 전용으로 둘지 Step 4에서 결정 |
| vectorbt 도입 유혹 | 1차는 Polars만; 성능·기능 한계 확인 후 재평가 |
| Walk-forward 복잡도 | 단일 자산 + 고정 파라미터부터 |
| 메트릭 정의 불일치 | 문서에 연율화(√252), MDD 부호 규약 명시 |
| Q-SEED 없는 CI | 단위 테스트는 synthetic Polars fixture 유지 |

---

## 7. 수락 기준 (Acceptance)

- [ ] Strategy / Indicator / Metrics에 공개 API와 docstring·타입 힌트
- [ ] Sortino, Profit Factor, Win Rate 단위 테스트 통과
- [ ] 비용 > 0 일 때 equity가 무비용 대비 낮아짐 검증
- [ ] Walk-forward가 최소 2개 폴드 결과를 반환
- [ ] SMA Cross + RSI 전략이 동일 엔진으로 백테스트 가능
- [ ] look-ahead: 시그널 발생 바 ≠ 체결 바 (기존 테스트 유지)
- [ ] lint / typecheck / unit tests green

---

## 8. PR 분할 제안

한 브랜치에서 순차 커밋하되, 리뷰 부담이 커지면 아래처럼 쪼갠다.

1. `feat(backtest): metrics module + richer BacktestResult`
2. `feat(indicators): ema, macd, bollinger, atr`
3. `feat(strategy): base protocol + RSI reversion`
4. `feat(backtest): costs, equity curve, walk-forward`
5. `docs(analysis-quant): usage + Phase 2 status`

---

## 9. 다음 액션

이 계획이 확정되면 Step 0(API 계약)부터 구현을 시작한다.
우선순위 조정이 필요하면 (예: Walk-forward를 뒤로, 비용/메트릭을 먼저) 이 문서를 갱신한다.
>>>>>>> b32ad17 (docs(analysis-quant): Phase 2 Quant Engine 작업 계획 추가)
=======
**Local (user):** Q-SEED smoke via README checklist after pulling this branch.
>>>>>>> 74fa7f9 (docs(analysis-quant): CLI flags and local Q-SEED checklist)
=======
**Local (user):** Q-SEED smoke via README checklist on `feat/analysis-quant`.
>>>>>>> 59a1c60 (docs(analysis-quant): detail follow-up branch roadmap and agent brief goal)
