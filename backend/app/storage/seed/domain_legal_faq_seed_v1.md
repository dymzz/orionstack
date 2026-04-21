# 第一阶段可直接入库 FAQ 内容：Legal 业务域 v1

## 1. 文档目标

本文档提供一份已按第一阶段边界清洗的 Legal 业务域 FAQ 种子内容，供知识库直接入库使用。

本内容遵循当前第一阶段边界：

- 以 FAQ / 业务知识问答主链路为核心
- 适用于企业内部高频法务与合规问答
- 当前阶段只做轻量元数据与访问范围标记
- 作为 FAQ 种子内容导入，而不是完整法务制度文档全集

---

## 2. 使用范围

本 FAQ 内容适用于以下场景：

- 企业内部知识助手的法务与合规问答
- 作为 A 类输入直接按 `manual_faq` 导入
- 提供可检索、可引用、可回源的基础问答内容
- 支撑合同流程、印章申请、合规咨询等高频法务问题

本 FAQ 内容不用于：

- 替代正式法务制度原文
- 替代外部律师意见
- 输出具体案件材料或诉讼策略
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

- `business_domain = legal`
- `document_type = faq`
- `source_type = manual_faq`
- `lifecycle_status = active`
- `access_scope = internal`
- `source_label = Legal FAQ`
- `source_locator = legal_faq_seed_v1#<faq-id>`

如进入文档登记层，可按第一阶段文档库最小字段表补齐 `document_id / created_at / updated_at` 等字段。

本文件属于文档接入边界中的 A 类输入，可不经过独立 cleaning adapter，直接进入 FAQ 入库链路。

---

## 4. 可入库 FAQ 内容（结构化）

下面内容可作为 FAQ 种子数据直接整理入库。

