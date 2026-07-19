"""
Channel taxonomy — map raw channel / source / medium strings to a
standardised group so downstream analysis can aggregate consistently
across different ad-platform naming conventions.

No network access, no LLM SDK, no absolute paths.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Standard channel groups (intentionally small and opinionated)
# ---------------------------------------------------------------------------

CHANNEL_GROUPS = [
    "Paid Search",
    "Paid Social",
    "Paid Display",
    "Paid Video",
    "Organic Search",
    "Organic Social",
    "Email",
    "Direct",
    "Referral",
    "Affiliate",
    "Other",
]

# ---------------------------------------------------------------------------
# Pattern-based classifier  (order matters — first match wins)
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, str]] = [
    # Paid channels
    (r"google\s*ads|adwords|sem|ppc|paid\s*search|search\s*ads|bing\s*ads|microsoft\s*ads", "Paid Search"),
    (r"facebook\s*ads|fb\s*ads|instagram\s*ads|meta\s*ads|paid\s*social|tiktok\s*ads|snapchat\s*ads|linkedin\s*ads|pinterest\s*ads", "Paid Social"),
    (r"display|gdn|programmatic|banner|dv360", "Paid Display"),
    (r"youtube\s*ads|video\s*ads|paid\s*video|ott|ctv", "Paid Video"),
    # Organic
    (r"organic\s*search|seo|google\s*/\s*organic|bing\s*/\s*organic", "Organic Search"),
    (r"organic\s*social|facebook\s*/\s*organic|instagram\s*/\s*organic", "Organic Social"),
    # Other named channels
    (r"email|newsletter|mailchimp|klaviyo|sendgrid", "Email"),
    (r"direct|none|^\(direct\)$|^\(none\)$", "Direct"),
    (r"referral|partner", "Referral"),
    (r"affiliate|impact|commission", "Affiliate"),
]

_COMPILED = [(re.compile(pat, re.IGNORECASE), group) for pat, group in _PATTERNS]


def classify_channel(raw: Optional[str]) -> str:
    """Return a standard group name for a raw channel/source string.

    >>> classify_channel("google / cpc")
    'Paid Search'
    >>> classify_channel(None)
    'Other'
    """
    if raw is None or (isinstance(raw, float) and raw != raw):  # NaN check
        return "Other"
    text = str(raw).strip()
    if not text:
        return "Other"
    for pattern, group in _COMPILED:
        if pattern.search(text):
            return group
    return "Other"


def add_channel_group(df: pd.DataFrame, source_col: str = "channel") -> pd.DataFrame:
    """Add a ``channel_group`` column by classifying *source_col*.

    If *source_col* doesn't exist the column is filled with ``'Other'``.
    The original *source_col* is preserved.
    """
    df = df.copy()
    if source_col in df.columns:
        df["channel_group"] = df[source_col].apply(classify_channel)
    else:
        df["channel_group"] = "Other"
    return df
