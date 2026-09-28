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
    """Plain connection for scripts (seed_grid, ingest)."""
    return psycopg.connect(settings.database_url, row_factory=dict_row)
