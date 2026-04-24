# OrionStack 第二阶段系统设计 v1

> 状态：**已完成落地（Phase 2 已关闭）**
> 目标方向：**Elasticsearch 单引擎 Hybrid Retrieval（Lexical + Vector + RRF）**
> 使用场景：**FAQ / 业务知识问答主链路的第二阶段升级**
> 与 `1_system_design.md` 的关系：`1_system_design.md` 继续作为**当前真实实现基线**；`2_system_design.md` 定义**第二阶段目标链路**（已完成落地）。
> 与 `3_system_design.md` 的关系：`3_system_design.md` 定义**第三阶段 SaaS 知识副本层**，本文件的 `KnowledgeUnit` 等对象将在第三阶段扩展。

---

## 1. 文档定位

### 1.1 文档目标

本文档用于定义 OrionStack FAQ / 业务知识问答主链路的第二阶段系统设计，目标是将当前“可运行但对自然问法可用性不足”的检索链路，升级为“对自然问法稳定可召回、可证据化、可降级”的目标链路。

### 1.2 与 `1_system_design.md` / `3_system_design.md` 的职责分工

- `1_system_design.md`：当前真实实现基线
- `2_system_design.md`：第二阶段检索链路升级设计（本文）
- `3_system_design.md`：第三阶段 SaaS 知识副本层设计（外部数据接入、新鲜度、权限、追溯、抽取漂移）

本文档不再描述“当前代码已经做到什么”，而是描述“第二阶段应收敛成什么”。

### 1.3 当前阶段问题定义

当前 FAQ 主链路的核心问题不是“效果还可继续优化”，而是**检索可用性尚未成立**。  
问题本质不是数据缺失，而是：

- 用户自然问法不能稳定进入正确召回链路
- 规则路由对短问法有硬门效应
- 词法检索对语义变体与短 query 不够稳
- FAQ 数据与文档数据仍未统一成同一知识单元体系

因此，第二阶段的目标不是继续扩高频词匹配，而是把主链路切换为：

```text
用户自然问法
-> Query Planner
-> Fast Track / Query Rules / Cache
-> Elasticsearch Hybrid Retrieval
-> Rerank + Evidence Extraction
-> Answer Composer
-> citations / trace / debug_info
```

### 1.4 第二阶段按职责链拆分

第二阶段不再把升级目标理解为一个“大检索改造包”，而统一拆成 6 条职责链推进：

1. **Query Planner 链**
   - 负责：`normalized_query`、`domain_hint`、`lexical_terms`、最小 query rewrite
   - 不负责：索引写入、前端展示、记录维护

2. **Knowledge Unit / Data Layer 链**
   - 负责：FAQ 与 document chunk 的统一知识单元表达、索引写入前的数据准备、最小数据层统一
   - 不负责：planner 推理、前端交互

3. **Retrieval Execution 链**
   - 负责：lexical、vector、hybrid、RRF 等检索执行能力
   - 不负责：回答最终组织策略、前端契约展示

4. **Rerank / Evidence 链**
   - 负责：候选重排、证据抽取、citation 强化、证据化回答支撑
   - 不负责：文档接入清洗、API 页面展示

5. **API Compatibility / Clarification 链**
   - 负责：在不打断当前 `/api/chat/ask` 主接口前提下承接第二阶段返回结构扩展、必要澄清与 fallback 兼容
   - 不负责：底层索引写入与排序实现

6. **Trace / Gray / Rollback 链**
   - 负责：检索 trace、灰度切换、旧链路回退、hard cases 记录、缓存与排查支撑
   - 不负责：把实验链路直接伪装为默认稳定链路

### 1.5 第二阶段切换原则

第二阶段链路切换统一遵循以下原则：

1. 每条链都应可独立灰度、独立回退；
2. 不把第二阶段新增逻辑重新堆回旧 `retriever.py`；
3. 不把第二阶段字段与目标能力反写进 `1_system_design.md` 当前默认实现；
4. 先完成链内边界清晰，再讨论跨链协同；
5. 当前主线 1 仍保持默认实现基线，第二阶段只描述升级目标与过渡替换路径。

---

## 2. 第二阶段设计目标与非目标

### 2.1 设计目标

第二阶段的目标是：

1. 让用户自然问法可稳定召回正确 FAQ / 文档证据
2. 让检索同时具备关键词精确命中与语义召回能力
3. 让最终回答尽量基于证据，而不是自由生成
4. 让高频、标准、稳定 FAQ 走更短更快的返回路径
5. 让系统在低置信、证据冲突、模型超时、旧制度命中等场景下，能够可解释地失败
6. 让链路具备可观测、可回放、可降级、可回滚能力

### 2.2 第二阶段验收核心语句

第二阶段的验收语句收敛为：

**用户用自然语言提问时，系统应优先在当前有效、当前可访问、当前版本正确的知识单元中完成稳定召回；若无法可靠回答，则必须以可解释、可回退、可修复的方式失败。**

