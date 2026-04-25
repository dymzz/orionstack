# OrionStack 交接文档

> 版本：v1
> 日期：2026-04-25
> 目的：为下一任开发者/AI 提供项目全貌、当前状态、关键决策与上手路径

---

## 1. 项目是什么

OrionStack 是一个**企业知识助手 / 文档问答系统**。核心能力：

1. 用户上传文档（.txt / .md / .pdf / .docx），系统自动切块、索引
2. 用户提问，系统走 **Query Planner → Hybrid Retrieval → Rerank + Evidence → LLM 回答** 链路
3. FAQ 兜底：弱命中或无命中时回落到 FAQ 知识库
4. 回答附带引用（citation）、操作入口（action link）、实时状态查询（dynamic query）
5. 所有问答记录、反馈、trace、hard case 自动落盘

**技术栈 / 当前默认实现**：

- 后端：Python 3.12+ / FastAPI / Uvicorn
- 前端：Vue 3 + TypeScript + Vite + vue-router@4
- 检索：Elasticsearch 8.x（IK 分词）
- LLM：可替换的 OpenAI-compatible / 本地 provider（当前仓库默认示例为 DashScope `qwen-plus`）
- 外部系统：通过 `SystemAdapter` 接入多系统（当前已实现 `OdooAdapter` / `MockAdapter`，Odoo 只是其一）
- 存储：JSONL 文件（无数据库）
- 容器：Docker Compose（当前提供 Elasticsearch + Odoo 参考环境）

---

## 2. 三阶段演进

### Phase 1：最小可运行基线

- FAQ + 文档问答主链路
- 路由、retriever、guardrails、citation
- JSONL 存储

### Phase 2：检索增强（已完成）

- Query Planner（local provider）
- Fast Track（规则优化小 query）
- Hybrid Retrieval（lexical + vector + RRF）
- Rerank + Evidence
- Clarification（多意图追问）
- 8 域 FAQ 种子（114 条审计样本）

### Phase 3：SaaS 知识副本层（已完成）

- Step 1：SourceRecord / ImportBatch / ExtractionCandidate 数据层 + freshness + tombstone
- Step 2：ActionLink（"答 + 引 + 跳"体验）
- Step 3：DynamicQuery（SystemAdapter Protocol + 可插拔 adapter，当前已实现 OdooAdapter / MockAdapter）
- Step 4：抽取管线自动化（可替换 LLM provider → 候选 → 审核 → 发布）
- Step 5：Trace / Hard Case provenance + issue 自动分类

### 2026-04-24 架构边界收口

- `Qwen` / `DashScope` 已收敛为当前默认示例和兼容入口；主路径命名是 `openai_compatible`、`planner_api_*`、`extraction_api_*`
- `Odoo` 已收敛为 `SystemAdapter` 的当前适配器之一；动态查询主路径不再依赖 Odoo 语义
- 动态查询默认 adapter 为 `mock`；如需验证当前 Odoo 示例，显式设置 `ORIONSTACK_DYNAMIC_QUERY_ADAPTER=odoo`
- `DynamicQueryService` 不解释 Odoo XML-RPC `domain` 等外部系统方言，adapter-specific 查询参数停留在具体 adapter 内
- DynamicQuery 识别规则来自 JSONL 数据的 `detect_patterns`，代码里不再维护业务 regex 表
- ActionLink 的领域展示来自 JSONL 数据的 `business_domains`，代码里不再维护 domain → resource_type 映射
- 旧的 `qwen_api` provider/router 名只作为兼容别名或历史 trace 名保留

### 2026-04-26 DynamicQuery 双模式 smoke 收口

- 新增 `backend/tests/test_dynamic_query_adapter_modes.py`，固化默认 `mock` 与显式 `odoo` 两种 adapter 选择路径
- 默认模式 smoke 会在 Odoo factory 被触碰时直接失败，防止无配置启动重新隐式依赖 Odoo
- 显式 Odoo 模式 smoke 只验证 adapter 分支选择与 chat dynamic query 透传，不发真实 XML-RPC 请求、不需要真实凭据
- Step 3 DynamicQuery 回归基线更新为 43 个测试：39 个基础/边界测试 + 4 个双模式 smoke

