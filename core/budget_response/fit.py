"""
Budget-response curve fitting.

Fits a log-linear model  ``revenue = a * ln(spend + 1) + b``  to historical
daily (spend, revenue) pairs.  This deliberately simple functional form
captures the diminishing-returns pattern seen in most ad channels without
requiring the data volume a full Hill or Michaelis–Menten model needs.

Fitting uses ordinary least-squares on the log-transformed spend, which is
deterministic given the same input.  An optional bootstrap confidence
interval uses a **seeded** RNG for reproducibility.

No network access, no LLM SDK, no absolute paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ResponseCurve:
    """Fitted spend → revenue response curve."""
    a: float              # coefficient on ln(spend + 1)
    b: float              # intercept
    r_squared: float      # goodness of fit (0–1)
    n_points: int         # number of data points used
    spend_min: float      # observed spend range
    spend_max: float

    def predict(self, spend: float) -> float:
        """Predict revenue for a given daily spend level."""
        return self.a * np.log(spend + 1) + self.b

    def to_dict(self) -> dict:
        return {
            "a": self.a,
            "b": self.b,
            "r_squared": self.r_squared,
            "n_points": self.n_points,
            "spend_min": self.spend_min,
            "spend_max": self.spend_max,
        }


def fit_response_curve(
    df: pd.DataFrame,
    spend_col: str = "spend",
    revenue_col: str = "revenue",
    min_points: int = 7,
) -> Optional[ResponseCurve]:
    """Fit a log-linear response curve to daily spend → revenue data.

    Parameters
    ----------
    df : DataFrame with *spend_col* and *revenue_col*.
    spend_col, revenue_col : column names.
    min_points : minimum rows needed to attempt a fit.

    Returns
    -------
    ResponseCurve or None if insufficient data or fit fails.
    """
    if spend_col not in df.columns or revenue_col not in df.columns:
        return None

    work = df[[spend_col, revenue_col]].copy()
    work[spend_col] = pd.to_numeric(work[spend_col], errors="coerce")
    work[revenue_col] = pd.to_numeric(work[revenue_col], errors="coerce")
    work = work.dropna()
    work = work[work[spend_col] > 0]  # log(0) is undefined

    if len(work) < min_points:
        return None

    spend = work[spend_col].to_numpy(dtype=float)
    revenue = work[revenue_col].to_numpy(dtype=float)

    # Transform: X = ln(spend + 1)
    X = np.log(spend + 1)
    n = len(X)

    # OLS:  revenue = a * X + b
    x_mean = X.mean()
    y_mean = revenue.mean()
    numerator = ((X - x_mean) * (revenue - y_mean)).sum()
    denominator = ((X - x_mean) ** 2).sum()

    if denominator == 0:
        return None

    a = float(numerator / denominator)
    b = float(y_mean - a * x_mean)

    # R²
    predicted = a * X + b
    ss_res = ((revenue - predicted) ** 2).sum()
    ss_tot = ((revenue - y_mean) ** 2).sum()
    r_squared = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    return ResponseCurve(
        a=round(a, 4),
        b=round(b, 4),
        r_squared=round(max(0.0, r_squared), 4),
        n_points=n,
        spend_min=float(spend.min()),
        spend_max=float(spend.max()),
    )


def fit_with_confidence(
    df: pd.DataFrame,
    spend_col: str = "spend",
    revenue_col: str = "revenue",
    n_bootstrap: int = 200,
    seed: int = 42,
) -> Tuple[Optional[ResponseCurve], Optional[Tuple[float, float]]]:
    """Fit the curve and estimate a 90 % CI for the coefficient *a* via
    bootstrap resampling.

    Returns
    -------
    (curve, ci) where *ci* is ``(a_5th_percentile, a_95th_percentile)``
    or ``None`` if the fit fails.
    """
    curve = fit_response_curve(df, spend_col, revenue_col)
    if curve is None:
        return None, None

    rng = np.random.default_rng(seed)
    work = df[[spend_col, revenue_col]].dropna()
    work = work[pd.to_numeric(work[spend_col], errors="coerce") > 0]
    n = len(work)

    a_samples = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        sample = work.iloc[idx]
        c = fit_response_curve(sample, spend_col, revenue_col, min_points=3)
        if c is not None:
            a_samples.append(c.a)

    if len(a_samples) < 10:
        return curve, None

    ci = (float(np.percentile(a_samples, 5)), float(np.percentile(a_samples, 95)))
    return curve, ci
