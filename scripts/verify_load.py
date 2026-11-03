"""Post-load verification: prove the warehouse was populated correctly.

Queries the dw/app layer through parameterised SQL and prints a short report:
row counts per fact, the most recent audit.load_batch rows, and any
reconciliation flags surfaced by the views. Run after run_ingestion.py.
"""

from __future__ import annotations

from hkn_asset.db.connection import get_connection
from hkn_asset.logging_setup import setup_logging

COUNT_QUERIES = {
    "dim_date": "SELECT COUNT(*) FROM dw.dim_date",
    "dim_field": "SELECT COUNT(*) FROM dw.dim_field",
    "dim_well": "SELECT COUNT(*) FROM dw.dim_well",
    "fact_production": "SELECT COUNT(*) FROM dw.fact_production",
    "fact_facility_daily": "SELECT COUNT(*) FROM dw.fact_facility_daily",
    "fact_deferment": "SELECT COUNT(*) FROM dw.fact_deferment",
    "fact_power": "SELECT COUNT(*) FROM dw.fact_power",
    "fact_maintenance": "SELECT COUNT(*) FROM dw.fact_maintenance",
}


def main() -> None:
    setup_logging(to_file=False)
    with get_connection() as conn:
        cur = conn.cursor()

        print("\n=== Row counts ===")
        for name, q in COUNT_QUERIES.items():
            cur.execute(q)
            print(f"  {name:<22} {cur.fetchone()[0]:>8}")

        print("\n=== Last 8 load batches ===")
        cur.execute(
            """
            SELECT TOP 8 load_batch_id, report_type, field_name,
                   report_date, row_count, status, loaded_by
            FROM audit.load_batch
            ORDER BY load_batch_id DESC
            """
        )
        for r in cur.fetchall():
            print(f"  #{r[0]:<4} {r[1]:<12} {r[2]:<8} {r[3]} rows={r[4]:<4} "
                  f"{r[5]:<10} by {r[6]}")

        print("\n=== Reconciliation flags (export > outlet) ===")
        cur.execute(
            """
            SELECT report_date, field_name, export_bbl, facility_outlet_bbl
            FROM app.v_facility_daily
            WHERE export_exceeds_outlet_flag = 1
            ORDER BY report_date DESC
            """
        )
        flagged = cur.fetchall()
        if not flagged:
            print("  none — all days reconcile")
        else:
            for r in flagged:
                print(f"  {r[0]} {r[1]}: export {r[2]} > outlet {r[3]}")

        print("\n=== Sample: top deferment causes ===")
        cur.execute(
            """
            SELECT cause, COUNT(*) AS events, SUM(deferred_bbl) AS bbl_lost
            FROM app.v_deferment
            GROUP BY cause
            ORDER BY bbl_lost DESC
            """
        )
        for r in cur.fetchall():
            print(f"  {r[0]:<10} events={r[1]:<4} bbl_lost={r[2]}")


if __name__ == "__main__":
    main()
