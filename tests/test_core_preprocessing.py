"""
Tests for core.preprocessing  (taxonomy.py, anomalies.py, seasonality.py)

Run:  python -m pytest tests/test_core_preprocessing.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.preprocessing.taxonomy import classify_channel, add_channel_group
from core.preprocessing.anomalies import flag_anomalies, clip_anomalies
from core.preprocessing.seasonality import (
    weekday_factors,
    weekday_additive,
    apply_seasonal_adjustment,
    MIN_DAYS_FOR_SEASONALITY,
)


# ===================================================================
# Helper: build a 21-day daily DataFrame
# ===================================================================

def _make_daily(n: int = 21, base_rev: float = 4000.0) -> pd.DataFrame:
    """Generate *n* consecutive days of synthetic data starting Monday."""
    dates = pd.date_range("2026-06-01", periods=n, freq="D")  # 2026-06-01 is a Monday
    rng = np.random.default_rng(42)
    rows = []
    for i, d in enumerate(dates):
        dow = d.dayofweek
        # Inject weekday seasonality: weekends ~20% lower
        lift = 0.82 if dow >= 5 else 1.0
        rev = base_rev * lift + rng.normal(0, 50)
        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            "spend": round(900 + rng.normal(0, 30)),
            "revenue": round(rev),
            "sessions": round(rev / 2),
        })
    return pd.DataFrame(rows)


# ===================================================================
# taxonomy
# ===================================================================

class TestClassifyChannel:

    def test_paid_search_variants(self):
        assert classify_channel("google ads") == "Paid Search"
        assert classify_channel("Google Ads - Brand") == "Paid Search"
        assert classify_channel("Bing Ads") == "Paid Search"
        assert classify_channel("SEM") == "Paid Search"
        assert classify_channel("ppc") == "Paid Search"

    def test_paid_social_variants(self):
        assert classify_channel("Facebook Ads") == "Paid Social"
        assert classify_channel("instagram ads") == "Paid Social"
        assert classify_channel("TikTok Ads") == "Paid Social"
        assert classify_channel("paid social") == "Paid Social"

    def test_organic_search(self):
        assert classify_channel("organic search") == "Organic Search"
        assert classify_channel("google / organic") == "Organic Search"
        assert classify_channel("seo") == "Organic Search"

    def test_email(self):
        assert classify_channel("email") == "Email"
        assert classify_channel("Klaviyo") == "Email"

    def test_direct(self):
        assert classify_channel("(direct)") == "Direct"
        assert classify_channel("direct") == "Direct"
        assert classify_channel("(none)") == "Direct"

    def test_none_and_empty(self):
        assert classify_channel(None) == "Other"
        assert classify_channel("") == "Other"
        assert classify_channel(float("nan")) == "Other"

    def test_unknown_string(self):
        assert classify_channel("some_random_campaign_xyz") == "Other"


class TestAddChannelGroup:

    def test_adds_column(self):
        df = pd.DataFrame({
            "date": ["2026-06-01"],
            "spend": [100],
            "revenue": [200],
            "channel": ["google ads"],
        })
        result = add_channel_group(df)
        assert "channel_group" in result.columns
        assert result["channel_group"].iloc[0] == "Paid Search"

    def test_missing_source_col_defaults_to_other(self):
        df = pd.DataFrame({"date": ["2026-06-01"], "revenue": [200]})
        result = add_channel_group(df)
        assert result["channel_group"].iloc[0] == "Other"

    def test_original_column_preserved(self):
        df = pd.DataFrame({"channel": ["facebook ads"]})
        result = add_channel_group(df)
        assert "channel" in result.columns
        assert result["channel"].iloc[0] == "facebook ads"


# ===================================================================
# anomalies
# ===================================================================

class TestFlagAnomalies:

    def test_no_anomalies_in_clean_data(self):
        df = _make_daily(14)
        result = flag_anomalies(df, column="revenue")
        assert "is_anomaly" in result.columns
        # With normal-ish data, expect few or no anomalies
        assert result["is_anomaly"].sum() <= 2

    def test_extreme_value_flagged(self):
        df = _make_daily(14)
        # Inject a massive outlier
        df.loc[0, "revenue"] = 999_999
        result = flag_anomalies(df, column="revenue")
        assert result["is_anomaly"].iloc[0] is True or result["is_anomaly"].iloc[0] == True

    def test_too_few_rows_flags_nothing(self):
        df = _make_daily(5)
        result = flag_anomalies(df, column="revenue", min_rows=7)
        assert result["is_anomaly"].sum() == 0

    def test_missing_column_flags_nothing(self):
        df = pd.DataFrame({"date": ["2026-06-01"], "spend": [100]})
        result = flag_anomalies(df, column="revenue")
        assert "is_anomaly" in result.columns
        assert result["is_anomaly"].sum() == 0


class TestClipAnomalies:

    def test_clips_extreme_value(self):
        df = _make_daily(14)
        df.loc[0, "revenue"] = 999_999
        original_max = df["revenue"].max()
        result = clip_anomalies(df, column="revenue")
        assert result["revenue"].max() < original_max

    def test_normal_values_unchanged(self):
        df = _make_daily(14)
        original = df["revenue"].copy()
        result = clip_anomalies(df, column="revenue")
        # If no anomalies, values should be the same
        np.testing.assert_array_almost_equal(
            result["revenue"].values, original.values, decimal=2
        )


# ===================================================================
# seasonality
# ===================================================================

class TestWeekdayFactors:

    def test_returns_seven_floats(self):
        df = _make_daily(21)
        factors = weekday_factors(df, column="revenue")
        assert len(factors) == 7
        assert all(isinstance(f, float) for f in factors)

    def test_neutral_when_too_few_days(self):
        df = _make_daily(10)
        factors = weekday_factors(df, column="revenue")
        assert factors == [1.0] * 7

    def test_weekday_vs_weekend_difference(self):
        """Our synthetic data has ~20% lower weekends, so Sat/Sun factors
        should be noticeably below 1.0."""
        df = _make_daily(28)  # 4 full weeks for stable estimate
        factors = weekday_factors(df, column="revenue")
        weekday_avg = sum(factors[:5]) / 5
        weekend_avg = sum(factors[5:]) / 2
        assert weekend_avg < weekday_avg

    def test_factors_average_near_one(self):
        """Multiplicative factors should average roughly 1.0 across the week."""
        df = _make_daily(28)
        factors = weekday_factors(df, column="revenue")
        avg = sum(factors) / 7
        assert abs(avg - 1.0) < 0.15  # generous tolerance

    def test_missing_column_returns_neutral(self):
        df = pd.DataFrame({"date": ["2026-06-01"], "spend": [100]})
        assert weekday_factors(df, column="revenue") == [1.0] * 7


class TestWeekdayAdditive:

    def test_returns_seven_floats(self):
        df = _make_daily(21)
        offsets = weekday_additive(df, column="revenue")
        assert len(offsets) == 7

    def test_offsets_sum_near_zero(self):
        """Additive offsets should roughly cancel out across the week."""
        df = _make_daily(28)
        offsets = weekday_additive(df, column="revenue")
        assert abs(sum(offsets)) < 500  # generous


class TestApplySeasonalAdjustment:

    def test_multiplicative(self):
        values = np.array([100.0, 100.0, 100.0])
        factors = [1.1, 1.0, 0.9, 1.0, 1.0, 0.8, 0.8]
        result = apply_seasonal_adjustment(values, "2026-06-01", factors, multiplicative=True)
        # 2026-06-01 is Monday (dow=0), factor=1.1
        assert abs(result[0] - 110.0) < 0.01
        # Tuesday (dow=1), factor=1.0
        assert abs(result[1] - 100.0) < 0.01
        # Wednesday (dow=2), factor=0.9
        assert abs(result[2] - 90.0) < 0.01

    def test_additive(self):
        values = np.array([100.0, 100.0])
        offsets = [50.0, -30.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        result = apply_seasonal_adjustment(values, "2026-06-01", offsets, multiplicative=False)
        assert abs(result[0] - 150.0) < 0.01  # Monday +50
        assert abs(result[1] - 70.0) < 0.01   # Tuesday -30
