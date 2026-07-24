from __future__ import annotations

import asyncio

import httpx
import pandas as pd
import pytest

from app.engine import monte_carlo_var
from app.engine.price_cache import build_supabase_price_cache_from_env
from app.main import app


async def _request(method: str, url: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, url, **kwargs)


def test_fetch_historical_prices_rejects_ticker_with_insufficient_history(
    monkeypatch,
):
    """
    Regression test for the SPCX scenario: a newly-IPO'd ticker with only
    a handful of real trading days silently truncates the ENTIRE joint
    dataset via dropna() (since dropna() removes any row where ANY
    ticker is missing), producing statistically meaningless annualised
    figures for every ticker in the portfolio, not just the thin one.
    This confirms the guard catches it and names the actual culprit.
    """
    monkeypatch.setattr(monte_carlo_var, "_PRICE_CACHE", None)

    full_dates = pd.bdate_range(end="2026-07-17", periods=1_260)
    recent_dates = full_dates[-6:]  # only 6 real trading days, like a fresh IPO

    downloaded_prices = pd.DataFrame(
        {
            "AAPL": pd.Series([150.0] * 1_260, index=full_dates),
            "GOOGL": pd.Series([120.0] * 1_260, index=full_dates),
            "SPCX": pd.Series(
                [150.0, 160.95, 155.0, 165.0, 158.0, 162.0], index=recent_dates
            ),
        }
    )

    def fake_download(tickers, period="5y", auto_adjust=True, progress=False):
        return pd.concat({"Close": downloaded_prices}, axis=1)

    monkeypatch.setattr("app.engine.monte_carlo_var.yf.download", fake_download)

    with pytest.raises(ValueError, match="SPCX"):
        monte_carlo_var.fetch_historical_prices(["AAPL", "GOOGL", "SPCX"], period="5y")


def test_fetch_historical_prices_allows_sufficient_history_for_all_tickers(
    monkeypatch,
):
    """Regression check: tickers that all have well over 252 trading days
    must pass through with no error -- the guard should never produce a
    false positive on a normal, well-established portfolio."""
    monkeypatch.setattr(monte_carlo_var, "_PRICE_CACHE", None)

    full_dates = pd.bdate_range(end="2026-07-17", periods=1_260)
    downloaded_prices = pd.DataFrame(
        {
            "AAPL": pd.Series([150.0] * 1_260, index=full_dates),
            "GOOGL": pd.Series([120.0] * 1_260, index=full_dates),
        }
    )

    def fake_download(tickers, period="5y", auto_adjust=True, progress=False):
        return pd.concat({"Close": downloaded_prices}, axis=1)

    monkeypatch.setattr("app.engine.monte_carlo_var.yf.download", fake_download)

    prices = monte_carlo_var.fetch_historical_prices(["AAPL", "GOOGL"], period="5y")
    assert len(prices) == 1_260


def test_fetch_historical_prices_rejects_insufficient_overlap_without_naming_wrong_ticker(
    monkeypatch,
):
    """
    Rarer edge case: no SINGLE ticker is individually thin (both have
    >= 252 trading days on their own), but their trading calendars barely
    overlap -- e.g. one ticker's history is entirely before the other's
    began. The guard must still catch this (the joint dropna() result is
    still too short to analyse), but should use the honest "insufficient
    overlap" message rather than incorrectly blaming one specific ticker
    that isn't actually thin on its own.
    """
    monkeypatch.setattr(monte_carlo_var, "_PRICE_CACHE", None)

    # Ticker A: 300 trading days, entirely in 2021.
    # Ticker B: 300 trading days, entirely in 2023 -- no calendar overlap.
    dates_a = pd.bdate_range(start="2021-01-01", periods=300)
    dates_b = pd.bdate_range(start="2023-01-01", periods=300)

    downloaded_prices = pd.DataFrame(
        {
            "OLDCO": pd.Series([100.0] * 300, index=dates_a),
            "NEWCO": pd.Series([50.0] * 300, index=dates_b),
        }
    )

    def fake_download(tickers, period="5y", auto_adjust=True, progress=False):
        return pd.concat({"Close": downloaded_prices}, axis=1)

    monkeypatch.setattr("app.engine.monte_carlo_var.yf.download", fake_download)

    with pytest.raises(ValueError, match="overlapping historical data"):
        monte_carlo_var.fetch_historical_prices(["OLDCO", "NEWCO"], period="5y")


