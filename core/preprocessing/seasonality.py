"""
Weekday-seasonality extraction.

Computes per-day-of-week multiplicative factors from a historical revenue
series so the forecasting engine can overlay weekday patterns on top of
trend.  Requires at least 14 days (two full weeks) to produce meaningful
factors — otherwise returns neutral (all-ones) factors.

No network access, no LLM SDK, no absolute paths.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

# Minimum days required before weekday seasonality is considered reliable.
MIN_DAYS_FOR_SEASONALITY = 14


def weekday_factors(df: pd.DataFrame, column: str = "revenue") -> List[float]:
    """Compute multiplicative weekday factors (Mon=0 … Sun=6).

    Each factor is the ratio of that weekday's average to the overall mean.
    A factor of 1.0 means the weekday is exactly average; >1.0 means
    above average; <1.0 means below.

    Returns a list of 7 floats (index 0 = Monday).  If data is
    insufficient (< 14 days) all factors are 1.0.
    """
    neutral = [1.0] * 7

    if column not in df.columns or "date" not in df.columns:
        return neutral

    work = df[["date", column]].copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["date"])
    work[column] = pd.to_numeric(work[column], errors="coerce")
    work = work.dropna(subset=[column])

    if len(work) < MIN_DAYS_FOR_SEASONALITY:
        return neutral

    overall_mean = work[column].mean()
    if overall_mean == 0:
        return neutral

    # .dt.dayofweek: Monday=0, Sunday=6
    work["dow"] = work["date"].dt.dayofweek
    dow_means = work.groupby("dow")[column].mean()

    factors = neutral[:]
    for dow in range(7):
        if dow in dow_means.index:
            factors[dow] = float(dow_means[dow] / overall_mean)

    return factors


def weekday_additive(df: pd.DataFrame, column: str = "revenue") -> List[float]:
    """Compute additive weekday offsets (Mon=0 … Sun=6).

    Each offset is  weekday_mean − overall_mean.
    Useful for the Monte Carlo engine's additive seasonal component.
    """
    zero = [0.0] * 7

    if column not in df.columns or "date" not in df.columns:
        return zero

    work = df[["date", column]].copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["date"])
    work[column] = pd.to_numeric(work[column], errors="coerce")
    work = work.dropna(subset=[column])

    if len(work) < MIN_DAYS_FOR_SEASONALITY:
        return zero

    overall_mean = work[column].mean()
    work["dow"] = work["date"].dt.dayofweek
    dow_means = work.groupby("dow")[column].mean()

    offsets = zero[:]
    for dow in range(7):
        if dow in dow_means.index:
            offsets[dow] = float(dow_means[dow] - overall_mean)

    return offsets


def apply_seasonal_adjustment(
    values: np.ndarray,
    start_date: str,
    factors: List[float],
    multiplicative: bool = True,
) -> np.ndarray:
    """Apply weekday factors/offsets to an array of daily values.

    Parameters
    ----------
    values : 1-D array of daily numeric values.
    start_date : ISO date string for values[0].
    factors : 7-element list (Mon=0 … Sun=6).
    multiplicative : if True, multiply; if False, add.
    """
    start = pd.Timestamp(start_date)
    result = np.array(values, dtype=float)
    for i in range(len(result)):
        dow = (start + pd.Timedelta(days=i)).dayofweek
        if multiplicative:
            result[i] *= factors[dow]
        else:
            result[i] += factors[dow]
    return result
