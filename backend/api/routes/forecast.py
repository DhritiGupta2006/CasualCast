"""
POST /api/forecast

Runs the full core/ pipeline (ingestion validation -> preprocessing ->
Monte Carlo forecast -> budget-response fit -> incrementality) via
core.rollup.orchestrator.run_pipeline -- the exact same function
src/predict.py calls for the scored batch pipeline. Given the same rows,
horizon, iterations, and seed, this route and predict.py can never
diverge, because they both bottom out in core.forecasting.engine.forecast.

This route computes nothing itself; it only shapes core/'s dataclasses
into JSON.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.rollup.orchestrator import run_pipeline

from ..dataframes import df_to_records, rows_to_clean_df
from ..schemas import ForecastRequest

router = APIRouter()


@router.post("/forecast")
async def forecast(req: ForecastRequest):
    df = rows_to_clean_df(req.rows)

    try:
        result = run_pipeline(
            df=df,
            horizon=req.horizon,
            iterations=req.iterations,
            seed=req.seed,
        )
    except Exception as exc:  # noqa: BLE001 -- surfaced as a clean 422, not a 500 stack trace
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    fc = result.forecast

    return {
        "results": [
            {"date": r.date, "p10": r.p10, "p50": r.p50, "p90": r.p90}
            for r in fc.results
        ],
        "historical": df_to_records(fc.historical),
        "stats": {
            "avg_p10": fc.stats.avg_p10,
            "avg_p50": fc.stats.avg_p50,
            "avg_p90": fc.stats.avg_p90,
            "confidence_range_pct": fc.stats.confidence_range_pct,
            "trend_direction": fc.stats.trend_direction,
            "slope": fc.stats.slope,
        },
        "horizon": fc.horizon,
        "iterations": fc.iterations,
        "seed": req.seed,
        "anomaly_count": result.anomaly_count,
        "channel_groups": result.channel_groups,
        "weekday_factors": result.weekday_factors,
        "notes": result.notes,
        "warnings": result.warnings,
    }
