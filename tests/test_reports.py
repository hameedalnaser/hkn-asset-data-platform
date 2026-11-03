from datetime import date

from hkn_asset.domain.reports import parse_filename


def test_parse_valid_filename():
    r = parse_filename("production_Sarsang_2026-11-03.xlsx")
    assert r is not None
    assert r.report_type == "production"
    assert r.field_name == "Sarsang"
    assert r.report_date == date(2026, 11, 3)


def test_parse_each_report_type():
    for rt in ("production", "deferment", "power", "maintenance"):
        r = parse_filename(f"{rt}_Atrush_2026-01-15.xlsx")
        assert r is not None and r.report_type == rt


def test_parse_rejects_unknown_type():
    assert parse_filename("costs_Sarsang_2026-11-03.xlsx") is None


def test_parse_rejects_bad_date():
    assert parse_filename("production_Sarsang_03-11-2026.xlsx") is None


def test_parse_rejects_non_xlsx():
    assert parse_filename("production_Sarsang_2026-11-03.csv") is None
