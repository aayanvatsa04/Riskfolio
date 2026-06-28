"""
Riskfolio — Monte Carlo VaR Engine (POC v1)
-------------------------------------------------
Given a user's portfolio (tickers + weights + current market value)
and a time horizon, simulate 10,000 price paths by default
(configurable via n_simulations) and compute the portfolio's
Value at Risk (VaR) at 95% confidence.

IMPORTANT — Portfolio Value Definition:
    portfolio_value refers to the CURRENT MARKET VALUE of the portfolio
    — i.e. what your holdings are worth TODAY if you sold everything,
    NOT the amount of cash you originally invested.

    Example: You invested $8,000 six months ago. Your holdings are
    now worth $10,000. You should input $10,000 — because that is
    what is actually at risk going forward. The $8,000 you originally
    paid is irrelevant to your current risk exposure.

    Note: The purchase date of your stocks is also irrelevant for VaR.
    VaR is purely forward-looking — it asks "what could I lose from
    TODAY onwards?" using the statistical behaviour of each stock
    over the past 5 years.

"""

import time

import numpy as np
import pandas as pd
import yfinance as yf

from app.engine.price_cache import SupabasePriceCache

_PRICE_CACHE = SupabasePriceCache()

# ─────────────────────────────────────────────
# SECTION 1: DATA INGESTION
# ─────────────────────────────────────────────


