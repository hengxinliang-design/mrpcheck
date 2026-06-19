# 主计划导入 ERP-LN — Python 版（第 1 期原型）

替代原 Excel-VBA 宏：服务器可定时运行，Excel 仅作录入界面，LN 业务逻辑保留在
LN 侧（中间表 + 处理进程），Python 通过 OData 读写中间表对接。

## 第 1 期范围

- ✅ 读 Excel（**按列名/配置映射**，告别 `Cells(i,38)` 硬编码）
- ✅ 本地预校验 + LN 适配器（datacheck / get.data / import / run.plan 四个入口）
- ✅ 回写 Excel：结果列 `ok`/错误，**失败行整行染红**（与 VBA 一致）
- ✅ 批量汇总（成功/失败/失败行号）+ 日志
- ✅ LN 适配器可插拔：`mock`（本地模拟，默认）↔ `odata`（真实，待填端点）
- ⏳ 真实 OData 对接（第 2/3 期）：填 `config.yaml` 的 `ln.odata.*`，实现 `ln_odata.py` 的 TODO

## 运行

```bash
cd /Users/hengxinliang/project
python3 -m mps_ln_import.main                 # 默认 mock 适配器
python3 -m mps_ln_import.main --adapter odata # 真实对接（需先配端点）
```

结果默认另存为 `<源文件>_result.xlsm`，不覆盖录入源。

## Web 服务模式（第 2 期骨架）

```bash
cd /Users/hengxinliang/project
pip3 install -r mps_ln_import/requirements.txt
uvicorn mps_ln_import.service.api:app --reload --host 0.0.0.0 --port 8000
```

第一版 API 使用 SQLite 和本地上传目录，配置在 `config.yaml` 的 `service.*`：

- `GET /health`
- `POST /api/mps-batches/upload`
- `GET /api/mps-batches`
- `GET /api/mps-batches/{batchId}`
- `GET /api/mps-batches/{batchId}/rows`
- `POST /api/mps-batches/{batchId}/validate`
- `POST /api/mps-batches/{batchId}/import`
- `GET /api/jobs/{jobId}`

当前 `validate/import` 为同步执行的任务壳，已经写入 job 状态；后续接 Celery/RQ 时 API 形状可以保持不变。

## 测试

```bash
cd /Users/hengxinliang/project
pip3 install -r mps_ln_import/requirements-dev.txt
python3 -m pytest mps_ln_import/tests -q
```

覆盖：本地校验、数据模型、mock 适配器、流程编排(importer)、Excel 读写(列映射/表头漂移告警/染红/结果路径)。合成临时 Excel，不依赖桌面真实文件。

## 演示失败行/红色高亮

编辑 `config.yaml`：

```yaml
ln:
  mock:
    fail_rows: [6, 9]   # 强制让 Excel 第 6、9 行导入失败
```

## 目录

```
mps_ln_import/
├── config.yaml            # 端点/认证、Excel路径、列映射、方案
├── main.py                # 入口（可调度）
├── core/
│   ├── models.py          # PlanRow / RunSummary
│   ├── validator.py       # 本地预校验
│   └── importer.py        # 编排流程
├── adapters/
│   ├── excel_reader.py    # 读（按配置列映射 + 表头漂移告警）
│   ├── excel_writer.py    # 写（结果 + 染红）
│   ├── ln_base.py         # LN 适配器抽象接口
│   ├── ln_mock.py         # 本地模拟实现
│   └── ln_odata.py        # 真实 OData 实现（桩，含 TODO）
└── README.md
```

## 切换到真实 LN（第 2/3 期）

1. LN 侧：建中间表 `tddev8xxx`（含 `guid/hdst/flag/isok/rdesc/crud` + 业务字段）+ 处理进程（复用现有 `ocpdevdllimport` 逻辑），开 OData 发布。
2. 填 `config.yaml` 的 `ln.odata.base_url / auth / *_entity`。
3. 实现 `ln_odata.py` 中 `_post_and_poll` / `get_master_data` / `run_plan` 的 TODO。
4. `--adapter odata` 运行，上层流程与 mock 完全一致。
```
