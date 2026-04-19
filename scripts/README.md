# Scripts Usage

`scripts/` 目录当前包含本地开发与最小发布辅助脚本。

所有脚本使用 Python 重写，不再依赖 PowerShell。

## 前置要求

- 已安装 `python`（建议 3.12+）
- 已安装 `npm`
- 已安装 `git`
- 建议在仓库根目录下准备 `.venv`

## 脚本列表

### `dev-backend.py`

用途：

- 启动后端开发服务

参数：

- `--app-mode demo|dev|prod`
- `--host 127.0.0.1`
- `--port 8000`
- `--check-only`

示例：

```bash
python scripts/dev-backend.py --app-mode dev --host 127.0.0.1 --port 8000
python scripts/dev-backend.py --check-only
```

### `dev-frontend.py`

用途：

- 启动前端开发服务

参数：

- `--install`
- `--backend-origin http://127.0.0.1:8000`
- `--check-only`

示例：

```bash
python scripts/dev-frontend.py
python scripts/dev-frontend.py --install --backend-origin http://127.0.0.1:8000
python scripts/dev-frontend.py --check-only
```

### `dev-demo.py`

用途：

- 一键启动后端与前端开发环境

参数：

- `--app-mode demo|dev|prod`
- `--port 8000`
- `--timeout 30`
- `--install-frontend`
- `--check-only`

示例：

```bash
python scripts/dev-demo.py
python scripts/dev-demo.py --app-mode demo --port 8000 --install-frontend
python scripts/dev-demo.py --check-only
```

### `git-release.py`

用途：

- 交互式创建本地版本发布提交
- 同步 `pyproject.toml` 的 `version`
- 创建 git tag
- 推送当前分支与 tag

默认行为：

- tag 格式为 `v<version>`，例如 `v0.1.3`
- `pyproject.toml` 中的 `version` 会被同步为 `0.1.3`
- 若未传 `--version` 或 `--commit-message`，脚本会交互式询问
- 提交前会再做一次确认

参数：

- `--version 0.1.3`
- `--commit-message "feat: ..."`
- `--tag-prefix v`
- `--remote origin`
- `--skip-push`
- `--check-only`

示例：

```bash
python scripts/git-release.py
python scripts/git-release.py --version 0.1.3 --commit-message "feat: complete P7 document management"
python scripts/git-release.py --version 0.1.3 --commit-message "chore: release 0.1.3" --skip-push
python scripts/git-release.py --version 0.1.3 --commit-message "chore: release 0.1.3" --check-only
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
- 如果使用 `--skip-push`，提交与 tag 只保留在本地
- 如果只想检查参数和版本摘要，可使用 `--check-only`

### `clean-local-records.py`

用途：

- 清理本地问答记录文件
- 仅作用于本地 `chat_records.jsonl` 与 `feedback_records.jsonl`

参数：

- `--chat-only`
- `--feedback-only`
- `--check-only`
- `--what-if`

示例：

```bash
python scripts/clean-local-records.py --check-only
python scripts/clean-local-records.py --what-if
python scripts/clean-local-records.py
python scripts/clean-local-records.py --chat-only
python scripts/clean-local-records.py --feedback-only
```

执行结果：

1. 输出当前本地记录文件路径、行数与大小
2. 根据参数选择清理 ask 记录或 feedback 记录
3. 删除目标本地记录文件

注意事项：

- 该脚本只清理本地记录文件，不清理文档上传数据
- `--what-if` 只预演，不实际删除
- `--check-only` 只检查当前文件状态，不执行清理

### `start-backend.py`

用途：

- 以生产配置启动后端服务（不带 `--reload`）

参数：

- `--app-mode prod|demo|dev`
- `--host 127.0.0.1`
- `--port 8000`
- `--workers 1`
- `--check-only`

示例：

```bash
python scripts/start-backend.py
python scripts/start-backend.py --app-mode prod --host 0.0.0.0 --port 8000 --workers 2
python scripts/start-backend.py --check-only
```

与 `dev-backend.py` 的差异：

- 不带 `--reload`：生产启动不做热重载
- 支持 `--workers` 参数：可启动多 worker 进程
- 默认 `--app-mode prod`：关闭 Debug 信息与记录查看接口

## 生产配置说明

### Phase 2 推荐启动矩阵

当前 phase 2 检索链建议按三档使用：

1. 默认全开档：
   - `ORIONSTACK_SEARCH_BACKEND=elasticsearch`
   - `ORIONSTACK_ENABLE_QUERY_PLANNER=true`
   - `ORIONSTACK_ENABLE_FAST_TRACK=true`
   - `ORIONSTACK_PLANNER_PROVIDER=local`
2. 软回退档：
   - `ORIONSTACK_SEARCH_BACKEND=elasticsearch`
   - `ORIONSTACK_ENABLE_QUERY_PLANNER=false`
   - `ORIONSTACK_ENABLE_FAST_TRACK=true`
3. 硬回退档：
   - `ORIONSTACK_SEARCH_BACKEND=local`
   - `ORIONSTACK_ENABLE_QUERY_PLANNER=false`
   - `ORIONSTACK_ENABLE_FAST_TRACK=false`

建议理解为：

- planner 高置信时：进入 `lexical + vector + RRF -> rerank + evidence`
- planner 低置信时：回退到 `Fast Track + lexical-only`
- 当前长期默认建议直接运行全开档；软/硬回退只保留为排障手段

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
| `ORIONSTACK_SEARCH_BACKEND` | `elasticsearch` | `elasticsearch`：默认全开档；`local`：硬回退到主线 1 默认链路 |
| `ORIONSTACK_ENABLE_QUERY_PLANNER` | `true` | 默认进入 planner -> hybrid -> rerank/evidence 服务链 |
| `ORIONSTACK_ENABLE_FAST_TRACK` | `true` | 默认启用小 query 规则与 lexical 过渡优化 |
| `ORIONSTACK_CHAT_RECORD_MAX_COUNT` | `200` | 问答记录保留上限 |
| `ORIONSTACK_FEEDBACK_RECORD_MAX_COUNT` | `200` | 反馈记录保留上限 |

### 推荐启动示例

```bash
# 默认全开档
ORIONSTACK_SEARCH_BACKEND=elasticsearch ORIONSTACK_ENABLE_FAST_TRACK=true ORIONSTACK_ENABLE_QUERY_PLANNER=true ORIONSTACK_PLANNER_PROVIDER=local python scripts/dev-backend.py

