"""Shared bits for talking to the Open-Meteo APIs."""
import logging
import time

import httpx
import pandas as pd

log = logging.getLogger("openmeteo")


def get_json(url: str, params: dict, *, tries: int = 4, wait: float = 5, timeout: float = 60) -> list[dict]:
    """GET with exponential back-off on 429. Always returns a list (one item per location)."""
    for attempt in range(tries):
        r = httpx.get(url, params=params, timeout=timeout)
        if r.status_code == 429:  # rate limited
            delay = wait * 2**attempt
            log.warning("rate limited, waiting %.0fs", delay)
            time.sleep(delay)
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"Open-Meteo error {r.status_code}: {r.text[:300]}")
        data = r.json()
        return data if isinstance(data, list) else [data]
    raise RuntimeError("Open-Meteo rate limit hit. Try again later (the free limit resets daily).")


def coords(cells: list[dict]) -> dict:
    """latitude/longitude params for a multi-location request."""
    return {
        "latitude": ",".join(f"{c['lat']:.4f}" for c in cells),
        "longitude": ",".join(f"{c['lon']:.4f}" for c in cells),
    }


def complete_daily_sum(df: pd.DataFrame, col: str, by: str = "valid_date") -> pd.Series:
    """Hourly column -> daily totals, NaN for any day that doesn't have all 24 hours."""
    g = df.groupby(by)[col]
    return g.sum(min_count=1).where(g.count() == 24)
