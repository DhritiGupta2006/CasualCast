"""
Anomaly detection — flag outlier days so downstream forecasting can
decide whether to clip, down-weight, or keep them.

Uses a robust IQR-based method (no trained model needed, deterministic,
works on small datasets) rather than Z-scores which assume normality.

No network access, no LLM SDK, no absolute paths.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def flag_anomalies(
    df: pd.DataFrame,
    column: str = "revenue",
    iqr_multiplier: float = 1.5,
    min_rows: int = 7,
) -> pd.DataFrame:
    """Add an ``is_anomaly`` boolean column based on the IQR fence method.

    Parameters
    ----------
    df : DataFrame
        Must contain *column* with numeric values.
    column : str
        Which numeric column to check for outliers.
    iqr_multiplier : float
        How many IQRs beyond Q1/Q3 count as an outlier.  The classic
        Tukey fence uses 1.5; use 2.0–3.0 for a more conservative gate.
    min_rows : int
        If the DataFrame has fewer rows than this, nothing is flagged
        (too little data to reliably identify outliers).

    Returns
    -------
    DataFrame with an added ``is_anomaly`` column (bool).
    """
    df = df.copy()

    if column not in df.columns or len(df) < min_rows:
        df["is_anomaly"] = False
        return df

    values = pd.to_numeric(df[column], errors="coerce")
    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    iqr = q3 - q1

    lower = q1 - iqr_multiplier * iqr
    upper = q3 + iqr_multiplier * iqr

    df["is_anomaly"] = (values < lower) | (values > upper)
    return df


def clip_anomalies(
    df: pd.DataFrame,
    column: str = "revenue",
    iqr_multiplier: float = 1.5,
    min_rows: int = 7,
) -> pd.DataFrame:
    """Replace outlier values with the fence boundary (Winsorisation).

    Same IQR logic as :func:`flag_anomalies` but instead of flagging,
    clips values to ``[lower_fence, upper_fence]``.
    """
    df = df.copy()

    if column not in df.columns or len(df) < min_rows:
        return df

    values = pd.to_numeric(df[column], errors="coerce")
    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    iqr = q3 - q1

    lower = q1 - iqr_multiplier * iqr
    upper = q3 + iqr_multiplier * iqr

    df[column] = values.clip(lower=lower, upper=upper)
    return df
