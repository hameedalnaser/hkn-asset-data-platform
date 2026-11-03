"""Report definitions: how to recognise and parse each Excel report type.

One place that knows the filename convention and the expected columns of
each source. Keeping this declarative means adding a new report type is a
data change, not a code change — the kind of maintainability the JD's
"one agreed set of data definitions" implies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

# Filenames look like: production_Sarsang_2026-11-03.xlsx
_FILENAME_RE = re.compile(
    r"^(?P<report_type>production|deferment|power|maintenance)"
    r"_(?P<field>[A-Za-z]+)"
    r"_(?P<date>\d{4}-\d{2}-\d{2})\.xlsx$"
)


@dataclass(frozen=True)
class ReportFile:
    """Parsed identity of an incoming report file."""

    report_type: str
    field_name: str
    report_date: date
    filename: str


def parse_filename(filename: str) -> ReportFile | None:
    """Return a ReportFile, or None if the name doesn't match the convention.

    Returning None (rather than raising) lets the pipeline skip and log
    stray files instead of crashing the whole run — a reliability habit.
    """
    m = _FILENAME_RE.match(filename)
    if not m:
        return None
    return ReportFile(
        report_type=m.group("report_type"),
        field_name=m.group("field"),
        report_date=date.fromisoformat(m.group("date")),
        filename=filename,
    )


@dataclass(frozen=True)
class ReportSpec:
    """What a valid report of this type must contain."""

    report_type: str
    sheet: str
    required_columns: tuple[str, ...]
    # columns that must be non-negative where present (physical sanity)
    non_negative_columns: tuple[str, ...] = field(default_factory=tuple)


SPECS: dict[str, ReportSpec] = {
    "production": ReportSpec(
        report_type="production",
        sheet="production",
        required_columns=("date", "field", "well", "oil_rate_bbl"),
        non_negative_columns=("gross_rate_bbl", "oil_rate_bbl", "export_bbl", "flare_mscf"),
    ),
    "deferment": ReportSpec(
        report_type="deferment",
        sheet="deferment",
        required_columns=("date", "field", "cause", "downtime_hours", "deferred_bbl"),
        non_negative_columns=("downtime_hours", "deferred_bbl"),
    ),
    "power": ReportSpec(
        report_type="power",
        sheet="power",
        required_columns=("date", "field", "generator", "capacity_mw", "avg_load_mw"),
        non_negative_columns=("capacity_mw", "hours_run", "avg_load_mw", "fuel_gas_mscf", "diesel_litres"),
    ),
    "maintenance": ReportSpec(
        report_type="maintenance",
        sheet="maintenance",
        required_columns=("date", "field", "work_order", "status"),
    ),
}
