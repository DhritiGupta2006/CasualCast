"""
core.forecasting — trend decomposition, Monte Carlo simulation, and the
main forecasting engine.
"""

from .engine import forecast
from .trend_decomposition import linear_trend, decompose
from .monte_carlo import simulate_paths, percentiles_from_paths

__all__ = [
    "forecast",
    "linear_trend",
    "decompose",
    "simulate_paths",
    "percentiles_from_paths",
]
