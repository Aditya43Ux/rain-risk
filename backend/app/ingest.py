"""Fetch ensemble forecasts and store rain probabilities per grid cell.

    python -m app.ingest

Run it every 6 hours (cron / systemd timer / GitHub Action). Each run is kept,
so you build up a forecast archive for calibration later.
"""
import logging
import time
from datetime import datetime, timezone

import httpx
import pandas as pd

from .config import settings
from .db import connect

log = logging.getLogger("ingest")
API_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
BATCH = 20  # locations per request

INSERT = """
INSERT INTO forecast_daily
    (cell_id, valid_date, model, fetched_at, p_rain, mean_mm, p90_mm, n_members)
VALUES
    (%(cell_id)s, %(valid_date)s, %(model)s, %(fetched_at)s,
     %(p_rain)s, %(mean_mm)s, %(p90_mm)s, %(n_members)s)
ON CONFLICT DO NOTHING
"""


def get_json(params: dict) -> dict | list:
    for attempt in range(4):
        r = httpx.get(API_URL, params=params, timeout=60)
        if r.status_code == 429:  # rate limited, back off
            time.sleep(5 * 2**attempt)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("Open-Meteo rate limit hit. Try again later or use fewer cells.")


def fetch_batch(cells: list[dict]) -> list[dict]:
    params = {
        "latitude": ",".join(f"{c['lat']:.4f}" for c in cells),
        "longitude": ",".join(f"{c['lon']:.4f}" for c in cells),
        "hourly": "precipitation",
        "models": settings.ensemble_model,
        "forecast_days": 7,
        "timezone": settings.timezone,
    }
    data = get_json(params)
    return data if isinstance(data, list) else [data]


def summarize(hourly: dict) -> pd.DataFrame:
    """Hourly precipitation per member -> one row per day.

    p_rain is the share of ensemble members whose daily total reaches the
    threshold. That is the raw, uncalibrated probability.
    """
    df = pd.DataFrame(hourly)
    df["date"] = pd.to_datetime(df["time"]).dt.date
    members = [c for c in df.columns if c.startswith("precipitation")]

    totals = df.groupby("date")[members].sum(min_count=1)  # mm per member per day
    valid = totals.notna()
    wet = (totals >= settings.rain_threshold_mm) & valid

    out = pd.DataFrame(
        {
            "p_rain": wet.sum(axis=1) / valid.sum(axis=1).replace(0, float("nan")),
            "mean_mm": totals.mean(axis=1),
            "p90_mm": totals.quantile(0.9, axis=1),
            "n_members": valid.sum(axis=1),
        }
    )
    return out.dropna(subset=["p_rain"])


def _num(x):
    return None if pd.isna(x) else float(x)


def run() -> None:
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0)

    with connect() as conn:
        cells = conn.execute("SELECT id, lat, lon FROM grid_cell ORDER BY id").fetchall()
        if not cells:
            raise SystemExit("No grid cells yet. Run: python -m app.seed_grid")

        total = 0
        for i in range(0, len(cells), BATCH):
            batch = cells[i : i + BATCH]
            results = fetch_batch(batch)
            if len(results) != len(batch):
                raise RuntimeError(f"Asked for {len(batch)} locations, got {len(results)}")

            rows = []
            for cell, res in zip(batch, results):
                summary = summarize(res["hourly"])
                for day, r in summary.iterrows():
                    rows.append(
                        {
                            "cell_id": cell["id"],
                            "valid_date": day,
                            "model": settings.ensemble_model,
                            "fetched_at": fetched_at,
                            "p_rain": float(r["p_rain"]),
                            "mean_mm": _num(r["mean_mm"]),
                            "p90_mm": _num(r["p90_mm"]),
                            "n_members": int(r["n_members"]),
                        }
                    )

            with conn.cursor() as cur:
                cur.executemany(INSERT, rows)
            conn.commit()
            total += len(rows)
            log.info("cells %d-%d done", i + 1, i + len(batch))
            time.sleep(1)  # be polite to the free API

    print(f"Stored {total} cell-day forecasts for {len(cells)} cells.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run()
