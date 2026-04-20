# 第一阶段可直接入库 FAQ 内容：Ops 业务域 v1

## 1. 文档目标

本文档提供一份已按第一阶段边界清洗的 Ops 业务域 FAQ 种子内容，供知识库直接入库使用。

本内容遵循当前第一阶段边界：

- 以 FAQ / 业务知识问答主链路为核心
- 适用于企业内部高频 Ops 问答
- 当前阶段只做轻量元数据与访问范围标记
- 作为 FAQ 种子内容导入，而不是完整运维制度文档全集

---

## 2. 使用范围

本 FAQ 内容适用于以下场景：

- 企业内部知识助手的 Ops 问答
- 作为 A 类输入直接按 `manual_faq` 导入
- 提供可检索、可引用、可回源的基础问答内容
- 支撑告警、发布、变更、值班、环境、工单、恢复等高频 Ops 问题

本 FAQ 内容不用于：

- 替代正式运维规范或变更制度原文
- 替代监控平台、工单系统或发布系统本身
- 输出敏感生产细节、密钥或高风险操作指令
- 承担复杂权限控制逻辑或跨系统自动编排

---

## 3. 清洗与入库假设

本 FAQ 内容已经按第一阶段最小可入库要求做了以下处理：

1. 问句统一为员工自然问法
2. 回答统一为稳定、简洁、可引用表达
3. 去除冗余口语、重复表述和不必要背景说明
4. 每条 FAQ 均保留可回源的最小问答元数据
5. 默认按 `active` 状态导入
6. 当前阶段只做 `access_scope` 标记，不做实际权限判断

建议默认元数据：

- `business_domain = ops`
- `document_type = faq`
- `source_type = manual_faq`
- `lifecycle_status = active`
- `access_scope = internal`
- `source_label = Ops FAQ`
- `source_locator = ops_faq_seed_v1#<faq-id>`

如进入文档登记层，可按第一阶段文档库最小字段表补齐 `document_id / created_at / updated_at` 等字段。

本文件属于文档接入边界中的 A 类输入，可不经过独立 cleaning adapter，直接进入 FAQ 入库链路。

---

## 4. 可入库 FAQ 内容（结构化）

下面内容可作为 FAQ 种子数据直接整理入库。

