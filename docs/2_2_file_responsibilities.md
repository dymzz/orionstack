# OrionStack 第二阶段文件职责说明 v1

> 对应设计文档：`docs/designs/2_system_design.md`  
> 配套进度文档：`docs/2_1_progress.md`  
> 配套字段文档：`docs/2_3_field_definitions.md`  
> 配套测试文档：`docs/2_4_test_strategy.md`

## 1. 文档目标

本文档用于配合 `docs/designs/2_system_design.md` 与 `docs/2_1_progress.md`，说明第二阶段**已落地文件**与**预留文件位**的职责边界。

本文档只解决一件事：

**避免第二阶段升级时，把新检索、新索引、新统一数据层的职责重新塞回第一阶段旧文件。**

本文档不承担以下职责：

- 不重写 `2_system_design.md` 的系统设计正文
- 不替代 `2_1_progress.md` 的推进顺序与状态说明
- 不替代 `2_3_field_definitions.md` 的字段语义解释
- 不替代 `2_4_test_strategy.md` 的测试分层与回归策略说明
- 不假设第二阶段目标链路已经一次性全部落地

---

## 2. 适用范围

本文档适用于第二阶段当前已经在仓库中出现、或已经明确预留文件位的能力，包括：

- FAQ 与 document chunk 统一为 `Knowledge Unit` 的数据层
- Elasticsearch lexical-only 过渡链路
- 第二阶段索引写入与索引健康检查
- 第二阶段配置开关与主服务过渡接线

当前**已实际落地**的第二阶段相关文件主要包括：

- `backend/app/storage/repositories/knowledge_unit_repo.py`
- `backend/app/retrieval/lexical_retriever.py`
- `backend/app/indexing/elastic_indexer.py`
- `backend/app/indexing/index_health_checker.py`

当前**已具备第二阶段过渡职责**、但不属于“纯新增文件”的文件包括：

- `backend/app/services/chat_service.py`
- `backend/app/config/settings.py`
- `backend/app/retrieval/retriever.py`
- `backend/app/storage/repositories/faq_repo.py`

---

## 3. 使用原则

### 3.1 先并行新增，不先回写旧链路

第二阶段新增能力优先通过新文件并行引入。

含义：

- 能新增文件承载的职责，不应继续堆到旧 `retriever.py`
- 能落在统一数据层的逻辑，不应继续散落在 FAQ / chunk 两套入口里重复实现

### 3.2 文件职责按“已落地”和“预留”分开理解

- 已落地文件：按当前真实代码职责维护
- 预留文件：只定义未来应放在哪里，不提前当作已实现模块使用

### 3.3 第二阶段重型能力必须可关闭

第二阶段相关文件职责应默认服从配置开关：

- lexical-only 可单独开启
- planner 可关闭
- hybrid / rerank / online fallback 不应默认硬依赖

### 3.4 服务入口稳定优先

第二阶段第一轮不优先改外部 API 形态。

因此：

- `chat.py` 仍保持稳定 API 入口
- 新能力优先在 `chat_service.py` 内部通过 adapter / 开关接入

---

## 4. 第二阶段已落地新增文件职责

## 4.1 统一数据层与索引层

### `backend/app/storage/repositories/knowledge_unit_repo.py`

职责：

- 作为第二阶段统一知识单元读取入口
- 把 FAQ 记录映射成 `KnowledgeUnit`
- 把 document chunk 映射成 `KnowledgeUnit`
- 提供统一的 `list_all / list_faq_units / list_chunk_units` 读取能力
- 为索引层与后续统一检索层提供统一数据视图

不负责：

- 不负责原始 FAQ 文件读取
- 不负责原始文档上传与切块
- 不负责检索排序、分数融合与回答生成
- 不负责直接决定哪些知识单元应被召回

### `backend/app/indexing/elastic_indexer.py`

职责：

- 维护 `knowledge_units_v1` 索引的最小建库与写入入口
- 负责索引 mapping 创建
- 负责将 `KnowledgeUnit` 批量写入 Elasticsearch
- 负责索引刷新与重建时的最小支持

不负责：

- 不负责知识单元如何生成
- 不负责查询路由与召回策略
- 不负责索引健康裁决之外的系统降级决策

### `backend/app/indexing/index_health_checker.py`

职责：

- 检查 Elasticsearch 连通性
- 检查目标索引是否存在
- 输出最小索引状态信息，例如 `connected / index_exists / doc_count / errors`
- 为第二阶段检索链路切换提供最小健康前置判断

不负责：

- 不负责自动修复索引
- 不负责建索引
- 不负责完整可观测平台或复杂巡检编排

## 4.2 第二阶段检索过渡层

### `backend/app/retrieval/lexical_retriever.py`

