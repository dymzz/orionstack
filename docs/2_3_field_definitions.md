# OrionStack 第二阶段新增字段说明 v1

> 对应设计文档：`docs/designs/2_system_design.md`  
> 配套进度文档：`docs/2_1_progress.md`  
> 配套职责文档：`docs/2_2_file_responsibilities.md`  
> 配套测试文档：`docs/2_4_test_strategy.md`  
> 文档定位：`2_system_design.md` 的字段解释表  
> 命名说明：仅按 `1_2_file_responsibilities.md` / `2_2_file_responsibilities.md` 的命名规范延续为 `2_3_field_definitions.md`，不假设未上传文件的具体内容与版式。  
> 适用范围：`2_system_design.md` + `document_ingestion_boundary.md`

---

## 1. 文档目标

本文档只做一件事：

**对 `2_system_design.md` 第二阶段新增或显著扩展的关键字段做解释对照，避免实现时把字段提前下沉到 `1_system_design.md`，或把不同层的字段混写。**

本文档不承担以下职责：

- 不重写 `2_system_design.md` 的系统设计
- 不重复解释 `1_system_design.md` 已冻结且语义未变化的字段
- 不替代检索、索引、API、数据库的详细实现文档
- 不替代 `2_4_test_strategy.md` 的测试分层与验证策略说明

---

## 2. 使用原则

1. 本文档只解释第二阶段新增或在第二阶段语义明显升级的字段。
2. 若字段已在 `1_system_design.md` 出现，但第二阶段语义发生扩展，应在“说明 / 不要误解”中明确写出。
3. 文档接入与清洗层输出字段，只有在进入 `Knowledge Unit` 或第二阶段链路后才纳入本表。
4. 配置常量（如阈值名）不等于业务字段；本文件优先解释对象字段、返回字段、追踪字段。

---

## 3. 第二阶段字段分组

第二阶段新增字段主要分为 7 组：

1. Query Planner 输出字段
2. Fast Track / 缓存字段
3. Knowledge Unit 字段
4. 检索过滤与检索信号字段
5. Rerank / Evidence / Clarification 字段
6. 第二阶段失败类型与响应补充字段
7. Retrieval Trace / hard_cases 字段

### 3.1 当前落地状态说明

为避免把“第二阶段目标字段”和“当前仓库已出现字段”混读，需先明确：

- 本文档中的字段**并不等于都已经落地**
- 其中一部分已经以最小实现或配置占位的形式进入仓库
- 另一部分仍属于 `2_system_design.md` 的目标字段，不应被误读成当前默认链路已启用

当前仓库中**已经出现或已有最小占位**的第二阶段字段，主要包括：

- 配置字段：`search_backend`、`elastic_url`、`elastic_index`、`elastic_use_ik_analyzer`、`enable_query_planner`、`planner_provider`、`planner_model`、`ollama_url`、`enable_fast_track`
- `KnowledgeUnit` 最小字段：`unit_id`、`source_kind`、`question`、`answer`、`body_text`、`keywords`、`business_domain`、`document_type`、`source_type`、`source_label`、`source_locator`、`access_scope`、`lifecycle_status`、`valid_from`、`valid_until`、`version`、`created_at`
- lexical-only 过渡链路已实际使用的过滤字段：`business_domain`、`access_scope`、`lifecycle_status`
- 当前链路已具备基础意义的追踪字段：`trace_id`

当前**仍主要属于第二阶段目标设计、尚未在仓库中完整落地**的字段，主要包括：

- planner 扩写结果：`intent`、`semantic_expansions`、`planner_confidence`
- vector / hybrid / RRF 相关字段：`question_vector`、`answer_vector`、`vector_score`、`vector_rank`、`rrf_rank`
- rerank / evidence / clarification 相关字段：`rerank_score`、`evidence_spans`、`evidence_confidence`、`conflict_reason`
- retrieval trace / hard cases 的完整字段集合

---

## 4. Query Planner 输出字段

