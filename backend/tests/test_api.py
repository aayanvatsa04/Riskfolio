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


def test_stress_test_calls_engine_with_validated_payload(monkeypatch):
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

    def fake_run_stress_test_analysis(**kwargs):
        engine_calls.append(kwargs)
        return {
            "tickers": ["AAPL", "MSFT"],
            "baseline": {
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
                "portfolio_value": kwargs["portfolio_value"],
                "portfolio_weights": kwargs["portfolio"],
            },
            "shocked": {
                "var": -680.0,
                "var_positive": 680.0,
                "cvar": -890.0,
                "cvar_positive": 890.0,
                "mean_pnl": 30.0,
                "std_pnl": 410.0,
                "worst_case": -3500.0,
                "best_case": 2200.0,
                "confidence_level": 0.95,
                "n_simulations": 10_000,
                "portfolio_value": 8500.0,
                "portfolio_weights": {"AAPL": 0.4, "MSFT": 0.6},
            },
            "shocks_applied": {
                "price_shocks": kwargs["price_shocks"],
                "volatility_multiplier": kwargs["volatility_multiplier"],
            },
            "timing": {
                "data_fetch_s": 0.01,
                "log_returns_s": 0.001,
                "statistics_s": 0.001,
                "baseline_simulation_s": 0.01,
                "shocked_simulation_s": 0.01,
                "total_s": 0.032,
            },
        }

    monkeypatch.setattr(
        "app.main.fetch_historical_prices", fake_fetch_historical_prices
    )
    monkeypatch.setattr(
        "app.main.run_stress_test_analysis", fake_run_stress_test_analysis
    )

    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/stress-test",
            json={
                "holdings": [
                    {"ticker": "aapl", "quantity": 10},
                    {"ticker": "MSFT", "quantity": 5},
                ],
                "price_shocks": {"AAPL": -0.15},
                "volatility_multiplier": 1.5,
            },
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert body["baseline"]["portfolio_value"] == 2000.0
    assert body["shocked"]["portfolio_value"] == 8500.0
    assert body["shocks_applied"]["price_shocks"] == {"AAPL": -0.15}
    assert body["shocks_applied"]["volatility_multiplier"] == 1.5
    assert fetch_calls == [{"tickers": ["AAPL", "MSFT"], "period": "5d"}]
    assert engine_calls == [
        {
            "portfolio": {"AAPL": 0.5, "MSFT": 0.5},
            "portfolio_value": 2000.0,
            "price_shocks": {"AAPL": -0.15},
            "volatility_multiplier": 1.5,
            "horizon": 1,
            "confidence_level": 0.95,
            "n_simulations": 10_000,
            "verbose": False,
        }
    ]


def test_stress_test_rejects_price_shock_at_negative_one():
    """A price shock of exactly -1.0 (100% loss) must be rejected at the
    API layer before ever reaching the engine."""
    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/stress-test",
            json={
                "holdings": [{"ticker": "AAPL", "quantity": 10}],
                "price_shocks": {"AAPL": -1.0},
            },
        )
    )

    assert response.status_code == 422


def test_stress_test_rejects_non_positive_volatility_multiplier():
    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/stress-test",
            json={
                "holdings": [{"ticker": "AAPL", "quantity": 10}],
                "volatility_multiplier": 0,
            },
        )
    )

    assert response.status_code == 422


def test_stress_test_reports_engine_failures(monkeypatch):
    def fake_fetch_historical_prices(_tickers, period="5y"):
        return pd.DataFrame(
            {"AAPL": [100.0]},
            index=pd.to_datetime(["2026-05-29"]),
        )

    def fake_run_stress_test_analysis(**_kwargs):
        raise RuntimeError("market data unavailable")

    monkeypatch.setattr(
        "app.main.fetch_historical_prices", fake_fetch_historical_prices
    )
    monkeypatch.setattr(
        "app.main.run_stress_test_analysis", fake_run_stress_test_analysis
    )

    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/stress-test",
            json={"holdings": [{"ticker": "AAPL", "quantity": 10}]},
        )
    )

    assert response.status_code == 500
    assert "market data unavailable" in response.json()["detail"]


