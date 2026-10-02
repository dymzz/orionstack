# OrionStack

企业知识助手 / 文档问答最小可运行系统。

当前版本提供本地 FAQ 与文档问答、抽取审核发布、动态查询适配器与来源追溯。下一版本使用同一个 PostgreSQL 数据库存储结构化事实和 pgvector 向量，接入 TypeSafe Jev 完成检索决策与证据筛选，再由 LLM 根据证据生成回答。外部连接与编排交给 n8n / workflow，经稳定的 Action/Event 契约连接 Integration Layer；workflow 不进入核心检索链。当前设计见根目录《OrionStack — DB + Vector + JEV 检索架构设计.md》。

## 能做什么

- 上传 `.txt` / `.md` / `.pdf` / `.docx` 文档
- 基于文档内容进行问答检索与引用返回
- FAQ 模式兜底（弱命中或无命中时自动回落）
- 问答记录与用户反馈自动落盘
- 开发态可查看最近问答记录与反馈

## 前置要求

- Python 3.14+（建议使用 `.venv`，与 `pyproject.toml` 一致）
- Node.js 18+（仅开发和构建前端时需要，生产部署不需要）
- Docker（生产 Compose 部署需要；本地 FAQ/文档问答可直接运行）

## 命令约定

- 项目服务与回归入口统一使用 Python 脚本：`python scripts/*.py`
- 本地切换配置统一修改 `.env`，不要在命令前拼接临时环境变量
- 后端启动脚本会优先使用仓库内 `.venv`，找不到时才回退到当前 `python`

## 快速启动（当前过渡基线）

当前版本默认使用本地 FAQ 与文档检索，不需要启动 Elasticsearch。下一版本目标是 **同一个 PostgreSQL 数据库中的结构化表 + pgvector 向量表**，由 TypeSafe Jev 选择检索路径、筛选候选证据，再由 LLM 生成带来源的回答。接入尚未完成，详见 [目标架构与交付计划](docs/designs/4_postgresql_jev_architecture.md)。

本地配置写入 `.env`：

```text
ORIONSTACK_SEARCH_BACKEND=local
ORIONSTACK_ENABLE_QUERY_PLANNER=false
ORIONSTACK_ENABLE_FAST_TRACK=false
```

启动应用：

```text
python scripts/dev-demo.py
```

浏览器打开 `http://localhost:5173` 即可使用。已有 `.env` 中的显式配置优先于代码默认值，升级时请同步以上三项。

上传文档后可以选定文档提问；审核发布的 FAQ 即时进入本地检索，重新加载后仍可使用，撤销后不再召回。

发布前检查：

```text
python scripts/release-check.py
```

原 Phase 2 文档用于历史实现参考，下一版本的开发与验收以新的 PostgreSQL + Jev 计划为准。

M1 已提供单库 PostgreSQL + pgvector schema、JSONL 迁移预览和 Jev/DeepSeek 客户端。核心连接与密钥分别读取 `ORIONSTACK_DATABASE_URL`、`TYPESAFE_API_KEY`、`DEEPSEEK_API_KEY` 环境变量。先用 `uv sync` 更新依赖，再运行：

```powershell
.venv\Scripts\python.exe scripts/check-core-providers.py
.venv\Scripts\python.exe scripts/migrate-postgres.py
```

以上命令默认只检查配置和预览，不调用模型、不连接数据库。实际迁移需显式 `--apply`，真实模型测试需 `--live-jev` / `--live-deepseek`。新 query/entities/actions/events 四接口尚未注册，现有问答保持当前链路。迁移错误、版本约束、联调进度与命令见 [M1 运行说明](docs/designs/5_core_foundation_runbook.md)。

## 生产部署

### 1. Docker Compose（推荐）

生产 compose 会启动：

- `frontend`：Nginx 静态站点 + `/api/*` 反代
- `backend`：FastAPI / Uvicorn（`prod` 模式）

先准备生产环境变量：

```text
cp .env.prod.example .env.prod
```

必须修改 `.env.prod` 中的：

- `ORIONSTACK_ADMIN_PASSWORD`
- `ORIONSTACK_ADMIN_TOKEN_SECRET`（至少 24 字符）
- `ORIONSTACK_CORS_ORIGINS`（部署域名，例如 `https://app.example.com`）