### 2026-04-25 Provider bad-case 闭环收口

- Provider bad-case audit 已完成 P1.1-P1.5 闭环：当前没有仍处于 `open` 的 provider 主链 bad-case
- 最新审计基线：`traces=251`、`hard_cases=4`、`audit_resolution={'closed_by_later_success': 5}`
- `演示资料在哪里找` 已由后续成功 trace 命中 `sales-faq-003`
- `某个功能的定位是什么` 已由后续成功 trace 命中 `product-faq-004`
- `怎么请假` 已恢复为合理 clarification，命中 `hr-faq-001` / `hr-faq-003`
- 本轮修复保持 provider/adapter-neutral：没有补单条 FAQ，没有写 query 特判，没有把 Qwen/Odoo 写成项目目标

---

## 3. 仓库结构

```text
orionstack/
├── backend/
│   ├── main.py                         # FastAPI 应用入口
│   ├── app/
│   │   ├── api/routes/                 # REST 端点
│   │   │   ├── health.py               #   /healthz
│   │   │   ├── chat.py                 #   /api/chat/* + trace + hard case
│   │   │   ├── documents.py            #   /api/documents/*
│   │   │   └── extraction.py           #   /api/extraction/* (Phase 3)
│   │   ├── config/settings.py          # 环境变量配置
│   │   ├── extract/                    # 抽取层 (Phase 3)
│   │   │   ├── prompt_templates.py     #   抽取 prompt + JSON 解析
│   │   │   ├── extraction_service.py   #   当前配置的抽取 provider → 候选
│   │   │   ├── candidate_reviewer.py   #   审核 → 发布（3 类型）
│   │   │   └── llm_extractor.py        #   候选对象创建
│   │   ├── guardrails/                 # 输入归一化
│   │   ├── indexing/                   # ES 索引 + 健康检查
│   │   ├── observability/              # trace 生成
│   │   ├── query/                      # Query Planner
│   │   ├── retrieval/                  # 检索（lexical / hybrid / citation）
│   │   ├── routing/                    # 路由决策
│   │   ├── runtime/                    # 动态查询 (Phase 3)
│   │   │   ├── system_adapter.py       #   Protocol 定义
│   │   │   ├── odoo_adapter.py         #   Odoo XML-RPC 适配器（当前实现之一）
│   │   │   ├── mock_adapter.py         #   测试适配器
│   │   │   ├── adapter_factory.py      #   适配器工厂
│   │   │   ├── dynamic_query_service.py#   检测 → 判权 → 执行
│   │   │   └── trace.py               #   trace 辅助
│   │   ├── schemas/                    # Pydantic 请求/响应模型
│   │   ├── services/
│   │   │   ├── chat_service.py         # 核心问答服务
│   │   │   ├── document_service.py     # 文档上传解析
│   │   │   └── chunk_service.py        # 切块
│   │   ├── storage/                    # JSONL 存储层
│   │   │   ├── repositories/           #   各对象 repo
│   │   │   ├── models/                 #   dataclass 定义
│   │   │   ├── seed/                   #   FAQ 种子数据
│   │   │   ├── action_links/           #   action link JSONL
│   │   │   ├── dynamic_queries/        #   dynamic query JSONL
│   │   │   ├── extraction_candidates/  #   候选 JSONL
│   │   │   ├── source_records/         #   源记录 JSONL
│   │   │   └── ...                     #   其他数据目录
│   │   ├── sync/                       # 同步层 (Phase 3)
│   │   │   ├── sync_service.py         #   同步编排
│   │   │   ├── sync_parser.py          #   导出文件解析
│   │   │   ├── freshness.py            #   check_freshness()
│   │   │   ├── freshness_checker.py    #   FreshnessResult
│   │   │   └── tombstone_handler.py    #   逻辑删除传播
│   │   └── testing/                    # 测试工具
│   └── tests/                          # backend 回归测试
├── frontend/
│   └── src/
│       ├── App.vue                     # 壳：导航（问答 + 管理入口）
│       ├── main.ts                     # 入口：createApp + router
│       ├── router.ts                   # vue-router 路由表
│       ├── pages/
│       │   ├── chat/ChatPage.vue       # 问答主页面
│       │   └── admin/
│       │       ├── AdminLayout.vue     #   管理 tab 子导航
│       │       ├── TraceListPage.vue   #   trace 查询
│       │       ├── HardCaseListPage.vue#   hard case 列表
│       │       ├── ExtractionReviewPage.vue # 候选审核
│       │       └── AdminDebugPage.vue  #   调试记录
│       ├── components/
│       │   ├── chat/                   #   问答组件（AnswerCard, CitationList, ChatInput...）
│       │   └── common/                 #   通用组件（CollapsiblePanel）
│       ├── services/
│       │   ├── api.ts                  #   问答 API
│       │   └── admin.ts               #   管理 API
│       ├── styles/index.css            # 全局样式
│       └── types/
│           ├── chat.ts                 #   问答类型
│           └── admin.ts                #   管理类型
├── scripts/                            # 16 个脚本（见 scripts/README.md）
├── docs/                               # 设计 + 进度 + 字段文档
├── docker-compose.yml                  # Elasticsearch + Odoo 参考环境
├── .env.example                        # 环境变量参考
└── HANDOFF.md                          # 本文件
```

