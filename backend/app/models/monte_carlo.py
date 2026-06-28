from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.common import HoldingRequest


class MonteCarloPathRequest(BaseModel):
    holdings: list[HoldingRequest] = Field(
        ...,
        description="Portfolio holdings used to simulate forward value paths.",
        min_length=1,
        max_length=20,
    )
    horizon: int = Field(
        default=22,
        ge=1,
        le=252,
        description="Forward simulation horizon in trading days.",
    )
    n_paths: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Number of Monte Carlo paths to simulate and return.",
    )
    volatility_multiplier: float = Field(
        default=1.0,
        ge=0.1,
        le=3.0,
        description="Multiplier applied to historical covariance-driven volatility.",
    )

    @field_validator("volatility_multiplier")
    @classmethod
    def validate_volatility_multiplier(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Volatility multiplier must be finite")
        return value


class MonteCarloPathPoint(BaseModel):
    day: int
    value: float


class MonteCarloSummaryPoint(BaseModel):
    day: int
    mean: float
    p05: float
    p50: float
    p95: float


class MonteCarloSimulationPath(BaseModel):
    path_id: int
    points: list[MonteCarloPathPoint]


class MonteCarloPathResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    horizon: int
    n_paths: int
    volatility_multiplier: float
    portfolio_value: float
    portfolio_weights: dict[str, float]
    summary: list[MonteCarloSummaryPoint]
    paths: list[MonteCarloSimulationPath]
    timing: dict[str, Any]
