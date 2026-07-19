"""
Tests for core.forecasting  (trend_decomposition.py, monte_carlo.py, engine.py)

Run:  python -m pytest tests/test_core_forecasting.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.forecasting.trend_decomposition import linear_trend, decompose, TrendResult
from core.forecasting.monte_carlo import (
    simulate_paths,
    percentiles_from_paths,
    DEFAULT_SEED,
)
from core.forecasting.engine import forecast, ForecastOutput


# ===================================================================
# Helper: build a clean daily DataFrame
# ===================================================================

def _make_daily(
    n: int = 21,
    base: float = 4000.0,
    slope: float = 20.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Synthetic daily data with known trend and weekday seasonality."""
    dates = pd.date_range("2026-06-01", periods=n, freq="D")
    rng = np.random.default_rng(seed)
    rows = []
    for i, d in enumerate(dates):
        dow = d.dayofweek
        weekend = 0.85 if dow >= 5 else 1.0
        rev = (base + slope * i) * weekend + rng.normal(0, 40)
        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            "spend": round(900 + rng.normal(0, 20)),
            "revenue": round(max(0, rev)),
            "sessions": round(max(0, rev / 2)),
        })
    return pd.DataFrame(rows)


# ===================================================================
# trend_decomposition — linear_trend
# ===================================================================

class TestLinearTrend:

    def test_perfect_line(self):
        """A perfectly linear series should have zero residual std_dev."""
        values = np.array([100.0, 200.0, 300.0, 400.0, 500.0])
        result = linear_trend(values)
        assert abs(result.slope - 100.0) < 0.01
        assert abs(result.intercept - 100.0) < 0.01
        assert result.std_dev < 0.01
        assert len(result.residuals) == 5
        assert len(result.fitted) == 5

    def test_flat_series(self):
        values = np.array([50.0, 50.0, 50.0, 50.0])
        result = linear_trend(values)
        assert abs(result.slope) < 0.01
        assert abs(result.intercept - 50.0) < 0.01

    def test_single_value(self):
        result = linear_trend(np.array([42.0]))
        assert result.slope == 0.0
        assert result.intercept == 42.0

    def test_noisy_uptrend_detected(self):
        rng = np.random.default_rng(7)
        values = np.array([1000 + 10 * i + rng.normal(0, 20) for i in range(30)])
        result = linear_trend(values)
        assert result.slope > 5.0  # true slope is 10
        assert result.std_dev > 0

    def test_residuals_sum_near_zero(self):
        """OLS residuals should sum to approximately zero."""
        rng = np.random.default_rng(99)
        values = np.array([500 + rng.normal(0, 50) for _ in range(20)])
        result = linear_trend(values)
        assert abs(result.residuals.sum()) < 1.0


# ===================================================================
# trend_decomposition — decompose
# ===================================================================

class TestDecompose:

    def test_returns_all_components(self):
        df = _make_daily(21)
        result = decompose(df, column="revenue")
        assert result.trend is not None
        assert len(result.seasonal_offsets) == 7
        assert len(result.detrended_residuals) == 21

    def test_short_data_neutral_seasonality(self):
        df = _make_daily(10)
        result = decompose(df, column="revenue")
        assert result.seasonal_offsets == [0.0] * 7

    def test_trend_slope_positive_for_uptrending_data(self):
        df = _make_daily(21, slope=30.0)
        result = decompose(df, column="revenue")
        assert result.trend.slope > 10.0


# ===================================================================
# monte_carlo — simulate_paths
# ===================================================================

