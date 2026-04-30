# OrionStack 第三阶段字段定义

> 状态：**基线 v1**
> 对应设计文档：`docs/designs/3_system_design.md`
> 配套职责文档：`docs/3_2_file_responsibilities.md`
> 目的：冻结 Phase 3 核心对象的字段语义与约束

---

## 1. 文档目标

本文档只回答：

**Phase 3 核心对象每个字段的语义、类型、约束与默认值是什么。**

本文档不承担：

- 不重写 `3_system_design.md` 的设计正文
- 不解释 Phase 1 / Phase 2 已有字段（见 `1_3_field_definitions.md` / `2_3_field_definitions.md`）
- 不替代 `3_2_file_responsibilities.md` 的文件职责边界

---

## 2. SourceRecord

### 2.1 语义

从原系统导入的原始记录。所有发布单元（KnowledgeUnit / ActionLink / DynamicQuery）和抽取候选（ExtractionCandidate）都以此为来源锚点。

### 2.2 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `source_record_id` | string | 是 | — | 本系统内原始来源记录 ID。格式建议 `sr-{source_system}-{hash[:8]}` |
| `tenant_id` | string | 是 | `"default"` | 租户标识。当前阶段只支持单租户，默认 `"default"` |
| `source_system` | string | 是 | — | 来源系统标识。枚举值：`dingtalk_hr` / `feishu_hr` / `zendesk_help` / `confluence` / `manual_export` |
| `source_object_type` | string | 是 | — | 来源对象类型。枚举值：`faq_doc` / `kb_article` / `help_page` / `policy_doc` / `process_doc` |
| `external_id` | string | 是 | — | 原系统记录 ID。与 `source_system` 联合唯一 |
| `source_locator` | string | 是 | — | 回源定位信息。可以是 URL、文件路径或 record pointer |
| `title` | string | 是 | `""` | 标题 |
| `raw_content` | text | 是 | `""` | 原始内容，不做结构化处理 |
| `content_hash` | string | 是 | — | `raw_content` 的 SHA-256 hex 前 16 位。用于增量对比 |
| `source_updated_at` | datetime | 是 | — | 来源系统中的最后更新时间 |
| `export_batch_id` | string | 是 | — | 导出批次 ID。标识这批数据从原系统的哪次导出产生 |
| `import_batch_id` | string | 否 | `None` | 导入批次 ID。标识本系统内的哪次 ImportBatch |
| `access_scope` | string | 是 | `"internal"` | 问答层最小权限范围。复用 Phase 1 枚举：`public / internal / restricted / team` |
| `status` | enum | 是 | `"active"` | `active / revoked / deleted / superseded` |
| `synced_at` | datetime | 是 | — | 导入完成时间 |

### 2.3 唯一约束

- `(source_system, external_id)` 联合唯一

### 2.4 状态流转

```text
active → revoked    (原系统撤权)
active → deleted    (原系统删除)
active → superseded (被更新版本替代，content_hash 变化)
```

---

## 3. KnowledgeUnit 扩展字段

Phase 2 已有的 `KnowledgeUnit` 字段不变（见 `2_3_field_definitions.md`），Phase 3 新增以下字段：

### 3.1 新增字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `tenant_id` | string | 是 | `"default"` | 租户标识 |
| `source_record_id` | string | 否 | `None` | 对应来源记录。`None` 表示当前由 manual_faq / seed 直接生成，不经过 SourceRecord |
| `import_batch_id` | string | 否 | `None` | 本单元对应的导入批次。用于从答案追到本系统导入批次 |
| `unit_version` | integer | 是 | `1` | 单元版本。每次从同一 SourceRecord 重新发布时 +1 |
| `fresh_until` | datetime | 否 | `None` | 正常可答上限。`None` 表示永不过期 |
| `stale_after` | datetime | 否 | `None` | 过期阈值。`None` 表示永不过期 |
| `published_at` | datetime | 否 | `None` | 发布时间。`None` 表示尚未发布 |

### 3.2 兼容性约束

- 现有 `manual_faq` / seed 生成的 KnowledgeUnit：`source_record_id = None`，`import_batch_id = None`，`unit_version = 1`，`fresh_until = None`，`stale_after = None`
- 新字段默认值保证 Phase 2 已有数据和测试零回归

### 3.3 新鲜度判定规则

| 条件 | 状态 | 处理 |
|---|---|---|
| `fresh_until is None` 或 `now <= fresh_until` | `fresh` | 正常可答 |
| `fresh_until is not None` 且 `fresh_until < now <= stale_after` | `warning` | 可答，附带提示 |
| `stale_after is not None` 且 `now > stale_after` | `stale` | 不直接答，优先跳原系统 |

---

