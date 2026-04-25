# OrionStack

企业知识助手 / 文档问答最小可运行系统。

当前仓库提供的是一组可运行的默认实现，而不是把架构目标锁死在单一厂商上：检索默认走 Elasticsearch，LLM 侧当前示例主要使用 OpenAI-compatible 配置与 DashScope `qwen-plus`，动态查询通过 adapter 接外部系统，仓库里当前已实现 `OdooAdapter` 和 `MockAdapter`。这些都是现有实现与示例环境，不是项目边界本身。

## 能做什么

- 上传 `.txt` / `.md` / `.pdf` / `.docx` 文档
- 基于文档内容进行问答检索与引用返回
- FAQ 模式兜底（弱命中或无命中时自动回落）
- 问答记录与用户反馈自动落盘
- 开发态可查看最近问答记录与反馈

## 前置要求

- Python 3.12+（建议使用 `.venv`）
- Node.js 18+（仅开发和构建前端时需要，生产部署不需要）
- Docker（Elasticsearch 必需；如需验证当前 OdooAdapter 示例，可再启动 Odoo）

## 快速启动（默认全开档）

默认运行方式依赖 Elasticsearch，并进入：

- `planner`
- `fast track`
- `hybrid retrieval`
- `rerank + evidence`

先启动 Elasticsearch：

```bash
docker compose up -d elasticsearch
```

再启动应用：

```bash
python scripts/dev-demo.py
```

浏览器打开 `http://localhost:5173` 即可使用。

如果只是临时排障或验证旧链路，再手动切到回退档。

## Phase 2 检索增强

当前项目默认使用 phase 2 全开档，长期推荐按三档理解：

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

说明：

- planner 高置信时：进入 `lexical + vector + RRF -> rerank + evidence`
- planner 低置信时：回退到 `Fast Track + lexical-only`
- 若当前机器上的 Elasticsearch 不可用，优先先做软回退；只有仍无法稳定使用时再做硬回退

要启用 Elasticsearch 过渡检索：

### 1. 启动 Elasticsearch

```bash
docker compose up -d elasticsearch
```

### 2. 索引知识单元

```bash
# 启动后端后，调用索引接口（或通过启动脚本自动索引）
ORIONSTACK_SEARCH_BACKEND=elasticsearch python scripts/dev-backend.py
```

### 3. 切换检索后端

```bash
# 默认全开档
ORIONSTACK_SEARCH_BACKEND=elasticsearch ORIONSTACK_ENABLE_FAST_TRACK=true ORIONSTACK_ENABLE_QUERY_PLANNER=true ORIONSTACK_PLANNER_PROVIDER=local python scripts/dev-backend.py

# 软回退：回到 Elasticsearch lexical-only
ORIONSTACK_SEARCH_BACKEND=elasticsearch ORIONSTACK_ENABLE_FAST_TRACK=true ORIONSTACK_ENABLE_QUERY_PLANNER=false python scripts/dev-backend.py

# 硬回退：完整回到主线 1 默认链路
ORIONSTACK_SEARCH_BACKEND=local ORIONSTACK_ENABLE_QUERY_PLANNER=false ORIONSTACK_ENABLE_FAST_TRACK=false python scripts/dev-backend.py
```

### 4. 发布前最小 smoke

建议至少执行：

```bash
python -m pytest backend/tests/test_chat_flow.py backend/tests/test_document_flow.py backend/tests/test_phase2_settings.py backend/tests/test_phase2_knowledge_unit.py backend/tests/test_phase2_indexing.py backend/tests/test_phase2_retrieval.py backend/tests/test_phase2_planner.py
```

如果只是验证当前 phase 2 专项回归面，可以直接执行：

