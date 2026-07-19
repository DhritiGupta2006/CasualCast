"""
LLM narration -- turns a numbers payload already computed by core/ into
prose via the Anthropic API, with a deterministic template fallback.

`narrate()` NEVER raises. Any failure -- missing API key, missing
`anthropic` package, network error, timeout, auth error, empty response --
degrades to the template summary from prompt_template.build_template_summary
and reports narration_source="template". The live demo's numeric surfaces
(forecast chart, budget simulator, incrementality figure) never depend on
this call succeeding.

The `anthropic` import is optional on purpose: core/ and src/ never import
this module (see backend/llm/__init__.py), but backend/api/routes/insights.py
does, and that route must keep working even in an environment where
`pip install -r backend/requirements-backend.txt` hasn't been run yet.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Literal

from .prompt_template import SYSTEM_PROMPT, build_template_summary, build_user_message, ensure_disclaimer

logger = logging.getLogger(__name__)

try:
    import anthropic
except ImportError:  # pragma: no cover -- exercised when requirements-backend.txt isn't installed
    anthropic = None  # type: ignore[assignment]

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
MAX_TOKENS = 300
TEMPERATURE = 0.3
REQUEST_TIMEOUT_SECONDS = 12.0
# Hard ceiling on top of the client's own timeout, so a misbehaving SDK call
# can never hang the /api/insights request indefinitely.
WAIT_FOR_TIMEOUT_SECONDS = REQUEST_TIMEOUT_SECONDS + 3.0

NarrationSource = Literal["llm", "template"]


@dataclass(frozen=True)
class NarrationResult:
    text: str
    source: NarrationSource


async def narrate(payload: Dict[str, Any]) -> NarrationResult:
    """Narrate `payload` (the same dict shape /api/insights returns to the
    frontend, minus the narration fields themselves) as prose.

    Falls back to a deterministic template summary -- never raises -- if:
    - ANTHROPIC_API_KEY isn't set,
    - the `anthropic` package isn't installed,
    - the API call errors, times out, or is rate-limited,
    - the model returns an empty response.
    """
    template_text = build_template_summary(payload)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return NarrationResult(text=template_text, source="template")
    if anthropic is None:
        logger.info("ANTHROPIC_API_KEY is set but the `anthropic` package isn't installed; using template narration.")
        return NarrationResult(text=template_text, source="template")

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)
        response = await asyncio.wait_for(
            client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_user_message(payload)}],
            ),
            timeout=WAIT_FOR_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 -- any failure degrades to template, never raises
        logger.warning("LLM narration failed (%s); falling back to template narration.", exc)
        return NarrationResult(text=template_text, source="template")

    text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text").strip()
    if not text:
        logger.warning("LLM narration returned an empty response; falling back to template narration.")
        return NarrationResult(text=template_text, source="template")

    text = ensure_disclaimer(text, payload)
    return NarrationResult(text=text, source="llm")
