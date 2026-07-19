"""
POST /api/upload

Accepts a raw CSV file (GA4/Shopify/ad-platform export, or anything with
recognizable date/spend/revenue-like columns), runs it through the exact
same core.ingestion + core.preprocessing steps src/generate_features.py
uses for the batch pipeline, and returns the cleaned, canonical rows.

This route is stateless -- CausalCast has no database. The frontend holds
the returned `rows` in memory and passes them back on subsequent calls to
/api/forecast, /api/simulate-budget, and /api/insights. That keeps the
live product simple while still guaranteeing every number downstream is
computed by core/, never by the frontend or by this route itself.
"""

from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from core.ingestion.schema import coerce_types, normalize_columns, validate_schema
from core.preprocessing.anomalies import flag_anomalies
from core.preprocessing.taxonomy import add_channel_group

from ..dataframes import df_to_records

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB -- generous for a CSV of daily rows


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB).")
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        raw_df = pd.read_csv(io.BytesIO(raw_bytes))
    except Exception as exc:  # noqa: BLE001 -- surfaced to the caller, not swallowed
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}") from exc

    # --- Ingestion: same normalize/coerce/validate as core.ingestion.loaders.load_csv,
    # done here on an in-memory frame instead of a file path since the CSV
    # arrived over the wire rather than living in data/. ---
    df, notes = normalize_columns(raw_df)
    df = coerce_types(df)

    errors = validate_schema(df)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    # --- Preprocessing preview (taxonomy + anomalies) so the UI can show
    # something useful immediately, without waiting on a forecast run. ---
    df = add_channel_group(df)
    df = flag_anomalies(df, column="revenue")
    df = df.sort_values("date").reset_index(drop=True)

    anomaly_count = int(df["is_anomaly"].sum())
    channel_groups = sorted(df["channel_group"].unique().tolist())

    # Return only the canonical columns the frontend/other routes expect
    # (DataRow), regardless of which optional columns this particular
    # export happened to include.
    out_cols = [c for c in ("date", "spend", "revenue", "sessions", "channel") if c in df.columns]

    return {
        "rows": df_to_records(df[out_cols]),
        "row_count": len(df),
        "notes": notes,
        "anomaly_count": anomaly_count,
        "channel_groups": channel_groups,
        "date_range": [str(df["date"].min()), str(df["date"].max())],
    }
