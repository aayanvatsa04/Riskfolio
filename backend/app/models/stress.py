from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.common import HoldingRequest


class StressTestRequest(BaseModel):
    """
    Request body for POST /api/v1/stress-test.

    Combines the same holdings format as /api/v1/analyze with two
    independent kinds of shock — see stress_test.py's module docstring
    for the full reasoning behind this split:
        - price_shocks: per-ticker, instantaneous, "this already happened"
        - volatility_multiplier: portfolio-wide, forward-looking,
          "expect more/less turbulence from here"
    """

    holdings: list[HoldingRequest] = Field(
        ...,
        description='Portfolio holdings, for example [{"ticker": "AAPL", "quantity": 10}].',
        min_length=1,
        max_length=20,
    )
    price_shocks: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Per-ticker instantaneous price shock, e.g. {'AAPL': -0.15} "
            "means AAPL's position instantly loses 15% of its value. "
            "Tickers not included default to 0.0 (no shock). Each value "
            "must be strictly greater than -1.0 — a position cannot lose "
            "100% or more of its value in a single shock."
        ),
    )
    volatility_multiplier: float = Field(
        default=1.0,
        gt=0,
        le=5.0,
        description=(
            "Multiplier applied to historical volatility (standard "
            "deviation) for the SHOCKED simulation only — the baseline "
            "always uses unmodified historical volatility. 1.0 = no "
            "change, 2.0 = twice as volatile going forward. Same "
            "convention as the Monte Carlo Price Paths chart's "
            "volatility_multiplier."
        ),
    )
    horizon: int = Field(
        default=1,
        description="Risk horizon in trading days. Supported values: 1, 5, or 22.",
    )
    confidence_level: float = Field(default=0.95, gt=0, lt=1)
    n_simulations: int = Field(default=10_000, ge=100, le=1_000_000)

    @field_validator("price_shocks")
    @classmethod
    def validate_price_shocks(cls, value: dict[str, float]) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for ticker, shock in value.items():
            if not math.isfinite(shock):
                raise ValueError(f"Price shock for {ticker} must be finite")
            if shock <= -1.0:
                raise ValueError(
                    f"Price shock for {ticker} must be greater than -1.0 "
                    "(a position cannot lose 100% or more of its value)"
                )
            normalized[ticker.strip().upper()] = shock
        return normalized

    @field_validator("horizon")
    @classmethod
    def validate_horizon(cls, horizon: int) -> int:
        if horizon not in {1, 5, 22}:
            raise ValueError("Horizon must be 1, 5, or 22 trading days")
        return horizon

    @field_validator("confidence_level")
    @classmethod
    def validate_confidence_level(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Confidence level must be finite")
        return value


class StressScenarioResult(BaseModel):
    """
    One side of the baseline/shocked comparison. Both "baseline" and
    "shocked" in StressTestResponse use this EXACT same shape
    deliberately, so the frontend can render either side through one
    shared component rather than special-casing each one.
    """

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
    portfolio_value: float
    portfolio_weights: dict[str, float]


class ShocksApplied(BaseModel):
    """Echoes back exactly which scenario was simulated, so the frontend
    doesn't need to keep its own copy of what the user requested."""

    price_shocks: dict[str, float]
    volatility_multiplier: float


class StressTestTimingBreakdown(BaseModel):
    data_fetch_s: float
    log_returns_s: float
    statistics_s: float
    baseline_simulation_s: float
    shocked_simulation_s: float
    total_s: float


class StressTestResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tickers: list[str]
    baseline: StressScenarioResult
    shocked: StressScenarioResult
    shocks_applied: ShocksApplied
    timing: StressTestTimingBreakdown | dict[str, Any]
