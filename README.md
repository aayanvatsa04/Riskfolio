# Riskfolio 📊

> Democratising Institutional Risk Intelligence for Retail Investors.

**NUS Orbital 2026 — Apollo 11** | Team: RAGs to Riches

---

## What is Riskfolio?

Riskfolio is a web platform where users input their stock portfolio and the system runs **10,000+ Monte Carlo simulations** on 5 years of real market data to compute the statistical worst-case loss (Value at Risk) and related risk metrics — bringing institutional-grade quantitative risk tools to everyday investors.

---

## Features

| Feature | Status |
|---|---|
| Vectorized Monte Carlo Engine (10,000+ GBM simulations) | ✅ Complete |
| Value at Risk (VaR) — 95% confidence interval | ✅ Complete |
| Expected Shortfall (CVaR) — average tail loss | ✅ Complete |
| Automated Pytest Suite | ✅ Complete |

---

## Tech Stack

**Frontend:** React (Next.js) · Tailwind CSS · Plotly.js

**Backend:** FastAPI (Python)

**Computation:** NumPy · Pandas

**Database:** PostgreSQL

**DevOps:** Docker · GitHub Actions

---

## Project Structure

```
Riskfolio/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app and API endpoints
│   │   ├── models.py                # Pydantic request/response models
│   │   └── engine/
│   │       ├── __init__.py
│   │       └── monte_carlo_var.py   # Monte Carlo VaR engine
│   ├── tests/                       # Pytest test suite
│   ├── pyproject.toml               # uv project metadata and dependencies
│   └── uv.lock                      # locked backend dependency graph
├── frontend/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   └── ...                          # Next.js frontend
├── .github/
│   └── workflows/
│       └── test.yml                 # GitHub Actions CI/CD pipeline (TBD for future milestones)
├── .gitignore
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.13
- [uv](https://docs.astral.sh/uv/) for backend dependency management
- Node.js 20+ (Node 22 recommended)
- pnpm managed by Corepack
- Docker Desktop, if using Docker Compose

Install the local toolchain if needed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
corepack enable
```

The frontend pins its package manager in `frontend/package.json`, so Corepack
will resolve the project pnpm version automatically. Prefer this over
`npm install -g pnpm` or the pnpm shell installer, which can leave contributors
on different global pnpm versions.

Clone the repo and create your local environment file:

```bash
git clone https://github.com/yourusername/Riskfolio.git
cd Riskfolio
cp .env.example .env
```

The root `.env` is used by Docker Compose and documents the default local
ports. Keep `.env.example` committed, but keep `.env` local.

### Backend Setup

```bash
cd backend
uv sync --group dev
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify the API from another terminal:

```bash
curl http://localhost:8000/api/v1/health
curl "http://localhost:8000/api/v1/historical-prices?tickers=AAPL&period=5d"
```

The main API endpoints are:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/historical-prices?tickers=AAPL&period=5d` | Fetch historical prices |
| `POST` | `/api/v1/analyze` | Analyze holdings by ticker and quantity |

Example `/api/v1/analyze` payload:

```json
{
  "holdings": [
    { "ticker": "AAPL", "quantity": 10 },
    { "ticker": "MSFT", "quantity": 5 }
  ],
  "horizon": 1,
  "confidence_level": 0.95,
  "n_simulations": 10000
}
```

### Frontend Setup

Open a second terminal:

```bash
cd frontend
pnpm install
pnpm exec next dev --port 3000
```

Open `http://localhost:3000`.

By default, the frontend calls `http://localhost:8000` for the API. If the
backend is running on another port, pass the API URL when starting Next:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001 pnpm exec next dev --port 3000
```

### Running the Monte Carlo Engine (standalone)

```python
from app.engine.monte_carlo_var import run_var_analysis

results = run_var_analysis(
    portfolio={"AAPL": 0.40, "TSLA": 0.30, "GOOGL": 0.30},
    portfolio_value=10_000,   # Current market value in USD
    horizon=1,                # 1-day VaR
    confidence_level=0.95,
    n_simulations=10_000,
    verbose=True              # set to False when calling from FastAPI
)
```

### Running Tests

```bash
cd backend
uv run pytest
uv run ruff check main.py app tests
```

Frontend checks:

```bash
cd frontend
pnpm exec tsc --noEmit
pnpm run build
```

### Running With Docker Compose

```bash
./scripts/compose-up.sh
```

This starts from frontend port `3000` and backend port `8000`. If either port
is occupied, the script increments until it finds a free port and writes the
selected values to `.env`.

The script prints the exact URLs to open, for example:

```text
Using backend:  http://localhost:8000
Using frontend: http://localhost:3000
```

The frontend is configured with `NEXT_PUBLIC_API_BASE_URL` from `.env`, so
browser requests call the selected host-mapped backend directly.

The default Compose ports are in `.env`. Copy `.env.example` if you need to
reset or customize local values.

Useful checks:

```bash
curl http://localhost:8000/api/v1/health
curl "http://localhost:8000/api/v1/historical-prices?tickers=AAPL&period=5d"
```

Stop the stack with:

```bash
docker compose down
```

If you want a different starting range, set it in `.env` or when starting:

```bash
FRONTEND_PORT_START=3005 ./scripts/compose-up.sh
```

---

## Software Engineering Practices

| Practice | Implementation |
|---|---|
| Modular Architecture | Monte Carlo engine strictly decoupled from FastAPI layer |
| Test-Driven Development (TDD) | Pytest suite covering the engine, API, and historical price endpoint |
| Branch Protection & PR Workflow | All changes via feature branches and pull requests — direct pushes to main blocked |
| Conventional Commits | Standardised commit message format enforced across the team |

---

## Team

| Member | Role |
|---|---|
| Aayan | Backend · Monte Carlo Engine |
| Yu Yang | Frontend · FastAPI Integration |

---

*NUS Orbital 2026 — Apollo 11*
