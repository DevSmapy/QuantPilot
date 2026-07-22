# QuantPilot

## AI 기반 퀀트 리서치 및 자동 투자 플랫폼

---

# 1. 프로젝트 개요

## 프로젝트명

**QuantPilot**

---

## 프로젝트 목표

QuantPilot은 다양한 금융 데이터 소스를 하나의 인터페이스로 통합하여

* 데이터 분석
* 전략 개발
* 백테스트
* AI 기반 리서치
* 포트폴리오 관리
* 자동 투자

까지 수행하는 AI 기반 Quant Research Platform이다.

본 프로젝트는 데이터 저장 방식과 무관하게 동일한 분석 환경을 제공하는 것을 핵심 목표로 한다.

---

## 프로젝트 철학

```
Collect Once,
Research Everywhere.
```

데이터는 한 번만 수집한다.

이후 모든 프로젝트는 동일한 데이터를 활용한다.

---

# 2. 전체 아키텍처

```
                   +----------------------+
                   |      Q-SEED          |
                   | Financial Data Lake  |
                   +----------+-----------+
                              |
                 Local Database / Parquet
                              |
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

# 3. 핵심 설계 원칙

## 3.1 Data Source Independence

전략 엔진은

> 데이터가 어디에서 오는지 절대 알지 못한다.

예를 들어

```
strategy.get_price("AAPL")
```

을 호출하면

Data Layer가

* Q-SEED
* DuckDB
* PostgreSQL
* Yahoo API
* Polygon API

중 적절한 데이터를 반환한다.

---

## 3.2 Local First

항상 로컬 데이터를 우선 사용한다.

```
Q-SEED

↓

DuckDB

↓

PostgreSQL

↓

Cache

↓

API

↓

Cache Update
```

이미 존재하는 데이터는 API를 호출하지 않는다.

---

## 3.3 Provider Pattern

모든 데이터 공급자는 동일한 인터페이스를 가진다.

```
BaseProvider

↓

QSeedProvider

YahooProvider

PolygonProvider

KISProvider

DuckDBProvider

PostgresProvider
```

이를 통해 데이터 공급자를 자유롭게 교체할 수 있다.

---

# 4. 시스템 구성

## Data Layer

역할

* 데이터 조회
* 데이터 캐싱
* 데이터 업데이트
* 데이터 통합

---

### DataSourceManager

모든 Provider를 관리한다.

```
Strategy

↓

DataSourceManager

↓

Provider 선택

↓

Data 반환
```

---

### Provider

모든 Provider는 다음 인터페이스를 구현한다.

```
get_price()

get_fundamental()

get_financial_statement()

get_news()

get_macro()

update()
```

---

### Cache Manager

API 호출 결과를 저장한다.

```
API

↓

Parquet

↓

다음 요청은 Cache 사용
```

---

### Metadata Manager

관리 대상

* 마지막 업데이트
* 데이터 출처
* 심볼 정보
* 거래소 정보

---

# 5. AI Research Engine

LLM을 이용하여

### 전략 설명

```
Momentum 전략입니다.

추세추종과 RSI를 함께 사용합니다.
```

---

### 전략 리뷰

```
과최적화 가능성이 있습니다.

Walk Forward Test를 추천합니다.
```

---

### 뉴스 요약

```
Reuters 기사

↓

요약

↓

감성 분석

↓

기업 태깅
```

---

### 투자 리포트 생성

예시

```
오늘의 추천 종목

시장 요약

리스크 요인

포트폴리오 변화
```

---

# 6. Backtesting Engine

지원

* Single Asset
* Portfolio
* Walk Forward
* Rolling Window

성과지표

* CAGR
* MDD
* Sharpe
* Sortino
* Profit Factor
* Win Rate
* Annual Return
* Monthly Return

---

# 7. Portfolio Engine

지원 예정

* Equal Weight
* Mean Variance
* Risk Parity
* Black-Litterman
* Kelly Criterion

---

# 8. Trading Engine

Broker API

지원 예정

* 한국투자증권
* 미래에셋
* Interactive Brokers

기능

* 주문
* 취소
* 리밸런싱
* 리스크 관리

---

# 9. 기술 스택

### Backend

* Python 3.12

### API

* FastAPI

### Database

* DuckDB
* PostgreSQL

### Data

* Polars
* Pandas

### Quant

* vectorbt
* Backtrader

### Visualization

* Plotly

### Dashboard

* Streamlit

### AI

* Ollama
* OpenAI API

### Automation

* n8n

### Container

* Docker

---

# 10. 프로젝트 구조

```
quantpilot/

