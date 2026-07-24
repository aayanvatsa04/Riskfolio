from __future__ import annotations

import asyncio

import httpx
import pandas as pd

from app.engine import monte_carlo_var
from app.main import app


async def _request(method: str, url: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, url, **kwargs)


def test_historical_prices_returns_serialized_price_rows(monkeypatch):
    calls = []

    def fake_fetch_historical_prices(
        tickers: list[str], period: str = "5y"
    ) -> pd.DataFrame:
        calls.append({"tickers": tickers, "period": period})
        return pd.DataFrame(
            {"AAPL": [190.5, 191.25], "TSLA": [250.0, 252.75]},
            index=pd.to_datetime(["2026-05-28", "2026-05-29"]),
        )

    monkeypatch.setattr(
        "app.main.fetch_historical_prices", fake_fetch_historical_prices
    )

    response = asyncio.run(
        _request("GET", "/api/v1/historical-prices?tickers=aapl,TSLA&period=1y")
    )

    assert response.status_code == 200
    assert response.json() == {
        "tickers": ["AAPL", "TSLA"],
        "period": "1y",
        "rows": [
            {"date": "2026-05-28", "prices": {"AAPL": 190.5, "TSLA": 250.0}},
            {"date": "2026-05-29", "prices": {"AAPL": 191.25, "TSLA": 252.75}},
        ],
    }
    assert calls == [{"tickers": ["AAPL", "TSLA"], "period": "1y"}]


def test_historical_prices_rejects_invalid_period():
    response = asyncio.run(
        _request("GET", "/api/v1/historical-prices?tickers=AAPL&period=bad")
    )

    assert response.status_code == 422


def test_unversioned_historical_prices_route_is_not_registered():
    response = asyncio.run(_request("GET", "/historical-prices?tickers=AAPL"))

    assert response.status_code == 404


def test_fetch_historical_prices_downloads_multiple_tickers(monkeypatch):
    downloaded_prices = pd.DataFrame(
        {
            "AAPL": [100.0, 101.0],
            "TSLA": [50.0, 51.0],
        },
        index=pd.to_datetime(["2026-06-25", "2026-06-26"]),
    )

    def fake_download(tickers, period="5y", auto_adjust=True, progress=False):
        assert tickers == ["AAPL", "TSLA"]
        assert period == "1y"
        assert auto_adjust is True
        assert progress is False
        return pd.concat({"Close": downloaded_prices}, axis=1)

    monkeypatch.setattr("app.engine.monte_carlo_var.yf.download", fake_download)

    prices = monte_carlo_var.fetch_historical_prices(["AAPL", "TSLA"], period="1y")

    pd.testing.assert_frame_equal(prices, downloaded_prices)


def test_fetch_historical_prices_downloads_single_ticker(monkeypatch):
    def fake_download(tickers, period="5y", auto_adjust=True, progress=False):
        assert tickers == ["AAPL"]
        assert period == "5d"
        assert auto_adjust is True
        assert progress is False
        return pd.DataFrame(
            {"Close": [190.5, 191.25]},
            index=pd.to_datetime(["2026-05-28", "2026-05-29"]),
        )

    monkeypatch.setattr("app.engine.monte_carlo_var.yf.download", fake_download)

    prices = monte_carlo_var.fetch_historical_prices(["AAPL"], period="5d")

    expected = pd.DataFrame(
        {"AAPL": [190.5, 191.25]},
        index=pd.to_datetime(["2026-05-28", "2026-05-29"]),
    )
    pd.testing.assert_frame_equal(prices, expected)
