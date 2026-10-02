# Scripts Usage

`scripts/` 目录当前包含本地开发、数据种子、抽取管线与最小发布辅助脚本。

所有 Python 脚本统一从仓库根目录运行：

```text
python scripts/<script_name>.py
```

本地普通配置可使用 `.env`；部署时核心连接串与密钥由进程环境注入，优先于 `.env`。

## 单库迁移与模型检查（M1）

先运行 `uv sync` 更新依赖。新核心读取 `ORIONSTACK_DATABASE_URL`、`TYPESAFE_API_KEY`、`DEEPSEEK_API_KEY`，没有硬编码密钥或旧 provider key 回退。

```powershell
.venv\Scripts\python.exe scripts/check-core-providers.py
.venv\Scripts\python.exe scripts/migrate-postgres.py
.venv\Scripts\python.exe scripts/migrate-postgres.py --schema-only
```

默认只输出配置存在性或文件迁移预览。schema/导入实际执行加 `--apply`，须目标库具备 pgvector；迁移脚本和批次均幂等，错误回滚整批。`--storage-root` 指定恢复目录，`--tenant-id` 仅为缺少 tenant 的记录提供默认值，`--no-seed` 排除内置 FAQ。孤立来源、非法状态等预览错误会阻断全部导入。

真实 API 检查使用虚构测试材料并产生少量调用费用，分别运行 `scripts/check-core-providers.py --live-jev` 或 `--live-deepseek`。当前四个新 API 仍是草案，完整边界与联调限制见 [M1 运行说明](../docs/designs/5_core_foundation_runbook.md)。

---

## 前置要求

- 已安装 Python 3.14+（与 `pyproject.toml` 一致）
- 已安装 `npm`
- 已安装 `git`
- 抽取管线脚本需要配置抽取 provider；当前配置优先读取 `ORIONSTACK_EXTRACTION_*`，旧的 `ORIONSTACK_QWEN_*` / `DASHSCOPE_API_KEY` 仍保留兼容

---

## 脚本列表

### 开发服务

#### `dev-backend.py`

启动后端开发服务（带 `--reload` 热重载）。

```text
python scripts/dev-backend.py --app-mode dev --host 127.0.0.1 --port 8000
python scripts/dev-backend.py --check-only
```

参数：`--app-mode demo|dev|prod` / `--host` / `--port` / `--check-only`

#### `dev-frontend.py`

启动前端开发服务。

```text
python scripts/dev-frontend.py
python scripts/dev-frontend.py --install --backend-origin http://127.0.0.1:8000
```

参数：`--install` / `--backend-origin` / `--check-only`

#### `dev-demo.py`

一键启动后端与前端开发环境。

```text
python scripts/dev-demo.py
python scripts/dev-demo.py --app-mode demo --port 8000 --install-frontend
```

参数：`--app-mode` / `--port` / `--timeout` / `--install-frontend` / `--check-only`

#### `start-backend.py`

以生产配置启动后端（不带 `--reload`，支持多 worker）。

```text
python scripts/start-backend.py --app-mode prod --workers 2
```

参数：`--app-mode prod|demo|dev` / `--host` / `--port` / `--workers` / `--check-only`

---

### 数据种子

#### `seed_action_links.py`

种子 ActionLink 数据 — 为当前 Odoo 示例模块生成 7 条 action link（请假、考勤、员工管理、报销、发票、CRM、项目）。

```text
python scripts/seed_action_links.py
```

输出：`backend/app/storage/action_links/action_links.jsonl`

#### `seed_dynamic_queries.py`

种子 DynamicQuery 定义 — 生成 5 条动态查询配置（请假状态、假期余额、报销状态、考勤记录、CRM 商机）。

```text
python scripts/seed_dynamic_queries.py
```

输出：`backend/app/storage/dynamic_queries/dynamic_queries.jsonl`

#### `seed_test_source_record.py`

种子测试用 SourceRecord — 写入一条"员工考勤与请假管理制度"制度文档，用于抽取管线验证。

```text
python scripts/seed_test_source_record.py
```

输出：`backend/app/storage/source_records/source_records.jsonl`

---

### 抽取管线

#### `pipeline_cli.py`

**核心脚本。** 可复用的文档 → 知识候选全自动管线。

