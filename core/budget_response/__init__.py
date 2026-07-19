"""
core.budget_response — fit and predict budget-response (spend → revenue)
curves for budget simulation.
"""

from .fit import fit_response_curve, ResponseCurve
from .predict import predict_revenue, simulate_budget_scenarios

__all__ = [
    "fit_response_curve",
    "ResponseCurve",
    "predict_revenue",
    "simulate_budget_scenarios",
]