### 2.3 当前优先要打通的自然问法样例

第二阶段当前优先要解决的，不是某一个业务域本身，而是：

**用户使用短自然问法、口语化问法、题面不一致问法时，系统仍能稳定召回正确知识单元，而不是直接 fallback。**

当前可先用 HR FAQ 作为第一批验证样例，但这些样例只用于说明“自然问法可用性问题”的典型形态，不构成第二阶段的唯一优先对象。

例如，以下输入可作为当前优先验证的自然问法样例：

- `请假`
- `怎么请假`
- `如何请假`
- `病假材料`
- `请假进度怎么看`

后续可按相同原则扩展到其他业务域的高频自然问法样例，而不是把第二阶段收缩为单一 HR 专项优化。

### 2.4 第二阶段明确不做的内容

第二阶段明确不做：

- Elasticsearch + Milvus 双系统并存
- 多 Agent 编排
- 重型 workflow graph
- 全库人工同义词平台
- learned fusion 取代默认 RRF
- 无证据的自由长答案生成
- 每次请求都跑的重型 self-correction loop

第二阶段只解决一件事：

**用户自然语言提问，系统也能找到，并且找到后能基于证据稳定回答。**

---

## 3. 为什么选择 Elasticsearch 单引擎 Hybrid

第二阶段明确选择：

**Elasticsearch 单引擎实现 Lexical + Vector + RRF**

而不是：

- 继续扩展现有纯规则 + 词法检索
- Elasticsearch + Milvus 双系统并存
- 让 LLM 直接绕过检索回答问题

### 3.1 选择理由

#### 理由 A：更符合当前问题本质

当前 FAQ 失败，不是因为系统不会“说”，而是因为系统不会“找”。

例如：

- `请假` 需要召回到“如何申请年假”
- `病假材料` 需要召回到“病假需要提交什么材料”
- `请假怎么看` 需要召回到“请假审批进度在哪里查看”

这类映射本质上需要：

- **Lexical**：保住关键词精确命中
- **Vector**：补足自然问法与 FAQ 题面之间的语义差异

#### 理由 B：避免双系统过重

双系统会带来：

- 两套索引
- 两套路由与召回
- 两套运维与同步
- 额外结果融合复杂度

对当前 FAQ 单场景阶段偏重。

#### 理由 C：便于把可用性、可观测、可回退收在同一引擎侧

使用单引擎更容易统一处理：

- metadata 过滤
- RRF 融合
- 向量索引量化
- health check
- trace 观测
- deployment / rollback

---

## 4. 第二阶段目标链路

### 4.1 目标主链路

```text
用户自然问法
-> normalize
-> Query Planner
-> Fast Track Gate
   -> exact_match_fast_track
   -> high_confidence_lexical_fast_track
   -> small_query_rules_layer
-> Elasticsearch Hybrid Retrieval
   -> lexical retrieval
   -> vector retrieval
   -> RRF fusion
-> Rerank + Evidence Extraction
-> Answer Composer
-> citations / trace / debug_info
```

### 4.2 各层职责

#### Normalize
负责：

- 输入清洗
- 去除冗余空白
- 保留用户原始语义

不负责：

- 复杂意图规划
- 检索改写

#### Query Planner
负责：

- 意图对齐
- Domain Hint 输出
- 多阶改写
- 词法检索输入提取
- 向量检索输入扩展

不负责：

- 文档召回
- 最终回答生成

#### Fast Track Gate
负责：

- 识别标准题面或极高置信 lexical 命中
- 命中时跳过昂贵检索与重排
- 作为本地性能保护层

不负责：

- 替代完整检索链路
- 处理模糊问法的主召回逻辑

#### Hybrid Retrieval
负责：

- 同时执行 lexical / vector 检索
- 做 metadata pre-filter
- 使用 RRF 融合结果
- 输出 top-k 候选与原始信号

不负责：

- 最终答案裁决
- 无证据回答

#### Rerank + Evidence Extraction
负责：

- 候选重排
- 最终相关性判定
- 证据句抽取
- 低置信与冲突场景识别

不负责：

- 替代检索
- 无证据生成

#### Answer Composer
负责：

- 基于证据生成简短稳定回答
- 返回 citations、trace 关键字段与 debug_info
- 在需要时进入澄清模式

不负责：

- 自由补全缺失制度
- 无证据长篇发挥

---

## 5. Query Planner 设计

### 5.1 基本原则

Planner 的目标不是“替用户说得更漂亮”，而是：

**把用户自然语言转换为检索层真正可用、可控、可约束的输入结构。**

对短 query（如 `请假`）尤其重要。

### 5.2 输出契约

```json
{
  "normalized_query": "请假",
  "intent": "faq_qa",
  "domain_hint": "hr",
  "semantic_expansions": [
    "员工休假申请",
    "请假申请流程",
    "病假材料与审批"
  ],
  "lexical_terms": ["请假", "HR", "流程", "审批", "病假", "年假"],
  "planner_confidence": 0.86
}
```

