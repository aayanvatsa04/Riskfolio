from __future__ import annotations

import asyncio

import httpx
import pandas as pd

from app.main import app


async def _request(method: str, url: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, url, **kwargs)


def _engine_response() -> dict:
    return {
        "var": -523.12,
        "var_positive": 523.12,
        "cvar": -701.45,
        "cvar_positive": 701.45,
        "mean_pnl": 42.3,
        "std_pnl": 380.12,
        "worst_case": -3201.22,
        "best_case": 2103.55,
        "confidence_level": 0.95,
        "n_simulations": 10_000,
        "timing": {
            "data_fetch_s": 2.31,
            "log_returns_s": 0.002,
            "statistics_s": 0.001,
            "monte_carlo_s": 0.018,
            "var_calculation_s": 0.001,
            "total_s": 2.33,
        },
    }


def test_health_check():
    response = asyncio.run(_request("GET", "/api/v1/health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_calls_engine_with_validated_payload(monkeypatch):
    fetch_calls = []
    engine_calls = []

    def fake_fetch_historical_prices(
        tickers: list[str], period: str = "5y"
    ) -> pd.DataFrame:
        fetch_calls.append({"tickers": tickers, "period": period})
        return pd.DataFrame(
            {"AAPL": [100.0], "TSLA": [50.0], "GOOGL": [200.0]},
            index=pd.to_datetime(["2026-05-29"]),
        )

    def fake_run_var_analysis(**kwargs):
        engine_calls.append(kwargs)
        return _engine_response()

    monkeypatch.setattr(
        "app.main.fetch_historical_prices", fake_fetch_historical_prices
    )
    monkeypatch.setattr("app.main.run_var_analysis", fake_run_var_analysis)

    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/analyze",
            json={
                "holdings": [
                    {"ticker": "aapl", "quantity": 40},
                    {"ticker": "TSLA", "quantity": 60},
                    {"ticker": "GOOGL", "quantity": 15},
                ],
                "horizon": 1,
                "confidence_level": 0.95,
                "n_simulations": 10_000,
            },
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert body["var_positive"] == 523.12
    assert body["portfolio_value"] == 10_000.0
    assert body["portfolio_weights"] == {"AAPL": 0.4, "TSLA": 0.3, "GOOGL": 0.3}
    assert body["holdings"] == [
        {
            "ticker": "AAPL",
            "quantity": 40.0,
            "latest_price": 100.0,
            "market_value": 4000.0,
            "weight": 0.4,
        },
        {
            "ticker": "TSLA",
            "quantity": 60.0,
            "latest_price": 50.0,
            "market_value": 3000.0,
            "weight": 0.3,
        },
        {
            "ticker": "GOOGL",
            "quantity": 15.0,
            "latest_price": 200.0,
            "market_value": 3000.0,
            "weight": 0.3,
        },
    ]
    assert fetch_calls == [{"tickers": ["AAPL", "TSLA", "GOOGL"], "period": "5d"}]
    assert engine_calls == [
        {
            "portfolio": {"AAPL": 0.4, "TSLA": 0.3, "GOOGL": 0.3},
            "portfolio_value": 10_000.0,
            "horizon": 1,
            "confidence_level": 0.95,
            "n_simulations": 10_000,
            "verbose": False,
        }
    ]


def test_analyze_rejects_invalid_quantity():
    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/analyze",
            json={
                "holdings": [{"ticker": "AAPL", "quantity": 0}],
            },
        )
    )

    assert response.status_code == 422


def test_analyze_rejects_invalid_horizon():
    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/analyze",
            json={
                "holdings": [{"ticker": "AAPL", "quantity": 10}],
                "horizon": 10,
            },
        )
    )

    assert response.status_code == 422


def test_analyze_reports_engine_failures(monkeypatch):
    def fake_fetch_historical_prices(_tickers, period="5y"):
        return pd.DataFrame(
            {"AAPL": [100.0]},
            index=pd.to_datetime(["2026-05-29"]),
        )

    def fake_run_var_analysis(**_kwargs):
        raise RuntimeError("market data unavailable")

    monkeypatch.setattr(
        "app.main.fetch_historical_prices", fake_fetch_historical_prices
    )
    monkeypatch.setattr("app.main.run_var_analysis", fake_run_var_analysis)

    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/analyze",
            json={
                "holdings": [{"ticker": "AAPL", "quantity": 10}],
            },
        )
    )

    assert response.status_code == 500
    assert "market data unavailable" in response.json()["detail"]


def test_monte_carlo_paths_calls_engine_with_slider_payload(monkeypatch):
    fetch_calls = []
    engine_calls = []

    def fake_fetch_historical_prices(
        tickers: list[str], period: str = "5y"
    ) -> pd.DataFrame:
        fetch_calls.append({"tickers": tickers, "period": period})
        return pd.DataFrame(
            {"AAPL": [100.0], "MSFT": [200.0]},
            index=pd.to_datetime(["2026-05-29"]),
        )

    def fake_run_price_path_analysis(**kwargs):
        engine_calls.append(kwargs)
        return {
            "horizon": kwargs["horizon"],
            "n_paths": kwargs["n_paths"],
            "volatility_multiplier": kwargs["volatility_multiplier"],
            "portfolio_value": kwargs["portfolio_value"],
            "portfolio_weights": kwargs["portfolio"],
            "summary": [
                {
                    "day": 0,
                    "mean": 2000.0,
                    "p05": 2000.0,
                    "p50": 2000.0,
                    "p95": 2000.0,
                },
                {
                    "day": 1,
                    "mean": 2010.0,
                    "p05": 1900.0,
                    "p50": 2005.0,
                    "p95": 2125.0,
                },
            ],
            "paths": [
                {
                    "path_id": 1,
                    "points": [
                        {"day": 0, "value": 2000.0},
                        {"day": 1, "value": 2010.0},
                    ],
                }
            ],
            "timing": {"total_s": 0.01},
        }

    monkeypatch.setattr(
        "app.main.fetch_historical_prices", fake_fetch_historical_prices
    )
    monkeypatch.setattr(
        "app.main.run_price_path_analysis", fake_run_price_path_analysis
    )

    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/monte-carlo-paths",
            json={
                "holdings": [
                    {"ticker": "aapl", "quantity": 10},
                    {"ticker": "MSFT", "quantity": 5},
                ],
                "horizon": 45,
                "n_paths": 80,
                "volatility_multiplier": 1.35,
            },
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert body["horizon"] == 45
    assert body["n_paths"] == 80
    assert body["volatility_multiplier"] == 1.35
    assert body["portfolio_value"] == 2000.0
    assert body["summary"][1]["p95"] == 2125.0
    assert fetch_calls == [{"tickers": ["AAPL", "MSFT"], "period": "5d"}]
    assert engine_calls == [
        {
            "portfolio": {"AAPL": 0.5, "MSFT": 0.5},
            "portfolio_value": 2000.0,
            "horizon": 45,
            "n_paths": 80,
            "volatility_multiplier": 1.35,
        }
    ]


def test_unversioned_analyze_route_is_not_registered():
    response = asyncio.run(
        _request(
            "POST",
            "/analyze",
            json={"holdings": [{"ticker": "AAPL", "quantity": 10}]},
        )
    )

    assert response.status_code == 404