## 4. ActionLink

### 4.1 语义

"跳"到原系统的入口。不作为核心答案知识本体，作为回答后的下一步动作入口。

### 4.2 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `action_link_id` | string | 是 | — | 链接 ID。格式建议 `al-{source_system}-{hash[:8]}` |
| `tenant_id` | string | 是 | `"default"` | 租户标识 |
| `source_record_id` | string | 是 | — | 来源记录 |
| `label` | string | 是 | — | 展示文案，如"去请假系统"、"查看审批记录" |
| `system_type` | string | 是 | — | 来源系统类型。复用 `source_system` 枚举 |
| `url` | string | 是 | — | 跳转链接 |
| `resource_type` | string | 是 | — | 目标资源类型。如 `leave_form` / `approval_detail` / `payroll_page` |
| `access_scope` | string | 是 | `"internal"` | 可见范围 |
| `status` | enum | 是 | `"active"` | `active / revoked / deleted` |
| `fresh_until` | datetime | 否 | `None` | 有效期 |
| `published_at` | datetime | 是 | — | 发布时间 |

---

## 5. DynamicQuery

### 5.1 语义

运行时允许查询的少量动态状态定义。不长期固化到知识池，运行时现查。

### 5.2 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `dynamic_query_id` | string | 是 | — | 查询定义 ID |
| `tenant_id` | string | 是 | `"default"` | 租户标识 |
| `source_record_id` | string | 否 | `None` | 对应来源记录。用于 SourceRecord 删除 / 撤权时传播失效 |
| `query_key` | string | 是 | — | 查询标识。如 `leave_status` / `payroll_balance` |
| `resource_type` | string | 是 | — | 资源类型。如 `leave` / `payroll` / `approval` |
| `action` | string | 是 | `"read"` | 允许动作。当前只支持 `read` |
| `scope_type` | string | 是 | `"self"` | 查询范围。`self / org / role` |
| `allowed_roles` | list[string] | 否 | `[]` | `scope_type = role` 时允许执行该查询的角色集合 |
| `status` | enum | 是 | `"active"` | `active / revoked` |
| `description` | text | 是 | — | 说明 |

### 5.3 约束

- `(query_key, tenant_id)` 联合唯一
- `scope_type = self` 时，运行时只允许查当前用户自己的状态
- `scope_type = role` 时，运行时必须命中 `allowed_roles`
- 当前阶段 `action` 只支持 `read`，不支持 `write / delete`

---

## 6. ExtractionCandidate

### 6.1 语义

LLM 结构化抽取后的候选对象。候选与发布分层，LLM 只写入候选，审核通过后才发布。

### 6.2 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `candidate_id` | string | 是 | — | 候选 ID |
| `tenant_id` | string | 是 | `"default"` | 租户标识 |
| `source_record_id` | string | 是 | — | 来源记录 |
| `candidate_type` | string | 是 | — | `faq` / `action_link` / `dynamic_query` |
| `payload_json` | json | 是 | — | 候选内容，结构取决于 `candidate_type` |
| `extractor_model` | string | 是 | — | 抽取模型标识。如 `qwen-plus` / `qwen3-1.7b` |
| `prompt_version` | string | 是 | — | prompt 版本。如 `v1` / `v2` |
| `source_span` | string | 是 | — | 来源片段定位。标识从 raw_content 的哪段文本抽取 |
| `source_span_hash` | string | 是 | — | 来源片段哈希。用于判定原文本是否变化 |
| `review_status` | enum | 是 | `"pending"` | `pending / approved / rejected` |
| `reviewed_by` | string | 否 | `None` | 审核人 |
| `reviewed_at` | datetime | 否 | `None` | 审核时间 |
| `created_at` | datetime | 是 | — | 创建时间 |

### 6.3 状态流转

```text
pending → approved   (审核通过，触发发布到 KnowledgeUnit / ActionLink / DynamicQuery)
pending → rejected   (审核拒绝)
```

### 6.4 payload_json 结构

按 `candidate_type` 不同：

- `faq`：`{"question": "...", "answer": "...", "keywords": [...]}`
- `action_link`：`{"label": "...", "url": "...", "resource_type": "..."}`
- `dynamic_query`：`{"query_key": "...", "resource_type": "...", "scope_type": "...", "allowed_roles": [...], "description": "..."}`

## 7. ExtractionTask

### 7.1 语义

同步层产生的待抽取任务。它不是 LLM 候选，不参与审核发布，只用于把 SourceRecord 新增 / 更新后的重抽需求交给抽取层。

