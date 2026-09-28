"""Load observed daily rainfall from NASA GPM IMERG into observation_daily.

    python -m app.observe_imerg                              # last 10 available days
    python -m app.observe_imerg --start 2026-06-01 --end 2026-09-25

Uses IMERG Late Run daily (GPM_3IMERGDL, V07): 0.1 degree satellite rainfall,
published about 14 hours after each day ends. A "day" in IMERG is a UTC day
(05:30 to 05:30 IST), so forecasts must also be stored as UTC days to match
(TIMEZONE=GMT in .env).

Each 0.1 degree IMERG pixel is assigned to the grid cell whose centre is
nearest, and the pixels in a cell are averaged.

Needs a free NASA Earthdata account. The first run asks for your username and
password and saves them to your home folder, so later runs (and the scheduled
task) log in automatically.
"""
import argparse
import logging
import shutil
from datetime import date, timedelta
from pathlib import Path

import earthaccess
import numpy as np
import pandas as pd
import xarray as xr

from .config import settings
from .db import connect

log = logging.getLogger("observe_imerg")

SHORT_NAME = "GPM_3IMERGDL"  # IMERG Late Run, daily, 0.1 degree
SOURCE = "imerg_late_v07"
DOWNLOAD_DIR = Path("imerg_data")

UPSERT = """
INSERT INTO observation_daily (cell_id, obs_date, rain_mm, source)
VALUES (%(cell_id)s, %(obs_date)s, %(rain_mm)s, %(source)s)
ON CONFLICT (cell_id, obs_date, source) DO UPDATE SET rain_mm = EXCLUDED.rain_mm
"""


def cell_key(lat: float, lon: float) -> tuple[float, float]:
    return (round(float(lat), 4), round(float(lon), 4))


def aggregate(ds: xr.Dataset, bbox: tuple[float, float, float, float], step: float) -> pd.DataFrame:
    """IMERG pixels inside bbox (plus half a cell) -> mean rain per grid cell centre.

    Returns columns: obs_date, lat, lon, rain_mm, n_pixels.
    """
    west, south, east, north = bbox
    half = step / 2
    sub = ds["precipitation"].sel(
        lat=slice(south - half, north + half),
        lon=slice(west - half, east + half),
    )
    df = sub.to_dataframe(name="rain_mm").reset_index()
    df = df.dropna(subset=["rain_mm"])
    df = df[df["rain_mm"] >= 0]  # drop any leftover fill values

    df["obs_date"] = pd.to_datetime(df["time"]).dt.date
    # snap each pixel to the nearest cell centre (cells are centred on multiples of step)
    df["cell_lat"] = (np.round(df["lat"] / step) * step).round(4)
    df["cell_lon"] = (np.round(df["lon"] / step) * step).round(4)

    out = (
        df.groupby(["obs_date", "cell_lat", "cell_lon"])["rain_mm"]
        .agg(rain_mm="mean", n_pixels="count")
        .reset_index()
        .rename(columns={"cell_lat": "lat", "cell_lon": "lon"})
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=date.fromisoformat, help="first day (default: 11 days ago)")
    ap.add_argument("--end", type=date.fromisoformat, help="last day (default: 2 days ago)")
    ap.add_argument("--keep-files", action="store_true", help="don't delete the downloaded files")
    args = ap.parse_args()

    today = date.today()
    end = args.end or today - timedelta(days=2)  # Late Run needs ~14 h after the day ends
    start = args.start or end - timedelta(days=2)
    if start > end:
        raise SystemExit("--start must be on or before --end")

    bbox = tuple(float(x) for x in settings.bbox.split(","))
    step = settings.grid_step

    earthaccess.login(persist=True)

    granules = earthaccess.search_data(
        short_name=SHORT_NAME,
        temporal=(start.isoformat(), end.isoformat()),
        bounding_box=bbox,
    )
    if not granules:
        raise SystemExit(f"No IMERG files found for {start} to {end}. Try an earlier --end date.")
    log.info("found %d daily files for %s to %s", len(granules), start, end)

    DOWNLOAD_DIR.mkdir(exist_ok=True)
    files = earthaccess.download(granules, local_path=str(DOWNLOAD_DIR))

    with connect() as conn:
        cells = {
            cell_key(r["lat"], r["lon"]): r["id"]
            for r in conn.execute("SELECT id, lat, lon FROM grid_cell").fetchall()
        }
        if not cells:
            raise SystemExit("No grid cells yet. Run: python -m app.seed_grid")

        total, unmatched = 0, 0
        for f in sorted(str(x) for x in files):
            with xr.open_dataset(f) as ds:
                agg = aggregate(ds, bbox, step)

            rows = []
            for r in agg.itertuples(index=False):
                cell_id = cells.get(cell_key(r.lat, r.lon))
                if cell_id is None:
                    unmatched += 1
                    continue
                rows.append(
                    {
                        "cell_id": cell_id,
                        "obs_date": r.obs_date,
                        "rain_mm": float(r.rain_mm),
                        "source": SOURCE,
                    }
                )
            with conn.cursor() as cur:
                cur.executemany(UPSERT, rows)
            conn.commit()
            total += len(rows)
            day = agg["obs_date"].iloc[0] if len(agg) else "?"
            log.info("%s: %d cells, max %.1f mm", day, len(rows), agg["rain_mm"].max() if len(agg) else 0)

    if unmatched:
        log.warning(
            "%d cell-days didn't match a grid cell. Is the grid centred on multiples of %s? "
            "(see step 7b: realign seed_grid.py and reseed)",
            unmatched,
            step,
        )
    if not args.keep_files:
        shutil.rmtree(DOWNLOAD_DIR, ignore_errors=True)

    print(f"Stored {total} observed cell-days from {len(files)} IMERG files.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
