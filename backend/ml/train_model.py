"""Step 9: learn "will it really rain here?" from past ECMWF forecasts + IMERG.

    python -m ml.train_model                    # train on 2024-2025, test on 2026
    python -m ml.train_model --features full    # same, also using season + location
    python -m ml.train_model --final            # train on all years and save

Run from the backend folder with the venv active. Needs:
    python -m pip install lightgbm scikit-learn joblib

Target:  1 if IMERG observed >= RAIN_THRESHOLD_MM in that cell on that UTC day.
Inputs:  what the forecast said (this cell and its neighbours), how far ahead
         it was issued, what the previous run said, season and location.
Output:  a probability of rain, compared on the held-out year with
         (a) always predicting the climatological rain rate,
         (b) the raw forecast used as yes/no, and
         (c) the raw forecast amount turned into a probability by a simple
             isotonic calibration. This is the baseline to beat: if the ML
             model can't beat (c), the extra complexity isn't paying off.
A leave-one-year-out table at the end checks the result isn't a fluke of 2026.
"""
import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

import lightgbm as lgb

from app.config import settings
from app.db import connect

MODEL_PATH = Path("models/rain_lgbm.joblib")
FORECAST_FEATURES = [
    "precip_mm",        # forecast rain in this cell
    "nbr_mean_mm",      # mean forecast in the 3x3 block around it
    "nbr_max_mm",       # wettest neighbour: rain nearby often spills over
    "nbr_wet_frac",     # share of the 3x3 block forecast to get >= threshold
    "prev_run_mm",      # what the run one day older said (consistency)
    "lead_days",
]
# Season and location. With only a few years of data these mostly memorise
# "how wet was August in the training years", which doesn't carry over to a
# different year, so they're off by default.
EXTRA_FEATURES = ["doy", "lat", "lon"]
FEATURE_SETS = {"forecast": FORECAST_FEATURES, "full": FORECAST_FEATURES + EXTRA_FEATURES}
MONOTONE_UP = {"precip_mm", "nbr_mean_mm", "nbr_max_mm", "nbr_wet_frac"}

QUERY = """
SELECT h.cell_id, c.lat, c.lon, h.valid_date, h.lead_days, h.precip_mm,
       o.rain_mm AS observed_mm
FROM forecast_hindcast h
JOIN grid_cell c ON c.id = h.cell_id
JOIN observation_daily o ON o.cell_id = h.cell_id AND o.obs_date = h.valid_date
"""


def load() -> pd.DataFrame:
    with connect() as conn:
        df = pd.DataFrame(conn.execute(QUERY).fetchall())
    if df.empty:
        raise SystemExit("No forecast/observation pairs. Load IMERG and backfill forecasts first.")
    df["valid_date"] = pd.to_datetime(df["valid_date"])
    return df


def add_features(df: pd.DataFrame, step: float, threshold: float) -> pd.DataFrame:
    df = df.copy()
    df["lat"] = df["lat"].round(4)
    df["lon"] = df["lon"].round(4)
    keys = ["valid_date", "lead_days"]

    # 3x3 neighbourhood of the forecast, same day and lead time
    base = df[keys + ["lat", "lon", "precip_mm"]]
    shifted = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            s = base.copy()
            s["lat"] = (s["lat"] + dy * step).round(4)
            s["lon"] = (s["lon"] + dx * step).round(4)
            shifted.append(s)
    nbrs = pd.concat(shifted, ignore_index=True)
    nbrs["wet"] = (nbrs["precip_mm"] >= threshold).astype(float)
    agg = (
        nbrs.groupby(keys + ["lat", "lon"])
        .agg(nbr_mean_mm=("precip_mm", "mean"), nbr_max_mm=("precip_mm", "max"), nbr_wet_frac=("wet", "mean"))
        .reset_index()
    )
    df = df.merge(agg, on=keys + ["lat", "lon"], how="left")

    # the older run's forecast for the same cell and day (lead + 1)
    prev = df[["cell_id", "valid_date", "lead_days", "precip_mm"]].copy()
    prev["lead_days"] = prev["lead_days"] - 1
    prev = prev.rename(columns={"precip_mm": "prev_run_mm"})
    df = df.merge(prev, on=["cell_id", "valid_date", "lead_days"], how="left")

    df["doy"] = df["valid_date"].dt.dayofyear
    df["rained"] = (df["observed_mm"] >= threshold).astype(int)
    return df


def fit(train: pd.DataFrame, features: list[str]) -> lgb.LGBMClassifier:
    model = lgb.LGBMClassifier(
        n_estimators=400,
        learning_rate=0.03,
        num_leaves=15,
        min_child_samples=100,  # small, correlated dataset: keep trees coarse
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        # more forecast rain should never lower the rain probability
        monotone_constraints=[1 if f in MONOTONE_UP else 0 for f in features],
        verbose=-1,
    )
    model.fit(train[features], train["rained"])
    return model