### 7.2 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `extraction_task_id` | string | 是 | — | 待抽取任务 ID |
| `tenant_id` | string | 是 | `"default"` | 租户标识 |
| `source_record_id` | string | 是 | — | 需要抽取的来源记录 |
| `source_system` | string | 是 | — | 来源系统 |
| `external_id` | string | 是 | — | 原系统记录 ID |
| `reason` | enum | 是 | — | `new_source_record / source_record_updated` |
| `status` | enum | 是 | `"pending"` | `pending / processing / completed / failed` |
| `import_batch_id` | string | 否 | `None` | 触发该任务的导入批次 |
| `supersedes_source_record_id` | string | 否 | `None` | 若由更新触发，指向被替代的旧 SourceRecord |
| `started_at` | datetime | 否 | `None` | 开始消费时间 |
| `finished_at` | datetime | 否 | `None` | 消费完成时间 |
| `error_summary` | text | 否 | `None` | 成功摘要或失败原因 |
| `created_at` | datetime | 是 | — | 创建时间 |

---

## 8. CleanupTask

### 8.1 语义

SourceRecord 删除、撤权或被新版本替代后产生的物理清理任务。它不负责逻辑失效，只把已经不可见的来源记录交给后台清理编排。

### 8.2 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `cleanup_task_id` | string | 是 | — | 清理任务 ID |
| `tenant_id` | string | 是 | `"default"` | 租户标识 |
| `source_record_id` | string | 是 | — | 需要物理清理的来源记录 |
| `source_system` | string | 是 | — | 来源系统 |
| `external_id` | string | 是 | — | 原系统记录 ID |
| `reason` | enum | 是 | — | `source_record_deleted / source_record_revoked / source_record_superseded` |
| `status` | enum | 是 | `"pending"` | `pending / processing / completed / failed / skipped` |
| `source_status` | enum | 是 | — | 触发清理时的 SourceRecord 状态：`deleted / revoked / superseded` |
| `import_batch_id` | string | 否 | `None` | 关联导入批次 |
| `started_at` | datetime | 否 | `None` | 开始消费时间 |
| `finished_at` | datetime | 否 | `None` | 消费完成时间 |
| `error_summary` | text | 否 | `None` | ES / 向量 backend 的处理摘要或失败原因 |
| `created_at` | datetime | 是 | — | 创建时间 |

---

## 9. ImportBatch

### 9.1 语义

一次同步 / 导入任务。记录批次级元信息、状态与追溯。

### 9.2 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `import_batch_id` | string | 是 | — | 导入批次 ID |
| `tenant_id` | string | 是 | `"default"` | 租户标识 |
| `source_system` | string | 是 | — | 来源系统 |
| `mode` | string | 是 | — | `full` / `incremental` |
| `started_at` | datetime | 是 | — | 开始时间 |
| `finished_at` | datetime | 否 | `None` | 结束时间 |
| `status` | enum | 是 | `"running"` | `running / success / partial_success / failed` |
| `record_count` | integer | 否 | `0` | 处理记录数 |
| `error_summary` | text | 否 | `None` | JSON 摘要：`added / updated / unchanged / failed / errors` |

### 9.3 状态流转

```text
running → success          (全部成功)
running → partial_success  (部分成功)
running → failed           (全部失败)
```

---

## 10. 枚举值汇总

### 10.1 source_system

| 值 | 说明 |
|---|---|
| `dingtalk_hr` | 钉钉 HR 导出 |
| `feishu_hr` | 飞书 HR 导出 |
| `zendesk_help` | Zendesk 帮助中心导出 |
| `confluence` | Confluence 知识库导出 |
| `manual_export` | 手动导出 / 上传 |

### 10.2 source_object_type

| 值 | 说明 |
|---|---|
| `faq_doc` | FAQ 文档 |
| `kb_article` | 知识库文章 |
| `help_page` | 帮助页面 |
| `policy_doc` | 制度文档 |
| `process_doc` | 流程文档 |

### 10.3 status（SourceRecord / ActionLink）

| 值 | 说明 |
|---|---|
| `active` | 正常可用 |
| `revoked` | 撤权 / 停用 |
| `deleted` | 已删除 |
| `superseded` | 被新版本替代 |

### 10.4 review_status（ExtractionCandidate）

| 值 | 说明 |
|---|---|
| `pending` | 待审核 |
| `approved` | 已通过 |
| `rejected` | 已拒绝 |

### 10.5 import_batch status

| 值 | 说明 |
|---|---|
| `running` | 进行中 |
| `success` | 全部成功 |
| `partial_success` | 部分成功 |
| `failed` | 全部失败 |

### 10.6 extraction_task status

| 值 | 说明 |
|---|---|
| `pending` | 等待消费 |
| `processing` | 消费中 |
| `completed` | 已生成候选 |
| `failed` | 消费失败 |

### 10.7 cleanup_task status

