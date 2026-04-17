# OrionStack 第二阶段系统设计对应的文件级最小改造清单 v1

> 状态：执行清单 v1  
> 对应设计文档：`docs/designs/2_system_design.md`  
> 配套职责文档：`docs/2_2_file_responsibilities.md`  
> 配套字段文档：`docs/2_3_field_definitions.md`  
> 配套测试文档：`docs/2_4_test_strategy.md`  
> 目标：把第二阶段设计从“系统设计基线”收成“第一轮最小可执行改造范围”  
> 原则：**最小切入、分步替换、旧链路可回退、先数据统一再切检索**

---

## 1. 当前目标

本清单只解决一件事：

**把 Phase 2 的目标链路，拆成当前仓库中可落地的最小文件级改造范围。**

本文档不承担以下职责：

- 不重写 `2_system_design.md` 的系统设计正文
- 不替代 `2_2_file_responsibilities.md` 的文件职责边界说明
- 不替代 `2_3_field_definitions.md` 的字段语义解释
- 不替代 `2_4_test_strategy.md` 的测试分层与回归策略说明

当前不追求：

- 一次性切完整 Query Planner + Hybrid + Rerank + Clarification 全链路
- 直接删除旧 FAQ / document-first 代码
- 在第一轮就把所有接口彻底冻结到最终形态

当前优先级按 Phase 2 设计顺序收敛为：

1. 统一 Knowledge Unit 入库
2. 接 Elastic lexical-only 过渡链路
3. 再接 vector + RRF
4. 再接 rerank + evidence extraction
5. 最后接 clarification / 按需 API fallback

当前真实状态补充：

- Phase 2 已不是纯规划：仓库中已出现最小过渡实现
- 当前已落地的核心文件包括：
  - `backend/app/storage/repositories/knowledge_unit_repo.py`
  - `backend/app/retrieval/lexical_retriever.py`
  - `backend/app/indexing/elastic_indexer.py`
  - `backend/app/indexing/index_health_checker.py`
- `backend/app/config/settings.py` 已补入第二阶段最小配置项
- `backend/app/services/chat_service.py` 已接入第二阶段过渡性的 search backend 切换入口
- Phase 2 已补齐第一轮最小单测保护：
  - `backend/tests/test_phase2_settings.py`
  - `backend/tests/test_phase2_knowledge_unit.py`
  - `backend/tests/test_phase2_indexing.py`
  - `backend/tests/test_phase2_retrieval.py`
- 但默认链路仍未完全切换到第二阶段目标形态；planner / hybrid / rerank / trace 仍未落地

---

## 2. 文件级改造总原则

### 2.1 原则一：先并行，不先替换

第一轮改造以“并行引入新模块”为主，不直接拆旧链路。

含义：

- 新文件优先新增
- 旧文件先降职责，不先删除
- 默认主链路先保持可运行
- 新链路先通过 feature flag / 配置开关灰度启用

### 2.2 原则二：先收数据，再切检索

在 FAQ 与 document chunk 尚未统一成 Knowledge Unit 之前，不应直接切默认检索主链路。

### 2.3 原则三：先 lexical-only，再 hybrid

Elastic 接入第一轮先承接 lexical 检索，不立即把 vector、RRF、rerank 全部一起打开。

### 2.4 原则四：所有重型能力都必须可关闭

以下能力第一轮必须支持关闭：

- Query Planner 强改写
- vector retrieval
- rerank
- clarification mode
- online API fallback

---

## 3. 第一轮新增文件清单

以下文件分为两类：

- 已经在仓库中落地的第一轮过渡文件
- 尚未落地、但已在第二阶段中明确预留的文件位

### 3.0 当前已落地的第一轮文件

#### `backend/app/storage/repositories/knowledge_unit_repo.py`

当前状态：

- 已落地
- 已提供 FAQ / chunk -> `KnowledgeUnit` 的统一映射入口

#### `backend/app/retrieval/lexical_retriever.py`

当前状态：

