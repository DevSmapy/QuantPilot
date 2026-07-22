# QuantPilot

**AI 기반 퀀트 리서치 및 자동 투자 플랫폼**

> Collect Once, Research Everywhere.

QuantPilot은 다양한 금융 데이터 소스를 하나의 인터페이스로 통합하여 데이터 분석, 전략 개발, 백테스트, AI 리서치, 포트폴리오 관리, 자동 투자까지 수행하는 Quant Research Platform입니다.

---

## 핵심 가치

| 원칙 | 설명 |
|------|------|
| **Data Source Independence** | 전략 코드는 데이터 출처를 알 필요가 없습니다. `DataSourceManager`가 Q-SEED, DuckDB, PostgreSQL, 외부 API 중 최적의 소스를 선택합니다. |
| **Local First** | 로컬 데이터(Q-SEED → DuckDB → PostgreSQL → Cache)를 우선 사용하고, 없을 때만 API를 호출합니다. |
| **Provider Pattern** | 모든 데이터 공급자는 `BaseProvider` 인터페이스를 구현하여 자유롭게 교체·확장할 수 있습니다. |

---

## 아키텍처

```
                   +----------------------+
                   |      Q-SEED          |
                   | Financial Data Lake  |
                   +----------+-----------+
                              |
                 Local Database / Parquet
                              |
        External APIs ---------+
                              |
                              ▼
                  QuantPilot Data Layer
                              |
                              ▼
                 Feature Engineering
                              |
                              ▼
                   Strategy Engine
                              |
            +-----------------+----------------+
            |                                  |
            ▼                                  ▼
      Backtesting                    AI Research
            |                                  |
            +-----------------+----------------+
                              |
                              ▼
                    Portfolio Manager
                              |
                              ▼
                     Trading Engine
                              |
                              ▼
                      Broker API
```

---

## 주요 기능

- **Data Layer** — 멀티 소스 데이터 조회, 캐싱, 메타데이터 관리
- **Strategy Engine** — 지표 기반 전략 개발 및 실행
- **Backtesting** — Single Asset, Portfolio, Walk Forward, Rolling Window
- **AI Research** — LLM 기반 전략 리뷰, 뉴스 요약, 투자 리포트 생성
- **Portfolio Engine** — Equal Weight, Mean Variance, Risk Parity 등 (예정)
- **Trading Engine** — KIS, IB 등 브로커 API 연동 (예정)
- **Dashboard** — Streamlit 기반 분석 UI (예정)

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Language | Python 3.12 |
| Package Manager | uv |
| API | FastAPI |
| Database | DuckDB, PostgreSQL |
| Data | Polars, Pandas |
| Quant | vectorbt, Backtrader |
| Visualization | Plotly |
| Dashboard | Streamlit |
| AI | Ollama, OpenAI API |
| Automation | n8n |
| Container | Docker |

---

## 프로젝트 구조

```
quantpilot/
├── providers/              # 데이터 공급자 (Q-SEED, Yahoo, KIS, Polygon ...)
├── datasource/             # DataSourceManager, Cache, Metadata
├── storage/                # Parquet, DuckDB, PostgreSQL
├── feature_engineering/
├── strategy/
├── indicators/
├── backtest/
├── ai/
├── optimizer/
├── trading/
├── dashboard/
├── docs/
└── tests/
```

---

## 로드맵

| Phase | 내용 | 상태 |
|-------|------|------|
| 1 | Data Platform — Provider, DataSourceManager, Cache, Q-SEED 연동 | 진행 예정 |
| 2 | Quant Engine — Indicator, Strategy, Backtest | |
| 3 | AI Research — LLM, 뉴스 분석, 전략 리뷰 | |
| 4 | Portfolio — Optimizer, Risk Management | |
| 5 | Auto Trading — Broker API, 실시간 주문 | |
| 6 | Dashboard — Streamlit, Analytics, Report | |

상세 기획은 [`plan.md`](plan.md)를 참고하세요.

---

## 브랜치 전략

```
main          ← 배포 가능한 안정 버전
develop       ← 기능 통합 브랜치
feature/*     ← 기능 단위 개발
```

---

## 개발 원칙

- 하나의 PR은 하나의 기능만 구현합니다.
- Provider를 직접 호출하지 않고 `DataSourceManager`를 통해 접근합니다.
- 새 데이터 소스는 `BaseProvider`를 상속하여 구현합니다.
- 모든 기능에 단위 테스트를 작성합니다.
- `ruff`, `black`, `mypy`를 통과해야 병합할 수 있습니다.

---

## MVP Quick Start (`feat/build-mvp`)

Vertical slice: Q-SEED data → SMA strategy → backtest → Ollama review.

모든 실행 환경은 **Docker + uv** 기준입니다. Ollama는 Docker 컨테이너에서 실행됩니다.

### 1. 환경 설정

```bash
cp .env.example .env
# QSEED_HOST_PATH를 본인 Q-SEED data 디렉터리 절대 경로로 설정 (필수)
# 기본 Ollama URL: http://ollama:11434 (`make up` bundled flow)
```

### 2. Docker로 실행 (권장)

```bash
# bundled Ollama + 개발 컨테이너 기동
make up

# 기존 ollama 컨테이너를 쓰는 경우
make up-external
make ollama-network

# MVP 데모 (AI 제외)
make demo

# MVP 데모 (Ollama 전략 리뷰 포함)
make demo-ai
```

Makefile 단축 명령:

```bash
make up            # bundled ollama + dev container
make up-external   # dev container only
make ollama-network
make demo          # MVP without AI
make demo-ai       # MVP with Ollama review
make shell         # dev container shell
```

기존 Ollama를 호스트 포트로 노출 중이면 `.env`에서 `OLLAMA_BASE_URL=http://host.docker.internal:11434`로 변경할 수 있습니다.

### 3. 로컬 개발 (uv)

Docker 없이 호스트에서 개발할 때:

```bash
uv sync
cp .env.example .env
# 로컬에서는 OLLAMA_BASE_URL=http://localhost:11434 로 변경
```

```bash
# 테스트 & 린트
uv run pytest -m "not integration"
uv run ruff check .
uv run black --check .
uv run mypy quantpilot

# 로컬 MVP 실행 (Q-SEED 경로를 호스트 경로로 설정)
uv run python scripts/run_mvp.py --symbol 005930.KS --skip-ai
```

Integration tests (Q-SEED 드라이브 마운트 필요):

```bash
uv run pytest -m integration
```

---

## 라이선스

TBD
