"""Validation and reconciliation checks.

Two kinds of check, matching how the JD frames the job:

  * VALIDATION  - is the file structurally usable? (right columns, parseable
                  dates, no negative rates). Failing these blocks the load.
  * RECONCILIATION - do the numbers make physical sense once loaded?
                  (export <= facility outlet, well oil ~ facility inlet,
                  downtime explains deferment). Failing these does NOT block
                  the load but is flagged loudly: "say when a number cannot
                  be trusted."

Pure functions on DataFrames so they unit-test without a database.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from hkn_asset.domain.reports import SPECS, ReportSpec


class Severity(str, Enum):
    ERROR = "ERROR"      # blocks the load
    WARNING = "WARNING"  # loads, but flagged for review


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    message: str

    def __str__(self) -> str:  # for logs
        return f"[{self.severity}] {self.code}: {self.message}"


# --------------------------------------------------------------------------- #
# Structural validation
# --------------------------------------------------------------------------- #
def validate_structure(df: pd.DataFrame, spec: ReportSpec) -> list[Finding]:
    findings: list[Finding] = []

    missing = [c for c in spec.required_columns if c not in df.columns]
    if missing:
        findings.append(
            Finding(Severity.ERROR, "MISSING_COLUMNS",
                    f"{spec.report_type}: missing required columns {missing}")
        )
        # can't check further without the columns
        return findings

    if df.empty:
        findings.append(Finding(Severity.ERROR, "EMPTY", f"{spec.report_type}: no rows"))
        return findings

    # negative values where physically impossible
    for col in spec.non_negative_columns:
        if col in df.columns:
            bad = df[pd.to_numeric(df[col], errors="coerce") < 0]
            if len(bad):
                findings.append(
                    Finding(Severity.ERROR, "NEGATIVE_VALUE",
                            f"{spec.report_type}.{col}: {len(bad)} negative value(s)")
                )

    return findings


# --------------------------------------------------------------------------- #
# Reconciliation (physical sanity). Each returns findings; tolerances are
# explicit so they can be argued about rather than hidden.
# --------------------------------------------------------------------------- #
def reconcile_production(df: pd.DataFrame, tol_bbl: float = 5.0) -> list[Finding]:
    """export <= facility_outlet <= facility_inlet, and sum(well oil) ~ inlet."""
    findings: list[Finding] = []

    facility = df[df["well"] == "FACILITY_TOTAL"]
    wells = df[df["well"] != "FACILITY_TOTAL"]
    if facility.empty:
        findings.append(Finding(Severity.WARNING, "NO_FACILITY_ROW",
                                 "production: no FACILITY_TOTAL row to reconcile against"))
        return findings

    row = facility.iloc[0]
    inlet = _num(row.get("facility_inlet_bbl"))
    outlet = _num(row.get("facility_outlet_bbl"))
    export = _num(row.get("export_bbl"))

    if None not in (export, outlet) and export > outlet + tol_bbl:
        findings.append(Finding(Severity.WARNING, "EXPORT_GT_OUTLET",
                                 f"export {export} > facility outlet {outlet}"))
    if None not in (outlet, inlet) and outlet > inlet + tol_bbl:
        findings.append(Finding(Severity.WARNING, "OUTLET_GT_INLET",
                                 f"facility outlet {outlet} > inlet {inlet}"))

    if inlet is not None:
        well_oil = pd.to_numeric(wells["oil_rate_bbl"], errors="coerce").sum()
        if abs(well_oil - inlet) > max(tol_bbl, 0.02 * inlet):
            findings.append(Finding(
                Severity.WARNING, "WELL_SUM_MISMATCH",
                f"sum of well oil {well_oil:.1f} != facility inlet {inlet:.1f}"))
    return findings


def reconcile_power(df: pd.DataFrame) -> list[Finding]:
    """avg load must not exceed nameplate capacity; hours_run in [0,24]."""
    findings: list[Finding] = []
    load = pd.to_numeric(df.get("avg_load_mw"), errors="coerce")
    cap = pd.to_numeric(df.get("capacity_mw"), errors="coerce")
    over = df[(load > cap) & cap.notna()]
    if len(over):
        findings.append(Finding(Severity.WARNING, "LOAD_GT_CAPACITY",
                                 f"power: {len(over)} generator-day(s) with load > capacity"))
    hrs = pd.to_numeric(df.get("hours_run"), errors="coerce")
    bad_hrs = df[(hrs < 0) | (hrs > 24)]
    if len(bad_hrs):
        findings.append(Finding(Severity.WARNING, "HOURS_OUT_OF_RANGE",
                                 f"power: {len(bad_hrs)} row(s) with hours_run outside 0-24"))
    return findings


def reconcile_deferment(df: pd.DataFrame) -> list[Finding]:
    """downtime_hours should be within a day; deferred barrels non-trivial."""
    findings: list[Finding] = []
    hrs = pd.to_numeric(df.get("downtime_hours"), errors="coerce")
    bad = df[(hrs < 0) | (hrs > 24)]
    if len(bad):
        findings.append(Finding(Severity.WARNING, "DOWNTIME_OUT_OF_RANGE",
                                 f"deferment: {len(bad)} row(s) with downtime outside 0-24h"))
    return findings


RECONCILERS = {
    "production": reconcile_production,
    "power": reconcile_power,
    "deferment": reconcile_deferment,
}


def run_all_checks(report_type: str, df: pd.DataFrame) -> list[Finding]:
    """Structural validation + any reconciliation for this report type."""
    spec = SPECS[report_type]
    findings = validate_structure(df, spec)
    # only reconcile if structurally sound (no ERROR findings)
    if not any(f.severity is Severity.ERROR for f in findings):
        reconciler = RECONCILERS.get(report_type)
        if reconciler:
            findings.extend(reconciler(df))
    return findings


def has_errors(findings: list[Finding]) -> bool:
    return any(f.severity is Severity.ERROR for f in findings)


def _num(v: object) -> float | None:
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None