从任意文本文档（.txt / .md）出发，调用当前配置的抽取 provider 抽取 FAQ / ActionLink / DynamicQuery 候选，审核后发布为可检索的知识单元。当前仓库默认示例使用 DashScope `qwen-plus`。

**完整管线流程：**

```text
任意文档 (.txt / .md)
       ↓ pipeline_cli import
  SourceRecord (raw_content)
       ↓ pipeline_cli extract → 当前配置的抽取 provider
  ExtractionCandidate (pending)
       ↓ pipeline_cli review --approve
  ┌──────────────┬───────────────┬─────────────────┐
  │ faq          │ action_link   │ dynamic_query    │
  │ KnowledgeUnit│ ActionLinkRepo│ DynamicQueryRepo │
  └──────────────┴───────────────┴─────────────────┘
```

**命令列表：**

```text
# 导入文档为 SourceRecord
python scripts/pipeline_cli.py import --file path/to/document.md --title "文档标题" --source-system wiki

# 一键完成：导入 + 抽取 + 自动审核 + 发布
python scripts/pipeline_cli.py import --file path/to/document.md --title "文档标题" --source-system wiki --auto-approve

# 从已有 SourceRecord 抽取候选
python scripts/pipeline_cli.py extract --source-record-id sr-xxx --candidate-types faq,action_link,dynamic_query

# 抽取后自动审核发布
python scripts/pipeline_cli.py extract --source-record-id sr-xxx --auto-approve

# 审核单条候选
python scripts/pipeline_cli.py review --candidate-id ec-xxx --approve
python scripts/pipeline_cli.py review --candidate-id ec-xxx --reject

# 列出候选
python scripts/pipeline_cli.py list --status pending
python scripts/pipeline_cli.py list --status approved
```

**import 参数：**

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `--file` | 是 | — | 文档文件路径（.txt / .md） |
| `--title` | 否 | 文件名 | 文档标题 |
| `--source-system` | 否 | `manual_upload` | 来源系统标识 |
| `--object-type` | 否 | `policy_doc` | 来源对象类型 |
| `--access-scope` | 否 | `internal` | 访问范围 |
| `--source-record-id` | 否 | 自动生成 | 覆盖 SourceRecord ID |
| `--auto-approve` | 否 | — | 导入后立即抽取 + 自动审核 + 发布 |
| `--candidate-types` | 否 | 全部 | 逗号分隔，仅 `--auto-approve` 时生效 |

**extract 参数：**

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `--source-record-id` | 是 | — | 要抽取的 SourceRecord ID |
| `--candidate-types` | 否 | 全部 | 逗号分隔：`faq,action_link,dynamic_query` |
| `--auto-approve` | 否 | — | 抽取后自动审核 + 发布 |

**review 参数：**

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `--candidate-id` | 是 | — | 候选 ID |
| `--approve` | 否 | — | 通过 |
| `--reject` | 否 | — | 拒绝 |
| `--reviewer` | 否 | `cli` | 审核人 |

**list 参数：**

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `--status` | 否 | `pending` | 状态过滤：pending / approved / rejected |

**环境变量：**

| 变量 | 说明 |
|---|---|
| `ORIONSTACK_EXTRACTION_PROVIDER` | 当前抽取 provider 名称，默认 `openai_compatible` |
| `ORIONSTACK_EXTRACTION_API_KEY` | 当前抽取 provider API Key 变量名（优先读取） |
| `ORIONSTACK_EXTRACTION_API_BASE` | 当前抽取 provider 的 OpenAI-compatible API 地址 |
| `ORIONSTACK_EXTRACTION_API_MODEL` | 当前抽取 provider 模型名 |
| `ORIONSTACK_QWEN_API_KEY` | 兼容旧配置时的回退 API Key 变量名 |
| `DASHSCOPE_API_KEY` | DashScope API Key（当前默认示例可回退读取），在 https://dashscope.aliyun.com 获取 |
| `ORIONSTACK_QWEN_API_BASE` | 兼容旧配置时的回退 API 地址 |
| `ORIONSTACK_QWEN_API_MODEL` | 兼容旧配置时的回退模型名 |

**E2E 验证记录：**

