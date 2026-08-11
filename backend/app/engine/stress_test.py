"""
Riskfolio — Stress Test Engine
-------------------------------------------------
This module answers a single question: "If a hypothetical market event
happened, how would my portfolio's risk change?"

THE CORE IDEA:
    Stress testing is fundamentally just running the EXISTING VaR engine
    TWICE — once with the portfolio exactly as it is today (the
    "baseline"), and once with a hypothetical scenario applied to it (the
    "shocked" case) — and showing both results side by side.

    This module does not introduce any new risk mathematics. It reuses
    app.engine.data's data pipeline (fetch_historical_prices,
    compute_log_returns, compute_statistics), monte_carlo_var.py's
    Cholesky-based GBM simulation (run_monte_carlo), and its VaR/CVaR
    extraction (calculate_var) UNCHANGED. The only new logic here is how
    a hypothetical "shock" is translated into different inputs for that
    same, already-tested pipeline.

TWO INDEPENDENT KINDS OF SHOCK:
    1. Price shocks (per-asset, instantaneous, backward-looking):
       "AAPL crashes 15% TODAY." This changes today's STARTING dollar
       value of that position, which changes the portfolio's weights
       (since the rest of the portfolio is now a bigger slice of a
       smaller pie). See apply_price_shocks() below.

    2. Volatility multiplier (portfolio-wide, forward-looking):
       "Markets get more turbulent GOING FORWARD." This scales every
       entry of the covariance matrix, widening the simulated P&L
       distribution for the forward-looking Monte Carlo run. Uses the
       exact same name and meaning as the existing volatility_multiplier
       parameter in run_monte_carlo_price_paths() (monte_carlo_var.py) —
       intentionally, so both features behave identically from a
       frontend/API-consumer's point of view.

    These two shocks are independent and can be combined: e.g. "AAPL
    crashes 15% today, AND we expect double the normal turbulence for the
    next month" applies both simultaneously.

WHAT THIS MODULE DELIBERATELY DOES NOT DO:
    It does not shock the drift/mean-return vector (mu). A permanent
    change to expected future returns is a different, more speculative
    kind of scenario (see the module docstring's Option A/B discussion in
    project history) — this module treats a "shock" as something that
    already happened to today's price level, not a change in an asset's
    long-run trend.
"""

from __future__ import annotations

import time

import numpy as np

# Reused, UNCHANGED, from the shared data pipeline.
from app.engine.data import (
    compute_log_returns,
    compute_statistics,
    fetch_historical_prices,
)
from app.engine.monte_carlo_var import (
    calculate_var,
    run_monte_carlo,
)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: PRICE SHOCK APPLICATION
# ─────────────────────────────────────────────────────────────────────────────