---

## 4. 如何启动

### 4.1 前置

- Python 3.12+（建议 `.venv`）
- Node.js 18+
- Docker（Elasticsearch；如需验证当前 OdooAdapter 示例，可再启动 Odoo）

### 4.2 启动 Elasticsearch

```bash
docker compose up -d elasticsearch
```

### 4.3 启动 Odoo（可选，用于验证当前 OdooAdapter 示例）

```bash
docker compose up -d odoo
```

### 4.4 一键开发启动

```bash
python scripts/dev-demo.py
```

浏览器打开 `http://localhost:5173`。

### 4.5 环境变量

必须配置的：

| 变量 | 用途 |
|---|---|
| `DASHSCOPE_API_KEY` | 当前 DashScope 示例所需的 API Key（Planner / 抽取管线） |

可选但重要的：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `ORIONSTACK_APP_MODE` | `demo` | `demo`/`dev` 显示调试面板；`prod` 隐藏 |
| `ORIONSTACK_SEARCH_BACKEND` | `elasticsearch` | `elasticsearch` 或 `local` |
| `ORIONSTACK_ENABLE_QUERY_PLANNER` | `true` | 是否启用 planner |
| `ORIONSTACK_ENABLE_FAST_TRACK` | `true` | 是否启用 fast track |
| `ORIONSTACK_DYNAMIC_QUERY_ADAPTER` | `mock` | 当前实现可选 `mock` 或 `odoo`，后续可扩展更多 adapter |
| `ORIONSTACK_ODOO_URL` | `http://localhost:8069` | 当前 OdooAdapter 示例地址 |
| `ORIONSTACK_ODOO_DB` | `odoo` | 当前 OdooAdapter 示例数据库 |
| `ORIONSTACK_ODOO_UID` | `2` | 当前 OdooAdapter 示例用户 ID |
| `ORIONSTACK_ODOO_PASSWORD` | — | 仅在使用 OdooAdapter 时通过环境变量注入 |

完整列表见 `.env.example`。

---

## 5. 测试

### 5.1 运行全部测试

```bash
.venv\Scripts\python.exe -m pytest backend/tests -q
```

当前项目环境基线：**353 passed, 21 skipped, 9 xfailed**（2026-04-26）。

裸 `python` 环境如果没有同步项目依赖，可能出现导入期缺包错误；当前 Windows 工作区回归请优先使用仓库内 `.venv`。live smoke 测试默认跳过，需要 API key / 网络时再显式运行。

### 5.2 Phase 3 专项测试

