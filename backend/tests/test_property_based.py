"""
Riskfolio — Property-Based Test Suite (Hypothesis)
-----------------------------------------------------------
Complements the hand-picked test cases in test_engine.py, test_optimizer.py,
and test_stress_test.py with AUTO-GENERATED edge cases.

WHY THIS EXISTS ALONGSIDE THE EXISTING TEST SUITES:
    A hand-written test picks specific numbers (e.g. "AAPL returns 0.04%
    daily") and checks the function behaves correctly FOR THOSE NUMBERS.
    Hypothesis instead describes the SHAPE of valid input ("any covariance
    matrix," "any long-only weight vector") and then generates hundreds of
    different concrete examples within that shape automatically --
    including edge cases a human wouldn't think to write by hand (a
    covariance matrix that's nearly singular, a weight vector where one
    asset is 99.99% of the portfolio, a P&L array where every value is
    identical). If a test fails, Hypothesis automatically "shrinks" the
    failing example down to the smallest, simplest input that still
    reproduces the failure -- making the root cause far easier to see
    than a failure buried in a 10,000-simulation array.

WHAT THIS FILE DELIBERATELY DOES NOT TEST:
    It does not re-test full end-to-end pipelines (run_var_analysis(),
    run_mpt_optimization(), run_stress_test_analysis()) with random
    holdings, since those require live yfinance data and network access
    is exactly the kind of external dependency Hypothesis examples
    shouldn't depend on. Instead, this file targets the PURE, DATA-IN
    DATA-OUT functions inside each engine -- the ones that take numbers
    and arrays directly, with no network or I/O involved -- since those
    are exactly what property-based testing is best suited for.
"""

from __future__ import annotations

import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from app.engine.monte_carlo_var import calculate_var, cholesky_decomposition
from app.engine.mpt_optimizer import (
    annualise_parameters,
    compute_portfolio_stats,
    simulate_random_portfolios,
)
from app.engine.stress_test import apply_price_shocks

# Applied to every test in this file: Hypothesis' default "test taking too
# long" health check fires easily on numerically heavier tests (Cholesky
# decomposition, matrix products) even when each individual run is fast,
# simply because we run MANY examples. Suppressing it here is safe --
# these tests still have a hard ceiling via max_examples on each @given.
_SUPPRESS_SLOW = settings(
    max_examples=100, suppress_health_check=[HealthCheck.too_slow]
)

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM STRATEGIES
# ─────────────────────────────────────────────────────────────────────────────
# Hypothesis's built-in strategies (st.floats, st.integers, ...) generate
# generic values. For domain-specific objects like "a valid covariance
# matrix," we need to build our own strategies that only ever produce
# values satisfying the mathematical properties those objects require.


@st.composite
def mu_sigma_pair(draw, min_assets: int = 2, max_assets: int = 5):
    """
    Generate a random, CONSISTENT (mu, sigma) pair for a random number of
    assets between min_assets and max_assets.

    THE KEY TECHNIQUE (why sigma isn't just "a random matrix"):
        A covariance matrix must be symmetric and positive semi-definite
        (PSD) -- these aren't optional properties, they're what makes it
        a valid covariance matrix at all (variance can never be
        negative). A uniformly random matrix does NOT have this property
        in general.

        The standard trick: for ANY real matrix A (any shape, any
        values), the product A @ A.T is ALWAYS symmetric and PSD. This
        is a basic linear algebra fact (it's literally the Gram matrix
        of A's rows). So we draw a random matrix A, then use A @ A.T as
        our covariance matrix -- guaranteed valid by construction, no
        matter what random values ended up in A.

        We add a tiny epsilon * I (identity matrix) on top. This nudges
        the matrix from "positive SEMI-definite" (could have a zero
        eigenvalue) to strictly "positive DEFINITE" (all eigenvalues
        strictly positive) -- np.linalg.cholesky() requires strict
        positive-definiteness and raises LinAlgError on a merely
        semi-definite matrix (e.g. one where two rows happen to be
        perfectly correlated by construction).

    Returns:
        Tuple of (mu, sigma):
            mu:    1D array, shape (n_assets,) -- random daily mean
                   returns, small realistic magnitude.
            sigma: 2D array, shape (n_assets, n_assets) -- a guaranteed
                   valid covariance matrix.
    """
    n = draw(st.integers(min_value=min_assets, max_value=max_assets))

    mu = draw(
        arrays(
            dtype=np.float64,
            shape=(n,),
            elements=st.floats(
                min_value=-0.01,
                max_value=0.01,
                allow_nan=False,
                allow_infinity=False,
            ),
        )
    )

    a = draw(
        arrays(
            dtype=np.float64,
            shape=(n, n),
            elements=st.floats(
                min_value=-0.5,
                max_value=0.5,
                allow_nan=False,
                allow_infinity=False,
            ),
        )
    )
    sigma = a @ a.T + np.eye(n) * 1e-6

    return mu, sigma


