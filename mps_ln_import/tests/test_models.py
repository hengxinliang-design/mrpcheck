from mps_ln_import.core.models import PlanRow, RunSummary
from .conftest import make_plan_row


def test_biz_key():
    row = make_plan_row(5, factory="PG3", item="A1", customer="Q1", customer_item="K1")
    assert row.biz_key == "PG3|A1|Q1|K1"


def test_is_blank():
    assert make_plan_row(5, factory="", item="", customer="", customer_item="").is_blank()
    assert not make_plan_row(5).is_blank()


def test_run_summary_counts_and_text():
    s = RunSummary(method="ACT")
    ok = make_plan_row(5); ok.ok = True
    bad = make_plan_row(6); bad.ok = False
    s.add(ok)
    s.add(bad)
    s.plan_run_ok = True
    s.plan_run_message = "已触发"

    assert s.total == 2
    assert s.ok_count == 1
    assert s.fail_count == 1
    assert s.fail_rows == [6]

    text = s.text()
    assert "成功: 1 行" in text
    assert "失败行号: 6" in text
    assert "run.plan: OK" in text
