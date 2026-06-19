from mps_ln_import.adapters.ln_mock import MockLNAdapter
from mps_ln_import.core.importer import Importer
from .conftest import make_plan_row


def test_importer_end_to_end(cfg):
    cfg["ln"]["mock"]["fail_rows"] = [6]
    rows = [
        make_plan_row(5, item="a04-x"),                       # 成功 + 物料规范化
        make_plan_row(6, item="b01"),                         # mock 强制失败
        make_plan_row(7, factory="", item=""),                # 本地校验失败
    ]
    summary = Importer(cfg, MockLNAdapter(cfg)).run("ACT", rows)

    assert summary.total == 3
    assert summary.ok_count == 1
    assert summary.fail_count == 2
    assert set(summary.fail_rows) == {6, 7}
    assert summary.plan_run_ok is True


def test_importer_normalizes_item(cfg):
    rows = [make_plan_row(5, item="a04-x")]
    Importer(cfg, MockLNAdapter(cfg)).run("ACT", rows)
    assert rows[0].item == "A04-X"
    assert rows[0].ok


def test_importer_local_validation_skips_ln(cfg):
    rows = [make_plan_row(5, factory="", item="")]
    Importer(cfg, MockLNAdapter(cfg)).run("ACT", rows)
    assert not rows[0].ok
    assert "本地校验失败" in rows[0].message


def test_importer_fetches_only_ln_master_fields(cfg):
    cfg["ln"]["mock"]["fetch_master"] = True
    rows = [make_plan_row(5, item="a04-x")]
    Importer(cfg, MockLNAdapter(cfg)).run("ACT", rows)
    # source=ln 的字段被带出, source=manual 的(mode/cqty/mqty)不应被覆盖
    assert rows[0].master["sfst"] == "<LN:sfst>"   # ln
    assert "mode" not in rows[0].master            # manual, 未取
