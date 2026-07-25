from __future__ import annotations

import math
from typing import Annotated

import pandas as pd
import yfinance as yf
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

SHARE_TARGET_TOLERANCE = 1e-4


def _read_yfinance_value(source: object, key: str) -> object:
    if isinstance(source, dict):
        return source.get(key)

    value = getattr(source, key, None)
    if value is not None:
        return value

    if hasattr(source, "get"):
        try:
            return source.get(key)
        except Exception:
            return None

    return None


def _get_quote_currency(ticker: str) -> str | None:
    """
    Best-effort yfinance metadata lookup.

    yfinance metadata can be unavailable or slow for otherwise valid symbols,
    so callers should treat None as "unknown" instead of invalid.
    """
    try:
        fast_info = yf.Ticker(ticker).fast_info
    except Exception:
        return None

    raw_currency = _read_yfinance_value(fast_info, "currency")

    if not isinstance(raw_currency, str):
        return None

    currency = raw_currency.strip().upper()
    return currency or None


def _get_ticker_metadata(ticker: str) -> dict:
    metadata: dict[str, str | None] = {
        "name": None,
        "currency": None,
        "exchange": None,
    }
    ticker_client = None

    try:
        ticker_client = yf.Ticker(ticker)
        fast_info = ticker_client.fast_info
    except Exception:
        fast_info = None

    if fast_info is not None:
        raw_currency = _read_yfinance_value(fast_info, "currency")
        if isinstance(raw_currency, str) and raw_currency.strip():
            metadata["currency"] = raw_currency.strip().upper()

        raw_exchange = _read_yfinance_value(fast_info, "exchange")
        if isinstance(raw_exchange, str) and raw_exchange.strip():
            metadata["exchange"] = raw_exchange.strip()

    info = {}
    if ticker_client is not None:
        try:
            info = ticker_client.get_info()
        except Exception:
            try:
                info = ticker_client.info
            except Exception:
                info = {}

    if isinstance(info, dict):
        for name_key in ("shortName", "longName", "displayName"):
            raw_name = info.get(name_key)
            if isinstance(raw_name, str) and raw_name.strip():
                metadata["name"] = raw_name.strip()
                break

        raw_currency = info.get("currency")
        if metadata["currency"] is None and isinstance(raw_currency, str):
            metadata["currency"] = raw_currency.strip().upper() or None

        raw_exchange = info.get("exchange")
        if metadata["exchange"] is None and isinstance(raw_exchange, str):
            metadata["exchange"] = raw_exchange.strip() or None

    return metadata


def _build_ticker_metadata(tickers: list[str]) -> dict[str, dict]:
    return {ticker: _get_ticker_metadata(ticker) for ticker in tickers}


def _validate_usd_quoted_tickers(tickers: list[str]) -> None:
    non_usd: dict[str, str] = {}

    for ticker in tickers:
        currency = _get_quote_currency(ticker)
        if currency is not None and currency != "USD":
            non_usd[ticker] = currency

    if non_usd:
        details = ", ".join(
            f"{ticker} ({currency})" for ticker, currency in sorted(non_usd.items())
        )
        raise ValueError(
            "Riskfolio currently supports USD-quoted tickers only. "
            f"Confirmed non-USD ticker(s): {details}."
        )


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
    _validate_usd_quoted_tickers(tickers)
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


def _build_share_targets(
    target_weights: dict[str, float] | None,
    valuations: list[dict],
    portfolio_value: float,
) -> dict:
    shares: dict[str, dict] = {}
    normalized_target_weights = target_weights or {}

    for valuation in valuations:
        ticker = valuation["ticker"]
        latest_price = float(valuation["latest_price"])
        current_shares = float(valuation["quantity"])
        current_weight = float(valuation["weight"])
        target_weight = float(normalized_target_weights.get(ticker, 0.0))
        target_shares = (
            (portfolio_value * target_weight) / latest_price
            if latest_price > 0
            else 0.0
        )
        share_delta = target_shares - current_shares

        if abs(share_delta) <= SHARE_TARGET_TOLERANCE:
            action = "already_correct"
            shares_to_trade = 0.0
        elif share_delta > 0:
            action = "buy"
            shares_to_trade = share_delta
        else:
            action = "sell"
            shares_to_trade = abs(share_delta)

        shares[ticker] = {
            "action": action,
            "current_shares": current_shares,
            "target_shares": target_shares,
            "delta_shares": share_delta,
            "shares_to_trade": shares_to_trade,
            "latest_price": latest_price,
            "current_weight": current_weight,
            "target_weight": target_weight,
            "target_value": portfolio_value * target_weight,
        }

    return {
        "portfolio_value": portfolio_value,
        "shares": shares,
    }


def _attach_share_targets(
    optimization_result: dict,
    valuations: list[dict],
    portfolio_value: float,
) -> dict:
    for key in (
        "max_sharpe_portfolio",
        "min_vol_portfolio",
        "current_portfolio",
    ):
        portfolio = optimization_result.get(key)
        if not isinstance(portfolio, dict):
            continue

        weights = portfolio.get("weights")
        portfolio["share_targets"] = _build_share_targets(
            weights if isinstance(weights, dict) else None,
            valuations,
            portfolio_value,
        )

    return optimization_result


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
    include_metadata: Annotated[
        bool,
        Query(description="Include ticker name, currency, and exchange metadata."),
    ] = False,
) -> dict:
    normalized_tickers = _normalize_tickers(tickers)
    if period not in ALLOWED_PERIODS:
        allowed = ", ".join(sorted(ALLOWED_PERIODS))
        raise HTTPException(status_code=422, detail=f"Period must be one of: {allowed}")

    try:
        _validate_usd_quoted_tickers(normalized_tickers)
        prices = fetch_historical_prices(normalized_tickers, period=period)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to fetch historical prices: {exc}",
        ) from exc

    response = {
        "tickers": normalized_tickers,
        "period": period,
        "rows": _serialize_prices(prices),
    }

    if include_metadata:
        response["metadata"] = _build_ticker_metadata(normalized_tickers)

    return response


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
        portfolio_weights, portfolio_value, holdings = _build_weighted_portfolio(
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
        result = run_mpt_optimization(
            tickers=list(portfolio_weights.keys()),
            current_weights=portfolio_weights,
            n_portfolios=request.n_portfolios,
            risk_free_rate=request.risk_free_rate,
            verbose=False,
        )

        # Enrich with today's portfolio value and per-ticker holdings detail
        # (same shape as /analyze's response) so a consumer can compute an
        # ACTIONABLE target -- e.g. "buy 3 more shares of AAPL" -- rather
        # than only ever seeing target weights as bare percentages.
        result["portfolio_value"] = portfolio_value
        result["holdings"] = holdings

        return _attach_share_targets(result, holdings, portfolio_value)

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