def fit_calibrated_raw(train: pd.DataFrame) -> IsotonicRegression:
    """Baseline: map the raw forecast amount to a rain probability, nothing else."""
    iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    iso.fit(train["precip_mm"], train["rained"])
    return iso


def report(test: pd.DataFrame, prob: np.ndarray, cal: np.ndarray, climo: float, threshold: float) -> None:
    y = test["rained"].to_numpy()
    raw = (test["precip_mm"] >= threshold).astype(float).to_numpy()

    b_climo = brier_score_loss(y, np.full(len(y), climo))
    b_raw = brier_score_loss(y, raw)
    b_cal = brier_score_loss(y, cal)
    b_ml = brier_score_loss(y, prob)
    print(f"\nTest rows: {len(y)}   rained: {y.mean():.0%}")
    print("\nBrier score (lower is better):")
    print(f"  always climatology ({climo:.0%}):   {b_climo:.4f}")
    print(f"  raw ECMWF yes/no:                {b_raw:.4f}")
    print(f"  raw ECMWF, calibrated:           {b_cal:.4f}   <- baseline to beat")
    print(f"  ML model:                        {b_ml:.4f}   ({1 - b_ml / b_cal:+.1%} vs calibrated raw)")
    print(f"  AUC (ranking wet vs dry days): raw {roc_auc_score(y, test['precip_mm']):.3f}, ML {roc_auc_score(y, prob):.3f}")

    print("\nBy lead time:     calib. Brier   ML Brier   ML correct   ML false alarms")
    t = test.assign(prob=prob, cal=cal)
    for lead, g in t.groupby("lead_days"):
        yes = g["prob"] >= 0.5
        fa = ((yes) & (g["rained"] == 0)).sum() / max(yes.sum(), 1)
        print(
            f"  {lead} day(s) ahead   {brier_score_loss(g['rained'], g['cal']):.4f}       "
            f"{brier_score_loss(g['rained'], g['prob']):.4f}     {(yes == g['rained']).mean():6.0%}      {fa:6.0%}"
        )

    frac, mean_p = calibration_curve(y, prob, n_bins=8, strategy="quantile")
    print("\nReliability (when the model says X%, it rained Y% of the time):")
    for p, o in zip(mean_p, frac):
        print(f"  says {p:4.0%}  ->  rained {o:4.0%}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-year", type=int, default=2026)
    ap.add_argument("--features", choices=FEATURE_SETS, default="forecast")
    ap.add_argument("--final", action="store_true", help="train on all years and save the model")
    args = ap.parse_args()
    features = FEATURE_SETS[args.features]

    threshold = settings.rain_threshold_mm
    df = add_features(load(), settings.grid_step, threshold)
    years = sorted(int(y) for y in df["valid_date"].dt.year.unique())
    print(f"Pairs: {len(df)}   years: {years}   rained overall: {df['rained'].mean():.0%}")

    if args.final:
        model = fit(df, features)
        MODEL_PATH.parent.mkdir(exist_ok=True)
        joblib.dump({"model": model, "features": features, "threshold_mm": threshold}, MODEL_PATH)
        print(f"Trained on all {len(df)} rows. Saved {MODEL_PATH}")
        return

    train = df[df["valid_date"].dt.year != args.test_year]
    test = df[df["valid_date"].dt.year == args.test_year]
    if train.empty or test.empty:
        raise SystemExit(f"Need data both in {args.test_year} and in other years. Have: {years}")
    train_years = sorted(int(y) for y in train["valid_date"].dt.year.unique())
    print(f"Features: {args.features} ({', '.join(features)})")
    print(f"Train: {len(train)} rows {train_years}   test: {len(test)} rows ({args.test_year})")

    model = fit(train, features)
    prob = model.predict_proba(test[features])[:, 1]
    cal = fit_calibrated_raw(train).predict(test["precip_mm"])
    report(test, prob, cal, climo=train["rained"].mean(), threshold=threshold)

    imp = pd.Series(model.booster_.feature_importance("gain"), index=features)
    print("\nWhat the model relies on (share of gain):")
    for name, share in (imp / imp.sum()).sort_values(ascending=False).items():
        print(f"  {name:13s} {share:5.0%}")

    print("\nLeave-one-year-out (train on the other years, test on this one):")
    print("  test year   rained   calib. raw   ML      ML vs calib.")
    for year in years:
        tr = df[df["valid_date"].dt.year != year]
        te = df[df["valid_date"].dt.year == year]
        if tr.empty:
            continue
        b_cal = brier_score_loss(te["rained"], fit_calibrated_raw(tr).predict(te["precip_mm"]))
        b_ml = brier_score_loss(te["rained"], fit(tr, features).predict_proba(te[features])[:, 1])
        print(f"  {year}        {te['rained'].mean():4.0%}     {b_cal:.4f}       {b_ml:.4f}  {1 - b_ml / b_cal:+6.1%}")


if __name__ == "__main__":
    main()