```bash
# Phase 3 基础链路：freshness / sync / trace / hard cases
.venv\Scripts\python.exe -m pytest backend/tests/test_phase3_*.py -q

# Phase 3 运行时组件：ActionLink / DynamicQuery / Adapter modes / Extraction
.venv\Scripts\python.exe -m pytest backend/tests/test_action_link.py backend/tests/test_dynamic_query.py backend/tests/test_dynamic_query_adapter_modes.py backend/tests/test_extraction.py -q
```

### 5.3 Phase 2 回归

```bash
.venv\Scripts\python.exe scripts/run-phase2-regression.py
```

---

## 6. 关键架构决策

### 6.1 三档检索

| 档位 | SEARCH_BACKEND | QUERY_PLANNER | FAST_TRACK |
|---|---|---|---|
| 全开（默认） | `elasticsearch` | `true` | `true` |
| 软回退 | `elasticsearch` | `false` | `true` |
| 硬回退 | `local` | `false` | `false` |

### 6.2 SystemAdapter Protocol

动态查询不直连单一系统，而是通过 `SystemAdapter` Protocol 解耦。Odoo 是当前已实现的一个适配器示例；新增外部系统只需：

1. 在 `backend/app/runtime/` 新建适配器文件
2. 实现 `name` 属性 + `fetch()` 方法
3. 在 `adapter_factory.py` 注册
4. 配置 `ORIONSTACK_DYNAMIC_QUERY_ADAPTER`

### 6.3 抽取管线

```
文档 → SourceRecord → 当前配置的抽取 provider → ExtractionCandidate → 人工审核 → 发布
                                                           ↓
                                              faq → KnowledgeUnit → ES
                                              action_link → ActionLinkRepo
                                              dynamic_query → DynamicQueryRepo
```

LLM 只产候选，不直接上线。`pipeline_cli.py` 支持 `--auto-approve` 但默认手动审核。

### 6.4 Freshness 链路

- `fresh_until` / `stale_after` 从 SourceRecord 同步时写入 KnowledgeUnit
- 检索时 `chat_service._check_hit_freshness()` 判定三态（fresh / warning / stale）
- stale 追加提示到回答文本（不是独立字段）
- trace 记录 `freshness_status`

### 6.5 Hard Case 自动分类

`_infer_issue_category()` 根据 `fallback_reason` + `source_record_id` 自动分类：

| 条件 | issue_category |
|---|---|
| 有 `source_record_id` | `extraction_drift`（优先） |
| `fallback_reason` 含 `no_evidence` | `retrieval_miss` |
| `fallback_reason` 含 `weak` | `evidence_weak` |
| `fallback_reason` 含 `ambiguous` | `retrieval_ambiguous` |
| `fallback_reason` 含 `routing` | `routing_mismatch` |
| 其他 | `unknown` |

### 6.6 前端路由

- `/` → ChatPage（纯问答）
- `/admin` → AdminLayout（tab 子导航）
  - `/admin/traces` — Trace 查询
  - `/admin/hard-cases` — Hard Case 列表
  - `/admin/extraction` — 候选审核
  - `/admin/debug` — 调试记录

管理页面与问答页面隔离，导航只有"问答"+"管理入口"两个入口。

---

## 7. 数据存储

全部使用 JSONL 文件，位于 `backend/app/storage/`：

| 目录 | 内容 |
|---|---|
| `seed/` | FAQ 种子数据 |
| `source_records/` | SourceRecord（原始导入记录） |
| `extraction_candidates/` | ExtractionCandidate（抽取候选） |
| `action_links/` | ActionLink（操作入口） |
| `dynamic_queries/` | DynamicQuery（动态查询定义） |
| `chat_records/` | 问答记录 |
| `feedback/` | 用户反馈 |
| `chunks/` | 文档切块 |
| `documents/` | 文档元数据 |
| `retrieval_traces/` | 检索 trace |
| `hard_cases/` | hard case |

---

## 8. 关键配置值

