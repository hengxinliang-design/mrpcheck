# BW 客户端过渡集成方案

本文档说明在客户现场目前只有 BW 客户端、无法直接提供 ERP/LN HTTP API 或 OData 的情况下，如何让新的 Web 服务继续复用原 Excel 宏的 ERP 调用能力。

## 1. 当前约束

原 Excel VBA 宏通过本机 COM/OLE 创建 BW 客户端对象：

```vb
Set baanobj = CreateObject("Baan.Application.hongji")
baanobj.Timeout = 300
baanobj.ParseExecFunction "ocpdevdllimport", dllfunction
returnvalue = baanobj.returnvalue
```

这意味着：

- 调用必须发生在安装并配置好 BW 客户端的 Windows 机器上。
- `Baan.Application.hongji` 是本机 COM ProgID，不是浏览器或普通 Linux/Mac 后端能直接调用的服务端 API。
- 如果后端部署在没有 BW 的服务器上，无法直接执行原宏里的 ERP 函数。

因此，在 ERP 团队提供正式 API 前，需要一个过渡方案。

## 2. 推荐过渡架构：BW Bridge Agent

在客户现场一台安装了 BW 客户端的 Windows 机器上部署一个轻量服务，称为 `BW Bridge Agent`。

```text
浏览器
  |
  v
MPS Web 服务 / FastAPI
  |
  | HTTP JSON
  v
BW Bridge Agent (Windows + BW 客户端)
  |
  | COM/OLE CreateObject("Baan.Application.hongji")
  v
BW / LN
```

新系统仍调用 HTTP 接口，不直接知道 BW COM 细节。Bridge 内部负责把 HTTP 请求转换为原来的 `ParseExecFunction` 调用。

## 3. Bridge 对外接口

Bridge 对外接口建议与 `ERP_API_REQUIREMENTS.md` 保持一致：

| Bridge 接口 | 内部调用 |
|---|---|
| `POST /api/mps/datacheck` | `cprrp.datacheck(...)` |
| `POST /api/mps/master-data` | 多次 `get.data(...)` 或封装后的批量取数 |
| `POST /api/mps/import-plan` | `cprrp.production.plan.quantity.import(...)` |
| `POST /api/mps/run-plan` | `run.plan(method)` |

这样未来 ERP 团队提供正式 API 时，MPS Web 服务只需要修改 `erp_api.base_url`，不用改前端和业务流程。

## 4. Bridge 内部调用方式

### 4.1 连接 BW

Bridge 启动或首次调用时执行：

```vb
Set baanobj = CreateObject("Baan.Application.hongji")
baanobj.Timeout = 300
```

### 4.2 执行函数

示例：

```vb
dllname = "ocpdevdllimport"
dllfunction = "cprrp.datacheck(""PG3"",""A04-00001-PKG-S"",""Q5869"",""K51401A47P"",""ACT"")"
baanobj.ParseExecFunction dllname, dllfunction
returnvalue = baanobj.returnvalue
```

Bridge 需要把 `returnvalue` 转换成结构化 JSON。

## 5. 原宏返回值兼容规则

### 5.1 DataCheck

原宏逻辑：

```vb
If Mid(Trim(returnvalue), 1, 1) = "2" Then
    Cells(row, 2) = Mid(Trim(returnvalue), 3, Len(Trim(returnvalue)))
Else
    Cells(row, 39) = Trim(returnvalue)
End If
```

Bridge 应转换为：

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

失败时：

```json
{
  "success": false,
  "code": "DATACHECK_FAILED",
  "message": "ERP返回的错误文本",
  "data": {
    "normalizedItemCode": ""
  }
}
```

### 5.2 Import Plan

原宏逻辑：

```vb
If Mid(Trim(returnvalue), 1, 1) <> "1" Then
    Cells(row, 39) = Trim(returnvalue)
Else
    Cells(row, 39) = "ok"
End If
```

Bridge 应转换为：

```json
{
  "success": true,
  "code": "OK",
  "message": "ok",
  "data": {}
}
```

失败时：

```json
{
  "success": false,
  "code": "IMPORT_FAILED",
  "message": "ERP返回的错误文本",
  "data": {}
}
```

## 6. 部署要求

Bridge 必须部署在满足以下条件的 Windows 机器上：

- 已安装 BW 客户端。
- 当前 Windows 用户能正常登录并使用 BW。
- 本机能成功创建 COM 对象 `Baan.Application.hongji`。
- 能访问 LN/ERP 环境。
- 能被 MPS Web 服务访问，或在同一内网/VPN 中。

建议：

- Bridge 使用固定服务账号运行。
- 服务账号的 BW 登录、权限、公司/环境配置与当前 Excel 宏用户一致。
- Bridge 只监听内网地址，不暴露到公网。

## 7. 并发和稳定性限制

BW COM 自动化通常不适合高并发。第一阶段建议：

- Bridge 内部使用单线程队列串行调用 BW。
- 每次调用设置超时，例如 300 秒。
- 如果 BW 对象异常，自动释放并重建。
- 记录每次请求、函数名、参数摘要、返回值、耗时和异常。

如果并发导入量较大，建议最终改为 ERP 侧正式 API 或 OData 中间表方案。

## 8. 安全要求

Bridge 至少需要：

- API Key 或内网网关鉴权。
- 限制调用来源 IP。
- 日志中避免记录敏感认证信息。
- 对传入参数做转义，防止破坏 `ParseExecFunction` 字符串格式。
- 对所有请求生成 `requestId`，方便追踪。

## 9. 与当前项目的衔接

当前项目已经预留：

- `config.yaml` 中的 `erp_api.*`
- `/api/erp-test/*` 测试接口
- `ERP_API_REQUIREMENTS.md` 中的接口契约

客户现场只有 BW 时，配置方式如下：

```yaml
erp_api:
  enabled: true
  base_url: "http://<BW_BRIDGE_HOST>:<PORT>"
  auth:
    type: api_key
    header_name: "X-API-Key"
    api_key: "<由Bridge提供>"
  endpoints:
    datacheck: "/api/mps/datacheck"
    master_data: "/api/mps/master-data"
    import_plan: "/api/mps/import-plan"
    run_plan: "/api/mps/run-plan"
```

后续 ERP 团队提供正式 API 后，只需要把 `base_url` 切换到 ERP API 地址。

## 10. 第一阶段建议

第一阶段推荐这样推进：

1. 客户现场确认哪台 Windows 机器可以稳定运行 BW。
2. 技术人员在该机器上验证 `CreateObject("Baan.Application.hongji")`。
3. 做一个最小 Bridge：先实现 `datacheck` 和 `import-plan`。
4. 用 `/api/erp-test/*` 做真实调用测试。
5. 再接入批次校验和导入流程。

