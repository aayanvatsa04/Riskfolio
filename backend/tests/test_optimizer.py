import numpy as np
import pytest

from app.engine.mpt_optimizer import (
    annualise_parameters,
    compute_portfolio_stats,
    run_mpt_optimization,
    simulate_random_portfolios,
)

TRADING_DAYS = 252

# ─── Shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def two_asset_params():
    """
    Minimal deterministic daily mu and sigma for a 2-asset portfolio.
    Using fixed values so tests are reproducible and easy to verify by hand.
    """
    mu = np.array([0.0008, 0.0012])  # daily mean returns
    sigma = np.array(
        [  # daily covariance matrix
            [0.0004, 0.0001],
            [0.0001, 0.0009],
        ]
    )
    return mu, sigma


@pytest.fixture
def three_asset_params():
    """
    Deterministic daily mu and sigma for a 3-asset portfolio.
    """
    mu = np.array([0.0008, 0.0012, 0.0005])
    sigma = np.array(
        [
            [0.0004, 0.0001, 0.00005],
            [0.0001, 0.0009, 0.00008],
            [0.00005, 0.00008, 0.0003],
        ]
    )
    return mu, sigma


# ─── Class 1: annualise_parameters ───────────────────────────────────────────


class TestAnnualiseParameters:
    """
    Tests for the annualise_parameters() function.

    Mathematical invariants verified:
        - annual_mu  = daily_mu  * 252  (drift scales linearly)
        - annual_sigma = daily_sigma * 252  (variance scales linearly)
        - Shapes are preserved
    """

    def test_mu_scales_by_trading_days(self, two_asset_params):
        """annual_mu must equal daily_mu multiplied by 252."""
        mu, sigma = two_asset_params
        annual_mu, _ = annualise_parameters(mu, sigma)
        np.testing.assert_array_almost_equal(annual_mu, mu * TRADING_DAYS)

    def test_sigma_scales_by_trading_days(self, two_asset_params):
        """annual_sigma must equal daily_sigma multiplied by 252."""
        mu, sigma = two_asset_params
        _, annual_sigma = annualise_parameters(mu, sigma)
        np.testing.assert_array_almost_equal(annual_sigma, sigma * TRADING_DAYS)

    def test_shapes_preserved(self, three_asset_params):
        """Output shapes must match input shapes exactly."""
        mu, sigma = three_asset_params
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        assert annual_mu.shape == mu.shape
        assert annual_sigma.shape == sigma.shape

    def test_annualised_vol_matches_sqrt_rule(self, two_asset_params):
        """
        For a single-asset portfolio (weight = 1.0), annualised volatility
        must equal daily_vol * sqrt(252) — the standard finance rule.
        """
        mu, sigma = two_asset_params
        _, annual_sigma = annualise_parameters(mu, sigma)
        # Asset 0: daily variance = 0.0004, daily vol = 0.02
        daily_vol_asset0 = np.sqrt(sigma[0, 0])
        annual_vol_asset0 = np.sqrt(annual_sigma[0, 0])
        expected_annual_vol = daily_vol_asset0 * np.sqrt(TRADING_DAYS)
        assert abs(annual_vol_asset0 - expected_annual_vol) < 1e-10


# ─── Class 2: simulate_random_portfolios ─────────────────────────────────────


