from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HoldingRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, ticker: str) -> str:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("Ticker cannot be empty")
        return normalized

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, quantity: float) -> float:
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Quantity must be a positive number")
        return quantity


class HoldingValuation(BaseModel):
    ticker: str
    quantity: float
    latest_price: float
    market_value: float
    weight: float


class PortfolioRequest(BaseModel):
    holdings: list[HoldingRequest] = Field(
        ...,
        description='Portfolio holdings, for example [{"ticker": "AAPL", "quantity": 10}].',
        min_length=1,
        max_length=20,
    )
    horizon: int = Field(
        default=22,
        description="Risk horizon in trading days. Supported values: 1, 5, or 22.",
    )
    confidence_level: float = Field(default=0.95, gt=0, lt=1)
    n_simulations: int = Field(default=10_000, ge=100, le=1_000_000)

    @field_validator("confidence_level")
    @classmethod
    def validate_finite_float(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Value must be finite")
        return value

    @field_validator("horizon")
    @classmethod
    def validate_horizon(cls, horizon: int) -> int:
        if horizon not in {1, 5, 22}:
            raise ValueError("Horizon must be 1, 5, or 22 trading days")
        return horizon


class TimingBreakdown(BaseModel):
    data_fetch_s: float
    log_returns_s: float
    statistics_s: float
    monte_carlo_s: float
    var_calculation_s: float
    total_s: float


class VaRResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    var: float
    var_positive: float
    cvar: float
    cvar_positive: float
    mean_pnl: float
    std_pnl: float
    worst_case: float
    best_case: float
    confidence_level: float
    n_simulations: int
    timing: TimingBreakdown | dict[str, Any]
    portfolio_value: float | None = None
    portfolio_weights: dict[str, float] | None = None
    holdings: list[HoldingValuation] | None = None


class HealthResponse(BaseModel):
    status: str


# ────────────────────────────────────────────────────────────────
# MPT OPTIMIZER MODELS
# ────────────────────────────────────────────────────────────────
# These models mirror the structure returned by run_mpt_optimization().
# FastAPI uses them to:
#   1. Validate the incoming request (OptimizeRequest)
#   2. Serialize and document the outgoing response (OptimizeResponse)
#
# The same design principle as the VaR models applies: all validation
# happens here at the API boundary, before the engine is ever called.
# ─────────────────────────────────────────────────────────────────────────────


class PortfolioPoint(BaseModel):
    """
    Annualised statistics for a single specific portfolio.

    Used three times in OptimizeResponse:
        - max_sharpe_portfolio: the portfolio with the highest Sharpe ratio
        - min_vol_portfolio:    the portfolio with the lowest annual volatility
        - current_portfolio:    the user's actual current allocation

    All return/volatility values are annualised decimals, not percentages.
    The frontend multiplies by 100 for display (e.g. 0.182 → "18.2%").
    """

    # Annual expected return as a decimal, e.g. 0.182 means 18.2% per year.
    # Can be negative for assets with a negative historical mean return.
    expected_return: float

    # Annual volatility (standard deviation of returns) as a decimal,
    # e.g. 0.241 means 24.1% per year. Always non-negative.
    volatility: float

    # Sharpe ratio: (expected_return - risk_free_rate) / volatility.
    # Measures return earned per unit of risk taken.
    # Higher is better. Negative Sharpe means the portfolio underperforms
    # the risk-free rate (e.g. US Treasuries).
    sharpe: float

    # Optional weight allocation dict, e.g. {"AAPL": 0.71, "TSLA": 0.29}.
    # Present for max_sharpe_portfolio, min_vol_portfolio, and current_portfolio
    # (all three include weights so the frontend can show allocation bars).
    # None for frontier_points — those are just dots on the chart.
    weights: dict[str, float] | None = None


class FrontierPoint(BaseModel):
    """
    A single simulated portfolio on the Efficient Frontier scatter chart.

    These are the gray dots in the background of the chart. Unlike
    PortfolioPoint, frontier points do NOT include weights — they are
    only used for plotting the cloud shape, not for displaying allocations.

    Up to 1,000 of these are returned per API response (sampled from
    the full n_portfolios simulation for a reasonable JSON payload size).
    """

    # Annual expected return as a decimal, e.g. 0.155 = 15.5% per year
    expected_return: float

    # Annual volatility as a decimal, e.g. 0.198 = 19.8% per year
    volatility: float

    # Sharpe ratio, used by the frontend to colour dots by quality
    # (higher Sharpe dots could be shown warmer/brighter if desired)
    sharpe: float


class OptimizeRequest(BaseModel):
    """
    Incoming request body for POST /api/v1/optimize.

    Mirrors PortfolioRequest (used for VaR analysis) but with two
    differences:
        1. min_length=2: optimization requires at least 2 distinct tickers —
           you cannot construct an Efficient Frontier with a single asset.
        2. Two optimizer-specific fields: n_portfolios and risk_free_rate.
    """

    holdings: list[HoldingRequest] = Field(
        ...,
        description=(
            "Portfolio holdings as ticker + quantity pairs. "
            "At least 2 distinct tickers are required. "
            'Example: [{"ticker": "AAPL", "quantity": 10}, '
            '{"ticker": "TSLA", "quantity": 5}]'
        ),
        min_length=2,  # Pydantic enforces this — a 422 is returned if only 1 holding
        max_length=20,  # Same cap as VaR analysis — prevents abuse
    )

    n_portfolios: int = Field(
        default=5_000,
        ge=500,  # Minimum 500 — fewer than this gives a sparse, misleading frontier
        le=50_000,  # Maximum 50,000 — above this the JSON payload becomes large
        description=(
            "Number of random portfolios to simulate for the Efficient Frontier. "
            "More portfolios = smoother frontier but slower response. "
            "5,000 is the recommended default."
        ),
    )

    risk_free_rate: float = Field(
        default=0.05,
        ge=0.0,  # Cannot be negative — a negative risk-free rate is nonsensical here
        lt=1.0,  # Must be less than 100% — a rate above 1.0 would be extraordinary
        description=(
            "Annualised risk-free rate used in the Sharpe ratio denominator. "
            "Default 0.05 = 5%, approximating the US 10-year Treasury yield."
        ),
    )

    @field_validator("risk_free_rate")
    @classmethod
    def validate_finite_rate(cls, value: float) -> float:
        """Reject NaN or Infinity — both would silently corrupt Sharpe calculations."""
        if not math.isfinite(value):
            raise ValueError("Risk-free rate must be a finite number")
        return value


class OptimizeTimingBreakdown(BaseModel):
    """
    Per-stage runtime breakdown for a single optimization request.

    Mirrors TimingBreakdown used in VaRResponse but with an
    optimization_s field instead of monte_carlo_s and var_calculation_s,
    since the optimizer has a different pipeline structure.
    """

    data_fetch_s: float  # Time to fetch 5 years of prices from yfinance
    log_returns_s: float  # Time to compute daily log returns
    statistics_s: float  # Time to compute μ, Σ, and annualise them
    optimization_s: float  # Time to simulate all n_portfolios (the vectorized step)
    total_s: float  # Wall-clock time for the entire endpoint


class OptimizeResponse(BaseModel):
    """
    Full response body for POST /api/v1/optimize.

    Contains everything the frontend needs to render:
        1. The Efficient Frontier scatter chart (frontier_points)
        2. The three annotated optimal portfolios (max Sharpe, min vol, current)
        3. Metadata echoed back for display (risk_free_rate, n_portfolios)
        4. Timing breakdown for debugging/performance monitoring

    model_config = ConfigDict(extra="ignore") means if the engine ever
    returns extra keys in its dict (e.g. during development), Pydantic
    silently ignores them rather than raising a validation error.
    """

    model_config = ConfigDict(extra="ignore")

    # The list of ticker symbols that were optimised, e.g. ["AAPL", "TSLA", "GOOGL"]
    tickers: list[str]

    # The scatter cloud — up to 1,000 sampled portfolios for the chart background.
    # Each FrontierPoint is one gray dot on the Efficient Frontier chart.
    frontier_points: list[FrontierPoint]

    # The portfolio with the highest Sharpe ratio among all simulations.
    # This is the mathematically optimal portfolio — best return per unit of risk.
    # Includes the exact weight allocation so the user knows how to rebalance.
    max_sharpe_portfolio: PortfolioPoint

    # The portfolio with the lowest annual volatility among all simulations.
    # This is the safest allocation — minimises swings regardless of return.
    # Includes the exact weight allocation.
    min_vol_portfolio: PortfolioPoint

    # The user's current portfolio, plotted on the frontier for comparison.
    # If this dot sits inside the cloud (not on the frontier boundary),
    # the user could improve their risk-return profile by rebalancing.
    current_portfolio: PortfolioPoint

    # Echoed back from the request so the frontend can display it.
    # e.g. "Risk-free rate used: 5.0%"
    risk_free_rate: float

    # Echoed back from the request so the frontend can display it.
    # e.g. "5,000 portfolios simulated"
    n_portfolios: int

    # Per-stage runtime breakdown. Accepts either the typed breakdown model
    # or a plain dict — the engine returns a plain dict, Pydantic coerces it.
    timing: OptimizeTimingBreakdown | dict[str, Any]
