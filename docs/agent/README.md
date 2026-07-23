# AI 투자 에이전트 시뮬레이션

히스토리컬 시세로 **미래 정보를 차단한 paper-trading 루프**를 돌리며, LLM(또는 Hold) 에이전트가 `buy` / `sell` / `hold`로 가상 자본을 운용하는지 검증하는 MVP입니다.

이 문서가 다루는 것: 공정한 시뮬레이션 루프, 매도·수익화, 매도 사유 강제, 다종목·비용, Streamlit 차트.  
다루지 않는 것: LLM 수익 보장, 실거래.

---

## 패키지 구조

```text
quantpilot/
  environment/     # 규칙적인 세계 (agent를 import하지 않음)
    clock.py       # SimulationClock — 거래일·as_of
    market.py      # HistoricalMarket + intersect_session_dates
    costs.py       # TradingCosts (commission_rate, slippage_bps)
    broker.py      # PaperBroker — multi-symbol holdings, pending, fees
    observation.py # ObservationBuilder → AgentObservation (legs)
    types.py
  agent/           # 행동 주체
    base.py        # TradingAgent.decide(obs) -> TradeDecision
    hold.py        # HoldAgent (항상 hold)
    llm.py         # LlmTradingAgent (Ollama JSON)
    decision.py    # 파싱·sell 사유·symbol 검증
  simulation/      # 조립
    session.py     # SimulationSession
    result.py      # SimResult (equity curve, decision log, fees)
    benchmark.py   # buy-and-hold (단일 / equal-weight 다종목)
scripts/run_agent_sim.py
scripts/streamlit_agent_sim.py
```

의존 방향: `simulation` → `environment` / `agent`. `environment`는 `agent`를 import하지 않습니다.

---

## 고정 규칙

1. **Look-ahead 금지** — `as_of` 이후 가격은 관측·프롬프트에 넣지 않습니다. 지표는 visible 구간에만 계산합니다. 로드 시 start 이전 lookback(기본 60거래일)을 포함합니다.
2. **하루 순서** — open으로 pending 체결 → close로 MTM → 결정일이면 결정 후 pending 등록(당일 미체결). 마지막 날에도 결정은 가능하나, 그날 pending은 **다음 날이 없어 폐기**.
3. **행동**

   | action | size | reason | symbol |
   |--------|------|--------|--------|
   | `buy` | 현금의 `0 < size ≤ 1` | 선택 | 유니버스 >1이면 **필수** |
   | `sell` | 해당 종목 수량의 `0 < size ≤ 1` | **필수** | 유니버스 >1이면 **필수** |
   | `hold` | 무시 | 선택 | 선택 |

   long-only, 정수 주수(내림). 기본 수수료·슬리피지 0 (`--commission-rate`, `--slippage-bps`로 변경). sell 사유 없음 / JSON 파싱 실패 / 브로커 거절 → hold. 결정은 EOD(당일 close 반영), 체결은 다음 거래일 open. pending은 한 건. 다종목 세션 달력은 유니버스 **교집합**.

4. **결정 주기** — 매 N거래일 (기본 `N=5`, `N=1`이면 매일).
5. **기간** — `--period-days`는 달력 일수. 루프는 그 안 거래일만.
6. **벤치마크** — buy-and-hold 최종 자산. **에이전트와 동일한** `TradingCosts`(진입 슬리피지·수수료)를 적용하고, 마지막 close로 평가합니다(청산 거래 없음). 다종목은 현금 균등 분할.

---

## 환경 변수

Mac / Windows 공통: `.env`에 **호스트 절대 경로**만 맞추면 Docker와 로컬 `uv run` 모두에서 동작합니다.

| 변수 | 역할 |
|------|------|
| `QSEED_HOST_PATH` | Mac/Windows의 Q-SEED data **절대 경로** (필수) |
| `QSEED_DATA_PATH` | 컨테이너 마운트 경로 (기본 `/data/qseed`) |
| `OLLAMA_BASE_URL` | Docker 기본 `http://ollama:11434` — 호스트 `uv run`에서는 `localhost`로 자동 변환 |
| `OLLAMA_MODEL` | 예: `llama3.2` |
| `DOCKER` | Compose/문서용 플래그 (경로·URL 해석은 컨테이너 여부로 자동) |

로컬에서 `/data/qseed`가 없으면 `QSEED_HOST_PATH`로 자동 fallback 합니다.  
`host.docker.internal`은 **컨테이너 → 호스트**용입니다. 호스트 `uv run`에서는 `localhost`(또는 자동 변환된 URL)를 씁니다.

Q-SEED data 디렉터리 예시:

