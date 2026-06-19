"""数据模型: 一行主计划 = 一个 PlanRow。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlanRow:
    row_index: int                       # Excel 行号(从 first_data_row 起)
    factory: str
    item: str
    customer: str
    customer_item: str
    master: dict[str, str] = field(default_factory=dict)   # 13个主数据字段 {逻辑名: 值}
    periods: list[str] = field(default_factory=list)        # 21个周期计划量(字符串, 与原VBA一致)

    # --- 处理结果 ---
    ok: bool = False
    message: str = ""

    @property
    def biz_key(self) -> str:
        """业务幂等键, 用于 guid 生成与去重(对应技能 §7.1)。"""
        return "|".join([self.factory, self.item, self.customer, self.customer_item])

    def is_blank(self) -> bool:
        """整行是否为空(无主键), 用于跳过尾部空行。"""
        return not any([self.factory, self.item, self.customer, self.customer_item])


@dataclass
class RunSummary:
    method: str
    total: int = 0
    ok_count: int = 0
    fail_count: int = 0
    fail_rows: list[int] = field(default_factory=list)
    plan_run_ok: Optional[bool] = None
    plan_run_message: str = ""

    def add(self, row: PlanRow) -> None:
        self.total += 1
        if row.ok:
            self.ok_count += 1
        else:
            self.fail_count += 1
            self.fail_rows.append(row.row_index)

    def text(self) -> str:
        lines = [
            f"导入完成 (方案: {self.method})",
            f"成功: {self.ok_count} 行 / 失败: {self.fail_count} 行 / 共 {self.total} 行",
        ]
        if self.fail_rows:
            lines.append("失败行号: " + " ".join(str(r) for r in self.fail_rows))
        if self.plan_run_ok is not None:
            lines.append(f"run.plan: {'OK' if self.plan_run_ok else '失败'} {self.plan_run_message}".strip())
        return "\n".join(lines)
