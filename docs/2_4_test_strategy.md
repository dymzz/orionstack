# OrionStack 第二阶段测试策略 v2

> 对应设计文档：`docs/designs/2_system_design.md`  
> 配套进度文档：`docs/2_1_progress.md`  
> 配套职责文档：`docs/2_2_file_responsibilities.md`  
> 配套字段文档：`docs/2_3_field_definitions.md`  
> 目标：把第二阶段测试从“已有 phase 2 单测位”推进到“真实链路稳定 + 各领域清洗文档 fixture 化 + hard-case 持续回归”。

---

## 1. 文档目标

本文档只回答第二阶段当前应如何测试，不扩写远期测试体系，不讨论通用测试教科书。

当前目标不是把整个仓库做成重型 TDD，而是把**最容易漂移的行为层先锁住**，再让新增的各领域清洗文档进入长期回归资产。

---

## 2. 当前测试策略总原则

第二阶段当前建议采用三层策略：

1. **Test-First**
   - 用于行为边界、返回契约、检索接收条件、反馈闭环等高漂移模块。
   - 这层的目标是：系统表面能跑时，也不能静默漂移。

2. **Smoke**
   - 用于启动、索引、文档解析、接口健康检查等“通不通”问题。
   - 这层的目标是：保证环境与主链路基本连通。

3. **Hard-Case Regression**
   - 用于真实失败样本、泛问法、模糊问法、跨域误路由、弱命中等边界问题。
   - 这层的目标是：把线上/联调失败逐步沉淀成稳定回归集。

---

## 3. 当前真实链路对应的测试分层

### 3.1 优先做 Test-First 的文件与能力

以下能力一旦漂移，系统通常不会立刻报错，但行为会越来越不稳定，因此应优先 test-first：

#### A. 主问答链路编排

- `backend/app/services/chat_service.py`
- `backend/app/api/routes/chat.py`

要锁住的内容：

- `normalize_query -> route -> planner -> retrieval -> rerank -> response` 的主链路不静默漂移
- `response_status = ok / fallback / refused / system_error` 的触发边界稳定
- `trace_id`、`citations`、`debug_info`、`clarification` 的最小返回契约稳定
- feedback 写入、hard-case 生成、retrieval trace 记录的闭环不丢

#### B. 路由与 query planning

- `backend/app/routing/rule_parser.py`
- `backend/app/routing/resolver.py`
- `backend/app/query/query_planner.py`

要锁住的内容：

- 空输入 / 非 FAQ 输入 / 正常输入的最小路由边界
- `route_result` 与 `route_confidence` 的行为稳定
- `domain_hint` 的域识别稳定
- `lexical_terms` 的补词行为稳定，尤其是 HR 类 query 的扩词不回退

#### C. 检索与接收判定

- `backend/app/retrieval/lexical_retriever.py`
- `backend/app/retrieval/vector_retriever.py`
- `backend/app/retrieval/hybrid_retriever.py`
- `backend/app/retrieval/evidence_extractor.py`
- `backend/app/retrieval/reranker.py`
- `backend/app/retrieval/citation_mapper.py`

要锁住的内容：

- lexical / vector / hybrid / rerank 的排序边界不静默变化
- FAQ 与 document 的相对得分方向稳定
- `evidence_confidence`、`rerank_accept`、`reject_reason` 等接收判定不漂
- `source_label / source_locator / snippet / citation_id` 不退化

#### D. 反馈、trace 与 hard-case 闭环

- `backend/app/storage/repositories/feedback_repo.py`
- `backend/app/observability/retrieval_trace.py`
- `backend/app/testing/hard_cases_repo.py`

要锁住的内容：

- feedback 能通过 `trace_id` 正确关联已有 ask 记录
- retrieval trace 能稳定记录与回放关键调试字段
- hard-case 能按 `trace_id` upsert，而不是重复污染
- 最近记录 / 最近 hard-case 的读取逻辑不反向破坏现有排查体验

#### E. 前后端返回契约

- `backend/app/schemas/request.py`
- `backend/app/schemas/response.py`
- `frontend/src/types/chat.ts`

