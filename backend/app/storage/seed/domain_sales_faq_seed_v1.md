# 第一阶段可直接入库 FAQ 内容：Sales 业务域 v1

## 1. 文档目标

本文档提供一份已按第一阶段边界清洗的 Sales 业务域 FAQ 种子内容，供知识库直接入库使用。

本内容遵循当前第一阶段边界：

- 以 FAQ / 业务知识问答主链路为核心
- 适用于企业内部高频销售支持与协同问答
- 当前阶段只做轻量元数据与访问范围标记
- 作为 FAQ 种子内容导入，而不是完整销售管理文档全集

---

## 2. 使用范围

本 FAQ 内容适用于以下场景：

- 企业内部知识助手的销售支持问答
- 作为 A 类输入直接按 `manual_faq` 导入
- 提供可检索、可引用、可回源的基础问答内容
- 支撑报价流程、合同审批、演示资料获取等高频销售问题

本 FAQ 内容不用于：

- 替代完整销售管理制度
- 输出敏感客户名单或成交价格底线
- 替代 CRM 系统操作手册
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

- `business_domain = sales`
- `document_type = faq`
- `source_type = manual_faq`
- `lifecycle_status = active`
- `access_scope = internal`
- `source_label = Sales FAQ`
- `source_locator = sales_faq_seed_v1#<faq-id>`

如进入文档登记层，可按第一阶段文档库最小字段表补齐 `document_id / created_at / updated_at` 等字段。

本文件属于文档接入边界中的 A 类输入，可不经过独立 cleaning adapter，直接进入 FAQ 入库链路。

---

## 4. 可入库 FAQ 内容（结构化）

下面内容可作为 FAQ 种子数据直接整理入库。

