from __future__ import annotations

import math
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.engine.monte_carlo_var import fetch_historical_prices, run_var_analysis
from app.models import HealthResponse, HoldingRequest, PortfolioRequest, VaRResponse

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


app.include_router(api_v1)
