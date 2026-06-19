"""Mock LN 适配器: 本地模拟, 让整条流水线在无 LN 环境下跑通。

模拟规则(可在 config.ln.mock 调整):
- datacheck: 工厂或物料为空 -> 失败; 否则成功, 物料编码统一转大写当作"规范化"。
- get_master_data: 回显一个带 <LN:字段> 前缀的占位值, 证明回填链路通。
- import_plan: 行号在 fail_rows 中, 或任一周期量为负 -> 失败; 否则成功。
- run_plan: 总是成功。
"""
from __future__ import annotations

import logging

from ..core.models import PlanRow
from .ln_base import CallResult, LNAdapter

log = logging.getLogger(__name__)


class MockLNAdapter(LNAdapter):
    def __init__(self, cfg: dict):
        mock = cfg["ln"].get("mock", {})
        self.fetch_master = bool(mock.get("fetch_master", True))
        self.fail_rows = set(mock.get("fail_rows") or [])

    def open(self) -> None:
        log.info("[mock] 连接 LN (模拟)")

    def close(self) -> None:
        log.info("[mock] 断开 LN (模拟)")

    def datacheck(self, row: PlanRow, method: str) -> CallResult:
        if not row.factory or not row.item:
            return CallResult(ok=False, message="datacheck失败: 工厂/物料不能为空")
        return CallResult(ok=True, value=row.item.upper())

    def get_master_data(self, row: PlanRow, method: str, field_name: str) -> CallResult:
        if not self.fetch_master:
            return CallResult(ok=True, value=row.master.get(field_name, ""))
        return CallResult(ok=True, value=f"<LN:{field_name}>")

    def import_plan(self, row: PlanRow, method: str) -> CallResult:
        if row.row_index in self.fail_rows:
            return CallResult(ok=False, message="import失败: (mock强制失败)")
        for i, p in enumerate(row.periods, start=1):
            if p and _to_float(p) < 0:
                return CallResult(ok=False, message=f"import失败: 第{i}周期计划量为负({p})")
        return CallResult(ok=True, message="ok")

    def run_plan(self, method: str) -> CallResult:
        log.info("[mock] run.plan(%s) (模拟)", method)
        return CallResult(ok=True, message="计划运算已触发(模拟)")


def _to_float(s: str) -> float:
    try:
        return float(s)
    except ValueError:
        return 0.0