### 5.3 多阶改写拆分

#### Semantic Expansion
用途：

- 面向向量检索
- 扩展短 query 的语义表征
- 弥补短输入语义稀疏问题

#### Keyword Extraction
用途：

- 面向 BM25 / lexical retrieval
- 提取最稳定的检索锚点
- 保住题面、标题、关键名词的硬命中能力

### 5.4 Planner Guardrails

#### Hard Keyword Locking
`lexical_terms` 中必须保留原始 query 的核心原子词。

#### Expansion Circuit Breaker
若出现以下任一情况，应熔断降级：

- 单条 expansion 过长
- 改写与原 query 偏移过大
- planner_confidence 明显不足
- domain_hint 缺失或不稳定

降级后只保留：

- `normalized_query`
- 原始核心 `lexical_terms`
- 必要的 `domain_hint`

#### Drift Guard
若 semantic expansion 越界到明显无关主题，直接丢弃。

#### Domain Anchoring
当 `domain_hint=hr` 时，扩写不得跳转到无关主题。

### 5.5 Planner 的运行策略

本地弱性能环境下，Planner 默认采用轻量 guardrails，不启用每次请求都跑的 embedding 自校验。  
只有在以下场景，才允许按需使用在线 LLM API 做更强 Planner：

- 本地模型低置信
- 高频短 query 多次失败
- 干扰项样本显示 Planner 漂移严重
- 当前总预算允许

---

## 6. Fast Track、Query Rules 与缓存

### 6.1 Fast Track 的目标

Fast Track 是性能保护层，不是检索主脑。  
目标是让标准、稳定、高频 FAQ 在不调用完整重链路时也能快速返回。

### 6.2 exact_match_fast_track

触发条件：

- 标准题面精确命中
- 或同义词白名单命中 canonical FAQ

结果：

- 直接返回
- 跳过 vector retrieval
- 跳过 rerank
- 视情况跳过 Elastic 请求

### 6.3 high_confidence_lexical_fast_track

触发条件：

- phrase/title 命中极高
- lexical top1 与 top2 差距显著
- metadata 过滤后已足够稳定

结果：

- 可跳过 vector retrieval
- 可按配置决定是否仍做轻量 rerank

### 6.4 Small Query Rules Layer

只针对极少数：

- 高频
- 业务价值高
- 语义极短
- 易跨域误召回

的 query，提供小规模规则层：

- pin 到 canonical FAQ id
- boost 指定 domain
- exclude 高噪音域
- 指定 metadata filter

约束：

- 只维护 10–30 个高风险 query
- 不扩展为全库规则系统
- 不替代 Planner + Hybrid 主链路

### 6.5 同义词兜底

Knowledge Unit 入库阶段可为**高频 FAQ 白名单**维护最少量别名：

- `canonical_question_id`
- `question_aliases`

作用仅限：

- exact match fast track
- 高频 FAQ 兜底

不扩展成全库人工同义词平台。

### 6.6 缓存击穿防御

高频命中后，应优先走轻量缓存。

推荐缓存 Key：

- `normalized_query`
- `domain_hint`
- `access_scope`
- `doc_version_snapshot`

如有需要，再补：

- `department_scope`

缓存 Value：

- `final_answer`
- `citations`
- `top_unit_ids`
- `trace_digest`
- `expires_at`

TTL 建议：

- 稳定 FAQ：1–24h
- 半稳定 FAQ：更短
- 个体态、状态态问题：默认不缓存最终答案

原则：

**缓存必须与版本快照绑定，否则缓存会放大旧制度问题。**

---

## 7. Unified Knowledge Units 设计

### 7.1 统一知识单元目标

第二阶段必须把 FAQ 与 document chunk 收为同一索引可消费的数据单元。  
不再长期维持：

- documents / chunks 一套
- mock FAQ fallback 一套

该统一的前提不是“任意原始文档可直接入库”，而是“任何进入下游索引的内容，最终都必须先被转换为满足最小契约的 Knowledge Unit”。对于复杂原始文档，该转换应通过 ingestion / cleaning adapter 完成。

### 7.2 最小字段结构

每条 Knowledge Unit 至少包含：

- `unit_id`
- `source_kind`
- `question`
- `answer`
- `body_text`
- `keywords`
- `business_domain`
- `document_type`
- `source_type`
- `source_label`
- `source_locator`
- `access_scope`
- `lifecycle_status`
- `valid_from`
- `valid_until`
- `version`
- `department_scope`
- `question_aliases`（高频 FAQ 场景可选）
- `question_vector`
- `answer_vector`

以上字段由 `2_system_design.md` 统一冻结。`document_ingestion_boundary.md` 只负责定义原始文档如何进入标准化知识输入，不再单独维护字段清单。

### 7.3 时间 / 状态感知

默认检索仅召回：

- `lifecycle_status = active`
- `valid_from <= now`
- `valid_until is null OR valid_until >= now`

