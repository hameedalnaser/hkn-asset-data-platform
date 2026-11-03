"""Apply the sql/ migration scripts to the configured database, in order.

Splits each file on T-SQL 'GO' batch separators (pyodbc sends one batch at a
time; GO is a client directive, not a SQL statement). Idempotent scripts mean
this is safe to re-run.

Usage:
    python scripts/run_migrations.py            # runs sql/*.sql in name order
    python scripts/run_migrations.py --only 08  # run only files starting '08'

Connects with the credentials in .env (SQL_USERNAME/PASSWORD). For the very
first run you point .env at the *admin* login so the script can create
schemas, roles and the app users (sql/02). After that the pipeline uses the
low-privilege etl_user.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from hkn_asset.config import PROJECT_ROOT, get_settings
from hkn_asset.db.connection import get_connection
from hkn_asset.logging_setup import get_logger, setup_logging

logger = get_logger(__name__)

# split on a line that is just GO (case-insensitive), optionally indented
_GO = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)


def split_batches(sql: str) -> list[str]:
    return [b.strip() for b in _GO.split(sql) if b.strip()]


def run_file(path: Path) -> None:
    logger.info("applying %s", path.name)
    batches = split_batches(path.read_text())
    with get_connection() as conn:
        cur = conn.cursor()
        for i, batch in enumerate(batches, 1):
            try:
                cur.execute(batch)
            except Exception:
                logger.error("failed in %s batch %s:\n%s", path.name, i, batch[:400])
                raise
    logger.info("  %s batches OK", len(batches))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="only run files whose name starts with this")
    parser.add_argument("--sql-dir", type=Path, default=PROJECT_ROOT / "sql")
    args = parser.parse_args()

    setup_logging()
    get_settings()  # fail fast if .env is missing

    files = sorted(p for p in args.sql_dir.glob("*.sql"))
    if args.only:
        files = [p for p in files if p.name.startswith(args.only)]
    if not files:
        logger.error("no .sql files matched")
        return 1

    for path in files:
        run_file(path)
    logger.info("all migrations applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
