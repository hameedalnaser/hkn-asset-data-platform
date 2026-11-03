"""Generate realistic daily oil & gas Excel reports for the Sarsang/Atrush demo.

These stand in for the real sources named in the JD:
  * Daily production  (wellhead -> facility inlet/outlet -> tank -> export)
  * Deferment/downtime (losses by cause: wells, facility, power, export)
  * Power generation  (generators: capacity, load, fuel gas, trips)
  * Maintenance work orders (CMMS extract: backlog, PM compliance, failures)

Each run writes one workbook per report type per day into sample_data/incoming,
mimicking files that would land there each morning. The numbers are internally
consistent (export <= inlet, downtime explains deferment) so the reconciliation
step in the pipeline has something real to check.

Usage:
    python scripts/generate_sample_reports.py --days 30
"""

from __future__ import annotations

import argparse
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from hkn_asset.config import get_settings

FIELDS = ["Sarsang", "Atrush"]

WELLS = {
    "Sarsang": ["SAR-01", "SAR-02", "SAR-03", "SAR-04", "SAR-05"],
    "Atrush": ["ATR-01", "ATR-02", "ATR-03"],
}

GENERATORS = {
    "Sarsang": ["GEN-A", "GEN-B", "GEN-C"],
    "Atrush": ["GEN-A", "GEN-B"],
}

EQUIPMENT = [
    "Separator V-101", "Export Pump P-201", "Export Pump P-202",
    "Gas Compressor K-301", "Water Pump P-401", "Generator GEN-A",
]
DOWNTIME_CAUSES = ["Wells", "Facility", "Power", "Export"]


def _rng(seed_date: date, field: str) -> random.Random:
    """Deterministic per day+field so re-runs reproduce the same reports."""
    return random.Random(f"{seed_date.isoformat()}-{field}")


def production_report(day: date, field: str) -> pd.DataFrame:
    r = _rng(day, field)
    rows = []
    facility_inlet = 0.0
    for well in WELLS[field]:
        base = r.uniform(800, 2500)
        # occasional well down
        down = r.random() < 0.08
        gross = 0.0 if down else base * r.uniform(0.9, 1.05)
        bsw = r.uniform(0.05, 0.35)  # basic sediment & water fraction
        oil = gross * (1 - bsw)
        facility_inlet += oil
        rows.append(
            {
                "date": day,
                "field": field,
                "well": well,
                "gross_rate_bbl": round(gross, 1),
                "bsw_fraction": round(bsw, 3),
                "oil_rate_bbl": round(oil, 1),
                "status": "DOWN" if down else "UP",
            }
        )
    # facility-level figures derived from well oil, with small losses
    treatment_loss = facility_inlet * r.uniform(0.0, 0.02)
    facility_outlet = facility_inlet - treatment_loss
    tank_opening = r.uniform(5000, 20000)
    export = facility_outlet * r.uniform(0.95, 1.0)
    tank_closing = tank_opening + facility_outlet - export
    flare_mscf = r.uniform(50, 400)
    rows.append(
        {
            "date": day,
            "field": field,
            "well": "FACILITY_TOTAL",
            "gross_rate_bbl": None,
            "bsw_fraction": None,
            "oil_rate_bbl": round(facility_inlet, 1),
            "status": "",
            # extra facility columns (sparse for well rows, filled here)
            "facility_inlet_bbl": round(facility_inlet, 1),
            "facility_outlet_bbl": round(facility_outlet, 1),
            "tank_opening_bbl": round(tank_opening, 1),
            "tank_closing_bbl": round(tank_closing, 1),
            "export_bbl": round(export, 1),
            "flare_mscf": round(flare_mscf, 1),
        }
    )
    return pd.DataFrame(rows)


def deferment_report(day: date, field: str) -> pd.DataFrame:
    r = _rng(day, field)
    rows = []
    n_events = r.randint(0, 3)
    for _ in range(n_events):
        cause = r.choice(DOWNTIME_CAUSES)
        hours = round(r.uniform(0.5, 12), 1)
        loss = round(hours * r.uniform(30, 120), 1)  # bbl lost
        rows.append(
            {
                "date": day,
                "field": field,
                "cause": cause,
                "equipment": r.choice(EQUIPMENT),
                "downtime_hours": hours,
                "deferred_bbl": loss,
                "comment": f"{cause} event",
            }
        )
    if not rows:  # always emit at least a zero row so the day is represented
        rows.append(
            {
                "date": day, "field": field, "cause": "None",
                "equipment": "", "downtime_hours": 0.0,
                "deferred_bbl": 0.0, "comment": "No deferment",
            }
        )
    return pd.DataFrame(rows)


def power_report(day: date, field: str) -> pd.DataFrame:
    r = _rng(day, field)
    rows = []
    for gen in GENERATORS[field]:
        capacity_mw = r.choice([5.0, 7.5, 10.0])
        tripped = r.random() < 0.05
        hours_run = 0.0 if tripped else round(r.uniform(18, 24), 1)
        load_mw = 0.0 if tripped else round(capacity_mw * r.uniform(0.5, 0.95), 2)
        fuel_gas_mscf = round(load_mw * hours_run * r.uniform(8, 12), 1)
        diesel_l = round(r.uniform(0, 500), 1) if r.random() < 0.3 else 0.0
        rows.append(
            {
                "date": day, "field": field, "generator": gen,
                "capacity_mw": capacity_mw, "hours_run": hours_run,
                "avg_load_mw": load_mw, "fuel_gas_mscf": fuel_gas_mscf,
                "diesel_litres": diesel_l,
                "trips": 1 if tripped else 0,
                "status": "TRIPPED" if tripped else "RUNNING",
            }
        )
    return pd.DataFrame(rows)


def maintenance_report(day: date, field: str) -> pd.DataFrame:
    r = _rng(day, field)
    rows = []
    n = r.randint(2, 6)
    for i in range(n):
        wo_type = r.choice(["PM", "PM", "CM", "CM", "Inspection"])
        created = day - timedelta(days=r.randint(0, 45))
        status = r.choice(["OPEN", "OPEN", "IN_PROGRESS", "CLOSED"])
        rows.append(
            {
                "date": day, "field": field,
                "work_order": f"WO-{field[:3].upper()}-{created.strftime('%y%m%d')}-{i:02d}",
                "equipment": r.choice(EQUIPMENT),
                "wo_type": wo_type,
                "priority": r.choice([1, 2, 2, 3, 3, 3]),
                "created_date": created,
                "status": status,
                "pm_due_date": created + timedelta(days=30) if wo_type == "PM" else None,
                "completed_date": day if status == "CLOSED" else None,
            }
        )
    return pd.DataFrame(rows)


REPORTS = {
    "production": production_report,
    "deferment": deferment_report,
    "power": power_report,
    "maintenance": maintenance_report,
}


def write_workbook(df: pd.DataFrame, path: Path, sheet: str) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name=sheet, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30, help="how many days back to generate")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    settings = get_settings()
    out_dir = settings.incoming_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    today = date.today()
    count = 0
    for offset in range(args.days):
        day = today - timedelta(days=offset)
        for field in FIELDS:
            for report_name, fn in REPORTS.items():
                df = fn(day, field)
                fname = f"{report_name}_{field}_{day.isoformat()}.xlsx"
                write_workbook(df, out_dir / fname, sheet=report_name)
                count += 1

    print(f"Generated {count} report files in {out_dir}")


if __name__ == "__main__":
    main()
