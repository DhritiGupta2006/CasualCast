"""
core.incrementality — directional incrementality signal estimation.
"""

from .signal import estimate_incrementality, IncrementalityResult

__all__ = [
    "estimate_incrementality",
    "IncrementalityResult",
]
