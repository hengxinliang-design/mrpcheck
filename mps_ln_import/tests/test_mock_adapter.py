from mps_ln_import.adapters.ln_mock import MockLNAdapter
from .conftest import make_plan_row


def test_datacheck_empty_item_fails(cfg):
    ln = MockLNAdapter(cfg)
    res = ln.datacheck(make_plan_row(5, item=""), "ACT")
    assert not res.ok
    assert "datacheck" in res.message


def test_datacheck_normalizes_item_uppercase(cfg):
    ln = MockLNAdapter(cfg)
    res = ln.datacheck(make_plan_row(5, item="a04-x"), "ACT")
    assert res.ok
    assert res.value == "A04-X"


def test_import_fail_rows(cfg):
    cfg["ln"]["mock"]["fail_rows"] = [6]
    ln = MockLNAdapter(cfg)
    assert ln.import_plan(make_plan_row(5), "ACT").ok
    assert not ln.import_plan(make_plan_row(6), "ACT").ok


def test_import_negative_period_fails(cfg):
    ln = MockLNAdapter(cfg)
    periods = ["0"] * 21
    periods[2] = "-5"
    res = ln.import_plan(make_plan_row(5, periods=periods), "ACT")
    assert not res.ok
    assert "第3周期" in res.message


def test_get_master_data_toggle(cfg):
    cfg["ln"]["mock"]["fetch_master"] = True
    ln = MockLNAdapter(cfg)
    row = make_plan_row(5)
    row.master["sfst"] = "原值"
    assert ln.get_master_data(row, "ACT", "sfst").value == "<LN:sfst>"

    cfg["ln"]["mock"]["fetch_master"] = False
    ln2 = MockLNAdapter(cfg)
    assert ln2.get_master_data(row, "ACT", "sfst").value == "原值"


def test_run_plan_ok(cfg):
    assert MockLNAdapter(cfg).run_plan("ACT").ok
