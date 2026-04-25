# Scripts Usage

`scripts/` 目录当前包含本地开发、数据种子、抽取管线与最小发布辅助脚本。

所有 Python 脚本统一从仓库根目录运行：

```text
python scripts/<script_name>.py
```

配置切换统一修改 `.env`；不要在命令前拼接临时环境变量。

---

## 前置要求

- 已安装 `python`（建议 3.12+）
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

#### `rebuild-elastic-index.py`

重建 Elasticsearch 索引（清空并重新写入所有 KnowledgeUnit）。

```text
python scripts/rebuild-elastic-index.py
```

#### `clean-local-records.py`

清理本地问答记录文件（`chat_records.jsonl` 与 `feedback_records.jsonl`）。

```text
python scripts/clean-local-records.py --what-if
python scripts/clean-local-records.py --chat-only
python scripts/clean-local-records.py --feedback-only
```

参数：`--chat-only` / `--feedback-only` / `--check-only` / `--what-if`

#### `git-release.py`

交互式创建本地版本发布提交、git tag 并推送。

```text
python scripts/git-release.py --version 0.2.0 --commit-message "feat: Phase 3 extraction pipeline"
python scripts/git-release.py --version 0.2.0 --skip-push
```

参数：`--version` / `--commit-message` / `--tag-prefix v` / `--remote origin` / `--skip-push` / `--check-only`

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

## Phase 2 推荐启动矩阵

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
