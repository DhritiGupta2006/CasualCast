"""
Load model + features, run the CausalCast forecast, write predictions.csv.

**Zero internet access** — every dependency is local:
  - Features come from generate_features.py (a local CSV).
  - Model comes from pickle/model.pkl (committed to the repo).
  - All math is in core/ (pandas + numpy only, no remote calls).

Usage
-----
    python src/predict.py FEATURES_PATH MODEL_PATH OUTPUT_PATH

Called by run.sh — all three paths are derived from run.sh's positional
arguments.
"""

import os
import pickle
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pandas as pd  # noqa: E402

from core.forecasting.engine import forecast  # noqa: E402
from core.budget_response.fit import ResponseCurve  # noqa: E402
from core.budget_response.predict import predict_revenue  # noqa: E402
from core.incrementality.signal import (  # noqa: E402
    estimate_incrementality,
    INCREMENTALITY_DISCLAIMER,
)


def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: python src/predict.py FEATURES_PATH MODEL_PATH OUTPUT_PATH")
        sys.exit(1)

    features_path = sys.argv[1]
    model_path = sys.argv[2]
    output_path = sys.argv[3]

    # ------------------------------------------------------------------
    # 1. Load features
    # ------------------------------------------------------------------
    df = pd.read_csv(features_path)
    print(f"Loaded {len(df)} feature rows from {features_path}")

    # ------------------------------------------------------------------
    # 2. Load pre-trained model
    # ------------------------------------------------------------------
    with open(model_path, "rb") as f:
        model = pickle.load(f)

    config = model["config"]
    print(f"Model v{model['version']}  seed={config['seed']}")

    # ------------------------------------------------------------------
    # 3. Run Monte Carlo forecast via core/
    # ------------------------------------------------------------------
    fc = forecast(
        df,
        column="revenue",
        horizon=config["horizon"],
        iterations=config["iterations"],
        seed=config["seed"],
    )

    # ------------------------------------------------------------------
    # 4. Assemble output rows
    # ------------------------------------------------------------------
    rows = []
    for r in fc.results:
        row: dict = {
            "date": r.date,
            "revenue_p10": r.p10,
            "revenue_p50": r.p50,
            "revenue_p90": r.p90,
            "trend_direction": fc.stats.trend_direction,
            "trend_slope": fc.stats.slope,
        }
        rows.append(row)

    output = pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # 5. Budget-response predictions (from pre-trained curve)
    # ------------------------------------------------------------------
    curve_dict = model.get("response_curve")
    if curve_dict is not None:
        curve = ResponseCurve(**curve_dict)
        avg_spend = float(df["spend"].mean()) if "spend" in df.columns else 0.0
        if avg_spend > 0:
            predicted_rev = predict_revenue(curve, avg_spend)
            output["baseline_spend"] = round(avg_spend, 2)
            output["predicted_roas"] = round(predicted_rev / avg_spend, 4)
    else:
        print("  [WARN] No response curve in model — skipping budget columns")

    # ------------------------------------------------------------------
    # 6. Incrementality signal
    # ------------------------------------------------------------------
    inc = estimate_incrementality(df)
    if inc is not None:
        output["incrementality_fraction"] = inc.incrementality_fraction
        output["incrementality_confidence"] = inc.confidence
        output["incrementality_baseline_extrapolated"] = inc.baseline_extrapolated
        output["incrementality_disclaimer"] = inc.disclaimer
    else:
        print("  [WARN] Could not estimate incrementality — skipping columns")

    # ------------------------------------------------------------------
    # 7. Write predictions (fresh, never append)
    # ------------------------------------------------------------------
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    output.to_csv(output_path, index=False)

    print(f"\nPredictions: {len(output)} rows → {output_path}")
    print(f"  Trend: {fc.stats.trend_direction} (slope={fc.stats.slope})")
    print(f"  Revenue P50 avg: ${fc.stats.avg_p50:,}")
    if inc is not None:
        print(
            f"  Incrementality: {inc.incrementality_fraction:.1%} "
            f"({inc.confidence} confidence)"
        )
        if inc.baseline_extrapolated:
            print(
                "  [NOTE] Zero-spend baseline is extrapolated far outside "
                "the observed spend range — confidence downgraded to 'low'."
            )
        print(f"  ⚠  {INCREMENTALITY_DISCLAIMER}")


if __name__ == "__main__":
    main()
