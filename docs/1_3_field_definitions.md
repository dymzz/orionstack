# OrionStack 当前阶段新增字段说明 v1

> 文档定位：`1_system_design.md` 的字段解释表  
> 命名说明：仅按 `1_2_file_responsibilities.md` / `2_2_file_responsibilities.md` 的命名规范延续为 `1_3_field_definitions.md`，不假设未上传文件的具体内容与版式。  
> 适用范围：`1_system_design.md`

---

## 1. 文档目标

本文档只做一件事：

**对 `1_system_design.md` 当前阶段冻结的关键字段做解释对照，避免后续实现时把字段语义写偏、写散或重复定义。**

本文档不承担以下职责：

- 不重新改写 `1_system_design.md`
- 不补充未在当前阶段冻结的重型 schema
- 不替代接口文档或数据库建表文档
- 不提前定义 `2_system_design.md` 的新增字段

---

## 2. 使用原则

1. 本文档优先解释“当前阶段已经冻结或明确建议冻结”的字段。
2. 同名字段若在不同对象中出现，必须按“所属对象”区分语义。
3. 本文档中的“说明 / 不要误解”为实现约束，不是可选备注。
4. 若后续代码实现需要新增字段，应先判断是否属于当前阶段，避免把 `2_system_design.md` 的字段提前写回 `1_system_design.md`。

---

## 3. 当前阶段字段总览

当前阶段的字段主要分为 5 组：

1. citation 返回字段
2. 最小对外结果状态字段
3. 轻量路由对象字段
4. 回源与入库辅助字段
5. 反馈 / 观测 / 调试字段

---

## 4. citation 返回字段

| 字段 | 所属对象 | 当前阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `citation_id` | citation item | 单条引用的稳定标识 | 只负责单条引用识别，不承担来源定位本身 |
| `source_label` | citation item | 前端展示给用户看的来源名称 | 是展示名称，不等于唯一定位键 |
| `source_locator` | citation item | 回源定位信息 | 必须能把引用定位回 FAQ / 文档位置；可由 `source_url`、`file_path`、`page_number`、`paragraph_id` 等组成 |
| `snippet` | citation item | 最小引用片段 | 只保留最小必要片段，不等于整段正文 |

### 4.1 `source_locator` 的拆分字段

> 当前阶段允许 `source_locator` 由下列字段之一或其组合构成。

| 字段 | 所属对象 | 当前阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `source_url` | locator component | 基于 URL 的回源 | 适用于网页或在线来源，不要求所有来源都必须有 |
| `file_path` | locator component | 基于文件路径的回源 | 适用于本地或文档库场景，不应直接暴露为权限系统 |
| `document_id` | locator component | 文档级唯一标识 | 是文档身份，不等于 chunk 身份 |
| `page_number` | locator component | 页级定位 | 仅在分页文档可用时使用 |
| `paragraph_id` | locator component | 段落级定位 | 适用于段落切分稳定的文档 |
| `chunk_id` | locator component | chunk 级定位 | 适用于按 chunk 入库的内容；当前阶段允许作为等价定位标识 |

---

## 5. 最小对外结果状态字段

| 字段 / 枚举值 | 所属对象 | 当前阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `ok` | response status | 正常回答 | 表示已进入标准回答路径，不代表答案一定完美 |
| `refused` | response status | 明确拒答 | 表示命中安全边界或明确不能回答 |
| `fallback` | response status | 统一兜底 | 表示未进入标准 FAQ 回答路径，不等于系统报错 |
| `system_error` | response status | 系统异常 | 表示不可恢复错误，不应与 `fallback` 混用 |

---

## 6. 轻量路由对象字段（`IntentDecision`）

| 字段 | 所属对象 | 当前阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `route` | `IntentDecision` | 指示当前请求走哪条最小路径 | 当前只允许 `faq_qa` / `fallback` |
| `confidence` | `IntentDecision` | 统一后的逻辑置信度 | 是标准化后的逻辑接口，不承诺严格概率意义 |
| `query_for_search` | `IntentDecision` | 下游检索使用的查询词 | 必须始终为字符串，不得输出复杂计划对象 |

### 6.1 `route` 允许值

| 取值 | 当前阶段作用 | 说明 / 不要误解 |
|---|---|---|
| `faq_qa` | 进入 FAQ / 知识问答主链路 | 不是“任何知识问题都能答” |
| `fallback` | 进入统一兜底路径 | 不是系统错误码 |

### 6.2 `fallback_reason` 最小枚举

| 枚举值 | 当前阶段作用 | 说明 / 不要误解 |
|---|---|---|
| `low_confidence` | 路由或判断置信度不足 | 用于说明“判断不够稳”，不是检索未命中本身 |
| `guardrail_blocked` | 命中护栏 | 优先表示边界阻断 |
| `rule_no_match` | 规则未命中 | 表示规则兜底也没接住 |
| `no_retrieval` | 检索未获得可用结果 | 不等于系统异常 |
| `system_error` | 系统执行异常 | 只用于真正异常路径 |

---

## 7. 回源与入库辅助字段

