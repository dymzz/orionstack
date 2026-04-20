# 第一阶段可直接入库 FAQ 内容：行政业务域 v1

## 1. 文档目标

本文档提供一份已按第一阶段边界清洗的行政业务域 FAQ 种子内容，供知识库直接入库使用。

本内容遵循当前第一阶段边界：

- 以 FAQ / 业务知识问答主链路为核心
- 适用于企业内部高频行政问答
- 当前阶段只做轻量元数据与访问范围标记
- 作为 FAQ 种子内容导入，而不是完整行政制度文档全集

---

## 2. 使用范围

本 FAQ 内容适用于以下场景：

- 企业内部知识助手的行政问答
- 作为 A 类输入直接按 `manual_faq` 导入
- 提供可检索、可引用、可回源的基础问答内容
- 支撑会议室、门禁、访客、办公用品、工位、工牌、快递、停车等高频行政问题

本 FAQ 内容不用于：

- 替代正式行政制度原文
- 替代完整园区管理规范或物业通知全集
- 输出高敏感个体身份信息或安保信息
- 承担复杂权限控制逻辑或跨系统编排

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

- `business_domain = admin`
- `document_type = faq`
- `source_type = manual_faq`
- `lifecycle_status = active`
- `access_scope = internal`
- `source_label = Admin FAQ`
- `source_locator = admin_faq_seed_v1#<faq-id>`

如进入文档登记层，可按第一阶段文档库最小字段表补齐 `document_id / created_at / updated_at` 等字段。

本文件属于文档接入边界中的 A 类输入，可不经过独立 cleaning adapter，直接进入 FAQ 入库链路。

---

## 4. 可入库 FAQ 内容（结构化）

下面内容可作为 FAQ 种子数据直接整理入库。

