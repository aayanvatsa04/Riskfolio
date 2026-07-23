"""
Riskfolio — MPT Optimizer (Efficient Frontier)
-------------------------------------------------
This module implements Harry Markowitz's Modern Portfolio Theory (1952),
the mathematical framework that won him the Nobel Prize in Economics.

THE CORE IDEA:
    Every portfolio of stocks can be described by two numbers:
        1. Expected return  — how much you expect to gain per year (%)
        2. Volatility       — how much your portfolio swings per year (%)

    If you plot every possible way to split your money across a set of
    stocks on a chart (volatility on x-axis, return on y-axis), you get
    a cloud of points. The upper-left boundary of that cloud is called
    the "Efficient Frontier" — it represents the best possible return
    for each level of risk. Any portfolio NOT on this frontier is
    suboptimal: you could get the same return with less risk, or more
    return for the same risk, by rebalancing.

HOW WE COMPUTE IT:
    Rather than solving the exact quadratic programming problem
    (scipy.optimize), we use a Monte Carlo approach: generate 5,000
    random weight combinations, compute return/volatility/Sharpe for
    each, and find the best among them. This approximates the frontier
    very well and is much easier to understand and maintain.

REUSE:
    This module imports fetch_historical_prices, compute_log_returns,
    and compute_statistics directly from monte_carlo_var.py. There is
    no duplicate data pipeline code — the same 5 years of price data,
    the same log return calculation, and the same mean vector (μ) and
    covariance matrix (Σ) are used as the foundation for both VaR
    and MPT analysis.

INPUTS:  List of tickers + user's current weights
OUTPUTS: Efficient frontier scatter data + 3 annotated portfolios:
             - Max Sharpe  (best return per unit of risk)
             - Min Vol     (least risky possible allocation)
             - Current     (where the user's actual portfolio sits)
"""

from __future__ import annotations

import time

import numpy as np
from scipy.optimize import minimize

# Import the data pipeline functions from the VaR engine.
# We deliberately reuse these rather than rewriting them — if the data
# pipeline ever changes (e.g. switching from yfinance to another source),
# both VaR and MPT automatically benefit from the update.
from app.engine.monte_carlo_var import (
    compute_log_returns,  # prices → daily log returns DataFrame
    compute_statistics,  # log returns → (μ vector, Σ matrix)
    fetch_historical_prices,  # tickers → 5-year daily price DataFrame
)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANT
# ─────────────────────────────────────────────────────────────────────────────

# The number of trading days in a calendar year.
# US stock markets are open ~252 days per year (365 minus weekends and
# public holidays). This constant is used to scale daily statistical
# parameters up to annualised figures, which are the standard unit for
# reporting expected returns and volatility in portfolio management.
TRADING_DAYS = 252


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: ANNUALISATION
# ─────────────────────────────────────────────────────────────────────────────


