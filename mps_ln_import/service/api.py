"""FastAPI entrypoint for the MPS LN import service."""
from __future__ import annotations

import copy
import tempfile
from pathlib import Path

import yaml

try:
    from fastapi import FastAPI, File, HTTPException, UploadFile
except ImportError as exc:  # pragma: no cover - exercised only without API deps
    raise RuntimeError(
        "FastAPI dependencies are not installed. Run: "
        "pip install -r mps_ln_import/requirements.txt"
    ) from exc

from .service import MPSImportService
from .erp_test import ERPTestClient, ERPTestClientNotConfigured
from .storage import SQLiteStore


def load_config(config_path: str = "mps_ln_import/config.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg = copy.deepcopy(cfg)
    cfg.setdefault("service", {})
    cfg["service"].setdefault("db_path", "mps_ln_import/data/mps_import.sqlite3")
    cfg["service"].setdefault("upload_dir", "mps_ln_import/data/uploads")
    cfg.setdefault("erp_api", {})
    cfg["erp_api"].setdefault("enabled", False)
    return cfg


def create_app(config_path: str = "mps_ln_import/config.yaml") -> FastAPI:
    cfg = load_config(config_path)
    store = SQLiteStore(cfg["service"]["db_path"])
    svc = MPSImportService(cfg, store, cfg["service"]["upload_dir"])
    erp_test = ERPTestClient(cfg)
    app = FastAPI(title="MPS LN Import Service", version="0.1.0")

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/api/mps-batches")
    def list_batches():
        return [b.__dict__ for b in store.list_batches()]

    @app.get("/api/mps-batches/{batch_id}")
    def get_batch(batch_id: str):
        try:
            batch = store.get_batch(batch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return batch.__dict__

    @app.get("/api/mps-batches/{batch_id}/rows")
    def get_rows(batch_id: str, status: str | None = None):
        try:
            store.get_batch(batch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return [r.__dict__ for r in store.list_rows(batch_id, only_status=status)]

    @app.post("/api/mps-batches/upload")
    async def upload_batch(file: UploadFile = File(...)):
        suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)
        try:
            batch = svc.create_batch_from_excel(tmp_path, source_file_name=file.filename)
        finally:
            tmp_path.unlink(missing_ok=True)
        return batch.__dict__

    @app.post("/api/mps-batches/{batch_id}/validate")
    def validate_batch(batch_id: str):
        try:
            job = svc.validate_batch(batch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return job.__dict__

    @app.post("/api/mps-batches/{batch_id}/import")
    def import_batch(batch_id: str, failed_rows_only: bool = False):
        try:
            job = svc.import_batch(batch_id, failed_rows_only=failed_rows_only)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return job.__dict__

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        try:
            job = store.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return job.__dict__

    @app.get("/api/erp-test/status")
    def erp_test_status():
        settings = cfg.get("erp_api", {})
        return {
            "enabled": bool(settings.get("enabled", False)),
            "baseUrlConfigured": bool(settings.get("base_url")) and "<" not in settings.get("base_url", ""),
            "endpoints": settings.get("endpoints", {}),
            "message": "reserved" if not settings.get("enabled", False) else "enabled",
        }

    @app.post("/api/erp-test/datacheck")
    def erp_test_datacheck(payload: dict):
        return _reserved_call(lambda: erp_test.datacheck(payload))

    @app.post("/api/erp-test/master-data")
    def erp_test_master_data(payload: dict):
        return _reserved_call(lambda: erp_test.master_data(payload))

    @app.post("/api/erp-test/import-plan")
    def erp_test_import_plan(payload: dict):
        return _reserved_call(lambda: erp_test.import_plan(payload))

    @app.post("/api/erp-test/run-plan")
    def erp_test_run_plan(payload: dict):
        return _reserved_call(lambda: erp_test.run_plan(payload))

    return app


def _reserved_call(fn):
    try:
        return fn()
    except ERPTestClientNotConfigured as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


app = create_app()