不显式查询历史制度时，不应让旧制度参与默认召回。

### 7.4 Question / Answer 双向量

FAQ 单元不再只生成一个总向量，而是至少分成：

- `question_vector`
- `answer_vector`

用途：

- `question_vector`：更适合命中用户问法
- `answer_vector`：更适合命中细节描述

v1 不采用 preview 的单字段多向量方案，先用两个独立向量字段。

### 7.5 Embedding 维度契约与量化策略

配置层必须冻结：

- `EMBEDDING_MODEL_ID`
- `EMBEDDING_DIMS`
- `QUESTION_VECTOR_DIMS`
- `ANSWER_VECTOR_DIMS`
- `VECTOR_INDEX_MODE`

原则：

1. 索引字段 dims 必须与 Provider 配置一致
2. 模型切换前必须通过索引一致性检查
3. 优先使用 Elasticsearch 原生向量量化与索引能力
4. 裁维 / Matryoshka 仅在模型明确支持时才开启

### 7.6 老数据迁移与默认值契约

为兼容旧 schema，建议默认值：

- `version`: 缺失时视为 `v1`
- `valid_from`: 若有 `created_at` 则取其值；否则取统一历史默认值
- `valid_until`: 缺失时为 `null`
- `department_scope`: 缺失时视为 `global`

迁移期混跑时必须满足：

- 缺字段时有安全默认语义
- 缓存键构造能处理旧数据缺少 version
- clarification / rerank 在元数据缺失时能自动降级

---

## 8. Elasticsearch Hybrid Retrieval 设计

### 8.1 Lexical Retrieval

字段：

- `question`
- `answer`
- `keywords`
- `source_label`

输入：

- `normalized_query`
- `lexical_terms`

作用：

- 保住关键词、题面、标题的精确命中

### 8.2 Vector Retrieval

字段：

- `question_vector`
- `answer_vector`

输入来源：

- `normalized_query`
- `semantic_expansions`

作用：

- 召回自然问法与 FAQ 题面的语义邻近结果

### 8.3 Domain Hint 下沉为检索层硬过滤

`domain_hint` 不能只停留在 Planner 层。  
当 `planner_confidence` 足够高、且 query 属于目标域时，应在 lexical / vector 检索前做 metadata pre-filter。

硬过滤字段至少包含：

- `business_domain`
- `access_scope`
- `lifecycle_status`
- `source_type`
- `document_type`
- `valid_from`
- `valid_until`

### 8.4 RRF 融合

默认采用：

- `RRF_RANK_CONSTANT = 60`
- `RRF_RANK_WINDOW_SIZE = 50`
- `LEXICAL_TOP_N = 50`
- `VECTOR_TOP_N = 50`

约束：

- 两路 Top-N 数量应一致
- v1 默认不启用复杂加权融合
- 后续若需要更细粒度控制，再评估 linear retriever / weighted RRF

### 8.5 保留原始检索信号

传给 reranker 前，必须保留：

- `bm25_score`
- `vector_score`
- `lexical_rank`
- `vector_rank`
- `rrf_rank`

这些信号用于：

- 排障
- smoke test
- “关键词作弊”识别
- 语义漂移识别
- rerank 接受判定辅助

---


### 8.6 Knowledge Unit 入库、回填与重建流程

为让第二阶段不只是“检索方案”，而成为可执行的索引演进方案，需要明确统一知识单元的入库、历史回填与索引重建流程。

#### 8.6.1 入库流程

新的 FAQ / document chunk 进入系统后，建议按以下顺序处理：

1. 文档接入判断
2. 对可直接进入链路的输入执行 direct ingest
3. 对复杂文档执行 ingestion / cleaning adapter
4. 转换为统一 Knowledge Unit
5. 补齐最小元数据：
   - `business_domain`
   - `access_scope`
   - `lifecycle_status`
   - `valid_from`
   - `valid_until`
   - `version`
6. 生成：
   - `question_vector`
   - `answer_vector`
7. 写入 `knowledge_units_v1`

#### 8.6.2 历史 FAQ / 文档的回填流程

对于已存在的 FAQ 种子与历史 document chunk，应支持一次性或批量回填。

建议步骤：

1. 扫描旧 FAQ / chunk 数据源
2. 映射为统一 Knowledge Unit 结构
3. 对缺失字段应用默认值契约：
   - `version = v1`
   - `valid_until = null`
   - `department_scope = global`
4. 批量生成双向量字段
5. 写入新索引并记录回填批次

#### 8.6.3 增量更新与全量重建的边界

建议区分以下两类操作：

**可增量回填的情况：**
- 新增 FAQ
- 新增 document chunk
- `answer` 文本小幅更新
- `keywords`、`source_label`、`source_locator` 更新

**建议全量重建的情况：**
- Embedding 模型更换
- 向量维度变化
- `question_vector` / `answer_vector` 生成逻辑变化
- 重要 tokenizer / normalization 规则变化
- 索引映射字段变化

