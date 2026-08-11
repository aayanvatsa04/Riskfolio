from __future__ import annotations

import asyncio

import httpx
import pandas as pd
import pytest

from app.engine import data
from app.main import app


async def _request(method: str, url: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, url, **kwargs)


def test_get_quote_currency_reads_fast_info(monkeypatch):
    class FakeTicker:
        fast_info = {"currency": "eur"}

    monkeypatch.setattr("app.engine.data.yf.Ticker", lambda _ticker: FakeTicker())

    assert data.get_quote_currency("BMW.DE") == "EUR"


def test_get_quote_currency_falls_back_to_info(monkeypatch):
    class FakeTicker:
        fast_info = {}

        def get_info(self):
            return {"currency": "JPY"}

    monkeypatch.setattr("app.engine.data.yf.Ticker", lambda _ticker: FakeTicker())

    assert data.get_quote_currency("7203.T") == "JPY"


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

    monkeypatch.setattr("app.engine.data.yf.download", fake_download)

    with pytest.raises(ValueError, match="SPCX"):
        data.fetch_historical_prices(["AAPL", "GOOGL", "SPCX"], period="5y")


def test_fetch_historical_prices_allows_sufficient_history_for_all_tickers(
    monkeypatch,
):
    """Regression check: tickers that all have well over 252 trading days
    must pass through with no error -- the guard should never produce a
    false positive on a normal, well-established portfolio."""
    full_dates = pd.bdate_range(end="2026-07-17", periods=1_260)
    downloaded_prices = pd.DataFrame(
        {
            "AAPL": pd.Series([150.0] * 1_260, index=full_dates),
            "GOOGL": pd.Series([120.0] * 1_260, index=full_dates),
        }
    )

    def fake_download(tickers, period="5y", auto_adjust=True, progress=False):
        return pd.concat({"Close": downloaded_prices}, axis=1)

    monkeypatch.setattr("app.engine.data.yf.download", fake_download)

    prices = data.fetch_historical_prices(["AAPL", "GOOGL"], period="5y")
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

    monkeypatch.setattr("app.engine.data.yf.download", fake_download)

    with pytest.raises(ValueError, match="overlapping historical data"):
        data.fetch_historical_prices(["OLDCO", "NEWCO"], period="5y")


def test_fetch_historical_prices_guard_does_not_apply_to_other_periods(monkeypatch):
    """The stricter analysis-grade guard is scoped to period="5y" only
    (the sole period actually used by the analysis engines). A request
    for a short period (e.g. "5d", used only for quick price lookups)
    must not trigger this check even with few rows."""
    downloaded_prices = pd.DataFrame(
        {"AAPL": [190.5, 191.25, 192.0]},
        index=pd.bdate_range(end="2026-07-17", periods=3),
    )

    def fake_download(tickers, period="5d", auto_adjust=True, progress=False):
        return pd.concat({"Close": downloaded_prices}, axis=1)

    monkeypatch.setattr("app.engine.data.yf.download", fake_download)

    prices = data.fetch_historical_prices(["AAPL"], period="5d")
    assert len(prices) == 3
    calls = []
    monkeypatch.setattr("app.main._get_quote_currency", lambda _ticker: "USD")

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


def test_historical_prices_can_include_ticker_metadata(monkeypatch):
    monkeypatch.setattr("app.main._get_quote_currency", lambda _ticker: "USD")
    monkeypatch.setattr(
        "app.main._get_ticker_metadata",
        lambda ticker: {
            "name": "Apple Inc." if ticker == "AAPL" else "Tesla, Inc.",
            "currency": "USD",
            "exchange": "NMS",
        },
    )

    def fake_fetch_historical_prices(
        tickers: list[str], period: str = "5y"
    ) -> pd.DataFrame:
        return pd.DataFrame(
            {"AAPL": [191.25], "TSLA": [252.75]},
            index=pd.to_datetime(["2026-05-29"]),
        )

    monkeypatch.setattr(
        "app.main.fetch_historical_prices", fake_fetch_historical_prices
    )

    response = asyncio.run(
        _request(
            "GET",
            "/api/v1/historical-prices?tickers=AAPL,TSLA&period=5d&include_metadata=true",
        )
    )

    assert response.status_code == 200
    assert response.json()["metadata"] == {
        "AAPL": {"name": "Apple Inc.", "currency": "USD", "exchange": "NMS"},
        "TSLA": {"name": "Tesla, Inc.", "currency": "USD", "exchange": "NMS"},
    }


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

    monkeypatch.setattr("app.engine.data.yf.download", fake_download)

    prices = data.fetch_historical_prices(["AAPL", "TSLA"], period="1y")

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

    monkeypatch.setattr("app.engine.data.yf.download", fake_download)

    prices = data.fetch_historical_prices(["AAPL"], period="5d")

    expected = pd.DataFrame(
        {"AAPL": [190.5, 191.25]},
        index=pd.to_datetime(["2026-05-28", "2026-05-29"]),
    )
    pd.testing.assert_frame_equal(prices, expected)
