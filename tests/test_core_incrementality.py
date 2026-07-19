"""
Tests for core.incrementality  (signal.py)

Run:  python -m pytest tests/test_core_incrementality.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.incrementality.signal import (
    estimate_incrementality,
    IncrementalityResult,
    INCREMENTALITY_DISCLAIMER,
)


# ===================================================================
# Helper
# ===================================================================

def _make_spend_revenue(n: int = 30, seed: int = 42) -> pd.DataFrame:
    """Synthetic data: revenue ≈ 600·ln(spend+1) + 500 + noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        spend = 500 + rng.integers(-200, 400)
        revenue = 600 * np.log(spend + 1) + 500 + rng.normal(0, 100)
        rows.append({
            "date": f"2026-06-{i+1:02d}",
            "spend": round(max(10, spend)),
            "revenue": round(max(0, revenue)),
        })
    return pd.DataFrame(rows)


# ===================================================================
# Tests
# ===================================================================

class TestEstimateIncrementality:

    def test_returns_result(self):
        df = _make_spend_revenue(30)
        result = estimate_incrementality(df)
        assert result is not None
        assert isinstance(result, IncrementalityResult)

    def test_disclaimer_always_present(self):
        df = _make_spend_revenue(30)
        result = estimate_incrementality(df)
        assert result is not None
        assert result.disclaimer == INCREMENTALITY_DISCLAIMER
        assert "not proven causation" in result.disclaimer

    def test_incrementality_fraction_between_0_and_1(self):
        df = _make_spend_revenue(30)
        result = estimate_incrementality(df)
        assert result is not None
        assert 0.0 <= result.incrementality_fraction <= 1.0

    def test_incremental_revenue_positive(self):
        """If spend drives revenue, incremental should be > 0."""
        df = _make_spend_revenue(30)
        result = estimate_incrementality(df)
        assert result is not None
        assert result.incremental_revenue >= 0

    def test_baseline_is_zero_spend_prediction(self):
        df = _make_spend_revenue(30)
        result = estimate_incrementality(df)
        assert result is not None
        # baseline = curve.predict(0) = a*ln(1) + b = b
        assert result.baseline_revenue >= 0

    def test_confidence_level_assigned(self):
        df = _make_spend_revenue(30)
        result = estimate_incrementality(df)
        assert result is not None
        assert result.confidence in ("high", "medium", "low")

    def test_returns_none_for_insufficient_data(self):
        df = pd.DataFrame({"spend": [100], "revenue": [200]})
        result = estimate_incrementality(df)
        assert result is None

    def test_returns_none_for_missing_columns(self):
        df = pd.DataFrame({"foo": [1, 2, 3]})
        result = estimate_incrementality(df)
        assert result is None

    def test_to_dict(self):
        df = _make_spend_revenue(30)
        result = estimate_incrementality(df)
        assert result is not None
        d = result.to_dict()
        assert "disclaimer" in d
        assert "incrementality_fraction" in d
        assert "curve" in d
        assert isinstance(d["curve"], dict)

    def test_deterministic(self):
        """Same data → same result, always."""
        df = _make_spend_revenue(25, seed=99)
        a = estimate_incrementality(df)
        b = estimate_incrementality(df)
        assert a is not None and b is not None
        assert a.incrementality_fraction == b.incrementality_fraction
        assert a.incremental_revenue == b.incremental_revenue

    def test_high_confidence_with_good_data(self):
        """30 days with a strong in-range log-linear fit (high R²) still
        gets downgraded to 'low' confidence here, because this fixture's
        spend never approaches zero (min ~300-900) — the same situation
        that caused the original bug. A clean in-range fit doesn't make
        the zero-spend extrapolation any more trustworthy; see
        test_extrapolation_flag_false_when_spend_spans_near_zero for the
        case where confidence legitimately reaches 'high'."""
        df = _make_spend_revenue(30)
        result = estimate_incrementality(df)
        assert result is not None
        assert result.confidence == "low"
        assert result.baseline_extrapolated is True

    def test_curve_attached(self):
        df = _make_spend_revenue(30)
        result = estimate_incrementality(df)
        assert result is not None
        assert result.curve is not None
        assert result.curve.a > 0

    def test_extrapolation_flag_false_when_spend_spans_near_zero(self):
        """When the data legitimately includes near-zero spend days, the
        zero-spend baseline is a real fit, not a guess."""
        rng = np.random.default_rng(7)
        rows = []
        for _ in range(30):
            spend = float(rng.uniform(0, 1000))
            revenue = 600 * np.log(spend + 1) + 500 + rng.normal(0, 50)
            rows.append({"spend": max(0.0, spend), "revenue": max(0.0, revenue)})
        df = pd.DataFrame(rows)
        result = estimate_incrementality(df)
        assert result is not None
        assert result.baseline_extrapolated is False
        assert isinstance(result.baseline_extrapolated, bool)

    def test_narrow_realistic_spend_range_is_flagged_and_downgraded(self):
        """Regression test: real ad-spend data rarely dips near zero. When
        the observed spend range sits far above zero (e.g. $700-$1000/day,
        like a typical always-on campaign), extrapolating the curve to
        spend=0 is unreliable and must NOT be silently reported as a clean
        100%-incremental, high-confidence figure."""
        rng = np.random.default_rng(3)
        rows = []
        for _ in range(30):
            spend = float(rng.uniform(700, 1000))
            # Deliberately noisy / not a clean log-linear relationship —
            # revenue mostly driven by something other than spend.
            revenue = 4000 + rng.normal(0, 400)
            rows.append({"spend": spend, "revenue": max(0.0, revenue)})
        df = pd.DataFrame(rows)
        result = estimate_incrementality(df)
        assert result is not None
        assert result.baseline_extrapolated is True
        # Confidence must never be "high" or "medium" when the baseline
        # itself is a severe extrapolation, regardless of in-range R².
        assert result.confidence == "low"

    def test_extrapolated_baseline_still_carries_disclaimer(self):
        rng = np.random.default_rng(3)
        rows = [
            {"spend": float(rng.uniform(700, 1000)), "revenue": 4000 + float(rng.normal(0, 400))}
            for _ in range(30)
        ]
        df = pd.DataFrame(rows)
        result = estimate_incrementality(df)
        assert result is not None
        assert result.disclaimer == INCREMENTALITY_DISCLAIMER

    def test_to_dict_includes_extrapolation_flag(self):
        df = _make_spend_revenue(30)
        result = estimate_incrementality(df)
        assert result is not None
        d = result.to_dict()
        assert "baseline_extrapolated" in d
        assert isinstance(d["baseline_extrapolated"], bool)
