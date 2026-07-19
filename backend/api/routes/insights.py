"""
POST /api/insights

Bundles the numbers a human reads as an "insight" -- trend direction,
incrementality (with its mandatory disclaimer), anomaly count, and the
best-ROAS budget scenario -- all computed by core/ via
core.rollup.orchestrator.run_pipeline.

The prose in `template_summary` comes from backend/llm/summarizer.narrate,
which narrates exactly this numeric payload via the Anthropic API when
ANTHROPIC_API_KEY is set, and falls back to a deterministic, no-network
template summary otherwise (missing key, missing `anthropic` package, or
any API failure). `narration_source` reports which path produced the text
("llm" or "template") -- the frontend can render either one identically,
so the insight panel is never blank or broken either way.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.incrementality.signal import INCREMENTALITY_DISCLAIMER
from core.rollup.orchestrator import run_pipeline

from ...llm.summarizer import narrate
from ..dataframes import rows_to_clean_df
from ..schemas import InsightsRequest

router = APIRouter()


@router.post("/insights")
async def insights(req: InsightsRequest):
    df = rows_to_clean_df(req.rows)

    try:
        result = run_pipeline(df=df)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    fc = result.forecast
    inc = result.incrementality
    top_scenario = (
        max(result.budget_scenarios, key=lambda s: s.predicted_roas)
        if result.budget_scenarios
        else None
    )

    numbers = {
        "trend": {
            "direction": fc.stats.trend_direction,
            "slope": fc.stats.slope,
            "avg_p50": fc.stats.avg_p50,
            "confidence_range_pct": fc.stats.confidence_range_pct,
        },
        "incrementality": inc.to_dict() if inc is not None else None,
        "incrementality_disclaimer": INCREMENTALITY_DISCLAIMER,
        "anomaly_count": result.anomaly_count,
        "channel_groups": result.channel_groups,
        "top_budget_scenario": (
            {
                "daily_spend": top_scenario.daily_spend,
                "predicted_daily_revenue": top_scenario.predicted_daily_revenue,
                "predicted_roas": top_scenario.predicted_roas,
            }
            if top_scenario is not None
            else None
        ),
        "warnings": result.warnings,
    }

    # The LLM (or its template fallback) only narrates `numbers` above --
    # it never sees anything it could mistake for an instruction to compute
    # or alter a figure, and it can't affect any other field in this response.
    narration = await narrate(numbers)

    return {
        **numbers,
        "template_summary": narration.text,
        "narration_source": narration.source,
    }

