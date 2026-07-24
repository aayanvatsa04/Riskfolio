from __future__ import annotations

import math
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.engine.monte_carlo_var import (
    fetch_historical_prices,
    run_price_path_analysis,
    run_var_analysis,
)
from app.engine.mpt_optimizer import run_mpt_optimization
from app.engine.stress_test import run_stress_test_analysis
from app.models import (
    HealthResponse,
    HoldingRequest,
    MonteCarloPathRequest,
    MonteCarloPathResponse,
    OptimizeRequest,
    OptimizeResponse,
    PortfolioRequest,
    StressTestRequest,
    StressTestResponse,
    VaRResponse,
)
from app.settings import settings

app = FastAPI(
    title="Riskfolio API",
    version="0.1.0",
    description="FastAPI wrapper for the Riskfolio Monte Carlo VaR engine.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        settings.NEXT_PUBLIC_ORIGIN,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_v1 = APIRouter(prefix="/api/v1")

ALLOWED_PERIODS = {
    "1d",
    "5d",
    "1mo",
    "3mo",
    "6mo",
    "1y",
    "2y",
    "5y",
    "10y",
    "ytd",
    "max",
}


def _combine_holdings(holdings: list[HoldingRequest]) -> dict[str, float]:
    quantities: dict[str, float] = {}

    for holding in holdings:
        quantities[holding.ticker] = (
            quantities.get(holding.ticker, 0.0) + holding.quantity
        )

    return quantities


def _latest_price_row(prices: pd.DataFrame) -> pd.Series:
    if prices.empty:
        raise ValueError("No recent price data found for the requested tickers")
    return prices.iloc[-1]


def _build_weighted_portfolio(
    holdings: list[HoldingRequest],
) -> tuple[dict[str, float], float, list[dict]]:
    quantities = _combine_holdings(holdings)
    tickers = list(quantities)
    latest_prices = _latest_price_row(fetch_historical_prices(tickers, period="5d"))

    valuations: list[dict] = []
    portfolio_value = 0.0

    for ticker, quantity in quantities.items():
        raw_price = latest_prices.get(ticker)
        if raw_price is None:
            raise ValueError(f"No recent price data found for {ticker}")

        latest_price = float(raw_price)
        if not math.isfinite(latest_price) or latest_price <= 0:
            raise ValueError(f"No valid latest price found for {ticker}")

        market_value = quantity * latest_price
        portfolio_value += market_value
        valuations.append(
            {
                "ticker": ticker,
                "quantity": quantity,
                "latest_price": latest_price,
                "market_value": market_value,
            }
        )

    if not math.isfinite(portfolio_value) or portfolio_value <= 0:
        raise ValueError("Calculated portfolio value must be positive")

    portfolio_weights: dict[str, float] = {}
    for valuation in valuations:
        weight = valuation["market_value"] / portfolio_value
        valuation["weight"] = weight
        portfolio_weights[valuation["ticker"]] = weight

    return portfolio_weights, portfolio_value, valuations


def _normalize_tickers(raw_tickers: list[str]) -> list[str]:
    tickers: list[str] = []

    for raw_ticker in raw_tickers:
        for part in raw_ticker.split(","):
            ticker = part.strip().upper()
            if ticker and ticker not in tickers:
                tickers.append(ticker)

    if not tickers:
        raise HTTPException(status_code=422, detail="At least one ticker is required")
    if len(tickers) > 20:
        raise HTTPException(status_code=422, detail="At most 20 tickers are allowed")

    return tickers


def _serialize_prices(prices: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []

    for index, row in prices.iterrows():
        date = index.strftime("%Y-%m-%d") if hasattr(index, "strftime") else str(index)
        rows.append(
            {
                "date": date,
                "prices": {
                    ticker: None if pd.isna(value) else float(value)
                    for ticker, value in row.items()
                },
            }
        )

    return rows


@app.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    return HealthResponse(status="ok")


@api_v1.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@api_v1.post("/analyze", response_model=VaRResponse)
async def analyze_portfolio(request: PortfolioRequest) -> dict:
    try:
        portfolio, portfolio_value, holdings = _build_weighted_portfolio(
            request.holdings
        )
        return run_var_analysis(
            portfolio=portfolio,
            portfolio_value=portfolio_value,
            horizon=request.horizon,
            confidence_level=request.confidence_level,
            n_simulations=request.n_simulations,
            verbose=False,
        ) | {
            "portfolio_value": portfolio_value,
            "portfolio_weights": portfolio,
            "holdings": holdings,
        }
    except (AssertionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to complete VaR analysis: {exc}",
        ) from exc


@api_v1.post("/monte-carlo-paths", response_model=MonteCarloPathResponse)
async def monte_carlo_paths(request: MonteCarloPathRequest) -> dict:
    try:
        portfolio, portfolio_value, _holdings = _build_weighted_portfolio(
            request.holdings
        )
        return run_price_path_analysis(
            portfolio=portfolio,
            portfolio_value=portfolio_value,
            horizon=request.horizon,
            n_paths=request.n_paths,
            volatility_multiplier=request.volatility_multiplier,
        )
    except (AssertionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to complete Monte Carlo path simulation: {exc}",
        ) from exc


@api_v1.get("/historical-prices")
async def historical_prices(
    tickers: Annotated[
        list[str],
        Query(
            min_length=1,
            description="Ticker symbols. Repeat the parameter or pass comma-separated values.",
        ),
    ],
    period: Annotated[
        str, Query(description="yfinance period, defaulting to 5y.")
    ] = "5y",
) -> dict:
    normalized_tickers = _normalize_tickers(tickers)
    if period not in ALLOWED_PERIODS:
        allowed = ", ".join(sorted(ALLOWED_PERIODS))
        raise HTTPException(status_code=422, detail=f"Period must be one of: {allowed}")

    try:
        prices = fetch_historical_prices(normalized_tickers, period=period)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to fetch historical prices: {exc}",
        ) from exc

    return {
        "tickers": normalized_tickers,
        "period": period,
        "rows": _serialize_prices(prices),
    }


@api_v1.post("/optimize", response_model=OptimizeResponse)
async def optimize_portfolio(request: OptimizeRequest) -> dict:
    """
    POST /api/v1/optimize

    Runs the MPT Efficient Frontier optimization for a given portfolio.

    WHAT THIS ENDPOINT DOES:
        1. Receives holdings (ticker + quantity pairs) and optimizer settings
        2. Calls _build_weighted_portfolio() to convert quantities to weights
           using live market prices — same helper used by /analyze
        3. Validates that at least 2 distinct tickers exist after deduplication
           (two holdings of AAPL still = 1 ticker after _combine_holdings())
        4. Calls run_mpt_optimization() with verbose=False
        5. Returns the full OptimizeResponse JSON

    REQUEST BODY:  OptimizeRequest  (validated by Pydantic before this runs)
    RESPONSE BODY: OptimizeResponse

    ERROR RESPONSES:
        422 Unprocessable Entity — invalid holdings, or duplicate tickers that
            reduce to fewer than 2 after _combine_holdings() deduplication
        500 Internal Server Error — unexpected failure (e.g. yfinance down,
            ticker not found, numpy error)
    """
    try:
        # Reuse the exact same helper that /analyze uses to convert
        # (ticker, quantity) pairs into portfolio weights via live prices.
        # _portfolio_value and _holdings are not needed by the optimizer
        # (it only uses weights), so we prefix them with _ to signal that.
        portfolio_weights, _portfolio_value, _holdings = _build_weighted_portfolio(
            request.holdings
        )

        # After _combine_holdings() merges duplicate tickers, we might end up
        # with fewer unique tickers than holdings. E.g. two AAPL holdings → one
        # AAPL entry. Pydantic enforced min_length=2 on the holdings list, but
        # that checks the number of HoldingRequest objects, not unique tickers.
        # This check covers that edge case.
        if len(portfolio_weights) < 2:
            raise ValueError(
                "At least 2 distinct tickers are required for optimisation. "
                "Your holdings resolve to only 1 unique ticker after deduplication."
            )

        # Run the full MPT pipeline. verbose=False suppresses all print output —
        # the endpoint returns only the clean results dict as JSON.
        return run_mpt_optimization(
            tickers=list(portfolio_weights.keys()),
            current_weights=portfolio_weights,
            n_portfolios=request.n_portfolios,
            risk_free_rate=request.risk_free_rate,
            verbose=False,
        )

    except (AssertionError, ValueError) as exc:
        # AssertionError: from engine internal assertions (e.g. weight sum check)
        # ValueError: from our validation above or _build_weighted_portfolio
        # Both are user-caused input problems → 422 Unprocessable Entity
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    except Exception as exc:
        # Anything else (yfinance network error, numpy failure, etc.) is an
        # unexpected server-side problem → 500 Internal Server Error
        raise HTTPException(
            status_code=500,
            detail=f"Unable to complete portfolio optimisation: {exc}",
        ) from exc


@api_v1.post("/stress-test", response_model=StressTestResponse)
async def stress_test_portfolio(request: StressTestRequest) -> dict:
    """
    POST /api/v1/stress-test

    Runs the SAME Monte Carlo VaR analysis twice for this portfolio: once
    unshocked (baseline) and once with the requested price shocks and/or
    volatility multiplier applied (shocked) — so the two can be compared
    side by side.

    WHAT THIS ENDPOINT DOES:
        1. Receives holdings (ticker + quantity pairs), per-ticker price
           shocks, a volatility multiplier, and the usual VaR settings
        2. Calls _build_weighted_portfolio() to convert quantities to
           weights using live market prices — same helper used by
           /analyze and /optimize, so "today's portfolio value" means
           exactly the same thing across all three endpoints
        3. Calls run_stress_test_analysis(), which internally re-runs the
           existing VaR engine's Monte Carlo simulation twice (baseline
           and shocked) on identical historical data
        4. Returns both results plus an echo of the exact scenario that
           was simulated

    REQUEST BODY:  StressTestRequest  (validated by Pydantic before this runs)
    RESPONSE BODY: StressTestResponse — "baseline" and "shocked" are
        IDENTICALLY SHAPED, so the frontend can render both sides of the
        comparison through the same component.

    ERROR RESPONSES:
        422 Unprocessable Entity — invalid holdings, or price shocks that
            (combined) reduce the portfolio to zero or negative value
        500 Internal Server Error — unexpected failure (e.g. yfinance
            down, ticker not found, numpy error)
    """
    try:
        # Reuse the exact same helper /analyze and /optimize use to
        # convert (ticker, quantity) pairs into portfolio weights via
        # live prices — this keeps "today's portfolio value" consistent
        # across every endpoint in the API.
        portfolio_weights, portfolio_value, _holdings = _build_weighted_portfolio(
            request.holdings
        )

        return run_stress_test_analysis(
            portfolio=portfolio_weights,
            portfolio_value=portfolio_value,
            price_shocks=request.price_shocks,
            volatility_multiplier=request.volatility_multiplier,
            horizon=request.horizon,
            confidence_level=request.confidence_level,
            n_simulations=request.n_simulations,
            verbose=False,
        )

    except (AssertionError, ValueError) as exc:
        # AssertionError: from engine internal assertions (e.g. weight
        # sum check). ValueError: from apply_price_shocks() when combined
        # shocks reduce the portfolio to zero/negative value, from the
        # volatility_multiplier guard, or from _build_weighted_portfolio.
        # All are user-caused input problems -> 422 Unprocessable Entity.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    except Exception as exc:
        # Anything else (yfinance network error, numpy failure, etc.) is
        # an unexpected server-side problem -> 500 Internal Server Error
        raise HTTPException(
            status_code=500,
            detail=f"Unable to complete stress test: {exc}",
        ) from exc


app.include_router(api_v1)