def apply_price_shocks(
    portfolio: dict[str, float],
    portfolio_value: float,
    price_shocks: dict[str, float],
) -> tuple[dict[str, float], float]:
    """
    Apply an instantaneous, per-ticker price shock to a portfolio and
    return the resulting NEW weights and NEW total portfolio value.

    WHY THIS DOESN'T NEED RAW PRICES OR QUANTITIES:
        A portfolio is fully described, for risk purposes, by its WEIGHTS
        (what fraction of the total is in each asset) and its TOTAL VALUE.
        Each asset's current dollar value is simply weight * total_value —
        we don't need to know the underlying share count or price per
        share at all to apply a percentage shock.

    THE MATH, WITH A CONCRETE EXAMPLE:
        Say a $10,000 portfolio is 40% AAPL ($4,000) and 60% MSFT
        ($6,000). If AAPL crashes 15% today (price_shocks={"AAPL": -0.15}):

            AAPL's new dollar value = $4,000 * (1 + (-0.15)) = $3,400
            MSFT's new dollar value = $6,000 * (1 + 0)       = $6,000
                                                    (no shock -> unchanged)

            New total portfolio value = $3,400 + $6,000 = $9,400

            New AAPL weight = $3,400 / $9,400 = 36.2%
            New MSFT weight = $6,000 / $9,400 = 63.8%

        Notice MSFT's WEIGHT increased (60% -> 63.8%) even though MSFT
        itself wasn't shocked at all — it simply makes up a bigger slice
        of a smaller total pie now. This is a real, important effect:
        a shock to one asset changes the EFFECTIVE diversification of the
        whole portfolio, which is exactly why we re-run the full Monte
        Carlo simulation on the new weights rather than just scaling the
        old VaR number directly.

    Args:
        portfolio:      Dict of ticker -> weight (must sum to ~1.0), the
                        portfolio's weights BEFORE any shock.
        portfolio_value: The portfolio's total value in its quote currency BEFORE any
                        shock (today's actual market value).
        price_shocks:   Dict of ticker -> shock, e.g. {"AAPL": -0.15}
                        means AAPL's position instantly loses 15% of its
                        value. A ticker not present in this dict is
                        treated as unshocked (0.0). Values must be
                        strictly greater than -1.0 (validated at the API
                        layer) — a position cannot lose 100% or more of
                        its value in a single shock.

    Returns:
        Tuple of (shocked_weights, shocked_portfolio_value):
            shocked_weights:       Dict of ticker -> NEW weight, summing
                                   to 1.0, reflecting the shock.
            shocked_portfolio_value: The NEW total portfolio value in the quote currency.

    Raises:
        ValueError: If the combined shocks reduce the total portfolio
                   value to zero or below (e.g. every asset shocked to
                   near -100% simultaneously). This should be rare given
                   the per-shock -1.0 floor enforced at the API layer, but
                   is checked defensively here since this function may
                   also be called directly (e.g. from tests or a future
                   script) without going through API validation.
    """
    shocked_dollar_values: dict[str, float] = {}

    for ticker, weight in portfolio.items():
        # .get(ticker, 0.0) means any ticker NOT explicitly shocked is
        # left completely unchanged — this lets the API caller (and
        # eventually the frontend) send shocks only for the sliders the
        # user actually moved, rather than every ticker every time.
        shock = price_shocks.get(ticker, 0.0)
        dollar_value = weight * portfolio_value
        shocked_dollar_values[ticker] = dollar_value * (1.0 + shock)

    shocked_portfolio_value = sum(shocked_dollar_values.values())

    if not np.isfinite(shocked_portfolio_value) or shocked_portfolio_value <= 0:
        raise ValueError(
            "Combined price shocks reduce the portfolio to zero or "
            "negative total value — reduce the magnitude of one or more "
            "shocks"
        )

    shocked_weights = {
        ticker: dollar_value / shocked_portfolio_value
        for ticker, dollar_value in shocked_dollar_values.items()
    }

    return shocked_weights, shocked_portfolio_value


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────


