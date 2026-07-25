# Riskfolio 📊

> Democratising Institutional Risk Intelligence for Retail Investors.

**NUS Orbital 2026 — Apollo 11** | Team: RAGs to Riches

**🔗 Live App:** [riskfolio-nine.vercel.app](https://riskfolio-nine.vercel.app)

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
| MPT Optimizer — Efficient Frontier with Max Sharpe and Min Vol portfolios, plus actionable buy/sell share targets (not just weight percentages) | ✅ Complete |
| Analytical Efficient Frontier — exact frontier via `scipy.optimize` (SLSQP), plotted alongside the Monte Carlo cloud | ✅ Complete |
| Stress Test Module — baseline vs. shocked VaR/CVaR under a hypothetical scenario (per-ticker price shocks + volatility multiplier) | ✅ Complete |
| Monte Carlo Price Paths — interactive simulated price-path visualization | ✅ Complete |
| Browser price caching — Dexie-backed quote response cache with stale fallback | ✅ Complete |
| Optional cloud portfolio sync — Google OAuth via Supabase with local-first privacy | ✅ Complete |
| Automated Pytest Suite (120 tests, including Hypothesis property-based tests) | ✅ Complete |

---

## Tech Stack

**Frontend:** React (Next.js) · Tailwind CSS · Recharts

**Backend:** FastAPI (Python)

**Computation:** NumPy · Pandas

**Storage:** IndexedDB (Dexie) for local portfolios and browser price cache · Supabase Auth/Postgres for optional cloud portfolio sync

**DevOps:** Docker · GitHub Actions

---

## Project Structure

```
Riskfolio/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app and API endpoints
│   │   ├── settings.py              # Environment/config loading
│   │   ├── models/                  # Pydantic request/response models (one file per feature)
│   │   │   ├── common.py            # Shared holding/health models
│   │   │   ├── var.py               # VaR request/response models
│   │   │   ├── optimizer.py         # MPT optimizer request/response models
│   │   │   ├── monte_carlo.py       # Monte Carlo price-path models
│   │   │   └── stress.py            # Stress test request/response models
│   │   └── engine/
│   │       ├── monte_carlo_var.py   # Monte Carlo VaR engine + price-path simulation
│   │       ├── mpt_optimizer.py     # MPT Efficient Frontier optimizer (Monte Carlo + analytical/SLSQP)
│   │       └── stress_test.py       # Stress test engine (baseline vs. shocked VaR)
│   ├── tests/                       # Pytest test suite (120 tests)
│   ├── pyproject.toml               # uv project metadata and dependencies
│   └── uv.lock                      # locked backend dependency graph
├── frontend/
│   ├── app/                         # Next.js app router pages
│   ├── components/                  # Portfolio form, charts (Efficient Frontier, Monte Carlo paths), shadcn/ui primitives
│   ├── lib/                         # API client, Dexie local storage, Supabase sync helpers
│   ├── package.json
│   └── pnpm-lock.yaml
├── supabase/
│   ├── config.toml
│   └── migrations/                  # SQL migrations for portfolio sync and RLS
├── .github/
│   └── workflows/
│       └── test.yml                 # GitHub Actions CI/CD pipeline (lint, format check, tests — backend and frontend)
├── .env.example                     # template — copy to .env for local development
├── .gitignore
├── HANDOFF.md                       # Backend → frontend integration notes for in-flight features
└── README.md
```

---

## Getting Started

### Step 1 — Clone the repo

```bash
git clone https://github.com/aayanvatsa04/Riskfolio.git
cd Riskfolio
```

---

### Step 2 — Create your local environment file

```bash
cp .env.example .env
```

The root `.env` stores local configuration used by Docker Compose and the
frontend. Keep `.env.example` committed to the repo, but keep `.env` local —
it is gitignored and should never be committed.

Optional Supabase cloud sync uses public browser-safe variables:

```bash
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=your-publishable-key
```

The frontend also reads these values from the repo-root `.env` during local
Next.js startup, so you do not need a second `.env.local` inside `frontend/`.
If these values are absent, Riskfolio still works in local-only mode. Portfolio
data remains in the user's browser and is not uploaded.

To enable cloud portfolio sync, configure Google OAuth in Supabase Auth and add
these redirect URLs:

```text
http://localhost:3000/auth/callback
https://your-production-domain/auth/callback
```

Apply `supabase/migrations/20260724090000_create_portfolios.sql` to the
Supabase project before using cloud sync. The migration creates the
`public.portfolios` table and enables RLS so authenticated users can only
access their own portfolios.

---

### Step 3 — Choose how you want to run the app

Riskfolio can be run two ways — pick whichever suits you, then follow
**only that section** below from top to bottom. Each option is fully
self-contained and lists everything it needs, including any tool
installs — you don't need to read the other option first.

- **Option A — Docker Compose (recommended):** one command, one
  terminal. Docker installs and manages all dependencies internally, so
  this is the fastest path to a running app.
- **Option B — Manual (two terminals):** runs the backend and frontend
  directly on your machine, outside Docker. More visibility into each
  service individually — useful if you're actively developing or
  debugging one side.

If you've already set up one option and want to try the other, that's
completely fine — see the note under Option A for why there's no
conflict either way.

---

## Running the App

### Option A — Docker Compose (recommended)

**Prerequisite:** Docker Desktop only.

Download from https://www.docker.com/products/docker-desktop/ and
install it like any desktop application.

**You do NOT need `uv`, Node.js, or `pnpm` installed on your machine for
this option** — Docker installs all backend and frontend dependencies
inside its own containers automatically, via the `RUN uv sync` and
`RUN pnpm install` steps already baked into `backend/Dockerfile` and
`frontend/Dockerfile`.

> **Already ran Option B's setup on your machine? No conflict.** The
> backend Dockerfile installs packages to `/usr/local` inside the
> container (not `/app/.venv`), so a host-side `.venv` is simply
> unused. The frontend's `docker-compose.yml` uses dedicated named
> volumes for `node_modules` and `.next`, which take priority over your
> host folders — so the container always uses its own Linux-native
> `node_modules`, never whatever's on your host. Either order is safe.

Make sure Docker Desktop is open and running, then from the repo root:

```bash
docker compose up --build
```

This starts the frontend on port `3000` and backend on port `8000`. Open
`http://localhost:3000` in your browser when the services are ready.

To stop the stack:
```bash
docker compose down
```

---

### Option B — Manual (two terminals)

**Prerequisites:** `uv`, Node.js 22, and `pnpm`, installed directly on
your machine (these are installed once and used across all your
projects, not just this one).

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

**Backend setup.** Run these from the `backend/` directory:

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

**Frontend setup:**
```bash
cd frontend
pnpm install
```

---

**Now run both services.** Open two terminal windows simultaneously and
run one command in each.

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

By default the frontend calls `/backend/api/v1/...` on its own origin,
matching the Vercel route prefix. In local development, Next rewrites
`/backend/*` to the FastAPI server at `http://localhost:8000/*`.

---

## Verifying the App is Working

These checks work regardless of which option (A or B) you used above —
they're just HTTP requests against the running backend, however it was
started.

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
| `GET` | `/` | Root health check. Returns `{"status": "ok"}` to confirm the server is running |
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/historical-prices?tickers=AAPL&period=5d` | Fetch historical prices |
| `POST` | `/api/v1/analyze` | Monte Carlo VaR analysis |
| `POST` | `/api/v1/optimize` | MPT Efficient Frontier optimization (Monte Carlo cloud + exact analytical frontier via SLSQP) |
| `POST` | `/api/v1/monte-carlo-paths` | Simulated portfolio price paths over time |
| `POST` | `/api/v1/stress-test` | Baseline vs. shocked VaR/CVaR under a hypothetical scenario |

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
Returns both `frontier_points` (the Monte Carlo cloud) and
`analytical_frontier_curve` (the exact frontier via `scipy.optimize`,
same shape) so both can be plotted on the same chart. Also returns
`portfolio_value` and `holdings` (today's value and per-ticker detail,
computed from live prices), plus `share_targets` on every portfolio
point (Max Sharpe, Min Vol, and Current Portfolio) — a ready-to-render
buy/sell breakdown per ticker (`target_shares`, `current_shares`,
`delta_shares`), so the frontend never has to convert weight
percentages into share counts itself.

**Example `/api/v1/stress-test` payload:**
```json
{
  "holdings": [
    { "ticker": "AAPL", "quantity": 10 },
    { "ticker": "MSFT", "quantity": 5 }
  ],
  "price_shocks": { "AAPL": -0.15 },
  "volatility_multiplier": 1.5
}
```
Returns `baseline` (unshocked) and `shocked` (scenario applied) VaR/CVaR
results, identically shaped, for direct side-by-side comparison.

---

## Running Tests

These commands run directly on your machine, not inside Docker — they
require Option B's local `uv`/`pnpm` setup, even if you're running the
actual app via Option A (Docker Compose).

```bash
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Frontend checks:
```bash
cd frontend
pnpm exec tsc --noEmit
pnpm run build
```

---

## Running the Engines Standalone

These also run directly on your machine, not inside Docker — same
requirement as "Running Tests" above: Option B's local `uv` setup, even
if you're running the actual app via Option A (Docker Compose).

Each engine can be run directly for development and debugging, printing a
full human-readable report.

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

**Stress test engine:**
```bash
cd backend
uv run python -m app.engine.stress_test
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
| Modular Architecture | Monte Carlo, MPT, and Stress Test engines strictly decoupled from the FastAPI layer |
| Test-Driven Development (TDD) | 124-test Pytest suite (hand-written + Hypothesis property-based tests) covering all three engines, API endpoints, and data pipeline |
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
