from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import pool

COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
KM_PER_DEGREE = 111.0


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["GET"],
    allow_headers=["*"],
)

MODEL = {"model": settings.ensemble_model}


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    """Which days are available, what 'rain' means, and how fresh the data is."""
    r = rows(
        """
        SELECT DISTINCT valid_date, fetched_at FROM forecast_daily
        WHERE model = %(model)s
          AND fetched_at = (SELECT max(fetched_at) FROM forecast_daily WHERE model = %(model)s)
        ORDER BY valid_date
        """,
        MODEL,
    )
    return {
        "model": settings.ensemble_model,
        "rain_threshold_mm": settings.rain_threshold_mm,
        "dates": [x["valid_date"].isoformat() for x in r],
        "updated_at": r[0]["fetched_at"].isoformat() if r else None,
    }


@app.get("/api/forecast/map")
def forecast_map(day: date):
    """Every grid cell for one day, as GeoJSON polygons with the rain chance."""
    r = rows(
        """
        SELECT c.id, f.p_rain, f.mean_mm, f.p90_mm,
               ST_AsGeoJSON(c.geom)::json AS geometry
        FROM forecast_latest f
        JOIN grid_cell c ON c.id = f.cell_id
        WHERE f.valid_date = %(day)s AND f.model = %(model)s
        """,
        {"day": day, **MODEL},
    )
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": x["id"],
                "geometry": x["geometry"],
                "properties": {
                    "chance_pct": pct(x["p_rain"]),
                    "mean_mm": x["mean_mm"],
                    "p90_mm": x["p90_mm"],
                },
            }
            for x in r
        ],
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
        """
        WITH me AS (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326) AS g)
        SELECT c.id, c.lat, c.lon, f.p_rain, f.mean_mm,
               ST_Distance(c.centroid::geography, me.g::geography) / 1000.0 AS km,
               degrees(ST_Azimuth(me.g, c.centroid)) AS bearing
        FROM me, grid_cell c
        JOIN forecast_latest f ON f.cell_id = c.id
        WHERE f.valid_date = %(day)s
          AND f.model = %(model)s
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
        """
        SELECT valid_date, p_rain, mean_mm, p90_mm
        FROM forecast_latest
        WHERE cell_id = %(id)s AND model = %(model)s
          AND fetched_at = (SELECT max(fetched_at) FROM forecast_daily WHERE model = %(model)s)
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