def run_stress_test_analysis(
    portfolio: dict[str, float],
    portfolio_value: float,
    price_shocks: dict[str, float] | None = None,
    volatility_multiplier: float = 1.0,
    horizon: int = 1,
    confidence_level: float = 0.95,
    n_simulations: int = 10_000,
    verbose: bool = False,
) -> dict:
    """
    Full end-to-end stress test pipeline: runs the SAME Monte Carlo VaR
    analysis twice — once unshocked (baseline), once with the requested
    shocks applied (shocked) — using identical historical data for both,
    so the two results are directly, fairly comparable.

    PIPELINE OVERVIEW:
        Steps 1-3:  Fetch data and compute mu/sigma ONCE (reused from the
                    VaR engine's data pipeline) — both the baseline and
                    shocked runs are built on the exact same historical
                    statistics, so any difference between them comes
                    purely from the shock, not from re-fetching different
                    data.
        Step 4:     BASELINE run — original weights, original sigma,
                    unmodified. This is identical to what /api/v1/analyze
                    would return for this portfolio.
        Step 5:     SHOCKED run — apply_price_shocks() computes new
                    weights and new portfolio value; sigma is scaled by
                    volatility_multiplier^2 (so standard deviation scales
                    by volatility_multiplier — see apply_price_shocks()
                    and the module docstring for why this is squared).
        Step 6:     Package both results, plus an echo of exactly which
                    shocks were applied, into one response.

    WHY BOTH RUNS SHARE mu (the drift/mean-return vector):
        Only sigma (the covariance/risk matrix) and the weights change
        between baseline and shocked. mu is intentionally left untouched
        in both runs — see the module docstring for why this module
        treats a "shock" as a today-level event and a volatility change,
        not a change to long-run expected returns.

    Args:
        portfolio:          Dict of ticker -> weight, current (unshocked)
                            portfolio weights. Must sum to ~1.0.
        portfolio_value:    Current (unshocked) total portfolio value in
                            the portfolio's quote currency.
        price_shocks:       Dict of ticker -> instantaneous price shock,
                            e.g. {"AAPL": -0.15}. Defaults to no shocks
                            for any ticker if omitted.
        volatility_multiplier: Multiplier applied to historical volatility
                            for the SHOCKED run only (the baseline run
                            always uses volatility_multiplier=1.0,
                            i.e. unmodified historical volatility, by
                            definition — that's what makes it the
                            baseline). Must be strictly positive.
        horizon:            Risk horizon in trading days (1, 5, or 22 —
                            validated at the API layer), used for BOTH
                            runs so they're comparable.
        confidence_level:   VaR confidence level, used for BOTH runs.
        n_simulations:      Number of Monte Carlo simulations, used for
                            BOTH runs.
        verbose:            If True, prints a human-readable baseline vs.
                            shocked comparison. Always False when called
                            from FastAPI.

    Returns:
        Dictionary with keys:
            "tickers"        — list of ticker symbols
            "baseline"       — dict: var, var_positive, cvar,
                               cvar_positive, mean_pnl, std_pnl,
                               worst_case, best_case, confidence_level,
                               n_simulations, portfolio_value,
                               portfolio_weights (the UNSHOCKED scenario)
            "shocked"        — dict with the SAME keys as "baseline",
                               computed under the shocked scenario. Same
                               shape as "baseline" so the frontend can
                               render both through one shared component.
            "shocks_applied" — dict: price_shocks (as given),
                               volatility_multiplier (as given) — an echo
                               of exactly what scenario was simulated
            "timing"         — per-stage runtime breakdown in seconds

    Raises:
        ValueError: If volatility_multiplier is not a positive finite
                   number, or if the combined price shocks reduce the
                   portfolio to zero or negative value (see
                   apply_price_shocks()).
    """
    if price_shocks is None:
        price_shocks = {}

    if not np.isfinite(volatility_multiplier) or volatility_multiplier <= 0:
        raise ValueError("Volatility multiplier must be a positive, finite number")

    tickers = list(portfolio.keys())
    weights = np.array(list(portfolio.values()))
    assert abs(weights.sum() - 1.0) < 1e-6, "Portfolio weights must sum to 1.0"

    total_start = time.perf_counter()

    # ── Steps 1-3: Data pipeline (reused from the VaR engine, run ONCE) ──
    # Both the baseline and shocked runs below are built on this exact
    # same mu/sigma — nothing is re-fetched or re-derived between them, so
    # any difference in their results comes purely from the shock itself.
    t0 = time.perf_counter()
    prices = fetch_historical_prices(tickers)
    t_fetch = time.perf_counter() - t0

    t0 = time.perf_counter()
    log_returns = compute_log_returns(prices)
    t_returns = time.perf_counter() - t0

    t0 = time.perf_counter()
    mu, sigma = compute_statistics(log_returns)
    t_stats = time.perf_counter() - t0

    # ── Step 4: BASELINE run — original weights, original sigma ─────────
    t0 = time.perf_counter()

    # Generate ONE fresh seed for this request, then pass the SAME seed
    # to both the baseline and shocked simulations below. Each call
    # independently creates its own np.random.default_rng(shared_seed),
    # so both draw byte-identical random shocks -- this cancels Monte
    # Carlo sampling noise out of the baseline-vs-shocked COMPARISON
    # specifically (see run_monte_carlo()'s docstring for the full
    # reasoning), while a fresh seed each request still means repeated
    # stress tests on the same inputs show natural simulation
    # variability, just not BETWEEN baseline and shocked within one
    # request.
    shared_seed = int(np.random.SeedSequence().generate_state(1)[0])

    baseline_pnl = run_monte_carlo(
        mu, sigma, weights, portfolio_value, horizon, n_simulations, seed=shared_seed
    )
    baseline_results = calculate_var(baseline_pnl, confidence_level)
    # Inject portfolio-level context so "baseline" is a fully self
    # contained object — the frontend shouldn't need to cross-reference
    # any other part of the response to render this side of the
    # comparison.
    baseline_results["portfolio_value"] = portfolio_value
    baseline_results["portfolio_weights"] = portfolio
    t_baseline = time.perf_counter() - t0

    # ── Step 5: SHOCKED run — new weights, scaled sigma ──────────────────
    t0 = time.perf_counter()
    shocked_weights_dict, shocked_portfolio_value = apply_price_shocks(
        portfolio, portfolio_value, price_shocks
    )
    # Rebuild the weights array in the SAME ticker order as mu/sigma
    # (dict iteration order in Python 3.7+ is insertion order, and
    # apply_price_shocks() preserves the input dict's key order, but we
    # index explicitly by `tickers` here to be robust regardless).
    shocked_weights_arr = np.array([shocked_weights_dict[t] for t in tickers])

    # Scale the ENTIRE covariance matrix by multiplier^2 so that standard
    # deviation (what "volatility_multiplier" means to an end user) scales
    # by exactly multiplier. Squaring here is necessary because variance
    # = std_dev^2 — see the module docstring and apply_price_shocks() for
    # the full derivation. Critically, scaling every entry by the SAME
    # scalar leaves the underlying CORRELATION structure between assets
    # completely unchanged (the multiplier cancels out of the correlation
    # formula) — this is a uniform stress on magnitude only, not a
    # simulation of correlations breaking down during a crisis.
    shocked_sigma = sigma * (volatility_multiplier**2)

    shocked_pnl = run_monte_carlo(
        mu,
        shocked_sigma,
        shocked_weights_arr,
        shocked_portfolio_value,
        horizon,
        n_simulations,
        seed=shared_seed,
    )
    shocked_results = calculate_var(shocked_pnl, confidence_level)
    shocked_results["portfolio_value"] = shocked_portfolio_value
    shocked_results["portfolio_weights"] = shocked_weights_dict
    t_shocked = time.perf_counter() - t0

    total_elapsed = time.perf_counter() - total_start

    timing = {
        "data_fetch_s": round(t_fetch, 4),
        "log_returns_s": round(t_returns, 4),
        "statistics_s": round(t_stats, 4),
        "baseline_simulation_s": round(t_baseline, 4),
        "shocked_simulation_s": round(t_shocked, 4),
        "total_s": round(total_elapsed, 4),
    }

    if verbose:
        print(f"\n{'=' * 60}")
        print("💥  STRESS TEST REPORT — Riskfolio")
        print(f"{'=' * 60}")
        print(f"\n🎯  SCENARIO: price_shocks={price_shocks}, ")
        print(f"    volatility_multiplier={volatility_multiplier}x")
        print(f"⏱️   RUNTIME: {total_elapsed:.3f}s")

        def _print_scenario(label: str, results: dict, emoji: str) -> None:
            print(f"\n{'-' * 60}")
            print(f"{emoji}  {label}")
            print(f"{'-' * 60}")
            print(f"    Portfolio Value:  ${results['portfolio_value']:,.2f}")
            print(f"    VaR:              ${results['var_positive']:,.2f}")
            print(f"    CVaR:             ${results['cvar_positive']:,.2f}")
            print(f"    Worst Case:       ${results['worst_case']:,.2f}")
            print(f"    Best Case:        ${results['best_case']:,.2f}")

        _print_scenario("BASELINE (unshocked)", baseline_results, "🟢")
        _print_scenario("SHOCKED (scenario applied)", shocked_results, "🔴")

        var_change_pct = (
            (shocked_results["var_positive"] - baseline_results["var_positive"])
            / baseline_results["var_positive"]
            * 100
            if baseline_results["var_positive"] > 0
            else float("nan")
        )
        print(f"\n{'-' * 60}")
        print("💡  INSIGHT")
        print(f"{'-' * 60}")
        print(f"\n    VaR changed by {var_change_pct:+.1f}% under this scenario.")
        print(f"{'=' * 60}\n")

    return {
        "tickers": tickers,
        "baseline": baseline_results,
        "shocked": shocked_results,
        "shocks_applied": {
            "price_shocks": price_shocks,
            "volatility_multiplier": volatility_multiplier,
        },
        "timing": timing,
    }


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE USAGE
# ─────────────────────────────────────────────────────────────────────────────
# Run this file directly to see a full printed baseline-vs-shocked report:
#     cd backend
#     uv run python -m app.engine.stress_test

if __name__ == "__main__":
    result = run_stress_test_analysis(
        portfolio={"AAPL": 0.40, "TSLA": 0.30, "GOOGL": 0.30},
        portfolio_value=10_000.0,
        price_shocks={"AAPL": -0.15, "TSLA": -0.30},
        volatility_multiplier=1.5,
        horizon=1,
        confidence_level=0.95,
        n_simulations=10_000,
        verbose=True,
    )