@st.composite
def valid_weights(draw, n_assets: int):
    """
    Generate a random long-only weight vector, summing to exactly 1.0,
    for a GIVEN number of assets (n_assets is passed in rather than drawn
    here, so callers can align it with an already-drawn mu/sigma pair of
    the same size).

    TECHNIQUE: draw n_assets positive numbers, then divide each by their
    sum. This is exactly the same normalization trick used in
    simulate_random_portfolios() itself (see mpt_optimizer.py Section 2)
    -- guarantees every weight is >= 0 (long-only) and the vector sums to
    exactly 1.0 (fully invested), by construction.
    """
    raw = draw(
        arrays(
            dtype=np.float64,
            shape=(n_assets,),
            elements=st.floats(
                min_value=1e-6, max_value=1.0, allow_nan=False, allow_infinity=False
            ),
        )
    )
    return raw / raw.sum()


# ─────────────────────────────────────────────────────────────────────────────
# CLASS 1: calculate_var() — VaR/CVaR extraction (monte_carlo_var.py)
# ─────────────────────────────────────────────────────────────────────────────


class TestCalculateVarProperties:
    """
    Property-based tests for calculate_var(). These check invariants that
    must hold for ANY P&L distribution, not just realistic simulated
    ones -- deliberately including degenerate cases (all values
    identical, extreme outliers) that Hypothesis generates but a human
    writing examples by hand would likely skip.
    """

    @given(
        pnl=arrays(
            dtype=np.float64,
            shape=st.integers(min_value=20, max_value=500),
            elements=st.floats(
                min_value=-1_000_000,
                max_value=1_000_000,
                allow_nan=False,
                allow_infinity=False,
            ),
        ),
        confidence_level=st.floats(min_value=0.5, max_value=0.999),
    )
    @_SUPPRESS_SLOW
    def test_cvar_never_exceeds_var(self, pnl, confidence_level):
        """
        CORE INVARIANT: CVaR must always be <= VaR.

        CVaR is defined as the AVERAGE of every P&L value that is <= VaR
        (the tail). The average of a set of numbers that are all <= some
        threshold can never itself exceed that threshold -- this is true
        by the definition of an average, regardless of what the P&L
        values actually are. This must hold for literally ANY array of
        numbers, which is exactly what makes it a good property-based
        test: no hand-picked example is needed to "trust" this, it's
        checked against hundreds of auto-generated distributions.
        """
        result = calculate_var(pnl, confidence_level)
        assert result["cvar"] <= result["var"] + 1e-9

    @given(
        pnl=arrays(
            dtype=np.float64,
            shape=st.integers(min_value=20, max_value=500),
            elements=st.floats(
                min_value=-1_000_000,
                max_value=1_000_000,
                allow_nan=False,
                allow_infinity=False,
            ),
        ),
        confidence_level=st.floats(min_value=0.5, max_value=0.999),
    )
    @_SUPPRESS_SLOW
    def test_worst_case_never_exceeds_var(self, pnl, confidence_level):
        """The single worst simulated outcome can never be BETTER (higher)
        than VaR -- VaR is a percentile cutoff, so at least one value at
        or below it must exist, and the minimum is always <= any
        percentile at or above the 0th."""
        result = calculate_var(pnl, confidence_level)
        assert result["worst_case"] <= result["var"] + 1e-9

    @given(
        pnl=arrays(
            dtype=np.float64,
            shape=st.integers(min_value=20, max_value=500),
            elements=st.floats(
                min_value=-1_000_000,
                max_value=1_000_000,
                allow_nan=False,
                allow_infinity=False,
            ),
        ),
        confidence_level=st.floats(min_value=0.5, max_value=0.999),
    )
    @_SUPPRESS_SLOW
    def test_best_case_never_below_worst_case(self, pnl, confidence_level):
        """best_case (max) must never be less than worst_case (min) --
        trivially true for any non-empty array, but worth locking in as
        an explicit invariant of the function's output contract."""
        result = calculate_var(pnl, confidence_level)
        assert result["best_case"] >= result["worst_case"] - 1e-9


