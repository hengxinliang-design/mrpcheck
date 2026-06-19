from mps_ln_import.service.service import MPSImportService
from mps_ln_import.service.storage import SQLiteStore

from .conftest import build_workbook


def test_service_batch_validate_import_flow(cfg, tmp_path):
    cfg["service"] = {
        "db_path": str(tmp_path / "svc.sqlite3"),
        "upload_dir": str(tmp_path / "uploads"),
    }
    cfg["ln"]["mock"]["fail_rows"] = [6]
    build_workbook(
        cfg,
        [
            {
                "factory": "PG3",
                "item": "a04-x",
                "customer": "Q1",
                "customer_item": "K1",
                "periods": ["0"] * 21,
            },
            {
                "factory": "PG3",
                "item": "b01",
                "customer": "Q2",
                "customer_item": "K2",
                "periods": ["1"] * 21,
            },
        ],
    )

    store = SQLiteStore(cfg["service"]["db_path"])
    service = MPSImportService(cfg, store, cfg["service"]["upload_dir"])

    batch = service.create_batch_from_excel(cfg["excel"]["path"])
    assert batch.method == "ACT"
    assert batch.status == "draft"
    assert batch.total_rows == 2

    validate_job = service.validate_batch(batch.id)
    assert validate_job.status == "succeeded"
    validated_rows = store.list_rows(batch.id)
    assert [r.status for r in validated_rows] == ["validated", "validated"]
    assert validated_rows[0].item == "A04-X"
    assert validated_rows[0].master["sfst"] == "<LN:sfst>"

    import_job = service.import_batch(batch.id)
    assert import_job.status == "succeeded"
    imported_rows = store.list_rows(batch.id)
    assert imported_rows[0].status == "imported"
    assert imported_rows[0].message == "ok"
    assert imported_rows[1].status == "failed"
    assert "mock强制失败" in imported_rows[1].message

    refreshed = store.get_batch(batch.id)
    assert refreshed.status == "completed_with_errors"
    assert refreshed.failed_rows == 1


def test_service_validation_failure_is_persisted(cfg, tmp_path):
    cfg["service"] = {
        "db_path": str(tmp_path / "svc.sqlite3"),
        "upload_dir": str(tmp_path / "uploads"),
    }
    build_workbook(
        cfg,
        [
            {
                "factory": "",
                "item": "",
                "customer": "Q1",
                "customer_item": "K1",
                "periods": ["0"] * 21,
            },
        ],
    )

    store = SQLiteStore(cfg["service"]["db_path"])
    service = MPSImportService(cfg, store, cfg["service"]["upload_dir"])
    batch = service.create_batch_from_excel(cfg["excel"]["path"])

    service.validate_batch(batch.id)
    rows = store.list_rows(batch.id)
    assert rows[0].status == "failed"
    assert "本地校验失败" in rows[0].message
    assert store.get_batch(batch.id).status == "validation_failed"