```json
[
  {
    "id": "admin-faq-001",
    "title": "会议室怎么预订？",
    "question": "会议室怎么预订？",
    "answer": "会议室通常可通过会议室预订系统或企业办公入口进行预订。请选择会议时间、会议室和参会信息后提交，预订结果以系统显示为准。",
    "keywords": ["会议室", "预订", "办公入口", "会议时间", "系统"],
    "business_domain": "admin",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Admin FAQ",
    "source_locator": "admin_faq_seed_v1#admin-faq-001",
    "snippet": "会议室通常可通过会议室预订系统或企业办公入口进行预订。"
  },
  {
    "id": "admin-faq-002",
    "title": "访客来访需要怎么登记？",
    "question": "访客来访需要怎么登记？",
    "answer": "访客来访通常需要在访客登记入口提交来访人信息、到访时间和被访人信息。登记成功后，按现场要求完成身份核验或前台确认。",
    "keywords": ["访客", "来访", "登记", "前台", "身份核验"],
    "business_domain": "admin",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Admin FAQ",
    "source_locator": "admin_faq_seed_v1#admin-faq-002",
    "snippet": "访客来访通常需要在访客登记入口提交来访人信息。"
  },
  {
    "id": "admin-faq-003",
    "title": "门禁权限怎么申请？",
    "question": "门禁权限怎么申请？",
    "answer": "如需开通门禁权限，可通过行政或园区服务入口提交申请，并填写通行区域、申请原因和使用期限。开通结果以审批和系统配置完成情况为准。",
    "keywords": ["门禁", "权限", "申请", "园区服务", "审批"],
    "business_domain": "admin",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Admin FAQ",
    "source_locator": "admin_faq_seed_v1#admin-faq-003",
    "snippet": "如需开通门禁权限，可通过行政或园区服务入口提交申请。"
  },
  {
    "id": "admin-faq-004",
    "title": "办公用品怎么申领？",
    "question": "办公用品怎么申领？",
    "answer": "办公用品通常可通过行政服务入口或固定申领流程提交申请。请按要求选择用品类型、数量和用途，审批或发放结果以系统通知为准。",
    "keywords": ["办公用品", "申领", "行政服务", "数量", "通知"],
    "business_domain": "admin",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Admin FAQ",
    "source_locator": "admin_faq_seed_v1#admin-faq-004",
    "snippet": "办公用品通常可通过行政服务入口或固定申领流程提交申请。"
  },
  {
    "id": "admin-faq-005",
    "title": "工位怎么申请或调整？",
    "question": "工位怎么申请或调整？",
    "answer": "如需申请新工位或调整工位，可通过行政服务入口提交申请，并说明所在部门、人员信息和调整原因。最终安排以行政确认结果为准。",
    "keywords": ["工位", "申请", "调整", "部门", "行政确认"],
    "business_domain": "admin",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Admin FAQ",
    "source_locator": "admin_faq_seed_v1#admin-faq-005",
    "snippet": "如需申请新工位或调整工位，可通过行政服务入口提交申请。"
  },
  {
    "id": "admin-faq-006",
    "title": "工牌丢了怎么补办？",
    "question": "工牌丢了怎么补办？",
    "answer": "工牌遗失后，应按流程尽快提交补办申请，并根据要求完成身份确认或费用处理。补办完成时间和领取方式以行政通知为准。",
    "keywords": ["工牌", "丢失", "补办", "身份确认", "行政通知"],
    "business_domain": "admin",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Admin FAQ",
    "source_locator": "admin_faq_seed_v1#admin-faq-006",
    "snippet": "工牌遗失后，应按流程尽快提交补办申请。"
  },
  {
    "id": "admin-faq-007",
    "title": "快递收发在哪里处理？",
    "question": "快递收发在哪里处理？",
    "answer": "公司快递的收发通常按前台、收发室或园区指定流程处理。具体收件地点、寄件要求和领取方式以公司行政通知为准。",
    "keywords": ["快递", "收发", "前台", "收发室", "领取"],
    "business_domain": "admin",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Admin FAQ",
    "source_locator": "admin_faq_seed_v1#admin-faq-007",
    "snippet": "公司快递的收发通常按前台、收发室或园区指定流程处理。"
  },
  {
    "id": "admin-faq-008",
    "title": "停车位怎么申请？",
    "question": "停车位怎么申请？",
    "answer": "如需申请停车位，可通过行政或园区服务入口提交停车申请，并填写车牌、使用期限和申请原因。审核结果以系统或行政通知为准。",
    "keywords": ["停车位", "申请", "车牌", "园区服务", "审核"],
    "business_domain": "admin",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Admin FAQ",
    "source_locator": "admin_faq_seed_v1#admin-faq-008",
    "snippet": "如需申请停车位，可通过行政或园区服务入口提交停车申请。"
  },
  {
    "id": "admin-faq-009",
    "title": "办公区设备报修怎么提？",
    "question": "办公区设备报修怎么提？",
    "answer": "办公区设备如空调、照明、门锁或公共设施出现问题时，可通过行政报修入口提交工单，并填写位置、故障现象和联系方式。处理进度以工单状态为准。",
    "keywords": ["报修", "设备", "空调", "工单", "进度"],
    "business_domain": "admin",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Admin FAQ",
    "source_locator": "admin_faq_seed_v1#admin-faq-009",
    "snippet": "办公区设备出现问题时，可通过行政报修入口提交工单。"
  },
  {
    "id": "admin-faq-010",
    "title": "名片怎么申请？",
    "question": "名片怎么申请？",
    "answer": "如需申请名片，可通过行政服务入口提交申请，并按模板填写姓名、职位、联系方式等信息。制作和领取时间以行政安排为准。",
    "keywords": ["名片", "申请", "模板", "职位", "行政服务"],
    "business_domain": "admin",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Admin FAQ",
    "source_locator": "admin_faq_seed_v1#admin-faq-010",
    "snippet": "如需申请名片，可通过行政服务入口提交申请。"
  },
  {
    "id": "admin-faq-011",
    "title": "前台电话或服务入口在哪里看？",
    "question": "前台电话或服务入口在哪里看？",
    "answer": "前台电话、行政服务入口或办公支持方式通常可在企业通讯录、员工门户或行政服务页面查看。若页面信息缺失，可联系直属行政同事确认。",
    "keywords": ["前台", "电话", "服务入口", "通讯录", "员工门户"],
    "business_domain": "admin",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Admin FAQ",
    "source_locator": "admin_faq_seed_v1#admin-faq-011",
    "snippet": "前台电话或行政服务入口通常可在企业通讯录或员工门户查看。"
  },
  {
    "id": "admin-faq-012",
    "title": "办公室搬迁或座位变更通知在哪里看？",
    "question": "办公室搬迁或座位变更通知在哪里看？",
    "answer": "办公室搬迁、座位调整或办公区变更通知通常通过企业公告、邮件通知或行政服务页面发布。具体执行时间与安排以最新正式通知为准。",
    "keywords": ["办公室搬迁", "座位变更", "通知", "企业公告", "邮件"],
    "business_domain": "admin",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Admin FAQ",
    "source_locator": "admin_faq_seed_v1#admin-faq-012",
    "snippet": "办公室搬迁或座位变更通知通常通过企业公告或邮件通知发布。"
  }
]
```

---

## 5. 入库说明

建议将上述 FAQ 内容按以下方式导入：

1. 每条 FAQ 作为一条独立知识条目或知识单元
2. 至少保留 `id / question / answer / keywords / source_locator / snippet`
3. 统一标记：
   - `business_domain = admin`
   - `document_type = faq`
   - `source_type = manual_faq`
   - `lifecycle_status = active`
   - `access_scope = internal`
4. 如进入文档库登记层，再补齐 `document_id / title / created_at / updated_at`

---

## 6. 当前阶段说明

这份 FAQ 内容的目标是：

- 支撑第一阶段企业内部高频行政问答
- 让系统先具备稳定、可控、可检索的行政 FAQ 基础内容
- 为后续接入 `policy / process / guide / notice` 保留一致的元数据习惯

当前阶段不追求：

- 覆盖所有园区或行政制度细节
- 覆盖不同办公地点的全部差异规则
- 处理高敏感安保或个体身份信息
- 代替正式制度原文、门禁系统或物业流程系统

一句话总结：

**本文件是一份按第一阶段行政业务域标准清洗后的 FAQ 种子内容，可作为 A 类输入直接进入企业内部知识问答系统的 FAQ 入库链路。**