```json
[
  {
    "id": "sales-faq-001",
    "title": "报价申请在哪里提交？",
    "question": "报价申请在哪里提交？",
    "answer": "报价申请可通过公司销售管理平台或 CRM 系统的报价模块提交，填写客户信息、产品明细和价格方案后提交审批。",
    "keywords": ["报价", "申请", "提交", "CRM", "审批"],
    "business_domain": "sales",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Sales FAQ",
    "source_locator": "sales_faq_seed_v1#sales-faq-001",
    "snippet": "报价申请可通过公司销售管理平台或 CRM 系统的报价模块提交，填写客户信息、产品明细和价格方案后提交审批。"
  },
  {
    "id": "sales-faq-002",
    "title": "销售合同应该怎么走审批？",
    "question": "销售合同应该怎么走审批？",
    "answer": "销售合同需在合同管理平台中发起审批流程，按合同金额和类型走对应审批层级。审批通过后由法务团队审核合同条款，确认无误后盖章生效。",
    "keywords": ["合同", "审批", "销售", "法务", "盖章"],
    "business_domain": "sales",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Sales FAQ",
    "source_locator": "sales_faq_seed_v1#sales-faq-002",
    "snippet": "销售合同需在合同管理平台中发起审批流程，按合同金额和类型走对应审批层级。"
  },
  {
    "id": "sales-faq-003",
    "title": "演示资料在哪里找？",
    "question": "演示资料在哪里找？",
    "answer": "演示资料可在销售资料中心或产品文档平台中查找和下载。如需定制化演示材料，建议联系产品团队或市场团队协助准备。",
    "keywords": ["演示", "资料", "销售", "下载", "产品"],
    "business_domain": "sales",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Sales FAQ",
    "source_locator": "sales_faq_seed_v1#sales-faq-003",
    "snippet": "演示资料可在销售资料中心或产品文档平台中查找和下载。"
  },
  {
    "id": "sales-faq-004",
    "title": "商机信息填到哪里？",
    "question": "商机信息填到哪里？",
    "answer": "商机信息应在 CRM 系统的商机模块中录入，填写客户名称、需求描述、预计金额和跟进计划。录入后商机会进入团队管理视图。",
    "keywords": ["商机", "CRM", "录入", "客户", "跟进"],
    "business_domain": "sales",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Sales FAQ",
    "source_locator": "sales_faq_seed_v1#sales-faq-004",
    "snippet": "商机信息应在 CRM 系统的商机模块中录入，填写客户名称、需求描述、预计金额和跟进计划。"
  },
  {
    "id": "sales-faq-005",
    "title": "客户问题该找谁支持？",
    "question": "客户问题该找谁支持？",
    "answer": "一般客户问题可先在内部支持联系人清单中查找对应负责人。如涉及技术、法务或财务等专项问题，建议通过内部协作流程转交对应团队。",
    "keywords": ["客户", "支持", "联系人", "协作", "转交"],
    "business_domain": "sales",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Sales FAQ",
    "source_locator": "sales_faq_seed_v1#sales-faq-005",
    "snippet": "一般客户问题可先在内部支持联系人清单中查找对应负责人。"
  },
  {
    "id": "sales-faq-006",
    "title": "CRM 使用说明在哪里？",
    "question": "CRM 使用说明在哪里？",
    "answer": "CRM 使用说明可在销售资料中心或内部知识库中查看，涵盖客户录入、商机管理、报价生成等常用操作指引。",
    "keywords": ["CRM", "使用说明", "销售", "知识库", "操作"],
    "business_domain": "sales",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Sales FAQ",
    "source_locator": "sales_faq_seed_v1#sales-faq-006",
    "snippet": "CRM 使用说明可在销售资料中心或内部知识库中查看。"
  },
  {
    "id": "sales-faq-007",
    "title": "报价审批流程是什么？",
    "question": "报价审批流程是什么？",
    "answer": "报价审批流程通常包括提交报价、直属上级审核、财务确认折扣和最终审批。审批层级和金额阈值以公司报价审批规范为准。",
    "keywords": ["报价", "审批", "流程", "折扣", "财务"],
    "business_domain": "sales",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Sales FAQ",
    "source_locator": "sales_faq_seed_v1#sales-faq-007",
    "snippet": "报价审批流程通常包括提交报价、直属上级审核、财务确认折扣和最终审批。"
  },
  {
    "id": "sales-faq-008",
    "title": "销售资料目录在哪里？",
    "question": "销售资料目录在哪里？",
    "answer": "销售资料目录通常维护在销售资料中心，按产品线、资料类型和版本进行分类。可通过搜索或目录导航快速定位所需资料。",
    "keywords": ["销售资料", "目录", "分类", "搜索", "下载"],
    "business_domain": "sales",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Sales FAQ",
    "source_locator": "sales_faq_seed_v1#sales-faq-008",
    "snippet": "销售资料目录通常维护在销售资料中心，按产品线、资料类型和版本进行分类。"
  },
  {
    "id": "sales-faq-009",
    "title": "客户拜访记录模板在哪里？",
    "question": "客户拜访记录模板在哪里？",
    "answer": "客户拜访记录模板可在销售资料中心的模板库中下载，也可在 CRM 系统中直接填写电子版拜访记录。",
    "keywords": ["拜访记录", "模板", "客户", "CRM", "下载"],
    "business_domain": "sales",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Sales FAQ",
    "source_locator": "sales_faq_seed_v1#sales-faq-009",
    "snippet": "客户拜访记录模板可在销售资料中心的模板库中下载，也可在 CRM 系统中直接填写电子版拜访记录。"
  },
  {
    "id": "sales-faq-010",
    "title": "合同模板在哪里获取？",
    "question": "合同模板在哪里获取？",
    "answer": "销售合同模板可在合同管理平台或法务标准模板库中获取。使用前建议确认模板版本是否为最新，如需调整条款需经法务审核。",
    "keywords": ["合同", "模板", "法务", "获取", "版本"],
    "business_domain": "sales",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Sales FAQ",
    "source_locator": "sales_faq_seed_v1#sales-faq-010",
    "snippet": "销售合同模板可在合同管理平台或法务标准模板库中获取。"
  },
  {
    "id": "sales-faq-011",
    "title": "内部支持联系人清单在哪里看？",
    "question": "内部支持联系人清单在哪里看？",
    "answer": "内部支持联系人清单通常维护在销售资料中心或内部通讯录中，按职能分类列出技术、法务、财务等支持对接人。",
    "keywords": ["联系人", "支持", "清单", "通讯录", "对接"],
    "business_domain": "sales",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Sales FAQ",
    "source_locator": "sales_faq_seed_v1#sales-faq-011",
    "snippet": "内部支持联系人清单通常维护在销售资料中心或内部通讯录中，按职能分类列出各支持对接人。"
  },
  {
    "id": "sales-faq-012",
    "title": "价格口径在哪里确认？",
    "question": "价格口径在哪里确认？",
    "answer": "价格口径以公司最新发布的价格通知或报价审批规范为准。如有疑问，建议联系财务或销售管理团队确认当前有效价格。",
    "keywords": ["价格", "口径", "报价", "确认", "通知"],
    "business_domain": "sales",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Sales FAQ",
    "source_locator": "sales_faq_seed_v1#sales-faq-012",
    "snippet": "价格口径以公司最新发布的价格通知或报价审批规范为准。"
  }
]
```

---

## 5. 入库说明

建议将上述 FAQ 内容按以下方式导入：

1. 每条 FAQ 作为一条独立知识条目或知识单元
2. 至少保留 `id / question / answer / keywords / source_locator / snippet`
3. 统一标记：
   - `business_domain = sales`
   - `document_type = faq`
   - `source_type = manual_faq`
   - `lifecycle_status = active`
   - `access_scope = internal`
4. 如进入文档库登记层，再补齐 `document_id / title / created_at / updated_at`

---

## 6. 当前阶段说明

这份 FAQ 内容的目标是：

- 支撑第一阶段企业内部销售支持高频问答
- 让系统先具备稳定、可控、可检索的 Sales FAQ 基础内容
- 为后续接入 `policy / process / guide / notice` 保留一致的元数据习惯

当前阶段不追求：

- 覆盖所有销售管理细节
- 处理高敏感客户信息或价格底线
- 输出竞争情报或经营预测
- 代替正式销售管理流程或权限系统

一句话总结：

**本文件是一份按第一阶段 Sales 业务域标准清洗后的 FAQ 种子内容，可作为 A 类输入直接进入企业内部知识问答系统的 FAQ 入库链路。**
