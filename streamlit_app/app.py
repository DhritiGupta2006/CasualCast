"""
CausalCast — Streamlit demo.

A bonus/alternative UI on top of the exact same core/ library the scored
batch pipeline (run.sh, src/predict.py) and the React+FastAPI live demo
(backend/) both use. This app computes NOTHING itself — every number
comes from a single core.rollup.orchestrator.run_pipeline() call, so
whatever this page shows can never diverge from a batch run of the same
data (design-doc ground rule #8, extended to this UI too).

This is additive only: it does not touch run.sh, core/, src/, backend/,
frontend/, tests/, or docs/. The scored submission pipeline and the React
live demo are completely unaffected by this file's existence.

Run:
    pip install -r streamlit_app/requirements-streamlit.txt
    streamlit run streamlit_app/app.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Make `import core` (and optionally `import backend.llm`) work regardless
# of the caller's cwd — same pattern src/predict.py and src/train.py use.
# No absolute paths: everything is relative to this file's location.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.ingestion.schema import coerce_types, normalize_columns, validate_schema  # noqa: E402
from core.rollup.orchestrator import run_pipeline  # noqa: E402
from core.incrementality.signal import INCREMENTALITY_DISCLAIMER  # noqa: E402
from core.budget_response.predict import simulate_budget_scenarios  # noqa: E402

st.set_page_config(page_title="CausalCast", page_icon="📈", layout="wide")

SAMPLE_DATA_PATH = REPO_ROOT / "data" / "sample_data.csv"


# ---------------------------------------------------------------------------
# Data loading — mirrors backend/api/dataframes.py's rows_to_clean_df, but
# built directly on core.ingestion.schema instead of FastAPI/pydantic since
# this file has no web framework in the loop.
# ---------------------------------------------------------------------------
def load_and_clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Normalize column names, coerce types, and validate. Never raises —
    returns (df, notes, errors); caller decides how to render errors."""
    df, notes = normalize_columns(raw)
    df = coerce_types(df)
    errors = validate_schema(df)
    return df, notes, errors


@st.cache_data(show_spinner=False)
def load_sample() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_DATA_PATH)


# ---------------------------------------------------------------------------
# Optional LLM narration — reuses backend/llm/ as-is (never re-implemented
# here). Degrades to the same deterministic template fallback backend/llm
# already ships if ANTHROPIC_API_KEY is unset or the call fails; this app
# never blocks on it.
# ---------------------------------------------------------------------------
def get_narration(payload: dict) -> tuple[str, str]:
    try:
        from backend.llm.summarizer import narrate
    except Exception:
        from backend.llm.prompt_template import build_template_summary
        return build_template_summary(payload), "template"

    result = asyncio.run(narrate(payload))
    return result.text, result.source


def build_insights_payload(result) -> dict:
    """Same shape backend/api/routes/insights.py builds — kept here so the
    template/LLM narration reads an identical payload in both UIs."""
    fc = result.forecast
    inc = result.incrementality
    top_scenario = None
    if result.budget_scenarios:
        top_scenario = max(result.budget_scenarios, key=lambda s: s.predicted_roas)
    return {
        "trend": {
            "direction": fc.stats.trend_direction,
            "slope": fc.stats.slope,
            "avg_p50": fc.stats.avg_p50,
            "confidence_range_pct": fc.stats.confidence_range_pct,
        },
        "incrementality": inc.to_dict() if inc else None,
        "incrementality_disclaimer": INCREMENTALITY_DISCLAIMER,
        "anomaly_count": result.anomaly_count,
        "channel_groups": result.channel_groups,
        "top_budget_scenario": (
            {
                "daily_spend": top_scenario.daily_spend,
                "predicted_daily_revenue": top_scenario.predicted_daily_revenue,
                "predicted_roas": top_scenario.predicted_roas,
            }
            if top_scenario
            else None
        ),
        "warnings": result.warnings,
    }


# ---------------------------------------------------------------------------
# Sidebar — data input + pipeline params
# ---------------------------------------------------------------------------
st.sidebar.title("CausalCast")
st.sidebar.caption("Streamlit demo — same `core/` pipeline as the scored batch run and the React live demo.")

source = st.sidebar.radio("Data source", ["Sample data", "Upload CSV"], index=0)

raw_df: pd.DataFrame | None = None
if source == "Sample data":
    if SAMPLE_DATA_PATH.exists():
        raw_df = load_sample()
        st.sidebar.success(f"Loaded {len(raw_df)} rows from data/sample_data.csv")
    else:
        st.sidebar.error("data/sample_data.csv not found.")
else:
    uploaded = st.sidebar.file_uploader("Daily spend/revenue CSV", type=["csv"])
    if uploaded is not None:
        raw_df = pd.read_csv(uploaded)

st.sidebar.divider()
horizon = st.sidebar.slider("Forecast horizon (days)", 7, 60, 30)
iterations = st.sidebar.slider("Monte Carlo iterations", 100, 2000, 1000, step=100)
seed = st.sidebar.number_input("Seed", value=42, step=1)
use_llm = st.sidebar.checkbox(
    "Narrate with LLM (if ANTHROPIC_API_KEY is set)",
    value=False,
    help="Falls back to a deterministic template summary automatically if unset or the call fails.",
)

st.title("📈 CausalCast")
st.caption(
    "Revenue forecast, budget-response curve, and a directional incrementality "
    "signal — computed once by `core/` and shared with the scored batch pipeline "
    "and the React live demo, so the numbers here can never diverge from either."
)

