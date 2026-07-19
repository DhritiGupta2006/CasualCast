"""
Forecasting engine — the single entry point that orchestrates
trend decomposition, Monte Carlo simulation, and result assembly.

Takes a clean daily DataFrame (from ingestion + preprocessing) and
returns a structured forecast with P10/P50/P90 bands plus summary stats.

Deterministic (seeded), no network access, no LLM SDK, no absolute paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd

from .monte_carlo import (
    DEFAULT_HORIZON,
    DEFAULT_ITERATIONS,
    DEFAULT_SEED,
    percentiles_from_paths,
    simulate_paths,
)
from .trend_decomposition import decompose


@dataclass(frozen=True)
class ForecastRow:
    """A single day in the forecast output."""
    date: str
    p10: float
    p50: float
    p90: float


@dataclass(frozen=True)
class ForecastStats:
    """Summary statistics for the whole forecast."""
    avg_p10: float
    avg_p50: float
    avg_p90: float
    confidence_range_pct: float  # (P90−P10)/P50 as a percentage
    trend_direction: str         # "up", "down", or "flat"
    slope: float                 # raw slope from linear trend


@dataclass(frozen=True)
class ForecastOutput:
    """Complete forecast result — everything the API or pipeline needs."""
    results: List[ForecastRow]
    historical: pd.DataFrame      # the input data, sorted by date
    stats: ForecastStats
    horizon: int
    iterations: int


def forecast(
    df: pd.DataFrame,
    column: str = "revenue",
    horizon: int = DEFAULT_HORIZON,
    iterations: int = DEFAULT_ITERATIONS,
    seed: int = DEFAULT_SEED,
) -> ForecastOutput:
    """Run a full Monte Carlo forecast on a daily time-series DataFrame.

    Parameters
    ----------
    df : DataFrame
        Must have ``date`` and *column* (plus ``spend``, ``sessions`` if
        available).  Should be daily granularity, sorted by date.
    column : str
        Numeric column to forecast (default ``"revenue"``).
    horizon : int
        Number of days to forecast forward.
    iterations : int
        Number of Monte Carlo simulation paths.
    seed : int
        RNG seed — same seed + same data = same output.

    Returns
    -------
    ForecastOutput containing per-day P10/P50/P90 rows, summary stats,
    and the historical data used.
    """
    # --- Ensure sorted by date ---
    work = df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    work["date"] = work["date"].dt.strftime("%Y-%m-%d")

    # --- Decompose: trend + seasonality + residuals ---
    dec = decompose(work, column=column)
    n_history = len(work)
    last_date = work["date"].iloc[-1]

    # --- Simulate forward paths ---
    sim = simulate_paths(
        n_history=n_history,
        slope=dec.trend.slope,
        intercept=dec.trend.intercept,
        std_dev=dec.trend.std_dev,
        seasonal_offsets=dec.seasonal_offsets,
        last_date=last_date,
        iterations=iterations,
        horizon=horizon,
        seed=seed,
    )
    pct = percentiles_from_paths(sim)

    # --- Assemble results ---
    results: List[ForecastRow] = []
    for i in range(horizon):
        results.append(ForecastRow(
            date=pct.dates[i],
            p10=round(float(pct.p10[i])),
            p50=round(float(pct.p50[i])),
            p90=round(float(pct.p90[i])),
        ))

    # --- Summary stats ---
    avg_p10 = round(float(pct.p10.mean()))
    avg_p50 = round(float(pct.p50.mean()))
    avg_p90 = round(float(pct.p90.mean()))
    conf_range = (
        round(((avg_p90 - avg_p10) / avg_p50) * 100)
        if avg_p50 > 0 else 0
    )
    direction = (
        "up" if dec.trend.slope > 0.5
        else "down" if dec.trend.slope < -0.5
        else "flat"
    )

    stats = ForecastStats(
        avg_p10=avg_p10,
        avg_p50=avg_p50,
        avg_p90=avg_p90,
        confidence_range_pct=conf_range,
        trend_direction=direction,
        slope=round(dec.trend.slope, 4),
    )

    return ForecastOutput(
        results=results,
        historical=work,
        stats=stats,
        horizon=horizon,
        iterations=iterations,
    )
