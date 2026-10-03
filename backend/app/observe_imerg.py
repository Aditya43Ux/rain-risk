"""Load observed daily rainfall from NASA GPM IMERG into observation_daily.

    python -m app.observe_imerg                              # fill any missing recent days
    python -m app.observe_imerg --start 2026-06-01 --end 2026-09-25

Uses IMERG Late Run daily (GPM_3IMERGDL, V07): 0.1 degree satellite rainfall,
published about 14 hours after each day ends. A "day" in IMERG is a UTC day
(05:30 to 05:30 IST), so forecasts must also be stored as UTC days to match
(TIMEZONE=GMT in .env).

Each 0.1 degree IMERG pixel is assigned to the grid cell whose centre is
nearest, and the pixels in a cell are averaged.

Without --start, it starts from the first missing day in the last
MAX_CATCH_UP_DAYS, so a missed or failed run is caught up next time.

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

from .config import BACKEND_DIR, settings
from .db import connect

log = logging.getLogger("observe_imerg")

SHORT_NAME = "GPM_3IMERGDL"  # IMERG Late Run, daily, 0.1 degree
SOURCE = "imerg_late_v07"
DOWNLOAD_DIR = BACKEND_DIR / "imerg_data"
DOWNLOAD_TRIES = 3
MAX_CATCH_UP_DAYS = 30

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

    return (
        df.groupby(["obs_date", "cell_lat", "cell_lon"])["rain_mm"]
        .agg(rain_mm="mean", n_pixels="count")
        .reset_index()
        .rename(columns={"cell_lat": "lat", "cell_lon": "lon"})
    )


def readable(path: Path) -> bool:
    try:
        with xr.open_dataset(path) as ds:
            ds["precipitation"].isel(time=0, lat=0, lon=0).load()
        return True
    except Exception:  # truncated or corrupt file
        return False


def download(granule) -> Path | None:
    """Download one granule and check it opens. A broken connection leaves a
    truncated file that earthaccess would otherwise reuse as "already downloaded"
    on every later run, so bad files are deleted and fetched again."""
    path = DOWNLOAD_DIR / granule.data_links()[0].split("/")[-1]
    for attempt in range(1, DOWNLOAD_TRIES + 1):
        if path.exists() and readable(path):
            return path
        path.unlink(missing_ok=True)
        try:
            earthaccess.download([granule], local_path=str(DOWNLOAD_DIR), threads=1)
        except Exception as e:  # earthaccess re-raises a bare Exception; the cause is logged above it
            log.warning("%s: download failed (try %d of %d): %s", path.name, attempt, DOWNLOAD_TRIES, e)
    if path.exists() and readable(path):
        return path
    path.unlink(missing_ok=True)
    log.error("%s: giving up after %d tries", path.name, DOWNLOAD_TRIES)
    return None


def default_start(conn, end: date) -> date | None:
    """First day in the catch-up window that has no observations yet (None if complete)."""
    first = end - timedelta(days=MAX_CATCH_UP_DAYS)
    have = {
        r["obs_date"]
        for r in conn.execute(
            "SELECT DISTINCT obs_date FROM observation_daily WHERE source = %s AND obs_date BETWEEN %s AND %s",
            (SOURCE, first, end),
        )
    }
    if not have:  # fresh install or a long gap: just the last few days
        return end - timedelta(days=2)
    days = (first + timedelta(days=n) for n in range(MAX_CATCH_UP_DAYS + 1))
    return next((d for d in days if d not in have), None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=date.fromisoformat, help="first day (default: first missing day)")
    ap.add_argument("--end", type=date.fromisoformat, help="last day (default: 2 days ago)")
    ap.add_argument("--keep-files", action="store_true", help="don't delete the downloaded files")
    args = ap.parse_args()

    end = args.end or date.today() - timedelta(days=2)  # Late Run needs ~14 h after the day ends
    bbox = settings.bbox_bounds
    step = settings.grid_step

    with connect() as conn:
        start = args.start or default_start(conn, end)
        if start is None:
            print(f"Already up to date (observations through {end}).")
            return
        if start > end:
            raise SystemExit("--start must be on or before --end")

        cells = {
            cell_key(r["lat"], r["lon"]): r["id"]
            for r in conn.execute("SELECT id, lat, lon FROM grid_cell").fetchall()
        }
        if not cells:
            raise SystemExit("No grid cells yet. Run: python -m app.seed_grid")

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
        total, unmatched, failed = 0, 0, 0
        try:
            for granule in granules:
                path = download(granule)
                if path is None:
                    failed += 1
                    continue
                with xr.open_dataset(path) as ds:
                    agg = aggregate(ds, bbox, step)

                rows = []
                for r in agg.itertuples(index=False):
                    cell_id = cells.get(cell_key(r.lat, r.lon))
                    if cell_id is None:
                        unmatched += 1
                        continue
                    rows.append({"cell_id": cell_id, "obs_date": r.obs_date, "rain_mm": float(r.rain_mm), "source": SOURCE})
                with conn.cursor() as cur:
                    cur.executemany(UPSERT, rows)
                conn.commit()
                total += len(rows)
                if len(agg):
                    log.info("%s: %d cells, max %.1f mm", agg["obs_date"].iloc[0], len(rows), agg["rain_mm"].max())
        finally:
            if not args.keep_files:
                shutil.rmtree(DOWNLOAD_DIR, ignore_errors=True)

    if unmatched:
        log.warning(
            "%d cell-days didn't match a grid cell. Is the grid centred on multiples of %s? "
            "(re-run app.seed_grid after changing BBOX or GRID_STEP)",
            unmatched,
            step,
        )
    print(f"Stored {total} observed cell-days from {len(granules) - failed} IMERG files.")
    if failed:
        raise SystemExit(f"{failed} file(s) could not be downloaded. The next run will retry them.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
