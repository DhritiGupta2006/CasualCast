"""
backend/llm — narration layer.

Turns the numbers core/ already computed (surfaced via backend/api/routes)
into plain-English prose using the Anthropic API. This package never
computes or alters a number itself -- it only narrates numbers handed to
it as plain dicts/floats by the caller.

Not imported by core/ or src/, and its only third-party dependency
(the `anthropic` SDK) lives in backend/requirements-backend.txt, never in
the root requirements.txt used by the scored batch pipeline.
"""
