"""
Shared market-data and return-statistics utilities for Riskfolio engines.

The VaR, MPT optimizer, stress-test, and historical-prices API flows all
start from the same pipeline:

    tickers -> adjusted close prices -> daily log returns -> mu/sigma

Keeping that pipeline here avoids making non-VaR engines depend on
monte_carlo_var.py just to fetch prices or compute shared statistics.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

# This constant governs whether the TOTAL data actually available is
# large enough to compute a statistically meaningful annualised figure.
# A newly-IPO'd ticker with only a handful of real trading days will
# always fail this check, since no cache can manufacture trading history.
# 252 = one full trading year, matching the x252 annualisation factor
# used throughout this engine -- annualising from meaningfully less
# than a year of data is where the x252 multiplication starts amplifying
# sampling noise into wildly unstable annual figures.
MIN_TRADING_DAYS_FOR_ANALYSIS = 252
SYMBOL_SEARCH_CACHE_TTL_SECONDS = 5 * 60
SYMBOL_SEARCH_LIMIT = 25
SEARCHABLE_QUOTE_TYPES = {
    "CRYPTOCURRENCY",
    "ETF",
    "EQUITY",
    "FUTURE",
    "INDEX",
    "MUTUALFUND",
}

_SYMBOL_SEARCH_CACHE: dict[
    tuple[str, int],
    tuple[float, list[dict[str, str | None]]],
] = {}


def _read_yfinance_value(source: object, key: str) -> object:
    if isinstance(source, dict):
        return source.get(key)

    value = getattr(source, key, None)
    if value is not None:
        return value

    if hasattr(source, "get"):
        try:
            return source.get(key)
        except Exception:
            return None

    return None


def _normalize_search_text(value: str) -> str:
    return " ".join(value.strip().split())


def _clean_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    return cleaned or None


def _first_clean_string(source: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        cleaned = _clean_string(source.get(key))
        if cleaned is not None:
            return cleaned

    return None


def _copy_search_results(
    results: list[dict[str, str | None]],
) -> list[dict[str, str | None]]:
    return [result.copy() for result in results]


def _coerce_symbol_search_result(
    quote: object,
) -> dict[str, str | None] | None:
    if not isinstance(quote, dict):
        return None

    symbol = _clean_string(quote.get("symbol"))
    if symbol is None:
        return None

    quote_type = _first_clean_string(quote, ("quoteType", "type"))
    if quote_type is not None and quote_type.upper() not in SEARCHABLE_QUOTE_TYPES:
        return None

    name = _first_clean_string(
        quote,
        ("shortname", "shortName", "longname", "longName", "displayName"),
    )
    exchange = _first_clean_string(quote, ("exchDisp", "exchange"))

    return {
        "symbol": symbol.upper(),
        "name": name,
        "exchange": exchange,
        "quoteType": quote_type.upper() if quote_type is not None else None,
        "typeDisp": _first_clean_string(quote, ("typeDisp",)),
        "currency": _normalize_quote_currency(quote.get("currency")),
    }


def search_ticker_symbols(
    query: str,
    limit: int = 8,
) -> list[dict[str, str | None]]:
    """
    Search Yahoo Finance symbols by company/index name or ticker.

    Yahoo Finance uses exchange-specific symbols such as D05.SI and index
    symbols such as ^N225. Keeping search server-side lets us use Yahoo's own
    symbol universe instead of shipping a static, stale list to the browser.
    """
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        return []

    bounded_limit = max(1, min(limit, SYMBOL_SEARCH_LIMIT))
    cache_key = (normalized_query.casefold(), bounded_limit)
    now = time.monotonic()
    cached = _SYMBOL_SEARCH_CACHE.get(cache_key)

    if cached is not None:
        cached_at, cached_results = cached
        if now - cached_at < SYMBOL_SEARCH_CACHE_TTL_SECONDS:
            return _copy_search_results(cached_results)

    search = yf.Search(
        normalized_query,
        max_results=bounded_limit,
        news_count=0,
        lists_count=0,
        include_cb=False,
        include_nav_links=False,
        include_research=False,
        include_cultural_assets=False,
        enable_fuzzy_query=True,
        recommended=0,
        timeout=8,
        raise_errors=False,
    )

    results: list[dict[str, str | None]] = []
    seen_symbols: set[str] = set()
    for quote in search.quotes:
        result = _coerce_symbol_search_result(quote)
        if result is None:
            continue

        symbol = result["symbol"]
        if symbol is None or symbol in seen_symbols:
            continue

        seen_symbols.add(symbol)
        results.append(result)

    _SYMBOL_SEARCH_CACHE[cache_key] = (now, _copy_search_results(results))
    return results


def _normalize_quote_currency(raw_currency: object) -> str | None:
    if not isinstance(raw_currency, str):
        return None

    currency = raw_currency.strip()
    if not currency:
        return None
    if currency.islower() or currency.isupper():
        return currency.upper()
    return currency


def get_quote_currency(ticker: str) -> str | None:
    """
    Best-effort yfinance quote-currency lookup.

    yfinance exposes `currency` through Ticker.fast_info and get_info().
    Return None when Yahoo metadata is unavailable; callers decide whether
    an unknown currency is acceptable for their workflow.
    """
    try:
        ticker_client = yf.Ticker(ticker)
    except Exception:
        return None

    try:
        fast_info = ticker_client.fast_info
    except Exception:
        fast_info = None

    if fast_info is not None:
        currency = _normalize_quote_currency(
            _read_yfinance_value(fast_info, "currency")
        )
        if currency is not None:
            return currency

    try:
        info = ticker_client.get_info()
    except Exception:
        try:
            info = ticker_client.info
        except Exception:
            info = {}

    if isinstance(info, dict):
        return _normalize_quote_currency(info.get("currency"))

    return None


def get_ticker_metadata(ticker: str) -> dict[str, str | None]:
    metadata: dict[str, str | None] = {
        "name": None,
        "currency": None,
        "exchange": None,
    }
    ticker_client = None

    try:
        ticker_client = yf.Ticker(ticker)
        fast_info = ticker_client.fast_info
    except Exception:
        fast_info = None

    if fast_info is not None:
        raw_currency = _read_yfinance_value(fast_info, "currency")
        currency = _normalize_quote_currency(raw_currency)
        if currency is not None:
            metadata["currency"] = currency

        raw_exchange = _read_yfinance_value(fast_info, "exchange")
        if isinstance(raw_exchange, str) and raw_exchange.strip():
            metadata["exchange"] = raw_exchange.strip()

    info = {}
    if ticker_client is not None:
        try:
            info = ticker_client.get_info()
        except Exception:
            try:
                info = ticker_client.info
            except Exception:
                info = {}

    if isinstance(info, dict):
        for name_key in ("shortName", "longName", "displayName"):
            raw_name = info.get(name_key)
            if isinstance(raw_name, str) and raw_name.strip():
                metadata["name"] = raw_name.strip()
                break

        if metadata["currency"] is None:
            metadata["currency"] = _normalize_quote_currency(info.get("currency"))

        raw_exchange = info.get("exchange")
        if metadata["exchange"] is None and isinstance(raw_exchange, str):
            metadata["exchange"] = raw_exchange.strip() or None

    return metadata


def fetch_historical_prices(tickers: list[str], period: str = "5y") -> pd.DataFrame:
    """
    Download adjusted daily closing prices for a list of tickers.

    Returns a DataFrame where:
        - Each column is a ticker, e.g. "AAPL" or "TSLA"
        - Each row is a trading day
        - Values are adjusted closing prices
    """
    print(f"\nFetching {period} historical data for: {tickers}...")

    raw_data = yf.download(tickers, period=period, auto_adjust=True, progress=False)

    if len(tickers) == 1:
        prices = raw_data[["Close"]]
        prices.columns = tickers
    else:
        prices = raw_data["Close"]

    # Capture each ticker's own coverage before joint dropna(). If one ticker
    # is newly listed, the joint result can be truncated for every ticker; this
    # lets the error name the actual thin ticker.
    per_ticker_counts = prices.count()

    prices = prices.dropna()

    # Only meaningful for period="5y", the analysis-grade period used by the
    # risk engines. Shorter periods are also used by the historical-prices API
    # for quick price lookups, where this guard should not apply.
    if period == "5y" and len(prices) < MIN_TRADING_DAYS_FOR_ANALYSIS:
        thin_tickers = [
            ticker
            for ticker in tickers
            if per_ticker_counts.get(ticker, 0) < MIN_TRADING_DAYS_FOR_ANALYSIS
        ]
        if thin_tickers:
            names = ", ".join(thin_tickers)
            plural = "s" if len(thin_tickers) > 1 else ""
            raise ValueError(
                f"Insufficient historical data: {names} "
                f"{'have' if len(thin_tickers) > 1 else 'has'} fewer than "
                f"{MIN_TRADING_DAYS_FOR_ANALYSIS} trading days of price "
                f"history (likely a recent IPO or newly-listed ticker{plural}). "
                f"At least {MIN_TRADING_DAYS_FOR_ANALYSIS} trading days "
                "(roughly one year) are required to compute statistically "
                "meaningful annualised risk and return figures. Try "
                "removing this ticker or waiting for more trading history "
                "to accumulate."
            )

        raise ValueError(
            f"Insufficient overlapping historical data across {', '.join(tickers)}: "
            f"only {len(prices)} trading days are common to all tickers, but at "
            f"least {MIN_TRADING_DAYS_FOR_ANALYSIS} are required."
        )

    print(f"Retrieved {len(prices)} trading days of data.\n")
    return prices


def compute_log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Convert daily prices into daily log returns.

    Log return formula:
        r_t = ln(P_t / P_{t-1})

    In pandas, .pct_change() gives simple returns (P_t/P_{t-1} - 1).
    np.log(1 + simple_return) converts those to log returns.
    """
    log_returns = np.log(1 + prices.pct_change())
    return log_returns.dropna()


def compute_statistics(log_returns: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Extract mean daily log returns and the daily covariance matrix.

    Returns:
        Tuple of (mu, sigma), where mu has shape (n_assets,) and sigma has
        shape (n_assets, n_assets).
    """
    mu = log_returns.mean().values
    sigma = log_returns.cov().values
    return mu, sigma
