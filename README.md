# OrionStack

> 2026-10-04 第 3 项 P1-2 最小反馈审计闭环完成：帮助度、候选相关性和事实纠错关联实际运行并幂等追加，Logs 串联原始召回/后处理/来源链/回答/反馈；服务端 Cedar 与当前来源访问校验，当前只读自己的记录。反馈均待复核、不可训练。Alembic 至 010_feedback_audit；155 项相关回归、49 项真实 HTTP 检查与浏览器验收通过。复核/训练导出、Core Cedar 统一和 OTel 仍待后续。见 [验收报告](docs/reports/2026-10-04_feedback_audit_acceptance.md)。

> 2026-10-04 工作台三模式已完成：资料问答附原文引用；普通聊天独立调用 DeepSeek 并保留有限上下文；系统反馈显示服务端实际调用状态、原因与请求 ID，可回读自己的回执。新增 append-only 工作台审计与 Alembic 009；160 项相关回归、36 项真实 HTTP 检查及网页交互通过。见 [三模式验收](docs/reports/2026-10-04_workbench_modes_acceptance.md)。

> 2026-10-04 本机工作台已通过真实 Confluence 问答：服务端将 admin/test 绑定独立验证租户，3 份原文 / 69 个本地 Qwen3 向量可检索，DeepSeek 回答附原文引用。47 项真实链路检查和浏览器验收通过；完整 5,189 份语料的后台索引仍在运行。配置、范围和运行记录见 [工作台知识问答验收](docs/reports/2026-10-04_workbench_knowledge_acceptance.md)。

> 2026-10-04 当前界面：登录默认聊天工作台；DataOps 提供附件/版本、强制隔离、Cedar、pgBackRest 仓库适配与脱敏诊断。DataOps 008 扫描迁移已完成，工作台迁移已至 009；扫描检查独立追加，未 ready 版本不能生成派生结果。基础设施尚未部署；联合恢复、retention 执行与派生 worker 待实施。旧 domain 演示资料和文档管理/范围 UI 已退休，历史 Raw 保留。详见 [当前 DataOps 边界](docs/designs/16_dataops_assets_runtime.md)。

企业知识助手 / 文档问答最小可运行系统。

P1-0/P1-1：四模块网页与新核心 API、逐条 EvidenceBundle/ChainProfile、BFF server-side session 已实现。企业身份使用外部 OIDC，内部主体采用 issuer/subject 映射，生产不用本地密码；真实 IdP 联调待配置。Secrets 交 OpenBao，正式迁移用 Alembic；DataOps 已接入 Cedar，三类待复核反馈和自己的实际运行审计 HTTP/Logs 已实现；完整 Core 授权统一、复核/训练导出、实体查询、OTel SDK 与联合恢复按 P1-2 至 P1-4 实施。见 [身份与运维边界](docs/designs/15_security_identity_operations.md) 和 [交付计划](docs/designs/12_p1_delivery_plan.md)。

工作台已经使用同一个 PostgreSQL 数据库存储知识和 pgvector 向量，默认通过本地 ONNX Runtime 调用 Qwen3-Embedding-0.6B，Cloudflare Workers AI REST 保留为备选。先封存原始 Top-K，再按需使用 Jev、reranker 或规则处理，LLM 根据最终证据生成回答。外部连接与编排通过稳定契约交给 n8n / workflow，workflow 不进入核心检索链。当前设计见根目录《OrionStack — DB + Vector + JEV 检索架构设计.md》。

## 能做什么

- 工作台区分资料问答、普通聊天与系统反馈；资料查询展示引用和来源链，普通聊天有真实 DeepSeek 回答，反馈提供本次服务端执行回执。
- DataOps 选择文件或文件夹，按 Asset/AssetVersion 隔离核验；存储、Tika、ClamAV 未配置时明确不可用。
- pgBackRest 备份状态、文件名和授权下载接口；未部署时显示待配置，联合恢复未验证。
- 管理员查看账号、开发演示身份和脱敏系统诊断；领域审计与系统遥测分开。
- 旧阶段工具与操作说明保留作历史兼容参考，新的实现范围以 P1 交付计划为准。

## 前置要求

- Python 3.14+（建议使用 `.venv`，与 `pyproject.toml` 一致）
- Node.js 18+（仅开发和构建前端时需要，生产部署不需要）
- Docker（生产 Compose 部署需要；本地 FAQ/文档问答可直接运行）

## 命令约定

