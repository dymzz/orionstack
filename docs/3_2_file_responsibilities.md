# OrionStack 第三阶段文件职责边界

> 状态：**基线 v1**
> 对应设计文档：`docs/designs/3_system_design.md`
> 配套进度文档：`docs/3_1_progress.md`
> 配套字段文档：`docs/3_3_field_definitions.md`
> 目的：定义 Phase 3 新增文件、扩展文件与预留文件位的职责边界

---

## 1. 文档目标

本文档只回答：

**Phase 3 的每个文件负责什么、不负责什么、改什么、不改什么。**

本文档不承担：

- 不重写 `3_system_design.md` 的设计正文
- 不替代 `3_3_field_definitions.md` 的字段语义解释
- 不替代 `3_1_progress.md` 的推进状态记录

---

## 2. Phase 3 新增文件

### 2.1 数据层

#### `backend/app/storage/repositories/source_record_repo.py`

职责：

- `SourceRecord` 的 CRUD
- 按 `source_system` / `external_id` 查询
- 按 `content_hash` 对比判定新增 / 更新 / 不变
- 按 `status` 过滤

不负责：

- 不直接写入 ES / 向量存储
- 不负责抽取逻辑
- 不负责发布 KnowledgeUnit

#### `backend/app/storage/repositories/import_batch_repo.py`

职责：

- `ImportBatch` 的 CRUD
- 记录同步批次的开始 / 结束 / 状态 / 错误
- 按批次查询导入记录

不负责：

- 不负责批次内具体的同步逻辑编排
- 不负责 ES / 向量写入

#### `backend/app/storage/repositories/extraction_candidate_repo.py`

职责：

- `ExtractionCandidate` 的 CRUD
- 按 `source_record_id` / `candidate_type` / `review_status` 查询
- 候选状态流转（`pending → approved / rejected`）

不负责：

- 不负责 LLM 抽取逻辑
- 不负责审核后的发布动作

#### `backend/app/storage/repositories/action_link_repo.py`

职责：

- `ActionLink` 的 CRUD
- 按 `source_record_id` / `status` / `access_scope` 查询
- 为检索结果附带 action link

不负责：

- 不负责跳转目标系统的实际逻辑
- 不负责 URL 生成（由同步层填充）

#### `backend/app/storage/repositories/dynamic_query_repo.py`

职责：

- `DynamicQuery` 的 CRUD
- 按 `query_key` / `status` 查询
- 运行时判定某查询是否允许执行

不负责：

- 不负责实际的状态查询调用
- 不负责缓存

---

### 2.2 运行时适配层

#### `backend/app/runtime/system_adapter.py`

职责：

- 定义 `SystemAdapter` Protocol（抽象接口）
- 约束所有外部系统适配器必须实现 `.name` 属性和 `.fetch(resource_type, params)` 方法
- 提供 `@runtime_checkable` 协议，支持 `isinstance` 检查

不负责：

- 不包含任何具体系统实现

#### `backend/app/runtime/odoo_adapter.py`

职责：

- 实现 `SystemAdapter` Protocol，通过 XML-RPC 连接 Odoo
- `model_fields_map` 将 `resource_type` 映射到 Odoo 模型 + 字段列表
- 映射表通过构造参数可覆盖，适配不同 Odoo 实例
- 作为当前已实现的外部系统适配器之一，为后续多系统适配提供参考

不负责：

- 不负责 query_key 正则检测（由 `DynamicQueryService` 负责）
- 不负责判权（由 `DynamicQueryService` 负责）
- 不负责数据清洗和格式化（由 `DynamicQueryService._sanitize_rows()` 负责）

#### `backend/app/runtime/mock_adapter.py`

职责：

- 实现 `SystemAdapter` Protocol，返回固定 fixture 数据
- 用于开发和测试环境
- fixture 数据通过构造参数可注入

不负责：

- 不连接任何真实外部系统

#### `backend/app/runtime/adapter_factory.py`

职责：

- 根据 `settings.dynamic_query_adapter` 选择并创建适配器实例
- 解耦 `DynamicQueryService` 与具体适配器实现

不负责：

- 不负责适配器的业务逻辑
- 不负责 query_key 检测或判权

#### `backend/app/runtime/dynamic_query_service.py`