# ─────────────────────────────────────────────────────────────────────────────
# CLASS 2: cholesky_decomposition() — correlation structure (monte_carlo_var.py)
# ─────────────────────────────────────────────────────────────────────────────


class TestCholeskyDecompositionProperties:
    """
    Property-based tests for cholesky_decomposition(), which every
    simulation function in the codebase (run_monte_carlo(),
    run_monte_carlo_price_paths()) depends on to generate correlated
    random shocks.
    """

    @given(mu_sigma=mu_sigma_pair())
    @_SUPPRESS_SLOW
    def test_reconstructs_original_covariance_matrix(self, mu_sigma):
        """
        THE DEFINING PROPERTY of a Cholesky decomposition: for ANY valid
        covariance matrix, L @ L.T must equal the original matrix. This
        is the mathematical guarantee the whole correlated-shock-
        generation technique (see monte_carlo_var.py Section 4) depends
        on -- if this didn't hold, every downstream simulation would be
        generating shocks with the WRONG correlation structure.
        """
        _mu, sigma = mu_sigma
        L = cholesky_decomposition(sigma)
        reconstructed = L @ L.T
        np.testing.assert_allclose(reconstructed, sigma, atol=1e-6)

    @given(mu_sigma=mu_sigma_pair())
    @_SUPPRESS_SLOW
    def test_result_is_lower_triangular(self, mu_sigma):
        """L must be lower triangular -- every entry ABOVE the diagonal
        must be exactly zero, by definition of a Cholesky factor."""
        _mu, sigma = mu_sigma
        L = cholesky_decomposition(sigma)
        upper_triangle_excluding_diagonal = np.triu(L, k=1)
        np.testing.assert_array_equal(
            upper_triangle_excluding_diagonal,
            np.zeros_like(upper_triangle_excluding_diagonal),
        )


# ─────────────────────────────────────────────────────────────────────────────
# CLASS 3: MPT Optimizer functions (mpt_optimizer.py)
# ─────────────────────────────────────────────────────────────────────────────


class TestMptOptimizerProperties:
    """Property-based tests for the pure statistical functions in the MPT
    optimizer engine."""

    @given(mu_sigma=mu_sigma_pair())
    @_SUPPRESS_SLOW
    def test_annualise_parameters_scales_linearly(self, mu_sigma):
        """For ANY daily mu/sigma, annualising must multiply both by
        EXACTLY 252 (TRADING_DAYS) -- no exceptions, no special cases."""
        mu, sigma = mu_sigma
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        np.testing.assert_allclose(annual_mu, mu * 252)
        np.testing.assert_allclose(annual_sigma, sigma * 252)

    @given(
        mu_sigma=mu_sigma_pair(), n_portfolios=st.integers(min_value=50, max_value=300)
    )
    @_SUPPRESS_SLOW
    def test_simulated_portfolio_weights_always_valid(self, mu_sigma, n_portfolios):
        """For ANY valid mu/sigma, every simulated random portfolio's
        weights must be non-negative and sum to exactly 1.0 -- the
        long-only, fully-invested constraint must never be violated
        regardless of how many assets or portfolios are simulated."""
        mu, sigma = mu_sigma
        n_assets = len(mu)
        result = simulate_random_portfolios(mu, sigma, n_assets, n_portfolios, 0.05)
        assert (result["weights"] >= 0).all()
        row_sums = result["weights"].sum(axis=1)
        np.testing.assert_allclose(row_sums, np.ones(n_portfolios), atol=1e-9)

    @given(
        mu_sigma=mu_sigma_pair(), n_portfolios=st.integers(min_value=50, max_value=300)
    )
    @_SUPPRESS_SLOW
    def test_simulated_portfolio_volatility_never_negative(
        self, mu_sigma, n_portfolios
    ):
        """Volatility (a standard deviation) can never be negative for
        ANY valid covariance matrix or weight combination."""
        mu, sigma = mu_sigma
        n_assets = len(mu)
        result = simulate_random_portfolios(mu, sigma, n_assets, n_portfolios, 0.05)
        assert (result["volatilities"] >= 0).all()

    @given(mu_sigma=mu_sigma_pair())
    @_SUPPRESS_SLOW
    def test_portfolio_stats_weights_dict_sums_to_one(self, mu_sigma):
        """For ANY valid weight vector, compute_portfolio_stats()'s
        returned weights dict must sum to 1.0, matching the input."""
        mu, sigma = mu_sigma
        n_assets = len(mu)
        weights_vec = np.full(n_assets, 1.0 / n_assets)
        tickers = [f"ASSET_{i}" for i in range(n_assets)]
        result = compute_portfolio_stats(weights_vec, mu, sigma, 0.05, tickers)
        assert abs(sum(result["weights"].values()) - 1.0) < 1e-9