if raw_df is None:
    st.info("Choose a data source in the sidebar to get started.")
    st.stop()

clean_df, notes, errors = load_and_clean(raw_df)

if errors:
    st.error("This data doesn't match the expected schema:\n\n" + "\n".join(f"- {e}" for e in errors))
    st.stop()

if notes:
    with st.expander("Automatic column/unit conversions applied", expanded=False):
        for n in notes:
            st.caption(f"• {n}")

if len(clean_df) < 7:
    st.warning(f"Only {len(clean_df)} valid row(s) after cleaning — need at least 7 days for a forecast.")
    st.stop()

with st.spinner("Running the CausalCast pipeline…"):
    result = run_pipeline(df=clean_df, horizon=int(horizon), iterations=int(iterations), seed=int(seed))

fc = result.forecast

for w in result.warnings:
    st.warning(w)

# ---------------------------------------------------------------------------
# Forecast chart + trend stats
# ---------------------------------------------------------------------------
col_chart, col_stats = st.columns([3, 1])

with col_chart:
    st.subheader("Revenue forecast")
    hist = fc.historical[["date", "revenue"]].rename(columns={"revenue": "p50"}).copy()
    hist["p10"] = hist["p50"]
    hist["p90"] = hist["p50"]
    hist["segment"] = "historical"

    future = pd.DataFrame(
        [{"date": r.date, "p10": r.p10, "p50": r.p50, "p90": r.p90, "segment": "forecast"} for r in fc.results]
    )
    chart_df = pd.concat([hist, future], ignore_index=True).set_index("date")
    st.line_chart(chart_df[["p10", "p50", "p90"]])

with col_stats:
    st.subheader("Trend")
    st.metric("Direction", fc.stats.trend_direction.title())
    st.metric("Avg P50 / day", f"${fc.stats.avg_p50:,.0f}")
    st.metric("Confidence range", f"{fc.stats.confidence_range_pct:.0f}%")
    if result.anomaly_count:
        st.caption(f"⚠ {result.anomaly_count} anomalous day(s) detected in the input data.")

st.divider()

# ---------------------------------------------------------------------------
# Budget-response — interactive spend slider on top of the fitted curve
# ---------------------------------------------------------------------------
st.subheader("Budget-response simulator")

if result.response_curve is None:
    st.info("Not enough spend data to fit a budget-response curve.")
else:
    curve = result.response_curve
    default_spend = float(pd.to_numeric(clean_df["spend"], errors="coerce").mean() or 0.0)
    spend = st.slider(
        "Daily spend ($)",
        min_value=0.0,
        max_value=max(default_spend * 3, 100.0),
        value=default_spend,
        step=10.0,
    )
    scenarios = simulate_budget_scenarios(curve, baseline_spend=default_spend, multipliers=[spend / default_spend] if default_spend > 0 else None)
    if scenarios:
        s = scenarios[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Predicted daily revenue", f"${s.predicted_daily_revenue:,.0f}")
        c2.metric("Predicted ROAS", f"{s.predicted_roas:.2f}×")
        c3.metric("vs. current spend", f"{s.delta_spend_pct:+.0f}%")
    st.caption(
        f"Curve fit: R²={curve.r_squared:.2f} on {curve.n_points} days, "
        f"observed spend range ${curve.spend_min:,.0f}–${curve.spend_max:,.0f}. "
        "Predictions get shakier the further `Daily spend` is from that observed range."
    )

st.divider()

# ---------------------------------------------------------------------------
# Incrementality — mandatory disclaimer, always rendered with the figure
# (mirrors frontend/.../IncrementalityBadge.tsx's enforcement of design-doc
# ground rule #7).
# ---------------------------------------------------------------------------
st.subheader("Incrementality")

inc = result.incrementality
if inc is None:
    st.info("Not enough spend/revenue data to estimate an incrementality signal (need at least 7 days with spend > 0).")
else:
    pct = round(inc.incrementality_fraction * 100)
    badge_col, text_col = st.columns([1, 3])
    with badge_col:
        st.metric(f"{inc.confidence.title()} confidence", f"{pct}%")
    with text_col:
        st.write(
            f"${inc.avg_actual_revenue:,.0f}/day average revenue, of which an estimated "
            f"${inc.incremental_revenue:,.0f}/day looks incremental to spend, above a "
            f"${inc.baseline_revenue:,.0f}/day baseline."
        )
    if inc.baseline_extrapolated:
        st.info(
            "Daily spend in this data never gets close to $0, so the zero-spend baseline above "
            "is extrapolated well outside the observed range — treat it as a rough upper bound, "
            "not a precise estimate. That's why confidence is capped at \"low\" here."
        )
    st.markdown(f"**{INCREMENTALITY_DISCLAIMER}.** This is a statistical signal derived from a fitted "
                f"spend→revenue curve, not a controlled experiment — it does not prove that spend caused this revenue.")

st.divider()

# ---------------------------------------------------------------------------
# Narration — template by default, LLM only if explicitly opted in
# ---------------------------------------------------------------------------
st.subheader("Summary")
payload = build_insights_payload(result)
if use_llm:
    with st.spinner("Narrating…"):
        text, source = get_narration(payload)
else:
    from backend.llm.prompt_template import build_template_summary
    text, source = build_template_summary(payload), "template"

st.write(text)
st.caption(f"Narration source: {source}")
