"""本地预校验: 在调用 LN 之前先挡掉明显错误, 减少无谓往返。"""
from __future__ import annotations

from .models import PlanRow


def validate_local(row: PlanRow, period_count: int) -> list[str]:
    """返回错误描述列表; 空列表表示通过。"""
    errors: list[str] = []

    if not row.factory:
        errors.append("工厂为空")
    if not row.item:
        errors.append("物料编码为空")

    if len(row.periods) != period_count:
        errors.append(f"周期列数={len(row.periods)}, 期望{period_count}")

    for i, p in enumerate(row.periods, start=1):
        if p == "":
            continue
        try:
            float(p)
        except ValueError:
            errors.append(f"第{i}周期计划量非数值: {p!r}")

    return errors