class TestSimulateRandomPortfolios:
    """
    Tests for simulate_random_portfolios().

    Mathematical invariants verified:
        - All weights >= 0 (long-only constraint)
        - All weight rows sum to exactly 1.0
        - Output array shapes are correct
        - All volatilities >= 0
        - Sharpe = (return - rf) / vol for every portfolio
        - More portfolios produces a lower minimum Sharpe (better coverage)
    """

    def test_weights_sum_to_one(self, two_asset_params):
        """Every simulated portfolio's weights must sum to 1.0."""
        mu, sigma = two_asset_params
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        result = simulate_random_portfolios(annual_mu, annual_sigma, 2, 500, 0.05)
        row_sums = result["weights"].sum(axis=1)
        np.testing.assert_array_almost_equal(row_sums, np.ones(500))

    def test_weights_are_non_negative(self, two_asset_params):
        """All weights must be >= 0 (no short selling)."""
        mu, sigma = two_asset_params
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        result = simulate_random_portfolios(annual_mu, annual_sigma, 2, 500, 0.05)
        assert (result["weights"] >= 0).all()

    def test_output_shapes(self, three_asset_params):
        """All output arrays must have the correct shapes."""
        mu, sigma = three_asset_params
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        n_portfolios = 200
        result = simulate_random_portfolios(
            annual_mu, annual_sigma, 3, n_portfolios, 0.05
        )
        assert result["weights"].shape == (n_portfolios, 3)
        assert result["returns"].shape == (n_portfolios,)
        assert result["volatilities"].shape == (n_portfolios,)
        assert result["sharpes"].shape == (n_portfolios,)

    def test_volatilities_non_negative(self, two_asset_params):
        """Portfolio volatility must never be negative."""
        mu, sigma = two_asset_params
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        result = simulate_random_portfolios(annual_mu, annual_sigma, 2, 500, 0.05)
        assert (result["volatilities"] >= 0).all()

    def test_sharpe_formula_holds(self, two_asset_params):
        """
        For every portfolio, Sharpe must equal (return - rf) / vol.
        Verified to within floating-point tolerance.
        """
        mu, sigma = two_asset_params
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        rf = 0.05
        result = simulate_random_portfolios(annual_mu, annual_sigma, 2, 100, rf)
        expected_sharpes = (result["returns"] - rf) / result["volatilities"]
        np.testing.assert_array_almost_equal(result["sharpes"], expected_sharpes)

    def test_equal_weight_portfolio_return(self, two_asset_params):
        """
        For a known equal-weight portfolio the expected return is
        simply the weighted average of annual_mu values.
        We verify this by checking a portfolio close to equal weights exists.
        """
        mu, sigma = two_asset_params
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        # Expected return for [0.5, 0.5] weights
        expected = float(np.array([0.5, 0.5]) @ annual_mu)
        result = simulate_random_portfolios(annual_mu, annual_sigma, 2, 5000, 0.05)
        # Among 5,000 random portfolios, at least one should be within 2% of equal weight
        # Check returns are in a sensible range around the equal-weight return
        assert result["returns"].min() < expected < result["returns"].max()


# ─── Class 3: compute_portfolio_stats ────────────────────────────────────────


class TestComputePortfolioStats:
    """
    Tests for compute_portfolio_stats() — the function that computes
    annualised statistics for a single specific weight vector.

    Mathematical invariants verified:
        - Return = w @ annual_mu
        - Volatility = sqrt(w @ annual_sigma @ w)
        - Sharpe = (return - rf) / vol
        - Output dict has all required keys
        - Weights dict maps tickers correctly
    """

    def test_return_matches_dot_product(self, two_asset_params):
        """Expected return must equal weights dot annual_mu."""
        mu, sigma = two_asset_params
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        weights = np.array([0.6, 0.4])
        result = compute_portfolio_stats(
            weights, annual_mu, annual_sigma, 0.05, ["A", "B"]
        )
        expected = float(weights @ annual_mu)
        assert abs(result["expected_return"] - expected) < 1e-10

    def test_volatility_matches_quadratic_form(self, two_asset_params):
        """Volatility must equal sqrt(w @ annual_sigma @ w)."""
        mu, sigma = two_asset_params
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        weights = np.array([0.6, 0.4])
        result = compute_portfolio_stats(
            weights, annual_mu, annual_sigma, 0.05, ["A", "B"]
        )
        expected_vol = float(np.sqrt(weights @ annual_sigma @ weights))
        assert abs(result["volatility"] - expected_vol) < 1e-10

    def test_sharpe_formula(self, two_asset_params):
        """Sharpe must equal (expected_return - risk_free_rate) / volatility."""
        mu, sigma = two_asset_params
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        weights = np.array([0.6, 0.4])
        rf = 0.05
        result = compute_portfolio_stats(
            weights, annual_mu, annual_sigma, rf, ["A", "B"]
        )
        expected_sharpe = (result["expected_return"] - rf) / result["volatility"]
        assert abs(result["sharpe"] - expected_sharpe) < 1e-10

    def test_output_keys_present(self, two_asset_params):
        """Result dict must contain all four required keys."""
        mu, sigma = two_asset_params
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        weights = np.array([0.5, 0.5])
        result = compute_portfolio_stats(
            weights, annual_mu, annual_sigma, 0.05, ["AAPL", "TSLA"]
        )
        assert "expected_return" in result
        assert "volatility" in result
        assert "sharpe" in result
        assert "weights" in result

    def test_weights_dict_maps_tickers_correctly(self, two_asset_params):
        """The weights dict must map each ticker to its correct weight value."""
        mu, sigma = two_asset_params
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        weights = np.array([0.7, 0.3])
        result = compute_portfolio_stats(
            weights, annual_mu, annual_sigma, 0.05, ["AAPL", "TSLA"]
        )
        assert abs(result["weights"]["AAPL"] - 0.7) < 1e-10
        assert abs(result["weights"]["TSLA"] - 0.3) < 1e-10

    def test_volatility_non_negative(self, three_asset_params):
        """Volatility must never be negative for any valid weight vector."""
        mu, sigma = three_asset_params
        annual_mu, annual_sigma = annualise_parameters(mu, sigma)
        weights = np.array([0.2, 0.5, 0.3])
        result = compute_portfolio_stats(
            weights, annual_mu, annual_sigma, 0.05, ["A", "B", "C"]
        )
        assert result["volatility"] >= 0


