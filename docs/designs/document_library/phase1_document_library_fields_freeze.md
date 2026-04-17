# 第一阶段通用企业文档库最小字段冻结表

## 1. 文档目标

本文档用于冻结 OrionStack 第一阶段“通用企业文档库”的最小字段集合，作为：

- 文档上传与登记
- 文档解析与切块
- 检索与 citation 回源
- 前端文档展示与筛选
- 后续第二阶段扩展

的统一基线。

当前阶段的原则是：

- 先保证知识问答主链路稳定可用
- 先做轻量元数据，不做重型知识中台
- 先做访问范围标记，不做细粒度权限系统

---

## 2. 第一阶段冻结范围

第一阶段文档库只冻结以下 5 类元数据维度：

1. 业务域（business_domain）
2. 文档类型（document_type）
3. 来源类型（source_type）
4. 生命周期状态（lifecycle_status）
5. 访问范围标记（access_scope）

当前阶段不冻结：

- RBAC/ABAC 权限规则
- 文档级授权审批流
- 多租户空间隔离规则
- 复杂标签体系
- 知识图谱实体关系

---

## 3. 最小字段冻结表

| 字段名 | 类型 | 必填 | 说明 | 示例 |
|---|---|---:|---|---|
| `document_id` | string | 是 | 文档唯一标识 | `doc_hr_0001` |
| `title` | string | 是 | 文档标题 | `年假申请流程` |
| `business_domain` | enum | 是 | 所属业务域 | `hr` |
| `document_type` | enum | 是 | 文档类型 | `process` |
| `source_type` | enum | 是 | 文档来源类型 | `upload` |
| `lifecycle_status` | enum | 是 | 生命周期状态 | `active` |
| `access_scope` | enum | 是 | 访问范围标记 | `internal` |
| `access_scope_value` | string | 否 | 访问范围补充值，仅在 `team` 等场景使用 | `hr` |
| `source_locator` | string | 是 | 文档来源定位信息 | `uploads/hr/leave_policy_v1.pdf` |
| `created_at` | datetime | 是 | 创建时间 | `2026-04-16T10:00:00Z` |
| `updated_at` | datetime | 是 | 最近更新时间 | `2026-04-16T10:00:00Z` |

---

## 4. 枚举冻结

### 4.1 `business_domain`

第一阶段建议固定为：

- `hr`
- `finance`
- `it`
- `ops`
- `legal`
- `product`
- `sales`
- `general`

当前阶段首个实际落地域：

- `hr`

### 4.2 `document_type`

第一阶段建议固定为：

- `policy`：制度 / 规范
- `process`：流程说明
- `faq`：常见问答
- `guide`：操作手册
- `notice`：通知公告
- `template`：模板
- `reference`：参考资料

### 4.3 `source_type`

第一阶段建议固定为：

- `upload`
- `manual_faq`
- `imported`

### 4.4 `lifecycle_status`

第一阶段建议固定为：

- `draft`
- `active`
- `deprecated`
- `archived`

默认检索范围建议：

- 仅 `active`

### 4.5 `access_scope`

第一阶段建议固定为：

- `public`：全员公开可见
- `internal`：企业内部可见
- `restricted`：受限内容
- `team`：团队范围内容

说明：

- 当前阶段只做访问范围标记
- 不做真正的细粒度权限控制
- `access_scope_value` 只在 `team` 等场景下补充范围值

---

## 5. 与 citation / 检索链路的关系

以上字段中，与当前问答链路直接相关的最小字段为：

- `document_id`
- `title`
- `business_domain`
- `document_type`
- `lifecycle_status`
- `access_scope`
- `source_locator`

其作用分别为：

- `document_id`：后端记录、chunk 归属、citation 回源
- `title`：前端文档展示与 citation 来源展示
- `business_domain`：前端筛选、后续第二场景扩展、检索过滤预留
- `document_type`：用户理解文档性质、前端分类展示
- `lifecycle_status`：避免陈旧文档污染检索
- `access_scope`：访问边界预留
- `source_locator`：原始文档定位

---

## 6. 第一阶段不建议继续增加的字段

当前阶段不建议纳入“最小冻结表”的字段包括：

- `owner_user_id`
- `approval_status`
- `confidential_level`
- `department_tree_path`
- `retention_policy`
- `classification_code`
- `review_cycle`
- `security_label`
- `tenant_id`
- `rbac_policy_id`

这些字段如果现在加入，会把 Phase 1 从“知识问答最小闭环”推进成“企业知识治理系统”，不符合当前边界。

---

## 7. 结论

第一阶段通用企业文档库的最小字段冻结结论如下：

- 先冻结最小文档元数据，而不是复杂文档治理模型
- 先冻结访问范围标记，而不是权限系统
- 先服务当前知识问答主链路，再为第二阶段扩展预留接口位

一句话总结：

**第一阶段文档库先按“业务域 + 文档类型 + 来源类型 + 生命周期状态 + 访问范围标记”冻结，不做重型权限与治理系统。**
