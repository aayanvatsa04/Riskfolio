from __future__ import annotations

import asyncio

import httpx
import pandas as pd

from app.engine import monte_carlo_var
from app.engine.price_cache import build_supabase_price_cache_from_env
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


def test_supabase_price_cache_uses_server_only_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "service-role-secret")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    cache = build_supabase_price_cache_from_env()

    assert cache is not None
    assert cache.supabase_url == "https://example.supabase.co"
    assert cache.api_key == "service-role-secret"


def test_supabase_price_cache_ignores_anon_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-public-key")
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    assert build_supabase_price_cache_from_env() is None


def test_fetch_historical_prices_uses_supabase_cache(monkeypatch):
    cached_prices = pd.DataFrame(
        {
            "AAPL": [190.5, 191.25],
            "TSLA": [250.0, 252.75],
        },
        index=pd.to_datetime(["2026-06-25", "2026-06-26"]),
    )

    class FakeCache:
        def __init__(self) -> None:
            self.query_calls = []
            self.upsert_calls = []

        def query_prices(self, tickers, start_date=None, end_date=None):
            self.query_calls.append(
                {
                    "tickers": tickers,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )
            return cached_prices

        def upsert_prices(self, prices, source="yfinance"):
            self.upsert_calls.append({"prices": prices, "source": source})

    fake_cache = FakeCache()
    monkeypatch.setattr(monte_carlo_var, "_PRICE_CACHE", fake_cache)

    def fail_download(*_args, **_kwargs):
        raise AssertionError("yfinance should not be called on cache hit")

    monkeypatch.setattr("app.engine.monte_carlo_var.yf.download", fail_download)

    prices = monte_carlo_var.fetch_historical_prices(["AAPL", "TSLA"], period="5d")

    pd.testing.assert_frame_equal(prices, cached_prices)
    assert len(fake_cache.query_calls) == 1
    assert fake_cache.upsert_calls == []


def test_fetch_historical_prices_backfills_supabase_cache(monkeypatch):
    class FakeCache:
        def __init__(self) -> None:
            self.query_calls = []
            self.upsert_calls = []

        def query_prices(self, tickers, start_date=None, end_date=None):
            self.query_calls.append(
                {
                    "tickers": tickers,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )
            return pd.DataFrame()

        def upsert_prices(self, prices, source="yfinance"):
            self.upsert_calls.append({"prices": prices, "source": source})

    fake_cache = FakeCache()
    monkeypatch.setattr(monte_carlo_var, "_PRICE_CACHE", fake_cache)

    def fake_download(tickers, period="5y", auto_adjust=True, progress=False):
        assert tickers == ["AAPL", "TSLA"]
        assert period == "1y"
        assert auto_adjust is True
        assert progress is False
        return pd.DataFrame(
            [[100.0, 50.0], [101.0, 51.0]],
            index=pd.to_datetime(["2026-06-25", "2026-06-26"]),
            columns=pd.MultiIndex.from_product([["Close"], ["AAPL", "TSLA"]]),
        )

    monkeypatch.setattr("app.engine.monte_carlo_var.yf.download", fake_download)

    prices = monte_carlo_var.fetch_historical_prices(["AAPL", "TSLA"], period="1y")

    expected = pd.DataFrame(
        {"AAPL": [100.0, 101.0], "TSLA": [50.0, 51.0]},
        index=pd.to_datetime(["2026-06-25", "2026-06-26"]),
    )

    pd.testing.assert_frame_equal(prices, expected)
    assert len(fake_cache.query_calls) == 1
    assert len(fake_cache.upsert_calls) == 1
    pd.testing.assert_frame_equal(fake_cache.upsert_calls[0]["prices"], expected)