│
├── app/
│
├── providers/
│   ├── base_provider.py
│   ├── qseed_provider.py
│   ├── yahoo_provider.py
│   ├── kis_provider.py
│   └── polygon_provider.py
│
├── datasource/
│   ├── datasource_manager.py
│   ├── cache_manager.py
│   └── metadata_manager.py
│
├── storage/
│   ├── parquet/
│   ├── duckdb/
│   ├── postgres/
│   └── metadata/
│
├── feature_engineering/
│
├── strategy/
│
├── indicators/
│
├── optimizer/
│
├── backtest/
│
├── ai/
│
├── trading/
│
├── dashboard/
│
├── docs/
│
└── tests/
```

---

# 11. 개발 로드맵

## Phase 1

Data Platform

* Provider
* DataSource Manager
* Cache
* Metadata
* Q-SEED 연동

---

## Phase 2

Quant Engine

* Indicator
* Strategy
* Backtest

---

## Phase 3

AI Research

* LLM
* 뉴스 분석
* 전략 리뷰

---

## Phase 4

Portfolio

* Optimizer
* Risk Management

---

## Phase 5

Auto Trading

* Broker API
* 실시간 주문

---

## Phase 6

Dashboard

* Streamlit
* Analytics
* Report

---

# 12. Git 브랜치 전략 (Cursor AI 친화형)

이 프로젝트는 **GitHub Flow보다 GitFlow를 단순화한 방식**을 추천한다. Cursor AI가 하나의 기능 단위로 작업하기에 가장 적합한 구조다.

```
main
│
develop
│
├── feature/data-provider
├── feature/qseed-provider
├── feature/cache-manager
├── feature/metadata-manager
├── feature/backtest-engine
├── feature/indicator-library
├── feature/strategy-engine
├── feature/news-engine
├── feature/llm-research
├── feature/portfolio-engine
├── feature/trading-engine
├── feature/dashboard
├── feature/report-generator
├── feature/docker
└── feature/ci-cd
```

### 브랜치 규칙

* `main`: 항상 배포 가능한 안정 버전
* `develop`: 모든 기능이 병합되는 통합 브랜치
* `feature/*`: 하나의 기능만 구현
* `release/*`: 정식 릴리스 준비
* `hotfix/*`: 운영 버그 수정

예시 작업 흐름:

```
develop
    │
    ├── feature/qseed-provider
    │        ↓
    │   Pull Request
    │        ↓
    ├──────────────→ develop
    │
    ├── feature/cache-manager
    │        ↓
    └──────────────→ develop
```

---

# 13. Cursor AI 작업 규칙

Cursor AI가 일관된 품질로 개발할 수 있도록 다음 규칙을 프로젝트 최상단 `AGENTS.md` 또는 `CONTRIBUTING.md`에 명시하는 것을 권장한다.

### 개발 원칙

* 하나의 PR은 하나의 기능만 구현한다.
* 비즈니스 로직은 Provider를 직접 호출하지 않고 반드시 `DataSourceManager`를 통해 접근한다.
* 새로운 데이터 소스는 `BaseProvider`를 상속받아 구현한다.
* 모든 기능에는 단위 테스트를 작성한다.
* 함수와 클래스에는 타입 힌트와 Docstring을 포함한다.
* `ruff`, `black`, `mypy`를 통과해야 병합할 수 있다.
* 설정값(API 키, 경로 등)은 환경 변수 또는 설정 파일로 관리하고 코드에 하드코딩하지 않는다.

---

## 향후 확장 계획

이 프로젝트는 처음부터 **플러그인 기반(Plugin Architecture)** 을 염두에 두고 설계한다. 따라서 새로운 브로커, 데이터 소스, AI 모델, 분석 모듈을 기존 코드를 크게 수정하지 않고 추가할 수 있도록 한다.

장기적으로는 다음과 같은 생태계를 목표로 한다.

* **Q-SEED**: 금융 데이터 레이크(Data Lake)
* **QuantPilot**: AI 기반 퀀트 리서치 플랫폼
* **Auto Trading**: 자동 투자 실행 엔진
* **Portfolio Analytics**: 성과 분석 및 리포팅 플랫폼
* **MCP Server**: 외부 AI 에이전트가 금융 데이터를 활용할 수 있는 표준 인터페이스
