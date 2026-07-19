"""
Schema definitions and column-name normalization for CausalCast ingestion.

Handles the many naming conventions across GA4, Shopify, Google Ads, Bing Ads
and other e-commerce / ad-platform CSV exports — maps them all to a single
canonical set of column names so downstream core/ modules never need to care
about the source platform.

No network access, no LLM SDK, no absolute paths.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Canonical column names used throughout core/
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS: List[str] = ["date", "spend", "revenue"]
OPTIONAL_COLUMNS: List[str] = ["sessions", "channel"]
ALL_EXPECTED: List[str] = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

# ---------------------------------------------------------------------------
# Synonym dictionary  (normalized-header → canonical name)
#
# Keys are lowercase, all non-alphanumeric characters stripped, so
# "Time Period", "time_period", "TimePeriod" all map to the same entry.
# ---------------------------------------------------------------------------

_SYNONYM_LISTS: Dict[str, List[str]] = {
    "date": [
        "date", "day", "timeperiod", "period", "reportingdate",
        "reportdate", "timestamp", "datetime", "weekof", "weekstarting",
        "monthof", "dateperiod", "activitydate", "statdate",
    ],
    "spend": [
        "spend", "cost", "adspend", "amountspent", "totalspend",
        "mediaspend", "adcost", "expense", "spendusd", "costusd",
        "totalcost",
    ],
    "revenue": [
        "revenue", "sales", "income", "conversionvalue",
        "conversionsvalue", "totalrevenue", "revenueusd",
        "grossrevenue", "totalsales", "orderrevenue",
        "conversionvalueall", "totalconversionvalue",
    ],
    "sessions": [
        "sessions", "visits", "traffic", "clicks", "users",
        "pageviews", "visitors",
    ],
    "channel": [
        "channel", "source", "medium", "sourcemedium",
        "channelgrouping", "defaultchannelgrouping", "campaignsource",
    ],
}

_SYNONYM_MAP: Dict[str, str] = {}
for _canonical, _synonyms in _SYNONYM_LISTS.items():
    for _syn in _synonyms:
        _SYNONYM_MAP[_syn] = _canonical


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _norm(name: str) -> str:
    """Lowercase, strip all non-alphanumeric characters."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _is_micros(raw_name: str) -> bool:
    """Does the raw column header indicate values are in micro-units?

    Google Ads exports cost as "metrics.cost_micros" (millionths of currency).
    """
    return bool(re.search(r"micro", raw_name, re.IGNORECASE))


def _match_synonym(normed: str) -> Optional[str]:
    """Find the canonical column name for a normalised header string.

    Tries an exact match first, then a suffix match (longest suffix wins)
    to handle prefixed headers like "metricscost" → endswith "cost" → "spend".
    """
    # Exact match — fast path
    if normed in _SYNONYM_MAP:
        return _SYNONYM_MAP[normed]

    # Suffix match — longest synonym first to prefer "totalcost" over "cost"
    best: Optional[Tuple[int, str]] = None
    for syn, canonical in _SYNONYM_MAP.items():
        if len(syn) >= 4 and normed.endswith(syn):
            if best is None or len(syn) > best[0]:
                best = (len(syn), canonical)
    return best[1] if best else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Rename DataFrame columns to canonical names; detect and scale micros.

    Returns
    -------
    (normalized_df, notes)
        *notes* lists any automatic unit conversions applied so the caller
        can surface them in the UI or logs.
    """
    df = df.copy()
    rename_map: Dict[str, str] = {}
    used_canonical: set[str] = set()
    notes: List[str] = []

    for col in df.columns:
        normed = _norm(col)
        has_micros = _is_micros(col)

        # For micros columns strip "micro"/"micros" before synonym lookup
        # so "costmicros" → "cost" → matches "spend".
        lookup = re.sub(r"micro[s]?", "", normed) if has_micros else normed

        canonical = _match_synonym(lookup)

        if canonical is not None and canonical not in used_canonical:
            # Scale micros before renaming
            if has_micros and canonical in ("spend", "revenue", "sessions"):
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0) * 1e-6
                notes.append(
                    f'"{col}" detected as micro-units — divided by 1,000,000.'
                )
            rename_map[col] = canonical
            used_canonical.add(canonical)

    df = df.rename(columns=rename_map)
    return df, notes


def validate_schema(df: pd.DataFrame) -> List[str]:
    """Check that required columns are present and data is non-empty.

    Returns a list of human-readable error strings (empty = valid).
    """
    errors: List[str] = []

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            errors.append(f"Required column '{col}' is missing.")

    if len(df) == 0:
        errors.append("DataFrame is empty — no rows to process.")

    if "date" in df.columns and df["date"].isna().all():
        errors.append("Column 'date' contains no parseable values.")

    return errors


def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Convert columns to their expected types.

    - date    → parsed to datetime, then formatted as YYYY-MM-DD strings.
                Rows with unparseable dates are dropped.
    - spend, revenue, sessions → float64.  Currency symbols ($,€,£) and
      thousands commas are stripped before conversion.
    """
    df = df.copy()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    for col in ("spend", "revenue", "sessions"):
        if col in df.columns:
            # Always convert to plain Python str first so the regex
            # replacement works regardless of pandas' dtype backend
            # (object vs StringDtype in pandas 3.x).
            series_str = df[col].astype(str)
            cleaned = series_str.str.replace(r"[\$,€£]", "", regex=True)
            df[col] = pd.to_numeric(cleaned, errors="coerce").fillna(0.0)

    return df
