"""
Shared pydantic models for backend/api routes.

These are thin request/response wrappers only -- they never compute a
forecast number themselves. Every route hands the underlying DataFrame to
core/ and serializes whatever core/ returns.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class DataRow(BaseModel):
    """One day of ingested spend/revenue data.

    Mirrors core.ingestion.schema's canonical columns (date, spend,
    revenue, sessions, channel) so a DataFrame built from a list of these
    can go straight into core.ingestion.schema.coerce_types /
    validate_schema without any renaming.
    """

    date: str
    spend: float
    revenue: float
    sessions: Optional[float] = None
    channel: Optional[str] = None


class ForecastRequest(BaseModel):
    rows: List[DataRow]
    horizon: int = Field(default=30, ge=1, le=180)
    iterations: int = Field(default=1000, ge=100, le=5000)
    seed: int = 42


class SimulateBudgetRequest(BaseModel):
    rows: List[DataRow]
    baseline_spend: Optional[float] = Field(default=None, gt=0)
    multipliers: Optional[List[float]] = None


class InsightsRequest(BaseModel):
    rows: List[DataRow]