- 已落地
- 已提供 Elasticsearch lexical-only 检索过渡实现

#### `backend/app/indexing/elastic_indexer.py`

当前状态：

- 已落地
- 已提供 `knowledge_units_v1` 的最小建索引与写入能力

#### `backend/app/indexing/index_health_checker.py`

当前状态：

- 已落地
- 已提供最小 Elasticsearch 连通性与索引状态检查

#### `backend/app/services/chat_service.py`

当前状态：

- 已出现第二阶段过渡接线
- 当前可通过 `settings.search_backend` 在本地链路与 Elasticsearch lexical-only 之间切换

#### `backend/app/config/settings.py`

当前状态：

- 已补入第二阶段最小配置开关
- 当前已覆盖 search backend / elastic / planner / fast track 的第一轮占位配置

### 3.1 当前尚未落地的 Query 与 LLM Provider

#### `backend/app/query/query_planner.py`
职责：

- 生成 `normalized_query`
- 生成 `domain_hint`
- 生成 `semantic_expansions`
- 生成 `lexical_terms`
- 执行 planner guardrails：
  - hard keyword locking
  - circuit breaker
  - drift guard
  - domain anchoring

第一轮要求：

- 可由本地实现或简单 provider 调用驱动
- 支持关闭 semantic expansion，仅保留 normalized + lexical_terms

#### `backend/app/llm/providers/base.py`
职责：

- 定义统一 provider 接口：
  - QueryPlannerProvider
  - RerankProvider
  - AnswerComposerProvider

#### `backend/app/llm/providers/ollama_provider.py`
职责：

- 承接本地 Ollama 模型调用
- 用于：
  - planner
  - 可选 rerank
  - 可选 composer

#### `backend/app/llm/providers/api_provider.py`
职责：

- 承接在线 LLM API
- 默认关闭，仅按需启用

---

### 3.2 第二阶段 Retrieval 层（已落地过渡 + 后续扩展）

#### `backend/app/retrieval/lexical_retriever.py`
职责：

- 承接 Elastic lexical-only 检索
- 作为当前 `retriever.py` 的过渡替代层
- 支持：
  - normalized_query
  - lexical_terms
  - metadata pre-filter

#### `backend/app/retrieval/vector_retriever.py`
职责：

- 承接 `question_vector` / `answer_vector` 双向量检索
- 支持：
  - normalized_query
  - semantic_expansions

第一轮要求：

- 允许关闭
- 不作为默认主路径强依赖

#### `backend/app/retrieval/hybrid_retriever.py`
职责：

- 组合 lexical + vector
- 应用 metadata pre-filter
- 执行 RRF 融合
- 输出：
  - lexical_hits
  - vector_hits
  - rrf_hits
  - 原始 retrieval signals

#### `backend/app/retrieval/reranker.py`
职责：

- 执行候选重排
- 判定：
  - accept_threshold
  - margin_threshold
- 输出：
  - top1_score
  - top2_score
  - accept / reject
  - conflict_detected

#### `backend/app/retrieval/evidence_extractor.py`
职责：

- 从 top 候选中提取 `evidence_spans`
- 若无明确证据，直接标记弱证据

---

### 3.3 第二阶段索引与数据层（已落地基座 + 后续目标）

#### `backend/app/storage/repositories/knowledge_unit_repo.py`
职责：

- 统一 FAQ 与 document chunk 的入库读取接口
- 提供：
  - FAQ -> Knowledge Unit 映射
  - chunk -> Knowledge Unit 映射
  - 历史回填入口

#### `backend/app/indexing/elastic_indexer.py`
职责：

- 建立 / 更新 `knowledge_units_v1`
- 处理：
  - 索引创建
  - 文档写入
  - question / answer 双向量写入
  - version / valid_from / valid_until 元数据同步

#### `backend/app/indexing/index_health_checker.py`
职责：

- 检查索引是否存在
- 检查字段与 dims 是否匹配配置
- 执行最小联通性查询
- 验证 Hybrid + RRF 查询路径可用

---

