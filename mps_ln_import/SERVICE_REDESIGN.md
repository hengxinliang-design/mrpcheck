# 主计划导入 ERP-LN 服务化设计

本文把原 Excel VBA 宏的业务处理逻辑重新设计为前后端服务。目标不是复刻 Excel 点击按钮，而是把“录入、校验、ERP 取数、导入、结果追踪”变成可审计、可重跑、可扩展的系统。

## 1. 原宏业务边界

原 Excel 宏主要做三件事：

1. 读取“主计划导入”表第 5 行以后的数据。
2. 通过 Baan/LN 客户端调用 `ocpdevdllimport` 下的 4GL 函数：
   - `cprrp.datacheck(...)`
   - `get.data(...)`
   - `cprrp.production.plan.quantity.import(...)`
   - `run.plan(method)`
3. 将处理结果写回 Excel 第 39 列 `AM`，成功写 `ok`，失败写 ERP 返回信息。

宏中的 Excel 只是录入和结果承载工具，真正业务规则在 LN/Baan 侧。因此服务化时应保留 LN 侧业务函数/处理逻辑，把 Excel 交互替换成 Web 页面和后端任务。

## 2. 服务化后的业务流程

推荐流程：

```text
用户上传/维护主计划
        |
        v
后端解析并落库为导入批次 + 明细行
        |
        v
本地预校验：必填、数量、期间数、重复行
        |
        v
ERP DataCheck：校验工厂/物料/客户/客户料号
        |
        v
ERP GetData：回填图号、规格、特征、库存、订单等字段
        |
        v
用户复核并调整手工字段/期间数量
        |
        v
提交导入任务
        |
        v
ERP ImportPlan：逐行导入 17 个主数据字段 + 21 个期间数量
        |
        v
ERP RunPlan：整批完成后按方案触发计划运行
        |
        v
任务结果、失败行、ERP 返回消息展示；可导出 Excel
```

与原宏的对应关系：

| 原宏 | 服务化动作 |
|---|---|
| `DataCheck_Click` | 批次校验接口：本地校验 + `datacheck` + `get.data` + 可选 `run.plan` |
| `UpdateForecast_Click` | 批次导入接口：逐行 `production.plan.quantity.import` |
| `AM列` | 明细行 `status/message` 字段 |
| 当前活动表 | 明确的批次 ID 和版本 |
| Excel 手工录入 | Web 表格编辑 + Excel 导入模板 |

## 3. 系统模块

### 前端

建议页面：

1. 批次列表
   - 显示方案、状态、总行数、成功数、失败数、创建人、创建时间。
   - 支持筛选：待校验、校验失败、待导入、导入中、已完成。

2. 批次详情
   - 类 Excel 网格展示明细。
   - 固定左侧主键列：工厂、物料、客户、客户料号。
   - 中间展示 ERP 回填字段：图号、名称规格、特征、库存、订单等。
   - 右侧展示 21 个期间数量。
   - 最右侧展示状态、ERP 返回消息。

3. 上传导入
   - 上传原 Excel 或标准模板。
   - 后端解析后生成批次。
   - 表头漂移只告警，不直接中断，除非关键列缺失。

4. 校验/导入操作区
   - `校验并回填`
   - `提交导入`
   - `重试失败行`
   - `导出结果 Excel`

5. 任务日志
   - 展示每一步调用耗时、失败原因、ERP 原始返回值。
   - 管理员可查看 LN 请求流水。

### 后端

推荐分层：

```text
API Controller
  - 批次、明细、上传、导入任务接口

Application Service
  - BatchService
  - ValidationService
  - ImportJobService

Domain/Core
  - PlanRow
  - Importer
  - Validator
  - RunSummary

Adapters
  - ExcelReader/ExcelWriter
  - LNAdapter
  - MockLNAdapter
  - ODataLNAdapter 或 BaanDllAdapter

Infrastructure
  - DB
  - Queue/Worker
  - Object Storage
  - Audit Log
```

现有目录 `mps_ln_import/core` 已经可以作为 `Domain/Core` 起点。服务化时不要把 ERP 调用写死在 API 里，应继续通过 `LNAdapter` 抽象。

## 4. API 设计

### 批次

```http
POST /api/mps-batches/upload
```

