"""编排: 读 -> 本地校验 -> datacheck -> 取主数据 -> 导入 -> 收集结果 -> 末尾 run.plan。

对应原 VBA: DataCheck_Click + UpdateForecast_Click 的合并流程, 但分层清晰、可测、有汇总。
"""
from __future__ import annotations

import logging

from ..adapters.ln_base import LNAdapter
from .models import PlanRow, RunSummary
from .validator import validate_local

log = logging.getLogger(__name__)


class Importer:
    def __init__(self, cfg: dict, ln: LNAdapter):
        self.cfg = cfg
        self.ln = ln
        self.period_count = cfg["columns"]["periods"]["count"]
        # 哪些 master 字段从 LN 带出(source=ln), 哪些手工保留
        self.ln_fields = [
            name for name, spec in cfg["columns"]["master"].items()
            if spec.get("source") == "ln"
        ]

    def run(self, method: str, rows: list[PlanRow]) -> RunSummary:
        summary = RunSummary(method=method)

        with self.ln:
            for row in rows:
                self._process_row(row, method)
                summary.add(row)

            res = self.ln.run_plan(method)
            summary.plan_run_ok = res.ok
            summary.plan_run_message = res.message

        log.info("\n%s", summary.text())
        return summary

    # ------------------------------------------------------------------
    def _process_row(self, row: PlanRow, method: str) -> None:
        # 1) 本地预校验
        local_errors = validate_local(row, self.period_count)
        if local_errors:
            row.ok = False
            row.message = "本地校验失败: " + "; ".join(local_errors)
            return

        # 2) LN datacheck(可能规范化物料编码)
        chk = self.ln.datacheck(row, method)
        if not chk.ok:
            row.ok = False
            row.message = chk.message
            return
        if chk.value and chk.value != row.item:
            log.info("行%d 物料规范化: %s -> %s", row.row_index, row.item, chk.value)
            row.item = chk.value

        # 3) 取主数据(原 get.data, source=ln 的字段)
        for fname in self.ln_fields:
            got = self.ln.get_master_data(row, method, fname)
            if got.ok:
                row.master[fname] = got.value

        # 4) 导入计划量
        imp = self.ln.import_plan(row, method)
        row.ok = imp.ok
        row.message = imp.message if imp.message else ("ok" if imp.ok else "import失败")
