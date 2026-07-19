"""
Tests for core.ingestion  (schema.py + loaders.py)

Run:  python -m pytest tests/test_core_ingestion.py -v
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from core.ingestion.schema import (
    REQUIRED_COLUMNS,
    coerce_types,
    normalize_columns,
    validate_schema,
)
from core.ingestion.loaders import load_csv, load_data_dir

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
TINY_SAMPLE = os.path.join(FIXTURE_DIR, "tiny_sample.csv")


# ===================================================================
# schema — normalize_columns
# ===================================================================

class TestNormalizeColumns:
    """Column renaming and micro-unit detection."""

    def test_standard_headers_unchanged(self):
        df = pd.DataFrame({
            "date": ["2026-06-01"],
            "spend": [900],
            "revenue": [4300],
            "sessions": [2100],
        })
        result, notes = normalize_columns(df)
        assert list(result.columns) == ["date", "spend", "revenue", "sessions"]
        assert notes == []

    def test_synonym_headers_renamed(self):
        """Common ad-platform header names should map to canonical ones."""
        df = pd.DataFrame({
            "Day": ["2026-06-01"],
            "Cost": [900],
            "Sales": [4300],
            "Clicks": [2100],
        })
        result, notes = normalize_columns(df)
        assert "date" in result.columns
        assert "spend" in result.columns
        assert "revenue" in result.columns
        assert "sessions" in result.columns
        assert notes == []

    def test_case_and_punctuation_insensitive(self):
        df = pd.DataFrame({
            "TIME_PERIOD": ["2026-06-01"],
            "Ad Spend": [900],
            "Total Revenue": [4300],
        })
        result, _ = normalize_columns(df)
        assert "date" in result.columns
        assert "spend" in result.columns
        assert "revenue" in result.columns

    def test_micros_column_scaled(self):
        """Google Ads 'Cost (micros)' should be divided by 1e6."""
        df = pd.DataFrame({
            "date": ["2026-06-01"],
            "Cost (micros)": [46_980_000],
            "revenue": [4300],
        })
        result, notes = normalize_columns(df)
        assert "spend" in result.columns
        assert abs(result["spend"].iloc[0] - 46.98) < 0.01
        assert len(notes) == 1
        assert "micro" in notes[0].lower()

    def test_metrics_cost_micros_suffix_match(self):
        """'metrics_cost_micros' should match via suffix after stripping micros."""
        df = pd.DataFrame({
            "date": ["2026-06-01"],
            "metrics_cost_micros": [10_000_000],
            "revenue": [500],
        })
        result, notes = normalize_columns(df)
        assert "spend" in result.columns
        assert abs(result["spend"].iloc[0] - 10.0) < 0.01
        assert len(notes) == 1

    def test_unmapped_columns_preserved(self):
        """Extra columns should survive untouched, not dropped."""
        df = pd.DataFrame({
            "date": ["2026-06-01"],
            "spend": [100],
            "revenue": [200],
            "campaign_id": ["abc123"],
        })
        result, _ = normalize_columns(df)
        assert "campaign_id" in result.columns

    def test_no_double_mapping(self):
        """If two raw columns would map to the same canonical, first wins."""
        df = pd.DataFrame({
            "cost": [100],
            "spend": [200],
            "date": ["2026-06-01"],
            "revenue": [300],
        })
        result, _ = normalize_columns(df)
        # One of them should be renamed, the other kept as-is
        assert "spend" in result.columns


# ===================================================================
# schema — validate_schema
# ===================================================================

class TestValidateSchema:

    def test_valid_schema_no_errors(self):
        df = pd.DataFrame({
            "date": ["2026-06-01"],
            "spend": [100],
            "revenue": [200],
        })
        assert validate_schema(df) == []

    def test_missing_required_columns(self):
        df = pd.DataFrame({"date": ["2026-06-01"], "foo": [100]})
        errors = validate_schema(df)
        assert any("spend" in e for e in errors)
        assert any("revenue" in e for e in errors)

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["date", "spend", "revenue"])
        errors = validate_schema(df)
        assert any("empty" in e.lower() for e in errors)

    def test_all_dates_na(self):
        df = pd.DataFrame({
            "date": [None, None],
            "spend": [100, 200],
            "revenue": [300, 400],
        })
        errors = validate_schema(df)
        assert any("date" in e.lower() for e in errors)


# ===================================================================
# schema — coerce_types
# ===================================================================

class TestCoerceTypes:

    def test_date_parsing(self):
        df = pd.DataFrame({
            "date": ["2026-06-01", "2026-06-02", "invalid_date"],
            "spend": [100, 200, 300],
            "revenue": [400, 500, 600],
        })
        result = coerce_types(df)
        # "invalid_date" row should be dropped
        assert len(result) == 2
        assert result["date"].iloc[0] == "2026-06-01"
        assert result["date"].iloc[1] == "2026-06-02"

    def test_currency_symbols_stripped(self):
        df = pd.DataFrame({
            "date": ["2026-06-01"],
            "spend": ["$1,234"],
            "revenue": ["€5,678"],
        })
        result = coerce_types(df)
        assert result["spend"].iloc[0] == 1234.0
        assert result["revenue"].iloc[0] == 5678.0

    def test_non_numeric_becomes_zero(self):
        df = pd.DataFrame({
            "date": ["2026-06-01"],
            "spend": ["not_a_number"],
            "revenue": [100],
        })
        result = coerce_types(df)
        assert result["spend"].iloc[0] == 0.0

    def test_sessions_optional(self):
        """coerce_types should not crash if sessions column is absent."""
        df = pd.DataFrame({
            "date": ["2026-06-01"],
            "spend": [100],
            "revenue": [200],
        })
        result = coerce_types(df)
        assert "sessions" not in result.columns  # absent, not invented


# ===================================================================
# loaders — load_csv
# ===================================================================

class TestLoadCSV:

    def test_loads_fixture(self):
        df, notes = load_csv(TINY_SAMPLE)
        assert len(df) == 14
        for col in REQUIRED_COLUMNS:
            assert col in df.columns
        assert notes == []

    def test_types_correct(self):
        df, _ = load_csv(TINY_SAMPLE)
        # pandas 3.x uses StringDtype; accept both it and object
        assert pd.api.types.is_string_dtype(df["date"])
        assert pd.api.types.is_numeric_dtype(df["spend"])
        assert pd.api.types.is_numeric_dtype(df["revenue"])

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_csv("nonexistent_path.csv")

    def test_invalid_schema_raises(self, tmp_path: Path):
        bad = tmp_path / "bad.csv"
        bad.write_text("foo,bar\n1,2\n")
        with pytest.raises(ValueError, match="Required column"):
            load_csv(str(bad))


# ===================================================================
# loaders — load_data_dir
# ===================================================================

class TestLoadDataDir:

    def test_loads_fixture_dir(self):
        df, notes = load_data_dir(FIXTURE_DIR)
        assert len(df) == 14
        for col in REQUIRED_COLUMNS:
            assert col in df.columns

    def test_multiple_csvs_concatenated(self, tmp_path: Path):
        for i in range(3):
            f = tmp_path / f"part_{i}.csv"
            f.write_text(
                "date,spend,revenue\n"
                f"2026-06-0{i+1},100,200\n"
            )
        df, _ = load_data_dir(str(tmp_path))
        assert len(df) == 3

    def test_no_csvs_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_data_dir(str(tmp_path))