def annualise_parameters(
    mu: np.ndarray,
    sigma: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Scale daily statistical parameters to annualised figures.

    compute_statistics() from the VaR engine gives us DAILY figures:
        mu    = average daily log return for each asset   shape: (n_assets,)
        sigma = daily covariance matrix                   shape: (n_assets, n_assets)

    For portfolio optimisation, convention is to work in ANNUAL figures
    so that numbers like "12% expected return" and "18% volatility" are
    immediately meaningful to an investor.

    HOW DRIFT ANNUALISES (mu):
        Drift scales LINEARLY with time. If a stock returns 0.04% per day
        on average, over 252 trading days it returns approximately:
            0.04% × 252 = 10.08% per year
        So: mu_annual = mu_daily × 252

    HOW COVARIANCE ANNUALISES (sigma):
        Under the assumption of independent daily returns (standard in GBM),
        the variance of a sum of T independent draws each with variance σ²
        is T × σ². So variance scales linearly with time too:
            sigma_annual = sigma_daily × 252

        This means annualised VOLATILITY (standard deviation) scales with √252:
            vol_annual = sqrt(sigma_annual) = sqrt(sigma_daily × 252)
                       = sqrt(252) × vol_daily  ≈  15.87 × vol_daily

        This is the familiar "multiply daily vol by √252" rule used everywhere
        in finance. We annualise the full covariance matrix so that the
        quadratic form w @ sigma_annual @ w directly gives annualised variance.

    Args:
        mu:     Daily mean return vector.     Shape: (n_assets,)
        sigma:  Daily covariance matrix.      Shape: (n_assets, n_assets)

    Returns:
        Tuple of (annual_mu, annual_sigma), same shapes as inputs.
    """
    annual_mu = mu * TRADING_DAYS  # element-wise scalar multiply
    annual_sigma = (
        sigma * TRADING_DAYS
    )  # element-wise scalar multiply (each entry ×252)
    return annual_mu, annual_sigma


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: RANDOM PORTFOLIO SIMULATION
# ─────────────────────────────────────────────────────────────────────────────


def simulate_random_portfolios(
    annual_mu: np.ndarray,
    annual_sigma: np.ndarray,
    n_assets: int,
    n_portfolios: int,
    risk_free_rate: float,
) -> dict[str, np.ndarray]:
    """
    Generate n_portfolios random weight combinations and compute the
    annualised expected return, volatility, and Sharpe ratio for each.
    This is the core computation that builds the Efficient Frontier cloud.

    FULLY VECTORIZED — no Python for loop over portfolios.
    All n_portfolios are computed simultaneously as matrix operations,
    running in NumPy's optimized C layer. With n_portfolios=5,000 and
    n_assets=5, this typically completes in under 5 milliseconds.

    ── STEP A: WEIGHT GENERATION ──────────────────────────────────────────────

    We want random weight vectors where each weight is ≥ 0 and all
    weights sum to exactly 1.0 (a valid long-only portfolio).

    Method: draw uniform random numbers and normalise each row.

        raw = np.random.random((n_portfolios, n_assets))
            → shape (5000, 3) for a 3-stock portfolio
            → each entry is a random number between 0 and 1

        weights = raw / raw.sum(axis=1, keepdims=True)
            → divide each row by its own sum
            → now every row sums to exactly 1.0
            → keepdims=True keeps shape (5000, 1) so broadcasting works

    Example for 3 assets, 4 simulations:
        raw =     [[0.8, 0.1, 0.3],   → row sums: [1.2, 0.6, 1.8, 0.9]
                   [0.2, 0.3, 0.1],
                   [0.9, 0.5, 0.4],
                   [0.3, 0.4, 0.2]]

        weights = [[0.67, 0.08, 0.25],   ← each row now sums to 1.0
                   [0.33, 0.50, 0.17],
                   [0.50, 0.28, 0.22],
                   [0.33, 0.44, 0.22]]

    This samples from the (n_assets - 1)-simplex — every valid long-only
    weight combination is reachable, and the distribution is approximately
    uniform over it.

    ── STEP B: EXPECTED RETURN ────────────────────────────────────────────────

    The expected annual return of a portfolio is simply the weighted average
    of each asset's expected annual return:

        E[R_portfolio] = Σᵢ wᵢ × μᵢ = w · μ

    In vectorized form, for all n_portfolios at once:

        port_returns = weights @ annual_mu
            shape: (n_portfolios, n_assets) @ (n_assets,) → (n_portfolios,)

    Each row of weights dots with annual_mu to give one expected return
    per portfolio.

    ── STEP C: PORTFOLIO VARIANCE (QUADRATIC FORM) ────────────────────────────

    This is the crucial calculation that makes MPT powerful. The variance
    of a portfolio is NOT just the weighted average of individual variances.
    It also depends on how the assets move together (covariance).

    For a single portfolio with weights w and covariance matrix Σ:
        Variance = w @ Σ @ w = wᵀ Σ w  (the quadratic form)

    Why this matters: if AAPL and TSLA are highly correlated (crash together),
    holding both gives you less diversification than holding two uncorrelated
    assets. The covariance matrix Σ encodes all of this. The quadratic form
    captures it mathematically:
        - High off-diagonal Σ entries (high correlation) → higher variance
        - Low or negative off-diagonal entries → diversification benefit

    Computing wᵀ Σ w for all 5,000 portfolios simultaneously uses einsum:

        np.einsum("pi,ij,pj->p", weights, annual_sigma, weights)

    Reading the einsum notation "pi,ij,pj->p":
        p = portfolio index (0 to 4999)
        i = first asset index
        j = second asset index
        "pi" = weights matrix, element [portfolio p, asset i]
        "ij" = covariance matrix, element [asset i, asset j]
        "pj" = weights matrix again, element [portfolio p, asset j]
        "->p" = sum over i and j, leaving one result per portfolio p

    This is equivalent to: for each portfolio p, compute weights[p] @ Σ @ weights[p]
    but does it for ALL portfolios in one C-layer operation.

    ── STEP D: SHARPE RATIO ───────────────────────────────────────────────────

    The Sharpe ratio measures return per unit of risk — how much extra
    return above the risk-free rate you earn for each percentage point
    of volatility you take on:

        Sharpe = (E[R_portfolio] - R_f) / σ_portfolio

    Where R_f is the risk-free rate (what you'd earn in US Treasuries, ~5%).
    A Sharpe above 1.0 is considered good. Above 2.0 is excellent.

    Higher Sharpe = better deal for the investor. The Max Sharpe portfolio
    is the single best risk-adjusted portfolio achievable from these assets.

    We use np.where to guard against division by zero in the edge case
    where a simulated portfolio somehow has zero volatility.

    Args:
        annual_mu:       Annualised mean return vector.     Shape: (n_assets,)
        annual_sigma:    Annualised covariance matrix.      Shape: (n_assets, n_assets)
        n_assets:        Number of assets in the portfolio.
        n_portfolios:    Number of random portfolios to simulate.
        risk_free_rate:  Annualised risk-free rate (e.g. 0.05 for 5%).

    Returns:
        Dictionary with four arrays, each of shape (n_portfolios,):
            "weights"      — the weight matrix,  shape (n_portfolios, n_assets)
            "returns"      — annualised expected return per portfolio
            "volatilities" — annualised volatility per portfolio
            "sharpes"      — Sharpe ratio per portfolio
    """
    # ── A: Generate random weights ──────────────────────────────────────────
    raw = np.random.random((n_portfolios, n_assets))
    # Normalise each row so all weights in a portfolio sum to exactly 1.0
    weights = raw / raw.sum(axis=1, keepdims=True)  # shape: (n_portfolios, n_assets)

    # ── B: Expected annual return per portfolio ──────────────────────────────
    # Dot product: for each portfolio, sum(weight_i × mu_i) over all assets
    port_returns = weights @ annual_mu  # shape: (n_portfolios,)

    # ── C: Annual variance per portfolio (quadratic form wᵀ Σ w) ────────────
    port_variances = np.einsum("pi,ij,pj->p", weights, annual_sigma, weights)
    # np.maximum clips any tiny negative values caused by floating-point
    # rounding errors in the matrix multiplication — variance can never be
    # negative in theory, but floating-point arithmetic can produce values
    # like -1e-16 which would cause sqrt to fail with a NaN.
    port_vols = np.sqrt(np.maximum(port_variances, 0.0))  # shape: (n_portfolios,)

    # ── D: Sharpe ratio per portfolio ────────────────────────────────────────
    # np.where(condition, value_if_true, value_if_false) — vectorized if/else
    # If volatility is effectively zero (shouldn't happen with real stocks but
    # defensive coding), assign Sharpe of 0.0 rather than dividing by zero.
    port_sharpes = np.where(
        port_vols > 1e-10,
        (port_returns - risk_free_rate) / port_vols,
        0.0,
    )  # shape: (n_portfolios,)

    return {
        "weights": weights,
        "returns": port_returns,
        "volatilities": port_vols,
        "sharpes": port_sharpes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2b: ANALYTICAL EFFICIENT FRONTIER (EXACT, VIA SCIPY.OPTIMIZE)
# ─────────────────────────────────────────────────────────────────────────────


def compute_analytical_frontier(
    annual_mu: np.ndarray,
    annual_sigma: np.ndarray,
    risk_free_rate: float,
    n_points: int = 50,
) -> list[dict]:
    """
    Compute the EXACT Efficient Frontier by solving a constrained quadratic
    optimization problem at a sweep of target returns, using
    scipy.optimize.minimize (method="SLSQP").

    WHY THIS EXISTS ALONGSIDE simulate_random_portfolios():
        simulate_random_portfolios() APPROXIMATES the frontier by randomly
        sampling thousands of weight combinations and keeping the best ones.
        It is simple, fast, and easy to reason about — but it is still an
        approximation: with n_portfolios=5,000, the highest-Sharpe sample
        found is typically within 1-2% of the true optimum (see the module
        docstring and section 12.5 of the project README).

        This function instead computes the MATHEMATICALLY EXACT frontier.
        For each target return, it asks: "of all portfolios that achieve
        AT LEAST this expected return, which one has the lowest possible
        variance?" That is a textbook constrained optimization problem,
        and SLSQP (Sequential Least Squares Programming) solves it exactly
        (up to numerical solver tolerance) rather than by random search.

        We deliberately compute and return BOTH curves (this one, and the
        Monte Carlo cloud from simulate_random_portfolios()) so the two can
        be plotted on the same chart. If the Monte Carlo cloud's upper-left
        edge hugs this exact curve closely, that is a direct, visual proof
        that the sampling approach is correct — turning the "within 1-2%"
        claim in the README into something a viewer can actually see,
        rather than just take on faith.

    THE OPTIMIZATION PROBLEM, FOR EACH TARGET RETURN r:

        minimize     wᵀ Σ w                    (portfolio variance)
        subject to   Σᵢ wᵢ  = 1                 (fully invested — no cash left over)
                     w · μ   = r                (hit the exact target return)
                     wᵢ ≥ 0  for all i           (long-only — no short positions,
                                                  consistent with every other
                                                  engine in this codebase)

        Tracing this out for many values of r (from the lowest-return asset
        to the highest-return asset) gives the full Efficient Frontier curve:
        for every level of return, the minimum possible risk to achieve it.

    HOW SLSQP FITS IN:
        SLSQP handles exactly this shape of problem — a smooth (quadratic)
        objective with linear equality constraints and simple bounds. We
        re-solve it once per target return (n_points times), each solve
        taking a small fraction of a millisecond for a handful of assets.
        This is why the sweep is fast even though it looks like "50 separate
        optimization problems" — each one is tiny.

    Args:
        annual_mu:       Annualised mean return vector.    Shape: (n_assets,)
        annual_sigma:    Annualised covariance matrix.      Shape: (n_assets, n_assets)
        risk_free_rate:  Annualised risk-free rate, used to compute the
                         Sharpe ratio at each point on the curve (same
                         formula as compute_portfolio_stats()).
        n_points:        Number of target returns to sweep between the
                         lowest and highest individual-asset annual return.
                         Default 50 — enough for a visually smooth curve
                         without solving hundreds of optimization problems.

    Returns:
        List of up to n_points dicts (fewer if some target returns are
        infeasible — see note below), each shaped identically to a Monte
        Carlo frontier point so the frontend can plot both series through
        the same chart component:
            "expected_return" — float, annualised expected return
            "volatility"      — float, annualised volatility (the MINIMUM
                                 possible volatility for this return level —
                                 this is what makes it "the frontier")
            "sharpe"          — float, Sharpe ratio at this point

    NOTE ON INFEASIBLE TARGETS:
        Every target return between the min and max individual-asset return
        is feasible for a long-only portfolio (you can always allocate more
        to the higher-return asset to reach it). In rare numerical edge
        cases SLSQP may fail to converge for a specific target (e.g. a
        target extremely close to a single-asset corner solution) — such
        points are silently skipped rather than raising, since one missing
        point out of 50 does not meaningfully affect the shape of the curve.
    """
    n_assets = len(annual_mu)

    # ── Determine the sweep range ────────────────────────────────────────
    # The lowest achievable return for a long-only portfolio is simply
    # holding 100% of whichever single asset has the lowest expected return
    # (you cannot go below that — there's no shorting). Symmetrically, the
    # highest achievable return is 100% in the highest-return asset.
    # Sweeping between these two bounds covers the entire feasible frontier.
    min_target = float(np.min(annual_mu))
    max_target = float(np.max(annual_mu))
    target_returns = np.linspace(min_target, max_target, n_points)

    # ── Shared optimizer setup ───────────────────────────────────────────
    # Bounds: every weight must be between 0 and 1 (long-only, no leverage).
    # This list is the same for every solve, so it is built once outside
    # the loop.
    bounds = [(0.0, 1.0) for _ in range(n_assets)]

    # Equal-weighted starting guess for every solve. SLSQP is a local
    # optimizer, but this problem is convex (quadratic objective, linear
    # constraints), so it reliably finds the global optimum regardless of
    # starting point — the equal-weight guess is just a simple, neutral
    # choice used for every target return in the sweep.
    initial_weights = np.full(n_assets, 1.0 / n_assets)

    def _portfolio_variance(weights: np.ndarray) -> float:
        """Objective function: wᵀ Σ w — the quantity SLSQP minimizes."""
        return float(weights @ annual_sigma @ weights)

    frontier_curve: list[dict] = []

    for target in target_returns:
        # Two equality constraints for this specific solve:
        #   1) weights must sum to 1 (fully invested)
        #   2) weighted return must exactly equal this sweep's target
        # `target=target` in the lambda default binds the CURRENT loop
        # value at definition time — without it, every constraint closure
        # would incorrectly reference the final value of `target` after
        # the loop finishes (a classic Python late-binding closure bug).
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
            {
                "type": "eq",
                "fun": lambda w, target=target: float(w @ annual_mu) - target,
            },
        ]

        result = minimize(
            _portfolio_variance,
            initial_weights,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 200, "ftol": 1e-12},
        )

        # Skip target returns where the solver failed to converge (see
        # docstring note above) rather than raising — a smooth 49-point
        # curve is preferable to crashing the whole optimization endpoint
        # over a single numerically awkward target.
        if not result.success:
            continue

        w_opt = result.x
        variance = float(w_opt @ annual_sigma @ w_opt)
        volatility = float(np.sqrt(max(variance, 0.0)))
        expected_return = float(w_opt @ annual_mu)

        # Same Sharpe formula as compute_portfolio_stats() and
        # simulate_random_portfolios() — guarded against division by zero.
        sharpe = (
            (expected_return - risk_free_rate) / volatility
            if volatility > 1e-10
            else 0.0
        )

        frontier_curve.append(
            {
                "expected_return": expected_return,
                "volatility": volatility,
                "sharpe": sharpe,
            }
        )

    return frontier_curve


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: SINGLE-PORTFOLIO STATISTICS
# ─────────────────────────────────────────────────────────────────────────────


def compute_portfolio_stats(
    weights_vec: np.ndarray,
    annual_mu: np.ndarray,
    annual_sigma: np.ndarray,
    risk_free_rate: float,
    tickers: list[str],
) -> dict:
    """
    Compute annualised statistics for a single specific weight vector.

    This function is called three times in the main pipeline:
        1. For the Max Sharpe portfolio (the weight row with highest Sharpe)
        2. For the Min Volatility portfolio (the weight row with lowest vol)
        3. For the user's current portfolio (their actual holdings weights)

    The math is identical to simulate_random_portfolios() but for one
    portfolio rather than 5,000 — plain dot products instead of matrix ops.

    WHY A SEPARATE FUNCTION?
        simulate_random_portfolios() returns numpy arrays and indices.
        To send results to the frontend, we need clean Python dicts with
        float values and ticker-keyed weight breakdowns. This function
        handles that conversion for the three portfolios we actually care about.

    Args:
        weights_vec:     1D array of portfolio weights.    Shape: (n_assets,)
        annual_mu:       Annualised mean return vector.    Shape: (n_assets,)
        annual_sigma:    Annualised covariance matrix.     Shape: (n_assets, n_assets)
        risk_free_rate:  Annualised risk-free rate.
        tickers:         List of ticker symbols, same order as weights/mu/sigma.
                         Used to build the {"AAPL": 0.4, "TSLA": 0.3, ...} dict.

    Returns:
        Dictionary with keys:
            "expected_return" — float, annualised expected return (e.g. 0.182 = 18.2%)
            "volatility"      — float, annualised volatility      (e.g. 0.241 = 24.1%)
            "sharpe"          — float, Sharpe ratio               (e.g. 0.877)
            "weights"         — dict mapping ticker → weight      (e.g. {"AAPL": 0.71})
    """
    # Expected annual return: weighted sum of each asset's annual mean return
    exp_return = float(weights_vec @ annual_mu)

    # Portfolio annual variance: the quadratic form wᵀ Σ w
    # For a single weight vector this is a simple sequence of two dot products:
    #     step 1: annual_sigma @ weights_vec  → shape (n_assets,)
    #     step 2: weights_vec @  ^^^          → scalar
    variance = float(weights_vec @ annual_sigma @ weights_vec)

    # Annualised volatility: square root of variance
    # max(variance, 0.0) guards against floating-point negatives (see above)
    volatility = float(np.sqrt(max(variance, 0.0)))

    # Sharpe ratio: excess return above risk-free rate per unit of volatility
    # The conditional prevents division by zero on degenerate portfolios
    sharpe = (
        float((exp_return - risk_free_rate) / volatility) if volatility > 1e-10 else 0.0
    )

    # Build the ticker-keyed weight dict, e.g. {"AAPL": 0.71, "TSLA": 0.29}
    # enumerate(tickers) pairs each ticker with its index in the weights array
    weights_dict = {ticker: float(weights_vec[i]) for i, ticker in enumerate(tickers)}

    return {
        "expected_return": exp_return,
        "volatility": volatility,
        "sharpe": sharpe,
        "weights": weights_dict,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────


def run_mpt_optimization(
    tickers: list[str],
    current_weights: dict[str, float],
    n_portfolios: int = 5_000,
    risk_free_rate: float = 0.05,
    verbose: bool = False,
) -> dict:
    """
    Full end-to-end MPT optimization pipeline.

    Orchestrates all steps from data ingestion through to the final
    results dictionary that the FastAPI endpoint returns as JSON.

    PIPELINE OVERVIEW:
        Steps 1–3:  Reuse the VaR engine's data pipeline
                    (fetch prices → log returns → μ, Σ)
        Step 4:     Annualise the daily parameters (×252)
        Step 5:     Simulate 5,000 random portfolios and compute
                    return, volatility, Sharpe for each (vectorized)
        Step 5b:    Compute the EXACT analytical frontier via
                    scipy.optimize (SLSQP) — see
                    compute_analytical_frontier() for full detail.
                    Runs alongside, not instead of, Step 5.
        Step 6:     Find the Max Sharpe and Min Vol portfolios
                    (argmax / argmin over the Sharpe / vol arrays)
        Step 7:     Compute stats for the user's current weights
                    (so they can see where they sit on the frontier)
        Step 8:     Sample up to 1,000 frontier points for the
                    chart payload (full 5,000 would bloat the JSON)

    WHY 5,000 PORTFOLIOS?
        With 3–5 stocks, 5,000 random samples provide a smooth, dense
        frontier cloud. The Max Sharpe found among 5,000 samples is
        typically within 1–2% of the analytical optimum (found by
        scipy.optimize). For a retail investor dashboard this precision
        is more than sufficient — and the approach is far more transparent
        and educational than a black-box optimizer.

    WHY CAP CHART POINTS AT 1,000?
        The frontend ScatterChart only needs enough points to render a
        smooth-looking cloud — 1,000 dots achieve that. Sending all 5,000
        would quadruple the JSON payload size for zero visual benefit.

    Args:
        tickers:          List of ticker symbols to optimise across.
                          Must contain at least 2 distinct tickers —
                          you cannot build a frontier with a single asset.
        current_weights:  The user's current portfolio as a dict mapping
                          ticker → weight, e.g. {"AAPL": 0.4, "TSLA": 0.6}.
                          Weights should sum to 1.0 (built by the API layer
                          from live prices and holdings quantities).
        n_portfolios:     Number of random weight combinations to simulate.
                          Default 5,000 — sufficient for a smooth frontier.
        risk_free_rate:   Annualised risk-free rate used for Sharpe calculation.
                          Default 0.05 = 5%, approximately the US 10-year
                          Treasury yield as of 2024–2025.
        verbose:          If True, prints a human-readable summary.
                          Always set to False when called from FastAPI —
                          the results dict is returned either way.

    Returns:
        Dictionary with the following keys (serialized to JSON by FastAPI):
            "tickers"              — list of ticker symbols
            "frontier_points"      — list of up to 1,000 dicts, each with
                                     expected_return, volatility, sharpe
                                     (the Monte Carlo scatter cloud)
            "analytical_frontier_curve" — list of up to 50 dicts, same shape
                                     as frontier_points, tracing the EXACT
                                     frontier via scipy.optimize (SLSQP).
                                     Plot alongside frontier_points to
                                     visually verify the Monte Carlo cloud
                                     hugs the true frontier.
            "max_sharpe_portfolio" — dict with expected_return, volatility,
                                     sharpe, weights (the optimal portfolio)
            "min_vol_portfolio"    — dict with the same fields (least risky)
            "current_portfolio"    — dict with the same fields (user's actual)
            "risk_free_rate"       — echoed back for the frontend to display
            "n_portfolios"         — echoed back for the frontend to display
            "timing"               — per-stage runtime breakdown in seconds

    Raises:
        ValueError: If fewer than 2 distinct tickers are provided.
    """
    # Guard: MPT requires at least 2 assets to construct a frontier.
    # A single asset has no diversification — its "frontier" is just a point.
    if len(tickers) < 2:
        raise ValueError(
            "At least 2 distinct tickers are required for portfolio optimisation"
        )

    total_start = time.perf_counter()

    # ── Steps 1–3: Data pipeline (reused from VaR engine) ───────────────────
    # These three functions are imported directly from monte_carlo_var.py.
    # They are not re-implemented here — see that file for full documentation.

    t0 = time.perf_counter()
    prices = fetch_historical_prices(tickers)
    # prices: DataFrame, shape (n_trading_days, n_assets)
    # e.g. 1,260 rows × 3 columns for a 3-stock portfolio over 5 years
    t_fetch = time.perf_counter() - t0

    t0 = time.perf_counter()
    log_returns = compute_log_returns(prices)
    # log_returns: DataFrame of daily log returns, shape (n_trading_days - 1, n_assets)
    # Row 0 is dropped because there is no "previous day" for the first price
    t_returns = time.perf_counter() - t0

    t0 = time.perf_counter()
    mu, sigma = compute_statistics(log_returns)
    # mu:    1D array of mean daily log returns,  shape: (n_assets,)
    # sigma: 2D covariance matrix of daily returns, shape: (n_assets, n_assets)

    # Scale from daily → annualised before any portfolio math
    annual_mu, annual_sigma = annualise_parameters(mu, sigma)
    # annual_mu:    shape (n_assets,)         — e.g. [0.18, 0.22, 0.15]
    # annual_sigma: shape (n_assets, n_assets) — all entries multiplied by 252
    t_stats = time.perf_counter() - t0

    # ── Step 5: Simulate random portfolios ──────────────────────────────────
    t0 = time.perf_counter()
    sim = simulate_random_portfolios(
        annual_mu, annual_sigma, len(tickers), n_portfolios, risk_free_rate
    )
    # sim["weights"]      shape: (n_portfolios, n_assets)  — all weight combinations
    # sim["returns"]      shape: (n_portfolios,)           — annualised expected return
    # sim["volatilities"] shape: (n_portfolios,)           — annualised volatility
    # sim["sharpes"]      shape: (n_portfolios,)           — Sharpe ratio
    t_opt = time.perf_counter() - t0

    # Unpack arrays for readability in the steps below
    weights_arr = sim["weights"]
    returns_arr = sim["returns"]
    vols_arr = sim["volatilities"]
    sharpes_arr = sim["sharpes"]

    # ── Step 5b: Compute the EXACT analytical frontier (scipy.optimize) ─────
    # This runs alongside (not instead of) the Monte Carlo cloud above, so
    # the frontend can plot both series and visually verify that the
    # sampled cloud's edge tracks the true frontier curve. See the
    # compute_analytical_frontier() docstring for full mathematical detail.
    t0 = time.perf_counter()
    analytical_frontier_curve = compute_analytical_frontier(
        annual_mu, annual_sigma, risk_free_rate
    )
    t_analytical = time.perf_counter() - t0

    # ── Step 6: Identify optimal portfolios ─────────────────────────────────

    # np.argmax returns the INDEX of the largest value in the array.
    # sharpes_arr is shape (5000,) — argmax gives us the row number of the
    # portfolio with the highest Sharpe ratio among all 5,000 simulations.
    max_sharpe_idx = int(np.argmax(sharpes_arr))

    # np.argmin returns the index of the smallest value — the least volatile
    # portfolio among all 5,000 simulations.
    min_vol_idx = int(np.argmin(vols_arr))

    # Now compute the full stats dict for each optimal portfolio using its
    # weight vector (the corresponding row of weights_arr)
    max_sharpe_portfolio = compute_portfolio_stats(
        weights_arr[max_sharpe_idx],  # weight vector for the best Sharpe row
        annual_mu,
        annual_sigma,
        risk_free_rate,
        tickers,
    )
    min_vol_portfolio = compute_portfolio_stats(
        weights_arr[min_vol_idx],  # weight vector for the lowest vol row
        annual_mu,
        annual_sigma,
        risk_free_rate,
        tickers,
    )

    # ── Step 7: Compute stats for the user's current portfolio ──────────────

    # Reconstruct a numpy weight vector from the dict, in the same ticker
    # order as annual_mu and annual_sigma (which follow the `tickers` list).
    # dict.get(t, 0.0) gracefully handles any ticker that might be missing
    # from current_weights — it defaults to 0% allocation.
    current_w = np.array([current_weights.get(t, 0.0) for t in tickers])

    current_portfolio = compute_portfolio_stats(
        current_w, annual_mu, annual_sigma, risk_free_rate, tickers
    )
    # Override the reconstructed weights dict with the original dict from the
    # API — this preserves the exact float values from the live price
    # calculation rather than introducing any rounding from the array round-trip
    current_portfolio["weights"] = current_weights

    # ── Step 8: Sample frontier points for the chart payload ────────────────

    # Cap at 1,000 points for the JSON response. With n_portfolios=5,000,
    # we randomly sample 1,000 indices without replacement.
    # "Without replacement" means no duplicate portfolios in the chart.
    chart_n = min(1_000, n_portfolios)
    if n_portfolios > chart_n:
        # Random sample of indices into the simulation arrays
        idx = np.random.choice(n_portfolios, chart_n, replace=False)
    else:
        # If n_portfolios ≤ 1,000, use all of them
        idx = np.arange(n_portfolios)

    # Build the list of dicts that becomes the scatter cloud on the frontend.
    # Each dict is one dot on the Efficient Frontier chart.
    frontier_points = [
        {
            "expected_return": float(returns_arr[i]),
            "volatility": float(vols_arr[i]),
            "sharpe": float(sharpes_arr[i]),
        }
        for i in idx
        # float() converts from numpy float64 to Python float for JSON serialization
    ]

    total_elapsed = time.perf_counter() - total_start

    # Timing breakdown — same pattern as run_var_analysis() in monte_carlo_var.py
    timing = {
        "data_fetch_s": round(t_fetch, 4),
        "log_returns_s": round(t_returns, 4),
        "statistics_s": round(t_stats, 4),
        "optimization_s": round(t_opt, 4),  # time for the 5,000-portfolio simulation
        "analytical_frontier_s": round(t_analytical, 4),  # time for the SLSQP sweep
        "total_s": round(total_elapsed, 4),
    }

    if verbose:
        print(f"\n{'=' * 60}")
        print("📊  MPT OPTIMISATION REPORT — Riskfolio")
        print(f"{'=' * 60}")
        print(f"\n🎲  SIMULATIONS:     {n_portfolios:,} random portfolios")
        print(f"⏱️   RUNTIME:         {total_elapsed:.3f}s")
        print(f"💹  RISK-FREE RATE:  {risk_free_rate:.1%} annualised")

        def _print_portfolio(label: str, portfolio: dict, emoji: str) -> None:
            """Helper to print a single portfolio's stats and weights cleanly."""
            print(f"\n{'-' * 60}")
            print(f"{emoji}  {label}")
            print(f"{'-' * 60}")
            print(f"    Expected Return:  {portfolio['expected_return']:.2%}")
            print(f"    Volatility:       {portfolio['volatility']:.2%}")
            print(f"    Sharpe Ratio:     {portfolio['sharpe']:.3f}")
            print("\n    Allocation:")
            for ticker, weight in sorted(
                portfolio["weights"].items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                bar = "█" * int(weight * 30)
                print(f"        {ticker:<8} {weight:>6.1%}  {bar}")

        _print_portfolio(
            "MAX SHARPE (Optimal — best return per unit of risk)",
            max_sharpe_portfolio,
            "🟢",
        )
        _print_portfolio(
            "MIN VOLATILITY (Least risky allocation)", min_vol_portfolio, "🔵"
        )
        _print_portfolio("YOUR CURRENT PORTFOLIO", current_portfolio, "🟡")

        print(f"\n{'-' * 60}")
        print("💡  INSIGHT")
        print(f"{'-' * 60}")

        sharpe_improvement = (
            max_sharpe_portfolio["sharpe"] - current_portfolio["sharpe"]
        )
        vol_improvement = (
            current_portfolio["volatility"] - min_vol_portfolio["volatility"]
        )

        print(f"""
    Rebalancing to Max Sharpe would improve your Sharpe ratio
    by {sharpe_improvement:+.3f} ({current_portfolio["sharpe"]:.3f} → {max_sharpe_portfolio["sharpe"]:.3f}).

    Rebalancing to Min Vol would reduce your annual volatility
    by {vol_improvement:.1%} ({current_portfolio["volatility"]:.1%} → {min_vol_portfolio["volatility"]:.1%}).

    If your current portfolio sits inside the frontier cloud,
    you could get a better risk-return profile without changing
    which stocks you hold — just the allocation.
        """)

        print(f"\n{'-' * 60}")
        print("⏱️   RUNTIME BREAKDOWN")
        print(f"{'-' * 60}")
        print(f"    Data Fetch (yfinance):       {timing['data_fetch_s']:.4f}s")
        print(f"    Log Returns Computation:     {timing['log_returns_s']:.4f}s")
        print(f"    Mean & Covariance Matrix:    {timing['statistics_s']:.4f}s")
        print(f"    Portfolio Simulation:        {timing['optimization_s']:.4f}s")
        print(f"    {'─' * 38}")
        print(f"    Total Runtime:               {timing['total_s']:.4f}s")
        print(f"{'=' * 60}\n")

    return {
        "tickers": tickers,
        "frontier_points": frontier_points,
        "analytical_frontier_curve": analytical_frontier_curve,
        "max_sharpe_portfolio": max_sharpe_portfolio,
        "min_vol_portfolio": min_vol_portfolio,
        "current_portfolio": current_portfolio,
        "risk_free_rate": risk_free_rate,
        "n_portfolios": n_portfolios,
        "timing": timing,
    }


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE USAGE
# ─────────────────────────────────────────────────────────────────────────────
# Run this file directly to see a full printed summary:
#     cd backend
#     uv run python -m app.engine.mpt_optimizer
#
# Set verbose=True to see the timing breakdown and portfolio comparison.
# When called from FastAPI, verbose is always False.

if __name__ == "__main__":
    result = run_mpt_optimization(
        tickers=["AAPL", "TSLA", "GOOGL"],
        current_weights={"AAPL": 0.40, "TSLA": 0.30, "GOOGL": 0.30},
        n_portfolios=5_000,
        risk_free_rate=0.05,
        verbose=True,
    )
