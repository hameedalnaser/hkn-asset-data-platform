"""Ingestion orchestrator: read -> validate -> reconcile -> stage -> merge.

One function processes one file inside one transaction. The whole run over
a directory is a sequence of these, each independently committed or rolled
back, each recorded in audit.load_batch. This is the reliability story the
JD asks for: "ingestion ... validation, reconciliation, scheduling and
monitoring", "reconciled, logged and documented".

Flow per file:
  1. parse filename              -> skip + log strays
  2. read Excel                  -> DataFrame
  3. validate structure          -> ERROR findings abort this file
  4. reconcile (physical sense)  -> WARNING findings logged, load continues
  5. open batch (audit)          -> load_batch_id
  6. insert into staging         -> parameterised bulk insert
  7. ensure date + run MERGE proc-> staging into dw, idempotent
  8. purge staging batch, close audit row
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from pathlib import Path

from hkn_asset.db import repository as repo
from hkn_asset.db.connection import get_connection
from hkn_asset.domain import validation
from hkn_asset.domain.reports import parse_filename
from hkn_asset.ingestion.readers import read_report
from hkn_asset.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class FileResult:
    filename: str
    status: str                      # LOADED / FAILED / SKIPPED
    rows: int = 0
    findings: list[validation.Finding] = dc_field(default_factory=list)
    error: str | None = None


def process_file(path: Path) -> FileResult:
    """Process a single report file end to end. Never raises for data issues;
    returns a FileResult so the batch run can continue past a bad file."""
    report = parse_filename(path.name)
    if report is None:
        logger.warning("SKIP: %s does not match the report naming convention", path.name)
        return FileResult(path.name, "SKIPPED", error="unrecognised filename")

    df = read_report(path, report)

    findings = validation.run_all_checks(report.report_type, df)
    for f in findings:
        (logger.error if f.severity is validation.Severity.ERROR else logger.warning)(
            "%s | %s", path.name, f
        )

    if validation.has_errors(findings):
        logger.error("ABORT %s: structural validation failed", path.name)
        return FileResult(path.name, "FAILED", findings=findings,
                          error="validation errors")

    # --- load inside one transaction ---
    try:
        with get_connection() as conn:
            batch_id = repo.start_load_batch(
                conn, path.name, report.report_type,
                report.field_name, report.report_date, len(df),
            )
            rows = repo.insert_staging(conn, report.report_type, df, batch_id)

            cur = conn.cursor()
            cur.execute("EXEC dw.usp_ensure_date @d = ?", report.report_date)

            repo.run_merge_proc(conn, report.report_type, batch_id)

            cur.execute(
                "EXEC dw.usp_purge_staging_batch @report_type = ?, @load_batch_id = ?",
                report.report_type, batch_id,
            )

            status = "VALIDATED" if findings else "LOADED"
            msg = "; ".join(str(f) for f in findings) or None
            repo.finish_load_batch(conn, batch_id, status, msg)
        logger.info("OK %s: %s rows loaded (batch %s)", path.name, rows, batch_id)
        return FileResult(path.name, "LOADED", rows=rows, findings=findings)
    except Exception as exc:  # DB/connection failures
        logger.exception("FAILED %s", path.name)
        return FileResult(path.name, "FAILED", findings=findings, error=str(exc))


def process_directory(incoming_dir: Path) -> list[FileResult]:
    """Process every .xlsx in a directory, newest first. Returns per-file results."""
    files = sorted(incoming_dir.glob("*.xlsx"))
    logger.info("found %s files in %s", len(files), incoming_dir)
    results = [process_file(p) for p in files]

    loaded = sum(r.status == "LOADED" for r in results)
    failed = sum(r.status == "FAILED" for r in results)
    skipped = sum(r.status == "SKIPPED" for r in results)
    logger.info("run complete: %s loaded, %s failed, %s skipped",
                loaded, failed, skipped)
    return results
