"""Create or update the database schema. Safe to re-run.

    python -m app.migrate

Applies every db/*.sql file in name order. Each file is idempotent
(IF NOT EXISTS / IF EXISTS), so this also brings older databases up to date.
"""
from .config import BACKEND_DIR
from .db import connect

SQL_DIR = BACKEND_DIR.parent / "db"


def main() -> None:
    files = sorted(SQL_DIR.glob("*.sql"))
    with connect() as conn:
        for f in files:
            conn.execute(f.read_text(encoding="utf-8"))
            print(f"applied {f.name}")


if __name__ == "__main__":
    main()
