"""
Riskfolio — Pytest Test Suite for the Stress Test Engine
-----------------------------------------------------------
Tests apply_price_shocks() (pure dollar-value reweighting math) and
run_stress_test_analysis() (the full baseline-vs-shocked pipeline).

Unlike test_optimizer.py's integration tests (which hit real yfinance
data), the integration tests here use a synthetic price fixture patched
in via monkeypatch — same approach as test_engine.py's sample_prices.
This keeps these tests fast, deterministic, and independent of network
availability, while still exercising the full real pipeline
(fetch -> log returns -> statistics -> Monte Carlo -> VaR) end to end.
"""

import numpy as np
import pandas as pd
import pytest

from app.engine import stress_test
from app.engine.stress_test import apply_price_shocks, run_stress_test_analysis

# ─── Shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_prices():
    """
    Synthetic 3-stock price history, same style as test_engine.py's
    sample_prices fixture — deterministic, fast, no network required.
    """
    np.random.seed(7)
    dates = pd.date_range(start="2023-01-01", periods=300, freq="B")
    n = len(dates)
    data = {
        "AAPL": 150 * np.exp(np.cumsum(np.random.normal(0.0006, 0.018, n))),
        "TSLA": 250 * np.exp(np.cumsum(np.random.normal(0.0004, 0.032, n))),
        "GOOGL": 120 * np.exp(np.cumsum(np.random.normal(0.0003, 0.020, n))),
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def simple_portfolio():
    """
    A round-number 3-asset portfolio, chosen so the reweighting math in
    apply_price_shocks() can be verified by hand (see module docstring's
    worked example: $10,000 total, 40/30/30 split).
    """
    return {"AAPL": 0.40, "TSLA": 0.30, "GOOGL": 0.30}


# ─── Class 1: apply_price_shocks ──────────────────────────────────────────────


class TestApplyPriceShocks:
    """
    Tests for apply_price_shocks() — pure dollar-value reweighting, no
    simulation involved.

    Mathematical invariants verified:
        - No shocks -> weights and portfolio value unchanged
        - A shocked asset's new weight matches hand-calculated arithmetic
        - Resulting weights always sum to 1.0
        - An unshocked asset's WEIGHT still changes (it's a bigger slice
          of a smaller pie), even though its own dollar value doesn't
        - Raises ValueError when combined shocks reduce total value to
          zero or below
    """

    def test_no_shocks_leaves_portfolio_unchanged(self, simple_portfolio):
        """With an empty price_shocks dict, weights and value must be identical
        to the input (within floating-point tolerance)."""
        weights, value = apply_price_shocks(simple_portfolio, 10_000.0, {})
        assert abs(value - 10_000.0) < 1e-9
        for ticker, weight in simple_portfolio.items():
            assert abs(weights[ticker] - weight) < 1e-9

    def test_matches_hand_calculated_example(self, simple_portfolio):
        """
        Verifies the exact worked example from the module docstring:
        $10,000 @ 40/30/30 (AAPL/TSLA/GOOGL), AAPL -15%, TSLA -30%.

            AAPL: $4,000 * 0.85 = $3,400
            TSLA: $3,000 * 0.70 = $2,100
            GOOGL: $3,000 * 1.00 = $3,000
            New total: $8,500
            New weights: AAPL 40.0%, TSLA 24.706%, GOOGL 35.294%
        """
        weights, value = apply_price_shocks(
            simple_portfolio, 10_000.0, {"AAPL": -0.15, "TSLA": -0.30}
        )
        assert abs(value - 8_500.0) < 1e-6
        assert abs(weights["AAPL"] - (3_400 / 8_500)) < 1e-9
        assert abs(weights["TSLA"] - (2_100 / 8_500)) < 1e-9
        assert abs(weights["GOOGL"] - (3_000 / 8_500)) < 1e-9

    def test_weights_always_sum_to_one(self, simple_portfolio):
        """Regardless of the shock combination, resulting weights must sum to 1.0."""
        weights, _value = apply_price_shocks(
            simple_portfolio, 10_000.0, {"AAPL": -0.5, "GOOGL": 0.25}
        )
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_unshocked_asset_weight_still_changes(self, simple_portfolio):
        """
        GOOGL is not shocked at all, but its WEIGHT must still increase,
        since it now makes up a larger slice of a smaller total portfolio.
        This is the key diversification-shifting effect described in the
        module docstring.
        """
        weights, _value = apply_price_shocks(
            simple_portfolio, 10_000.0, {"AAPL": -0.15, "TSLA": -0.30}
        )
        assert weights["GOOGL"] > simple_portfolio["GOOGL"]

    def test_raises_when_portfolio_value_hits_zero(self, simple_portfolio):
        """A -100% (or worse) shock on every asset must raise, not
        silently divide by zero or return a negative portfolio value.
        Note: -1.0 exactly means "this position is now worth $0" -- the
        API layer rejects shocks <= -1.0 before they ever reach this
        function (see StressTestRequest.validate_price_shocks), but this
        engine-level function is tested directly here regardless, since
        it may be called from other contexts without that validation."""
        with pytest.raises(ValueError, match="zero or negative"):
            apply_price_shocks(
                simple_portfolio,
                10_000.0,
                {"AAPL": -1.0, "TSLA": -1.0, "GOOGL": -1.0},
            )

    def test_ticker_not_in_shocks_defaults_to_zero(self, simple_portfolio):
        """A ticker absent from price_shocks must be treated as unshocked (0.0)."""
        weights, value = apply_price_shocks(simple_portfolio, 10_000.0, {"AAPL": -0.10})
        # TSLA and GOOGL dollar values are unchanged individually, even
        # though their WEIGHTS shift slightly due to the smaller total.
        expected_total = (0.40 * 10_000 * 0.90) + (0.30 * 10_000) + (0.30 * 10_000)
        assert abs(value - expected_total) < 1e-6


# ─── Class 2: run_stress_test_analysis (integration) ──────────────────────────


class TestRunStressTestAnalysis:
    """
    Integration tests for run_stress_test_analysis() — the full pipeline,
    using a synthetic (monkeypatched) price fixture rather than live
    yfinance data, so these tests are fast and deterministic.

    Mathematical invariants verified:
        - Response has all required keys, baseline and shocked share the
          same shape
        - Baseline reflects the ORIGINAL portfolio value/weights exactly
        - Shocked reflects the SHOCKED portfolio value/weights exactly
          (cross-checked against apply_price_shocks() directly)
        - volatility_multiplier <= 0 raises ValueError
        - No shocks at all -> baseline and shocked portfolio
          value/weights are identical (though P&L draws differ, since
          they're independent random simulations)
    """

    @pytest.fixture(autouse=True)
    def patch_price_fetch(self, monkeypatch, sample_prices):
        """Autouse: every test in this class gets synthetic prices instead
        of a real yfinance call, applied directly to the module under test."""
        monkeypatch.setattr(
            stress_test, "fetch_historical_prices", lambda tickers: sample_prices
        )

    @pytest.fixture
    def stress_result(self, simple_portfolio):
        return run_stress_test_analysis(
            portfolio=simple_portfolio,
            portfolio_value=10_000.0,
            price_shocks={"AAPL": -0.15, "TSLA": -0.30},
            volatility_multiplier=1.5,
            horizon=1,
            confidence_level=0.95,
            n_simulations=2_000,
            verbose=False,
        )

    def test_response_has_required_keys(self, stress_result):
        assert "tickers" in stress_result
        assert "baseline" in stress_result
        assert "shocked" in stress_result
        assert "shocks_applied" in stress_result
        assert "timing" in stress_result

    def test_baseline_and_shocked_have_matching_shape(self, stress_result):
        """baseline and shocked must have IDENTICAL key sets, so the
        frontend can render both through one shared component."""
        assert set(stress_result["baseline"].keys()) == set(
            stress_result["shocked"].keys()
        )

    def test_baseline_uses_original_portfolio_value(
        self, stress_result, simple_portfolio
    ):
        """Baseline must reflect the UNSHOCKED portfolio exactly."""
        assert abs(stress_result["baseline"]["portfolio_value"] - 10_000.0) < 1e-6
        for ticker, weight in simple_portfolio.items():
            assert (
                abs(stress_result["baseline"]["portfolio_weights"][ticker] - weight)
                < 1e-9
            )

    def test_shocked_matches_apply_price_shocks_directly(
        self, stress_result, simple_portfolio
    ):
        """
        Cross-check: the shocked portfolio_value/weights in the pipeline's
        output must exactly match calling apply_price_shocks() directly
        with the same inputs -- proving the pipeline doesn't silently
        apply the shock differently internally.
        """
        expected_weights, expected_value = apply_price_shocks(
            simple_portfolio, 10_000.0, {"AAPL": -0.15, "TSLA": -0.30}
        )
        assert abs(stress_result["shocked"]["portfolio_value"] - expected_value) < 1e-6
        for ticker, weight in expected_weights.items():
            assert (
                abs(stress_result["shocked"]["portfolio_weights"][ticker] - weight)
                < 1e-9
            )

    def test_shocks_applied_echoes_input(self, stress_result):
        """shocks_applied must echo back exactly what was requested."""
        assert stress_result["shocks_applied"]["price_shocks"] == {
            "AAPL": -0.15,
            "TSLA": -0.30,
        }
        assert stress_result["shocks_applied"]["volatility_multiplier"] == 1.5

    def test_no_shocks_baseline_and_shocked_share_same_portfolio(
        self, simple_portfolio
    ):
        """
        With price_shocks={} and volatility_multiplier=1.0, baseline and
        shocked should describe the IDENTICAL portfolio (same value, same
        weights) -- they'll still show slightly different VaR/CVaR
        numbers since each is an independent random Monte Carlo draw, but
        the portfolio itself hasn't changed at all.
        """
        result = run_stress_test_analysis(
            portfolio=simple_portfolio,
            portfolio_value=10_000.0,
            price_shocks={},
            volatility_multiplier=1.0,
            n_simulations=2_000,
        )
        assert (
            abs(
                result["baseline"]["portfolio_value"]
                - result["shocked"]["portfolio_value"]
            )
            < 1e-6
        )
        for ticker in simple_portfolio:
            assert (
                abs(
                    result["baseline"]["portfolio_weights"][ticker]
                    - result["shocked"]["portfolio_weights"][ticker]
                )
                < 1e-9
            )

    def test_raises_for_non_positive_volatility_multiplier(self, simple_portfolio):
        """volatility_multiplier <= 0 must raise, not silently produce a
        degenerate (zero or negative variance) simulation."""
        with pytest.raises(ValueError, match="positive"):
            run_stress_test_analysis(
                portfolio=simple_portfolio,
                portfolio_value=10_000.0,
                volatility_multiplier=0.0,
            )

    def test_timing_breakdown_present(self, stress_result):
        timing = stress_result["timing"]
        assert "data_fetch_s" in timing
        assert "log_returns_s" in timing
        assert "statistics_s" in timing
        assert "baseline_simulation_s" in timing
        assert "shocked_simulation_s" in timing
        assert "total_s" in timing