# ─────────────────────────────────────────────────────────────────────────────
# CLASS 4: Stress Test engine (stress_test.py)
# ─────────────────────────────────────────────────────────────────────────────


class TestStressTestProperties:
    """Property-based tests for apply_price_shocks() -- the pure
    reweighting math behind the Stress Test module."""

    @given(
        n_assets=st.integers(min_value=2, max_value=6),
        portfolio_value=st.floats(
            min_value=100.0, max_value=10_000_000.0, allow_nan=False
        ),
        data=st.data(),
    )
    @_SUPPRESS_SLOW
    def test_shocked_weights_always_sum_to_one(self, n_assets, portfolio_value, data):
        """
        For ANY starting portfolio and ANY combination of price shocks
        (each bounded away from -1.0, so the portfolio never hits zero
        value -- that specific edge case is already covered by a
        dedicated deterministic test in test_stress_test.py), the
        resulting shocked weights must still sum to exactly 1.0. A shock
        redistributes value between assets -- it can never cause the
        weights to stop describing a complete (100%) allocation.
        """
        tickers = [f"ASSET_{i}" for i in range(n_assets)]
        weights_arr = data.draw(valid_weights(n_assets))
        portfolio = dict(zip(tickers, weights_arr, strict=True))

        # Bounded to (-0.9, 5.0): comfortably away from the -1.0 floor
        # that would zero out an individual position, so this test
        # focuses purely on the "weights still sum to 1" property rather
        # than re-testing the already-covered zero-value edge case.
        shocks = {
            ticker: data.draw(
                st.floats(
                    min_value=-0.9, max_value=5.0, allow_nan=False, allow_infinity=False
                )
            )
            for ticker in tickers
        }

        shocked_weights, _shocked_value = apply_price_shocks(
            portfolio, portfolio_value, shocks
        )
        assert abs(sum(shocked_weights.values()) - 1.0) < 1e-6

    @given(
        n_assets=st.integers(min_value=2, max_value=6),
        portfolio_value=st.floats(
            min_value=100.0, max_value=10_000_000.0, allow_nan=False
        ),
        data=st.data(),
    )
    @_SUPPRESS_SLOW
    def test_no_shocks_leaves_value_and_weights_unchanged(
        self, n_assets, portfolio_value, data
    ):
        """With an EMPTY price_shocks dict, the resulting portfolio value
        and every weight must be unchanged from the input, regardless of
        how many assets or what the starting weights were."""
        tickers = [f"ASSET_{i}" for i in range(n_assets)]
        weights_arr = data.draw(valid_weights(n_assets))
        portfolio = dict(zip(tickers, weights_arr, strict=True))

        shocked_weights, shocked_value = apply_price_shocks(
            portfolio, portfolio_value, {}
        )

        assert abs(shocked_value - portfolio_value) < 1e-6
        for ticker in tickers:
            assert abs(shocked_weights[ticker] - portfolio[ticker]) < 1e-9

    @given(
        n_assets=st.integers(min_value=2, max_value=6),
        portfolio_value=st.floats(
            min_value=100.0, max_value=10_000_000.0, allow_nan=False
        ),
        data=st.data(),
    )
    @_SUPPRESS_SLOW
    def test_shocked_weights_always_non_negative(self, n_assets, portfolio_value, data):
        """Since every individual shock is bounded above -1.0 (see the
        module docstring and API validation), no individual asset's
        shocked dollar value -- and therefore no resulting weight -- can
        ever go negative."""
        tickers = [f"ASSET_{i}" for i in range(n_assets)]
        weights_arr = data.draw(valid_weights(n_assets))
        portfolio = dict(zip(tickers, weights_arr, strict=True))

        shocks = {
            ticker: data.draw(
                st.floats(
                    min_value=-0.9, max_value=5.0, allow_nan=False, allow_infinity=False
                )
            )
            for ticker in tickers
        }

        shocked_weights, _shocked_value = apply_price_shocks(
            portfolio, portfolio_value, shocks
        )
        assert all(weight >= 0 for weight in shocked_weights.values())