def _price_period_window(
    period: str,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    end_date = pd.Timestamp.now(tz="UTC").normalize()

    if period == "max":
        return None, end_date
    if period == "ytd":
        return pd.Timestamp(year=end_date.year, month=1, day=1), end_date

    offsets = {
        "1d": pd.Timedelta(days=7),
        "5d": pd.Timedelta(days=14),
        "1mo": pd.DateOffset(months=1),
        "3mo": pd.DateOffset(months=3),
        "6mo": pd.DateOffset(months=6),
        "1y": pd.DateOffset(years=1),
        "2y": pd.DateOffset(years=2),
        "5y": pd.DateOffset(years=5),
        "10y": pd.DateOffset(years=10),
    }
    offset = offsets.get(period)
    if offset is None:
        return None, end_date
    return end_date - offset, end_date


def fetch_historical_prices(tickers: list[str], period: str = "5y") -> pd.DataFrame:
    """
    Download adjusted daily closing prices for a list of tickers
    over the last 5 years using yfinance.

    Returns a DataFrame where:
        - Each column is a ticker (e.g. "AAPL", "TSLA")
        - Each row is a trading day
        - Values are the adjusted closing price in USD

    'Adjusted' closing price accounts for stock splits and dividends,
    so it gives a cleaner picture of true price history.
    """
    print(f"\n📥 Fetching 5-year historical data for: {tickers}...")

    if _PRICE_CACHE:
        start_date, end_date = _price_period_window(period)
        try:
            cached_prices = _PRICE_CACHE.query_prices(tickers, start_date, end_date)
            if not cached_prices.empty:
                print(f"✅ Retrieved {len(cached_prices)} cached trading days.\n")
                return cached_prices
        except Exception as exc:
            print(
                f"⚠️ Supabase price cache query failed; falling back to yfinance: {exc}"
            )

    raw_data = yf.download(tickers, period=period, auto_adjust=True, progress=False)

    if len(tickers) == 1:
        prices = raw_data[["Close"]]
        prices.columns = tickers
    else:
        prices = raw_data["Close"]

    prices = prices.dropna()

    if _PRICE_CACHE:
        try:
            _PRICE_CACHE.upsert_prices(prices, source="yfinance")
        except Exception as exc:
            print(f"⚠️ Supabase price cache upsert failed: {exc}")

    print(f"✅ Retrieved {len(prices)} trading days of data.\n")
    return prices


# ─────────────────────────────────────────────
# SECTION 2: LOG RETURNS
# ─────────────────────────────────────────────


def compute_log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Convert daily prices into daily log returns.

    Log return formula:
        r_t = ln(P_t / P_{t-1})

    Which is equivalent to:
        r_t = ln(P_t) - ln(P_{t-1})

    In pandas, .pct_change() gives simple returns (P_t/P_{t-1} - 1).
    We use np.log(1 + simple_return) to convert to log returns,
    which is equivalent to ln(P_t / P_{t-1}).

    Why log returns?
    - Time-additive: 5-day log return = sum of 5 daily log returns
    - Approximately normally distributed (required for GBM)
    - Handles compounding correctly
    """
    log_returns = np.log(1 + prices.pct_change())
    log_returns = log_returns.dropna()
    return log_returns


# ─────────────────────────────────────────────
# SECTION 3: STATISTICAL PARAMETERS
# ─────────────────────────────────────────────


def compute_statistics(log_returns: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Extract the two key statistical parameters from historical log returns:

    1. Mean return vector (mu):
       The average daily log return for each asset.
       Shape: (n_assets,)
       e.g. [0.0008, 0.0012, 0.0005] for 3 stocks

    2. Covariance matrix (sigma):
       Captures how much each pair of assets moves together.
       Shape: (n_assets, n_assets)
       - Diagonal entries = variance of each asset (solo volatility)
       - Off-diagonal entries = covariance between pairs (co-movement)

    The covariance matrix is the heart of multi-asset risk modeling.
    A portfolio of highly correlated stocks is riskier than
    a diversified one — sigma captures all of that.
    """
    mu = log_returns.mean().values
    sigma = log_returns.cov().values
    return mu, sigma


# ─────────────────────────────────────────────
# SECTION 4: CHOLESKY DECOMPOSITION
# ─────────────────────────────────────────────


def cholesky_decomposition(cov_matrix: np.ndarray) -> np.ndarray:
    """
    Decompose the covariance matrix into a lower triangular matrix L
    such that: Sigma = L @ L.T

    This is used to generate CORRELATED random shocks across assets.

    The idea:
    - If you draw independent random numbers Z ~ N(0,1) for each asset,
      they're uncorrelated — unrealistic.
    - Multiplying by L "mixes" them so that the resulting shocks
      have the same correlation structure as the historical data.

    Concretely: correlated_shocks = L @ independent_shocks

    np.linalg.cholesky() performs this decomposition.
    It requires the matrix to be positive semi-definite (which a valid
    covariance matrix always is).
    """
    L = np.linalg.cholesky(cov_matrix)
    return L


# ─────────────────────────────────────────────
# SECTION 5: MONTE CARLO SIMULATION
# ─────────────────────────────────────────────


def run_monte_carlo(
    mu: np.ndarray,
    cov_matrix: np.ndarray,
    weights: np.ndarray,
    portfolio_value: float,
    horizon: int,
    n_simulations: int = 10_000,
) -> np.ndarray:
    """
    Run n_simulations Monte Carlo simulations of portfolio P&L
    over the given time horizon (in trading days).

    VECTORIZED IMPLEMENTATION — no Python for loop.
    All n_simulations simulations are computed simultaneously as matrix
    operations, which NumPy executes in optimized C code.
    This is typically 100x faster than a Python loop.

    GBM Formula (scaled for multi-day horizon):
        simulated_returns = mu * T + (L @ Z) * sqrt(T)

    Where:
        mu       = mean daily log return vector, shape (n_assets,)
                   scaled by horizon T (drift scales linearly with time)
        L        = Cholesky factor of covariance matrix, shape (n_assets, n_assets)
        Z        = matrix of independent standard normal shocks,
                   shape (n_assets, n_simulations)
                   — all n_simulations shocks drawn at once
        sqrt(T)  = volatility scales with square root of time
                   (from Brownian motion theory — uncertainty grows
                   sub-linearly, not proportionally, with time)

    Vectorized steps:
        1. Draw Z: shape (n_assets, n_simulations) — all shocks at once
        2. Correlate: L @ Z -> shape (n_assets, n_simulations)
        3. Add drift: mu_scaled + correlated_shocks * sqrt(T)
        4. Convert log returns -> simple returns: exp(r) - 1
        5. Compute portfolio return: weights dot each column
        6. Scale by portfolio_value -> dollar P&L array

    Returns:
        Array of shape (n_simulations,) — the full P&L distribution.
        Positive values = gains, negative values = losses.
    """
    n_assets = len(mu)
    L = cholesky_decomposition(cov_matrix)

    Z = np.random.standard_normal((n_assets, n_simulations))
    correlated_shocks = L @ Z

    mu_scaled = mu * horizon
    sqrt_horizon = np.sqrt(horizon)
    simulated_log_returns = mu_scaled[:, np.newaxis] + correlated_shocks * sqrt_horizon

    simulated_simple_returns = np.exp(simulated_log_returns) - 1
    portfolio_returns = weights @ simulated_simple_returns
    portfolio_pnl = portfolio_value * portfolio_returns

    return portfolio_pnl


def run_monte_carlo_price_paths(
    mu: np.ndarray,
    cov_matrix: np.ndarray,
    weights: np.ndarray,
    portfolio_value: float,
    horizon: int,
    n_paths: int = 100,
    volatility_multiplier: float = 1.0,
) -> np.ndarray:
    """
    Simulate full portfolio value paths over time for charting.

    Unlike run_monte_carlo(), which returns only the terminal P&L distribution
    used for VaR, this returns the portfolio value at day 0 and every simulated
    trading day through the selected horizon.

    Returns:
        Array of shape (horizon + 1, n_paths), where row 0 is the current
        portfolio value and each column is one simulated path.
    """
    if horizon < 1:
        raise ValueError("Horizon must be at least 1 trading day")
    if n_paths < 1:
        raise ValueError("Number of paths must be positive")
    if not np.isfinite(volatility_multiplier) or volatility_multiplier <= 0:
        raise ValueError("Volatility multiplier must be positive")

    n_assets = len(mu)
    L = cholesky_decomposition(cov_matrix)

    z = np.random.standard_normal((horizon, n_assets, n_paths))
    correlated_shocks = np.einsum("ij,tjn->tin", L, z)
    daily_log_returns = (
        mu[np.newaxis, :, np.newaxis]
        + correlated_shocks * volatility_multiplier
    )

    cumulative_log_returns = np.cumsum(daily_log_returns, axis=0)
    asset_growth = np.exp(cumulative_log_returns)
    portfolio_growth = np.tensordot(weights, asset_growth, axes=(0, 1))
    simulated_values = portfolio_value * portfolio_growth

    initial_values = np.full((1, n_paths), portfolio_value)
    return np.vstack([initial_values, simulated_values])


# ─────────────────────────────────────────────
# SECTION 6: VaR CALCULATION
# ─────────────────────────────────────────────


def calculate_var(portfolio_pnl: np.ndarray, confidence_level: float = 0.95) -> dict:
    """
    Extract Value at Risk (VaR) from the simulated P&L distribution.

    VaR at 95% confidence = the 5th percentile of the P&L distribution.

    Interpretation: "There is a 5% chance of losing MORE than VaR dollars
    over the given time horizon."

    We also compute CVaR (Conditional VaR / Expected Shortfall) —
    the AVERAGE loss in the worst 5% of scenarios.

    Returns a dictionary with VaR, CVaR, and supporting statistics.
    """
    percentile = (1 - confidence_level) * 100

    var = np.percentile(portfolio_pnl, percentile)

    tail_losses = portfolio_pnl[portfolio_pnl <= var]
    cvar = np.mean(tail_losses)

    return {
        "var": var,
        "var_positive": abs(var),
        "cvar": cvar,
        "cvar_positive": abs(cvar),
        "mean_pnl": np.mean(portfolio_pnl),
        "std_pnl": np.std(portfolio_pnl),
        "worst_case": np.min(portfolio_pnl),
        "best_case": np.max(portfolio_pnl),
        "confidence_level": confidence_level,
        "n_simulations": len(portfolio_pnl),
    }


# ─────────────────────────────────────────────
# SECTION 7: PLAIN-ENGLISH OUTPUT
# ─────────────────────────────────────────────


def explain_results(
    results: dict,
    portfolio_value: float,
    horizon: int,
    tickers: list[str],
    weights: list[float],
) -> None:
    """
    Translate the raw VaR numbers into plain English for a retail investor.

    NOTE: Only called when verbose=True in run_var_analysis.
    When called from FastAPI, verbose=False so this is skipped entirely —
    the API returns the raw results dictionary directly to the frontend.
    """
    var_pct = (results["var_positive"] / portfolio_value) * 100
    cvar_pct = (results["cvar_positive"] / portfolio_value) * 100
    horizon_label = {1: "1 day", 5: "1 week (5 days)", 22: "1 month (22 days)"}.get(
        horizon, f"{horizon} trading days"
    )

    print("=" * 60)
    print("📊  PORTFOLIO RISK REPORT — Riskfolio")
    print("=" * 60)

    print("\n💼  YOUR PORTFOLIO")
    print(f"    Current Market Value:  ${portfolio_value:,.2f}")
    print("    (i.e. what your holdings are worth today, not your original investment)")
    for ticker, weight in zip(tickers, weights, strict=False):
        print(f"    {ticker}: {weight * 100:.1f}%  (${portfolio_value * weight:,.2f})")

    print(f"\n⏱️   TIME HORIZON:  {horizon_label}")
    print(f"🎲  SIMULATIONS RUN:  {results['n_simulations']:,}")

    print("\n" + "-" * 60)
    print("⚠️   VALUE AT RISK (VaR) — 95% Confidence")
    print("-" * 60)
    print(f"\n    VaR:  ${results['var_positive']:,.2f}  ({var_pct:.1f}% of portfolio)")
    print(f"""
    📖 What this means (in plain English):
       Over the next {horizon_label}, there is a 5% chance you
       could lose ${results["var_positive"]:,.2f} or MORE from your
       ${portfolio_value:,.2f} portfolio.

       Put another way: in roughly 1 out of every 20 similar
       {horizon_label} periods, you should expect a loss of at
       least this size.

       The other 95% of the time, your loss will be LESS than
       ${results["var_positive"]:,.2f}.
    """)

    print("-" * 60)
    print("🔴  EXPECTED SHORTFALL (CVaR) — Worst-Case Average")
    print("-" * 60)
    print(
        f"\n    CVaR:  ${results['cvar_positive']:,.2f}  ({cvar_pct:.1f}% of portfolio)"
    )
    print(f"""
    📖 What this means (in plain English):
       CVaR answers: "If things DO go badly (that worst 5%),
       how bad does it actually get on average?"

       In those worst-case scenarios, you would lose on average
       ${results["cvar_positive"]:,.2f} — that's {cvar_pct:.1f}% of your portfolio.
    """)

    print("-" * 60)
    print(f"📈  SIMULATION SUMMARY ({results['n_simulations']:,} possible futures)")
    print("-" * 60)
    print(f"    Expected P&L:   ${results['mean_pnl']:+,.2f}")
    print(f"    Best Case:      ${results['best_case']:+,.2f}")
    print(f"    Worst Case:     ${results['worst_case']:+,.2f}")

    print("\n" + "-" * 60)
    print("📚  GLOSSARY (Key Terms Explained)")
    print("-" * 60)
    print("""
    VaR (Value at Risk):
        A threshold loss. "95% VaR of $500" means: you are 95%
        confident your loss won't exceed $500 over this period.

    CVaR (Conditional VaR / Expected Shortfall):
        The average loss in the worst 5% of scenarios. It tells
        you how deep the hole gets when things go wrong.

    Monte Carlo Simulation:
        A technique where we simulate thousands of possible
        futures for your portfolio using historical data and
        randomness — like running the market 10,000 times.

    Portfolio Value (Current Market Value):
        The total worth of your holdings TODAY — what you would
        receive if you sold everything right now. This is what
        is at risk, regardless of what you originally paid or
        when you bought your stocks.

    Confidence Level (95%):
        Means we're covering 95% of outcomes. The remaining
        5% are the "tail risk" — rare but severe events.
    """)
    print("=" * 60)


# ─────────────────────────────────────────────
# MAIN: WIRE EVERYTHING TOGETHER
# ─────────────────────────────────────────────


def run_var_analysis(
    portfolio: dict,  # e.g. {"AAPL": 0.5, "TSLA": 0.3, "GOOGL": 0.2}
    portfolio_value: float,  # CURRENT MARKET VALUE in USD (what holdings are
    # worth TODAY, not original investment)
    horizon: int = 1,  # trading days: 1, 5, or 22
    confidence_level: float = 0.95,
    n_simulations: int = 10_000,
    verbose: bool = True,  # True  = print full human-readable report (default)
    # False = silent, return dict only (use for FastAPI)
) -> dict:
    """
    Full end-to-end pipeline:
        Portfolio input -> Data fetch -> Log returns -> Statistics
        -> Monte Carlo -> VaR -> results dict

    Args:
        portfolio:         Dict of ticker -> weight. Weights must sum to 1.0.
        portfolio_value:   Current market value of holdings in USD today.
        horizon:           Time horizon in trading days (1, 5, or 22).
        confidence_level:  VaR confidence level (default 0.95 = 95%).
        n_simulations:     Number of Monte Carlo simulations (default 10,000).
        verbose:           If True, prints full plain-English report and timing.
                           Set to False when calling from FastAPI — the raw
                           results dict is returned either way.

    Returns:
        dict with keys: var, var_positive, cvar, cvar_positive, mean_pnl,
                        std_pnl, worst_case, best_case, confidence_level,
                        n_simulations, timing
    """
    tickers = list(portfolio.keys())
    weights = np.array(list(portfolio.values()))

    assert abs(weights.sum() - 1.0) < 1e-6, "Portfolio weights must sum to 1.0"

    total_start = time.perf_counter()

    t0 = time.perf_counter()
    prices = fetch_historical_prices(tickers)
    t_fetch = time.perf_counter() - t0

    t0 = time.perf_counter()
    log_returns = compute_log_returns(prices)
    t_returns = time.perf_counter() - t0

    t0 = time.perf_counter()
    mu, sigma = compute_statistics(log_returns)
    t_stats = time.perf_counter() - t0

    t0 = time.perf_counter()
    portfolio_pnl = run_monte_carlo(
        mu, sigma, weights, portfolio_value, horizon, n_simulations
    )
    t_simulation = time.perf_counter() - t0

    t0 = time.perf_counter()
    results = calculate_var(portfolio_pnl, confidence_level)
    t_var = time.perf_counter() - t0

    total_elapsed = time.perf_counter() - total_start

    results["timing"] = {
        "data_fetch_s": round(t_fetch, 4),
        "log_returns_s": round(t_returns, 4),
        "statistics_s": round(t_stats, 4),
        "monte_carlo_s": round(t_simulation, 4),
        "var_calculation_s": round(t_var, 4),
        "total_s": round(total_elapsed, 4),
    }

    # Only print when verbose=True — skip entirely when called from FastAPI
    if verbose:
        explain_results(results, portfolio_value, horizon, tickers, weights.tolist())
        print("\n" + "-" * 60)
        print("⏱️   RUNTIME BREAKDOWN")
        print("-" * 60)
        print(f"    Data Fetch (yfinance):       {t_fetch:.4f}s")
        print(f"    Log Returns Computation:     {t_returns:.4f}s")
        print(f"    Mean & Covariance Matrix:    {t_stats:.4f}s")
        print(f"    Monte Carlo ({n_simulations:,} sims):   {t_simulation:.4f}s")
        print(f"    VaR / CVaR Extraction:       {t_var:.4f}s")
        print("    " + "-" * 40)
        print(f"    Total Runtime:               {total_elapsed:.4f}s")
        print("-" * 60 + "\n")

    return results


def run_price_path_analysis(
    portfolio: dict,
    portfolio_value: float,
    horizon: int = 22,
    n_paths: int = 100,
    volatility_multiplier: float = 1.0,
) -> dict:
    """
    End-to-end Monte Carlo price-path simulation for frontend visualization.

    Uses the same historical data, log-return statistics, covariance matrix,
    Cholesky correlation handling, and current portfolio-value definition as
    run_var_analysis(), but returns values through time instead of terminal VaR.
    """
    tickers = list(portfolio.keys())
    weights = np.array(list(portfolio.values()))

    assert abs(weights.sum() - 1.0) < 1e-6, "Portfolio weights must sum to 1.0"

    total_start = time.perf_counter()

    t0 = time.perf_counter()
    prices = fetch_historical_prices(tickers)
    t_fetch = time.perf_counter() - t0

    t0 = time.perf_counter()
    log_returns = compute_log_returns(prices)
    t_returns = time.perf_counter() - t0

    t0 = time.perf_counter()
    mu, sigma = compute_statistics(log_returns)
    t_stats = time.perf_counter() - t0

    t0 = time.perf_counter()
    path_values = run_monte_carlo_price_paths(
        mu=mu,
        cov_matrix=sigma,
        weights=weights,
        portfolio_value=portfolio_value,
        horizon=horizon,
        n_paths=n_paths,
        volatility_multiplier=volatility_multiplier,
    )
    t_simulation = time.perf_counter() - t0

    total_elapsed = time.perf_counter() - total_start

    summary = []
    for day, values in enumerate(path_values):
        summary.append(
            {
                "day": day,
                "mean": float(np.mean(values)),
                "p05": float(np.percentile(values, 5)),
                "p50": float(np.percentile(values, 50)),
                "p95": float(np.percentile(values, 95)),
            }
        )

    paths = []
    for path_index in range(path_values.shape[1]):
        paths.append(
            {
                "path_id": path_index + 1,
                "points": [
                    {"day": day, "value": float(value)}
                    for day, value in enumerate(path_values[:, path_index])
                ],
            }
        )

    return {
        "horizon": horizon,
        "n_paths": n_paths,
        "volatility_multiplier": volatility_multiplier,
        "portfolio_value": portfolio_value,
        "portfolio_weights": portfolio,
        "summary": summary,
        "paths": paths,
        "timing": {
            "data_fetch_s": round(t_fetch, 4),
            "log_returns_s": round(t_returns, 4),
            "statistics_s": round(t_stats, 4),
            "monte_carlo_s": round(t_simulation, 4),
            "total_s": round(total_elapsed, 4),
        },
    }


# ─────────────────────────────────────────────
# EXAMPLE USAGE
# ─────────────────────────────────────────────
# This block only runs when you execute this file directly:
#     python monte_carlo_var.py
#
# It is NOT executed when this module is imported by FastAPI.
#
# Yu Yang: run this first to see a full sample output before
# integrating with the API. When you call run_var_analysis()
# from FastAPI, pass verbose=False to suppress all prints and
# get only the clean results dict back.

if __name__ == "__main__":
    my_portfolio = {
        "AAPL": 0.40,  # 40% Apple
        "TSLA": 0.30,  # 30% Tesla
        "GOOGL": 0.30,  # 30% Google
    }

    results = run_var_analysis(
        portfolio=my_portfolio,
        portfolio_value=10_000,  # Current market value: holdings are worth $10,000 TODAY
        horizon=1,  # 1-day VaR
        confidence_level=0.95,  # 95% confidence
        n_simulations=1_000_000,
        verbose=True,  # set to False when calling from FastAPI
    )
