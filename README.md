# OrionStack

企业 AI 应用底座仓库。

## 当前定位

本仓库当前承载 OrionStack 首期 MVP：**企业知识助手 / 文档问答**。

当前主线聚焦：

- 文档上传与解析
- 索引构建
- 检索问答
- 引用返回
- 会话、日志与反馈基础链路

当前不追求：

- 大而全平台化
- 多 Agent 协同
- 自动审批与自动写入旧系统
- 以替代 ERP / OA / 权限系统为目标的重构工程

## 目录概览

```text
orionstack/
├── frontend/
├── backend/
├── docs/
└── README.md
```

## 本地启动

最短路径启动 Demo：

```powershell
.\scripts\dev-demo.ps1
```

只检查脚本和环境，不实际拉起服务：

```powershell
.\scripts\dev-demo.ps1 -CheckOnly
```

分别启动前后端：

```powershell
.\scripts\dev-backend.ps1 -AppMode dev -BackendHost 127.0.0.1
.\scripts\dev-frontend.ps1
```

补充说明：

- `dev-demo.ps1` 会先启动后端，并等待 `GET /healthz` 就绪后再启动前端。
- `dev-backend.ps1` 默认优先使用仓库根目录下的 `.venv\Scripts\python.exe`。
- `dev-frontend.ps1` 默认只在 `node_modules` 缺失时安装依赖；如需强制刷新依赖，可使用 `-Install`。
