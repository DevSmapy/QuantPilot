# feat/analysis-quant — Quant Analysis Engine 작업 계획

> Phase 2 (Quant Engine)를 MVP 수준에서 **재사용 가능한 분석 엔진**으로 확장한다.
> 기준 문서: [`plan.md`](../../plan.md) §6 Backtesting / §11 Phase 2

---

## 1. 목표

`DataSourceManager`로 받은 가격 데이터에 대해

1. 지표(indicator)를 조합하고
2. 전략(strategy)이 시그널을 생성하며
3. 백테스트가 성과·리스크 지표를 산출하고
4. CLI/테스트로 검증 가능

한 **분석 파이프라인**을 만든다.

성공 기준:

- 전략/지표/백테스트가 공통 인터페이스로 교체 가능
- look-ahead bias 없이 시그널 실행
- `plan.md`에 명시된 핵심 성과지표 대부분 산출
- Provider를 직접 호출하지 않음 (`DataSourceManager`만 사용)

---

## 2. 현재 상태 (As-Is)

| 영역 | 구현 | 한계 |
|------|------|------|
| Indicators | `sma`, `rsi` | EMA/MACD/ATR/볼린저 없음, 공통 API 없음 |
| Strategy | `SMACrossStrategy` | 베이스 클래스 없음, RSI 전략 등 확장 경로 없음 |
| Backtest | `BacktestEngine` (long-only) | 수수료·슬리피지·포지션 사이징·equity curve 미반환 |
| Metrics | total_return, CAGR, MDD, Sharpe, trades | Sortino, Profit Factor, Win Rate, Monthly Return 없음 |
| Modes | Single Asset only | Portfolio / Walk Forward / Rolling Window 없음 |
| Feature Eng. | 없음 | `plan.md`의 `feature_engineering/` 미구현 |
| CLI | `scripts/run_mvp.py` | SMA Cross 고정 |

Agent Simulation(`environment` / `simulation`)은 별도 트랙이며, 본 브랜치는 **규칙 기반 퀀트 분석**에 집중한다.

---

## 3. 범위 (In / Out)

### In Scope

- Indicator 라이브러리 확장 + 공통 시그니처
- Strategy protocol / base
- Backtest 엔진 고도화 (비용, 메트릭, equity curve)
- Walk-forward / rolling window (single-asset)
- Feature helpers (수익률, 롤링 통계 등 최소 세트)
- 단위 테스트 + 문서 + 데모 CLI 확장

### Out of Scope (후속 브랜치)

- Portfolio optimizer (Mean Variance, Risk Parity 등) → Phase 4
- Broker / live trading → Phase 5
- Streamlit analytics dashboard → Phase 6
- vectorbt / Backtrader 직접 의존 (필요 시 별도 평가; 1차는 Polars 자체 구현)
- 멀티 자산 클래스 / 선물·옵션

---

## 4. 제안 패키지 구조

```
quantpilot/
├── indicators/
│   ├── __init__.py          # 공개 API re-export
│   ├── base.py              # Indicator protocol / helpers
│   ├── sma.py / ema.py / rsi.py / macd.py / atr.py / bollinger.py
├── strategy/
│   ├── __init__.py
│   ├── base.py              # Strategy protocol (run → signals)
│   ├── sma_cross.py
│   └── rsi_reversion.py     # 예시 전략 1개 추가
├── feature_engineering/
│   ├── __init__.py
│   └── returns.py           # log/simple return, rolling vol 등
├── backtest/
│   ├── __init__.py
│   ├── costs.py             # commission / slippage (환경 모듈과 정합 가능하면 재사용)
│   ├── metrics.py           # CAGR, MDD, Sharpe, Sortino, ...
│   ├── engine.py            # event-driven long-only (+ 옵션 long/flat)
│   └── walk_forward.py      # train/test 윈도우 분할 실행
```

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