| 字段 | 所属对象 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `normalized_query` | planner output | 规划后的基础检索输入 | 第二阶段它是 planner 输出的一部分，不仅是输入清洗结果 |
| `intent` | planner output | 标识当前请求意图 | 当前目标场景仍应收敛到 FAQ / 知识问答，不扩展为通用意图中台 |
| `domain_hint` | planner output | 为检索提供业务域提示 | 在第二阶段可下沉为 metadata pre-filter 依据 |
| `semantic_expansions` | planner output | 向量检索使用的语义扩展 | 用于补足短 query 语义，不应改写用户原始意图 |
| `lexical_terms` | planner output | 词法检索使用的稳定检索锚点 | 必须保留原 query 的核心原子词 |
| `planner_confidence` | planner output | planner 输出的可信度 | 用于决定扩写是否保留或降级，不等于最终回答置信度 |

---

## 5. Fast Track / 缓存字段

### 5.1 缓存 Key

| 字段 | 所属对象 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `normalized_query` | cache key | 标识归一化问题 | 作为缓存键的一部分，不应单独承担全部缓存语义 |
| `domain_hint` | cache key | 限制业务域 | 防止跨域误命中缓存 |
| `access_scope` | cache key | 隔离访问范围 | 避免不同访问范围共用缓存 |
| `doc_version_snapshot` | cache key | 绑定文档版本快照 | 防止旧制度静默污染缓存 |
| `department_scope` | cache key（可选） | 细化部门范围 | 仅在部门维度确实影响答案时加入 |

### 5.2 缓存 Value

| 字段 | 所属对象 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `final_answer` | cache value | 缓存最终回答文本 | 仅适用于稳定 FAQ，不应用于个体态问题 |
| `citations` | cache value | 缓存引用结果 | 应与对应版本快照一致 |
| `top_unit_ids` | cache value | 缓存命中的知识单元 ID | 用于回放与排查，不替代 citations |
| `trace_digest` | cache value | 记录本次关键路径摘要 | 是摘要，不是完整 trace |
| `expires_at` | cache value | 缓存失效时间 | 仍需结合版本快照，不可只靠 TTL |

---

## 6. Knowledge Unit 字段

### 6.1 最小字段结构

| 字段 | 所属对象 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `unit_id` | Knowledge Unit | 统一知识单元唯一标识 | 是单元 ID，不等于文档 ID |
| `source_kind` | Knowledge Unit | 标识来源种类 | 用于区分 FAQ、document chunk 等来源 |
| `question` | Knowledge Unit | FAQ 问题面 | 适用于 FAQ 型单元；非 FAQ 型可为空或不主用 |
| `answer` | Knowledge Unit | FAQ 答案面 | 适用于 FAQ 型单元；不等于最终生成回答 |
| `body_text` | Knowledge Unit | 可检索正文 | 必须是可检索文本，不是原始二进制引用 |
| `keywords` | Knowledge Unit | 词法召回辅助锚点 | 用于 lexical retrieval，不应滥扩成人工同义词平台 |
| `business_domain` | Knowledge Unit | 业务域 | 是检索过滤和分域召回的重要依据 |
| `document_type` | Knowledge Unit | 文档类型 | 用于过滤和清洗后的语义分层 |
| `source_type` | Knowledge Unit | 来源类型 | 用于区分 FAQ、制度文档、通知等来源语义 |
| `source_label` | Knowledge Unit | 来源展示名称 | 展示字段，不替代定位字段 |
| `source_locator` | Knowledge Unit | 回源定位信息 | 第二阶段依旧是 citations、缓存、版本判断的重要基础 |
| `access_scope` | Knowledge Unit | 访问范围 | 必须参与过滤与缓存隔离 |
| `lifecycle_status` | Knowledge Unit | 生命周期状态 | 默认仅召回 active 内容 |
| `valid_from` | Knowledge Unit | 生效起始时间 | 用于时效过滤 |
| `valid_until` | Knowledge Unit | 生效截止时间 | 缺失时通常表示仍有效 |
| `version` | Knowledge Unit | 版本号 | 版本控制、缓存失效、冲突判断的重要依据 |
| `department_scope` | Knowledge Unit | 部门范围 | 用于细化部门差异制度 |
| `question_vector` | Knowledge Unit | 面向问法召回的向量 | 更适合命中用户问法 |
| `answer_vector` | Knowledge Unit | 面向细节召回的向量 | 更适合命中答案细节描述 |

### 6.2 文档接入 / 清洗层补充字段

> 以下字段来自 `document_ingestion_boundary.md`，只有在进入第二阶段统一知识单元时才需要解释。