- 项目服务与回归入口统一使用 Python 脚本：`python scripts/*.py`
- 本地切换配置统一修改 `.env`，不要在命令前拼接临时环境变量
- 后端启动脚本会优先使用仓库内 `.venv`，找不到时才回退到当前 `python`

## 快速启动（当前过渡基线）

当前版本默认使用本地 FAQ 与文档检索，不需要启动 Elasticsearch。下一版本目标是 **同一个 PostgreSQL 数据库中的结构化表 + pgvector 向量表**；Jev 是可选处理器，原始召回和训练派生独立保存。新库、CLI 与认证后的 `/api/query`、`/api/documents` 已实现，模块化网页已切换新核心，Web 使用 BFF session；详见 [目标架构与交付计划](docs/designs/4_postgresql_jev_architecture.md)。

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

以上命令默认只检查配置和预览，不调用模型、不连接数据库。实际迁移需显式 `--apply`，真实模型测试需 `--live-jev` / `--live-deepseek`。新 `/api/query` 与文档生命周期接口已注册；entities/actions/events 仍为草案，旧网页继续使用原链路。迁移错误、版本约束、联调进度与命令见 [M1 运行说明](docs/designs/5_core_foundation_runbook.md)。

M2 新增 Workers AI embedding、pgvector 召回、不可变 raw journal、可选处理器、独立反馈及训练样本派生。默认 embedding provider 为 `onnx`，从 `ORIONSTACK_ONNX_DIR` 读取本地 Qwen3-Embedding-0.6B / 1024 维。设置 `ORIONSTACK_EMBEDDING_PROVIDER=cloudflare_workers_ai` 才使用 Cloudflare 备选及其 `CF_API_TOKEN`、`CF_ACCOUNT_ID`。`scripts/check-core-providers.py --live-embedding` 使用两条虚构中文文本验证 API；入库、召回和隔离 PostgreSQL 测试命令见 [原始召回运行说明](docs/designs/6_raw_retrieval_processing.md)。未配置 Jev key 也可运行默认 raw 链路。

## P0 核心 API

P0 1–4 已完成真实 legacy 迁移、受控文档入库、认证查询/raw 日常归档与逐字摘录的来源核验。目标 PostgreSQL 17 / pgvector 0.8.2 已保存 5 份文档、94 个 chunk 向量和 99 条知识记录；两条缺来源 FAQ 的 7 条历史记录单独隔离，原文件保留。Workers AI、DeepSeek 和真实 query/upload/download/revoke 已联调通过。

使用新核心请调用 `/api/query` 和 `/api/documents`；登录仍用 `/api/v1/auth/login`。旧网页迁移、结构化实体查询、反馈 HTTP 与中文质量评测属于下一步。接口、服务端权限映射、清单迁移与 PowerShell 示例见 [P0 运行说明](docs/designs/7_p0_query_ingestion_runbook.md)；实际契约见 [Knowledge API](docs/designs/core_knowledge.openapi.json)。

2026-10-03 追加现有 HR 文档与真实 DeepSeek 验证已通过：本地 Qwen3 召回 18 个 raw 候选，最终 5 个候选、2 条核验引用，raw 与回答真实保存。当前网页操作步骤、已验证项目和旧链路误答问题见 [网页验证指引](docs/reports/2026-10-03_web_validation.md)。

下一阶段以 [P1-0 至 P1-4 修订计划](docs/designs/12_p1_delivery_plan.md) 为准：核心契约、四模块网页、新核心 QA、逐条 ChainProfile 来源事实链、反馈/审计/标签、结构化只读查询及语义/来源链评测与备份隔离恢复。信用/风险决策系统与 workflow/rollback 待其他模块完善后实现；保留边界说明，不作为当前核心依赖。设计已记录，DTO/API 扩展和网页待实施，见 [ChainProfile](docs/designs/13_chain_profile.md)、[架构模式边界](docs/designs/14_architecture_patterns.md) 与 [模块化网页](docs/designs/11_modular_web_plan.md)。

Confluence 基准入库入口为 `scripts/ingest-confluence-benchmark.py`，读取 `data/EnterpriseRAG-Bench/confluence`，默认只预览；`--apply --stage-only` 保存原文和 chunk，`--apply --index-only` 批量生成本地 Qwen3 ONNX 向量并恢复中断进度。默认使用独立租户 `enterprise-rag-bench`，保留原始 dsid 与相对路径，并把版本清单保存到 PostgreSQL。命令、来源映射和验收方式见 [Confluence 基准入库说明](docs/designs/8_enterprise_rag_benchmark_ingestion.md)。

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
