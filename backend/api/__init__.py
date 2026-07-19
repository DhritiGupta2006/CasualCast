"""
backend.api — live FastAPI product surface for CausalCast.

Everything here calls into core/ directly (never src/) so live-demo
numbers and the scored batch pipeline can never diverge on the same
input. Nothing in core/ or src/ imports anything from backend/ — the
dependency only flows one direction.
"""