| 字段 | 所属对象 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `chunk_id` | ingest output / locator | chunk 级稳定定位标识 | 可作为 `source_locator` 的组成部分或等价定位标识 |
| `question_aliases` | FAQ supplement | 高频 FAQ 别名白名单 | 只建议用于高频 FAQ fast track，不扩展为全库同义词平台 |

### 6.3 默认值契约字段

| 字段 | 所属对象 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `version = v1` | migration default | 兼容旧 schema 的默认版本 | 仅在旧数据缺失版本时使用 |
| `valid_until = null` | migration default | 表示当前仍有效 | 不是“未知时间” |
| `department_scope = global` | migration default | 表示默认全局部门范围 | 不是精确部门归属 |

---

## 7. 检索过滤与检索信号字段

### 7.1 metadata pre-filter 字段

| 字段 | 所属对象 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `business_domain` | retrieval filter | 按业务域硬过滤 | `domain_hint` 足够稳时应下沉到检索层 |
| `access_scope` | retrieval filter | 按访问范围过滤 | 防止越权召回 |
| `lifecycle_status` | retrieval filter | 按生命周期过滤 | 默认只召回 active |
| `source_type` | retrieval filter | 按来源类型过滤 | 避免不同来源混召回 |
| `document_type` | retrieval filter | 按文档类型过滤 | 用于缩小召回面 |
| `valid_from` | retrieval filter | 生效时间下界 | 控制当前制度有效性 |
| `valid_until` | retrieval filter | 生效时间上界 | 控制过期制度排除 |

### 7.2 原始检索信号字段

| 字段 | 所属对象 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `bm25_score` | retrieval candidate | 词法检索分数 | 不代表最终相关性裁决 |
| `vector_score` | retrieval candidate | 向量检索分数 | 不应直接与 `bm25_score` 做裸比较 |
| `lexical_rank` | retrieval candidate | 词法检索排序位次 | 用于 RRF 与排障 |
| `vector_rank` | retrieval candidate | 向量检索排序位次 | 用于 RRF 与排障 |
| `rrf_rank` | retrieval candidate | RRF 融合后的位次 | 是融合结果，不是单路原始分数 |

---

## 8. Rerank / Evidence / Clarification 字段

### 8.1 Rerank 与证据字段

| 字段 | 所属对象 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `rerank_score` | rerank result | 候选重排后的相关性分数 | 仅用于第二阶段接受 / 拒绝判断 |
| `evidence_spans` | evidence result | 被抽取的证据片段 | 无明确证据时不应进入 Answer Composer |
| `evidence_confidence` | evidence result | 证据可信度 | 用于辅助接受判断，不替代主分数 |
| `accept` / `reject` | rerank result | 是否接受当前候选 | 是 rerank 结果，不是最终对外状态字段 |

### 8.2 冲突与澄清字段

| 字段 | 所属对象 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `conflict_detected` | clarification result | 标记是否检测到冲突 | 只有高分、低分差、证据冲突时才应触发 |
| `conflict_reason` | clarification result | 标记冲突原因 | 例如版本冲突、部门范围冲突、证据语义冲突 |
| `clarification_required` | clarification result | 标记是否需要向用户发起澄清 | 不是默认对话分支 |

---

## 9. 第二阶段失败类型与响应补充字段

### 9.1 响应补充字段

| 字段 | 所属对象 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `fallback_reason` | response / trace | 标记具体失败原因 | 第二阶段比当前阶段更细，但仍应收敛 |
| `clarification_required` | response / trace | 表示进入澄清模式 | 不等于失败本身 |
| `stale_policy_blocked` | response / trace | 表示被旧制度阻断 | 是时效 / 版本约束结果 |
| `low_confidence_retrieval` | response / trace | 表示检索低置信 | 用于区分“找不到”和“证据不稳” |
| `model_timeout` | response / trace | 表示模型超时 | 应与系统降级路径联动 |
| `cache_served` | response / trace | 标记是否由缓存直接服务 | 便于区分短路径与完整链路 |

### 9.2 失败子类型最小集合

