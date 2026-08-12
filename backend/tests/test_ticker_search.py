from __future__ import annotations

import asyncio

import httpx

from app.engine import data
from app.main import app


async def _request(method: str, url: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, url, **kwargs)


def test_search_ticker_symbols_normalizes_yahoo_results(monkeypatch):
    calls = []

    class FakeSearch:
        def __init__(self, query: str, **kwargs):
            calls.append({"query": query, "kwargs": kwargs})
            self.quotes = [
                {
                    "symbol": "d05.si",
                    "shortname": "DBS Group Holdings Ltd",
                    "exchDisp": "Singapore",
                    "quoteType": "EQUITY",
                    "typeDisp": "Equity",
                    "currency": "sgd",
                },
                {
                    "symbol": "^n225",
                    "shortname": "Nikkei 225",
                    "exchDisp": "Osaka",
                    "quoteType": "INDEX",
                    "typeDisp": "Index",
                    "currency": "jpy",
                },
                {
                    "symbol": "IGNORED",
                    "shortname": "Ignored Option",
                    "quoteType": "OPTION",
                },
                {
                    "symbol": "D05.SI",
                    "shortname": "Duplicate DBS",
                    "quoteType": "EQUITY",
                },
            ]

    data._SYMBOL_SEARCH_CACHE.clear()
    monkeypatch.setattr("app.engine.data.yf.Search", FakeSearch)

    results = data.search_ticker_symbols("  dbs   group  ", limit=5)

    assert calls == [
        {
            "query": "dbs group",
            "kwargs": {
                "max_results": 5,
                "news_count": 0,
                "lists_count": 0,
                "include_cb": False,
                "include_nav_links": False,
                "include_research": False,
                "include_cultural_assets": False,
                "enable_fuzzy_query": True,
                "recommended": 0,
                "timeout": 8,
                "raise_errors": False,
            },
        }
    ]
    assert results == [
        {
            "symbol": "D05.SI",
            "name": "DBS Group Holdings Ltd",
            "exchange": "Singapore",
            "quoteType": "EQUITY",
            "typeDisp": "Equity",
            "currency": "SGD",
        },
        {
            "symbol": "^N225",
            "name": "Nikkei 225",
            "exchange": "Osaka",
            "quoteType": "INDEX",
            "typeDisp": "Index",
            "currency": "JPY",
        },
    ]


def test_search_ticker_symbols_uses_short_lived_cache(monkeypatch):
    calls = 0

    class FakeSearch:
        def __init__(self, _query: str, **_kwargs):
            nonlocal calls
            calls += 1
            self.quotes = [{"symbol": "AAPL", "shortname": "Apple Inc."}]

    data._SYMBOL_SEARCH_CACHE.clear()
    monkeypatch.setattr("app.engine.data.yf.Search", FakeSearch)

    first_results = data.search_ticker_symbols("apple", limit=8)
    second_results = data.search_ticker_symbols("apple", limit=8)

    assert first_results == second_results
    assert calls == 1


def test_ticker_search_route(monkeypatch):
    calls = []

    def fake_search_ticker_symbols(query: str, limit: int = 8):
        calls.append({"query": query, "limit": limit})
        return [
            {
                "symbol": "D05.SI",
                "name": "DBS Group Holdings Ltd",
                "exchange": "Singapore",
                "quoteType": "EQUITY",
                "typeDisp": "Equity",
                "currency": "SGD",
            }
        ]

    monkeypatch.setattr("app.main.search_ticker_symbols", fake_search_ticker_symbols)

    response = asyncio.run(
        _request("GET", "/api/v1/ticker-search?q=%20DBS%20%20Group%20&limit=3")
    )

    assert response.status_code == 200
    assert calls == [{"query": "DBS Group", "limit": 3}]
    assert response.json() == {
        "query": "DBS Group",
        "results": [
            {
                "symbol": "D05.SI",
                "name": "DBS Group Holdings Ltd",
                "exchange": "Singapore",
                "quoteType": "EQUITY",
                "typeDisp": "Equity",
                "currency": "SGD",
            }
        ],
    }
