# 第一阶段可直接入库 FAQ 内容：Finance 业务域 v1

## 1. 文档目标

本文档提供一份已按第一阶段边界清洗的 Finance 业务域 FAQ 种子内容，供知识库直接入库使用。

本内容遵循当前第一阶段边界：

- 以 FAQ / 业务知识问答主链路为核心
- 适用于企业内部高频 Finance 问答
- 当前阶段只做轻量元数据与访问范围标记
- 作为 FAQ 种子内容导入，而不是完整财务制度文档全集

---

## 2. 使用范围

本 FAQ 内容适用于以下场景：

- 企业内部知识助手的 Finance 问答
- 作为 A 类输入直接按 `manual_faq` 导入
- 提供可检索、可引用、可回源的基础问答内容
- 支撑报销、付款、借款、预算、发票、工资条等高频财务问题

本 FAQ 内容不用于：

- 替代正式财务制度原文
- 替代完整报销系统或付款审批系统
- 输出高敏感个人财务数据
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

- `business_domain = finance`
- `document_type = faq`
- `source_type = manual_faq`
- `lifecycle_status = active`
- `access_scope = internal`
- `source_label = Finance FAQ`
- `source_locator = finance_faq_seed_v1#<faq-id>`

如进入文档登记层，可按第一阶段文档库最小字段表补齐 `document_id / created_at / updated_at` 等字段。

本文件属于文档接入边界中的 A 类输入，可不经过独立 cleaning adapter，直接进入 FAQ 入库链路。

---

## 4. 可入库 FAQ 内容（结构化）

下面内容可作为 FAQ 种子数据直接整理入库。