#### 8.6.4 与缓存失效的关系

当以下字段发生变化时，应触发相关缓存失效：

- `version`
- `valid_from`
- `valid_until`
- `question`
- `answer`
- `question_aliases`
- `department_scope`

缓存失效至少应影响：

- fast track 缓存
- 高频短 query 缓存
- trace 中的 doc version snapshot 校验

#### 8.6.5 最小约束

1. 任何可被检索的 FAQ / chunk，最终都应能映射到统一 Knowledge Unit
2. 新旧 schema 混跑时，缺失字段必须有安全默认语义
3. 索引重建必须先于默认链路切换
4. 任何影响向量语义空间的变更，都不得仅做局部热更新

## 9. Rerank、Evidence Extraction 与 Clarification Mode

### 9.1 Rerank 的职责

Reranker 的职责不是“写得更好”，而是：

- 候选重排
- 接受 / 拒绝判定
- 证据句抽取
- 低置信与冲突识别

### 9.2 接受阈值与分差判定

建议配置：

- `RERANK_ACCEPT_THRESHOLD`
- `RERANK_MARGIN_THRESHOLD`

最小接受条件：

- `top1_score >= accept_threshold`
- `top1_score - top2_score >= margin_threshold`
- `top1` 存在有效 `evidence_spans`

否则直接 fallback。

### 9.3 Evidence Extraction

输出至少包含：

- `rerank_score`
- `evidence_spans`
- `evidence_confidence`
- `accept` / `reject`

原则：

**无明确证据，不进入 Answer Composer。**

### 9.4 冲突证据识别

当以下条件同时成立时，应标记冲突：

1. `top1_score >= accept_threshold`
2. `top2_score >= accept_threshold`
3. `top1_score - top2_score < margin_threshold`
4. 检测到以下任一冲突：
   - `version` 冲突
   - `department_scope` 冲突
   - `evidence_spans` 语义冲突

### 9.5 Clarification Mode

Clarification Mode 不是默认对话分支，而是**冲突化解器**。

只在高分 + 低分差 + 冲突证据同时成立时触发。  
典型反问示例：

- “您是想了解当前生效的请假制度，还是历史版本规定？”
- “您是想了解研发部的请假规定，还是销售部的请假规定？”

建议新增输出字段：

- `conflict_detected`
- `conflict_reason`
- `clarification_required`

---

## 10. Answer Composer 与失败类型

### 10.1 Answer Composer 的职责

- 基于 top1 / topN 证据输出简短回答
- 返回 citation 与 source_locator
- 控制风格稳定、短、可引用
- 遇到冲突时进入 clarification_mode
- 遇到无证据时保守 fallback

### 10.2 Fallback 子类型

响应契约建议补充：

- `fallback_reason`
- `clarification_required`
- `stale_policy_blocked`
- `low_confidence_retrieval`
- `conflict_detected`
- `model_timeout`
- `cache_served`

建议的失败子类型最小集合：

- `no_evidence`
- `low_confidence`
- `stale_policy_blocked`
- `conflict_requires_clarification`
- `model_timeout`
- `system_degraded`

原则：

**Fallback 不是单一状态，而是用户可感知的失败类型集合。**

### 10.3 实施顺序与切换路径表

为避免第二阶段改造一次性切换过多组件，本阶段改造应按“先并行、再灰度、后替换”的顺序推进。

#### Step 1：统一知识单元入库，不切默认链路

目标：

- 新增 `knowledge_unit_repo`
- 将 FAQ 单元与 document chunk 统一转换为 `knowledge_units_v1`
- 补齐最小字段：
  - `unit_id`
  - `source_kind`
  - `question`
  - `answer`
  - `business_domain`
  - `access_scope`
  - `lifecycle_status`
  - `valid_from`
  - `valid_until`
  - `version`

约束：

- 当前默认问答链路保持不变
- 只建立并验证新索引，不替换线上主检索
- 复杂原始文档的接入判断与清洗不在本 Step 1 的字段清单内展开，统一以 `document_ingestion_boundary.md` 为准。

#### Step 2：先接 Elasticsearch lexical-only，作为过渡检索层

目标：

- 先用 Elastic full-text / BM25 承接当前 lexical 检索
- 保留 `retriever.py` 作为回退路径
- 验证：
  - FAQ 标题命中
  - 高置信 lexical fast track
  - metadata pre-filter 是否正常工作

约束：

- 此阶段不强制启用向量检索
- 重点先确认索引结构、filter 与 fast track 的稳定性

#### Step 3：接入 vector retrieval + RRF，但默认只灰度少量 Query

目标：

- 引入 `question_vector` / `answer_vector`
- 打通 lexical + vector + RRF
- 先对少量高频 query 灰度：
  - `请假`
  - `病假材料`
  - `工资条`
  - `调休`

约束：

- 默认仍允许回退到 lexical-only
- 不在此阶段直接放开全部 query

#### Step 4：引入 rerank + evidence extraction