要锁住的内容：

- `debug_info` 中当前已经落地的字段不静默删除或改名
- `citations` 与前端展示字段不失配
- `clarification` 与 `response_status` 组合关系稳定

---

### 3.2 只保留 Smoke 的文件与能力

以下能力当前重点是“可用”，不值得先投入大量细粒度行为测试：

#### A. 启动与健康检查

- `backend/main.py`
- `backend/app/api/routes/health.py`
- `scripts/dev-backend.py`
- `scripts/dev-demo.py`
- `scripts/start-backend.py`

Smoke 只要求：

- 后端可启动
- `/healthz` 正常
- demo/dev 主链路可跑通

#### B. ES 环境与索引基础能力

- `backend/app/indexing/index_health_checker.py`
- `backend/app/indexing/elastic_indexer.py`

Smoke 只要求：

- ES 可连通
- 索引可创建
- 最小知识单元可写入
- 索引写入后可被检索链路消费

#### C. 文档解析与切块基础能力

- `backend/app/services/document_parser.py`
- `backend/app/services/chunk_service.py`
- `backend/app/services/document_service.py`

Smoke 只要求：

- `.txt / .md / .pdf / .docx` 最小解析链路可跑
- 切块结果非空
- 文档上传 / 列表 / 删除的主操作可用

---

## 4. 当前必须稳定的 Regression 边界

### 4.1 默认主链路边界

必须稳定：

- FAQ 已知 query 命中
- fallback / refused / ok / system_error 的基本响应契约
- `debug_info` 在 demo/dev 与 prod 下的暴露边界
- `search_backend` 切换不破坏 local 默认链路

### 4.2 第二阶段检索边界

必须稳定：

- `domain_hint` 与 `lexical_terms` 的已有扩展策略不被静默改坏
- lexical-only、hybrid、hybrid-rerank、clarification 的切换边界清晰
- `lifecycle_status = active` 的默认过滤不失效
- `source_label / source_locator / snippet` 始终保留最小回源能力

### 4.3 文档链路边界

必须稳定：

- 文档上传成功后有最小元数据
- chunk 落地后有最小回源字段
- 文档删除时元数据与 chunk 一起清理
- 清洗后的文档 fixture 在测试中可稳定复用，不与运行时临时数据混用

### 4.4 闭环排查边界

必须稳定：

- `trace_id` 贯穿 ask / feedback / trace / hard-case
- feedback 可生成 hard-case
- hard-case 可持续追加并支持去重更新
- retrieval trace 可作为 replay 与坏例复盘输入

---

## 5. 当前已落地的最小测试位

根据现有文档，第二阶段已经有一批最小 phase 2 测试位，至少包括：

- `backend/tests/test_phase2_settings.py`
- `backend/tests/test_phase2_knowledge_unit.py`
- `backend/tests/test_phase2_retrieval.py`
- `backend/tests/test_phase2_query_planner.py`
- `backend/tests/test_phase2_indexing.py`

这些测试位不应删除，后续应继续作为第二阶段最小保护带。

`backend/tests/test_phase2_retrieval.py` 当前已就 strong lexical winner 通用融合规则绑定如下行为断言：

- `test_hybrid_retriever_keeps_dominant_lexical_faq_ahead_of_noisy_vector_hits`
  - 原 FAQ 强胜者保护不回归
- `test_hybrid_retriever_keeps_dominant_lexical_document_chunk_ahead_of_noisy_vector_hits`
  - document_chunk 强胜者同享同一条通用保护
- `test_hybrid_retriever_keeps_dominant_lexical_winner_when_runner_up_is_different_source_kind`
  - 顶位与次位跨 source_kind 时通用规则仍触发
- `test_hybrid_retriever_protects_lonely_strong_lexical_winner`
  - 单条强胜者在 fusion 层被识别为 dominant，给未来融合收紧留出前置保护点
- `test_hybrid_retriever_does_not_find_dominant_lexical_winner_below_absolute_floor`
  - 低分孤点不触发 dominance bonus，防止 rare-term fluke 反向干扰

