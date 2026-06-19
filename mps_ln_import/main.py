"""入口。供 Task Scheduler / cron / Airflow 调度。

用法:
    python3 -m mps_ln_import.main                         # 用 config.yaml 默认(mock)
    python3 -m mps_ln_import.main --adapter odata         # 切真实 OData(需先配端点)
    python3 -m mps_ln_import.main --config other.yaml
"""
from __future__ import annotations

import argparse
import logging
import sys

import yaml

from .adapters.excel_reader import ExcelReader
from .adapters.excel_writer import ExcelWriter
from .adapters.ln_base import LNAdapter
from .adapters.ln_mock import MockLNAdapter
from .adapters.ln_odata import ODataLNAdapter
from .core.importer import Importer


def build_adapter(cfg: dict) -> LNAdapter:
    name = cfg["ln"]["adapter"]
    if name == "mock":
        return MockLNAdapter(cfg)
    if name == "odata":
        return ODataLNAdapter(cfg)
    raise ValueError(f"未知 ln.adapter: {name}")


def setup_logging(cfg: dict) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    log_path = cfg.get("output", {}).get("log_path")
    if log_path:
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        handlers=handlers,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="主计划导入 ERP-LN (Python 第1期原型)")
    ap.add_argument("--config", default="mps_ln_import/config.yaml")
    ap.add_argument("--adapter", choices=["mock", "odata"], help="覆盖 config 的 ln.adapter")
    args = ap.parse_args(argv)

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if args.adapter:
        cfg["ln"]["adapter"] = args.adapter

    setup_logging(cfg)
    log = logging.getLogger("main")

    try:
        method, rows = ExcelReader(cfg).read()
        if not rows:
            log.warning("无有效数据行, 退出。")
            return 0

        ln = build_adapter(cfg)
        summary = Importer(cfg, ln).run(method, rows)
        ExcelWriter(cfg).write(rows)

        print("\n" + "=" * 48)
        print(summary.text())
        print("=" * 48)
        return 0 if summary.fail_count == 0 else 2
    except Exception:
        log.exception("运行失败")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
