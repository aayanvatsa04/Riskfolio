from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.common import HoldingRequest, HoldingValuation


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