```json
[
  {
    "id": "finance-faq-001",
    "title": "如何提交日常报销？",
    "question": "如何提交日常报销？",
    "answer": "进入报销系统后选择对应报销类型，填写费用信息并上传合规票据后提交审批。审批通过后，报销将按公司流程进入付款环节。",
    "keywords": ["报销", "费用", "票据", "审批", "付款"],
    "business_domain": "finance",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Finance FAQ",
    "source_locator": "finance_faq_seed_v1#finance-faq-001",
    "snippet": "进入报销系统后选择对应报销类型，填写费用信息并上传合规票据后提交审批。"
  },
  {
    "id": "finance-faq-002",
    "title": "报销需要上传什么票据？",
    "question": "报销需要上传什么票据？",
    "answer": "报销通常需要上传与费用类型匹配的合规发票或票据。若为差旅类费用，还应按公司要求补充行程单、住宿单或其他附件。",
    "keywords": ["报销", "票据", "发票", "差旅", "附件"],
    "business_domain": "finance",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Finance FAQ",
    "source_locator": "finance_faq_seed_v1#finance-faq-002",
    "snippet": "报销通常需要上传与费用类型匹配的合规发票或票据。"
  },
  {
    "id": "finance-faq-003",
    "title": "差旅报销怎么提交？",
    "question": "差旅报销怎么提交？",
    "answer": "差旅结束后，应在报销系统中选择差旅报销类型，填写出差时间、地点和费用明细，并按要求上传交通、住宿等相关票据。",
    "keywords": ["差旅", "报销", "出差", "住宿", "交通"],
    "business_domain": "finance",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Finance FAQ",
    "source_locator": "finance_faq_seed_v1#finance-faq-003",
    "snippet": "应在报销系统中选择差旅报销类型，填写出差时间、地点和费用明细。"
  },
  {
    "id": "finance-faq-004",
    "title": "付款申请提交后在哪里查看进度？",
    "question": "付款申请提交后在哪里查看进度？",
    "answer": "付款申请提交后，可在付款申请记录或审批记录页面查看当前状态。若长时间未处理，可按流程联系对应审批人或财务。",
    "keywords": ["付款", "申请", "进度", "审批", "财务"],
    "business_domain": "finance",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Finance FAQ",
    "source_locator": "finance_faq_seed_v1#finance-faq-004",
    "snippet": "可在付款申请记录或审批记录页面查看当前状态。"
  },
  {
    "id": "finance-faq-005",
    "title": "借款申请怎么走？",
    "question": "借款申请怎么走？",
    "answer": "如需业务借款，应按公司流程在借款或付款系统中发起申请，填写用途、金额和预计归还或核销方式，并提交审批。",
    "keywords": ["借款", "申请", "用途", "金额", "审批"],
    "business_domain": "finance",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Finance FAQ",
    "source_locator": "finance_faq_seed_v1#finance-faq-005",
    "snippet": "应按公司流程在借款或付款系统中发起申请，填写用途、金额并提交审批。"
  },
  {
    "id": "finance-faq-006",
    "title": "发票抬头和税号在哪里查看？",
    "question": "发票抬头和税号在哪里查看？",
    "answer": "发票抬头和税号通常可在财务制度说明、报销指引页面或财务服务入口查看。开票前建议以公司最新对外开票信息为准。",
    "keywords": ["发票", "抬头", "税号", "财务制度", "开票"],
    "business_domain": "finance",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Finance FAQ",
    "source_locator": "finance_faq_seed_v1#finance-faq-006",
    "snippet": "发票抬头和税号通常可在财务制度说明、报销指引页面或财务服务入口查看。"
  },
  {
    "id": "finance-faq-007",
    "title": "报销被退回后怎么处理？",
    "question": "报销被退回后怎么处理？",
    "answer": "报销被退回后，应先查看退回原因，并按要求补充或修改费用信息、票据或附件后重新提交。若原因不明确，可联系财务或审批人确认。",
    "keywords": ["报销", "退回", "修改", "票据", "附件"],
    "business_domain": "finance",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Finance FAQ",
    "source_locator": "finance_faq_seed_v1#finance-faq-007",
    "snippet": "应先查看退回原因，并按要求补充或修改信息后重新提交。"
  },
  {
    "id": "finance-faq-008",
    "title": "预算不足时怎么申请付款或报销？",
    "question": "预算不足时怎么申请付款或报销？",
    "answer": "如遇预算不足，应先按公司流程申请预算调整或补充审批，再继续提交付款或报销申请。具体以预算管理规则和审批要求为准。",
    "keywords": ["预算", "不足", "付款", "报销", "审批"],
    "business_domain": "finance",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Finance FAQ",
    "source_locator": "finance_faq_seed_v1#finance-faq-008",
    "snippet": "应先按公司流程申请预算调整或补充审批，再继续提交付款或报销申请。"
  },
  {
    "id": "finance-faq-009",
    "title": "工资条在哪里查看？",
    "question": "工资条在哪里查看？",
    "answer": "工资条通常可在员工自助平台、薪酬系统或公司指定入口查看。如未显示，请先确认账号权限或联系财务或 HR。",
    "keywords": ["工资条", "员工自助", "薪酬系统", "查看", "权限"],
    "business_domain": "finance",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Finance FAQ",
    "source_locator": "finance_faq_seed_v1#finance-faq-009",
    "snippet": "工资条通常可在员工自助平台、薪酬系统或公司指定入口查看。"
  },
  {
    "id": "finance-faq-010",
    "title": "个税信息在哪里查看？",
    "question": "个税信息在哪里查看？",
    "answer": "个税相关信息通常可在薪酬系统、员工服务入口或个税申报相关说明中查看。具体展示范围以公司系统与当地申报规则为准。",
    "keywords": ["个税", "薪酬系统", "员工服务", "申报", "查看"],
    "business_domain": "finance",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Finance FAQ",
    "source_locator": "finance_faq_seed_v1#finance-faq-010",
    "snippet": "个税相关信息通常可在薪酬系统、员工服务入口或个税申报相关说明中查看。"
  },
  {
    "id": "finance-faq-011",
    "title": "对公付款需要准备哪些材料？",
    "question": "对公付款需要准备哪些材料？",
    "answer": "对公付款通常需要准备合同、发票、收款账户信息及公司流程要求的审批材料。具体材料范围以付款类型和制度要求为准。",
    "keywords": ["对公付款", "合同", "发票", "收款账户", "审批材料"],
    "business_domain": "finance",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Finance FAQ",
    "source_locator": "finance_faq_seed_v1#finance-faq-011",
    "snippet": "对公付款通常需要准备合同、发票、收款账户信息及审批材料。"
  },
  {
    "id": "finance-faq-012",
    "title": "备用金怎么申请或核销？",
    "question": "备用金怎么申请或核销？",
    "answer": "如需申请备用金，应按流程在财务系统中提交申请；使用后应在规定时间内按要求提交票据并完成核销。具体规则以公司财务制度为准。",
    "keywords": ["备用金", "申请", "核销", "票据", "财务制度"],
    "business_domain": "finance",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Finance FAQ",
    "source_locator": "finance_faq_seed_v1#finance-faq-012",
    "snippet": "应按流程在财务系统中提交申请；使用后按要求提交票据并完成核销。"
  }
]
```

---

## 5. 入库说明

建议将上述 FAQ 内容按以下方式导入：

1. 每条 FAQ 作为一条独立知识条目或知识单元
2. 至少保留 `id / question / answer / keywords / source_locator / snippet`
3. 统一标记：
   - `business_domain = finance`
   - `document_type = faq`
   - `source_type = manual_faq`
   - `lifecycle_status = active`
   - `access_scope = internal`
4. 如进入文档库登记层，再补齐 `document_id / title / created_at / updated_at`

---

## 6. 当前阶段说明

这份 FAQ 内容的目标是：

- 支撑第一阶段企业内部 Finance 高频问答
- 让系统先具备稳定、可控、可检索的 Finance FAQ 基础内容
- 为后续接入 `policy / process / guide / notice` 保留一致的元数据习惯

当前阶段不追求：

- 覆盖所有财务制度细节
- 覆盖所有税务、票据和地区差异
- 处理高敏感个体薪酬或财务信息
- 代替正式制度原文、报销系统或付款审批系统

一句话总结：

**本文件是一份按第一阶段 Finance 业务域标准清洗后的 FAQ 种子内容，可作为 A 类输入直接进入企业内部知识问答系统的 FAQ 入库链路。**
