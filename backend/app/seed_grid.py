"""Create the grid of cells for BBOX. Safe to re-run.

    python -m app.seed_grid
"""
import numpy as np

from .config import settings
from .db import connect

INSERT = """
INSERT INTO grid_cell (lat, lon, centroid, geom)
VALUES (
    %(lat)s, %(lon)s,
    ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326),
    ST_MakeEnvelope(%(w)s, %(s)s, %(e)s, %(n)s, 4326)
)
ON CONFLICT (lat, lon) DO NOTHING
"""


def main() -> None:
    west, south, east, north = (float(x) for x in settings.bbox.split(","))
    step = settings.grid_step
    half = step / 2

    lons = np.arange(np.ceil(west / step) * step, east + 1e-9, step)
    lats = np.arange(np.ceil(south / step) * step, north + 1e-9, step)

    rows = []
    for lat in lats:
        for lon in lons:
            lat, lon = round(float(lat), 4), round(float(lon), 4)
            rows.append(
                {
                    "lat": lat,
                    "lon": lon,
                    "w": lon - half,
                    "s": lat - half,
                    "e": lon + half,
                    "n": lat + half,
                }
            )

    with connect() as conn, conn.cursor() as cur:
        cur.executemany(INSERT, rows)
    print(f"Seeded {len(rows)} cells ({len(lats)} x {len(lons)}) at {step} degree spacing.")


if __name__ == "__main__":
    main()
