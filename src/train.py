"""
Train the CausalCast model and write pickle/model.pkl.

This script exists for REPRODUCIBILITY — it shows a judge exactly how
model.pkl was produced.  It is NOT called by run.sh.

Usage
-----
    python src/train.py [DATA_DIR] [MODEL_OUTPUT_PATH]

Defaults:
    DATA_DIR        = ./data
    MODEL_OUTPUT_PATH = ./pickle/model.pkl
"""

import os
import pickle
import sys

# ---------------------------------------------------------------------------
# Resolve repo root so `import core…` works when run as
# `python src/train.py` from anywhere.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.ingestion import load_data_dir  # noqa: E402
from core.preprocessing.seasonality import weekday_factors  # noqa: E402
from core.budget_response.fit import fit_response_curve  # noqa: E402

# ---------------------------------------------------------------------------
# Fixed seed — everything stochastic is reproducible.
# ---------------------------------------------------------------------------
SEED = 42


def main() -> None:
    # --- resolve paths (relative only, from positional args) ---
    repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    data_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(repo_root, "data")
    model_path = (
        sys.argv[2]
        if len(sys.argv) > 2
        else os.path.join(repo_root, "pickle", "model.pkl")
    )

    # ------------------------------------------------------------------
    # 1. Load training data
    # ------------------------------------------------------------------
    df, notes = load_data_dir(data_dir)
    for n in notes:
        print(f"  [NOTE] {n}")
    print(f"Loaded {len(df)} rows from {data_dir}")

    # ------------------------------------------------------------------
    # 2. Fit budget-response curve (deterministic OLS — no randomness)
    # ------------------------------------------------------------------
    curve = fit_response_curve(df)
    if curve is None:
        print("WARNING: could not fit response curve — insufficient data.")
        curve_dict = None
    else:
        curve_dict = curve.to_dict()
        print(
            f"Fitted response curve: a={curve.a:.4f}, b={curve.b:.4f}, "
            f"R²={curve.r_squared:.4f}  (n={curve.n_points})"
        )

    # ------------------------------------------------------------------
    # 3. Extract weekday seasonality factors
    # ------------------------------------------------------------------
    wf = weekday_factors(df, column="revenue")
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    print("Weekday factors:")
    for name, factor in zip(day_names, wf):
        print(f"  {name}: {factor:.4f}")

    # ------------------------------------------------------------------
    # 4. Bundle into a model dict and pickle
    # ------------------------------------------------------------------
    model = {
        "version": "0.1.0",
        "response_curve": curve_dict,
        "weekday_factors": wf,
        "config": {
            "seed": SEED,
            "horizon": 30,
            "iterations": 1000,
        },
        "training_meta": {
            "n_rows": len(df),
            "date_range": [str(df["date"].min()), str(df["date"].max())],
        },
    }

    model_dir = os.path.dirname(model_path)
    if model_dir:
        os.makedirs(model_dir, exist_ok=True)
    with open(model_path, "wb") as f:
        pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"\nModel saved → {model_path}")


if __name__ == "__main__":
    main()