上传 Excel，返回批次。

```json
{
  "batchId": "B202606190001",
  "method": "ACT",
  "status": "draft",
  "totalRows": 120
}
```

```http
GET /api/mps-batches
GET /api/mps-batches/{batchId}
GET /api/mps-batches/{batchId}/rows
PATCH /api/mps-batches/{batchId}/rows/{rowId}
```

### 校验与回填

```http
POST /api/mps-batches/{batchId}/validate
```

后台创建异步任务：

```json
{
  "jobId": "J202606190001",
  "type": "validate",
  "status": "queued"
}
```

### 导入

```http
POST /api/mps-batches/{batchId}/import
```

可支持只导入指定行：

```json
{
  "mode": "failed_rows_only"
}
```

### 任务

```http
GET /api/jobs/{jobId}
GET /api/jobs/{jobId}/events
```

`events` 可用于前端轮询或 SSE/WebSocket 实时刷新。

### 导出

```http
GET /api/mps-batches/{batchId}/export.xlsx
```

生成与原 Excel 相近的结果文件：失败行染红，结果列写 `ok` 或错误信息。

## 5. 数据模型

核心表：

### `mps_import_batch`

| 字段 | 说明 |
|---|---|
| `id` | 批次 ID |
| `method` | 方案，如 `ACT` |
| `status` | `draft/validated/validation_failed/importing/completed/failed` |
| `source_file_name` | 原始文件名 |
| `total_rows` | 总行数 |
| `ok_rows` | 成功行数 |
| `failed_rows` | 失败行数 |
| `created_by` | 创建人 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

### `mps_import_row`

| 字段 | 说明 |
|---|---|
| `id` | 明细 ID |
| `batch_id` | 批次 ID |
| `excel_row_no` | 原 Excel 行号 |
| `factory` | 工厂 |
| `item` | 物料编码 |
| `customer` | 客户 |
| `customer_item` | 客户料号 |
| `master_json` | 13 个主数据字段 |
| `periods_json` | 21 个期间数量 |
| `status` | `draft/validated/imported/failed` |
| `message` | ERP 返回消息 |
| `normalized_item` | ERP 规范化后的物料编码 |
| `last_checked_at` | 最近校验时间 |
| `last_imported_at` | 最近导入时间 |

### `mps_import_job`

| 字段 | 说明 |
|---|---|
| `id` | 任务 ID |
| `batch_id` | 批次 ID |
| `type` | `validate/import/export` |
| `status` | `queued/running/succeeded/failed/canceled` |
| `progress_total` | 总进度 |
| `progress_done` | 已完成 |
| `message` | 当前消息 |
| `started_at` | 开始时间 |
| `finished_at` | 结束时间 |

### `mps_ln_call_log`

记录每次 LN 调用，便于追责和排错：

| 字段 | 说明 |
|---|---|
| `id` | 日志 ID |
| `job_id` | 任务 ID |
| `row_id` | 明细 ID，可为空 |
| `operation` | `datacheck/get_data/import_plan/run_plan` |
| `request_payload` | 请求参数 |
| `response_payload` | ERP 返回 |
| `ok` | 是否成功 |
| `duration_ms` | 耗时 |
| `created_at` | 时间 |

## 6. LN 对接方案

有两种落地方式：

### 方案 A：中间表 + OData，推荐

后端不直接模拟 Excel COM/Baan 客户端，而是通过 LN OData 写中间表，由 LN 侧处理进程复用现有 4GL 逻辑。

优点：

- 适合服务器部署，不依赖 Windows Excel/Baan 客户端。
- 可审计、可重跑、可幂等。
- 批量任务更稳定。

处理方式：

1. 后端写入中间表：操作类型、业务主键、主数据、21 期数量、批次号、行号、幂等键。
2. LN 后台进程处理该记录。
3. 后端轮询中间表状态：成功、失败、返回消息。
4. 整批完成后触发 `run.plan(method)` 等价逻辑。

### 方案 B：服务端 COM/Baan DLL 适配器，过渡方案

后端部署在能安装 Baan 客户端的 Windows 机器上，用 COM 调用替代 VBA 的 `CreateObject`。

