"""
POST /api/simulate-budget

Backs the frontend's budget slider. Deliberately calls
core.budget_response directly rather than core.rollup.orchestrator.run_pipeline
-- fitting the response curve and evaluating it at a handful of spend
levels is cheap and deterministic (plain OLS, no Monte Carlo), so a
slider can hit this on every drag without re-running the full forecast
simulation each time.

Still: the curve fit and every predicted number come from core/, never
from this route or the frontend.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

from core.budget_response.fit import fit_response_curve
from core.budget_response.predict import predict_revenue, simulate_budget_scenarios

from ..dataframes import rows_to_clean_df
from ..schemas import SimulateBudgetRequest

router = APIRouter()


@router.post("/simulate-budget")
async def simulate_budget(req: SimulateBudgetRequest):
    df = rows_to_clean_df(req.rows)

    curve = fit_response_curve(df)
    if curve is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Not enough spend/revenue data to fit a budget-response "
                "curve -- need at least 7 days with spend > 0."
            ),
        )

    baseline_spend = req.baseline_spend
    if baseline_spend is None:
        spend_col = pd.to_numeric(df["spend"], errors="coerce")
        baseline_spend = float(spend_col.mean())

    if baseline_spend <= 0:
        raise HTTPException(status_code=422, detail="baseline_spend must be greater than zero.")

    scenarios = simulate_budget_scenarios(
        curve, baseline_spend=baseline_spend, multipliers=req.multipliers
    )

    return {
        "baseline_spend": round(baseline_spend, 2),
        "baseline_predicted_revenue": round(predict_revenue(curve, baseline_spend), 2),
        "curve": curve.to_dict(),
        "scenarios": [
            {
                "daily_spend": s.daily_spend,
                "predicted_daily_revenue": s.predicted_daily_revenue,
                "predicted_roas": s.predicted_roas,
                "delta_spend_pct": s.delta_spend_pct,
                "delta_revenue_pct": s.delta_revenue_pct,
            }
            for s in scenarios
        ],
    }
