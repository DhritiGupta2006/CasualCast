"""
Budget-response prediction — use a fitted curve to predict revenue at
hypothetical spend levels and generate scenario tables.

Deterministic (no randomness involved), no network access.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .fit import ResponseCurve


@dataclass(frozen=True)
class BudgetScenario:
    """One row of a what-if budget simulation."""
    daily_spend: float
    predicted_daily_revenue: float
    predicted_roas: float           # revenue / spend
    delta_spend_pct: float          # % change vs. baseline
    delta_revenue_pct: float        # % change vs. baseline


def predict_revenue(curve: ResponseCurve, spend: float) -> float:
    """Predict daily revenue for a single spend level.

    Parameters
    ----------
    curve : fitted ResponseCurve
    spend : daily spend amount (must be >= 0)

    Returns
    -------
    Predicted daily revenue (float, clamped to >= 0).
    """
    return max(0.0, curve.predict(spend))


def simulate_budget_scenarios(
    curve: ResponseCurve,
    baseline_spend: float,
    multipliers: Optional[List[float]] = None,
) -> List[BudgetScenario]:
    """Generate a table of predicted outcomes at various spend levels.

    Parameters
    ----------
    curve : fitted ResponseCurve
    baseline_spend : current / average daily spend
    multipliers : list of factors to apply to baseline_spend.
        Defaults to [0.5, 0.75, 1.0, 1.25, 1.5, 2.0].

    Returns
    -------
    List of BudgetScenario objects, one per multiplier.
    """
    if multipliers is None:
        multipliers = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

    baseline_rev = predict_revenue(curve, baseline_spend)
    results: List[BudgetScenario] = []

    for m in multipliers:
        spend = baseline_spend * m
        rev = predict_revenue(curve, spend)
        roas = rev / spend if spend > 0 else 0.0
        delta_spend = (m - 1.0) * 100
        delta_rev = ((rev - baseline_rev) / baseline_rev * 100) if baseline_rev > 0 else 0.0

        results.append(BudgetScenario(
            daily_spend=round(spend, 2),
            predicted_daily_revenue=round(rev, 2),
            predicted_roas=round(roas, 4),
            delta_spend_pct=round(delta_spend, 1),
            delta_revenue_pct=round(delta_rev, 1),
        ))

    return results
