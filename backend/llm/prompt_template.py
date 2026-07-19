"""
Prompt construction + the deterministic template fallback for the LLM
narration layer.

Both `build_user_message` (what we send to the model) and
`build_template_summary` (what we show if there's no model call at all)
work off the exact same plain-dict payload -- the JSON shape
backend/api/routes/insights.py already builds from core/'s output before
this module ever sees it. Neither function imports anything from core/;
they only read numbers out of a dict, so this file has no way to
compute or alter a forecast number, only describe one.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

# Canonical disclaimer string. Imported from core/ (not redefined here) so
# there is exactly one source of truth for its exact wording -- the same
# string core.incrementality.signal.INCREMENTALITY_DISCLAIMER exports and
# frontend/.../IncrementalityBadge.tsx renders.
from core.incrementality.signal import INCREMENTALITY_DISCLAIMER

SYSTEM_PROMPT = f"""You are a narration layer for CausalCast, a marketing-analytics \
forecasting tool. You will be given a JSON object containing numbers that \
have ALREADY been computed by a deterministic statistics pipeline -- \
trend direction and slope, forecast P50, an incrementality estimate, \
anomaly counts, and a top budget scenario.

Your only job is to narrate these numbers in plain, confident, marketer-\
friendly English. Rules, no exceptions:

1. Never invent, compute, adjust, round differently, or contradict a \
   number in the JSON. Every figure you mention must come directly from \
   the JSON you were given.
2. Do not invent facts not present in the JSON (no causes, no external \
   events, no comparisons to industry benchmarks).
3. If the JSON's "incrementality" field is not null, your narration MUST \
   include this exact sentence verbatim, unmodified, somewhere in your \
   response: "{INCREMENTALITY_DISCLAIMER}."
4. If "anomaly_count" is greater than 0, mention it briefly.
5. If "warnings" is non-empty, briefly note that data-quality warnings \
   were raised.
6. Write 2-4 sentences of plain prose. No markdown, no bullet points, no \
   headers, no emoji.
7. Never mention that you are an AI, a model, or that this text was \
   generated -- write as a plain analytics summary.
"""


def build_user_message(payload: Dict[str, Any]) -> str:
    """The only content sent to the model: the numbers themselves, as JSON,
    with no additional instructions (those live in SYSTEM_PROMPT so they
    can't be confused with data)."""
    return json.dumps(payload, indent=2, default=str)


def build_template_summary(payload: Dict[str, Any]) -> str:
    """Deterministic, no-network, no-model narration built with plain
    string formatting. This is what /api/insights returns when there's no
    API key, the `anthropic` package isn't installed, or the LLM call
    fails for any reason -- so the insight panel is never blank or broken.
    """
    trend = payload.get("trend") or {}
    inc = payload.get("incrementality")
    anomaly_count = payload.get("anomaly_count") or 0
    warnings = payload.get("warnings") or []

    parts = []

    direction = trend.get("direction", "flat")
    avg_p50 = trend.get("avg_p50")
    if avg_p50 is not None:
        parts.append(f"Revenue trend is {direction} (avg P50 ~${avg_p50:,.0f}/day over the forecast window).")
    else:
        parts.append(f"Revenue trend is {direction}.")

    if inc is not None:
        fraction = inc.get("incrementality_fraction", 0.0)
        confidence = inc.get("confidence", "low")
        disclaimer = inc.get("disclaimer", INCREMENTALITY_DISCLAIMER)
        parts.append(
            f"Roughly {fraction:.0%} of revenue looks incremental to spend "
            f"({confidence} confidence) -- {disclaimer.lower()}."
        )

    if anomaly_count:
        parts.append(
            f"{anomaly_count} anomalous day(s) were detected in the input data and may be widening the "
            f"confidence bands."
        )

    if warnings:
        parts.append(f"{len(warnings)} data-quality warning(s) were raised for this dataset.")

    return " ".join(parts)


def ensure_disclaimer(text: str, payload: Dict[str, Any]) -> str:
    """Belt-and-suspenders enforcement of rule 3 above. The model is told
    to include the disclaimer verbatim, but this layer never trusts a
    model to always follow instructions -- if an incrementality figure is
    present and the disclaimer text isn't found in the model's output
    (case-insensitively), it's appended rather than silently omitted.
    """
    inc = payload.get("incrementality")
    if inc is None:
        return text
    disclaimer: Optional[str] = inc.get("disclaimer") or INCREMENTALITY_DISCLAIMER
    if disclaimer.lower() not in text.lower():
        text = text.rstrip()
        if not text.endswith((".", "!", "?")):
            text += "."
        text += f" ({disclaimer}.)"
    return text