职责：

- 承接 Elasticsearch lexical-only 检索
- 面向 `knowledge_units_v1` 执行统一词法召回
- 支持 `normalized_query` 与 `lexical_terms`
- 支持最小 metadata filter：`business_domain / access_scope / lifecycle_status`
- 输出统一 `LexicalHit` 结构，供服务层后续处理

不负责：

- 不负责 Query Planner 生成
- 不负责 vector retrieval
- 不负责 RRF 融合
- 不负责 rerank 与 evidence extraction
- 不负责回答文本改写

## 4.3 第二阶段服务与配置接线层

### `backend/app/services/chat_service.py`

职责：

- 继续作为问答主服务入口
- 在不改外部 API 形态的前提下，承接第二阶段过渡接线
- 维护本地检索与 Elasticsearch lexical-only 检索之间的切换入口
- 统一串联：归一化、基础路由保护、检索、citation 映射、响应构建
- 持有 `KnowledgeUnitRepository` 作为第二阶段统一数据视图接入点

不负责：

- 不负责把 planner、hybrid、rerank 的完整实现全部内联在一个函数里
- 不负责成为第二阶段所有实验逻辑的堆放点
- 不负责替代索引层、retrieval 层、provider 层的独立职责

### `backend/app/config/settings.py`

职责：

- 维护第二阶段最小配置开关与环境变量入口
- 当前已承接：
  - `search_backend`
  - `elastic_url`
  - `elastic_index`
  - `elastic_use_ik_analyzer`
  - `enable_query_planner`
  - `planner_provider`
  - `planner_model`
  - `ollama_url`
  - `enable_fast_track`
- 为第二阶段重型能力保留“默认可关闭”的配置基础

不负责：

- 不负责实现 planner 本身
- 不负责实现检索逻辑本身
- 不负责承载复杂运行时状态

---

## 5. 第二阶段中保留但不应继续堆新逻辑的旧文件

### `backend/app/retrieval/retriever.py`

当前定位：

- 仍是当前本地链路与 document-first 的兼容实现
- 属于过渡层，不是第二阶段新能力的长期主承载文件

约束：

- 不应继续往其中堆 planner、hybrid、rerank、evidence 等第二阶段新逻辑
- 如有新检索模块，应优先新增独立文件承载

### `backend/app/storage/repositories/faq_repo.py`

当前定位：

- 保留为 mock / demo FAQ 数据源读取器
- 继续服务第一阶段兼容链路与第二阶段统一映射输入

约束：

- 不应再次演化成第二阶段统一数据中心
- FAQ 与 document 的统一视图应优先落在 `knowledge_unit_repo.py`

---

## 6. 第二阶段预留但当前尚未落地的文件位

以下文件位在第二阶段设计中是合理的，但当前仓库尚未真正落地。

当前要求是：

- 先在职责文档中冻结“该放哪类逻辑”
- 不把这些职责提前塞回旧文件

### 6.1 Query / Provider 层

预留文件位：

- `backend/app/query/query_planner.py`
- `backend/app/llm/providers/base.py`
- `backend/app/llm/providers/ollama_provider.py`
- `backend/app/llm/providers/api_provider.py`

未来应承载：

- planner 输出生成
- provider 统一抽象
- Ollama / API 调用封装

当前不应塞回：

- `chat_service.py`
- `settings.py`

### 6.2 Retrieval 扩展层

预留文件位：

- `backend/app/retrieval/vector_retriever.py`
- `backend/app/retrieval/hybrid_retriever.py`
- `backend/app/retrieval/reranker.py`
- `backend/app/retrieval/evidence_extractor.py`

未来应承载：

- 向量召回
- lexical + vector 融合
- rerank 判断
- evidence spans 抽取

当前不应塞回：

- `retriever.py`
- `lexical_retriever.py`

### 6.3 观测与测试层

预留文件位：

- `backend/app/observability/retrieval_trace.py`
- `backend/app/testing/hard_cases_repo.py`

未来应承载：

- 第二阶段 retrieval trace 落盘与回放
- hard cases 收集与回归样本管理

当前不应塞回：

- `feedback_repo.py`
- `chat_record_repo.py`

---

## 7. 前端边界说明

第二阶段当前尚未新增独立的前端检索升级文件树。

当前边界：

- 前端仍由现有 `ChatPage.vue` 与相关组件做最小兼容
- 不新增第二套 phase2 专用前端目录
- 若未来出现 clarification、trace、冲突解释等复杂交互，再新增专门组件文件承载

---

## 8. 一句话收口

**第二阶段文件职责的核心原则是：统一数据层、独立检索层、配置开关优先、旧链路可回退；新增能力优先落新文件，不再反向堆回第一阶段旧文件。**
