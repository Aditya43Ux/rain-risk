"""Live rain probabilities from the trained LightGBM model.

    python -m app.predict

Fetches ECMWF's latest deterministic forecast for the next 8 UTC days, builds
exactly the same features the model was trained on (using the training
script's own feature code, so live and training can't drift apart), and stores
one probability per cell and day in forecast_daily under model "lgbm_v1".

Run it after app.ingest (run_ingest.bat does both).
"""
import logging
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from ml.train_model import MODEL_PATH, add_features

from .config import settings
from .db import connect, grid_cells
from .openmeteo import complete_daily_sum, coords, get_json

log = logging.getLogger("predict")

# Same source as the training data, so the model sees the same kind of numbers.
API_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
SOURCE_MODEL = "ecmwf_ifs025"
OUT_MODEL = "lgbm_v1"
FORECAST_DAYS = 8  # today + 7
BATCH = 10

INSERT = """
INSERT INTO forecast_daily
    (cell_id, valid_date, model, fetched_at, p_rain, mean_mm, p90_mm, n_members)
VALUES
    (%(cell_id)s, %(valid_date)s, %(model)s, %(fetched_at)s, %(p_rain)s, %(mean_mm)s, NULL, NULL)
ON CONFLICT DO NOTHING
"""


def daily(hourly: dict) -> pd.DataFrame:
    """Hourly -> UTC-day totals of the current run and the run one day older."""
    df = pd.DataFrame(hourly)
    df["valid_date"] = pd.to_datetime(df["time"]).dt.normalize()
    out = pd.DataFrame(index=sorted(df["valid_date"].unique()))
    for col, name in (("precipitation", "precip_mm"), ("precipitation_previous_day1", "prev_run_mm")):
        if col in df:
            out[name] = complete_daily_sum(df, col)
        else:
            out[name] = np.nan
    return out.rename_axis("valid_date").reset_index()


def fetch(cells: list[dict]) -> pd.DataFrame:
    frames = []
    for i in range(0, len(cells), BATCH):
        batch = cells[i : i + BATCH]
        results = get_json(
            API_URL,
            {
                **coords(batch),
                "hourly": "precipitation,precipitation_previous_day1",
                "models": SOURCE_MODEL,
                "forecast_days": FORECAST_DAYS,
                "timezone": "GMT",
            },
            wait=10,
        )
        if len(results) != len(batch):
            raise RuntimeError(f"Asked for {len(batch)} locations, got {len(results)}")
        for cell, res in zip(batch, results):
            d = daily(res["hourly"])
            d["cell_id"], d["lat"], d["lon"] = cell["id"], cell["lat"], cell["lon"]
            frames.append(d)
        time.sleep(1)
    return pd.concat(frames, ignore_index=True)


def build_rows(fc: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame:
    """Keep today..today+7 and assign lead times the way training defined them."""
    fc = fc.dropna(subset=["precip_mm"])
    fc = fc[(fc["valid_date"] >= today) & (fc["valid_date"] <= today + pd.Timedelta(days=7))].copy()
    # training leads are 1-7 days; today is treated as lead 1 (it's even closer)
    fc["lead_days"] = ((fc["valid_date"] - today).dt.days).clip(lower=1, upper=7)
    return fc


def predict(fc: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    base = fc[["cell_id", "lat", "lon", "valid_date", "lead_days", "precip_mm"]].assign(observed_mm=np.nan)
    feats = add_features(base, settings.grid_step, bundle["threshold_mm"])
    # training took "previous run" from older rows in the hindcast table; live, the
    # API gives it directly, so replace what add_features found (nothing) with it
    feats = feats.drop(columns="prev_run_mm").merge(
        fc[["cell_id", "valid_date", "prev_run_mm"]], on=["cell_id", "valid_date"], how="left"
    )
    feats["p_rain"] = bundle["model"].predict_proba(feats[bundle["features"]])[:, 1]
    return feats


def main() -> None:
    if not MODEL_PATH.exists():
        raise SystemExit(f"No trained model at {MODEL_PATH}. Run: python -m ml.train_model --final")
    bundle = joblib.load(MODEL_PATH)
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0)
    today = pd.Timestamp(fetched_at.date())

    with connect() as conn:
        cells = grid_cells(conn)
        fc = build_rows(fetch(cells), today)
        out = predict(fc, bundle)

        rows = [
            {
                "cell_id": int(r.cell_id),
                "valid_date": r.valid_date.date(),
                "model": OUT_MODEL,
                "fetched_at": fetched_at,
                "p_rain": float(r.p_rain),
                "mean_mm": float(r.precip_mm),
            }
            for r in out.itertuples(index=False)
        ]
        with conn.cursor() as cur:
            cur.executemany(INSERT, rows)
        conn.commit()

    summary = out.groupby(out["valid_date"].dt.date)["p_rain"].agg(["mean", "max"])
    for d, r in summary.iterrows():
        log.info("%s  avg %3.0f%%  max %3.0f%%", d, r["mean"] * 100, r["max"] * 100)
    missing_prev = out["prev_run_mm"].isna().mean()
    if missing_prev > 0.2:
        log.warning("previous-run forecast missing for %.0f%% of rows (the model copes, but check the API)", missing_prev * 100)
    print(f"Stored {len(rows)} ML rain probabilities ({out['cell_id'].nunique()} cells x {out['valid_date'].nunique()} days).")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    main()