对称地，vector 侧也绑定了同一套通用规则的行为断言：

- `test_hybrid_retriever_keeps_dominant_vector_winner_ahead_of_noisy_lexical_hits`
  - strong vector winner 不被双榜都在的 noisy lexical 候选反超
- `test_hybrid_retriever_protects_lonely_strong_vector_winner`
  - 单条强 vector winner 在 fusion 层被识别为 dominant
- `test_hybrid_retriever_does_not_find_dominant_vector_winner_below_absolute_floor`
  - 低分向量孤点不触发 dominance bonus，防止低相似度 fluke 反向干扰

这八条断言的共同约束：**只基于 score / rank / count 判断，不依赖任何领域字段或 unit_id 列表**；lexical 与 vector 两侧共用 `_find_dominant_side_winner_id` 抽象，只通过 `ratio` 与 `absolute_floor` 两个参数区分量级。

此外，`test_phase2_retrieval.py` 还绑定两条对称的 **end-to-end 断言**，把 fusion 规则的有效性贯穿整条服务链：

- `test_chat_service_propagates_lexical_dominance_bonus_through_rerank_to_response`
  - 覆盖 lexical 侧：lexical rank 1 孤点 winner + 双榜 noisy rival
- `test_chat_service_propagates_vector_dominance_bonus_through_rerank_to_response`
  - 覆盖 vector 侧：vector rank 1 孤点 winner + 双榜 noisy rival

两条断言的共同结构：

- 使用真实 `HybridRetriever`，fake lexical / vector / planner 驱动 `ChatService`
- 无对应 bonus 时：双榜 noisy 候选在 fusion rank 1，正确候选被挤出 rerank top_n，最终触发 `no_evidence` fallback
- 有 bonus 时：正确候选稳居 fusion rank 1，rerank 与 evidence 接力，`ChatAskResponse.answer` 与 `citations[0]` 对应预期单元
- 断言**不测单一层**，而是直接验证 fusion 规则能落到用户可见的 answer 上

fusion 与 rerank 的关系边界：**rerank 的 accept/reject 由 `evidence_confidence >= 0.15` 决定，不看 fusion score 绝对值**。因此 `+0.02` 级别的 dominance bonus 只影响候选是否进入 rerank top_n 窗口，不会翻转 accept/reject。这也是当前不必对 rerank 阈值做“跟随 fusion 变化”的重校的原因。

数据流纪律（与 fusion 规则互补的上游防线）：

- `test_chat_service_propagates_planner_domain_hint_to_both_lexical_and_vector_sides`
  - 断言 `planner.domain_hint == "hr"` 时 `fake_lexical_retriever.calls[0]["business_domain"] == "hr"` 且 `fake_vector_retriever.calls[0]["business_domain"] == "hr"`
  - 用真实 `HybridRetriever` 包裹 fake lexical / vector 两侧，单条测试同时覆盖 `ChatService → HybridRetriever` 与 `HybridRetriever → 两侧 retriever` 两跳 kwarg 透传
  - 动机：数据流 narrow 与 fusion bonus 是互补关系 —— narrow 在召回阶段砍掉跨域噪声，bonus 在融合阶段保护 rank 1；若 narrow 失守，bonus 撑不住所有回流噪声

fusion dominance 可观测性（为未来 trace 回放铺观察点）：

- `test_hybrid_retriever_records_dominance_attribution_per_candidate_on_hybrid_hits`
  - 单层断言：`HybridHit.lexical_dominance_applied` / `vector_dominance_applied` 是**每候选**的 bool，不是全局标记
  - 验证赢家被标记为 True、普通候选为 False、vector 侧在 floor 以下不会误标记
- `test_chat_service_surfaces_fusion_dominance_attribution_in_debug_rrf_topk`
  - 贯穿断言：`_fuse_hits` 设置的归因必须活过 `rrf_rank` 二次排序与 `_summarize_hybrid_hits` 投影，并落到 `response.debug_info.rrf_topk[i]` 的同名字段；由 `api/routes/chat.py` 的 `model_dump()` 自动流入 `retrieval_trace.jsonl`
  - 反向防误标：即使是“无 bonus 时会赢、有 bonus 时被挤下去”的 noisy 竞争者，`lexical_dominance_applied` 也必须是 False，防止未来 refactor 把归因误套在所有候选上

