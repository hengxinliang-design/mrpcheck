from mps_ln_import.core.validator import validate_local
from .conftest import make_plan_row


def test_valid_row_passes():
    row = make_plan_row(5, periods=["0"] * 21)
    assert validate_local(row, 21) == []


def test_missing_factory_and_item():
    row = make_plan_row(5, factory="", item="", periods=["0"] * 21)
    errs = validate_local(row, 21)
    assert "工厂为空" in errs
    assert "物料编码为空" in errs


def test_wrong_period_count():
    row = make_plan_row(5, periods=["0"] * 20)
    errs = validate_local(row, 21)
    assert any("周期列数" in e for e in errs)


def test_non_numeric_period():
    periods = ["0"] * 21
    periods[3] = "abc"
    row = make_plan_row(5, periods=periods)
    errs = validate_local(row, 21)
    assert any("第4周期" in e for e in errs)


def test_blank_periods_allowed():
    periods = [""] * 21
    row = make_plan_row(5, periods=periods)
    assert validate_local(row, 21) == []