class TestSimulatePaths:

    def test_output_shape(self):
        sim = simulate_paths(
            n_history=20, slope=10.0, intercept=4000.0, std_dev=100.0,
            seasonal_offsets=[0.0] * 7, last_date="2026-06-21",
            iterations=500, horizon=15, seed=42,
        )
        assert sim.paths.shape == (500, 15)
        assert len(sim.dates) == 15

    def test_deterministic_with_same_seed(self):
        """Same seed → same paths, every time."""
        kwargs = dict(
            n_history=20, slope=10.0, intercept=4000.0, std_dev=100.0,
            seasonal_offsets=[0.0] * 7, last_date="2026-06-21",
            iterations=100, horizon=10, seed=42,
        )
        a = simulate_paths(**kwargs)
        b = simulate_paths(**kwargs)
        np.testing.assert_array_equal(a.paths, b.paths)

    def test_different_seed_different_paths(self):
        kwargs = dict(
            n_history=20, slope=10.0, intercept=4000.0, std_dev=100.0,
            seasonal_offsets=[0.0] * 7, last_date="2026-06-21",
            iterations=100, horizon=10,
        )
        a = simulate_paths(**kwargs, seed=1)
        b = simulate_paths(**kwargs, seed=2)
        assert not np.array_equal(a.paths, b.paths)

    def test_no_negative_revenue(self):
        """Revenue paths should be clipped to >= 0."""
        sim = simulate_paths(
            n_history=20, slope=-50.0, intercept=200.0, std_dev=500.0,
            seasonal_offsets=[0.0] * 7, last_date="2026-06-21",
            iterations=200, horizon=30, seed=42,
        )
        assert sim.paths.min() >= 0.0

    def test_dates_are_consecutive(self):
        sim = simulate_paths(
            n_history=10, slope=0, intercept=100, std_dev=10,
            seasonal_offsets=[0.0] * 7, last_date="2026-06-14",
            iterations=10, horizon=5, seed=42,
        )
        assert sim.dates[0] == "2026-06-15"
        assert sim.dates[-1] == "2026-06-19"


class TestPercentilesFromPaths:

    def test_p10_le_p50_le_p90(self):
        sim = simulate_paths(
            n_history=20, slope=10.0, intercept=4000.0, std_dev=200.0,
            seasonal_offsets=[0.0] * 7, last_date="2026-06-21",
            iterations=1000, horizon=30, seed=42,
        )
        pct = percentiles_from_paths(sim)
        assert len(pct.dates) == 30
        for i in range(30):
            assert pct.p10[i] <= pct.p50[i] <= pct.p90[i]


# ===================================================================
# engine — forecast (end-to-end)
# ===================================================================

class TestForecastEngine:

    def test_produces_output(self):
        df = _make_daily(21)
        out = forecast(df)
        assert isinstance(out, ForecastOutput)
        assert len(out.results) == 30
        assert out.horizon == 30
        assert out.iterations == 1000

    def test_deterministic_with_same_seed(self):
        df = _make_daily(21)
        a = forecast(df, seed=42)
        b = forecast(df, seed=42)
        for ra, rb in zip(a.results, b.results):
            assert ra.p50 == rb.p50

    def test_results_have_dates(self):
        df = _make_daily(14)
        out = forecast(df, horizon=7)
        assert len(out.results) == 7
        # First forecast date should be day after last historical
        last_hist = out.historical["date"].iloc[-1]
        first_fc = out.results[0].date
        last_dt = pd.Timestamp(last_hist)
        first_dt = pd.Timestamp(first_fc)
        assert (first_dt - last_dt).days == 1

    def test_stats_populated(self):
        df = _make_daily(21, slope=30.0)
        out = forecast(df)
        assert out.stats.avg_p50 > 0
        assert out.stats.confidence_range_pct >= 0
        assert out.stats.trend_direction in ("up", "down", "flat")
        assert out.stats.slope != 0

    def test_p10_le_p50_le_p90_in_results(self):
        df = _make_daily(21)
        out = forecast(df)
        for row in out.results:
            assert row.p10 <= row.p50 <= row.p90

    def test_custom_horizon(self):
        df = _make_daily(14)
        out = forecast(df, horizon=10, iterations=100)
        assert len(out.results) == 10
        assert out.iterations == 100

    def test_historical_preserved_in_output(self):
        df = _make_daily(14)
        out = forecast(df)
        assert len(out.historical) == 14
        assert "date" in out.historical.columns
        assert "revenue" in out.historical.columns
