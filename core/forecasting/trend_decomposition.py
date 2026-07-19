"""
Trend decomposition — fit a linear trend to a revenue series, compute
residuals and their standard deviation.

Deterministic, no network access, no LLM SDK, no absolute paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TrendResult:
    """Output of a linear trend fit."""
    slope: float
    intercept: float
    std_dev: float          # standard deviation of residuals
    residuals: np.ndarray   # raw residual per observation
    fitted: np.ndarray      # trend line values


def linear_trend(values: np.ndarray) -> TrendResult:
    """Ordinary least-squares linear trend on a 1-D array of values.

    Parameters
    ----------
    values : 1-D numeric array (one value per time step, equally spaced).

    Returns
    -------
    TrendResult with slope, intercept, residual std-dev, and per-point
    residuals.  The ``fitted`` array is the trend line evaluated at each
    input index.
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 2:
        return TrendResult(
            slope=0.0,
            intercept=float(values[0]) if n == 1 else 0.0,
            std_dev=0.0,
            residuals=np.zeros(n),
            fitted=values.copy(),
        )

    x = np.arange(n, dtype=float)
    x_mean = x.mean()
    y_mean = values.mean()

    numerator = ((x - x_mean) * (values - y_mean)).sum()
    denominator = ((x - x_mean) ** 2).sum()
    slope = float(numerator / denominator) if denominator != 0 else 0.0
    intercept = float(y_mean - slope * x_mean)

    fitted = slope * x + intercept
    residuals = values - fitted
    std_dev = float(np.sqrt((residuals ** 2).sum() / max(1, n - 2)))

    return TrendResult(
        slope=slope,
        intercept=intercept,
        std_dev=std_dev,
        residuals=residuals,
        fitted=fitted,
    )


@dataclass(frozen=True)
class DecomposeResult:
    """Full decomposition: trend + seasonal offsets + residuals."""
    trend: TrendResult
    seasonal_offsets: List[float]   # additive, length-7 (Mon=0 … Sun=6)
    detrended_residuals: np.ndarray


def decompose(
    df: pd.DataFrame,
    column: str = "revenue",
) -> DecomposeResult:
    """Decompose a daily series into trend + weekday seasonality + residuals.

    Parameters
    ----------
    df : DataFrame with ``date`` and *column*.
    column : name of the numeric column to decompose.

    Returns
    -------
    DecomposeResult — everything the Monte Carlo engine needs to simulate
    forward paths.
    """
    from core.preprocessing.seasonality import weekday_additive

    work = df[["date", column]].copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    values = work[column].to_numpy(dtype=float)

    # 1. Fit linear trend
    trend = linear_trend(values)

    # 2. Compute weekday offsets (returns zeros if < 14 days)
    seasonal_offsets = weekday_additive(df, column=column)

    # 3. Remove trend + seasonal from values to get pure residuals
    seasonal_applied = np.zeros(len(values))
    for i in range(len(values)):
        dow = work["date"].iloc[i].dayofweek
        seasonal_applied[i] = seasonal_offsets[dow]

    detrended_residuals = values - trend.fitted - seasonal_applied

    return DecomposeResult(
        trend=trend,
        seasonal_offsets=seasonal_offsets,
        detrended_residuals=detrended_residuals,
    )