目标：

- 增加 `rerank_score`
- 增加 `evidence_spans`
- 启用 `RERANK_ACCEPT_THRESHOLD`
- 启用 `RERANK_MARGIN_THRESHOLD`

约束：

- 无明确证据时直接 fallback
- 此阶段仍可关闭 Answer Composer，仅返回模板化答案 + citations

#### Step 5：最后接入 Clarification Mode 与按需 API fallback

目标：

- 仅在高分、低分差、冲突证据同时成立时开启 Clarification Mode
- 仅在本地队列繁忙、低置信 query 或预算允许时启用在线 API

约束：

- Clarification Mode 不作为默认分支
- API fallback 不得成为所有 query 的固定前置步骤

#### 默认切换原则

1. 先完成数据统一，再切检索
2. 先完成 lexical-only，再切 hybrid
3. 先完成 hybrid，再启用 rerank
4. 先完成 rerank，再启用 clarification / API fallback
5. 任一阶段不稳定时，按降级路径退回上一层稳定链路

---



## 11. LLM / Provider / 延迟预算

### 11.1 LLM 的定位

LLM 在第二阶段中的职责不是“直接替代 FAQ”，而是：

- Query Planner
- 条件触发的 Rerank
- 条件触发的 Answer Composer

### 11.2 本地优先、按需接 API

默认策略：

- 本地 LLM：Gemma 3 4B（第一轮主实现）
- 在线 LLM API：仅在本地队列繁忙、低置信 query、或需要更强 Planner / Rerank 时启用

### 11.3 Provider 抽象

统一抽象：

- `QueryPlannerProvider`
- `EmbeddingProvider`
- `RerankProvider`
- `AnswerComposerProvider`

业务链路只依赖接口，不绑定模型来源。

### 11.4 延迟预算与降级表

默认执行顺序：

```text
exact_match_fast_track
-> high_confidence_lexical_fast_track
-> hybrid retrieval
-> local rerank
-> local answer composer
-> online API rerank / composer（仅按需）
-> fallback
```

原则：

1. 标准题面命中优先直接返回
2. 高置信 lexical 命中优先跳过 vector / rerank
3. 本地队列繁忙或预算不足时，跳过本地 composer
4. 在线 API 只作为按需增强位
5. 超过总预算仍不确定时，直接 fallback

---

## 12. 可观测性、测试与回归

### 12.1 Hybrid Smoke Test Set

必须包含：

- 目标命中样本：`请假`、`怎么请假`、`病假材料`
- 干扰项样本：同词异域、标题强匹配但正文无证据、跨域强 lexical 噪音
- 近义但无证据样本

必须记录：

- lexical top-k
- vector top-k
- RRF top-k
- rerank top-k
- evidence_spans
- 各阶段 domain 分布

### 12.2 Retrieval Trace 契约

每次请求建议最少记录：

- `trace_id`
- `raw_query`
- `normalized_query`
- `intent`
- `domain_hint`
- `semantic_expansions`
- `lexical_terms`
- `filters`
- `lexical_hits`
- `vector_hits`
- `rrf_hits`
- `rerank_result`
- `evidence_spans`
- `final_status`

原则：

**没有可回放 trace，后续调参与坏例复盘都不可靠。**

### 12.3 负反馈回流为硬样本池

以下请求应进入 `hard_cases`：

- 用户点击“无帮助 / 不准确”
- 进入 clarification_mode
- 被 stale_policy_blocked 拦截
- 高频 query 走降级路径仍失败

样本池最少字段：

- `trace_id`
- `raw_query`
- `normalized_query`
- `domain_hint`
- `fallback_reason`
- `top_candidates`
- `evidence_spans`
- `user_feedback`
- `created_at`

原则：

**用户负反馈不是运营数据，而是下一轮检索改造的硬样本。**

---


### 12.4 最小观测指标定义

除功能验收外，`2_system_design.md` 对应方案还应冻结一组最小观测指标，用于判断链路是否真的变得更可用、更稳定，而不是只凭体感判断。

#### 指标 1：fast_track_hit_rate

定义：

- 进入 `exact_match_fast_track` 或 `high_confidence_lexical_fast_track` 并直接返回的请求占比

用途：

- 评估标准 FAQ / 高频短 query 是否被更短路径正确承接
- 评估是否减少了不必要的向量检索与 LLM 调用

#### 指标 2：hybrid_retrieval_success_rate

定义：

- 进入 Hybrid Retrieval 后，top-k 中至少包含一个正确目标 Knowledge Unit 的占比

用途：

- 评估 lexical + vector + RRF 是否真的提升了召回
- 区分“检索没找到”和“后续 rerank/composer 出问题”

#### 指标 3：rerank_accept_rate

定义：

- 进入 rerank 后，最终满足 `accept_threshold` 且存在 `evidence_spans` 的请求占比

用途：

- 评估 rerank 是否在有效去噪
- 评估 evidence extraction 是否足够稳定

