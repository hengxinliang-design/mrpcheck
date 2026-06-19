"""LN 适配器接口。上层 importer 只依赖这个抽象, 换实现不动业务流程。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..core.models import PlanRow


@dataclass
class CallResult:
    ok: bool
    message: str = ""
    value: str = ""        # 单值返回(如 get.data / datacheck 规范化后的物料)


class LNAdapter(ABC):
    """对应原 4GL 的 4 个入口。"""

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def datacheck(self, row: PlanRow, method: str) -> CallResult:
        """校验主键。ok=True 时 value 为规范化后的物料编码(可能与输入不同)。"""

    @abstractmethod
    def get_master_data(self, row: PlanRow, method: str, field_name: str) -> CallResult:
        """取单个主数据字段(原 get.data, 现可走 OData GET)。"""

    @abstractmethod
    def import_plan(self, row: PlanRow, method: str) -> CallResult:
        """导入 17 主数据 + 21 周期量(原 cprrp.production.plan.quantity.import)。"""

    @abstractmethod
    def run_plan(self, method: str) -> CallResult:
        """触发计划运算(原 run.plan), 整批末执行一次。"""

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()