职责：

- `detect_query_key(query)` — 正则识别动态查询意图
- `is_allowed(query_key)` — 通过 repo 判权
- `execute(query_key, params)` — 调用 `SystemAdapter.fetch()` 获取实时数据并返回 `DynamicQueryResultItem`
- `_sanitize_rows()` — 清洗原始行数据（去除 `id`、序列化复杂类型）

不负责：

- 不直接连接外部系统（通过 adapter 间接调用）
- 不负责适配器实例创建（由 `adapter_factory` 负责）

---

### 2.2 同步层

#### `backend/app/sync/sync_service.py`

职责：

- 编排一次完整的同步流程（`ImportBatch` → `SourceRecord` → 判定变更 → 更新发布层）
- 对比 `content_hash` 判定新增 / 更新 / 删除 / 不变
- 触发 tombstone 处理
- 触发 ES / 向量写入

不负责：

- 不负责解析原始导出文件格式（由 `sync_parser.py` 负责）
- 不负责 LLM 抽取（由 `extract/` 负责）

#### `backend/app/sync/sync_parser.py`

职责：

- 解析不同来源系统的导出文件格式
- 输出标准化的 `SourceRecord` 列表
- 按来源系统类型分发解析逻辑

不负责：

- 不负责同步编排
- 不负责 ES / 向量写入

#### `backend/app/sync/freshness_checker.py`

职责：

- 运行时判定 `KnowledgeUnit` / `ActionLink` 的新鲜度区间
- 返回 `fresh / warning / stale` 三态
- 为 `chat_service.py` 提供新鲜度信号

不负责：

- 不负责触发同步刷新
- 不负责 ES / 向量操作

#### `backend/app/sync/tombstone_handler.py`

职责：

- 接收 `SourceRecord` 的状态变更（`revoked / deleted`）
- 传播到关联 `KnowledgeUnit` / `ActionLink` / `DynamicQuery`
- 触发异步 ES / 向量清理

不负责：

- 不负责同步流程编排
- 不负责候选审核

---

### 2.3 抽取层

#### `backend/app/extract/llm_extractor.py`

职责：

- 接收已解析的 payload 列表，创建 `ExtractionCandidate` 对象
- 记录 `extractor_model` / `prompt_version` / `source_span` / `source_span_hash`

不负责：

- 不负责调用 LLM API（由 `extraction_service.py` 负责）
- 不负责候选审核

#### `backend/app/extract/prompt_templates.py`

职责：

- 定义抽取 prompt 模板（系统 prompt + 三类候选格式说明）
- `build_extraction_messages()` 构造 API 调用的 messages 列表
- `parse_extraction_response()` 解析 LLM 返回的 JSON

不负责：

- 不负责调用 API
- 不负责创建候选对象

#### `backend/app/extract/extraction_service.py`

职责：

- 调用当前配置的抽取 provider（当前仓库默认示例为 DashScope `qwen-plus`），传入 prompt 模板生成的 messages
- 解析 LLM 返回的候选 JSON，通过 `llm_extractor` 创建 `ExtractionCandidate`
- 将候选写入 `ExtractionCandidateRepo`
- 当前实现读取 `ORIONSTACK_QWEN_API_KEY`，若为空则回退到 `DASHSCOPE_API_KEY`

不负责：

- 不负责候选审核与发布
- 不负责构造 prompt（由 `prompt_templates.py` 负责）

#### `backend/app/extract/candidate_reviewer.py`

职责：

- `review_candidate()` — 审核候选，状态流转（`pending → approved / rejected`）
- `publish_candidate()` — 审核通过后发布到目标对象（支持 3 种类型）：
  - `faq` → `KnowledgeUnit`（通过 `map_faq_item_to_knowledge_unit`）
  - `action_link` → `ActionLink`（写入 `ActionLinkRepo`）
  - `dynamic_query` → `DynamicQuery`（写入 `DynamicQueryRepo`）
- `publish_approved_faq_candidate()` — 向后兼容的 FAQ 专用发布

不负责：

- 不负责人工审核 UI
- 不负责 ES / 向量写入

不负责：

- 不负责 LLM 抽取
- 不负责人工审核 UI（只提供规则校验）

---

## 3. Phase 3 扩展的已有文件