# 软回退：回到 Elasticsearch lexical-only
ORIONSTACK_SEARCH_BACKEND=elasticsearch ORIONSTACK_ENABLE_FAST_TRACK=true ORIONSTACK_ENABLE_QUERY_PLANNER=false python scripts/dev-backend.py

# 硬回退：完整回到主线 1 默认链路
ORIONSTACK_SEARCH_BACKEND=local ORIONSTACK_ENABLE_QUERY_PLANNER=false ORIONSTACK_ENABLE_FAST_TRACK=false python scripts/dev-backend.py
```

### 发布前最小 smoke

建议至少执行：

```bash
python -m pytest backend/tests/test_chat_flow.py backend/tests/test_document_flow.py backend/tests/test_phase2_settings.py backend/tests/test_phase2_knowledge_unit.py backend/tests/test_phase2_indexing.py backend/tests/test_phase2_retrieval.py backend/tests/test_phase2_planner.py
```

若当前准备长期使用默认全开档，建议再手动验证：

- `请假`
- `病假材料`
- `请假进度怎么看`

预期：

- `route_result = faq_qa_elastic`
- `retrieved_chunks` 为 FAQ 风格 ID
- `citation.source_locator` 为 `hr_faq_seed_v1#...`
- 不返回 `document_chunk` JSON 残片

### `prod` 模式行为

将 `ORIONSTACK_APP_MODE` 设为 `prod` 时：

- `debug_info` 不会返回给前端，即使请求带了 `debug=true`
- `/api/chat/records` 与 `/api/chat/feedback` 接口返回 `404`
- 前端 `canDebug` 为 `false`，不展示 Debug 面板与最近记录区

### CORS 来源

生产环境必须将 `ORIONSTACK_CORS_ORIGINS` 设为实际部署域名，否则前端无法跨域请求后端。

示例：

```bash
export ORIONSTACK_CORS_ORIGINS="https://app.example.com"
```

不设置时默认为开发来源：

- `http://localhost:5173`
- `http://127.0.0.1:5173`

### 前端生产构建

```bash
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

```bash
export ORIONSTACK_CHAT_RECORD_MAX_COUNT=50
export ORIONSTACK_FEEDBACK_RECORD_MAX_COUNT=50
```

行为说明：

- 每次保存新记录后检查当前记录总数
- 如果超出 `max_count`，自动删除最旧记录
- 设置为 `0` 或不配置时保留默认上限 200 条