### 3.4 当前尚未落地的运行与观测层

#### `backend/app/observability/retrieval_trace.py`
职责：

- 统一生成 Retrieval Trace
- 包含：
  - raw_query
  - normalized_query
  - domain_hint
  - lexical_hits
  - vector_hits
  - rrf_hits
  - rerank_result
  - evidence_spans
  - final_status

#### `backend/app/testing/hard_cases_repo.py`
职责：

- 管理 hard cases
- 支持：
  - 用户负反馈样本回流
  - smoke set / regression set 读取

#### `backend/app/cache/query_cache.py`
职责：

- 提供轻量缓存能力
- key 至少包含：
  - normalized_query
  - domain_hint
  - access_scope
  - doc_version_snapshot

---

## 4. 第一轮需要改职责的旧文件

以下旧文件建议“改职责”，而不是立即删除。

### 4.1 `backend/app/services/chat_service.py`
当前问题：

- 仍围绕旧主链路组织
- 直接依赖旧 resolver / retriever / faq fallback 习惯

第一轮改造目标：

- 保持它继续作为主服务入口
- 但把内部流程改成可切换：

```text
normalize
-> optional query planner
-> fast track gate
-> retrieval adapter
-> optional rerank
-> optional answer composer
-> response builder
```

最小要求：

- 能通过配置在旧链路 / lexical-only / hybrid 之间切换
- 不直接把所有 phase2 逻辑硬编码在一个函数里

---

### 4.2 `backend/app/routing/rule_parser.py`
当前问题：

- 对 FAQ 短 query 有硬门效应

第一轮改造目标：

- 从“决定问题是否进入主链路”
- 降级为：
  - 空输入保护
  - 明显无效输入保护
  - 极少数安全拒答

第一轮不再要求它负责：

- 判断“请假”是否像 FAQ
- 决定 query 是否值得检索

---

### 4.3 `backend/app/retrieval/retriever.py`
当前问题：

- 是旧最小检索器
- 职责混合：
  - lexical
  - FAQ fallback
  - 阈值判定

第一轮改造目标：

- 不立刻删除
- 降级为：
  - 兼容旧链路的过渡实现
  - 或封装到 lexical-only adapter 中

原则：

- 旧链路仍可回退使用
- 不再继续向这个文件堆 phase2 新逻辑

---

### 4.4 `backend/app/storage/repositories/faq_repo.py`
当前问题：

- 仍是独立 FAQ 数据源读取器
- 容易继续强化“FAQ 一套、document 一套”的分裂结构

第一轮改造目标：

- 保留为 demo/mock provider
- 不再作为 phase2 主数据源中心
- 后续通过 `knowledge_unit_repo.py` 做统一映射

---

### 4.5 `backend/app/config/settings.py`
第一轮改造目标：

新增以下配置分组：

- Query Planner
- Elastic Search Backend
- Embedding dims
- Fast Track
- RRF 参数
- Rerank 阈值
- API fallback
- Index health check
- Cache / trace / smoke test

原则：

- 当前值可先占位
- 设计先冻结字段名与职责，不先冻结所有阈值数值

---

## 5. 第一轮建议保留不动的旧文件

这些文件第一轮建议不主动大改，只在必要时做兼容补充。

### `backend/app/api/routes/chat.py`
原因：

- API 入口尽量稳定
- Phase 2 第一轮不应先改外部路由形态

### `backend/app/schemas/request.py`
原因：

- 请求体第一轮不需要暴露复杂新参数
- 内部可先通过配置开关驱动 phase2

### `backend/app/schemas/document.py`
原因：

- 文档上传与基础 document 结构仍可继续使用
- 知识单元转换逻辑放到 repo / indexing 层处理

### `frontend/src/pages/chat/ChatPage.vue`
原因：

- 第一轮重点在后端链路
- 前端只需兼容新增状态字段，不先重做页面结构

---

## 6. 第一轮前后端最小契约改动

### 6.1 后端响应建议新增字段

第一轮建议在现有响应基础上最少补：