当前建议是在保留这些测试位的前提下，再补三类测试：

1. 链路行为测试  
2. 各领域清洗文档 fixture 测试  
3. hard-case 回归测试  

---

## 6. 新增：各领域清洗文档进入测试资产

你当前已经明确：`backend/tests` 新加入了**各领域清洗过的文档**。

这一步的意义不是“多了几份测试素材”，而是第二阶段测试边界发生了升级：

```text
以前：测试主要围绕 FAQ mock / 最小知识单元 / 单个域样本
现在：测试可以围绕多业务域清洗文档的真实输入形态，做跨域、跨问法、跨检索模式回归
```

### 6.1 当前对这些清洗文档的定位

这些文档当前最适合作为：

- fixture
- 领域回归样本
- 检索验证样本
- clarification / fallback / no_evidence 验证样本
- 新 hard-case 的对照基线

不建议把这些清洗文档当成：

- 运行时临时上传数据的替代品
- 所有测试都直接读取的大杂烩数据池
- 与线上 hard-case 混写的同一个数据源

### 6.2 各领域清洗文档应承担的测试职责

新增的各领域清洗文档，建议承担以下职责：

#### A. 领域命中验证

每个业务域至少验证：

- 该域典型 query 可进入对应 domain hint 或保持中性但仍可正确命中
- 不同域 query 不会轻易错命中到相邻业务域

#### B. 领域内自然问法验证

每个业务域至少验证：

- 标准问法
- 更口语化问法
- 更短的泛问法
- 同义改写问法

#### C. 领域内弱命中 / no_evidence 验证

每个业务域至少验证：

- 不存在明确证据时，系统能 fallback 或进入 clarification
- 不会把“有一点像”的文档强答成正确答案

#### D. 领域回源字段验证

每个业务域至少验证：

- citation 中仍保留 `source_label / source_locator / snippet`
- chunk / FAQ / knowledge unit 回源字段完整
- 文档进入检索后不会丢失最小来源信息

---

## 7. 新增后的测试结构建议

### 7.1 保留现有 phase 2 测试位

继续保留：

- settings
- knowledge_unit
- retrieval
- query_planner
- indexing

这些文件承担“系统基础行为最小保护带”。

### 7.2 新增按职责划分的测试层

建议在 `backend/tests` 中按职责新增三类测试：

#### A. 行为层测试

建议方向：

- `test_chat_flow_phase2.py`
- `test_chat_contract_phase2.py`
- `test_feedback_hard_cases_phase2.py`

主要覆盖：

- ask -> response
- ask -> feedback -> hard-case
- debug_info / response_status / citations 契约

#### B. 各领域文档 fixture 测试

建议方向：

- `test_domain_documents_retrieval.py`
- `test_domain_documents_clarification.py`
- `test_domain_documents_citation.py`

主要覆盖：

- 多业务域清洗文档进入知识单元后的检索与命中行为
- 各域问法的命中、误命中、no_evidence、clarification
- 回源字段与 evidence 表现

#### C. hard-case 回归测试

建议方向：

- `test_phase2_hard_cases.py`
- `test_phase2_regression_queries.py`

主要覆盖：

- 已知失败 query 不回归
- 真实 down feedback 样本持续复现
- 真实 no_evidence 样本持续复现

---

## 8. 各领域清洗文档应如何接入测试

### 8.1 建议接入方式

建议把这些文档作为**只读 fixture 资产**接入测试，而不是在测试中手写大段文本。

建议流程：

1. 在测试中读取指定领域清洗文档 fixture
2. 统一走“文档 -> chunk -> knowledge unit”或“文档 -> 上传 -> 检索”路径
3. 对同一份 fixture 复用多个 query 做回归
4. 用固定断言验证命中、fallback、clarification、citation

### 8.2 断言重点

不建议断言：

- 某个检索分数的绝对值必须完全相同
- 某个内部候选列表顺序永远不变到小数级别

