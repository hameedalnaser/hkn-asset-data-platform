"""Read Excel reports into tidy DataFrames.

Uses pandas + openpyxl (JD names openpyxl explicitly). Normalises column
names and parses the report date so downstream code sees consistent types,
regardless of how the workbook was formatted.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from hkn_asset.domain.reports import SPECS, ReportFile


def read_report(path: Path, report: ReportFile) -> pd.DataFrame:
    """Load one report workbook into a DataFrame, lightly normalised."""
    spec = SPECS[report.report_type]
    df = pd.read_excel(path, sheet_name=spec.sheet, engine="openpyxl")

    # normalise headers: strip + lower-case so 'Field' == 'field'
    df.columns = [str(c).strip().lower() for c in df.columns]

    # coerce the date column to python date (not timestamp) for a clean key
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    return df