| 配置 | 值 | 说明 |
|---|---|---|
| `freshness_default_hours` | 72 | 新导入知识默认 fresh 时长 |
| `stale_default_hours` | 168 | 新导入知识默认 stale 阈值 |
| `ORIONSTACK_PLANNER_API_MODEL` | `qwen-plus` | 当前默认 planner 示例模型 |
| `ORIONSTACK_PLANNER_API_BASE` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 当前默认 planner OpenAI-compatible 示例地址 |
| `ORIONSTACK_EXTRACTION_API_MODEL` | `qwen-plus` | 当前默认抽取示例模型 |
| `ORIONSTACK_EXTRACTION_API_BASE` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 当前默认抽取 OpenAI-compatible 示例地址 |
| `ORIONSTACK_ELASTIC_INDEX` | `knowledge_units_v1` | ES 索引名 |
| `ORIONSTACK_CHAT_RECORD_MAX_COUNT` | 200 | 问答记录保留上限 |

---

## 9. 文档导航

| 想了解... | 读什么 |
|---|---|
| 系统全貌和快速上手 | `README.md` + 本文件 |
| Phase 1 实现基线 | `docs/designs/1_system_design.md` |
| Phase 2 检索升级 | `docs/designs/2_system_design.md` |
| Provider 主链坏例审计 | `docs/2_10_provider_bad_case_audit_kickoff.md` |
| Provider open 坏例 triage | `docs/2_12_provider_open_bad_case_triage.md` |
| Phase 3 知识副本层 | `docs/designs/3_system_design.md` |
| Phase 3 推进状态 | `docs/3_1_progress.md` |
| Phase 3 文件职责 | `docs/3_2_file_responsibilities.md` |
| Phase 3 字段定义 | `docs/3_3_field_definitions.md` |
| 文档接入边界 | `docs/designs/document_ingestion_boundary.md` |
| 文档库标准 | `docs/designs/document_library/` |
| 脚本用法 | `scripts/README.md` |
| 文档目录导航 | `docs/README.md` |

**推荐阅读顺序**（新开发者/AI 上手）：

1. 本文件（`HANDOFF.md`）
2. `README.md`（快速启动）
3. `docs/designs/3_system_design.md`（当前阶段设计）
4. `docs/3_1_progress.md`（推进状态）
5. `docs/3_2_file_responsibilities.md`（文件边界）

---

## 10. 已知问题

| 问题 | 状态 | 说明 |
|---|---|---|
| 裸 `python` 环境可能缺依赖 | 已知环境问题 | 项目依赖已在 `pyproject.toml`；以 `uv run ...` 为测试基线 |
| Odoo 19 字段差异 | 已处理 | `hr.leave` 用 `holiday_status_id`（不是 `holiday_type`） |
| `_build_clarification_response` 缺参 | 已修复 | ActionLink 集成时暴露并修复 |
| JSONL 存储 | 架构限制 | 无数据库，不适合高并发生产环境 |

---

## 11. 后续方向（未排优先级）

以下方向在 `3_system_design.md §4` 中标记为"暂缓"：

- 全自动发布（不经人工审核直接上线）
- 多租户 RBAC / ABAC 权限
- 实时同步（定时增量导入）
- 多系统适配器（钉钉、飞书、Zendesk、Confluence）
- 生产数据库（替换 JSONL）
- 认证系统（当前无用户登录）
- 前端 trace / hard case 管理 UX 改进
- 生产部署配置（容器化、CI/CD、监控）

---

## 12. Odoo 参考环境

| 项 | 值 |
|---|---|
| 地址 | `http://localhost:8069` |
| 数据库 | `odoo` |
| uid | `2` |
| 版本 | Odoo 19 |

认证信息不写入仓库，请通过本地 `.env` 或部署密钥系统注入 `ORIONSTACK_ODOO_PASSWORD` 等变量。

---

## 13. 一句话收口

**Phase 1-3 全部完成，provider bad-case 主链当前无 open 项，项目环境回归基线稳定（`.venv\Scripts\python.exe -m pytest backend/tests -q`：353 passed, 21 skipped, 9 xfailed），系统可一键启动（`python scripts/dev-demo.py`），文档体系完整（设计 + 进度 + 职责 + 字段四层），下一任接手者按本文件 + `docs/` 目录即可继续。**