启动：

```text
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

默认访问 `http://localhost:8080`，可通过 `ORIONSTACK_HTTP_PORT` 修改宿主机端口。

检查：

```text
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

运行态检查端点：

- `/healthz`：进程存活检查，只返回 `{"status":"ok"}`
- `/readyz`：部署 readiness，只返回 `status`；不 ready 时返回 503
- `/readyz/detail`：需要管理员认证，返回 app 版本、app mode、生产配置安全状态与检索后端状态

当前持久化数据使用 Docker named volumes，包括问答记录、trace、hard case、上传文档、SourceRecord 与候选数据。首次启动时，后端会在 action link / dynamic query 持久卷为空时拷贝镜像内默认 JSONL 配置。生产 Compose 使用本地检索；PostgreSQL 接入完成后再更新数据库部署配置。

抽取 FAQ、导入批次、抽取任务和清理任务也使用独立持久卷。升级已有部署前，先按下面的流程停止旧后端并备份完整 storage，保留旧容器内尚未挂卷的数据；新持久卷不能自动找回旧容器的临时文件。

备份生产 storage 数据：

```text
docker compose --env-file .env.prod -f docker-compose.prod.yml stop backend
docker compose --env-file .env.prod -f docker-compose.prod.yml cp backend:/app/backend/app/storage ./prod-storage-snapshot
python scripts/backup-storage.py --storage-root ./prod-storage-snapshot --output-dir backups
docker compose --env-file .env.prod -f docker-compose.prod.yml start backend
```

恢复前先预览：

```text
python scripts/restore-storage.py backups/orionstack-storage-YYYYMMDDTHHMMSSZ.tar.gz --what-if
```

恢复前会核对 manifest、文件大小与 SHA-256；文档元数据中的上传路径会改为恢复目标下的路径。生产卷恢复应在容器路径下执行，示例见 `wiki/backup-restore.md`。

发布前建议运行统一检查：

```text
python scripts/release-check.py
```

快速本地检查可运行：

```text
python scripts/release-check.py --quick
```

GitHub Actions 已配置 `.github/workflows/release-check.yml`，在 PR 与 `main` / `master` push 时运行同一个 release check。

### 2. 手动部署（可选）

如不使用 Docker Compose，也可以手动构建前端并启动后端。

构建前端：

```text
npm --prefix frontend run build
```

构建产物在 `frontend/dist/`，由 Nginx 或其他静态文件服务提供。

启动后端：

```text
python scripts/start-backend.py
```

默认以 `prod` 模式启动，不带热重载，监听 `127.0.0.1:8000`。

常用参数：

```text
python scripts/start-backend.py --app-mode prod --host 0.0.0.0 --port 8000 --workers 2
```

### 3. 环境变量

本地配置优先写入 `.env`；部署环境可使用平台自带的环境变量配置。参见 `.env.example` 获取完整列表。

关键变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ORIONSTACK_APP_MODE` | `demo` | `demo`/`dev`：显示 Debug 与记录面板；`prod`：隐藏 |
| `ORIONSTACK_HOST` | `127.0.0.1` | 后端监听地址 |
| `ORIONSTACK_PORT` | `8000` | 后端监听端口 |
| `ORIONSTACK_LOG_LEVEL` | `INFO` | 后端日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `ORIONSTACK_ACCESS_LOG_ENABLED` | `true` | 是否输出简要 access log；不记录请求体或 token |
| `ORIONSTACK_CORS_ORIGINS` | 开发默认值 | 前端允许的来源，逗号分隔 |
| `ORIONSTACK_SEARCH_BACKEND` | `local` | 当前过渡版本使用本地检索；PostgreSQL 接入见目标架构计划 |
| `ORIONSTACK_ELASTIC_URL` | `http://localhost:9200` | ES 连接地址 |
| `ORIONSTACK_ELASTIC_INDEX` | `knowledge_units_v1` | ES 索引名称 |
| `ORIONSTACK_ENABLE_QUERY_PLANNER` | `false` | 旧 planner 默认关闭，下一版本使用 Jev 路径决策 |
| `ORIONSTACK_ENABLE_FAST_TRACK` | `false` | 旧 Fast Track 默认关闭 |
| `ORIONSTACK_PLANNER_PROVIDER` | `local` | Planner provider：`local` / `openai_compatible` / `qwen_api` / `llama_cpp` |
| `ORIONSTACK_PLANNER_API_BASE` | DashScope OpenAI-compatible 地址 | 当前 planner provider 的 API 地址 |
| `ORIONSTACK_PLANNER_API_MODEL` | `qwen-plus` | 当前 planner provider 的模型名 |
| `ORIONSTACK_EXTRACTION_PROVIDER` | `openai_compatible` | 抽取 provider：`openai_compatible` / `qwen_api` / `llama_cpp` |
| `ORIONSTACK_EXTRACTION_API_BASE` | DashScope OpenAI-compatible 地址 | 当前抽取 provider 的 API 地址 |
| `ORIONSTACK_EXTRACTION_API_MODEL` | `qwen-plus` | 当前抽取 provider 的模型名 |
| `ORIONSTACK_DYNAMIC_QUERY_ADAPTER` | `mock` | 动态查询适配器：`mock` / `odoo` / 自定义 |
| `ORIONSTACK_ADMIN_USERNAME` | `admin` | 管理入口用户名，生产必须覆盖 |
| `ORIONSTACK_ADMIN_PASSWORD` | `admin` | 管理入口密码，生产必须覆盖；prod 使用默认值会拒绝启动 |
| `ORIONSTACK_ADMIN_TOKEN_SECRET` | `orionstack-dev-secret` | 管理 token 签名密钥，生产必须覆盖且至少 24 字符 |
| `ORIONSTACK_ADMIN_TOKEN_TTL_SECONDS` | `28800` | 管理 token 有效期（秒） |
| `ORIONSTACK_CHAT_RECORD_MAX_COUNT` | `200` | 问答记录保留上限 |
| `ORIONSTACK_FEEDBACK_RECORD_MAX_COUNT` | `200` | 反馈记录保留上限 |

