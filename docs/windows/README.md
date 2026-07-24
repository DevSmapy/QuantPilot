# Windows에서 QuantPilot 실행하기

이 가이드는 Windows(PowerShell / Docker Desktop)에서 현재 사용 가능한 기능을 실행하는 방법을 정리합니다. Make가 없어도 따라 할 수 있습니다.

시뮬레이션 규칙·패키지 구조는 [`docs/agent/README.md`](../agent/README.md)를 참고하세요.

---

## 전제

| 항목 | 설명 |
|------|------|
| OS | Windows 10/11, PowerShell 5+ 또는 PowerShell 7 |
| Python | 3.12 (호스트 `uv` 경로를 쓸 때) |
| 패키지 관리 | [uv](https://docs.astral.sh/uv/) |
| 데이터 | Q-SEED `data/` 디렉터리 (아래 레이아웃) |
| Docker | [Docker Desktop](https://www.docker.com/products/docker-desktop/) (경로 A, 선택) |
| Ollama | LLM MVP 리뷰·에이전트에 필요. Hold-only / `--skip-ai`에는 불필요 |

Q-SEED data 레이아웃 예시:

```text
D:/path/to/Q-SEED/data/
├── stocks_0001.parquet
├── stocks_*.parquet
└── data_log/
```

---

## 사용 가능한 기능

| 기능 | 진입점 | 비고 |
|------|--------|------|
| MVP 데모 (전략 → 백테스트, AI 선택) | `scripts/run_mvp.py` | `--skip-ai`로 Ollama 없이 실행 가능 |
| 에이전트 시뮬레이션 (CLI) | `scripts/run_agent_sim.py` | Hold / Ollama, 다종목·수수료·슬리피지 |
| Streamlit equity / 매매 마커 | `scripts/streamlit_agent_sim.py` | `uv sync --group viz` 필요 |
| 단위 테스트·린트 | `pytest` / `ruff` / `black` / `mypy` | |

---

## 환경 변수 (`.env`)

Docker와 호스트 `uv`가 **같은 `.env`** 를 씁니다. `QSEED_HOST_PATH`만 Windows 절대 경로로 맞추면 됩니다.

```powershell
Copy-Item .env.example .env
notepad .env   # 또는 원하는 에디터
```

권장 설정:

```env
QSEED_HOST_PATH=D:/Users/User/Q-SEED/data
QSEED_DATA_PATH=/data/qseed
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2
DOCKER=1
```

동작 요약:

- **Docker Compose**: `QSEED_HOST_PATH`를 `/data/qseed`로 마운트하고, Ollama는 `http://ollama:11434`를 사용합니다.
- **호스트 `uv run`**: `/data/qseed`가 없으면 `QSEED_HOST_PATH`로 자동 fallback하고, `http://ollama:11434`는 `http://localhost:11434`로 자동 변환됩니다.
- Windows 경로는 **슬래시(`/`)** 형태를 권장합니다 (`D:/...`).
- `host.docker.internal`은 **컨테이너 → 호스트**용입니다. 호스트 `uv`에서는 보통 자동 변환된 `localhost`를 쓰면 됩니다.
- Docker Desktop에서 드라이브 문자 경로가 실패하면 따옴표(`"D:/..."`)를 시도하세요. 해당 드라이브 공유가 켜져 있어야 합니다.

로컬 전용으로 URL·경로를 직접 고정하려면 `.env.example` 하단 optional overrides를 참고하세요. 보통은 필요 없습니다.

---

## 경로 A: Docker Desktop

저장소 루트에서 PowerShell을 엽니다. Make 없이도 `docker compose`로 동일하게 동작합니다.

### 1) Bundled Ollama + 개발 컨테이너

```powershell
docker compose --profile dev --profile bundled-ollama up -d ollama quantpilot-dev
```

Bundled Ollama의 **서비스 이름(DNS)** 은 `ollama`이고, **컨테이너 이름**은 `quantpilot-ollama`입니다. `.env`의 `OLLAMA_BASE_URL=http://ollama:11434`는 서비스 이름을 가리킵니다.

### 2) 이미 떠 있는 외부 Ollama 컨테이너만 쓸 때

호스트에 따로 띄운 Ollama 컨테이너(보통 이름 `ollama`)를 QuantPilot 네트워크에 붙입니다. Bundled(`quantpilot-ollama`)와 혼동하지 마세요.

```powershell
docker compose --profile dev up -d quantpilot-dev

# 프로젝트 디렉터리 이름이 QuantPilot이면 기본 네트워크는 quantpilot_default
# COMPOSE_PROJECT_NAME을 바꿨다면 실제 네트워크 이름으로 교체
docker network ls | Select-String quantpilot

# 이미 연결되어 있으면 에러가 납니다 — 그 경우 건너뛰면 됩니다
docker network connect quantpilot_default ollama
```

컨테이너 이름이 `ollama`가 아니면 실제 이름으로 바꾸세요.

### MVP 데모

`--skip-ai`는 Ollama 없이 가능합니다. **전략 리뷰(AI) 포함** 명령은 위에서 Ollama가 기동·연결된 뒤에 실행하세요 (§1 bundled `up` 또는 §2 네트워크 connect).

```powershell
# AI 없이
docker compose run --rm quantpilot python scripts/run_mvp.py --symbol 005930.KS --start 2023-01-01 --end 2023-12-31 --skip-ai

# Ollama 전략 리뷰 포함 (ollama 서비스가 떠 있어야 함)
docker compose run --rm quantpilot python scripts/run_mvp.py --symbol 005930.KS --start 2023-01-01 --end 2023-12-31
```

### 에이전트 시뮬레이션 (컨테이너 안)

`quantpilot-dev`가 떠 있어야 합니다 (§1 또는 §2의 `up` 이후). `compose run`만으로 MVP를 돌린 상태에서는 `exec`가 실패합니다.

```powershell
docker compose exec quantpilot-dev python scripts/run_agent_sim.py --start 2024-01-02 --target 12000000 --period-days 90 --hold-only
```

### Make가 있는 경우 (선택)

Git Bash / WSL / Make for Windows가 있으면 README의 `make up`, `make demo` 등을 그대로 쓸 수 있습니다.

### 종료

```powershell
docker compose --profile dev --profile bundled-ollama down
```

---

## 경로 B: 호스트 `uv`

```powershell
uv sync
```

`.env`의 `QSEED_HOST_PATH`만 맞춰 두면 됩니다 (공유 `.env` 모델).

### MVP

```powershell
uv run python scripts/run_mvp.py --symbol 005930.KS --skip-ai
```

### 에이전트 — Hold만 (Ollama 불필요)

```powershell
uv run python scripts/run_agent_sim.py `
  --start 2024-01-02 `
  --capital 10000000 `
  --target 12000000 `
  --period-days 90 `
  --decision-every 5 `
  --hold-only
```

### 에이전트 — 다종목 + 비용

```powershell
uv run python scripts/run_agent_sim.py `
  --symbols 005930.KS,000660.KS `
  --start 2024-01-02 `
  --target 12000000 `
  --period-days 90 `
  --commission-rate 0.00015 `
  --slippage-bps 5 `
  --hold-only
```

### 에이전트 — LLM (호스트 Ollama)

Ollama가 `http://localhost:11434`에서 응답하는지 확인한 뒤:

```powershell
uv run python scripts/run_agent_sim.py `
  --symbol 005930.KS `
  --start 2024-01-02 `
  --capital 10000000 `
  --target 12000000 `
  --period-days 90 `
  --decision-every 5 `
  --runs 1 `
  --model llama3.2
```

### Streamlit

```powershell
uv sync --group viz
uv run streamlit run scripts/streamlit_agent_sim.py
```

---

## 검증 (테스트·린트)

```powershell
uv run pytest -m "not integration"
uv run ruff check .
uv run black --check .
uv run mypy quantpilot
```

에이전트 관련만:

```powershell
uv run pytest tests/test_agent_decision.py `
  tests/test_environment_broker.py `
  tests/test_environment_market_clock.py `
  tests/test_simulation_session.py `
  tests/test_package_deps.py -q
```

Integration 테스트는 Q-SEED 경로가 설정된 환경에서:

```powershell
uv run pytest -m integration
```

---

## 트러블슈팅

| 증상 | 확인 |
|------|------|
| `QSEED_HOST_PATH` / compose 시작 실패 | `.env`에 절대 경로가 있는지, `D:/...` 형태·드라이브 공유 |
| 로컬에서 데이터를 못 찾음 | `QSEED_HOST_PATH`가 실제 폴더인지. `/data/qseed`만 두고 호스트 경로를 비우면 fallback 실패 |
| Ollama 연결 거부 | Docker → `http://ollama:11434` + ollama 기동. 호스트 → localhost(자동 변환). 컨테이너인데 host-only URL을 강제로 넣지 않았는지 확인 |
| `make` 명령 없음 | 이 문서의 `docker compose` / `uv run` 사용 |
| `network connect` 실패 | 네트워크 이름(`docker network ls`), 컨테이너 이름 확인. Bundled는 `quantpilot-ollama`. 이미 연결됨 에러면 무시 |
| `exec` 실패 (no container) | 먼저 §1/§2에서 `quantpilot-dev`를 `up` |
| Streamlit / viz 패키지 없음 | `uv sync --group viz` |
| 이미지와 호스트 코드 불일치 | `docker compose build quantpilot` 후 재실행 |
| PowerShell에서 줄 이어쓰기 | bash의 `\` 대신 백틱 `` ` `` |

---

## 관련 문서

- 제품 개요·Unix Make Quick Start: [`README.md`](../../README.md)
- 에이전트 규칙·플래그: [`docs/agent/README.md`](../agent/README.md)
- 환경 변수 템플릿: [`.env.example`](../../.env.example)
