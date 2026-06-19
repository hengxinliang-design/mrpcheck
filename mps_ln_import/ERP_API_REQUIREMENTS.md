# ERP/LN 主计划导入接口需求说明

本文档用于给 ERP/LN 开发团队评估和实现接口。目标是替代原 Excel VBA 宏中通过 Baan 客户端调用 `ocpdevdllimport` DLL 函数的方式，让新的 Web 服务通过 HTTP API 或 OData 调用 ERP 侧现有业务逻辑。

## 1. 背景

现有 Excel 宏在“主计划导入”工作表中完成以下动作：

1. 逐行读取主计划数据。
2. 调用 ERP/LN 侧函数校验物料、客户、客户料号和方案。
3. 从 ERP/LN 回填图号、名称规格、库存、销售订单等字段。
4. 将 21 个期间的主计划/预测数量导入 ERP/LN。
5. 触发计划运行。

原 VBA 调用的 ERP 侧函数如下：

| 原函数 | 用途 |
|---|---|
| `cprrp.datacheck(factory, itemcode, customer, customeritemcode, method)` | 校验主键并可能返回规范化后的物料编码 |
| `get.data(factory, itemcode, customer, customeritemcode, method, columnNumber)` | 按字段编号回填 ERP 主数据/库存/订单数据 |
| `cprrp.production.plan.quantity.import(...)` | 导入一行主计划数据 |
| `run.plan(method)` | 按方案触发计划运行 |

新系统不要求 ERP 团队提供 4GL 源码。ERP 团队只需要将上述业务能力封装为稳定接口，供新系统调用。

## 2. 总体要求

### 2.1 接口形式

优先级：

1. HTTP JSON API
2. OData Action/Function
3. OData 中间表 + 后台处理进程

无论使用哪种形式，对外语义需要与本文档一致。

### 2.2 认证和网络

ERP 团队需提供：

- API 基础地址
- 认证方式：OAuth2、Basic Auth、API Key、企业网关 Token 等
- 测试环境地址
- 生产环境地址
- 调用频率限制
- 超时时间建议
- 白名单或 VPN 要求

### 2.3 通用响应格式

