"""Application service for batch creation and processing."""
from __future__ import annotations

import copy
import shutil
from pathlib import Path

from ..adapters.excel_reader import ExcelReader
from ..adapters.ln_base import LNAdapter
from ..adapters.ln_mock import MockLNAdapter
from ..adapters.ln_odata import ODataLNAdapter
from .processor import BatchProcessor
from .storage import SQLiteStore, new_id


def build_ln_adapter(cfg: dict) -> LNAdapter:
    name = cfg["ln"]["adapter"]
    if name == "mock":
        return MockLNAdapter(cfg)
    if name == "odata":
        return ODataLNAdapter(cfg)
    raise ValueError(f"未知 ln.adapter: {name}")


class MPSImportService:
    def __init__(self, cfg: dict, store: SQLiteStore, upload_dir: str | Path):
        self.cfg = cfg
        self.store = store
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def create_batch_from_excel(self, source_path: str | Path, source_file_name: str | None = None):
        source_path = Path(source_path)
        display_name = source_file_name or source_path.name
        stored_name = f"{new_id('upload')}_{display_name}"
        stored_path = self.upload_dir / stored_name
        shutil.copy2(source_path, stored_path)

        cfg = copy.deepcopy(self.cfg)
        cfg["excel"]["path"] = str(stored_path)
        method, rows = ExcelReader(cfg).read()
        return self.store.create_batch(method, display_name, str(stored_path), rows)

    def validate_batch(self, batch_id: str):
        processor = BatchProcessor(self.cfg, self.store, build_ln_adapter(self.cfg))
        return processor.validate_batch(batch_id)

    def import_batch(self, batch_id: str, failed_rows_only: bool = False):
        processor = BatchProcessor(self.cfg, self.store, build_ln_adapter(self.cfg))
        return processor.import_batch(batch_id, failed_rows_only=failed_rows_only)
