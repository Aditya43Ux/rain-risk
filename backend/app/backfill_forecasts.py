"""Load past ECMWF forecasts into forecast_hindcast, for training and verification.

    python -m app.backfill_forecasts --start 2026-06-01 --end 2026-09-23

Uses Open-Meteo's Previous Runs API: for every hour, what the model predicted
1, 2, ... 7 days earlier. These are the single "deterministic" ECMWF run, not
the 51-member ensemble, and are archived from early 2024.

Hourly values are summed into UTC days, matching IMERG's days. A day is only
kept if all 24 hours are present.
"""
import argparse
import logging
import time
from datetime import date, timedelta

import httpx
import pandas as pd

from .db import connect

log = logging.getLogger("backfill")

API_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
MODEL = "ecmwf_ifs025"
LEADS = range(1, 8)
CHUNK_DAYS = 92  # one request covers ~3 months for one cell

UPSERT = """
INSERT INTO forecast_hindcast (cell_id, valid_date, lead_days, model, precip_mm)
VALUES (%(cell_id)s, %(valid_date)s, %(lead_days)s, %(model)s, %(precip_mm)s)
ON CONFLICT (cell_id, valid_date, lead_days, model) DO UPDATE SET precip_mm = EXCLUDED.precip_mm
"""


def get_json(params: dict) -> dict:
    for attempt in range(5):
        r = httpx.get(API_URL, params=params, timeout=90)
        if r.status_code == 429:  # rate limited
            wait = 30 * 2**attempt
            log.warning("rate limited, waiting %ds", wait)
            time.sleep(wait)
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"API error {r.status_code}: {r.text[:300]}")
        return r.json()
    raise RuntimeError("Still rate limited. Try again later (the free limit resets daily).")


def daily_totals(hourly: dict) -> pd.DataFrame:
    """Hourly precipitation_previous_dayN -> rows of (valid_date, lead_days, precip_mm)."""
    df = pd.DataFrame(hourly)
    df["valid_date"] = pd.to_datetime(df["time"]).dt.date
    rows = []
    for lead in LEADS:
        col = f"precipitation_previous_day{lead}"
        if col not in df:
            continue
        g = df.groupby("valid_date")[col]
        daily = g.sum(min_count=1)[g.count() == 24]  # complete days only
        rows.append(pd.DataFrame({"valid_date": daily.index, "lead_days": lead, "precip_mm": daily.values}))
    if not rows:
        return pd.DataFrame(columns=["valid_date", "lead_days", "precip_mm"])
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=date.fromisoformat, required=True)
    ap.add_argument("--end", type=date.fromisoformat, required=True)
    args = ap.parse_args()
    if args.start > args.end:
        raise SystemExit("--start must be on or before --end")

    hourly_vars = ",".join(f"precipitation_previous_day{n}" for n in LEADS)

    with connect() as conn:
        cells = conn.execute("SELECT id, lat, lon FROM grid_cell ORDER BY id").fetchall()
        if not cells:
            raise SystemExit("No grid cells yet. Run: python -m app.seed_grid")

        total = 0
        chunk_start = args.start
        while chunk_start <= args.end:
            chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS - 1), args.end)
            for cell in cells:
                data = get_json(
                    {
                        "latitude": cell["lat"],
                        "longitude": cell["lon"],
                        "hourly": hourly_vars,
                        "models": MODEL,
                        "start_date": chunk_start.isoformat(),
                        "end_date": chunk_end.isoformat(),
                        "timezone": "GMT",
                    }
                )
                df = daily_totals(data["hourly"])
                rows = [
                    {
                        "cell_id": cell["id"],
                        "valid_date": r.valid_date,
                        "lead_days": int(r.lead_days),
                        "model": MODEL,
                        "precip_mm": float(r.precip_mm),
                    }
                    for r in df.itertuples(index=False)
                ]
                with conn.cursor() as cur:
                    cur.executemany(UPSERT, rows)
                conn.commit()
                total += len(rows)
                time.sleep(0.5)  # stay well under the free per-minute limit
            log.info("%s to %s done (%d rows so far)", chunk_start, chunk_end, total)
            chunk_start = chunk_end + timedelta(days=1)

    print(f"Stored {total} past forecasts (cell x day x lead time).")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    main()
