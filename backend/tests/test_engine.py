"""
Riskfolio — Pytest Test Suite for Monte Carlo VaR Engine
---------------------------------------------------------
Tests the mathematical correctness and robustness of each
function in monte_carlo_var.py.

Run with:
    pytest test_engine.py -v

The -v flag (verbose) prints each test name and pass/fail
status individually, which is cleaner to read.
"""

import pytest
import numpy as np
import pandas as pd
from monte_carlo_var import (
    compute_log_returns,
    compute_statistics,
    cholesky_decomposition,
    run_monte_carlo,
    calculate_var,
)

# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────
# Fixtures are reusable pieces of test data that
# multiple tests can share. Instead of recreating
# the same data in every test, you define it once
# here and pytest injects it automatically.

@pytest.fixture
def sample_prices():
    """
    A small synthetic price DataFrame mimicking 3 stocks
    over 10 trading days. We use synthetic data here (not
    real yfinance data) so tests are:
    - Fast (no network call)
    - Deterministic (same data every time)
    - Independent (don't break if Yahoo Finance is down)
    """
    np.random.seed(42)
    dates = pd.date_range(start="2023-01-01", periods=10, freq="B")  # B = business days
    data = {
        "AAPL":  [150.0, 152.0, 151.5, 153.0, 154.0, 153.5, 155.0, 156.0, 155.5, 157.0],
        "TSLA":  [200.0, 198.0, 202.0, 205.0, 203.0, 207.0, 210.0, 208.0, 212.0, 215.0],
        "GOOGL": [100.0, 101.0, 100.5, 102.0, 103.0, 102.5, 104.0, 105.0, 104.5, 106.0],
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def sample_log_returns(sample_prices):
    """Log returns derived from sample_prices — shared across multiple tests."""
    return compute_log_returns(sample_prices)


@pytest.fixture
def sample_statistics(sample_log_returns):
    """Mean vector and covariance matrix derived from sample_log_returns."""
    return compute_statistics(sample_log_returns)


@pytest.fixture
def sample_weights():
    """A valid portfolio weight vector summing to 1.0."""
    return np.array([0.4, 0.3, 0.3])


# ─────────────────────────────────────────────
# SECTION 2 TESTS: LOG RETURNS
# ─────────────────────────────────────────────

class TestComputeLogReturns:

    def test_output_shape(self, sample_prices, sample_log_returns):
        """
        Log returns should have exactly one fewer row than prices
        because the first row is dropped (no previous day to compare).
        """
        assert len(sample_log_returns) == len(sample_prices) - 1

    def test_correct_number_of_columns(self, sample_prices, sample_log_returns):
        """
        Number of columns (tickers) should be preserved.
        """
        assert sample_log_returns.shape[1] == sample_prices.shape[1]

    def test_no_nan_values(self, sample_log_returns):
        """
        After dropping the first row, there should be no NaN values
        remaining in the log returns DataFrame.
        """
        assert not sample_log_returns.isnull().values.any()

    def test_log_return_formula(self, sample_prices, sample_log_returns):
        """
        Verify the log return formula is correct by manually computing
        the first return for AAPL and comparing:
            r = ln(P_t / P_{t-1}) = ln(152.0 / 150.0)
        """
        expected = np.log(152.0 / 150.0)
        actual = sample_log_returns["AAPL"].iloc[0]
        assert abs(actual - expected) < 1e-10


# ─────────────────────────────────────────────
# SECTION 3 TESTS: STATISTICS
# ─────────────────────────────────────────────

class TestComputeStatistics:

    def test_mu_shape(self, sample_statistics, sample_prices):
        """
        Mean return vector should have one value per asset.
        Shape should be (n_assets,) = (3,) for our 3-stock portfolio.
        """
        mu, _ = sample_statistics
        assert mu.shape == (sample_prices.shape[1],)

    def test_sigma_shape(self, sample_statistics, sample_prices):
        """
        Covariance matrix should be square: (n_assets x n_assets).
        For 3 stocks this should be (3, 3).
        """
        _, sigma = sample_statistics
        n = sample_prices.shape[1]
        assert sigma.shape == (n, n)

    def test_sigma_is_symmetric(self, sample_statistics):
        """
        A valid covariance matrix must be symmetric:
        sigma[i][j] == sigma[j][i] for all i, j.
        This is a mathematical property of covariance.
        """
        _, sigma = sample_statistics
        assert np.allclose(sigma, sigma.T)

    def test_sigma_diagonal_is_positive(self, sample_statistics):
        """
        Diagonal entries of the covariance matrix are variances —
        they must always be positive (variance can never be negative).
        """
        _, sigma = sample_statistics
        assert np.all(np.diag(sigma) > 0)


# ─────────────────────────────────────────────
# SECTION 4 TESTS: CHOLESKY DECOMPOSITION
# ─────────────────────────────────────────────

class TestCholeskyDecomposition:

    def test_reconstruction(self, sample_statistics):
        """
        The fundamental property of Cholesky decomposition:
            L @ L.T must equal the original covariance matrix Sigma.
        We verify this holds within floating point tolerance.
        """
        _, sigma = sample_statistics
        L = cholesky_decomposition(sigma)
        reconstructed = L @ L.T
        assert np.allclose(reconstructed, sigma)

    def test_lower_triangular(self, sample_statistics):
        """
        Cholesky produces a lower triangular matrix —
        all entries above the diagonal must be zero.
        np.tril extracts the lower triangle; if L equals
        its own lower triangle, it's lower triangular.
        """
        _, sigma = sample_statistics
        L = cholesky_decomposition(sigma)
        assert np.allclose(L, np.tril(L))

    def test_output_shape(self, sample_statistics):
        """
        L should have the same shape as the covariance matrix.
        """
        _, sigma = sample_statistics
        L = cholesky_decomposition(sigma)
        assert L.shape == sigma.shape


# ─────────────────────────────────────────────
# SECTION 5 TESTS: MONTE CARLO SIMULATION
# ─────────────────────────────────────────────

class TestRunMonteCarlo:

    def test_output_length(self, sample_statistics, sample_weights):
        """
        The simulation should return exactly n_simulations P&L values.
        """
        mu, sigma = sample_statistics
        n_simulations = 1000
        result = run_monte_carlo(mu, sigma, sample_weights, 10_000, 1, n_simulations)
        assert len(result) == n_simulations

    def test_output_is_numpy_array(self, sample_statistics, sample_weights):
        """
        Output should be a NumPy array, not a list or DataFrame.
        """
        mu, sigma = sample_statistics
        result = run_monte_carlo(mu, sigma, sample_weights, 10_000, 1, 1000)
        assert isinstance(result, np.ndarray)

    def test_contains_both_gains_and_losses(self, sample_statistics, sample_weights):
        """
        With enough simulations, the distribution should contain both
        positive (gains) and negative (losses) P&L values.
        A realistic simulation should never produce only gains or only losses.
        """
        mu, sigma = sample_statistics
        result = run_monte_carlo(mu, sigma, sample_weights, 10_000, 1, 10_000)
        assert np.any(result > 0), "Expected some positive P&L values (gains)"
        assert np.any(result < 0), "Expected some negative P&L values (losses)"

    def test_scales_linearly_with_portfolio_value(self, sample_statistics, sample_weights):
        """
        VaR (and all P&L values) should scale linearly with portfolio_value.
        If we double the portfolio value with the same random seed,
        all P&L values should exactly double.
        """
        mu, sigma = sample_statistics
        np.random.seed(42)
        result_10k = run_monte_carlo(mu, sigma, sample_weights, 10_000, 1, 1000)
        np.random.seed(42)
        result_20k = run_monte_carlo(mu, sigma, sample_weights, 20_000, 1, 1000)
        assert np.allclose(result_20k, result_10k * 2)

    def test_longer_horizon_increases_spread(self, sample_statistics, sample_weights):
        """
        A longer time horizon should produce a wider spread of outcomes
        (higher standard deviation of P&L) because uncertainty grows
        with time per the square root of time rule.
        """
        mu, sigma = sample_statistics
        np.random.seed(42)
        result_1day = run_monte_carlo(mu, sigma, sample_weights, 10_000, 1, 10_000)
        np.random.seed(42)
        result_22day = run_monte_carlo(mu, sigma, sample_weights, 10_000, 22, 10_000)
        assert np.std(result_22day) > np.std(result_1day)


# ─────────────────────────────────────────────
# SECTION 6 TESTS: VaR CALCULATION
# ─────────────────────────────────────────────

class TestCalculateVar:

    @pytest.fixture
    def sample_pnl(self, sample_statistics, sample_weights):
        """Simulated P&L array used across VaR tests."""
        mu, sigma = sample_statistics
        np.random.seed(42)
        return run_monte_carlo(mu, sigma, sample_weights, 10_000, 1, 10_000)

    def test_var_is_negative(self, sample_pnl):
        """
        VaR represents a loss, so the raw var value should be negative.
        (var_positive is the absolute value used for display.)
        """
        results = calculate_var(sample_pnl, 0.95)
        assert results["var"] < 0

    def test_var_positive_equals_abs_var(self, sample_pnl):
        """
        var_positive should be exactly the absolute value of var.
        """
        results = calculate_var(sample_pnl, 0.95)
        assert results["var_positive"] == abs(results["var"])

    def test_cvar_worse_than_var(self, sample_pnl):
        """
        CVaR (Expected Shortfall) must always be worse (more negative)
        than VaR — it's the average of outcomes BEYOND the VaR threshold,
        so it should always be a larger loss than VaR itself.
        """
        results = calculate_var(sample_pnl, 0.95)
        assert results["cvar"] <= results["var"]

    def test_worst_case_worse_than_cvar(self, sample_pnl):
        """
        The single worst simulation must be worse than or equal to CVaR,
        since CVaR is an average of the tail and worst case is the extreme.
        """
        results = calculate_var(sample_pnl, 0.95)
        assert results["worst_case"] <= results["cvar"]

    def test_best_case_is_positive(self, sample_pnl):
        """
        With a large enough simulation, the best case should be a gain.
        """
        results = calculate_var(sample_pnl, 0.95)
        assert results["best_case"] > 0

    def test_correct_number_of_simulations(self, sample_pnl):
        """
        n_simulations in the results dict should match the actual
        length of the P&L array passed in.
        """
        results = calculate_var(sample_pnl, 0.95)
        assert results["n_simulations"] == len(sample_pnl)

    def test_higher_confidence_gives_higher_var(self, sample_pnl):
        """
        A higher confidence level means we're covering more of the
        distribution, so the VaR threshold should be a larger loss.
        99% VaR should be worse (more negative) than 95% VaR.
        """
        results_95 = calculate_var(sample_pnl, 0.95)
        results_99 = calculate_var(sample_pnl, 0.99)
        assert results_99["var"] <= results_95["var"]


# ─────────────────────────────────────────────
# EDGE CASE TESTS
# ─────────────────────────────────────────────

class TestEdgeCases:

    def test_single_asset_portfolio(self):
        """
        A single-stock portfolio should work correctly —
        the covariance matrix is just a 1x1 matrix (the variance).
        This tests the single-ticker edge case we handle in yfinance fetch.
        """
        np.random.seed(42)
        # Synthetic single-asset log returns
        single_returns = pd.DataFrame({
            "AAPL": np.random.normal(0.001, 0.02, 252)
        })
        mu, sigma = compute_statistics(single_returns)
        weights = np.array([1.0])
        result = run_monte_carlo(mu, sigma, weights, 10_000, 1, 1000)
        assert len(result) == 1000

    def test_weights_must_sum_to_one(self, sample_statistics):
        """
        The engine should raise an AssertionError if portfolio weights
        don't sum to 1.0 — this is our input validation guard.
        """
        mu, sigma = sample_statistics
        bad_weights = np.array([0.5, 0.3, 0.3])  # sums to 1.1
        portfolio = {"AAPL": 0.5, "TSLA": 0.3, "GOOGL": 0.3}

        with pytest.raises(AssertionError):
            from monte_carlo_var import run_var_analysis
            run_var_analysis(portfolio, 10_000, horizon=1)

    def test_equal_weight_portfolio(self, sample_statistics):
        """
        An equally weighted portfolio (1/n per asset) should run
        without errors and return valid results.
        """
        mu, sigma = sample_statistics
        n = len(mu)
        equal_weights = np.array([1/n] * n)
        result = run_monte_carlo(mu, sigma, equal_weights, 10_000, 1, 1000)
        assert len(result) == 1000
        assert not np.any(np.isnan(result)), "Result should not contain NaN values"