| 枚举值 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|
| `no_evidence` | 找到了候选但没有可接受证据 | 不等于纯检索空结果 |
| `low_confidence` | 相关性或判断不够稳 | 需要和 trace 一起看原因 |
| `stale_policy_blocked` | 被过期 / 历史制度阻断 | 反映时间 / 状态过滤生效 |
| `conflict_requires_clarification` | 高分冲突需澄清 | 不是普通 fallback |
| `model_timeout` | 关键模型步骤超时 | 应进入降级或 fallback |
| `system_degraded` | 系统进入降级运行 | 表示系统仍可运行但能力降级 |

---

## 10. Retrieval Trace / hard_cases 字段

### 10.1 Retrieval Trace 最小字段

| 字段 | 所属对象 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `trace_id` | retrieval trace | 串联全链路 | 与当前阶段保持一致，但第二阶段更依赖可回放能力 |
| `raw_query` | retrieval trace | 原始问题 | 便于复盘用户真实问法 |
| `normalized_query` | retrieval trace | 归一化问题 | 是 planner 与检索的基础输入之一 |
| `intent` | retrieval trace | 记录最终意图识别 | 便于对照 planner 输出 |
| `domain_hint` | retrieval trace | 记录分域提示 | 用于分析域内/域外漂移 |
| `semantic_expansions` | retrieval trace | 记录语义扩展结果 | 用于检查 planner 漂移 |
| `lexical_terms` | retrieval trace | 记录词法检索词 | 用于检查硬关键词是否丢失 |
| `filters` | retrieval trace | 记录实际下发的过滤条件 | 用于排查过滤是否过严或失效 |
| `lexical_hits` | retrieval trace | 记录 lexical top-k | 用于对照 vector / RRF |
| `vector_hits` | retrieval trace | 记录 vector top-k | 用于分析语义召回 |
| `rrf_hits` | retrieval trace | 记录 RRF 融合结果 | 用于验证融合是否有效 |
| `rerank_result` | retrieval trace | 记录 rerank 输出 | 用于区分检索与重排责任 |
| `evidence_spans` | retrieval trace | 记录证据片段 | 用于定位 evidence extraction 是否有效 |
| `final_status` | retrieval trace | 记录最终状态 | 用于对照 response status / fallback |

### 10.2 hard_cases 样本池字段

| 字段 | 所属对象 | 第二阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `trace_id` | hard_cases item | 关联原请求 | 便于回放 |
| `raw_query` | hard_cases item | 原始问题 | 保留用户真实表达 |
| `normalized_query` | hard_cases item | 归一化问题 | 便于分析清洗后的偏移 |
| `domain_hint` | hard_cases item | 记录域提示 | 便于识别跨域误召回 |
| `fallback_reason` | hard_cases item | 标记失败原因 | 用于做问题聚类 |
| `top_candidates` | hard_cases item | 记录 top 候选 | 用于检查错召回 |
| `evidence_spans` | hard_cases item | 记录证据 | 便于判断是“没证据”还是“证据抽错” |
| `user_feedback` | hard_cases item | 用户负反馈 | 是硬样本池入口，不是运营装饰数据 |
| `created_at` | hard_cases item | 记录时间 | 用于时间窗口分析 |

---

## 11. 第二阶段最容易写偏的点

1. 不要把 `domain_hint` 只停留在 planner 层；它在第二阶段可以成为检索层过滤依据。  
2. 不要把 `question_vector` / `answer_vector` 合并回一个“总向量”概念。  
3. 不要把 `source_label` 当成 `source_locator` 使用。  
4. 不要把 `rerank_score`、`bm25_score`、`vector_score` 混成同一类分数。  
5. 不要把 `clarification_required` 当成默认对话模式。  
6. 不要把 `question_aliases` 扩展成全库人工同义词系统。  
7. 不要把 `2_system_design.md` 的字段提前写回 `1_system_design.md` 的最小链路实现。  

---

## 12. 一句话收口

`2_3_field_definitions.md` 的目标不是制造更多字段，而是把第二阶段真正新增的字段分层解释清楚：

- planner 用什么字段
- retrieval 依赖什么字段
- Knowledge Unit 至少要有什么字段
- rerank / evidence / clarification 依赖什么字段
- trace / hard_cases 如何回放

**`2_system_design.md` 的新增字段应围绕 Query Planner、Knowledge Unit、Hybrid Retrieval、Rerank / Evidence、Clarification、Trace 6 条主线收敛，不应回流污染 `1_system_design.md` 的当前最小实现。**
