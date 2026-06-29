from __future__ import annotations

import math

from pydantic import BaseModel, Field, field_validator


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


class HealthResponse(BaseModel):
    status: str