def test_optimize_includes_portfolio_value_and_holdings(monkeypatch):
    """
    Regression test for a real gap: /optimize used to compute
    portfolio_value and holdings internally (needed just to derive
    current_portfolio's weights) but discarded both before returning,
    leaving the frontend with only percentage weights -- not enough to
    show a user something actionable like "buy 3 more shares of AAPL".
    This confirms portfolio_value, holdings, AND the derived
    share_targets (actionable buy/sell deltas, computed server-side via
    compute_share_targets()) are all now present in the response.
    """

    def fake_fetch_historical_prices(_tickers, period="5y"):
        return pd.DataFrame(
            {"AAPL": [200.0, 202.0], "MSFT": [300.0, 305.0]},
            index=pd.to_datetime(["2026-05-28", "2026-05-29"]),
        )

    def fake_run_mpt_optimization(**_kwargs):
        return {
            "tickers": ["AAPL", "MSFT"],
            "frontier_points": [],
            "analytical_frontier_curve": [],
            "max_sharpe_portfolio": {
                "expected_return": 0.18,
                "volatility": 0.22,
                "sharpe": 0.59,
                "weights": {"AAPL": 0.7, "MSFT": 0.3},
            },
            "min_vol_portfolio": {
                "expected_return": 0.12,
                "volatility": 0.15,
                "sharpe": 0.47,
                "weights": {"AAPL": 0.4, "MSFT": 0.6},
            },
            "current_portfolio": {
                "expected_return": 0.15,
                "volatility": 0.18,
                "sharpe": 0.5,
                "weights": {"AAPL": 0.6, "MSFT": 0.4},
            },
            "risk_free_rate": 0.05,
            "n_portfolios": 5_000,
            "timing": {
                "data_fetch_s": 0.01,
                "log_returns_s": 0.001,
                "statistics_s": 0.001,
                "optimization_s": 0.01,
                "analytical_frontier_s": 0.05,
                "total_s": 0.072,
            },
        }

    monkeypatch.setattr(
        "app.main.fetch_historical_prices", fake_fetch_historical_prices
    )
    monkeypatch.setattr("app.main.run_mpt_optimization", fake_run_mpt_optimization)

    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/optimize",
            json={
                "holdings": [
                    {"ticker": "AAPL", "quantity": 10},
                    {"ticker": "MSFT", "quantity": 5},
                ]
            },
        )
    )

    assert response.status_code == 200
    body = response.json()

    # portfolio_value must be present and correct: 10*202 + 5*305 = 3545.0
    assert "portfolio_value" in body
    assert body["portfolio_value"] == 3545.0

    # holdings must be present with full per-ticker detail, matching the
    # same shape /analyze already returns.
    assert "holdings" in body
    holdings_by_ticker = {h["ticker"]: h for h in body["holdings"]}
    assert holdings_by_ticker["AAPL"]["quantity"] == 10.0
    assert holdings_by_ticker["AAPL"]["latest_price"] == 202.0
    assert holdings_by_ticker["AAPL"]["market_value"] == 2020.0
    assert holdings_by_ticker["MSFT"]["quantity"] == 5.0
    assert holdings_by_ticker["MSFT"]["latest_price"] == 305.0
    assert holdings_by_ticker["MSFT"]["market_value"] == 1525.0

    # share_targets must be populated on every portfolio point that has
    # weights, using compute_share_targets() server-side -- so the
    # frontend never has to do this math itself.
    max_sharpe_targets = body["max_sharpe_portfolio"]["share_targets"]
    assert max_sharpe_targets is not None
    assert "AAPL" in max_sharpe_targets["shares"]
    assert "MSFT" in max_sharpe_targets["shares"]
    for ticker_result in max_sharpe_targets["shares"].values():
        assert (
            ticker_result["delta_shares"]
            == ticker_result["target_shares"] - ticker_result["current_shares"]
        )

    # Self-consistency for current_portfolio's OWN math (target_shares -
    # current_shares == delta_shares) is checked the same way as above.
    # NOTE: we do NOT assert suggested_portfolio_value == portfolio_value
    # here, since this test's current_portfolio.weights is hand-crafted
    # mock data ({"AAPL": 0.6, "MSFT": 0.4}) that doesn't actually derive
    # from the mocked prices -- that exact self-consistency guarantee
    # (feeding a portfolio its own real weights recovers its own real
    # value) is already rigorously covered at the engine level in
    # test_optimizer.py::TestComputeShareTargets, using weights that
    # genuinely match their holdings.
    current_targets = body["current_portfolio"]["share_targets"]
    assert current_targets is not None
    for ticker_result in current_targets["shares"].values():
        assert (
            ticker_result["delta_shares"]
            == ticker_result["target_shares"] - ticker_result["current_shares"]
        )


def test_unversioned_analyze_route_is_not_registered():
    response = asyncio.run(
        _request(
            "POST",
            "/analyze",
            json={"holdings": [{"ticker": "AAPL", "quantity": 10}]},
        )
    )

    assert response.status_code == 404
