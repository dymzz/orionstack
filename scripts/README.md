# Scripts Usage

`scripts/` 目录当前包含本地开发与最小发布辅助脚本。

## 前置要求

- Windows PowerShell / PowerShell 7
- 已安装 `python`
- 已安装 `npm`
- 已安装 `git`
- 建议在仓库根目录下准备 `.venv`

## 脚本列表

### `dev-backend.ps1`

用途：

- 启动后端开发服务

参数：

- `-AppMode demo|dev|prod`
- `-BackendHost 127.0.0.1`
- `-Port 8000`
- `-CheckOnly`

示例：

```powershell
.\scripts\dev-backend.ps1 -AppMode dev -BackendHost 127.0.0.1 -Port 8000
.\scripts\dev-backend.ps1 -CheckOnly
```

### `dev-frontend.ps1`

用途：

- 启动前端开发服务

参数：

- `-Install`
- `-BackendOrigin http://127.0.0.1:8000`
- `-CheckOnly`

示例：

```powershell
.\scripts\dev-frontend.ps1
.\scripts\dev-frontend.ps1 -Install -BackendOrigin http://127.0.0.1:8000
.\scripts\dev-frontend.ps1 -CheckOnly
```

### `dev-demo.ps1`

用途：

- 一键启动后端与前端开发环境

参数：

- `-AppMode demo|dev|prod`
- `-BackendPort 8000`
- `-BackendReadyTimeoutSeconds 30`
- `-InstallFrontend`
- `-CheckOnly`

示例：

```powershell
.\scripts\dev-demo.ps1
.\scripts\dev-demo.ps1 -AppMode demo -BackendPort 8000 -InstallFrontend
.\scripts\dev-demo.ps1 -CheckOnly
```

### `git-release.ps1`

用途：

- 交互式创建本地版本发布提交
- 同步 `pyproject.toml` 的 `version`
- 创建 git tag
- 推送当前分支与 tag

默认行为：

- tag 格式为 `v<version>`，例如 `v0.1.3`
- `pyproject.toml` 中的 `version` 会被同步为 `0.1.3`
- 若未传 `-Version` 或 `-CommitMessage`，脚本会交互式询问
- 提交前会再做一次确认

参数：

- `-Version 0.1.3`
- `-CommitMessage "feat: ..."`
- `-TagPrefix v`
- `-RemoteName origin`
- `-SkipPush`
- `-CheckOnly`

示例：

```powershell
.\scripts\git-release.ps1
.\scripts\git-release.ps1 -Version 0.1.3 -CommitMessage "feat: complete P7 document management"
.\scripts\git-release.ps1 -Version 0.1.3 -CommitMessage "chore: release 0.1.3" -SkipPush
.\scripts\git-release.ps1 -Version 0.1.3 -CommitMessage "chore: release 0.1.3" -CheckOnly
```

执行结果：

1. 更新 `pyproject.toml` 版本
2. 执行 `git add --all`
3. 执行 `git commit -m "..."`
4. 创建注解 tag：`git tag -a v0.1.3 -m "release v0.1.3"`
5. 推送当前分支与 tag

注意事项：

- 如果 tag 已存在，脚本会直接停止
- 如果当前没有可提交变更，脚本会直接停止
- 如果使用 `-SkipPush`，提交与 tag 只保留在本地
- 如果只想检查参数和版本摘要，可使用 `-CheckOnly`

### `clean-local-records.ps1`

用途：

- 清理本地问答记录文件
- 仅作用于本地 `chat_records.jsonl` 与 `feedback_records.jsonl`

参数：

- `-ChatOnly`
- `-FeedbackOnly`
- `-CheckOnly`
- `-WhatIf`

示例：

```powershell
.\scripts\clean-local-records.ps1 -CheckOnly
.\scripts\clean-local-records.ps1 -WhatIf
.\scripts\clean-local-records.ps1
.\scripts\clean-local-records.ps1 -ChatOnly
.\scripts\clean-local-records.ps1 -FeedbackOnly
```

