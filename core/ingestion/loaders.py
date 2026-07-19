"""
CSV loaders for CausalCast ingestion.

Loads raw CSV files from a single path or an entire directory, normalises
columns via ``schema``, coerces types, and validates that required fields
are present — returning a clean ``pandas.DataFrame`` ready for downstream
preprocessing.

No network access, no LLM SDK, no absolute paths beyond what the caller
passes in.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import pandas as pd

from .schema import coerce_types, normalize_columns, validate_schema


def load_csv(
    file_path: str,
) -> Tuple[pd.DataFrame, List[str]]:
    """Load a single CSV file, normalise, coerce, and validate.

    Parameters
    ----------
    file_path : str
        Path to the CSV file (relative or absolute — caller decides).

    Returns
    -------
    (df, notes)
        *df* has canonical column names and correct dtypes.
        *notes* records any automatic conversions (e.g. micros scaling).

    Raises
    ------
    FileNotFoundError
        If *file_path* does not exist.
    ValueError
        If required columns are missing after normalisation.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    raw = pd.read_csv(path)
    df, notes = normalize_columns(raw)
    df = coerce_types(df)

    errors = validate_schema(df)
    if errors:
        raise ValueError(
            f"Schema validation failed for {file_path}: {'; '.join(errors)}"
        )

    return df, notes


def load_data_dir(
    data_dir: str,
) -> Tuple[pd.DataFrame, List[str]]:
    """Load every CSV in *data_dir*, concatenate, normalise, and validate.

    Parameters
    ----------
    data_dir : str
        Directory containing one or more ``.csv`` files.

    Returns
    -------
    (df, notes)

    Raises
    ------
    FileNotFoundError
        If *data_dir* contains no CSV files.
    ValueError
        If required columns are missing after normalisation.
    """
    csv_files = sorted(Path(data_dir).glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    frames: List[pd.DataFrame] = []
    for f in csv_files:
        frames.append(pd.read_csv(f))

    combined = pd.concat(frames, ignore_index=True)
    combined, notes = normalize_columns(combined)
    combined = coerce_types(combined)

    errors = validate_schema(combined)
    if errors:
        raise ValueError(f"Schema validation failed: {'; '.join(errors)}")

    return combined, notes
