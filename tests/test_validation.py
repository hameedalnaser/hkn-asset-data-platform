import pandas as pd
import pytest

from hkn_asset.domain import validation as v
from hkn_asset.domain.reports import SPECS


# ----------------------------- structural ----------------------------- #
def test_missing_required_column_is_error():
    df = pd.DataFrame({"date": ["2026-11-03"], "field": ["Sarsang"]})  # no well/oil
    findings = v.validate_structure(df, SPECS["production"])
    assert v.has_errors(findings)
    assert any(f.code == "MISSING_COLUMNS" for f in findings)


def test_empty_frame_is_error():
    df = pd.DataFrame(columns=["date", "field", "well", "oil_rate_bbl"])
    findings = v.validate_structure(df, SPECS["production"])
    assert any(f.code == "EMPTY" for f in findings)


def test_negative_rate_is_error():
    df = pd.DataFrame({
        "date": ["2026-11-03"], "field": ["Sarsang"], "well": ["SAR-01"],
        "oil_rate_bbl": [-10.0],
    })
    findings = v.validate_structure(df, SPECS["production"])
    assert any(f.code == "NEGATIVE_VALUE" for f in findings)


def test_clean_frame_has_no_errors():
    df = pd.DataFrame({
        "date": ["2026-11-03"], "field": ["Sarsang"], "well": ["SAR-01"],
        "oil_rate_bbl": [100.0],
    })
    findings = v.validate_structure(df, SPECS["production"])
    assert not v.has_errors(findings)


# --------------------------- reconciliation ---------------------------- #
def _prod_frame(export, outlet, inlet, well_oil):
    return pd.DataFrame([
        {"well": "SAR-01", "oil_rate_bbl": well_oil},
        {"well": "FACILITY_TOTAL", "oil_rate_bbl": inlet,
         "facility_inlet_bbl": inlet, "facility_outlet_bbl": outlet,
         "export_bbl": export},
    ])


def test_reconcile_ok_when_consistent():
    df = _prod_frame(export=95, outlet=100, inlet=100, well_oil=100)
    assert v.reconcile_production(df) == []


def test_reconcile_flags_export_over_outlet():
    df = _prod_frame(export=150, outlet=100, inlet=100, well_oil=100)
    codes = [f.code for f in v.reconcile_production(df)]
    assert "EXPORT_GT_OUTLET" in codes


def test_reconcile_flags_well_sum_mismatch():
    df = _prod_frame(export=95, outlet=100, inlet=100, well_oil=50)
    codes = [f.code for f in v.reconcile_production(df)]
    assert "WELL_SUM_MISMATCH" in codes


def test_reconcile_findings_are_warnings_not_errors():
    df = _prod_frame(export=150, outlet=100, inlet=100, well_oil=100)
    findings = v.reconcile_production(df)
    assert findings and not v.has_errors(findings)  # warnings don't block load


def test_power_load_over_capacity_flagged():
    df = pd.DataFrame({"capacity_mw": [5.0], "avg_load_mw": [7.0], "hours_run": [20]})
    codes = [f.code for f in v.reconcile_power(df)]
    assert "LOAD_GT_CAPACITY" in codes


def test_power_hours_out_of_range_flagged():
    df = pd.DataFrame({"capacity_mw": [5.0], "avg_load_mw": [3.0], "hours_run": [30]})
    codes = [f.code for f in v.reconcile_power(df)]
    assert "HOURS_OUT_OF_RANGE" in codes


@pytest.mark.parametrize("hours,expect", [(5, False), (30, True), (-2, True)])
def test_deferment_downtime_range(hours, expect):
    df = pd.DataFrame({"downtime_hours": [hours], "deferred_bbl": [100]})
    codes = [f.code for f in v.reconcile_deferment(df)]
    assert ("DOWNTIME_OUT_OF_RANGE" in codes) is expect