建议断言：

- 是否命中正确业务域
- 是否进入正确响应类型
- 顶部候选是否包含正确来源
- `source_locator / snippet / citation_id` 是否存在
- `rerank_accept / evidence_confidence` 是否落在预期方向
- 是否出现错误的跨域强答

---

## 9. 当前最值得优先收口的 hard-case 簇

基于当前已落地的 hard-case 数据与现有 HR 种子内容，以下样本应优先进入长期回归：

### 9.1 请假泛问法簇

- `请假`
- `怎么请假`
- `如何请假`
- `请假怎么走`
- `请假流程`

目的：

- 避免系统在“泛问法”与“具体问法”之间反复漂移
- 避免把模糊 query 误答成某一个具体 FAQ

### 9.2 年假 / 病假 / 审批进度簇

围绕现有 HR FAQ 种子优先收：

- `如何申请年假？`
- `病假需要提交什么材料？`
- `请假审批进度在哪里查看？`
- `调休余额在哪里看？`

目的：

- 锁住 `domain_hint = hr` 后的 lexical_terms 扩展是否真正对检索起作用
- 锁住 rerank / evidence 接收条件不反向把已有 seed 打成 no_evidence

### 9.3 上传文档簇

- `如何上传文档？`
- `上传文档怎么做？`
- `文档怎么上传`
- `上传后为什么没建立索引`

目的：

- 这类样本已经出现过真实 down 反馈，应纳入长期 regression，而不是只做一次性修复

### 9.4 各领域跨域误命中簇

基于新增的多业务域清洗文档，应新增：

- HR 问法误命中 Finance / Legal / IT
- Finance 问法误命中 Ops / Sales
- Product / IT 邻域问法误命中

目的：

- 新增多域 fixture 后，最容易出现的不是“完全查不到”，而是“查到隔壁域”

---

## 10. 当前建议的执行顺序

### 第一步：先稳当前行为边界

先补：

- `chat_service`
- `chat route`
- `rule_parser`
- `query_planner`
- `reranker`
- `feedback / retrieval_trace / hard_cases`

### 第二步：把新增各领域清洗文档接成 fixture

目标：

- 让这些文档不只是测试素材，而是可重复、可组合的回归输入

### 第三步：从真实 hard-case 往回补测试

优先吸收：

- 已有 `down` feedback
- 已有 `no_evidence`
- 已有跨域误判
- 已有 clarification 边界样本

### 第四步：最后再补环境类 smoke

包括：

- ES 连通
- ES IK 中文分词插件可用
- 建索引
- 上传/解析/切块
- 启动/健康检查

其中 IK 分词 smoke 可直接通过 ES HTTP 接口验证：

```bash
curl http://localhost:9200/_cat/plugins
curl -X POST "http://localhost:9200/_analyze" -H "Content-Type: application/json" -d "{\"analyzer\":\"ik_max_word\",\"text\":\"如何申请年假\"}"
```

两条命令的最小通过标准：

- `_cat/plugins` 输出包含 `analysis-ik 8.17.0`
- `_analyze` 输出能切出 `如何 / 申请 / 年假` 这类词元

启用 IK 的最小前置条件：

- `docker compose build elasticsearch` 已构建带 IK 的镜像
- `ORIONSTACK_ELASTIC_USE_IK_ANALYZER=true` 已写入 `.env`
- 老索引已 `DELETE` 后由 `ensure_index` 重建

---

## 11. 当前阶段结论

第二阶段当前最合适的测试方向不是“把所有代码都写成重型单测”，而是：

```text
基础 phase 2 测试位继续保留
+ 行为边界 test-first
+ 各领域清洗文档 fixture 化
+ 真实 hard-case 持续回归
```

一句话总结：

**`backend/tests` 新加入的各领域清洗文档，不应只被视为“更多测试文件”，而应正式升级为第二阶段的领域回归资产；`docs/2_4_test_strategy.md` 也应随之从“已有 phase 2 测试说明”升级为“行为测试 + 领域 fixture + hard-case 回归”的执行文档。**
