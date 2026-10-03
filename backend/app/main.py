from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .config import settings
from .db import pool

COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
KM_PER_DEGREE = 111.0

# Every endpoint reads only the newest run of the display model, so all of them
# agree on which forecast they show.
LATEST_RUN = "(SELECT max(fetched_at) FROM forecast_daily WHERE model = %(model)s)"
MODEL = {"model": settings.display_model}


def compass(deg: float | None) -> str | None:
    if deg is None:
        return None
    return COMPASS[int((deg % 360 + 22.5) // 45) % 8]


def pct(p: float | None) -> int | None:
    return None if p is None else round(p * 100)


def rows(sql: str, params: dict | None = None) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(sql, params or {}).fetchall()


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(title="Rain risk API", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/forecast/area")
def forecast_area():
    """Everything the map needs in one response: the grid as GeoJSON polygons,
    with each cell's rain chance and expected mm for every forecast day.

    properties.chance_pct[i] and properties.mean_mm[i] belong to dates[i].
    """
    forecast = rows(
        f"""
        SELECT cell_id, valid_date, p_rain, mean_mm, fetched_at
        FROM forecast_daily
        WHERE model = %(model)s AND fetched_at = {LATEST_RUN}
        ORDER BY valid_date
        """,
        MODEL,
    )
    dates = sorted({r["valid_date"] for r in forecast})
    col = {d: i for i, d in enumerate(dates)}
    cells = rows("SELECT id, ST_AsGeoJSON(geom, 5)::json AS geometry FROM grid_cell ORDER BY id")

    chance = {c["id"]: [None] * len(dates) for c in cells}
    amount = {c["id"]: [None] * len(dates) for c in cells}
    for r in forecast:
        if r["cell_id"] in chance:
            chance[r["cell_id"]][col[r["valid_date"]]] = pct(r["p_rain"])
            amount[r["cell_id"]][col[r["valid_date"]]] = r["mean_mm"]

    return {
        "model": settings.display_model,
        "rain_threshold_mm": settings.rain_threshold_mm,
        "updated_at": forecast[0]["fetched_at"].isoformat() if forecast else None,
        "dates": [d.isoformat() for d in dates],
        "grid": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": c["id"],
                    "geometry": c["geometry"],
                    "properties": {"chance_pct": chance[c["id"]], "mean_mm": amount[c["id"]]},
                }
                for c in cells
            ],
        },
    }


@app.get("/api/forecast/nearby")
def forecast_nearby(
    day: date,
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    radius_km: float = Query(25, gt=0, le=200),
):
    """Rain chance for every cell within radius_km of a point, nearest first."""
    r = rows(
        f"""
        WITH me AS (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326) AS g)
        SELECT c.id, c.lat, c.lon, f.p_rain, f.mean_mm,
               ST_Distance(c.centroid::geography, me.g::geography) / 1000.0 AS km,
               degrees(ST_Azimuth(me.g, c.centroid)) AS bearing
        FROM me, grid_cell c
        JOIN forecast_daily f ON f.cell_id = c.id
        WHERE f.valid_date = %(day)s
          AND f.model = %(model)s
          AND f.fetched_at = {LATEST_RUN}
          AND ST_DWithin(c.centroid::geography, me.g::geography, %(radius_m)s)
        ORDER BY km
        """,
        {"lat": lat, "lon": lon, "day": day, "radius_m": radius_km * 1000, **MODEL},
    )
    return {
        "day": day.isoformat(),
        "radius_km": radius_km,
        "cells": [
            {
                "cell_id": x["id"],
                "lat": x["lat"],
                "lon": x["lon"],
                "distance_km": round(x["km"], 1),
                "direction": compass(x["bearing"]),
                "chance_pct": pct(x["p_rain"]),
                "mean_mm": x["mean_mm"],
            }
            for x in r
        ],
    }


@app.get("/api/forecast/point")
def forecast_point(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
):
    """Every available day for the grid cell nearest to a point."""
    nearest = rows(
        """
        WITH me AS (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326) AS g)
        SELECT c.id, c.lat, c.lon,
               ST_Distance(c.centroid::geography, me.g::geography) / 1000.0 AS km
        FROM me, grid_cell c
        ORDER BY c.centroid <-> me.g
        LIMIT 1
        """,
        {"lat": lat, "lon": lon},
    )
    if not nearest or nearest[0]["km"] > settings.grid_step * KM_PER_DEGREE:
        raise HTTPException(404, "That spot is outside the forecast area.")
    cell = nearest[0]

    days = rows(
        f"""
        SELECT valid_date, p_rain, mean_mm, p90_mm
        FROM forecast_daily
        WHERE cell_id = %(id)s AND model = %(model)s AND fetched_at = {LATEST_RUN}
        ORDER BY valid_date
        """,
        {"id": cell["id"], **MODEL},
    )
    return {
        "cell": {"id": cell["id"], "lat": cell["lat"], "lon": cell["lon"]},
        "days": [
            {
                "date": d["valid_date"].isoformat(),
                "chance_pct": pct(d["p_rain"]),
                "mean_mm": d["mean_mm"],
                "p90_mm": d["p90_mm"],
            }
            for d in days
        ],
    }
