"""SQLite persistence for service-mode batches, rows, and jobs.

The storage layer is intentionally small and dependency-free so the first web
prototype can run locally before a PostgreSQL/queue deployment is introduced.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from ..core.models import PlanRow


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class BatchRecord:
    id: str
    method: str
    status: str
    source_file_name: str
    source_file_path: str
    total_rows: int
    ok_rows: int
    failed_rows: int
    created_at: str
    updated_at: str


@dataclass
class RowRecord:
    id: str
    batch_id: str
    excel_row_no: int
    factory: str
    item: str
    customer: str
    customer_item: str
    master: dict[str, str]
    periods: list[str]
    status: str
    message: str
    normalized_item: str


@dataclass
class JobRecord:
    id: str
    batch_id: str
    type: str
    status: str
    progress_total: int
    progress_done: int
    message: str
    started_at: str
    finished_at: str


class SQLiteStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA foreign_keys = ON")
            yield con
            con.commit()
        finally:
            con.close()

    def init_schema(self) -> None:
        with self.connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS mps_import_batch (
                    id TEXT PRIMARY KEY,
                    method TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_file_name TEXT NOT NULL,
                    source_file_path TEXT NOT NULL,
                    total_rows INTEGER NOT NULL DEFAULT 0,
                    ok_rows INTEGER NOT NULL DEFAULT 0,
                    failed_rows INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mps_import_row (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL REFERENCES mps_import_batch(id) ON DELETE CASCADE,
                    excel_row_no INTEGER NOT NULL,
                    factory TEXT NOT NULL DEFAULT '',
                    item TEXT NOT NULL DEFAULT '',
                    customer TEXT NOT NULL DEFAULT '',
                    customer_item TEXT NOT NULL DEFAULT '',
                    master_json TEXT NOT NULL DEFAULT '{}',
                    periods_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    normalized_item TEXT NOT NULL DEFAULT '',
                    last_checked_at TEXT NOT NULL DEFAULT '',
                    last_imported_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS mps_import_job (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL REFERENCES mps_import_batch(id) ON DELETE CASCADE,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress_total INTEGER NOT NULL DEFAULT 0,
                    progress_done INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL DEFAULT '',
                    finished_at TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_mps_rows_batch ON mps_import_row(batch_id);
                CREATE INDEX IF NOT EXISTS idx_mps_jobs_batch ON mps_import_job(batch_id);
                """
            )

    def create_batch(self, method: str, source_file_name: str, source_file_path: str, rows: list[PlanRow]) -> BatchRecord:
        batch_id = new_id("bat")
        now = utc_now()
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO mps_import_batch
                    (id, method, status, source_file_name, source_file_path, total_rows, created_at, updated_at)
                VALUES (?, ?, 'draft', ?, ?, ?, ?, ?)
                """,
                (batch_id, method, source_file_name, source_file_path, len(rows), now, now),
            )
            for row in rows:
                con.execute(
                    """
                    INSERT INTO mps_import_row
                        (id, batch_id, excel_row_no, factory, item, customer, customer_item,
                         master_json, periods_json, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')
                    """,
                    (
                        new_id("row"),
                        batch_id,
                        row.row_index,
                        row.factory,
                        row.item,
                        row.customer,
                        row.customer_item,
                        json.dumps(row.master, ensure_ascii=False),
                        json.dumps(row.periods, ensure_ascii=False),
                    ),
                )
        return self.get_batch(batch_id)

    def list_batches(self) -> list[BatchRecord]:
        with self.connect() as con:
            rows = con.execute("SELECT * FROM mps_import_batch ORDER BY created_at DESC").fetchall()
        return [self._batch(r) for r in rows]

    def get_batch(self, batch_id: str) -> BatchRecord:
        with self.connect() as con:
            row = con.execute("SELECT * FROM mps_import_batch WHERE id = ?", (batch_id,)).fetchone()
        if row is None:
            raise KeyError(f"batch not found: {batch_id}")
        return self._batch(row)

    def update_batch_status(self, batch_id: str, status: str) -> None:
        with self.connect() as con:
            con.execute(
                "UPDATE mps_import_batch SET status = ?, updated_at = ? WHERE id = ?",
                (status, utc_now(), batch_id),
            )

    def refresh_batch_counts(self, batch_id: str) -> None:
        with self.connect() as con:
            counts = con.execute(
                """
                SELECT
                    SUM(CASE WHEN status IN ('validated', 'imported') THEN 1 ELSE 0 END) AS ok_rows,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_rows
                FROM mps_import_row
                WHERE batch_id = ?
                """,
                (batch_id,),
            ).fetchone()
            con.execute(
                """
                UPDATE mps_import_batch
                SET ok_rows = ?, failed_rows = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(counts["ok_rows"] or 0), int(counts["failed_rows"] or 0), utc_now(), batch_id),
            )

    def list_rows(self, batch_id: str, only_status: str | None = None) -> list[RowRecord]:
        sql = "SELECT * FROM mps_import_row WHERE batch_id = ?"
        params: tuple[str, ...] = (batch_id,)
        if only_status:
            sql += " AND status = ?"
            params = (batch_id, only_status)
        sql += " ORDER BY excel_row_no"
        with self.connect() as con:
            rows = con.execute(sql, params).fetchall()
        return [self._row(r) for r in rows]

    def update_row_from_plan(self, row_id: str, row: PlanRow, status: str, checked: bool = False, imported: bool = False) -> None:
        with self.connect() as con:
            con.execute(
                """
                UPDATE mps_import_row
                SET item = ?, master_json = ?, periods_json = ?, status = ?, message = ?,
                    normalized_item = ?, last_checked_at = CASE WHEN ? THEN ? ELSE last_checked_at END,
                    last_imported_at = CASE WHEN ? THEN ? ELSE last_imported_at END
                WHERE id = ?
                """,
                (
                    row.item,
                    json.dumps(row.master, ensure_ascii=False),
                    json.dumps(row.periods, ensure_ascii=False),
                    status,
                    row.message,
                    row.item,
                    1 if checked else 0,
                    utc_now(),
                    1 if imported else 0,
                    utc_now(),
                    row_id,
                ),
            )

    def create_job(self, batch_id: str, job_type: str, total: int) -> JobRecord:
        job_id = new_id("job")
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO mps_import_job
                    (id, batch_id, type, status, progress_total, progress_done, started_at)
                VALUES (?, ?, ?, 'running', ?, 0, ?)
                """,
                (job_id, batch_id, job_type, total, utc_now()),
            )
        return self.get_job(job_id)

    def update_job(self, job_id: str, status: str, done: int, message: str = "") -> None:
        finished_at = utc_now() if status in {"succeeded", "failed", "canceled"} else ""
        with self.connect() as con:
            con.execute(
                """
                UPDATE mps_import_job
                SET status = ?, progress_done = ?, message = ?,
                    finished_at = CASE WHEN ? != '' THEN ? ELSE finished_at END
                WHERE id = ?
                """,
                (status, done, message, finished_at, finished_at, job_id),
            )

    def get_job(self, job_id: str) -> JobRecord:
        with self.connect() as con:
            row = con.execute("SELECT * FROM mps_import_job WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"job not found: {job_id}")
        return self._job(row)

    def list_jobs(self, batch_id: str) -> list[JobRecord]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM mps_import_job WHERE batch_id = ? ORDER BY started_at DESC",
                (batch_id,),
            ).fetchall()
        return [self._job(r) for r in rows]

    @staticmethod
    def row_to_plan(record: RowRecord) -> PlanRow:
        return PlanRow(
            row_index=record.excel_row_no,
            factory=record.factory,
            item=record.item,
            customer=record.customer,
            customer_item=record.customer_item,
            master=dict(record.master),
            periods=list(record.periods),
        )

    @staticmethod
    def _batch(row: sqlite3.Row) -> BatchRecord:
        return BatchRecord(**dict(row))

    @staticmethod
    def _row(row: sqlite3.Row) -> RowRecord:
        d = dict(row)
        return RowRecord(
            id=d["id"],
            batch_id=d["batch_id"],
            excel_row_no=d["excel_row_no"],
            factory=d["factory"],
            item=d["item"],
            customer=d["customer"],
            customer_item=d["customer_item"],
            master=json.loads(d["master_json"] or "{}"),
            periods=json.loads(d["periods_json"] or "[]"),
            status=d["status"],
            message=d["message"],
            normalized_item=d["normalized_item"],
        )

    @staticmethod
    def _job(row: sqlite3.Row) -> JobRecord:
        return JobRecord(**dict(row))

