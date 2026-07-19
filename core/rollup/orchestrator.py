"""
Pipeline orchestrator — runs the full CausalCast pipeline in order:

  ingestion → preprocessing → forecasting → budget_response → incrementality

Returns a single ``PipelineResult`` containing all outputs so callers
(``src/predict.py`` for the scored pipeline, ``backend/api`` for the live
demo) get one deterministic, self-contained result object.

No network access, no LLM SDK, no absolute paths beyond what the caller
passes in.  Every stochastic step uses the provided *seed*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from core.ingestion import load_csv, load_data_dir
from core.preprocessing.taxonomy import add_channel_group
from core.preprocessing.anomalies import flag_anomalies
from core.preprocessing.seasonality import weekday_factors
from core.forecasting.engine import forecast, ForecastOutput
from core.budget_response.fit import fit_response_curve, ResponseCurve
from core.budget_response.predict import simulate_budget_scenarios, BudgetScenario
from core.incrementality.signal import (
    estimate_incrementality,
    IncrementalityResult,
)


@dataclass
class PipelineResult:
    """Complete output of a full pipeline run."""
    # --- data ---
    data: pd.DataFrame                               # cleaned daily data
    anomaly_count: int = 0                            # rows flagged as anomalies
    channel_groups: List[str] = field(default_factory=list)
    weekday_factors: List[float] = field(default_factory=list)

    # --- forecasting ---
    forecast: Optional[ForecastOutput] = None

    # --- budget response ---
    response_curve: Optional[ResponseCurve] = None
    budget_scenarios: List[BudgetScenario] = field(default_factory=list)

    # --- incrementality ---
    incrementality: Optional[IncrementalityResult] = None

    # --- meta ---
    notes: List[str] = field(default_factory=list)    # conversion notes etc.
    warnings: List[str] = field(default_factory=list)


def run_pipeline(
    data_dir: Optional[str] = None,
    file_path: Optional[str] = None,
    df: Optional[pd.DataFrame] = None,
    horizon: int = 30,
    iterations: int = 1000,
    seed: int = 42,
    baseline_spend: Optional[float] = None,
    budget_multipliers: Optional[List[float]] = None,
) -> PipelineResult:
    """Run the full CausalCast pipeline.

    Exactly ONE of *data_dir*, *file_path*, or *df* must be provided.

    Parameters
    ----------
    data_dir : path to a directory of CSV files.
    file_path : path to a single CSV file.
    df : an already-loaded DataFrame (for the live API path).
    horizon : forecast horizon in days.
    iterations : number of Monte Carlo paths.
    seed : RNG seed for all stochastic steps.
    baseline_spend : daily spend for budget scenarios (defaults to mean).
    budget_multipliers : spend multipliers for scenario table.

    Returns
    -------
    PipelineResult with all outputs populated.
    """
    notes: List[str] = []
    warnings: List[str] = []

    # ------------------------------------------------------------------
    # 1. Ingestion
    # ------------------------------------------------------------------
    if df is not None:
        clean = df.copy()
    elif file_path is not None:
        clean, file_notes = load_csv(file_path)
        notes.extend(file_notes)
    elif data_dir is not None:
        clean, dir_notes = load_data_dir(data_dir)
        notes.extend(dir_notes)
    else:
        raise ValueError("Provide one of: data_dir, file_path, or df.")

    # ------------------------------------------------------------------
    # 2. Preprocessing
    # ------------------------------------------------------------------
    # 2a. Channel taxonomy
    clean = add_channel_group(clean)
    channel_groups = sorted(clean["channel_group"].unique().tolist())

    # 2b. Anomaly detection
    clean = flag_anomalies(clean, column="revenue")
    anomaly_count = int(clean["is_anomaly"].sum())
    if anomaly_count > 0:
        warnings.append(
            f"{anomaly_count} anomalous day(s) detected in revenue — "
            f"included in the analysis but may widen confidence bands."
        )

    # 2c. Weekday seasonality factors (informational — the forecast
    #     engine computes its own internally, but we surface these for
    #     the API / UI).
    wf = weekday_factors(clean, column="revenue")

    # ------------------------------------------------------------------
    # 3. Forecasting
    # ------------------------------------------------------------------
    fc = forecast(
        clean,
        column="revenue",
        horizon=horizon,
        iterations=iterations,
        seed=seed,
    )

    # ------------------------------------------------------------------
    # 4. Budget-response curve
    # ------------------------------------------------------------------
    curve = fit_response_curve(clean)
    scenarios: List[BudgetScenario] = []
    if curve is not None:
        b_spend = baseline_spend
        if b_spend is None:
            spend_col = pd.to_numeric(clean.get("spend"), errors="coerce")
            b_spend = float(spend_col.mean()) if spend_col is not None else 0.0
        if b_spend > 0:
            scenarios = simulate_budget_scenarios(
                curve, baseline_spend=b_spend, multipliers=budget_multipliers,
            )
    else:
        warnings.append(
            "Could not fit a budget-response curve — insufficient spend "
            "data.  Budget scenarios are unavailable."
        )

    # ------------------------------------------------------------------
    # 5. Incrementality
    # ------------------------------------------------------------------
    inc = estimate_incrementality(clean)
    if inc is None:
        warnings.append(
            "Could not estimate incrementality — insufficient data."
        )

    # ------------------------------------------------------------------
    # Assemble
    # ------------------------------------------------------------------
    return PipelineResult(
        data=clean,
        anomaly_count=anomaly_count,
        channel_groups=channel_groups,
        weekday_factors=wf,
        forecast=fc,
        response_curve=curve,
        budget_scenarios=scenarios,
        incrementality=inc,
        notes=notes,
        warnings=warnings,
    )
