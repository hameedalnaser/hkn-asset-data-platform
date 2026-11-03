"""Round-trip test: generate a report, read it back, check it validates."""

from datetime import date

import pandas as pd

from hkn_asset.domain import validation as v
from hkn_asset.domain.reports import parse_filename
from hkn_asset.ingestion.readers import read_report


def _write(tmp_path, name, df):
    p = tmp_path / name
    with pd.ExcelWriter(p, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name=name.split("_")[0], index=False)
    return p


def test_reader_normalises_headers_and_date(tmp_path):
    raw = pd.DataFrame({
        "Date": [date(2026, 11, 3)], "Field": ["Sarsang"],
        "Well": ["SAR-01"], "Oil_Rate_Bbl": [100.0],
    })
    path = _write(tmp_path, "production_Sarsang_2026-11-03.xlsx", raw)
    report = parse_filename(path.name)
    df = read_report(path, report)
    # headers lower-cased
    assert "oil_rate_bbl" in df.columns
    assert df["date"].iloc[0] == date(2026, 11, 3)


def test_generated_production_report_passes_checks(tmp_path):
    # mirror what the generator produces, minimally
    raw = pd.DataFrame([
        {"date": date(2026, 11, 3), "field": "Sarsang", "well": "SAR-01",
         "oil_rate_bbl": 100.0},
        {"date": date(2026, 11, 3), "field": "Sarsang", "well": "FACILITY_TOTAL",
         "oil_rate_bbl": 100.0, "facility_inlet_bbl": 100.0,
         "facility_outlet_bbl": 99.0, "export_bbl": 95.0},
    ])
    path = _write(tmp_path, "production_Sarsang_2026-11-03.xlsx", raw)
    report = parse_filename(path.name)
    df = read_report(path, report)
    findings = v.run_all_checks("production", df)
    assert not v.has_errors(findings)
