"""
core.ingestion — load and normalize CSV data from any supported
e-commerce / ad-platform export format.
"""

from .loaders import load_csv, load_data_dir
from .schema import (
    REQUIRED_COLUMNS,
    OPTIONAL_COLUMNS,
    normalize_columns,
    validate_schema,
    coerce_types,
)

__all__ = [
    "load_csv",
    "load_data_dir",
    "REQUIRED_COLUMNS",
    "OPTIONAL_COLUMNS",
    "normalize_columns",
    "validate_schema",
    "coerce_types",
]