| 测试文档 | 内容长度 | 抽取结果 |
|---|---|---|
| 员工考勤与请假管理制度 | 967 字 | 9 FAQ → KnowledgeUnit |
| 差旅费用报销管理办法 | 509 字 | 8 FAQ + 2 ActionLink + 2 DynamicQuery |

---

### 测试与回归

#### `release-check.py`

发布前统一检查入口，适合本地和 CI 共用。默认执行全量后端测试、前端生产构建、生产 compose 配置校验。

```text
python scripts/release-check.py
python scripts/release-check.py --quick
python scripts/release-check.py --skip-compose
python scripts/release-check.py --check-only
```

参数：`--quick` / `--skip-backend` / `--skip-frontend` / `--skip-compose` / `--check-only`

说明：compose config 校验会使用受控环境变量并隐藏输出，避免本机 API key 出现在日志里。

GitHub Actions 工作流 `.github/workflows/release-check.yml` 会安装 Python / Node 依赖并执行同一个脚本，确保本地与 CI 使用同一检查入口。

#### `run-phase2-regression.py`

一键执行 Phase 2 专项回归（检索、chat flow、trace、hard cases）。

```text
python scripts/run-phase2-regression.py
python scripts/run-phase2-regression.py -k clarification
```

参数：`--check-only`，额外参数透传给 `pytest`。

#### `generate-provider-audit-samples.py`

生成 provider 主链审计样本（114 条），覆盖所有 seed FAQ。旧入口 `generate-cloud-audit-samples.py` 保留兼容。

```text
python scripts/generate-provider-audit-samples.py
```

#### `audit-provider-bad-cases.py`

审计当前 planner provider 主链 bad cases，按语料缺口、clarification 边界、evidence 阈值、planner 边界等队列归类。旧入口 `audit-cloud-bad-cases.py` 保留兼容。

```text
python scripts/audit-provider-bad-cases.py
python scripts/audit-provider-bad-cases.py --provider openai_compatible,llama_cpp
python scripts/audit-provider-bad-cases.py --include-local
```

#### `probe_llama_server.py`

探测本地 llama-server 连通性与响应质量。

```text
python scripts/probe_llama_server.py
```

---

### 运维

#### `backup-storage.py`

备份本地 `backend/app/storage/` 中的 JSONL 数据与上传文件，输出 `.tar.gz`，内含 `manifest.json`（文件列表、大小、SHA-256）。

```text
python scripts/backup-storage.py
python scripts/backup-storage.py --output-dir backups
python scripts/backup-storage.py --no-uploads
python scripts/backup-storage.py --check-only
```

参数：`--storage-root` / `--output-dir` / `--no-uploads` / `--check-only`

#### `restore-storage.py`

从 `backup-storage.py` 生成的 `.tar.gz` 恢复本地 storage。恢复会覆盖同名文件；默认拒绝执行，必须先预览或显式确认。

```text
python scripts/restore-storage.py backups/orionstack-storage-YYYYMMDDTHHMMSSZ.tar.gz --what-if
python scripts/restore-storage.py backups/orionstack-storage-YYYYMMDDTHHMMSSZ.tar.gz --confirm-restore
```

参数：`backup_path` / `--storage-root` / `--what-if` / `--confirm-restore`

生产 Docker Compose 使用 named volumes。推荐生产备份流程：

```text
docker compose --env-file .env.prod -f docker-compose.prod.yml stop backend
docker compose --env-file .env.prod -f docker-compose.prod.yml cp backend:/app/backend/app/storage ./prod-storage-snapshot
python scripts/backup-storage.py --storage-root ./prod-storage-snapshot --output-dir backups
docker compose --env-file .env.prod -f docker-compose.prod.yml start backend
```

备份覆盖 15 个存储目录，包括 extracted_faqs、import_batches、extraction_tasks 和 cleanup_tasks。恢复前会核对文件列表、大小与 SHA-256，并将文档上传路径改为恢复目标路径。生产恢复应直接使用容器中的 storage root，操作步骤见 [备份与恢复指南](../wiki/backup-restore.md)。当前脚本只覆盖文件存储，PostgreSQL 备份将在数据库接入阶段实现。

#### `rebuild-elastic-index.py`

重建 Elasticsearch 索引（清空并重新写入所有 KnowledgeUnit）。