```json
[
  {
    "id": "ops-faq-001",
    "title": "服务告警在哪里查看？",
    "question": "服务告警在哪里查看？",
    "answer": "服务告警通常可在公司监控平台或告警中心查看。建议先查看当前告警级别、触发时间、影响服务与处理状态，再决定是否升级处理。",
    "keywords": ["告警", "监控平台", "告警中心", "处理状态", "服务"],
    "business_domain": "ops",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Ops FAQ",
    "source_locator": "ops_faq_seed_v1#ops-faq-001",
    "snippet": "服务告警通常可在公司监控平台或告警中心查看。"
  },
  {
    "id": "ops-faq-002",
    "title": "值班安排在哪里确认？",
    "question": "值班安排在哪里确认？",
    "answer": "值班安排通常可在值班表、团队日历或 Ops 值班系统中确认。若发现排班冲突或交接异常，应按流程联系值班负责人调整。",
    "keywords": ["值班", "排班", "团队日历", "值班系统", "交接"],
    "business_domain": "ops",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Ops FAQ",
    "source_locator": "ops_faq_seed_v1#ops-faq-002",
    "snippet": "值班安排通常可在值班表、团队日历或 Ops 值班系统中确认。"
  },
  {
    "id": "ops-faq-003",
    "title": "生产变更需要怎么申请？",
    "question": "生产变更需要怎么申请？",
    "answer": "生产变更通常需要先提交变更申请，填写变更内容、影响范围、执行窗口、回滚方案与负责人，并按流程完成审批后再执行。",
    "keywords": ["生产变更", "变更申请", "执行窗口", "回滚方案", "审批"],
    "business_domain": "ops",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Ops FAQ",
    "source_locator": "ops_faq_seed_v1#ops-faq-003",
    "snippet": "生产变更通常需要先提交变更申请，并按流程完成审批后再执行。"
  },
  {
    "id": "ops-faq-004",
    "title": "发布窗口在哪里查看？",
    "question": "发布窗口在哪里查看？",
    "answer": "发布窗口通常可在发布日历、变更平台或团队公告中查看。执行发布前应确认当前窗口是否允许变更，并核对是否存在冻结期。",
    "keywords": ["发布窗口", "发布日历", "变更平台", "冻结期", "公告"],
    "business_domain": "ops",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Ops FAQ",
    "source_locator": "ops_faq_seed_v1#ops-faq-004",
    "snippet": "发布窗口通常可在发布日历、变更平台或团队公告中查看。"
  },
  {
    "id": "ops-faq-005",
    "title": "环境异常应该先看什么？",
    "question": "环境异常应该先看什么？",
    "answer": "发现环境异常时，通常应先查看监控告警、最近变更、服务状态页与关键日志，确认影响范围后再按标准排查流程处理。",
    "keywords": ["环境异常", "监控告警", "最近变更", "服务状态", "日志"],
    "business_domain": "ops",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Ops FAQ",
    "source_locator": "ops_faq_seed_v1#ops-faq-005",
    "snippet": "发现环境异常时，通常应先查看监控告警、最近变更、服务状态页与关键日志。"
  },
  {
    "id": "ops-faq-006",
    "title": "工单处理进度在哪里看？",
    "question": "工单处理进度在哪里看？",
    "answer": "工单处理进度通常可在工单系统中查看当前状态、处理人、更新时间与处理记录。若长时间未推进，可按流程催办或升级。",
    "keywords": ["工单", "处理进度", "处理记录", "催办", "升级"],
    "business_domain": "ops",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Ops FAQ",
    "source_locator": "ops_faq_seed_v1#ops-faq-006",
    "snippet": "工单处理进度通常可在工单系统中查看当前状态、处理人、更新时间与处理记录。"
  },
  {
    "id": "ops-faq-007",
    "title": "日志应该去哪里查看？",
    "question": "日志应该去哪里查看？",
    "answer": "日志通常可在统一日志平台、应用控制台或指定检索入口查看。排查时建议优先按时间范围、服务名与错误关键字过滤。",
    "keywords": ["日志", "日志平台", "应用控制台", "检索", "错误关键字"],
    "business_domain": "ops",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Ops FAQ",
    "source_locator": "ops_faq_seed_v1#ops-faq-007",
    "snippet": "日志通常可在统一日志平台、应用控制台或指定检索入口查看。"
  },
  {
    "id": "ops-faq-008",
    "title": "服务状态页在哪里查看？",
    "question": "服务状态页在哪里查看？",
    "answer": "服务状态页通常可在运维门户、监控平台或团队常用入口查看，用于确认服务当前是否可用以及是否存在已知故障。",
    "keywords": ["服务状态页", "运维门户", "监控平台", "故障", "可用性"],
    "business_domain": "ops",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Ops FAQ",
    "source_locator": "ops_faq_seed_v1#ops-faq-008",
    "snippet": "服务状态页通常可在运维门户、监控平台或团队常用入口查看。"
  },
  {
    "id": "ops-faq-009",
    "title": "回滚方案一般在哪里填写？",
    "question": "回滚方案一般在哪里填写？",
    "answer": "回滚方案通常需要在变更申请单、发布单或执行文档中提前填写，并在执行前确认回滚条件、责任人与恢复步骤。",
    "keywords": ["回滚方案", "变更申请单", "发布单", "恢复步骤", "执行文档"],
    "business_domain": "ops",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Ops FAQ",
    "source_locator": "ops_faq_seed_v1#ops-faq-009",
    "snippet": "回滚方案通常需要在变更申请单、发布单或执行文档中提前填写。"
  },
  {
    "id": "ops-faq-010",
    "title": "资源申请需要提交什么信息？",
    "question": "资源申请需要提交什么信息？",
    "answer": "资源申请通常需要说明申请用途、环境类型、资源规格、预计使用时长、负责人及成本归属，具体要求以资源申请流程为准。",
    "keywords": ["资源申请", "环境类型", "资源规格", "使用时长", "负责人"],
    "business_domain": "ops",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Ops FAQ",
    "source_locator": "ops_faq_seed_v1#ops-faq-010",
    "snippet": "资源申请通常需要说明申请用途、环境类型、资源规格、预计使用时长、负责人及成本归属。"
  },
  {
    "id": "ops-faq-011",
    "title": "备份恢复申请怎么提？",
    "question": "备份恢复申请怎么提？",
    "answer": "如需执行备份恢复，通常应提交恢复申请，说明目标环境、恢复时间点、影响范围与审批信息，并按流程由有权限的人员执行。",
    "keywords": ["备份恢复", "恢复申请", "目标环境", "恢复时间点", "审批"],
    "business_domain": "ops",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Ops FAQ",
    "source_locator": "ops_faq_seed_v1#ops-faq-011",
    "snippet": "如需执行备份恢复，通常应提交恢复申请，说明目标环境、恢复时间点、影响范围与审批信息。"
  },
  {
    "id": "ops-faq-012",
    "title": "事故复盘记录在哪里看？",
    "question": "事故复盘记录在哪里看？",
    "answer": "事故复盘记录通常可在团队知识库、复盘文档库或事故管理平台查看。若需要追踪后续整改项，应同时查看行动项状态。",
    "keywords": ["事故复盘", "知识库", "事故管理平台", "整改项", "行动项"],
    "business_domain": "ops",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Ops FAQ",
    "source_locator": "ops_faq_seed_v1#ops-faq-012",
    "snippet": "事故复盘记录通常可在团队知识库、复盘文档库或事故管理平台查看。"
  }
]
```

---

## 5. 入库说明

建议将上述 FAQ 内容按以下方式导入：

1. 每条 FAQ 作为一条独立知识条目或知识单元
2. 至少保留 `id / question / answer / keywords / source_locator / snippet`
3. 统一标记：
   - `business_domain = ops`
   - `document_type = faq`
   - `source_type = manual_faq`
   - `lifecycle_status = active`
   - `access_scope = internal`
4. 如进入文档库登记层，再补齐 `document_id / title / created_at / updated_at`

---

## 6. 当前阶段说明

这份 FAQ 内容的目标是：

- 支撑第一阶段企业内部 Ops 高频问答
- 让系统先具备稳定、可控、可检索的 Ops FAQ 基础内容
- 为后续接入 `runbook / incident / change / release / status_page` 保留一致的元数据习惯

当前阶段不追求：

- 覆盖所有生产运维细节
- 覆盖所有基础设施差异与环境差异
- 输出敏感生产配置、密钥或危险操作步骤
- 代替正式运维制度、监控系统或发布系统

一句话总结：

**本文件是一份按第一阶段 Ops 业务域标准清洗后的 FAQ 种子内容，可作为 A 类输入直接进入企业内部知识问答系统的 FAQ 入库链路。**
