"""
CausalCast core — shared, network-free forecasting library.

Imported by BOTH the scored batch pipeline (src/) and the live FastAPI
backend (backend/api/).  Contains no LLM code, no network I/O beyond
reading files it is explicitly given a path to.
"""

__version__ = "0.1.0"