```bash
python scripts/run-phase2-regression.py
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

## 生产部署

### 1. 构建前端

> 以下步骤需要 Node.js 18+。构建完成后生产环境不再依赖 Node.js。

```bash
cd frontend
npm run build
```

构建产物在 `frontend/dist/`，由 Nginx 或其他静态文件服务提供。

### 2. 启动后端

```bash
python scripts/start-backend.py
```

默认以 `prod` 模式启动，不带热重载，监听 `127.0.0.1:8000`。

常用参数：

```bash
python scripts/start-backend.py --app-mode prod --host 0.0.0.0 --port 8000 --workers 2
```

### 3. 环境变量

所有配置通过环境变量控制。参见 `.env.example` 获取完整列表。

关键变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ORIONSTACK_APP_MODE` | `demo` | `demo`/`dev`：显示 Debug 与记录面板；`prod`：隐藏 |
| `ORIONSTACK_HOST` | `127.0.0.1` | 后端监听地址 |
| `ORIONSTACK_PORT` | `8000` | 后端监听端口 |
| `ORIONSTACK_CORS_ORIGINS` | 开发默认值 | 前端允许的来源，逗号分隔 |
| `ORIONSTACK_SEARCH_BACKEND` | `elasticsearch` | `elasticsearch`：默认全开档；`local`：硬回退到主线 1 默认链路 |
| `ORIONSTACK_ELASTIC_URL` | `http://localhost:9200` | ES 连接地址 |
| `ORIONSTACK_ELASTIC_INDEX` | `knowledge_units_v1` | ES 索引名称 |
| `ORIONSTACK_ENABLE_QUERY_PLANNER` | `true` | 默认开启 planner -> hybrid -> rerank/evidence 服务链 |
| `ORIONSTACK_ENABLE_FAST_TRACK` | `true` | 默认开启小 query 规则与 lexical 过渡优化 |
| `ORIONSTACK_PLANNER_PROVIDER` | `local` | Planner provider：`local` / `openai_compatible` / `qwen_api` / `llama_cpp` |
| `ORIONSTACK_PLANNER_API_BASE` | DashScope OpenAI-compatible 地址 | 当前 planner provider 的 API 地址 |
| `ORIONSTACK_PLANNER_API_MODEL` | `qwen-plus` | 当前 planner provider 的模型名 |
| `ORIONSTACK_EXTRACTION_PROVIDER` | `openai_compatible` | 抽取 provider：`openai_compatible` / `qwen_api` / `llama_cpp` |
| `ORIONSTACK_EXTRACTION_API_BASE` | DashScope OpenAI-compatible 地址 | 当前抽取 provider 的 API 地址 |
| `ORIONSTACK_EXTRACTION_API_MODEL` | `qwen-plus` | 当前抽取 provider 的模型名 |
| `ORIONSTACK_DYNAMIC_QUERY_ADAPTER` | `mock` | 动态查询适配器：`mock` / `odoo` / 自定义 |
| `ORIONSTACK_CHAT_RECORD_MAX_COUNT` | `200` | 问答记录保留上限 |
| `ORIONSTACK_FEEDBACK_RECORD_MAX_COUNT` | `200` | 反馈记录保留上限 |

兼容说明：旧的 `ORIONSTACK_QWEN_API_*`、`ORIONSTACK_QWEN_API_KEY`、`DASHSCOPE_API_KEY` / `QWEN_API_KEY` 仍可作为回退配置读取，但不再是唯一入口。

生产环境必须设置 `ORIONSTACK_CORS_ORIGINS`：

```bash
export ORIONSTACK_CORS_ORIGINS="https://app.example.com"
```

### 4. `prod` 模式行为

- Debug 信息不返回前端
- `/api/chat/records` 与 `/api/chat/feedback` 返回 404
- 前端不展示 Debug 面板与最近记录区

### 5. Nginx 参考

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
}
```

## 项目结构

```text
orionstack/
├── backend/                 # FastAPI 后端
│   ├── main.py              # 应用入口
│   └── app/
│       ├── api/routes/       # 路由（health, chat, documents）
│       ├── config/           # 配置（settings.py）
│       ├── guardrails/       # 输入归一化
│       ├── indexing/         # ES 索引与健康检查
│       ├── llm/providers/   # LLM Provider 抽象（占位）
│       ├── query/            # Query Planner（占位）
│       ├── retrieval/        # 检索（retriever, lexical_retriever, citation_mapper）
│       ├── routing/          # 路由决策
│       ├── runtime/          # trace 生成
│       ├── schemas/          # 请求与响应模型
│       ├── services/         # 业务服务
│       └── storage/          # 本地存储（JSONL + KnowledgeUnit）
├── frontend/                 # Vue 3 + Vite 前端
│   └── src/
│       ├── components/chat/  # 问答组件
│       ├── pages/chat/       # 问答主页面
│       ├── services/         # API 调用
│       ├── styles/           # 全局样式
│       └── types/            # 类型定义
├── scripts/                 # 启动与维护脚本
├── docs/                    # 设计与进度文档
├── docker-compose.yml       # ES + Odoo 示例容器配置
├── .env.example             # 环境变量参考
└── README.md
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/healthz` | 健康检查 |
| `POST` | `/api/chat/ask` | 问答请求 |
| `POST` | `/api/chat/feedback` | 提交反馈 |
| `GET` | `/api/chat/records` | 最近问答记录（仅 demo/dev） |
| `GET` | `/api/chat/feedback` | 最近反馈记录（仅 demo/dev） |
| `POST` | `/api/documents/upload` | 上传文档 |
| `GET` | `/api/documents` | 文档列表 |
| `DELETE` | `/api/documents/{id}` | 删除文档 |

## 脚本说明

| 脚本 | 用途 |
|------|------|
| `dev-backend.py` | 开发模式启动后端（带热重载） |
| `dev-frontend.py` | 启动前端开发服务 |
| `dev-demo.py` | 一键启动前后端开发环境 |
| `start-backend.py` | 生产模式启动后端（不带热重载） |
| `run-phase2-regression.py` | 一键执行 phase 2 专项回归 |
| `clean-local-records.py` | 清理本地记录文件 |
| `git-release.py` | 交互式版本发布 |

详细参数说明见 `scripts/README.md`。

## 数据存储

当前使用本地 JSONL 文件存储，数据位于 `backend/app/storage/data/`：

- `chat_records.jsonl` — 问答记录
- `feedback_records.jsonl` — 反馈记录
- `chunks.jsonl` — 文档切块
- `documents.jsonl` — 文档元数据

记录保留数量可通过环境变量配置，超出自增数量后自动截断最旧记录。
