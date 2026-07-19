#!/usr/bin/env bash
#
# run.sh — CausalCast scored batch pipeline entrypoint.
#
# Usage:
#   ./run.sh [DATA_DIR] [MODEL_PATH] [OUTPUT_PATH]
#
# All three arguments are positional and optional; defaults match the
# submission guide's recommended layout:
#   DATA_DIR    = ./data
#   MODEL_PATH  = ./pickle/model.pkl
#   OUTPUT_PATH = ./output/predictions.csv
#
# This script NEVER retrains (src/train.py is not called here) and makes
# NO network calls — it only runs src/generate_features.py followed by
# src/predict.py, both of which read local files and call core/.
#
# No setup beyond `pip install -r requirements.txt` is required.

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve repo root so this script works regardless of the caller's cwd.
# ---------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DATA_DIR="${1:-"${REPO_ROOT}/data"}"
MODEL_PATH="${2:-"${REPO_ROOT}/pickle/model.pkl"}"
OUTPUT_PATH="${3:-"${REPO_ROOT}/output/predictions.csv"}"

# Features file lives alongside the other pipeline-generated artifacts.
FEATURES_PATH="${REPO_ROOT}/output/features.csv"

echo "CausalCast pipeline"
echo "  DATA_DIR    = ${DATA_DIR}"
echo "  MODEL_PATH  = ${MODEL_PATH}"
echo "  OUTPUT_PATH = ${OUTPUT_PATH}"
echo

PYTHON_BIN="${PYTHON_BIN:-python3}"

# 1. Feature generation (core/ingestion + core/preprocessing)
"${PYTHON_BIN}" "${REPO_ROOT}/src/generate_features.py" "${DATA_DIR}" "${FEATURES_PATH}"

# 2. Prediction (core/forecasting + core/budget_response + core/incrementality)
"${PYTHON_BIN}" "${REPO_ROOT}/src/predict.py" "${FEATURES_PATH}" "${MODEL_PATH}" "${OUTPUT_PATH}"

echo
echo "Done → ${OUTPUT_PATH}"
