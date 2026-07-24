from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.common import HoldingRequest, HoldingValuation


class ShareTarget(BaseModel):
    """One ticker's actionable target within a ShareTargetsSummary --
    how many shares to hold, vs. how many are currently held."""

    target_shares: int
    current_shares: int
    # Positive = buy, negative = sell, 0 = already correct.
    delta_shares: int
    # Dollar amount this ticker should hold at the computed
    # suggested_portfolio_value (see ShareTargetsSummary).
    target_value: float


class ShareTargetsSummary(BaseModel):
    """
    Translates a PortfolioPoint's weight percentages into concrete,
    actionable share counts -- see compute_share_targets() in
    mpt_optimizer.py for the full derivation of suggested_portfolio_value.

    Weights alone only fix a RATIO between tickers, not an absolute
    dollar amount -- a portfolio holding twice as much of everything in
    the same ratio has identical return/volatility/Sharpe. This summary
    picks one concrete total (suggested_portfolio_value) chosen to
    require the LEAST total buying/selling from the user's current
    holdings, then reports the resulting per-ticker share targets.
    """

    # The total dollar value this target portfolio is scaled to. Chosen
    # via least-squares projection onto the user's current market values
    # -- NOT necessarily equal to today's total portfolio value.
    suggested_portfolio_value: float
    shares: dict[str, ShareTarget]


class PortfolioPoint(BaseModel):
    expected_return: float
    volatility: float
    sharpe: float
    weights: dict[str, float] | None = None
    # Optional: populated by the /optimize endpoint using the user's
    # actual holdings, so the frontend can show "hold 12 shares
    # (currently 7) -- buy 5" instead of only a bare percentage.
    share_targets: ShareTargetsSummary | None = None


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
    # Today's total portfolio value in USD, computed from live prices at
    # request time (same value used to derive current_portfolio's weights).
    # Combined with each target portfolio's `weights`, this is what lets a
    # consumer compute an ACTIONABLE target: target_value = weight *
    # portfolio_value, then target_shares = target_value / latest_price
    # (see `holdings` below for latest_price per ticker) — without this,
    # a caller only has percentages, not something a retail user can act
    # on directly (e.g. "buy 3 more shares of AAPL").
    portfolio_value: float
    # Per-ticker current quantity, latest live price, market value, and
    # weight — same shape as VaRResponse.holdings (see models/var.py) for
    # consistency across every endpoint. Combined with portfolio_value and
    # any target portfolio's weights above, this gives everything needed
    # to compute a buy/sell share delta without a second API call.
    holdings: list[HoldingValuation]
    timing: OptimizeTimingBreakdown | dict[str, Any]