- `fallback_reason`
- `clarification_required`
- `conflict_detected`
- `cache_served`
- `trace_id`

### 6.2 前端第一轮只需识别的新增状态

前端第一轮不需要做完整新交互，只要能识别：

- `no_evidence`
- `low_confidence`
- `stale_policy_blocked`
- `conflict_requires_clarification`
- `model_timeout`
- `system_degraded`

---

## 7. 第一轮明确不做的文件/实现

以下内容明确不在第一轮落地：

### 7.1 不做的实现
- Elasticsearch + Milvus 双系统
- learned fusion
- 全库人工同义词平台
- 每次请求都跑的 Planner embedding self-check
- 多 Agent / workflow graph
- 全量 Clarification Mode 对话树
- 默认开启 online API fallback

### 7.2 不急着新增的文件
- 复杂多租户权限文件
- 独立的 workflow 编排器
- 多索引分治管理器
- 复杂 cache cluster 管理器

---

## 8. 第一轮文件级实施顺序

### Step 1：数据与索引基座
优先做：

- `knowledge_unit_repo.py`
- `elastic_indexer.py`
- `index_health_checker.py`

目标：

- 先把 FAQ / chunk 统一进 `knowledge_units_v1`
- 不切默认主链路

当前状态：

- 已基本落地
- `knowledge_unit_repo.py`、`elastic_indexer.py`、`index_health_checker.py` 已进入仓库
- 但是否作为团队默认运行链路使用，仍取决于部署配置与索引环境

### Step 2：lexical-only 过渡层
优先做：

- `lexical_retriever.py`
- `chat_service.py` 中的 retrieval adapter 切换

目标：

- 先用 Elastic 承接 lexical
- 保留旧 retriever 回退路径

当前状态：

- 已部分落地
- `lexical_retriever.py` 已进入仓库
- `chat_service.py` 已出现最小 retrieval adapter 切换
- 旧 `retriever.py` 仍保留作为本地兼容回退路径

### Step 3：Planner 最小可用
优先做：

- `query_planner.py`
- `ollama_provider.py`
- settings 中的 planner 配置

目标：

- 先输出：
  - normalized_query
  - domain_hint
  - lexical_terms
- semantic expansions 可先弱化

当前状态：

- 尚未落地
- 目前仅 `settings.py` 中预留了 planner 相关配置项

### Step 4：Hybrid + RRF
优先做：

- `vector_retriever.py`
- `hybrid_retriever.py`

目标：

- 小范围灰度：
  - 请假
  - 病假材料
  - 工资条
  - 调休

当前状态：

- 尚未落地

### Step 5：Rerank + Evidence
优先做：

- `reranker.py`
- `evidence_extractor.py`
- retrieval trace 落盘

当前状态：

- 尚未落地

### Step 6：缓存 / hard cases / API fallback
最后做：

- `query_cache.py`
- `hard_cases_repo.py`
- `api_provider.py`

当前状态：

- 尚未落地

---

## 9. 第一轮最小验收清单

第一轮文件级改造完成后，至少要满足：

1. FAQ 与 document chunk 已能映射成统一 Knowledge Unit
2. Elastic lexical-only 可独立跑通
3. `请假`、`病假材料` 这类 query 至少能在灰度链路中进入新检索
4. Retrieval Trace 可落盘
5. 旧链路仍可通过配置回退
6. phase2 新增文件职责清晰，不把逻辑重新堆回旧 `retriever.py`

按当前真实状态看：

- 第 1 条已具备最小落地基础
- 第 1 条对应的最小单测保护已补齐
- 第 5 条已具备最小配置回退基础
- 第 6 条已通过 `docs/2_2_file_responsibilities.md` 做职责收口
- 第 2 / 3 / 4 条仍不能视为已整体完成

---

## 10. 一句话收口

这份文件级最小改造清单 v1 的核心不是“把所有第二阶段能力一次性写完”，而是：

**把第二阶段系统设计拆成当前仓库里最小、可回退、可灰度、可执行的文件级落地范围。**
