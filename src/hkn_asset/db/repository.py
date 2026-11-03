"""Data access for the ingestion pipeline.

Every SQL statement here is PARAMETERISED (? placeholders, values passed
separately) — JD: "parameterised SQL". No f-string value interpolation ever
reaches the database. Table/column names (never user input) are the only
identifiers formatted into SQL, and they come from our own code.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import TYPE_CHECKING

import pandas as pd

from hkn_asset.logging_setup import get_logger

if TYPE_CHECKING:
    import pyodbc

logger = get_logger(__name__)


# Column order per staging table (excluding load_batch_id, prepended at load).
STAGING_COLUMNS: dict[str, tuple[str, ...]] = {
    "production": (
        "report_date", "field_name", "well", "gross_rate_bbl", "bsw_fraction",
        "oil_rate_bbl", "status", "facility_inlet_bbl", "facility_outlet_bbl",
        "tank_opening_bbl", "tank_closing_bbl", "export_bbl", "flare_mscf",
    ),
    "deferment": (
        "report_date", "field_name", "cause", "equipment",
        "downtime_hours", "deferred_bbl", "comment",
    ),
    "power": (
        "report_date", "field_name", "generator", "capacity_mw", "hours_run",
        "avg_load_mw", "fuel_gas_mscf", "diesel_litres", "trips", "status",
    ),
    "maintenance": (
        "report_date", "field_name", "work_order", "equipment", "wo_type",
        "priority", "created_date", "status", "pm_due_date", "completed_date",
    ),
}

# Map DataFrame column names -> staging column names where they differ.
_DF_RENAME = {"field": "field_name", "date": "report_date"}


def start_load_batch(
    conn: pyodbc.Connection, source_file: str, report_type: str,
    field_name: str, report_date: date, row_count: int,
) -> int:
    """Insert a STARTED batch row, return its load_batch_id. Parameterised."""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO audit.load_batch
            (source_file, report_type, field_name, report_date, row_count, status)
        OUTPUT INSERTED.load_batch_id
        VALUES (?, ?, ?, ?, ?, 'STARTED')
        """,
        source_file, report_type, field_name, report_date, row_count,
    )
    batch_id = int(cur.fetchone()[0])
    logger.info("load_batch %s STARTED for %s", batch_id, source_file)
    return batch_id


def finish_load_batch(
    conn: pyodbc.Connection, batch_id: int, status: str, message: str | None = None
) -> None:
    """Mark a batch LOADED/VALIDATED/FAILED with a timestamp. Parameterised."""
    conn.cursor().execute(
        """
        UPDATE audit.load_batch
           SET status = ?, message = ?, finished_at_utc = SYSUTCDATETIME()
         WHERE load_batch_id = ?
        """,
        status, message, batch_id,
    )
    logger.info("load_batch %s -> %s", batch_id, status)


def insert_staging(
    conn: pyodbc.Connection, report_type: str, df: pd.DataFrame, batch_id: int
) -> int:
    """Bulk-insert a report's rows into its staging table. Parameterised.

    Uses executemany with fast_executemany for throughput. The column list
    is from our own STAGING_COLUMNS map (trusted identifiers), and every
    value is bound as a parameter.
    """
    columns = STAGING_COLUMNS[report_type]
    staged = df.rename(columns=_DF_RENAME)

    # keep only known columns; add any missing as NULL so the row shape is fixed
    for col in columns:
        if col not in staged.columns:
            staged[col] = None
    staged = staged[list(columns)]

    # NaN -> None so pyodbc sends SQL NULL, not the string 'nan'
    staged = staged.astype(object).where(pd.notna(staged), None)

    placeholders = ", ".join(["?"] * (len(columns) + 1))  # +1 for load_batch_id
    col_list = ", ".join(("load_batch_id", *columns))
    sql = f"INSERT INTO staging.{report_type} ({col_list}) VALUES ({placeholders})"

    rows: list[Sequence[object]] = [
        (batch_id, *tuple(r)) for r in staged.itertuples(index=False, name=None)
    ]

    cur = conn.cursor()
    cur.fast_executemany = True
    cur.executemany(sql, rows)
    logger.info("inserted %s rows into staging.%s (batch %s)", len(rows), report_type, batch_id)
    return len(rows)


def run_merge_proc(conn: pyodbc.Connection, report_type: str, batch_id: int) -> None:
    """Call the stored proc that MERGEs this batch from staging into dw.

    Parameterised call to a proc whose name comes from our own code.
    """
    proc = f"dw.usp_merge_{report_type}"
    conn.cursor().execute(f"EXEC {proc} @load_batch_id = ?", batch_id)
    logger.info("merged batch %s via %s", batch_id, proc)
