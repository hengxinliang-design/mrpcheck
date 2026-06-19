"""Batch processors for validation and import jobs."""
from __future__ import annotations

from ..adapters.ln_base import LNAdapter
from ..core.validator import validate_local
from .storage import SQLiteStore


class BatchProcessor:
    def __init__(self, cfg: dict, store: SQLiteStore, ln: LNAdapter):
        self.cfg = cfg
        self.store = store
        self.ln = ln
        self.period_count = cfg["columns"]["periods"]["count"]
        self.ln_fields = [
            name for name, spec in cfg["columns"]["master"].items()
            if spec.get("source") == "ln"
        ]

    def validate_batch(self, batch_id: str):
        batch = self.store.get_batch(batch_id)
        records = self.store.list_rows(batch_id)
        job = self.store.create_job(batch_id, "validate", len(records))
        done = 0

        self.store.update_batch_status(batch_id, "validating")
        try:
            with self.ln:
                for record in records:
                    row = self.store.row_to_plan(record)
                    errors = validate_local(row, self.period_count)
                    if errors:
                        row.ok = False
                        row.message = "本地校验失败: " + "; ".join(errors)
                        status = "failed"
                    else:
                        chk = self.ln.datacheck(row, batch.method)
                        if not chk.ok:
                            row.ok = False
                            row.message = chk.message
                            status = "failed"
                        else:
                            if chk.value:
                                row.item = chk.value
                            for field_name in self.ln_fields:
                                got = self.ln.get_master_data(row, batch.method, field_name)
                                if got.ok:
                                    row.master[field_name] = got.value
                            row.ok = True
                            row.message = "validated"
                            status = "validated"

                    self.store.update_row_from_plan(record.id, row, status, checked=True)
                    done += 1
                    self.store.update_job(job.id, "running", done, f"已校验 {done}/{len(records)} 行")

            self.store.refresh_batch_counts(batch_id)
            failed = len([r for r in self.store.list_rows(batch_id) if r.status == "failed"])
            self.store.update_batch_status(batch_id, "validation_failed" if failed else "validated")
            self.store.update_job(job.id, "succeeded", done, "校验完成")
        except Exception as exc:
            self.store.update_batch_status(batch_id, "failed")
            self.store.update_job(job.id, "failed", done, str(exc))
            raise

        return self.store.get_job(job.id)

    def import_batch(self, batch_id: str, failed_rows_only: bool = False):
        batch = self.store.get_batch(batch_id)
        records = self.store.list_rows(batch_id)
        if failed_rows_only:
            records = [r for r in records if r.status == "failed"]
        else:
            records = [r for r in records if r.status in {"validated", "failed"}]
        job = self.store.create_job(batch_id, "import", len(records))
        done = 0

        self.store.update_batch_status(batch_id, "importing")
        try:
            with self.ln:
                for record in records:
                    row = self.store.row_to_plan(record)
                    errors = validate_local(row, self.period_count)
                    if errors:
                        row.ok = False
                        row.message = "本地校验失败: " + "; ".join(errors)
                        status = "failed"
                    else:
                        imp = self.ln.import_plan(row, batch.method)
                        row.ok = imp.ok
                        row.message = imp.message if imp.message else ("ok" if imp.ok else "import失败")
                        status = "imported" if imp.ok else "failed"
                    self.store.update_row_from_plan(record.id, row, status, imported=True)
                    done += 1
                    self.store.update_job(job.id, "running", done, f"已导入 {done}/{len(records)} 行")

                plan = self.ln.run_plan(batch.method)

            self.store.refresh_batch_counts(batch_id)
            failed = len([r for r in self.store.list_rows(batch_id) if r.status == "failed"])
            self.store.update_batch_status(batch_id, "completed_with_errors" if failed else "completed")
            self.store.update_job(job.id, "succeeded", done, f"导入完成; run.plan: {plan.message}")
        except Exception as exc:
            self.store.update_batch_status(batch_id, "failed")
            self.store.update_job(job.id, "failed", done, str(exc))
            raise

        return self.store.get_job(job.id)

