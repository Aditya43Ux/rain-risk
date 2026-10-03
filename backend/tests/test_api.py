"""API against the real database. Skipped when PostgreSQL isn't reachable."""
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

try:
    psycopg.connect(settings.database_url, connect_timeout=2).close()
except psycopg.OperationalError:
    pytest.skip("database not reachable", allow_module_level=True)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def area(client):
    r = client.get("/api/forecast/area")
    assert r.status_code == 200
    data = r.json()
    if not data["dates"]:
        pytest.skip("no forecast stored yet")
    return data


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_area_shape(area):
    n = len(area["dates"])
    assert area["dates"] == sorted(area["dates"])
    assert area["updated_at"]
    assert area["grid"]["features"]
    for f in area["grid"]["features"]:
        assert f["geometry"]["type"] == "Polygon"
        assert len(f["properties"]["chance_pct"]) == n
        assert len(f["properties"]["mean_mm"]) == n
        assert all(p is None or 0 <= p <= 100 for p in f["properties"]["chance_pct"])


def test_point_matches_area(client, area):
    f = next(f for f in area["grid"]["features"] if any(p is not None for p in f["properties"]["chance_pct"]))
    ring = f["geometry"]["coordinates"][0][:-1]
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)

    r = client.get("/api/forecast/point", params={"lat": lat, "lon": lon})
    assert r.status_code == 200
    data = r.json()
    assert data["cell"]["id"] == f["id"]
    by_date = {d["date"]: d["chance_pct"] for d in data["days"]}
    for d, p in zip(area["dates"], f["properties"]["chance_pct"]):
        assert by_date.get(d) == p

    near = client.get("/api/forecast/nearby", params={"lat": lat, "lon": lon, "day": area["dates"][0], "radius_km": 50})
    cells = near.json()["cells"]
    assert cells[0]["cell_id"] == f["id"]
    assert [c["distance_km"] for c in cells] == sorted(c["distance_km"] for c in cells)


def test_point_outside_area(client):
    assert client.get("/api/forecast/point", params={"lat": -60, "lon": -100}).status_code == 404


def test_validation(client):
    assert client.get("/api/forecast/point", params={"lat": 200, "lon": 0}).status_code == 422
    assert client.get("/api/forecast/nearby", params={"lat": 0, "lon": 0, "day": "x"}).status_code == 422
