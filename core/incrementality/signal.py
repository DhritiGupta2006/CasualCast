"""
Incrementality signal estimation.

Estimates the *directional* incremental contribution of ad spend to
revenue.  This is NOT proven causation — it is a statistical signal based
on the observed spend→revenue correlation and the fitted budget-response
curve.  The result MUST always carry the disclaimer::

    "Directional signal, not proven causation"

…which is enforced in the frontend via ``IncrementalityBadge.tsx`` and
documented in ``docs/methodology.md``.

Approach
--------
1.  Fit the log-linear budget-response curve to daily (spend, revenue).
2.  Estimate *baseline revenue* — the model's prediction at zero spend:
    ``baseline = curve.predict(0)`` which equals the intercept ``b``.
3.  *Incremental revenue* = avg(actual_revenue) − baseline.
4.  *Incrementality fraction* = incremental / avg(actual_revenue).
5.  Confidence is derived from the curve's R² and sample size, then
    downgraded when step 2 is a severe extrapolation (see
    ``_is_severely_extrapolated`` below) — real ad-spend data almost never
    includes days near zero spend, so "predicted revenue at spend = 0" is
    frequently far outside the range the curve was actually fit on. Left
    unchecked, that extrapolation tends to land below zero, gets floored
    at 0, and silently produces a maxed-out 100%-incremental,
    "high confidence" reading regardless of the underlying data — which is
    the opposite of a *directional* signal. See docs/methodology.md.

No network access, no LLM SDK, no absolute paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from core.budget_response.fit import fit_response_curve, ResponseCurve


# ---------------------------------------------------------------------------
# Disclaimer constant — importable so the frontend badge and docs can
# reference the same canonical string.
# ---------------------------------------------------------------------------

INCREMENTALITY_DISCLAIMER = "Directional signal, not proven causation"


@dataclass(frozen=True)
class IncrementalityResult:
    """Output of an incrementality estimation."""
    baseline_revenue: float          # predicted revenue at zero spend
    avg_actual_revenue: float        # observed mean daily revenue
    incremental_revenue: float       # avg_actual − baseline
    incrementality_fraction: float   # incremental / avg_actual  (0–1)
    confidence: str                  # "high", "medium", or "low"
    curve: Optional[ResponseCurve]   # the underlying fitted curve
    baseline_extrapolated: bool = False  # True if spend=0 is far outside
                                          # the observed spend range, so
                                          # `baseline_revenue` is an
                                          # unreliable extrapolation
    disclaimer: str = INCREMENTALITY_DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "baseline_revenue": round(self.baseline_revenue, 2),
            "avg_actual_revenue": round(self.avg_actual_revenue, 2),
            "incremental_revenue": round(self.incremental_revenue, 2),
            "incrementality_fraction": round(self.incrementality_fraction, 4),
            "confidence": self.confidence,
            "baseline_extrapolated": self.baseline_extrapolated,
            "disclaimer": self.disclaimer,
            "curve": self.curve.to_dict() if self.curve else None,
        }


def _confidence_level(r_squared: float, n_points: int) -> str:
    """Heuristic confidence label from R² and sample size."""
    if r_squared >= 0.6 and n_points >= 21:
        return "high"
    if r_squared >= 0.3 and n_points >= 14:
        return "medium"
    return "low"


def _is_severely_extrapolated(curve: ResponseCurve) -> bool:
    """True when spend = 0 is far outside the spend range the curve was
    actually fit on, in the log-space the curve is fit in.

    The curve is fit on ``ln(spend + 1)``. We compare the log-distance from
    0 to the observed minimum spend against the log-width of the observed
    spend range itself. If that distance is at least as large as the
    observed range, the "prediction at spend = 0" is extrapolating by at
    least a full range-width beyond the data the curve actually saw — far
    enough that the intercept is a guess, not a fit. This is the common
    case for real ad-spend data, which rarely includes near-zero days.
    """
    if curve.spend_min <= 0:
        # Data already includes near-zero spend — little to no extrapolation.
        return False
    log_min = np.log(curve.spend_min + 1)
    log_max = np.log(curve.spend_max + 1)
    log_range = log_max - log_min
    # Guard against a degenerate (near-constant) spend range: treat any
    # nonzero distance to zero as severe extrapolation in that case, since
    # there's no in-sample variation to anchor the intercept at all.
    if log_range <= 1e-9:
        return bool(log_min > 1e-9)
    return bool(log_min >= log_range)


def estimate_incrementality(
    df: pd.DataFrame,
    spend_col: str = "spend",
    revenue_col: str = "revenue",
) -> Optional[IncrementalityResult]:
    """Estimate incrementality from daily spend/revenue data.

    Parameters
    ----------
    df : DataFrame with *spend_col* and *revenue_col*.

    Returns
    -------
    IncrementalityResult or None if the budget-response curve can't be
    fitted (too few data points or missing columns).
    """
    curve = fit_response_curve(df, spend_col=spend_col, revenue_col=revenue_col)
    if curve is None:
        return None

    # Baseline = predicted revenue at zero spend (just the intercept)
    raw_baseline = curve.predict(0)
    baseline = max(0.0, raw_baseline)

    # Observed average
    rev = pd.to_numeric(df[revenue_col], errors="coerce").dropna()
    avg_actual = float(rev.mean()) if len(rev) > 0 else 0.0

    incremental = max(0.0, avg_actual - baseline)
    fraction = incremental / avg_actual if avg_actual > 0 else 0.0

    extrapolated = _is_severely_extrapolated(curve)

    confidence = _confidence_level(curve.r_squared, curve.n_points)
    if extrapolated:
        # A good R² only tells you the curve fits the observed spend
        # range well — it says nothing about the intercept, which sits
        # outside that range entirely. Never report this as "high" or
        # "medium" confidence, no matter how clean the in-range fit is.
        confidence = "low"

    return IncrementalityResult(
        baseline_revenue=round(baseline, 2),
        avg_actual_revenue=round(avg_actual, 2),
        incremental_revenue=round(incremental, 2),
        incrementality_fraction=round(fraction, 4),
        confidence=confidence,
        curve=curve,
        baseline_extrapolated=extrapolated,
    )