```text
python scripts/rebuild-elastic-index.py
python scripts/rebuild-elastic-index.py --check-only
```

参数：`--check-only`

#### `clean-local-records.py`

清理本地问答记录文件（`chat_records.jsonl` 与 `feedback_records.jsonl`）。

```text
python scripts/clean-local-records.py --what-if
python scripts/clean-local-records.py --chat-only
python scripts/clean-local-records.py --feedback-only
```

参数：`--chat-only` / `--feedback-only` / `--check-only` / `--what-if`

#### `git-release.py`

交互式创建本地版本发布提交、git tag 并推送。默认会先运行 `python scripts/release-check.py --quick`，发布说明应先更新 `CHANGELOG.md`。

```text
python scripts/git-release.py --version 0.3.35 --commit-message "release: v0.3.35"
python scripts/git-release.py --version 0.2.0 --skip-push
python scripts/git-release.py --version 0.2.0 --skip-release-check
```

参数：`--version` / `--commit-message` / `--tag-prefix v` / `--remote origin` / `--skip-release-check` / `--skip-push` / `--check-only`

---

## Phase 3 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `ORIONSTACK_EXTRACTION_PROVIDER` | `openai_compatible` | 抽取 provider 名称；当前内置 `openai_compatible` / `qwen_api` / `llama_cpp` |
| `ORIONSTACK_EXTRACTION_API_KEY` | — | 抽取 provider API Key（优先读取） |
| `ORIONSTACK_EXTRACTION_API_BASE` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 抽取 provider OpenAI-compatible API 地址 |
| `ORIONSTACK_EXTRACTION_API_MODEL` | `qwen-plus` | 抽取 provider 模型名 |
| `ORIONSTACK_QWEN_API_KEY` | — | 兼容旧配置时的回退 API Key |
| `DASHSCOPE_API_KEY` | — | DashScope API Key（当前默认示例可回退读取） |
| `ORIONSTACK_QWEN_API_BASE` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 兼容旧配置时的回退 API 地址 |
| `ORIONSTACK_QWEN_API_MODEL` | `qwen-plus` | 兼容旧配置时的回退模型名 |
| `ORIONSTACK_ODOO_URL` | `http://localhost:8069` | Odoo 服务地址 |
| `ORIONSTACK_ODOO_DB` | `odoo` | Odoo 数据库名 |
| `ORIONSTACK_ODOO_UID` | `2` | Odoo 用户 ID |
| `ORIONSTACK_ODOO_PASSWORD` | — | Odoo 用户密码，通过 `.env` 或部署密钥注入 |
| `ORIONSTACK_DYNAMIC_QUERY_ADAPTER` | `mock` | 当前实现适配器选择：`mock` / `odoo` / 自定义 |

---

## Phase 2 历史启动矩阵

当前过渡基线使用 `local / false / false`，生产 Compose 不启动 ES。下一版本按根目录《OrionStack — DB + Vector + JEV 检索架构设计.md》实施，交付目标见 [下一版本计划](../docs/designs/4_postgresql_jev_architecture.md)。下表仅用于历史链路参考。

| 档位 | SEARCH_BACKEND | QUERY_PLANNER | FAST_TRACK | 说明 |
|---|---|---|---|---|
| 全开（推荐） | `elasticsearch` | `true` | `true` | planner → hybrid → rerank/evidence |
| 软回退 | `elasticsearch` | `false` | `true` | lexical-only |
| 硬回退 | `local` | `false` | `false` | 回到 Phase 1 默认链路 |

切换档位只改 `.env`，启动命令保持不变。

```text
python scripts/dev-backend.py
```

---

## prod 模式行为

`ORIONSTACK_APP_MODE=prod` 时：

- `debug_info` 不返回给前端
- `/api/chat/records` 与 `/api/chat/feedback` 返回 `404`
- 前端 `canDebug` 为 `false`

---

## 前端生产构建

```text
npm --prefix frontend run build
```

构建产物在 `frontend/dist/`，可直接通过 Nginx 等提供。

---

## 记录保留策略

后端自动截断最旧记录，默认保留 200 条：

- `ORIONSTACK_CHAT_RECORD_MAX_COUNT=200`
- `ORIONSTACK_FEEDBACK_RECORD_MAX_COUNT=200`
