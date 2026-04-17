# OrionStack 第二阶段最小测试策略 v1

> 对应设计文档：`docs/designs/2_system_design.md`  
> 配套进度文档：`docs/2_1_progress.md`  
> 配套职责文档：`docs/2_2_file_responsibilities.md`  
> 配套字段文档：`docs/2_3_field_definitions.md`

---

## 1. 文档目标

本文档只解决一件事：

**为第二阶段当前已经落地的过渡模块，以及后续将继续落地的检索升级模块，定义一套最小、可执行、可回归的测试策略。**

本文档不承担以下职责：

- 不重写 `2_system_design.md` 的系统设计
- 不替代 `2_2_file_responsibilities.md` 的文件职责边界说明
- 不替代 `2_3_field_definitions.md` 的字段语义解释
- 不替代 `2_1_progress.md` 的推进状态说明
- 不替代详细测试用例文件本身
- 不引入重型 benchmark 平台或新的测试基础设施要求

---

## 2. 适用范围

本文档适用于第二阶段当前已经进入仓库、或明确将在后续接入的能力，包括：

- `Knowledge Unit` 统一数据层
- Elasticsearch lexical-only 过渡检索链路
- 第二阶段索引写入与索引健康检查
- 主服务中的 phase 2 search backend 切换入口
- 后续将接入的 planner / hybrid / rerank / trace / hard cases

当前仓库中**已落地并应纳入最小测试策略**的文件主要包括：

- `backend/app/storage/repositories/knowledge_unit_repo.py`
- `backend/app/retrieval/lexical_retriever.py`
- `backend/app/indexing/elastic_indexer.py`
- `backend/app/indexing/index_health_checker.py`
- `backend/app/services/chat_service.py`
- `backend/app/config/settings.py`

当前仓库中**已经存在的最小测试基础**主要包括：

- `backend/tests/test_chat_flow.py`
- `backend/tests/test_document_flow.py`

---

## 3. 使用原则

### 3.1 先保证最小可执行，再扩大覆盖

第二阶段测试当前不追求一次性覆盖 planner、hybrid、rerank、clarification、trace 全链路。

当前优先目标是：

- 已落地能力有最小回归保护
- 切换 search backend 时不至于无测试保护
- 关键升级不破坏第一阶段当前默认可运行链路

### 3.2 默认测试基线不依赖外部重型服务

默认本地回归基线应优先依赖：

- `pytest`
- 临时目录 / 本地 jsonl
- monkeypatch / stub

而不应默认要求：

- 在线 API
- 完整 benchmark 平台
- 复杂 observability 平台
- 永久在线 Elasticsearch 集群

### 3.3 测试分为 smoke 与 regression 两层

- **smoke**：修改后快速确认主链路还能跑通
- **regression**：对已落地边界做稳定断言，防止行为回退

### 3.4 当前已落地能力与目标能力分开验收

- 已落地模块：要求有明确测试入口或建议补齐的直接测试位
- 尚未落地模块：只先定义未来测试应覆盖什么，不提前写成“已具备测试保护”

---

## 4. 当前仓库已具备的测试基础

### 4.1 `backend/tests/test_chat_flow.py`

当前已覆盖的核心场景包括：

- FAQ 已知问题命中
- document-first 命中优先于 FAQ
- `document_ids` 范围限制下的检索行为
- 选中文档不命中时的 fallback
- 弱检索命中下的 fallback / FAQ 兜底
- 基础安全拒答
- debug 信息在不同运行模式下的暴露边界
- citation 最小结构与最小回源定位断言

当前意义：

- 它已经承担了第二阶段之前主链路的最小保护带
- 后续 phase 2 过渡接线若破坏默认链路，应首先在这里暴露

### 4.2 `backend/tests/test_document_flow.py`

当前已覆盖的核心场景包括：

- 文档上传
- 文档列表
- 文档删除
- 文档解析与切块落盘
- chunk 最小回源元数据
- citation 回源定位字段
- 非法后缀拦截

当前意义：

- 它提供了 document chunk -> citation -> retrieval 之前的数据基座保护
- 后续 phase 2 若继续统一 document chunk 为 `Knowledge Unit`，这里仍是上游数据正确性的最小保障

### 4.3 当前空缺但已明确存在测试价值的 phase 2 模块

当前尚缺少专门测试文件或明确断言的模块主要包括：

- `knowledge_unit_repo.py`
- `lexical_retriever.py`
- `elastic_indexer.py`
- `index_health_checker.py`
- `chat_service.py` 在 `search_backend = elasticsearch` 下的最小切换行为

---

## 5. 第二阶段最小 Smoke 策略

## 5.1 当前必须可执行的本地 smoke

每次涉及以下改动之一时，至少应执行一轮本地 smoke：

- `chat_service.py`
- `retriever.py`
- `lexical_retriever.py`
- `knowledge_unit_repo.py`
- `document_service.py`
- `chunk_repo.py`
- `settings.py`
- 任何会影响 citation、fallback、debug_info、document scope 的修改

当前建议命令：

```bash
python -m pytest backend/tests/test_chat_flow.py backend/tests/test_document_flow.py
```

当前 smoke 至少应覆盖：

