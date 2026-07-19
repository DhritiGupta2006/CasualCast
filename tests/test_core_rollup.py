"""
Tests for core.rollup  (orchestrator.py)

Run:  python -m pytest tests/test_core_rollup.py -v
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.rollup.orchestrator import run_pipeline, PipelineResult

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
TINY_SAMPLE = os.path.join(FIXTURE_DIR, "tiny_sample.csv")


# ===================================================================
# Helper
# ===================================================================

def _make_daily(n: int = 21, seed: int = 42) -> pd.DataFrame:
    """Synthetic daily data with known trend and spend-revenue correlation."""
    dates = pd.date_range("2026-06-01", periods=n, freq="D")
    rng = np.random.default_rng(seed)
    rows = []
    for i, d in enumerate(dates):
        spend = 500 + rng.integers(-200, 400)
        revenue = 600 * np.log(spend + 1) + 500 + rng.normal(0, 80)
        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            "spend": round(max(10, spend)),
            "revenue": round(max(0, revenue)),
            "sessions": round(max(0, revenue / 2)),
        })
    return pd.DataFrame(rows)


# ===================================================================
# Tests
# ===================================================================

class TestRunPipeline:

    def test_from_dataframe(self):
        df = _make_daily(21)
        result = run_pipeline(df=df)
        assert isinstance(result, PipelineResult)
        assert result.forecast is not None
        assert len(result.forecast.results) == 30  # default horizon
        assert result.data is not None

    def test_from_file_path(self):
        result = run_pipeline(file_path=TINY_SAMPLE)
        assert isinstance(result, PipelineResult)
        assert len(result.data) == 14
        assert result.forecast is not None

    def test_from_data_dir(self):
        result = run_pipeline(data_dir=FIXTURE_DIR)
        assert isinstance(result, PipelineResult)
        assert result.forecast is not None

    def test_no_source_raises(self):
        with pytest.raises(ValueError, match="Provide one of"):
            run_pipeline()

    def test_deterministic(self):
        """Same data + same seed → same forecast."""
        df = _make_daily(21)
        a = run_pipeline(df=df, seed=42)
        b = run_pipeline(df=df, seed=42)
        assert a.forecast is not None and b.forecast is not None
        for ra, rb in zip(a.forecast.results, b.forecast.results):
            assert ra.p50 == rb.p50

    def test_different_seed_different_output(self):
        df = _make_daily(21)
        a = run_pipeline(df=df, seed=1)
        b = run_pipeline(df=df, seed=2)
        assert a.forecast is not None and b.forecast is not None
        # At least some P50s should differ
        diffs = [ra.p50 != rb.p50 for ra, rb in zip(a.forecast.results, b.forecast.results)]
        assert any(diffs)

    def test_channel_groups_populated(self):
        df = _make_daily(21)
        result = run_pipeline(df=df)
        assert "channel_group" in result.data.columns
        assert len(result.channel_groups) > 0

    def test_anomaly_detection_runs(self):
        df = _make_daily(21)
        result = run_pipeline(df=df)
        assert "is_anomaly" in result.data.columns
        assert isinstance(result.anomaly_count, int)

    def test_weekday_factors_populated(self):
        df = _make_daily(21)
        result = run_pipeline(df=df)
        assert len(result.weekday_factors) == 7

    def test_forecast_stats(self):
        df = _make_daily(21)
        result = run_pipeline(df=df)
        assert result.forecast is not None
        stats = result.forecast.stats
        assert stats.avg_p50 > 0
        assert stats.trend_direction in ("up", "down", "flat")

    def test_budget_response_curve_fitted(self):
        df = _make_daily(21)
        result = run_pipeline(df=df)
        assert result.response_curve is not None
        assert result.response_curve.r_squared >= 0

    def test_budget_scenarios_generated(self):
        df = _make_daily(21)
        result = run_pipeline(df=df)
        assert len(result.budget_scenarios) > 0

    def test_custom_budget_multipliers(self):
        df = _make_daily(21)
        result = run_pipeline(df=df, budget_multipliers=[0.5, 1.0, 3.0])
        assert len(result.budget_scenarios) == 3

    def test_incrementality_estimated(self):
        df = _make_daily(21)
        result = run_pipeline(df=df)
        assert result.incrementality is not None
        assert result.incrementality.disclaimer == "Directional signal, not proven causation"

    def test_custom_horizon_and_iterations(self):
        df = _make_daily(14)
        result = run_pipeline(df=df, horizon=10, iterations=100)
        assert result.forecast is not None
        assert len(result.forecast.results) == 10
        assert result.forecast.iterations == 100

    def test_notes_and_warnings_are_lists(self):
        df = _make_daily(21)
        result = run_pipeline(df=df)
        assert isinstance(result.notes, list)
        assert isinstance(result.warnings, list)