| 字段 | 所属对象 | 当前阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `embedding_model_version` | index / storage metadata | 标记向量或检索索引对应的 embedding 版本 | 用于避免升级模型后继续无感使用旧向量 |
| `normalized_query` | request / debug | 归一化后的输入文本 | 当前阶段主要用于安全校验、缓存匹配、路由与检索；必须与 `raw_query` 区分 |
| `raw_query` | request / log | 用户原始输入 | 用于审计、排错与观测，不应被归一化后覆盖 |

---

## 8. 反馈与观测字段

### 8.1 核心必记字段

| 字段 | 所属对象 | 当前阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `trace_id` | request / log | 串联输入、路由、检索、生成、反馈 | 是全链路追踪键，应在请求入口生成 |
| `raw_query` | request / log | 记录原始问题 | 与 `normalized_query` 不是同一字段 |
| `retrieved_chunk_ids` | retrieval log | 记录检索命中的候选内容 ID | 默认优先记录 ID，不要求默认落全文 |
| `answer_text` | response / log | 最终返回给用户的回答 | 不应承担全部状态语义 |
| `feedback_label` | feedback | 记录点赞 / 点踩等反馈结果 | 当前阶段建议最小为 `up` / `down` |
| `token_input` | model log | 输入 token 数 | 用于评估成本与模型负载 |
| `token_output` | model log | 输出 token 数 | 用于评估回答长度与成本 |
| `total_latency_ms` | request metric | 整体请求耗时 | 是总耗时，不是首字延迟 |

### 8.2 扩展观测字段

| 字段 | 所属对象 | 当前阶段作用 | 说明 / 不要误解 |
|---|---|---|---|
| `session_id` | session / log | 所属会话标识 | 仅在会话概念存在时记录 |
| `created_at` | log | 请求时间戳 | 用于排序、排查、回放 |
| `router_used` | routing log | 本次实际使用的路由器 / 解析器 | 用于排查不同 parser 行为差异 |
| `route_result` | routing log | 最终路由结果 | 建议与 `IntentDecision.route` 保持一致语义 |
| `raw_confidence` | routing log | 路由原始置信度 | 用于分析模型/规则原始输出，不替代标准化 `confidence` |
| `threshold_used` | routing log | 本次判定采用的阈值 | 用于排查阈值漂移 |
| `cache_hit` | cache log | 是否命中缓存 | 当前阶段主要服务高频 FAQ 拦截 |
| `fallback_reason` | routing / response log | 兜底原因 | 应收敛为固定枚举，避免自由文本扩散 |
| `response_status` | response log | 最终对外结果状态 | 建议与 `ok` / `refused` / `fallback` / `system_error` 对齐 |
| `input_mode` | input log | 输入来源方式 | 例如自由输入、示例点击、模板生成 |
| `question_template_used` | input log | 命中的固定问句模板标识 | 当前阶段仅用于输入引导观测 |
| `raw_query_length` | input metric | 原始输入长度 | 用于观察超长输入问题 |
| `normalized_query_length` | input metric | 归一化后输入长度 | 用于评估清洗影响 |
| `first_token_latency_ms` | stream metric | 首字延迟 | 仅在流式生成场景下记录 |
| `router_prompt_version` | config / debug | 路由 prompt 或规则版本 | 用于回放与定位版本差异 |
| `answer_prompt_version` | config / debug | 回答生成 prompt 版本 | 不应与 router 版本混用 |
| `config_version` | config / debug | 当前阈值与策略配置版本 | 作为整体配置快照标识 |
| `normalized_query` | request / debug | 归一化后的实际查询文本 | 用于观察清洗后输入 |
| `retrieved_chunk_scores` | retrieval log | 候选内容的相似度或排序分数 | 当前阶段用于调试，不要求前端默认展示 |
| `final_prompt` | debug | 最终发送给模型的 prompt | 开发态可记录；生产态可按需关闭或脱敏 |
| `debug_bundle_id` | debug | 一组调试上下文的标识 | 用于前端复制或回放调试上下文 |
| `demo_mode_used` | debug / environment | 标记是否运行于 Demo 模式 | 用于隔离 Demo 与正式路径 |

---

## 9. 当前阶段最容易写偏的点

### 9.1 不要把这些字段混成一类

1. `response_status` 与 `answer_text` 不是同一层语义。  
2. `confidence` 与 `raw_confidence` 不是同一字段。  
3. `source_label` 与 `source_locator` 不是同一作用。  
4. `raw_query` 与 `normalized_query` 必须同时保留。  
5. `fallback_reason` 与 `system_error` 不能互相代替。  

### 9.2 当前阶段不应提前引入的字段类型

当前阶段不建议提前写入以下类型字段：

- 多工具计划字段
- 图执行状态字段
- 多 Agent 协作字段
- 复杂权限系统字段
- `2_system_design.md` 中的 Query Planner / Hybrid Retrieval / Rerank 专用字段

---

## 10. 最终结论

`1_3_field_definitions.md` 的目标不是补全一份大而全 schema，而是冻结当前阶段最容易跑偏的字段语义。

一句话收敛：

**`1_system_design.md` 当前应优先冻结 citation、结果状态、轻量路由、回源定位、反馈与观测字段；不要把下一阶段的检索增强字段提前混入当前实现。**