#### 指标 4：clarification_trigger_rate

定义：

- 触发 `clarification_mode` 的请求占比

用途：

- 监控澄清模式是否过度触发
- 若触发率异常升高，应优先检查：
  - version 冲突
  - department_scope 冲突
  - rerank 分差阈值设置过严

#### 指标 5：stale_policy_block_rate

定义：

- 因 `valid_from / valid_until` 时间窗口过滤而被阻断的请求占比

用途：

- 监控是否存在旧制度误召回风险
- 监控知识单元的时间字段是否缺失或迁移不完整

#### 指标 6：fallback_rate_by_reason

定义：

- 按 `fallback_reason` 维度统计的失败占比

建议至少拆分：

- `no_evidence`
- `low_confidence`
- `stale_policy_blocked`
- `conflict_requires_clarification`
- `model_timeout`
- `system_degraded`

#### 使用原则

1. 所有指标必须可按 `trace_id` 回放
2. 指标异常时，应优先定位到具体层：
   - fast track
   - hybrid retrieval
   - rerank
   - composer
3. 指标用于决定是否继续放量，不作为单次请求正确性的唯一依据

## 13. 冷启动、健康检查、发布与回滚

### 13.1 索引健康检查

建议新增：

- `backend/app/indexing/index_health_checker.py`

职责：

1. 检查索引是否存在
2. 检查 `question_vector` / `answer_vector` dims 是否与当前配置一致
3. 检查文本、keyword、alias、metadata 字段是否齐全
4. 执行最小联通性请求，验证 Hybrid + RRF 查询路径可用

### 13.2 发布前门槛

切换默认链路前，至少满足：

- smoke set 通过率达到预设下限
- `hard_cases` 通过率不低于上一版
- 高频 FAQ 不出现明显回归
- 时间过滤与缓存版本快照校验通过

### 13.3 回滚触发条件

满足任一情况，建议立即回滚：

- 高频 query fallback 比例显著上升
- `stale_policy_blocked` 异常飙升
- `model_timeout` / API 超时持续超预算
- `hard_cases` 通过率显著下降
- clarification mode 触发率异常升高且用户放弃率增加

### 13.4 降级路径

从重到轻建议为：

1. `local_llm + hybrid + rerank`
2. `hybrid + rerank`
3. `hybrid without llm_composer`
4. `high_confidence_lexical_fast_track`
5. `exact_match_fast_track`
6. `safe fallback`

原则：

**链路不稳时，应优先退回更短路径，而不是硬撑到完全不可用。**

---


### 13.5 敏感边界与日志脱敏

当前 `2_system_design.md` 对应方案主要服务于 FAQ / 业务知识问答主链路，其中 HR FAQ 是首批重点场景之一。
因此，除检索可用性外，还必须补齐最小的敏感边界与日志脱敏约束。

#### 13.5.1 边界原则

本方案用于：

- 企业内部 FAQ / 制度问答
- 对公开或内部可访问制度内容进行检索与解释
- 返回可引用、可回源的制度答案

本方案不用于：

- 输出个人敏感人事数据
- 替代正式审批系统
- 处理员工编号、手机号、身份证号等身份识别型查询
- 绕过 `access_scope` 返回越权内容

#### 13.5.2 FAQ 主链路的最小敏感拦截

对于包含以下内容的 query，默认不进入 FAQ 主链路：

- 身份证号
- 手机号
- 银行卡号
- 员工编号
- 明显个人隐私字段

这些请求应：

- 直接拒绝进入 FAQ 检索链路
- 或进入单独的受控业务系统
- 不落入 `hard_cases` 的原文样本池

#### 13.5.3 Trace 与日志脱敏原则

`raw_query`、`Retrieval Trace`、`hard_cases`、反馈记录默认遵循以下约束：

1. 不记录可直接识别个人身份的完整字段
2. 必要时仅保留脱敏片段或哈希摘要
3. `trace_digest` 优先替代长原文落盘
4. `evidence_spans` 仅保留制度证据，不保留用户隐私原文

#### 13.5.4 access_scope 的最小职责

`access_scope` 当前不是完整权限系统，但至少承担以下职责：

- 防止跨访问范围的 FAQ / 制度内容被误召回
- 防止高敏感知识单元进入默认 FAQ 主链路
- 为后续更严格权限控制预留 metadata 基础

#### 13.5.5 最小约束

1. FAQ 主链路优先回答“制度问题”，而不是“个人数据问题”
2. 日志、trace、样本池优先保留问题模式，不保留完整个人身份信息
3. 若 query 同时包含制度问答与个人敏感信息，优先按敏感拦截处理

## 14. 配置草案