```text
/path/to/Q-SEED/data/
├── stocks_0001.parquet
├── stocks_*.parquet
└── data_log/
```

---

## 실행

### Hold만 (Ollama 없이 스모크)

```bash
uv run python scripts/run_agent_sim.py \
  --start 2024-01-02 \
  --capital 10000000 \
  --target 12000000 \
  --period-days 90 \
  --decision-every 5 \
  --hold-only
```

### 다종목 + 비용

```bash
uv run python scripts/run_agent_sim.py \
  --symbols 005930.KS,000660.KS \
  --start 2024-01-02 \
  --target 12000000 \
  --period-days 90 \
  --commission-rate 0.00015 \
  --slippage-bps 5 \
  --hold-only
```

### LLM 에이전트

```bash
uv run python scripts/run_agent_sim.py \
  --symbol 005930.KS \
  --start 2024-01-02 \
  --capital 10000000 \
  --target 12000000 \
  --period-days 90 \
  --decision-every 5 \
  --runs 1 \
  --model llama3.2
```

### Streamlit 차트

```bash
uv sync --group viz
uv run streamlit run scripts/streamlit_agent_sim.py
```

사이드바에서 심볼·주가 종목·차트 종류(Close line / Candlestick)·기간·비용·hold-only를 설정한 뒤 실행합니다.

- 진행 중: equity·주가 차트 live 갱신, 진행률, **Trade log**(체결일·action·종목·주수·체결가·notional·fee·매도 사유). LLM 사용 시 결정 직전 `Waiting for Ollama…` 표시. 결과는 `st.session_state`에 보관되어 위젯 변경 후에도 유지됩니다.
- Equity: target 수평선, Buy&Hold **최종** 자산 마커(일별 경로 아님; 에이전트와 동일 비용), 매수/매도 마커는 체결 직후 open MTM.
- 주가: 평균단가 점선(보유 구간만). Close line 모드 마커는 **close**에 맞춤(hover는 체결가). Candlestick 모드 마커는 **체결가**(슬리피지 시 봉 H/L 밖일 수 있음).
- 완료 후 equity/fills CSV 다운로드 (`total_shares` + `holdings` 컬럼).

주요 플래그:

| 플래그 | 기본 | 설명 |
|--------|------|------|
| `--start` | (필수) | 시뮬레이션 시작일 |
| `--target` | (필수) | 목표 자산 |
| `--symbol` | `005930.KS` | 단일 종목 |
| `--symbols` | 없음 | 콤마 구분 다종목 (`--symbol`보다 우선) |
| `--capital` | 10000000 | 초기 현금 |
| `--period-days` | 90 | 달력 일수 윈도우 |
| `--decision-every` | 5 | N거래일마다 결정 |
| `--commission-rate` | 0 | 수수료율 (notional 비율) |
| `--slippage-bps` | 0 | 슬리피지 (bps) |
| `--runs` | 1 | 순차 반복 횟수 |
| `--hold-only` | off | LLM 대신 HoldAgent |
| `--model` | settings | Ollama 모델명 |
| `--temperature` | 0.7 | Ollama temperature (`--runs` 분산용) |
| `--seed` | 없음 | 있으면 run i에 `seed+i-1` 전달 |
| `--lookback-sessions` | 60 | start 이전 필요 거래일 수 (미달 시 종료) |

결정일마다 CLI에 `날짜 / cash / equity / action / reason`이 한 줄로 출력됩니다. 종료 시 최종 자산 vs target, fees, buy-and-hold를 비교합니다. `--runs N`(N>1)이면 최종자산 목록과 목표 달성 횟수를 요약합니다.

---

## Docker 참고

기존 SMA MVP 데모:

```bash
make up          # 또는 make up-external && make ollama-network
make demo        # AI 없이
make demo-ai     # Ollama 전략 리뷰 (run_mvp.py)
```

`make demo-ai`는 **전략 리뷰** 스크립트입니다. 에이전트 시뮬레이션은 `scripts/run_agent_sim.py`입니다.

Docker 이미지와 호스트 코드가 어긋나면 `storage/metadata/shard_index.json` 형식 오류가 날 수 있습니다. 그 경우:

```bash
docker compose build quantpilot
```

---

## 테스트

```bash
uv run pytest tests/test_agent_decision.py \
  tests/test_environment_broker.py \
  tests/test_environment_market_clock.py \
  tests/test_simulation_session.py \
  tests/test_package_deps.py -q
```

---

## 후속 (미구현)

- LM Studio, 투자 성향 모방
- sell 사유 “품질” 재판정, consensus 종목 추천
