"""Database connection management.

JD standards: authenticated access, no credentials in code (creds come from
config/env), encrypted transport (Encrypt=yes in the connection string).

pyodbc is imported lazily so the rest of the package (readers, validation,
sample generator, their tests) can run on a machine without the ODBC driver
installed. Only code that actually talks to SQL needs pyodbc present.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from hkn_asset.config import get_settings
from hkn_asset.logging_setup import get_logger

if TYPE_CHECKING:  # for type hints only; no runtime import
    import pyodbc

logger = get_logger(__name__)


@contextmanager
def get_connection() -> Iterator[pyodbc.Connection]:
    """Yield a pyodbc connection built from env-based settings.

    Transactions are committed on clean exit and rolled back on exception,
    so a failed load never leaves half-written data (reliability).
    """
    import pyodbc  # lazy

    settings = get_settings()
    conn = pyodbc.connect(settings.odbc_connection_string, autocommit=False)
    logger.debug("opened SQL connection to %s/%s", settings.sql_server, settings.sql_database)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("transaction rolled back")
        raise
    finally:
        conn.close()
