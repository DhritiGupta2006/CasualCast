"""
Generate features from raw data in DATA_DIR.

Reads every CSV in DATA_DIR (by glob pattern — never hardcodes a
filename list or row count), normalises columns, adds channel groups,
aggregates to daily totals, flags anomalies, and writes a clean
features file.

Usage
-----
    python src/generate_features.py DATA_DIR FEATURES_OUTPUT_PATH

Called by run.sh — DATA_DIR and FEATURES_OUTPUT_PATH are derived from
run.sh's three positional arguments.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pandas as pd  # noqa: E402

from core.ingestion import load_data_dir  # noqa: E402
from core.preprocessing.taxonomy import add_channel_group  # noqa: E402
from core.preprocessing.anomalies import flag_anomalies  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python src/generate_features.py DATA_DIR FEATURES_OUTPUT_PATH")
        sys.exit(1)

    data_dir = sys.argv[1]
    features_path = sys.argv[2]

    # ------------------------------------------------------------------
    # 1. Ingest — reads every *.csv in DATA_DIR via core/ingestion
    # ------------------------------------------------------------------
    df, notes = load_data_dir(data_dir)
    for n in notes:
        print(f"  [NOTE] {n}")
    print(f"Ingested {len(df)} rows from {data_dir}")

    # ------------------------------------------------------------------
    # 2. Channel taxonomy
    # ------------------------------------------------------------------
    df = add_channel_group(df)

    # ------------------------------------------------------------------
    # 3. Aggregate to daily totals
    #    Some exports have one row per campaign per day — collapse them
    #    so the forecasting engine sees a clean daily series.
    # ------------------------------------------------------------------
    agg_map: dict[str, str] = {"spend": "sum", "revenue": "sum"}
    if "sessions" in df.columns:
        agg_map["sessions"] = "sum"

    daily = df.groupby("date", as_index=False).agg(agg_map)
    daily = daily.sort_values("date").reset_index(drop=True)

    was_aggregated = len(daily) < len(df)
    if was_aggregated:
        print(
            f"  Aggregated {len(df)} rows → {len(daily)} daily rows "
            f"(duplicate dates collapsed)"
        )

    # ------------------------------------------------------------------
    # 4. Anomaly detection
    # ------------------------------------------------------------------
    daily = flag_anomalies(daily, column="revenue")
    n_anomalies = int(daily["is_anomaly"].sum())
    if n_anomalies:
        print(f"  {n_anomalies} anomalous day(s) flagged")

    # ------------------------------------------------------------------
    # 5. Write features
    # ------------------------------------------------------------------
    features_dir = os.path.dirname(features_path)
    if features_dir:
        os.makedirs(features_dir, exist_ok=True)
    daily.to_csv(features_path, index=False)

    print(f"Features: {len(daily)} rows → {features_path}")


if __name__ == "__main__":
    main()