### 3.1 `backend/app/storage/repositories/knowledge_unit_repo.py`

扩展方向：

- `KnowledgeUnit` dataclass 新增字段：`tenant_id` / `source_record_id` / `unit_version` / `fresh_until` / `stale_after` / `published_at`
- `map_faq_item_to_knowledge_unit()` 补全新字段映射
- `list_all()` / `list_faq_units()` 支持 `tenant_id` 和 freshness 过滤
- 新增 `publish_from_candidate()` 方法：从审核通过的 `ExtractionCandidate` 生成 `KnowledgeUnit`

不改变：

- 现有 `unit_id` / `source_kind` / `question` / `answer` / `body_text` / `keywords` / `business_domain` 等字段语义不变
- 现有 JSONL / markdown seed 加载逻辑不变
- Phase 2 已有的默认值行为不变

### 3.2 `backend/app/indexing/elastic_indexer.py`

扩展方向：

- ES mapping 新增 Phase 3 字段
- `ensure_index()` 升级 mapping 版本
- 写入时包含新字段

不改变：

- 现有 indexing 流程不变
- IK 分词配置不变

### 3.3 `backend/app/services/chat_service.py`

扩展方向：

- 检索结果的新鲜度判定（调用 `freshness_checker`）
- 回答中附带 action link
- stale 区间的提示文案
- 动态查询集成：FAQ 路由低置信度时尝试 `_try_dynamic_query()`
- `_find_action_links_by_resource_type()` 按 resource_type 查找关联 action link

不改变：

- 现有 planner → hybrid → rerank → evidence → clarification 主链路不变
- 动态查询不拦截高置信度 FAQ 路由

### 3.4 `backend/app/observability/retrieval_trace.py`

扩展方向：

- trace 新增 `source_record_id` / `import_batch_id` / `unit_version` / `freshness_status`

不改变：

- 现有 trace 结构与写入逻辑不变

### 3.5 `backend/app/config/settings.py`

扩展方向：

- 新增 Phase 3 最小配置项（freshness 默认阈值、同步模式等）
- 新增动态查询适配器配置（`dynamic_query_adapter` / `odoo_url` / `odoo_db` / `odoo_uid` / `odoo_password`）

不改变：

- 现有 Phase 1 / Phase 2 配置项不变

---

## 4. Phase 3 预留文件位（第一轮不实现）

以下文件在设计中有明确定义，但第一轮不急于落地：

- `backend/app/api/routes/sync.py` — 同步管理 API（按需）
- `backend/app/runtime/dingtalk_adapter.py` — 钉钉适配器（未来扩展，只需实现 Protocol 即可）
- `backend/app/runtime/feishu_adapter.py` — 飞书适配器（未来扩展）

---

## 4.1 已实现的 API 端点

### 抽取管线 API (`backend/app/api/routes/extraction.py`)

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/extraction/extract` | POST | 从 SourceRecord 抽取候选（调用当前配置的抽取 provider） |
| `/api/extraction/review` | POST | 审核（approve/reject）+ 自动发布 |
| `/api/extraction/candidates` | GET | 列出候选（按 status 过滤） |

### CLI 管线脚本 (`scripts/pipeline_cli.py`)

| 命令 | 说明 |
|---|---|
| `pipeline_cli import --file <path> --title <t>` | 导入文档为 SourceRecord |
| `pipeline_cli extract --source-record-id <id>` | 抽取候选 |
| `pipeline_cli review --candidate-id <id> --approve` | 审核单条候选 |
| `pipeline_cli list --status pending` | 列出候选 |

`import` 支持 `--auto-approve` 一步完成：导入 → 抽取 → 审核 → 发布。

---

## 5. 不做的事

以下文件/逻辑明确不在 Phase 3 中创建：

- 不创建全平台 API 统一层
- 不创建 RBAC / ABAC 权限服务
- 不创建工作流引擎
- 不把 Phase 3 的逻辑写回 Phase 1 / Phase 2 的旧文件
- 不把 `SourceRecord` 的原始内容解析逻辑混入 `knowledge_unit_repo.py`

---

## 6. 一句话收口

Phase 3 的文件职责边界遵循：**新文件优先新增，已有文件只扩展不重写，旧链路不破坏。**
