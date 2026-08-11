"""
Shared market-data and return-statistics utilities for Riskfolio engines.

The VaR, MPT optimizer, stress-test, and historical-prices API flows all
start from the same pipeline:

    tickers -> adjusted close prices -> daily log returns -> mu/sigma

Keeping that pipeline here avoids making non-VaR engines depend on
monte_carlo_var.py just to fetch prices or compute shared statistics.
"""

from __future__ import annotations

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
