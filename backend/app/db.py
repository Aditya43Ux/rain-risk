import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

# Used by the API (opened/closed in main.py's lifespan).
pool = ConnectionPool(
    settings.database_url,
    min_size=1,
    max_size=5,
    open=False,
    kwargs={"row_factory": dict_row},
)


def connect():
    """Plain connection for scripts (seed_grid, ingest, ...)."""
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def grid_cells(conn) -> list[dict]:
    """Every grid cell as {id, lat, lon}, or exit with a hint if the grid is empty."""
    cells = conn.execute("SELECT id, lat, lon FROM grid_cell ORDER BY id").fetchall()
    if not cells:
        raise SystemExit("No grid cells yet. Run: python -m app.seed_grid")
    return cells
