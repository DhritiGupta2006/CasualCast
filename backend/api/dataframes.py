"""
DataFrame <-> JSON helpers shared across backend/api routes.

Kept in backend/ (not core/) since it's purely a web-response concern --
core/ never knows about JSON, HTTP, or FastAPI.
"""

from __future__ import annotations

import json
from typing import List

import pandas as pd

from fastapi import HTTPException

from core.ingestion.schema import coerce_types, validate_schema
from .schemas import DataRow


def df_to_records(df: pd.DataFrame) -> List[dict]:
    """Convert a DataFrame to plain-Python-typed dict records.

    Round-trips through ``DataFrame.to_json`` rather than
    ``to_dict(orient="records")`` so numpy/pandas scalar types (np.float64,
    np.bool_, pd.Timestamp, NaN) never leak into the HTTP response --
    everything comes back as native Python str/float/int/None.
    """
    return json.loads(df.to_json(orient="records"))


def rows_to_clean_df(rows: List[DataRow]) -> pd.DataFrame:
    """Build a validated, type-coerced DataFrame from request rows.

    Raises HTTPException(400/422) the same way every route needs to, so
    each route can call this once instead of repeating the boilerplate.
    """
    if not rows:
        raise HTTPException(status_code=400, detail="No data rows provided.")

    df = pd.DataFrame([r.model_dump() for r in rows])
    df = coerce_types(df)

    errors = validate_schema(df)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    return df