1. FAQ 命中仍然正常
2. document-first 命中仍然正常
3. 选中文档范围限制仍然生效
4. 弱命中时 fallback 仍然正常
5. unsafe 请求仍然拒答
6. 文档上传 / 列表 / 删除仍然可用
7. citation 最小结构与最小回源字段未退化

### 5.2 Phase 2 环境就绪时的可选 smoke

当 Elasticsearch 环境可用时，建议额外执行一轮 phase 2 过渡 smoke：

目标：

- 确认 `search_backend = elasticsearch` 时主链路能切到 lexical-only 检索
- 确认索引可连通、可写入、可查询
- 确认默认链路仍可回退

当前建议覆盖：

1. `IndexHealthChecker.check()` 返回基本可用状态
2. `ElasticIndexer.ensure_index()` 可成功建索引
3. `ElasticIndexer.index_units()` 可成功写入最小知识单元
4. `LexicalRetriever.search()` 能返回至少一个有效结果
5. `ChatService` 在 `search_backend = elasticsearch` 时能进入过渡检索路径

说明：

- 这层 smoke 当前应视为**环境可选项**
- 不应反向变成所有本地开发的默认前置门槛

---

## 6. 第二阶段最小 Regression 策略

## 6.1 当前必须稳定的 regression 边界

以下边界一旦已落地，就不应在后续 phase 2 改造中被静默破坏：

### A. 当前默认主链路边界

必须稳定：

- FAQ 已知 query 命中
- document-first 与 FAQ fallback 的相对优先级
- fallback / refused / ok 的基本响应契约
- debug_info 在 demo/dev 与 prod 下的暴露边界

### B. 文档链路边界

必须稳定：

- 文档上传成功后有最小元数据
- chunk 落地后有最小回源字段
- `source_label / source_locator / snippet` 不退化
- 文档删除时元数据与 chunk 一起清理

### C. 第二阶段过渡边界

必须稳定：

- `settings.py` 中已有的 phase 2 开关不应被静默删除或改名
- `KnowledgeUnit` 最小字段集合不应随意漂移
- lexical-only 已实际使用的 filter 字段不应无提示失效
- `search_backend` 切换不应破坏 local 默认链路

## 6.2 建议新增的 regression 测试位

当继续推进 phase 2 时，建议优先新增以下测试文件：

### `backend/tests/test_phase2_knowledge_unit.py`

建议覆盖：

- FAQ -> `KnowledgeUnit` 映射
- chunk -> `KnowledgeUnit` 映射
- `list_all / list_faq_units / list_chunk_units` 行为
- 默认字段与最小兼容值

### `backend/tests/test_phase2_retrieval.py`

建议覆盖：

- `LexicalRetriever` 的 query 为空行为
- `LexicalRetriever` 的 `lifecycle_status = active` 默认过滤
- `business_domain / access_scope / lifecycle_status` filter 拼装行为
- `search_backend` 切换后的最小服务行为

说明：

- 其中一部分可通过 stub / monkeypatch 完成
- 不要求所有 regression 都依赖真实 Elasticsearch 实例

### `backend/tests/test_phase2_indexing.py`

建议覆盖：

- `ElasticIndexer.ensure_index()` 的 mapping 选择逻辑
- `ElasticIndexer.index_units()` 的最小写入流程
- `IndexHealthChecker` 的 `connected / index_exists / doc_count / errors` 输出结构

---

## 7. 与 `2_system_design.md` 的关系

`2_system_design.md` 对第二阶段测试提出了更高目标，包括：

- Hybrid Smoke Test Set
- Retrieval Trace 契约
- hard cases 样本池
- 发布前门槛
- 回滚触发条件

但当前仓库的最小测试策略应分层理解：

### 7.1 当前已可执行层

当前真正应执行并维护的，是：

- 本地 `pytest` 主链路 smoke
- 文档链路 regression
- 对 phase 2 已落地模块的最小单测补齐

### 7.2 后续目标测试层

只有当以下能力真正落地后，才应把对应测试升级为默认要求：

- planner 输出
- hybrid retrieval
- rerank + evidence
- retrieval trace 落盘
- hard cases 样本回流
- cache / version snapshot / stale policy 校验

---

## 8. 当前建议的最小发布门槛

在第二阶段继续落地、但尚未切默认链路之前，当前建议门槛为：

1. `backend/tests/test_chat_flow.py` 通过
2. `backend/tests/test_document_flow.py` 通过
3. 若修改涉及 phase 2 Elasticsearch 过渡链路，则补一轮环境可用下的 elastic smoke
4. 不允许因为 phase 2 新能力而破坏当前 local 默认链路
5. 不允许因为 phase 2 字段或职责扩展而让 citation / debug_info / fallback 契约无声漂移

---

## 9. 当前明确不做的事

本文档当前明确不要求：

- 新增前端测试框架
- 引入完整 benchmark 平台
- 为每个 query 建大规模评测集
- 把 smoke cases 扩展成重型测试矩阵
- 在未落地 planner / hybrid / rerank 时伪造完整 phase 2 测试通过结论

---

## 10. 一句话收口

**第二阶段最小测试策略的目标不是提前建设完整评测平台，而是先为已落地过渡模块建立 smoke 与 regression 保护带，并为后续 planner / hybrid / rerank / trace 的测试位预留清晰入口。**
