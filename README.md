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
| MPT Optimizer — Efficient Frontier with Max Sharpe and Min Vol portfolios | ✅ Complete |
| Automated Pytest Suite (61 tests) | ✅ Complete |

---

## Tech Stack

**Frontend:** React (Next.js) · Tailwind CSS · Recharts

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
│   │       ├── monte_carlo_var.py   # Monte Carlo VaR engine
│   │       └── mpt_optimizer.py     # MPT Efficient Frontier optimizer
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
├── .env.example                     # template — copy to .env for local development
├── .gitignore
└── README.md
```

---

## Getting Started

### Step 1 — Install global prerequisites

These tools are installed once on your machine and used across all projects.

---

**uv** — Python package manager for the backend.

Mac / Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installing, close and reopen your terminal so `uv` is on your PATH.

---

**Node.js 22** — JavaScript runtime required for the frontend.

Mac / Linux — install via nvm (Node version manager):
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | sh
```
Close and reopen your terminal, then:
```bash
nvm install 22
nvm use 22
```

Windows — download the Node.js 22 installer directly from https://nodejs.org and run it.

---

**pnpm** — frontend package manager, installed via Corepack which ships with Node:
```bash
corepack enable
corepack prepare pnpm@latest --activate
```

The frontend pins its package manager version in `frontend/package.json`, so
Corepack resolves the correct pnpm version automatically. Prefer this over
`npm install -g pnpm` or the standalone pnpm installer, which can leave
contributors on different global pnpm versions.

---

**Docker Desktop** — optional, but recommended. Lets you run the entire app
with a single command without managing two terminals.

Download from https://www.docker.com/products/docker-desktop/ and install it
like any desktop application.

---

### Step 2 — Clone the repo

```bash
git clone https://github.com/aayanvatsa04/Riskfolio.git
cd Riskfolio
```

---

### Step 3 — Create your local environment file

```bash
cp .env.example .env
```

The root `.env` stores local port configuration used by Docker Compose.
Keep `.env.example` committed to the repo, but keep `.env` local — it is
gitignored and should never be committed.

> **Note:** If you run the app via Docker Compose, `./scripts/compose-up.sh`
> creates `.env` automatically if it does not exist. The manual `cp` step
> above is only strictly needed if you are running the app without Docker.

---

### Step 4 — Backend setup

Run these from the `backend/` directory:

```bash
cd backend

# Install all Python dependencies into backend/.venv
uv sync --group dev

# Set up git hooks so ruff runs automatically on every commit
uv run pre-commit install
```

To configure VS Code to use the project Python interpreter, open the command
palette (`Ctrl+Shift+P` on Windows/Linux, `Cmd+Shift+P` on Mac), run
`Python: Select Interpreter`, and choose the interpreter inside `backend/.venv`.

---

### Step 5 — Frontend setup

```bash
cd frontend
pnpm install
```

---

## Running the App

### Option A — Docker Compose (recommended)

Make sure Docker Desktop is open and running, then from the repo root:

```bash
./scripts/compose-up.sh
```

This starts from frontend port `3000` and backend port `8000`. If either port
is occupied, the script increments until it finds a free port and writes the
selected values to `.env`.

The script prints the exact URLs when ready:

```text
Using backend:  http://localhost:8000
Using frontend: http://localhost:3000
```

Open `http://localhost:3000` in your browser.

To stop the stack:
```bash
docker compose down
```

To start on a different port range:
```bash
FRONTEND_PORT_START=3005 ./scripts/compose-up.sh
```

To reset or customise ports, edit `.env` directly or recopy from the template:
```bash
cp .env.example .env
```

---

### Option B — Manual (two terminals)

Open two terminal windows simultaneously and run one command in each.

**Terminal 1 — backend:**
```bash
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Wait until you see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

**Terminal 2 — frontend:**
```bash
cd frontend
pnpm exec next dev --port 3000
```

Wait until you see:
```
ready - started server on http://localhost:3000
```

Open `http://localhost:3000` in your browser.

By default the frontend calls `http://localhost:8000` for the API. If the
backend is running on a different port, pass the URL explicitly:
```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001 pnpm exec next dev --port 3000
```

---

## Verifying the App is Working

Once running, confirm all endpoints respond:

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Historical prices
curl "http://localhost:8000/api/v1/historical-prices?tickers=AAPL&period=5d"

# VaR analysis
curl -s http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"holdings":[{"ticker":"AAPL","quantity":10},{"ticker":"MSFT","quantity":5}],"horizon":1}' \
  | python3 -m json.tool | head -20

# MPT optimizer
curl -s http://localhost:8000/api/v1/optimize \
  -H "Content-Type: application/json" \
  -d '{"holdings":[{"ticker":"AAPL","quantity":10},{"ticker":"MSFT","quantity":5}]}' \
  | python3 -m json.tool | head -20
```

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/historical-prices?tickers=AAPL&period=5d` | Fetch historical prices |
| `POST` | `/api/v1/analyze` | Monte Carlo VaR analysis |
| `POST` | `/api/v1/optimize` | MPT Efficient Frontier optimization |

**Example `/api/v1/analyze` payload:**
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

**Example `/api/v1/optimize` payload:**
```json
{
  "holdings": [
    { "ticker": "AAPL", "quantity": 10 },
    { "ticker": "MSFT", "quantity": 5 }
  ],
  "n_portfolios": 5000,
  "risk_free_rate": 0.05
}
```

---

## Running Tests

```bash
cd backend
uv run pytest
uv run ruff check app/
```

Frontend checks:
```bash
cd frontend
pnpm exec tsc --noEmit
pnpm run build
```

---

## Running the Engines Standalone

Both engines can be run directly for development and debugging. Each prints
a full human-readable report when run this way.

**Monte Carlo VaR engine:**
```bash
cd backend
uv run python -m app.engine.monte_carlo_var
```

**MPT optimizer engine:**
```bash
cd backend
uv run python -m app.engine.mpt_optimizer
```

> **Note:** Always use `python -m app.engine.<module>` from the `backend/`
> directory, not `python app/engine/<module>.py` directly. The `-m` flag
> ensures Python resolves imports relative to `backend/` where the `app`
> package lives.

---

## uv Quick Reference

Run all commands from `backend/`.

| Task | Command |
|---|---|
| Install all dependencies | `uv sync --group dev` |
| Add a runtime dependency | `uv add package-name` |
| Add a dev-only dependency | `uv add --dev package-name` |
| Run a Python file or command | `uv run python path/to/file.py` |
| Install pre-commit hooks | `uv run pre-commit install` |
| Run all hooks manually | `uv run pre-commit run --all-files` |

`uv sync` creates `backend/.venv` automatically if it does not already exist.
The `uv.lock` file pins exact dependency versions — commit it to the repo so
all contributors use identical package versions.

---

## Software Engineering Practices

| Practice | Implementation |
|---|---|
| Modular Architecture | Monte Carlo and MPT engines strictly decoupled from FastAPI layer |
| Test-Driven Development (TDD) | 61-test Pytest suite covering both engines, API endpoints, and data pipeline |
| Branch Protection & PR Workflow | All changes via feature branches and pull requests — direct pushes to main blocked |
| Conventional Commits | Standardised commit message format enforced across the team |
| Pre-commit Hooks | Ruff linter and formatter run automatically on every commit |

---

## Team

| Member | Role |
|---|---|
| Aayan | Backend · Monte Carlo Engine · MPT Optimizer |
| Yu Yang | Frontend · FastAPI Integration |

---

*NUS Orbital 2026 — Apollo 11*