优点是改造快，缺点是部署脆弱、并发差、依赖桌面客户端。只建议作为短期过渡。

## 7. 处理规则

### 本地预校验

在调用 LN 前先检查：

- 工厂、物料、客户、客户料号至少满足业务要求。
- 21 个期间数量必须是数字或空。
- 同批次中业务主键重复时提示。
- 方案 `method` 不能为空。
- 期间数必须为 21。

### DataCheck 等价规则

每行调用 `datacheck`：

- 返回成功且带规范化物料时，更新物料编码。
- 返回失败时，该行状态为 `failed`，不进入导入。

然后对 LN 来源字段调用 `get.data` 回填：

- `seak/dsca/cpcl/wght/sfst/bqty/mpud/qhnd/dqan/oqan`
- 保留手工字段：`mode/cqty/mqty`

### ImportPlan 等价规则

导入时只处理通过校验的行。每行传入：

- 4 个业务主键
- 13 个主数据字段
- 21 个期间数量
- 方案 `method`

ERP 返回第一位等价于原宏：

- `1...`：成功，行状态 `imported`，消息 `ok`
- 其他：失败，行状态 `failed`，消息为 ERP 返回值

### RunPlan 规则

原宏在 `DataCheck` 末尾执行 `run.plan(method)`，在 `UpdateForecast` 末尾没有执行。服务化建议把它设计为可配置：

- 校验后运行：兼容原 `DataCheck`
- 导入后运行：更符合“整批导入后触发计划”的业务直觉
- 手工按钮运行：由计划员确认后触发

默认建议：导入完成且无严重错误后，由用户点击“运行计划”或按批次配置自动运行。

## 8. 与现有 Python 原型的衔接

现有代码可以按以下方式演进：

1. 保留 `core/models.py` 的 `PlanRow`，增加数据库 ID、状态枚举。
2. 保留 `core/importer.py` 的编排逻辑，改为可回调进度、逐行持久化状态。
3. 保留 `adapters/ln_base.py`，继续扩展 `ODataLNAdapter`。
4. `ExcelReader/ExcelWriter` 从主流程依赖变为导入/导出适配器。
5. 新增 API 层，例如 `FastAPI`：
   - `api/batches.py`
   - `api/jobs.py`
   - `api/exports.py`
6. 新增 Worker 层，例如 `Celery/RQ/Arq`：
   - `validate_batch_job`
   - `import_batch_job`
   - `export_batch_job`

## 9. 推荐技术栈

如果没有既定技术栈，建议：

- 前端：React + TypeScript + TanStack Table
- 后端：FastAPI + SQLAlchemy
- 数据库：PostgreSQL
- 异步任务：Celery + Redis，或 RQ + Redis
- 文件存储：本地 NAS/MinIO/S3，按企业环境选择
- LN 对接：优先 OData 中间表

如果企业内部更偏 Java：

- 前端仍可用 React
- 后端用 Spring Boot
- 任务用 Quartz/Spring Batch
- 核心业务逻辑按本文模型迁移即可

## 10. 实施阶段

### 第 1 阶段：保留 Excel，后端批处理

- 使用现有 `mps_ln_import` 原型。
- 支持上传 Excel、后台运行、下载结果 Excel。
- LN 使用 mock 跑通，后续切 OData。

### 第 2 阶段：Web 批次管理

- 批次、明细、状态、日志落库。
- 前端展示、编辑、筛选失败行。
- 支持重试失败行。

### 第 3 阶段：真实 LN 对接

- LN 中间表/OData 发布。
- 实现 `ODataLNAdapter`。
- 打通校验、回填、导入、运行计划。

### 第 4 阶段：替代 Excel

- Web 表格成为主录入入口。
- Excel 只保留导入/导出模板。
- 增加权限、审批、版本留痕。

## 11. 关键风险

- LN 侧 `datacheck/get.data/import/run.plan` 的真实返回码需要明确文档化。
- 原宏依赖“当前活动表”，服务化必须改成明确批次，避免误导入。
- 21 个期间的日期含义需要从表头变成结构化字段，否则后续月份滚动容易出错。
- `run.plan` 放在校验后还是导入后，需要业务确认。
- 如果短期仍走 COM/Baan 客户端，服务器并发能力和稳定性会受限。