```json
[
  {
    "id": "legal-faq-001",
    "title": "合同送审在哪里提交？",
    "question": "合同送审在哪里提交？",
    "answer": "合同送审可通过公司法务平台或合同管理入口提交，填写合同基本信息并上传合同文本后，系统会自动流转至法务审批。",
    "keywords": ["合同", "送审", "提交", "法务", "审批"],
    "business_domain": "legal",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Legal FAQ",
    "source_locator": "legal_faq_seed_v1#legal-faq-001",
    "snippet": "合同送审可通过公司法务平台或合同管理入口提交，填写合同基本信息并上传合同文本后，系统会自动流转至法务审批。"
  },
  {
    "id": "legal-faq-002",
    "title": "用章申请怎么走？",
    "question": "用章申请怎么走？",
    "answer": "用章申请需在印章管理系统中提交，选择印章类型、用途和预计归还时间，经部门负责人和印章管理员审批后领取使用。",
    "keywords": ["用章", "印章", "申请", "审批", "领取"],
    "business_domain": "legal",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Legal FAQ",
    "source_locator": "legal_faq_seed_v1#legal-faq-002",
    "snippet": "用章申请需在印章管理系统中提交，经部门负责人和印章管理员审批后领取使用。"
  },
  {
    "id": "legal-faq-003",
    "title": "NDA 模板在哪里获取？",
    "question": "NDA 模板在哪里获取？",
    "answer": "NDA 模板可在公司法务平台的标准模板库中下载。如需针对特定场景调整条款，建议先联系法务团队确认后再签署。",
    "keywords": ["NDA", "模板", "保密协议", "法务", "下载"],
    "business_domain": "legal",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Legal FAQ",
    "source_locator": "legal_faq_seed_v1#legal-faq-003",
    "snippet": "NDA 模板可在公司法务平台的标准模板库中下载。"
  },
  {
    "id": "legal-faq-004",
    "title": "法务咨询应该找谁？",
    "question": "法务咨询应该找谁？",
    "answer": "法务咨询可通过公司法务咨询入口提交问题，或直接联系公司法务团队的公共咨询渠道。紧急事项建议先通过直属上级协调。",
    "keywords": ["法务", "咨询", "联系", "渠道", "法务团队"],
    "business_domain": "legal",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Legal FAQ",
    "source_locator": "legal_faq_seed_v1#legal-faq-004",
    "snippet": "法务咨询可通过公司法务咨询入口提交问题，或直接联系公司法务团队的公共咨询渠道。"
  },
  {
    "id": "legal-faq-005",
    "title": "哪些合同必须走法务审批？",
    "question": "哪些合同必须走法务审批？",
    "answer": "涉及对外付款、知识产权授权、数据共享、保密义务和担保条款的合同通常必须走法务审批。具体范围以公司合同管理制度为准。",
    "keywords": ["合同", "审批", "法务", "知识产权", "保密"],
    "business_domain": "legal",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Legal FAQ",
    "source_locator": "legal_faq_seed_v1#legal-faq-005",
    "snippet": "涉及对外付款、知识产权授权、数据共享、保密义务和担保条款的合同通常必须走法务审批。"
  },
  {
    "id": "legal-faq-006",
    "title": "合同审批一般需要多久？",
    "question": "合同审批一般需要多久？",
    "answer": "合同审批周期取决于合同类型与复杂程度。标准模板合同通常较快，定制条款或高风险合同可能需要多轮审核。具体时间可在合同管理系统中查看当前状态。",
    "keywords": ["合同", "审批", "周期", "时间", "审核"],
    "business_domain": "legal",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Legal FAQ",
    "source_locator": "legal_faq_seed_v1#legal-faq-006",
    "snippet": "合同审批周期取决于合同类型与复杂程度，具体时间可在合同管理系统中查看当前状态。"
  },
  {
    "id": "legal-faq-007",
    "title": "合规问题应该怎么上报？",
    "question": "合规问题应该怎么上报？",
    "answer": "发现合规问题后，应通过合规上报入口提交说明，或联系法务团队的合规专员。涉及紧急风险的事项应同时通知直属上级。",
    "keywords": ["合规", "上报", "风险", "法务", "通知"],
    "business_domain": "legal",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Legal FAQ",
    "source_locator": "legal_faq_seed_v1#legal-faq-007",
    "snippet": "发现合规问题后，应通过合规上报入口提交说明，或联系法务团队的合规专员。"
  },
  {
    "id": "legal-faq-008",
    "title": "印章丢了怎么办？",
    "question": "印章丢了怎么办？",
    "answer": "发现印章遗失后，应立即向印章管理员和法务团队报告，并按印章管理制度启动遗失处理流程，包括登记备案和补刻申请。",
    "keywords": ["印章", "遗失", "报告", "补刻", "备案"],
    "business_domain": "legal",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Legal FAQ",
    "source_locator": "legal_faq_seed_v1#legal-faq-008",
    "snippet": "发现印章遗失后，应立即向印章管理员和法务团队报告，并按印章管理制度启动遗失处理流程。"
  },
  {
    "id": "legal-faq-009",
    "title": "保密协议到期了需要续签吗？",
    "question": "保密协议到期了需要续签吗？",
    "answer": "保密协议到期后是否需要续签，取决于协议类型和业务需要。建议联系法务团队确认当前协议状态和续签要求。",
    "keywords": ["保密协议", "到期", "续签", "NDA", "法务"],
    "business_domain": "legal",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Legal FAQ",
    "source_locator": "legal_faq_seed_v1#legal-faq-009",
    "snippet": "保密协议到期后是否需要续签，取决于协议类型和业务需要。"
  },
  {
    "id": "legal-faq-010",
    "title": "外部律师怎么申请？",
    "question": "外部律师怎么申请？",
    "answer": "需要聘请外部律师时，应通过法务平台提交外部律师申请，说明案件背景和需求，经法务负责人审批后方可启动委托流程。",
    "keywords": ["外部律师", "申请", "委托", "审批", "法务"],
    "business_domain": "legal",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "restricted",
    "source_label": "Legal FAQ",
    "source_locator": "legal_faq_seed_v1#legal-faq-010",
    "snippet": "需要聘请外部律师时，应通过法务平台提交外部律师申请，经法务负责人审批后方可启动委托流程。"
  },
  {
    "id": "legal-faq-011",
    "title": "知识产权归属问题怎么确认？",
    "question": "知识产权归属问题怎么确认？",
    "answer": "知识产权归属问题建议先查阅公司知识产权管理制度中的相关条款。如仍有疑问，可通过法务咨询入口提交具体场景说明，由法务团队确认。",
    "keywords": ["知识产权", "归属", "制度", "法务", "确认"],
    "business_domain": "legal",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Legal FAQ",
    "source_locator": "legal_faq_seed_v1#legal-faq-011",
    "snippet": "知识产权归属问题建议先查阅公司知识产权管理制度中的相关条款，如仍有疑问可联系法务团队确认。"
  },
  {
    "id": "legal-faq-012",
    "title": "数据使用合规要求有哪些？",
    "question": "数据使用合规要求有哪些？",
    "answer": "数据使用应遵守公司数据与信息使用规范，包括数据分类分级、访问权限控制和合规使用范围。具体要求请参见公司数据合规制度或联系法务团队。",
    "keywords": ["数据", "合规", "使用", "规范", "分类"],
    "business_domain": "legal",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Legal FAQ",
    "source_locator": "legal_faq_seed_v1#legal-faq-012",
    "snippet": "数据使用应遵守公司数据与信息使用规范，包括数据分类分级、访问权限控制和合规使用范围。"
  }
]
```

---

## 5. 入库说明

建议将上述 FAQ 内容按以下方式导入：

1. 每条 FAQ 作为一条独立知识条目或知识单元
2. 至少保留 `id / question / answer / keywords / source_locator / snippet`
3. 统一标记：
   - `business_domain = legal`
   - `document_type = faq`
   - `source_type = manual_faq`
   - `lifecycle_status = active`
   - `access_scope = internal`
4. 如进入文档库登记层，再补齐 `document_id / title / created_at / updated_at`

---

## 6. 当前阶段说明

这份 FAQ 内容的目标是：

- 支撑第一阶段企业内部法务与合规高频问答
- 让系统先具备稳定、可控、可检索的 Legal FAQ 基础内容
- 为后续接入 `policy / process / guide / notice` 保留一致的元数据习惯

当前阶段不追求：

- 覆盖所有法务制度细节
- 处理具体案件或诉讼策略
- 输出高敏感法律材料
- 代替正式制度原文、法务审批系统或权限系统

一句话总结：

**本文件是一份按第一阶段 Legal 业务域标准清洗后的 FAQ 种子内容，可作为 A 类输入直接进入企业内部知识问答系统的 FAQ 入库链路。**
