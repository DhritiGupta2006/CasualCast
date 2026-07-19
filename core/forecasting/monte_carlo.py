"""
Monte Carlo simulation — generate many possible future revenue paths
from a decomposed model (trend + seasonality + noise) and extract
percentile bands.

Every stochastic operation uses a **seeded** ``numpy.random.Generator``
so the same input always produces the same output.

No network access, no LLM SDK, no absolute paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd


DEFAULT_ITERATIONS = 1000
DEFAULT_HORIZON = 30
DEFAULT_SEED = 42


@dataclass(frozen=True)
class SimulationResult:
    """Raw output of a Monte Carlo simulation run."""
    paths: np.ndarray          # shape (iterations, horizon)
    dates: List[str]           # ISO date strings for each horizon day


@dataclass(frozen=True)
class PercentileResult:
    """P10 / P50 / P90 bands derived from simulated paths."""
    dates: List[str]
    p10: np.ndarray
    p50: np.ndarray
    p90: np.ndarray


def simulate_paths(
    n_history: int,
    slope: float,
    intercept: float,
    std_dev: float,
    seasonal_offsets: List[float],
    last_date: str,
    iterations: int = DEFAULT_ITERATIONS,
    horizon: int = DEFAULT_HORIZON,
    seed: int = DEFAULT_SEED,
) -> SimulationResult:
    """Simulate *iterations* future revenue paths.

    Each path extends the linear trend, adds weekday seasonality, and
    injects Gaussian noise drawn from the historical residual volatility.

    Parameters
    ----------
    n_history : int
        Number of historical data points (used to continue the trend
        index beyond the last observed day).
    slope, intercept : float
        Linear trend parameters from :func:`linear_trend`.
    std_dev : float
        Standard deviation of historical residuals.
    seasonal_offsets : list of 7 floats
        Additive weekday offsets (Mon=0 … Sun=6).
    last_date : str
        ISO date of the last historical observation.
    iterations : int
        Number of Monte Carlo paths.
    horizon : int
        Number of days to forecast.
    seed : int
        RNG seed for reproducibility.

    Returns
    -------
    SimulationResult with a ``paths`` array of shape (iterations, horizon)
    and a list of ISO date strings.
    """
    rng = np.random.default_rng(seed)
    last_dt = pd.Timestamp(last_date)

    dates: List[str] = []
    for h in range(1, horizon + 1):
        d = last_dt + pd.Timedelta(days=h)
        dates.append(d.strftime("%Y-%m-%d"))

    paths = np.empty((iterations, horizon), dtype=float)

    for it in range(iterations):
        for h in range(horizon):
            idx = n_history + h   # continue the trend index
            future_dt = last_dt + pd.Timedelta(days=h + 1)
            dow = future_dt.dayofweek
            seasonal = seasonal_offsets[dow] if len(seasonal_offsets) == 7 else 0.0
            noise = rng.normal(0, std_dev)
            value = slope * idx + intercept + seasonal + noise
            paths[it, h] = max(0.0, value)  # revenue can't be negative

    return SimulationResult(paths=paths, dates=dates)


def percentiles_from_paths(sim: SimulationResult) -> PercentileResult:
    """Extract P10 / P50 / P90 bands from simulated paths.

    Parameters
    ----------
    sim : SimulationResult from :func:`simulate_paths`.

    Returns
    -------
    PercentileResult with arrays for each percentile band.
    """
    p10 = np.percentile(sim.paths, 10, axis=0)
    p50 = np.percentile(sim.paths, 50, axis=0)
    p90 = np.percentile(sim.paths, 90, axis=0)

    return PercentileResult(
        dates=sim.dates,
        p10=p10,
        p50=p50,
        p90=p90,
    )
