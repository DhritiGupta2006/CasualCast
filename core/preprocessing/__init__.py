"""
core.preprocessing — clean and enrich ingested data before forecasting.

Modules:
  taxonomy    — map raw channel/source names to a standard grouping
  anomalies   — detect and flag outlier days (promos, outages, etc.)
  seasonality — extract weekday-level seasonality factors
"""

from .taxonomy import classify_channel, add_channel_group
from .anomalies import flag_anomalies
from .seasonality import weekday_factors, apply_seasonal_adjustment

__all__ = [
    "classify_channel",
    "add_channel_group",
    "flag_anomalies",
    "weekday_factors",
    "apply_seasonal_adjustment",
]
