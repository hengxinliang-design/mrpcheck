import yaml
from fastapi.testclient import TestClient

from mps_ln_import.service.api import create_app


def test_reserved_erp_test_endpoints_are_disabled_by_default(base_cfg, tmp_path):
    base_cfg["service"] = {
        "db_path": str(tmp_path / "svc.sqlite3"),
        "upload_dir": str(tmp_path / "uploads"),
    }
    base_cfg["erp_api"] = {
        "enabled": False,
        "base_url": "https://<ERP_API_HOST>",
        "endpoints": {
            "datacheck": "/api/mps/datacheck",
            "master_data": "/api/mps/master-data",
            "import_plan": "/api/mps/import-plan",
            "run_plan": "/api/mps/run-plan",
        },
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(base_cfg, allow_unicode=True), encoding="utf-8")

    client = TestClient(create_app(str(config_path)))

    status = client.get("/api/erp-test/status")
    assert status.status_code == 200
    assert status.json()["enabled"] is False
    assert status.json()["message"] == "reserved"

    for path in [
        "/api/erp-test/datacheck",
        "/api/erp-test/master-data",
        "/api/erp-test/import-plan",
        "/api/erp-test/run-plan",
    ]:
        res = client.post(path, json={})
        assert res.status_code == 501
        assert "reserved but not enabled" in res.json()["detail"]