```text
ORIONSTACK_QUERY_PLANNER_PROVIDER=local_ollama
ORIONSTACK_QUERY_PLANNER_MODEL=gemma3:4b

ORIONSTACK_RERANK_PROVIDER=local_ollama
ORIONSTACK_RERANK_MODEL=gemma3:4b

ORIONSTACK_ANSWER_PROVIDER=local_ollama
ORIONSTACK_ANSWER_MODEL=gemma3:4b

ORIONSTACK_EMBEDDING_PROVIDER=local
ORIONSTACK_EMBEDDING_MODEL=bge-small-zh-v1.5
ORIONSTACK_EMBEDDING_DIMS=768
ORIONSTACK_QUESTION_VECTOR_DIMS=768
ORIONSTACK_ANSWER_VECTOR_DIMS=768
ORIONSTACK_VECTOR_INDEX_MODE=elastic_native_quantized
ORIONSTACK_ENABLE_MATRYOSHKA=false

ORIONSTACK_SEARCH_BACKEND=elasticsearch
ORIONSTACK_ELASTIC_INDEX=knowledge_units_v1
ORIONSTACK_ELASTIC_ENABLE_RRF=true

ORIONSTACK_ENABLE_FAST_TRACK=true
ORIONSTACK_EXACT_MATCH_FAST_TRACK=true
ORIONSTACK_HIGH_CONFIDENCE_LEXICAL_FAST_TRACK=true
ORIONSTACK_FAST_TRACK_SYNONYM_MATCH=true

ORIONSTACK_PLANNER_HARD_KEYWORD_LOCKING=true
ORIONSTACK_PLANNER_ENABLE_CIRCUIT_BREAKER=true
ORIONSTACK_PLANNER_MAX_SEMANTIC_EXPANSION_CHARS=50
ORIONSTACK_PLANNER_ENABLE_DRIFT_GUARD=true
ORIONSTACK_PLANNER_ENABLE_DOMAIN_ANCHORING=true
ORIONSTACK_PLANNER_ENABLE_EMBEDDING_SELF_CHECK=false

ORIONSTACK_RRF_RANK_CONSTANT=60
ORIONSTACK_RRF_RANK_WINDOW_SIZE=50
ORIONSTACK_LEXICAL_TOP_N=50
ORIONSTACK_VECTOR_TOP_N=50

ORIONSTACK_ENABLE_API_FALLBACK=false
ORIONSTACK_API_FALLBACK_ON_LOCAL_QUEUE_BUSY=true
ORIONSTACK_API_FALLBACK_ON_LOW_CONFIDENCE=true
ORIONSTACK_RERANK_ACCEPT_THRESHOLD=0.60
ORIONSTACK_RERANK_MARGIN_THRESHOLD=0.05

ORIONSTACK_ENABLE_SMOKE_TEST_LOG=true
ORIONSTACK_ENABLE_INDEX_HEALTH_CHECK=true
```

说明：

- 阈值先作占位，后续以测试集结果冻结
- dims 与 index mode 可先作为索引契约冻结
- 量化实现优先依赖 Elasticsearch 原生能力
- 本地/API 切换条件仍允许按阶段迭代

---

## 15. 第一轮实现优先级

### P1：Query Planner 最小可用
- `normalized_query`
- `domain_hint`
- `semantic_expansions`
- `lexical_terms`
- 基础 guardrails

### P2：Knowledge Units + Elastic Hybrid
- FAQ / chunk 统一入库
- lexical + vector 双路检索
- metadata 过滤
- RRF 融合

### P3：Fast Track + 高风险 Query 规则层
- 标准题面命中
- 高频 FAQ 别名白名单
- 小规模 query rules

### P4：Rerank + Evidence Extraction
- accept threshold
- margin threshold
- evidence_spans
- conflict_detected

### P5：Trace / Hard Cases / Rollback
- retrieval trace
- smoke test
- hard_cases
- 发布与回滚门槛

---

## 16. 第一轮验收标准

以下输入必须通过：

- `请假`
- `怎么请假`
- `如何请假`
- `病假材料`
- `请假进度怎么看`

要求：

1. 不返回 fallback（除确实无证据）
2. 能稳定命中正确 HR FAQ 单元
3. citation 返回 `HR FAQ` 与 `hr_faq_seed_v1#...`
4. debug_info 至少包含：
   - planner 输出
   - fast track 命中情况
   - lexical top-k
   - vector top-k
   - RRF 合并结果
   - rerank top-k
   - evidence_spans
   - top1/top2 分差
   - 最终命中 unit
5. 干扰项测试中，domain 过滤必须能抑制明显跨域误召回

---

## 17. 实施边界总结

第二阶段设计收敛为：

**Elasticsearch 单引擎 Hybrid Retrieval（Lexical + Vector + RRF）+ Query Planner + Fast Track + Evidence-based Answering**

同时补齐：

- Planner guardrails
- 高风险 query 白名单兜底
- 时间窗口过滤
- 版本感知缓存
- 冲突澄清
- retrieval trace
- hard cases 回流
- fallback 子类型
- 发布 / 回滚 / 降级门槛

这套设计不再是“FAQ 检索改造草案的增补合集”，而是：

**OrionStack FAQ / 业务知识问答第二阶段的目标系统设计基线。**