执行结果：

1. 输出当前本地记录文件路径、行数与大小
2. 根据参数选择清理 ask 记录或 feedback 记录
3. 删除目标本地记录文件

注意事项：

- 该脚本只清理本地记录文件，不清理文档上传数据
- `-WhatIf` 只预演，不实际删除
- `-CheckOnly` 只检查当前文件状态，不执行清理

### `start-backend.ps1`

用途：

- 以生产配置启动后端服务（不带 `--reload`）

参数：

- `-AppMode prod|demo|dev`
- `-BackendHost 127.0.0.1`
- `-Port 8000`
- `-Workers 1`
- `-CheckOnly`

示例：

```powershell
.\scripts\start-backend.ps1
.\scripts\start-backend.ps1 -AppMode prod -BackendHost 0.0.0.0 -Port 8000 -Workers 2
.\scripts\start-backend.ps1 -CheckOnly
```

与 `dev-backend.ps1` 的差异：

- 不带 `--reload`：生产启动不做热重载
- 支持 `-Workers` 参数：可启动多 worker 进程
- 默认 `-AppMode prod`：关闭 Debug 信息与记录查看接口

## 生产配置说明

### 环境变量

后端通过环境变量读取所有配置。可用变量参见仓库根目录 `.env.example`。

关键配置项：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ORIONSTACK_APP_MODE` | `demo` | `demo` / `dev` / `prod` |
| `ORIONSTACK_HOST` | `127.0.0.1` | 监听地址，生产环境可改为 `0.0.0.0` |
| `ORIONSTACK_PORT` | `8000` | 监听端口 |
| `ORIONSTACK_CORS_ORIGINS` | 开发默认值 | 允许的前端来源，逗号分隔 |
| `ORIONSTACK_ROUTE_CONFIDENCE_THRESHOLD` | `0.6` | 路由置信度阈值 |
| `ORIONSTACK_RETRIEVAL_MIN_SCORE` | `2` | 检索最低分 |
| `ORIONSTACK_CHAT_RECORD_MAX_COUNT` | `200` | 问答记录保留上限 |
| `ORIONSTACK_FEEDBACK_RECORD_MAX_COUNT` | `200` | 反馈记录保留上限 |

### `prod` 模式行为

将 `ORIONSTACK_APP_MODE` 设为 `prod` 时：

- `debug_info` 不会返回给前端，即使请求带了 `debug=true`
- `/api/chat/records` 与 `/api/chat/feedback` 接口返回 `404`
- 前端 `canDebug` 为 `false`，不展示 Debug 面板与最近记录区

### CORS 来源

生产环境必须将 `ORIONSTACK_CORS_ORIGINS` 设为实际部署域名，否则前端无法跨域请求后端。

示例：

```powershell
$env:ORIONSTACK_CORS_ORIGINS = "https://app.example.com"
```

不设置时默认为开发来源：

- `http://localhost:5173`
- `http://127.0.0.1:5173`

### 前端生产构建

```powershell
cd frontend
npm run build
```

构建产物在 `frontend/dist/`，可直接通过 Nginx 或其他静态文件服务提供。

前端生产模式下 `canDebug` 为 `false`，不展示 Debug 面板与最近记录区。

## 记录保留策略

后端在保存记录时会自动截断最旧记录，默认保留数量为 200 条。

配置项：

- `ORIONSTACK_CHAT_RECORD_MAX_COUNT`：问答记录保留数量上限，默认 `200`
- `ORIONSTACK_FEEDBACK_RECORD_MAX_COUNT`：反馈记录保留数量上限，默认 `200`

设置方式：

```powershell
$env:ORIONSTACK_CHAT_RECORD_MAX_COUNT = "50"
$env:ORIONSTACK_FEEDBACK_RECORD_MAX_COUNT = "50"
```

行为说明：

- 每次保存新记录后检查当前记录总数
- 如果超出 `max_count`，自动删除最旧记录
- 设置为 `0` 或不配置时保留默认上限 200 条
