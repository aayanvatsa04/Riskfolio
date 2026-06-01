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
| Automated Pytest Suite (26 tests) | ✅ Complete |

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
│   ├── tests/
│   │   └── test_engine.py           # Pytest test suite
│   └── requirements.txt
├── frontend/
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
- Python 3.10+
- Node.js 18+

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/Riskfolio.git
cd Riskfolio

# Set up Python virtual environment
cd backend
python3.10 -m venv .venv
source .venv/bin/activate        # Mac/Linux
# or
.venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
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
python -m pytest tests/test_engine.py -v
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
Using frontend: http://localhost:3001
```

The frontend is configured with `NEXT_PUBLIC_API_BASE_URL` from `.env`, so
browser requests call the selected host-mapped backend directly.

The default Compose ports are in `.env`. Copy `.env.example` if you need to
reset or customize local values.

Useful checks:

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/historical-prices?tickers=AAPL&period=5d"
```

Stop the stack with:

```bash
docker compose down
```

If you want a different starting range, set it in `.env` or when starting:

```bash
FRONTEND_PORT_START=3005 ./scripts/compose-up.sh
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

---

## Software Engineering Practices

| Practice | Implementation |
|---|---|
| Modular Architecture | Monte Carlo engine strictly decoupled from FastAPI layer |
| Test-Driven Development (TDD) | Pytest suite with 26 tests covering every engine function |
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
