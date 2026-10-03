"""Pure data-processing logic: no network, no database."""
from datetime import date

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from app.backfill_forecasts import daily_totals
from app.ingest import summarize
from app.main import compass, pct
from app.observe_imerg import aggregate
from app.openmeteo import complete_daily_sum
from app.predict import build_rows, daily
from ml.train_model import add_features


def hours(day: str, n: int = 24) -> list[str]:
    return [f"{day}T{h:02d}:00" for h in range(n)]


@pytest.mark.parametrize(
    "deg, expected",
    [(0, "N"), (22.4, "N"), (22.5, "NE"), (90, "E"), (180, "S"), (270, "W"), (337.5, "N"), (-45, "NW"), (None, None)],
)
def test_compass(deg, expected):
    assert compass(deg) == expected


def test_pct():
    assert pct(None) is None
    assert pct(0.234) == 23
    assert pct(1.0) == 100


def test_complete_daily_sum_drops_partial_days():
    df = pd.DataFrame({"valid_date": ["a"] * 24 + ["b"] * 23, "x": [1.0] * 47})
    out = complete_daily_sum(df, "x")
    assert out["a"] == 24
    assert np.isnan(out["b"])


def test_summarize_counts_wet_members():
    # 4 members; daily totals 0, 0.5, 1.0, 2.4 mm -> 2 of 4 reach 1 mm
    hourly = {"time": hours("2026-07-01")}
    for i, total in enumerate([0, 0.5, 1.0, 2.4]):
        hourly[f"precipitation_member{i:02d}" if i else "precipitation"] = [total / 24] * 24
    out = summarize(hourly)
    row = out.loc[date(2026, 7, 1)]
    assert row["p_rain"] == pytest.approx(0.5)
    assert row["n_members"] == 4
    assert row["mean_mm"] == pytest.approx(0.975)


def test_summarize_ignores_missing_members():
    hourly = {"time": hours("2026-07-01"), "precipitation": [1.0] * 24, "precipitation_member01": [None] * 24}
    row = summarize(hourly).iloc[0]
    assert row["n_members"] == 1
    assert row["p_rain"] == 1.0


def test_backfill_daily_totals_keeps_complete_days_only():
    hourly = {
        "time": hours("2026-07-01") + hours("2026-07-02", 12),
        "precipitation_previous_day1": [0.5] * 36,
        "precipitation_previous_day3": [0.1] * 36,
    }
    out = daily_totals(hourly)
    assert set(out["lead_days"]) == {1, 3}
    assert list(out["valid_date"].unique()) == [date(2026, 7, 1)]
    assert out.set_index("lead_days").loc[1, "precip_mm"] == pytest.approx(12.0)


def test_predict_daily_and_lead_times():
    hourly = {"time": hours("2026-07-01") + hours("2026-07-02"), "precipitation": [0.1] * 48}
    d = daily(hourly)
    assert d["precip_mm"].tolist() == pytest.approx([2.4, 2.4])
    assert d["prev_run_mm"].isna().all()  # column missing from the response

    fc = d.assign(cell_id=1, lat=0.0, lon=0.0)
    rows = build_rows(fc, pd.Timestamp("2026-07-01"))
    assert rows["lead_days"].tolist() == [1, 1]  # today counts as lead 1


def test_add_features_neighbourhood():
    # 3x3 block, centre cell forecast 9 mm, the rest 0 mm
    cells = [(i, 10 + dy * 0.25, 70 + dx * 0.25) for i, (dy, dx) in enumerate((y, x) for y in (-1, 0, 1) for x in (-1, 0, 1))]
    df = pd.DataFrame(
        {
            "cell_id": [c[0] for c in cells],
            "lat": [c[1] for c in cells],
            "lon": [c[2] for c in cells],
            "valid_date": pd.Timestamp("2026-07-01"),
            "lead_days": 2,
            "precip_mm": [9.0 if c[0] == 4 else 0.0 for c in cells],
            "observed_mm": 0.0,
        }
    )
    out = add_features(df, step=0.25, threshold=1.0).set_index("cell_id")
    assert out.loc[4, "nbr_mean_mm"] == pytest.approx(1.0)
    assert out.loc[4, "nbr_wet_frac"] == pytest.approx(1 / 9)
    assert out.loc[0, "nbr_max_mm"] == 9.0  # corner still sees the wet centre
    assert out.loc[0, "nbr_mean_mm"] == pytest.approx(9 / 4)  # only 4 cells exist around a corner
    assert out["prev_run_mm"].isna().all()  # no lead-3 rows
    assert (out["rained"] == 0).all()


def test_aggregate_snaps_pixels_to_cells():
    lats = np.round(np.arange(9.85, 10.16, 0.1), 2)  # 9.85 .. 10.15
    lons = np.round(np.arange(69.85, 70.16, 0.1), 2)
    rain = np.arange(len(lats) * len(lons), dtype=float).reshape(1, len(lons), len(lats))
    rain[0, 1, 1] = np.nan  # the (69.95, 9.95) pixel
    ds = xr.Dataset(
        {"precipitation": (("time", "lon", "lat"), rain)},
        coords={"time": pd.to_datetime(["2026-07-01"]), "lon": lons, "lat": lats},
    )
    out = aggregate(ds, bbox=(70.0, 10.0, 70.0, 10.0), step=0.25)
    assert len(out) == 1
    row = out.iloc[0]
    assert (row["lat"], row["lon"]) == (10.0, 70.0)
    # only pixels within half a cell (9.875-10.125) count: 2 x 2, one of them NaN
    assert row["n_pixels"] == 3
    assert row["obs_date"] == date(2026, 7, 1)
