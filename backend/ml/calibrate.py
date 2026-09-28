r"""Phase 2: make "70%" actually mean 70%.

Raw ensemble probabilities are usually overconfident. This fits an isotonic
calibrator on (forecast probability, did it really rain?) pairs and reports
Brier score before and after on a held-out, later period.

Export training pairs once you have observations in observation_daily, e.g. for
forecasts issued 3 days ahead (run in psql):

    \copy (
      SELECT f.valid_date, f.p_rain, (o.rain_mm >= 1.0)::int AS observed
      FROM forecast_daily f
      JOIN observation_daily o
        ON o.cell_id = f.cell_id AND o.obs_date = f.valid_date
      WHERE f.valid_date - f.fetched_at::date = 3
    ) TO 'pairs.csv' CSV HEADER

Then:  python ml/calibrate.py pairs.csv
"""
import argparse

import joblib
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out", default="calibrator.joblib")
    args = ap.parse_args()

    df = pd.read_csv(args.csv, parse_dates=["valid_date"]).dropna(subset=["p_rain", "observed"])
    df = df.sort_values("valid_date")  # split by time, never randomly

    cut = int(len(df) * 0.8)
    train, test = df.iloc[:cut], df.iloc[cut:]

    iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    iso.fit(train["p_rain"], train["observed"])
    calibrated = iso.predict(test["p_rain"])

    print(f"train rows: {len(train)}   test rows: {len(test)}")
    print(f"Brier score raw:        {brier_score_loss(test['observed'], test['p_rain']):.4f}")
    print(f"Brier score calibrated: {brier_score_loss(test['observed'], calibrated):.4f}  (lower is better)")

    frac_wet, mean_pred = calibration_curve(test["observed"], calibrated, n_bins=10, strategy="quantile")
    print("\nReliability (predicted vs. actually rained):")
    for p, o in zip(mean_pred, frac_wet):
        print(f"  {p:5.0%}  ->  {o:5.0%}")

    iso.fit(df["p_rain"], df["observed"])  # final model uses all data
    joblib.dump(iso, args.out)
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