建议所有接口统一返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "",
  "data": {}
}
```

失败示例：

```json
{
  "success": false,
  "code": "ITEM_CUSTOMER_MAPPING_NOT_FOUND",
  "message": "物料和客户料号未建立对应关系",
  "data": {}
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `success` | boolean | 是 | 本次业务处理是否成功 |
| `code` | string | 是 | 机器可读返回码 |
| `message` | string | 是 | 给用户/运维查看的中文或英文说明 |
| `data` | object | 否 | 业务数据 |

## 3. 接口一：主数据校验 DataCheck

### 3.1 用途

替代原函数：

```text
cprrp.datacheck(factory, itemcode, customer, customeritemcode, method)
```

用于校验工厂、物料、客户、客户料号、方案是否有效，并在必要时返回 ERP 侧规范化后的物料编码。

### 3.2 建议接口

```http
POST /api/mps/datacheck
Content-Type: application/json
```

### 3.3 请求参数

```json
{
  "factory": "PG3",
  "itemCode": "A04-00001-PKG-S",
  "customer": "Q5869",
  "customerItemCode": "K51401A47P",
  "method": "ACT"
}
```

| 字段 | 类型 | 必填 | 对应 Excel/VBA | 说明 |
|---|---|---:|---|---|
| `factory` | string | 是 | A列 工厂 | 工厂代码 |
| `itemCode` | string | 是 | B列 物料编码 | 物料编码 |
| `customer` | string | 是 | C列 客户 | 客户代码 |
| `customerItemCode` | string | 是 | D列 客户料号 | 客户物料号 |
| `method` | string | 是 | B1 方案 | 方案，如 `ACT` |

### 3.4 成功响应

```json
{
  "success": true,
  "code": "OK",
  "message": "",
  "data": {
    "normalizedItemCode": "A04-00001-PKG-S"
  }
}
```

### 3.5 失败响应

```json
{
  "success": false,
  "code": "ITEM_CUSTOMER_MAPPING_NOT_FOUND",
  "message": "物料和客户料号未建立对应关系",
  "data": {
    "normalizedItemCode": ""
  }
}
```

### 3.6 兼容原宏返回规则

原宏中：

- 返回值首位为 `2`：表示返回规范化物料编码，并写回 B 列。
- 其他返回：写入 AM 列作为错误/提示。

新接口应直接返回结构化字段 `normalizedItemCode`，不要再要求新系统解析字符串首位。

## 4. 接口二：ERP 回填数据 Master Data

### 4.1 用途

替代原函数：

```text
get.data(factory, itemcode, customer, customeritemcode, method, columnNumber)
```

原宏按字段编号逐个取值。新接口建议一次返回全部 ERP 回填字段，减少多次网络调用。

### 4.2 建议接口

```http
POST /api/mps/master-data
Content-Type: application/json
```

### 4.3 请求参数

```json
{
  "factory": "PG3",
  "itemCode": "A04-00001-PKG-S",
  "customer": "Q5869",
  "customerItemCode": "K51401A47P",
  "method": "ACT"
}
```

### 4.4 成功响应

```json
{
  "success": true,
  "code": "OK",
  "message": "",
  "data": {
    "seak": "5896-015",
    "dsca": "5896-015中框组件成品",
    "cpcl": "无",
    "wght": "12.5",
    "sfst": "100",
    "bqty": "200",
    "mpud": "2026-06-19",
    "qhnd": "500",
    "dqan": "20",
    "oqan": "300"
  }
}
```

### 4.5 返回字段说明

| 字段 | 对应 Excel 列 | 原 4GL 字段变量 | 说明 |
|---|---:|---|---|
| `seak` | E | `seak` | 图号 |
| `dsca` | F | `dsca` | 名称规格（说明） |
| `cpcl` | G | `cpcl` | 特征 |
| `wght` | H | `wght` | 单重g |
| `sfst` | K | `sfst` | 安全库存 |
| `bqty` | M | `bqty` | 单箱数量 |
| `mpud` | N | `mpud` | 主计划更新日期 |
| `qhnd` | O | `qhnd` | 成品实时库存 |
| `dqan` | P | `dqan` | 销售订单逾期量 |
| `oqan` | Q | `oqan` | 未来销售订单交货量 |

以下字段在原宏中被跳过，属于手工维护字段，新接口不需要返回：

| 字段 | 对应 Excel 列 | 说明 |
|---|---:|---|
| `mode` | I | 车型 |
| `cqty` | J | 单车用量 |
| `mqty` | L | 单箱数量（手工） |

## 5. 接口三：导入主计划 Import Plan

### 5.1 用途

替代原函数：

```text
cprrp.production.plan.quantity.import(...)
```

用于向 ERP/LN 导入一行主计划数据。每行包含：

- 4 个业务主键
- 13 个主数据字段
- 21 个期间数量
- 方案 `method`

### 5.2 建议接口

```http
POST /api/mps/import-plan
Content-Type: application/json
```

### 5.3 请求参数

```json
{
  "batchId": "B202606190001",
  "rowId": "R000001",
  "method": "ACT",
  "factory": "PG3",
  "itemCode": "A04-00001-PKG-S",
  "customer": "Q5869",
  "customerItemCode": "K51401A47P",
  "master": {
    "seak": "5896-015",
    "dsca": "5896-015中框组件成品",
    "cpcl": "无",
    "wght": "12.5",
    "mode": "",
    "cqty": "",
    "sfst": "100",
    "mqty": "",
    "bqty": "200",
    "mpud": "2026-06-19",
    "qhnd": "500",
    "dqan": "20",
    "oqan": "300"
  },
  "periods": [
    "0", "0", "0", "0", "0", "0", "0",
    "200", "0", "0", "0", "0", "0", "0",
    "0", "0", "0", "0", "0", "0", "0"
  ]
}
```

### 5.4 请求字段说明

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `batchId` | string | 建议 | 新系统批次号，用于追踪 |
| `rowId` | string | 建议 | 新系统行号，用于追踪 |
| `method` | string | 是 | 方案 |
| `factory` | string | 是 | 工厂 |
| `itemCode` | string | 是 | 物料编码 |
| `customer` | string | 是 | 客户 |
| `customerItemCode` | string | 是 | 客户料号 |
| `master` | object | 是 | 13 个主数据字段 |
| `periods` | array[string] | 是 | 21 个期间数量，顺序对应 Excel R 到 AL 列 |

### 5.5 成功响应

```json
{
  "success": true,
  "code": "OK",
  "message": "ok",
  "data": {
    "erpDocumentNo": "",
    "erpRowId": ""
  }
}
```

### 5.6 失败响应

```json
{
  "success": false,
  "code": "IMPORT_FAILED",
  "message": "第 9 期计划数量不允许为负数",
  "data": {
    "erpDocumentNo": "",
    "erpRowId": ""
  }
}
```

### 5.7 兼容原宏返回规则

原宏中：

- 返回值首位为 `1`：导入成功，Excel AM 列写 `ok`。
- 返回值首位不是 `1`：导入失败，Excel AM 列写 ERP 返回文本。

新接口应通过 `success` 表示成功/失败，通过 `message` 返回可展示错误信息。

## 6. 接口四：运行计划 Run Plan

### 6.1 用途

替代原函数：

```text
run.plan(method)
```

用于在批次校验或导入完成后触发 ERP/LN 侧计划运行。

### 6.2 建议接口

```http
POST /api/mps/run-plan
Content-Type: application/json
```

### 6.3 请求参数

```json
{
  "batchId": "B202606190001",
  "method": "ACT"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `batchId` | string | 建议 | 新系统批次号 |
| `method` | string | 是 | 方案 |

### 6.4 成功响应

```json
{
  "success": true,
  "code": "OK",
  "message": "计划运算已触发",
  "data": {
    "planJobId": "ERP_PLAN_JOB_202606190001"
  }
}
```

### 6.5 失败响应

```json
{
  "success": false,
  "code": "RUN_PLAN_FAILED",
  "message": "方案 ACT 当前不允许运行计划",
  "data": {
    "planJobId": ""
  }
}
```

## 7. 可选接口：批量导入

如果 ERP 团队支持批量处理，建议增加批量接口，以减少逐行调用开销。

```http
POST /api/mps/import-plan-batch
Content-Type: application/json
```

请求：

```json
{
  "batchId": "B202606190001",
  "method": "ACT",
  "rows": [
    {
      "rowId": "R000001",
      "factory": "PG3",
      "itemCode": "A04-00001-PKG-S",
      "customer": "Q5869",
      "customerItemCode": "K51401A47P",
      "master": {},
      "periods": []
    }
  ]
}
```

响应：

```json
{
  "success": true,
  "code": "OK",
  "message": "批量导入完成",
  "data": {
    "rows": [
      {
        "rowId": "R000001",
        "success": true,
        "code": "OK",
        "message": "ok"
      }
    ]
  }
}
```

批量接口不是第一阶段必需项。如果实现周期较长，第一阶段可以只提供单行 `import-plan`。

## 8. 幂等和追踪要求

建议 ERP 接口支持以下字段用于追踪和幂等：

| 字段 | 说明 |
|---|---|
| `batchId` | 新系统批次号 |
| `rowId` | 新系统行 ID |
| `requestId` | 单次请求唯一 ID，可由新系统生成 |

ERP 侧应尽量保证：

- 相同 `requestId` 重复提交时，不重复导入。
- 返回结果可按 `batchId`、`rowId`、`requestId` 追踪。
- 接口日志保留请求参数、处理结果、错误信息和处理时间。

## 9. 错误码建议

ERP 团队可以按实际业务补充，建议至少包括：

| 错误码 | 含义 |
|---|---|
| `OK` | 成功 |
| `INVALID_ARGUMENT` | 参数缺失或格式错误 |
| `METHOD_NOT_FOUND` | 方案不存在 |
| `FACTORY_NOT_FOUND` | 工厂不存在 |
| `ITEM_NOT_FOUND` | 物料不存在 |
| `CUSTOMER_NOT_FOUND` | 客户不存在 |
| `CUSTOMER_ITEM_NOT_FOUND` | 客户料号不存在 |
| `ITEM_CUSTOMER_MAPPING_NOT_FOUND` | 物料、客户、客户料号关系不存在 |
| `MASTER_DATA_NOT_FOUND` | 回填主数据不存在 |
| `IMPORT_FAILED` | 主计划导入失败 |
| `RUN_PLAN_FAILED` | 运行计划失败 |
| `ERP_INTERNAL_ERROR` | ERP 内部错误 |

## 10. 性能和超时要求

建议目标：

| 接口 | 单次响应目标 |
|---|---:|
| `datacheck` | 2 秒内 |
| `master-data` | 3 秒内 |
| `import-plan` | 5 秒内 |
| `run-plan` | 可异步，立即返回计划任务号 |

如 `run-plan` 需要较长时间，建议 ERP 接口返回 `planJobId`，并额外提供查询计划任务状态的接口。

## 11. 验收测试用例

ERP 团队交付接口后，至少需要提供以下测试场景：

1. 正常物料、客户、客户料号、方案校验成功。
2. 物料不存在，`datacheck` 返回失败。
3. 客户料号不存在，`datacheck` 返回失败。
4. 输入物料编码需要规范化，`datacheck` 返回 `normalizedItemCode`。
5. `master-data` 正常返回全部 ERP 回填字段。
6. `master-data` 对不存在的主数据返回明确错误。
7. `import-plan` 正常导入一行 21 期数量。
8. `import-plan` 对非法数量返回明确错误。
9. 同一 `requestId` 重复提交时不重复导入。
10. `run-plan` 正常触发计划运行，并返回可追踪任务号或成功信息。

## 12. 第一阶段最小交付范围

第一阶段 ERP 团队至少提供：

| 接口 | 是否必需 |
|---|---:|
| `POST /api/mps/datacheck` | 必需 |
| `POST /api/mps/master-data` | 必需 |
| `POST /api/mps/import-plan` | 必需 |
| `POST /api/mps/run-plan` | 必需 |

批量导入、计划任务状态查询、更多审计接口可以放到第二阶段。

