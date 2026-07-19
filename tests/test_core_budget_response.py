"""
Tests for core.budget_response  (fit.py, predict.py)

Run:  python -m pytest tests/test_core_budget_response.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.budget_response.fit import (
    fit_response_curve,
    fit_with_confidence,
    ResponseCurve,
)
from core.budget_response.predict import (
    predict_revenue,
    simulate_budget_scenarios,
    BudgetScenario,
)


# ===================================================================
# Helper: synthetic spend/revenue data with log-linear relationship
# ===================================================================

def _make_spend_revenue(n: int = 30, seed: int = 42) -> pd.DataFrame:
    """Generate data where revenue ≈ 600·ln(spend+1) + 500 + noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        spend = 500 + rng.integers(-200, 400)
        revenue = 600 * np.log(spend + 1) + 500 + rng.normal(0, 100)
        rows.append({
            "date": f"2026-06-{i+1:02d}",
            "spend": round(max(10, spend)),
            "revenue": round(max(0, revenue)),
            "sessions": round(max(0, revenue / 2)),
        })
    return pd.DataFrame(rows)


# ===================================================================
# fit — fit_response_curve
# ===================================================================

class TestFitResponseCurve:

    def test_fits_log_linear_data(self):
        df = _make_spend_revenue(30)
        curve = fit_response_curve(df)
        assert curve is not None
        assert curve.a > 0   # revenue increases with spend
        assert curve.r_squared > 0.3  # should get a decent fit
        assert curve.n_points == 30

    def test_returns_none_for_too_few_points(self):
        df = _make_spend_revenue(3)
        curve = fit_response_curve(df, min_points=7)
        assert curve is None

    def test_returns_none_for_missing_columns(self):
        df = pd.DataFrame({"foo": [1, 2, 3]})
        assert fit_response_curve(df) is None

    def test_spend_range_captured(self):
        df = _make_spend_revenue(20)
        curve = fit_response_curve(df)
        assert curve is not None
        assert curve.spend_min > 0
        assert curve.spend_max > curve.spend_min

    def test_predict_method(self):
        df = _make_spend_revenue(30)
        curve = fit_response_curve(df)
        assert curve is not None
        rev_low = curve.predict(100)
        rev_high = curve.predict(2000)
        # Diminishing returns: higher spend → higher revenue, but sub-linear
        assert rev_high > rev_low

    def test_to_dict(self):
        df = _make_spend_revenue(20)
        curve = fit_response_curve(df)
        assert curve is not None
        d = curve.to_dict()
        assert "a" in d
        assert "r_squared" in d
        assert isinstance(d["a"], float)

    def test_deterministic(self):
        """Same data → same curve, always."""
        df = _make_spend_revenue(25, seed=99)
        a = fit_response_curve(df)
        b = fit_response_curve(df)
        assert a is not None and b is not None
        assert a.a == b.a
        assert a.b == b.b


# ===================================================================
# fit — fit_with_confidence
# ===================================================================

class TestFitWithConfidence:

    def test_returns_curve_and_ci(self):
        df = _make_spend_revenue(30)
        curve, ci = fit_with_confidence(df, seed=42)
        assert curve is not None
        assert ci is not None
        low, high = ci
        assert low < high
        assert low <= curve.a <= high  # point estimate inside CI

    def test_deterministic_bootstrap(self):
        """Same seed → same CI bounds."""
        df = _make_spend_revenue(30)
        _, ci_a = fit_with_confidence(df, seed=7)
        _, ci_b = fit_with_confidence(df, seed=7)
        assert ci_a == ci_b

    def test_different_seeds_different_ci(self):
        df = _make_spend_revenue(30)
        _, ci_a = fit_with_confidence(df, seed=1)
        _, ci_b = fit_with_confidence(df, seed=2)
        # CIs should differ (extremely unlikely to be identical)
        assert ci_a != ci_b


# ===================================================================
# predict — predict_revenue
# ===================================================================

class TestPredictRevenue:

    def test_basic_prediction(self):
        df = _make_spend_revenue(30)
        curve = fit_response_curve(df)
        assert curve is not None
        rev = predict_revenue(curve, 1000)
        assert rev > 0

    def test_zero_spend_non_negative(self):
        df = _make_spend_revenue(30)
        curve = fit_response_curve(df)
        assert curve is not None
        rev = predict_revenue(curve, 0)
        assert rev >= 0

    def test_diminishing_returns(self):
        """Equal additive spend increases should yield decreasing revenue gains."""
        # Use a known curve directly to test the model property.
        curve = ResponseCurve(
            a=600.0, b=500.0, r_squared=0.9, n_points=30,
            spend_min=100, spend_max=1000,
        )
        # Equal additive steps: +1000 each time
        rev_1000 = predict_revenue(curve, 1000)
        rev_2000 = predict_revenue(curve, 2000)
        rev_3000 = predict_revenue(curve, 3000)
        gain_1 = rev_2000 - rev_1000  # going from 1000→2000
        gain_2 = rev_3000 - rev_2000  # going from 2000→3000
        assert gain_1 > 0
        assert gain_2 > 0
        assert gain_2 < gain_1  # diminishing returns on equal additive steps


# ===================================================================
# predict — simulate_budget_scenarios
# ===================================================================

class TestSimulateBudgetScenarios:

    def test_default_multipliers(self):
        df = _make_spend_revenue(30)
        curve = fit_response_curve(df)
        assert curve is not None
        scenarios = simulate_budget_scenarios(curve, baseline_spend=800)
        assert len(scenarios) == 6  # default 6 multipliers
        assert all(isinstance(s, BudgetScenario) for s in scenarios)

    def test_custom_multipliers(self):
        df = _make_spend_revenue(30)
        curve = fit_response_curve(df)
        assert curve is not None
        scenarios = simulate_budget_scenarios(
            curve, baseline_spend=800, multipliers=[0.5, 1.0, 3.0]
        )
        assert len(scenarios) == 3

    def test_baseline_is_1x(self):
        """At multiplier=1.0, delta_spend_pct should be 0."""
        df = _make_spend_revenue(30)
        curve = fit_response_curve(df)
        assert curve is not None
        scenarios = simulate_budget_scenarios(curve, baseline_spend=800)
        baseline = [s for s in scenarios if abs(s.delta_spend_pct) < 0.1]
        assert len(baseline) == 1
        assert abs(baseline[0].delta_revenue_pct) < 0.1

    def test_roas_populated(self):
        df = _make_spend_revenue(30)
        curve = fit_response_curve(df)
        assert curve is not None
        scenarios = simulate_budget_scenarios(curve, baseline_spend=800)
        for s in scenarios:
            assert s.predicted_roas > 0
            assert s.daily_spend > 0

    def test_higher_spend_higher_revenue(self):
        df = _make_spend_revenue(30)
        curve = fit_response_curve(df)
        assert curve is not None
        scenarios = simulate_budget_scenarios(
            curve, baseline_spend=800, multipliers=[0.5, 1.0, 2.0]
        )
        revs = [s.predicted_daily_revenue for s in scenarios]
        assert revs[0] < revs[1] < revs[2]