| 值 | 说明 |
|---|---|
| `pending` | 等待消费 |
| `processing` | 消费中 |
| `completed` | 已完成物理清理 |
| `failed` | 清理失败 |
| `skipped` | 因安全边界或 backend 未配置而跳过 |

### 10.8 scope_type（DynamicQuery）

| 值 | 说明 |
|---|---|
| `self` | 只查当前用户自己的状态 |
| `org` | 查组织范围内 |
| `role` | 按角色限定，必须配置并命中 `allowed_roles` |

---

## 11. SystemAdapter Protocol（运行时适配器接口）

### 11.1 语义

`SystemAdapter` 是所有外部系统适配器的抽象协议（Protocol）。动态查询不直连具体外部系统，而是通过此协议解耦。任何新系统只需实现此协议即可接入。当前仓库已实现 `OdooAdapter` / `MockAdapter`，但它们是现有实现，不是架构边界本身。

### 11.2 接口定义

```python
class SystemAdapter(Protocol):
    @property
    def name(self) -> str:
        """适配器名称标识，如 'odoo' / 'mock' / 'dingtalk'。"""
        ...

    def fetch(self, resource_type: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """
        统一查询入口。

        参数：
          resource_type: OrionStack 资源类型标识，如 'leave_status' / 'expense_status'
          params:        查询参数，由具体 adapter 解释；通用层不假设外部系统方言

        返回：
          标准化行数据列表，每个元素是一个 dict，key 为字段名，value 为原始值。
          不应包含 'id' 字段（由 sanitize 阶段去除）。
        """
        ...
```

### 11.3 已实现适配器

| 适配器 | 文件 | 传输方式 | 可配置项 |
|---|---|---|---|
| `OdooAdapter` | `runtime/odoo_adapter.py` | XML-RPC | `url` / `db` / `uid` / `password` / `model_fields_map` |
| `MockAdapter` | `runtime/mock_adapter.py` | 内存 fixture | `fixtures` |

### 11.4 OdooAdapter model_fields_map 格式

```python
{
    "resource_type": ("odoo.model.name", ["field1", "field2", ...]),
}
```

| resource_type | Odoo 模型 | 字段 |
|---|---|---|
| `leave_status` | `hr.leave` | `name, holiday_status_id, date_from, date_to, state, number_of_days` |
| `expense_status` | `hr.expense` | `name, total_amount, state, date` |
| `attendance_balance` | `hr.attendance` | `check_in, check_out, worked_hours` |
| `crm_pipeline` | `crm.lead` | `name, expected_revenue, stage_id, probability` |

### 11.5 如何新增适配器

1. 在 `backend/app/runtime/` 下新建文件（如 `dingtalk_adapter.py`）
2. 实现 `SystemAdapter` Protocol 的 `name` 属性和 `fetch()` 方法
3. 在 `backend/app/runtime/adapter_factory.py` 注册新分支
4. 在 `backend/app/config/settings.py` 添加该适配器所需环境变量（如有）
5. 在种子数据中注册该适配器支持的 `resource_type`

### 11.6 适配器选择配置

| 环境变量 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `ORIONSTACK_DYNAMIC_QUERY_ADAPTER` | string | `mock` | 当前默认适配器名称，可替换为 `odoo` 或其他实现 |
| `ORIONSTACK_ODOO_URL` | string | `http://localhost:8069` | Odoo 服务地址 |
| `ORIONSTACK_ODOO_DB` | string | `odoo` | Odoo 数据库名 |
| `ORIONSTACK_ODOO_UID` | int | `2` | Odoo 用户 ID |
| `ORIONSTACK_ODOO_PASSWORD` | string | — | Odoo 用户密码；仅在使用 OdooAdapter 时通过环境变量注入 |

---

## 12. Phase 2 → Phase 3 字段迁移说明

| Phase 2 已有字段 | Phase 3 变化 | 说明 |
|---|---|---|
| `KnowledgeUnit.business_domain` | 不变 | 继续使用 8 域枚举 |
| `KnowledgeUnit.lifecycle_status` | 不变 | `active / revoked / deprecated / archived` |
| `KnowledgeUnit.access_scope` | 不变 | `public / internal / restricted / team` |
| `KnowledgeUnit.source_locator` | 不变 | 扩展用途：可指向 `SourceRecord.source_locator` |
| `KnowledgeUnit.version` | 不变（string `"v1"`） | 新增 `unit_version`（integer），两者并存 |

---

## 13. 一句话收口

Phase 3 的字段设计遵循：**新字段默认值保证 Phase 2 零回归，枚举值优先复用，新对象以 SourceRecord 为来源锚点，外部系统通过 Protocol 解耦。**