兼容说明：旧的 `ORIONSTACK_QWEN_API_*`、`ORIONSTACK_QWEN_API_KEY`、`DASHSCOPE_API_KEY` / `QWEN_API_KEY` 仍可作为回退配置读取，但不再是唯一入口。

生产环境必须设置 `ORIONSTACK_CORS_ORIGINS`，例如：

```text
ORIONSTACK_CORS_ORIGINS=https://app.example.com
```

### 4. `prod` 模式行为

- Debug 信息不返回前端
- `/admin/*` 与对应管理 API 需要管理员登录
- `prod` 模式会校验管理认证配置：默认密码、默认 token secret 或过短 secret 会导致后端拒绝启动
- `prod` 模式下，即使管理员已登录，`/api/chat/records`、`/api/chat/feedback`、trace 与 hard case 调试接口仍按隐藏处理
- 前端问答页不展示 Debug 面板与最近记录区

### 5. 日志与排障

后端日志输出到 stdout，适合 Docker / 云平台收集。当前日志包含：

- `startup_begin` / `shutdown_complete`
- `elastic_indexing_completed` / `elastic_indexing_skipped`
- `request_completed` / `request_failed`
- `admin_login_succeeded` / `admin_login_failed` / `admin_logout`

日志不会记录请求体、密码或 Bearer token。查看生产日志：

```text
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f backend
```

排障优先看：

```text
curl http://localhost:8080/healthz
curl http://localhost:8080/readyz
```

### 6. Nginx 参考（手动部署）

最小 Nginx 配置示例：

