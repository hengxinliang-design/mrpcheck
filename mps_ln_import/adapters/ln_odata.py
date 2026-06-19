"""真实 OData 适配器(桩)。

实现思路(对应推荐架构: 中间表 + OData + LN处理进程):
  datacheck/import_plan -> 向中间表实体 POST 一行(crud=I, 带 guid), 然后轮询该行处理结果。
  get_master_data       -> 直接 GET 物料主数据实体(无需中间表)。
  run_plan              -> 由 LN 处理进程在整批末触发, 这里仅发一个收尾标记/或调 ION。

第1期不连真实环境: base_url 仍为占位时, open() 直接报错给出明确提示。
拿到端点和中间表后, 把下面 TODO 填上即可, 上层流程无需改动。
"""
from __future__ import annotations

import hashlib
import logging
import time

from ..core.models import PlanRow
from .ln_base import CallResult, LNAdapter

log = logging.getLogger(__name__)

_PLACEHOLDER = "<LN主机>"


class ODataLNAdapter(LNAdapter):
    def __init__(self, cfg: dict):
        self.o = cfg["ln"]["odata"]
        self.client = None  # httpx.Client

    def open(self) -> None:
        base = self.o.get("base_url", "")
        if _PLACEHOLDER in base or not base:
            raise RuntimeError(
                "OData 端点未配置。请在 config.yaml 的 ln.odata.base_url / auth 填入真实值后再用 --adapter odata。"
                "(第1期请用默认 mock 适配器跑通流水线)"
            )
        import httpx
        self.client = httpx.Client(base_url=base, headers=self._auth_headers(), timeout=30)
        log.info("[odata] 已连接 %s", base)

    def close(self) -> None:
        if self.client:
            self.client.close()

    # ------------------------------------------------------------------
    def datacheck(self, row: PlanRow, method: str) -> CallResult:
        # TODO: POST 中间表(crud=I, op=datacheck), 轮询结果, 解析规范化物料/错误
        guid = self._guid(row, method, "datacheck")
        return self._post_and_poll(op="datacheck", row=row, method=method, guid=guid)

    def get_master_data(self, row: PlanRow, method: str, field_name: str) -> CallResult:
        # TODO: GET 物料主数据实体, 取对应字段
        # resp = self.client.get(f"/{self.o['item_entity']}('{row.item}')", params={"$select": field_name})
        raise NotImplementedError("get_master_data: 待按物料主数据 OData 实体实现")

    def import_plan(self, row: PlanRow, method: str) -> CallResult:
        guid = self._guid(row, method, "import")
        return self._post_and_poll(op="import", row=row, method=method, guid=guid)

    def run_plan(self, method: str) -> CallResult:
        # TODO: 触发 LN 处理进程跑计划(ION 触发活动 / 或写一条收尾标记由处理进程执行)
        raise NotImplementedError("run_plan: 待按 ION/处理进程触发方式实现")

    # ------------------------------------------------------------------
    def _post_and_poll(self, op: str, row: PlanRow, method: str, guid: str) -> CallResult:
        """写中间表一行 -> 轮询 isok/rdesc(幂等键 guid, 对应技能 §7.1)。"""
        # TODO: 构造中间表 payload(主键+17主数据+21周期量+method+guid+crud=I)
        # payload = {...}
        # self.client.post(f"/{self.o['middle_table_entity']}", json=payload)
        # 然后按 poll.interval/timeout 轮询该 guid 的 flag/rdesc
        raise NotImplementedError(f"_post_and_poll({op}): 待按中间表 OData 实体实现")

    def _auth_headers(self) -> dict:
        # TODO: OAuth2 取 token / 或 Basic
        return {}

    @staticmethod
    def _guid(row: PlanRow, method: str, op: str) -> str:
        raw = f"{row.biz_key}|{method}|{op}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()
