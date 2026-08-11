from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.common import HoldingRequest, HoldingValuation


class ShareTarget(BaseModel):
    action: Literal["buy", "sell", "already_correct"]
    current_shares: float
    target_shares: float
    delta_shares: float
    shares_to_trade: float
    latest_price: float
    current_weight: float
    target_weight: float
    target_value: float


class ShareTargets(BaseModel):
    portfolio_value: float
    portfolio_currency: str | None = None
    shares: dict[str, ShareTarget]


class PortfolioPoint(BaseModel):
    expected_return: float
    volatility: float
    sharpe: float
    weights: dict[str, float] | None = None
    share_targets: ShareTargets | None = None


class FrontierPoint(BaseModel):
    expected_return: float
    volatility: float
    sharpe: float


class OptimizeRequest(BaseModel):
    holdings: list[HoldingRequest] = Field(
        ...,
        description=(
            "Portfolio holdings as ticker + quantity pairs. "
            "At least 2 distinct tickers are required."
        ),
        min_length=2,
        max_length=20,
    )
    n_portfolios: int = Field(
        default=5_000,
        ge=500,
        le=50_000,
        description="Number of random portfolios to simulate.",
    )
    risk_free_rate: float = Field(
        default=0.05,
        ge=0.0,
        lt=1.0,
        description="Annualised risk-free rate used in the Sharpe ratio.",
    )

    @field_validator("risk_free_rate")
    @classmethod
    def validate_finite_rate(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Risk-free rate must be a finite number")
        return value


class OptimizeTimingBreakdown(BaseModel):
    data_fetch_s: float
    log_returns_s: float
    statistics_s: float
    optimization_s: float
    # Time spent solving the scipy.optimize (SLSQP) sweep that produces the
    # exact analytical frontier curve, separate from optimization_s (which
    # times the Monte Carlo weight-sampling cloud only).
    analytical_frontier_s: float
    total_s: float


class OptimizeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tickers: list[str]
    # The Monte Carlo cloud: up to 1,000 randomly-sampled feasible portfolios.
    frontier_points: list[FrontierPoint]
    # The EXACT Efficient Frontier: up to 50 points tracing the true
    # minimum-variance boundary, computed via scipy.optimize (SLSQP) in
    # compute_analytical_frontier(). Same shape as frontier_points so the
    # frontend can render both as series on the same chart — the Monte
    # Carlo cloud's upper-left edge should visually hug this curve, which
    # doubles as a live correctness check on the sampling approach.
    analytical_frontier_curve: list[FrontierPoint]
    max_sharpe_portfolio: PortfolioPoint
    min_vol_portfolio: PortfolioPoint
    current_portfolio: PortfolioPoint
    risk_free_rate: float
    n_portfolios: int
    # Today's total portfolio value in the shared quote currency, computed
    # from live prices at request time (same value used to derive current_portfolio's weights).
    # Combined with each target portfolio's `weights`, this is what lets a
    # consumer compute an ACTIONABLE target: target_value = weight *
    # portfolio_value, then target_shares = target_value / latest_price
    # (see `holdings` below for latest_price per ticker) — without this,
    # a caller only has percentages, not something a retail user can act
    # on directly (e.g. "buy 3 more shares of AAPL").
    portfolio_value: float
    portfolio_currency: str | None = None
    # Per-ticker current quantity, latest live price, market value, and
    # weight — same shape as VaRResponse.holdings (see models/var.py) for
    # consistency across every endpoint. Combined with portfolio_value and
    # any target portfolio's weights above, this gives everything needed
    # to compute a buy/sell share delta without a second API call.
    holdings: list[HoldingValuation]
    timing: OptimizeTimingBreakdown | dict[str, Any]