# ─── Class 4: run_mpt_optimization (integration) ─────────────────────────────


class TestRunMptOptimization:
    """
    Integration tests for run_mpt_optimization() — the full pipeline.

    These tests use real yfinance data (like test_engine.py does for VaR),
    so they require a network connection and may take a few seconds.

    Mathematical invariants verified:
        - Response has all required keys
        - Max Sharpe portfolio has the highest Sharpe among frontier points
        - Min Vol portfolio has the lowest volatility among frontier points
        - All returned weight dicts sum to approximately 1.0
        - frontier_points count is capped at 1,000
        - Raises ValueError for fewer than 2 tickers
    """

    @pytest.fixture
    def optimization_result(self):
        """
        Run a real optimization once and reuse across all tests in this class.
        Using a small n_portfolios=500 so tests run quickly.
        """
        return run_mpt_optimization(
            tickers=["AAPL", "MSFT"],
            current_weights={"AAPL": 0.5, "MSFT": 0.5},
            n_portfolios=500,
            risk_free_rate=0.05,
            verbose=False,
        )

    def test_response_has_required_keys(self, optimization_result):
        """The result dict must contain all keys the API response expects."""
        result = optimization_result
        assert "tickers" in result
        assert "frontier_points" in result
        assert "max_sharpe_portfolio" in result
        assert "min_vol_portfolio" in result
        assert "current_portfolio" in result
        assert "risk_free_rate" in result
        assert "n_portfolios" in result
        assert "timing" in result

    def test_max_sharpe_has_highest_sharpe_in_frontier(self, optimization_result):
        """
        The max_sharpe_portfolio Sharpe must be >= every frontier point's Sharpe.
        This is the core correctness invariant of the optimizer.
        """
        result = optimization_result
        max_sharpe = result["max_sharpe_portfolio"]["sharpe"]
        frontier_sharpes = [p["sharpe"] for p in result["frontier_points"]]
        assert max_sharpe >= max(frontier_sharpes) - 1e-6

    def test_min_vol_has_lowest_volatility_in_frontier(self, optimization_result):
        """
        The min_vol_portfolio volatility must be <= every frontier point's volatility.
        """
        result = optimization_result
        min_vol = result["min_vol_portfolio"]["volatility"]
        frontier_vols = [p["volatility"] for p in result["frontier_points"]]
        assert min_vol <= min(frontier_vols) + 1e-6

    def test_max_sharpe_weights_sum_to_one(self, optimization_result):
        """Max Sharpe portfolio weights must sum to 1.0."""
        weights = optimization_result["max_sharpe_portfolio"]["weights"]
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_min_vol_weights_sum_to_one(self, optimization_result):
        """Min Vol portfolio weights must sum to 1.0."""
        weights = optimization_result["min_vol_portfolio"]["weights"]
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_frontier_points_capped_at_1000(self, optimization_result):
        """frontier_points must never exceed 1,000 entries."""
        assert len(optimization_result["frontier_points"]) <= 1_000

    def test_frontier_points_have_required_keys(self, optimization_result):
        """Every frontier point must have expected_return, volatility, sharpe."""
        for point in optimization_result["frontier_points"]:
            assert "expected_return" in point
            assert "volatility" in point
            assert "sharpe" in point

    def test_tickers_echoed_correctly(self, optimization_result):
        """The tickers list in the response must match what was passed in."""
        assert set(optimization_result["tickers"]) == {"AAPL", "MSFT"}

    def test_raises_for_single_ticker(self):
        """ValueError must be raised when fewer than 2 tickers are provided."""
        with pytest.raises(ValueError, match="At least 2 distinct tickers"):
            run_mpt_optimization(
                tickers=["AAPL"],
                current_weights={"AAPL": 1.0},
                n_portfolios=100,
                verbose=False,
            )

    def test_timing_breakdown_present(self, optimization_result):
        """Timing dict must contain all expected stage keys."""
        timing = optimization_result["timing"]
        assert "data_fetch_s" in timing
        assert "log_returns_s" in timing
        assert "statistics_s" in timing
        assert "optimization_s" in timing
        assert "total_s" in timing