def test_fetch_historical_prices_guard_does_not_apply_to_other_periods(monkeypatch):
    """The stricter analysis-grade guard is scoped to period="5y" only
    (the sole period actually used by the analysis engines). A request
    for a short period (e.g. "5d", used only for quick price lookups)
    must not trigger this check even with few rows."""
    monkeypatch.setattr(monte_carlo_var, "_PRICE_CACHE", None)

    downloaded_prices = pd.DataFrame(
        {"AAPL": [190.5, 191.25, 192.0]},
        index=pd.bdate_range(end="2026-07-17", periods=3),
    )

    def fake_download(tickers, period="5d", auto_adjust=True, progress=False):
        return pd.concat({"Close": downloaded_prices}, axis=1)

    monkeypatch.setattr("app.engine.monte_carlo_var.yf.download", fake_download)

    prices = monte_carlo_var.fetch_historical_prices(["AAPL"], period="5d")
    assert len(prices) == 3
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
    # IMPORTANT: these dates are generated relative to "now" at the moment
    # the test runs, rather than hardcoded to a fixed calendar date.
    #
    # WHY THIS MATTERS: fetch_historical_prices() only treats cached data as
    # "fresh enough to skip yfinance" if the most recent cached trading day
    # is within CACHE_FRESHNESS_DAYS (7 days) of today — see
    # _cache_covers_requested_period() in monte_carlo_var.py. A fixed
    # calendar date (e.g. "2026-06-26") only satisfies that 7-day window
    # for a short time after it's written — once more than 7 real days
    # pass, this test would start failing even though nothing in the
    # actual caching logic changed, purely because the hardcoded date
    # aged out. Anchoring to pd.Timestamp.now() means this test remains
    # correct no matter when it's actually run.
    recent_business_days = pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=4)
    cached_prices = pd.DataFrame(
        {
            "AAPL": [188.0, 189.25, 190.5, 191.25],
            "TSLA": [247.5, 249.0, 250.0, 252.75],
        },
        index=recent_business_days,
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


def test_fetch_historical_prices_refreshes_partial_supabase_cache(monkeypatch):
    cached_prices = pd.DataFrame(
        {
            "AAPL": [190.5, 191.25, 192.0, 193.5, 194.0],
            "TSLA": [250.0, 252.75, 253.0, 254.25, 255.0],
        },
        index=pd.to_datetime(
            [
                "2026-06-22",
                "2026-06-23",
                "2026-06-24",
                "2026-06-25",
                "2026-06-26",
            ]
        ),
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

    downloaded_prices = pd.DataFrame(
        {
            "AAPL": [100.0] * 1_071,
            "TSLA": [50.0] * 1_071,
        },
        index=pd.bdate_range(end="2026-06-26", periods=1_071),
    )

    def fake_download(tickers, period="5y", auto_adjust=True, progress=False):
        assert tickers == ["AAPL", "TSLA"]
        assert period == "5y"
        assert auto_adjust is True
        assert progress is False
        return pd.concat({"Close": downloaded_prices}, axis=1)

    monkeypatch.setattr("app.engine.monte_carlo_var.yf.download", fake_download)

    prices = monte_carlo_var.fetch_historical_prices(["AAPL", "TSLA"], period="5y")

    pd.testing.assert_frame_equal(prices, downloaded_prices)
    assert len(fake_cache.query_calls) == 1
    assert len(fake_cache.upsert_calls) == 1
    pd.testing.assert_frame_equal(
        fake_cache.upsert_calls[0]["prices"], downloaded_prices
    )


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
