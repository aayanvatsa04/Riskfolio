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