```nginx
server {
    listen 80;
    server_name app.example.com;

    root /path/to/orionstack/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /healthz {
        proxy_pass http://127.0.0.1:8000;
    }

    location /readyz {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

## 项目结构

```text
orionstack/
├── backend/                 # FastAPI 后端
│   ├── main.py              # 应用入口
│   └── app/
│       ├── api/routes/       # 路由（health, chat, documents, extraction）
│       ├── config/           # 配置（settings.py）
│       ├── extract/          # 抽取 provider -> 候选 -> 审核发布
│       ├── guardrails/       # 输入归一化
│       ├── indexing/         # ES 索引与健康检查
│       ├── observability/    # retrieval trace
│       ├── query/            # Query Planner 与 provider
│       ├── retrieval/        # 检索（retriever, lexical_retriever, citation_mapper）
│       ├── routing/          # 路由决策
│       ├── runtime/          # 动态查询 adapter 与 trace 辅助
│       ├── schemas/          # 请求与响应模型
│       ├── services/         # 业务服务
│       ├── storage/          # 本地 JSONL 存储与仓储
│       ├── sync/             # SourceRecord 同步、freshness、tombstone
│       └── testing/          # hard case 等测试辅助
├── frontend/                 # Vue 3 + Vite 前端
│   └── src/
│       ├── components/chat/  # 问答组件
│       ├── pages/admin/      # trace / hard case / extraction / debug 管理页
│       ├── pages/chat/       # 问答主页面
│       ├── services/         # API 调用
│       ├── styles/           # 全局样式
│       └── types/            # 类型定义
├── scripts/                 # 启动与维护脚本
├── docs/                    # 设计与进度文档
├── CHANGELOG.md             # 版本变更记录
├── docker-compose.yml       # ES + Odoo 示例容器配置
├── .env.example             # 环境变量参考
└── README.md
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/healthz` | 进程存活检查 |
| `GET` | `/readyz` | 部署 readiness 检查 |
| `POST` | `/api/chat/ask` | 问答请求 |
| `POST` | `/api/chat/feedback` | 提交反馈 |
| `GET` | `/api/chat/records` | 最近问答记录（需 admin，且仅 demo/dev） |
| `GET` | `/api/chat/feedback` | 最近反馈记录（需 admin，且仅 demo/dev） |
| `GET` | `/api/chat/traces/{trace_id}` | 检索 trace 回放（需 admin，且仅 demo/dev） |
| `GET` | `/api/chat/hard-cases` | hard case 列表（需 admin，且仅 demo/dev） |
| `POST` | `/api/documents/upload` | 上传文档 |
| `GET` | `/api/documents` | 文档列表 |
| `DELETE` | `/api/documents/{id}` | 删除文档 |
| `POST` | `/api/extraction/extract` | 从 SourceRecord 抽取候选（需 admin） |
| `POST` | `/api/extraction/review` | 审核候选并按需发布（需 admin） |
| `GET` | `/api/extraction/candidates` | 候选列表（需 admin） |

## 脚本说明

| 脚本 | 用途 |
|------|------|
| `dev-backend.py` | 开发模式启动后端（带热重载） |
| `dev-frontend.py` | 启动前端开发服务 |
| `dev-demo.py` | 一键启动前后端开发环境 |
| `start-backend.py` | 生产模式启动后端（不带热重载） |
| `release-check.py` | 发布前统一检查 |
| `backup-storage.py` | 备份本地 storage 数据 |
| `restore-storage.py` | 恢复 storage 备份 |
| `migrate-postgres.py` | 默认预览，显式事务迁移单库 PostgreSQL + pgvector |
| `check-core-providers.py` | 检查核心环境变量，显式测试 Jev/DeepSeek |
| `run-phase2-regression.py` | 一键执行 phase 2 专项回归 |
| `clean-local-records.py` | 清理本地记录文件 |
| `git-release.py` | 交互式版本发布 |

详细参数说明见 `scripts/README.md`。

版本变更记录见 `CHANGELOG.md`。发布前先运行 `python scripts/release-check.py`，再使用 `python scripts/git-release.py --version <x.y.z> --commit-message "release: v<x.y.z>"`。

## 数据存储

当前使用本地 JSONL 文件存储，数据位于 `backend/app/storage/` 下的分目录：

- `chat_records/` — 问答记录
- `feedback/` — 反馈记录
- `retrieval_traces/` — 检索 trace
- `hard_cases/` — hard case
- `documents/` / `chunks/` / `uploads/` — 文档元数据、切块与上传文件
- `source_records/` / `extraction_candidates/` — 原始来源记录与抽取候选
- `action_links/` / `dynamic_queries/` — 原系统入口与动态查询定义

记录保留数量可通过环境变量配置，超出自增数量后自动截断最旧记录。
