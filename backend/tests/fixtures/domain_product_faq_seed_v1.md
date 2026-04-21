# 第一阶段可直接入库 FAQ 内容：Product 业务域 v1

## 1. 文档目标

本文档提供一份已按第一阶段边界清洗的 Product 业务域 FAQ 种子内容，供知识库直接入库使用。

本内容遵循当前第一阶段边界：

- 以 FAQ / 业务知识问答主链路为核心
- 适用于企业内部高频产品协同与认知问答
- 当前阶段只做轻量元数据与访问范围标记
- 作为 FAQ 种子内容导入，而不是完整产品管理文档全集

---

## 2. 使用范围

本 FAQ 内容适用于以下场景：

- 企业内部知识助手的产品协同问答
- 作为 A 类输入直接按 `manual_faq` 导入
- 提供可检索、可引用、可回源的基础问答内容
- 支撑需求提交、版本发布、缺陷反馈等高频产品问题

本 FAQ 内容不用于：

- 替代完整产品路线图
- 替代未公开功能设计文档
- 输出高敏感竞争策略分析
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

- `business_domain = product`
- `document_type = faq`
- `source_type = manual_faq`
- `lifecycle_status = active`
- `access_scope = internal`
- `source_label = Product FAQ`
- `source_locator = product_faq_seed_v1#<faq-id>`

如进入文档登记层，可按第一阶段文档库最小字段表补齐 `document_id / created_at / updated_at` 等字段。

本文件属于文档接入边界中的 A 类输入，可不经过独立 cleaning adapter，直接进入 FAQ 入库链路。

---

## 4. 可入库 FAQ 内容（结构化）

下面内容可作为 FAQ 种子数据直接整理入库。

```json
[
  {
    "id": "product-faq-001",
    "title": "产品需求应该在哪里提交？",
    "question": "产品需求应该在哪里提交？",
    "answer": "产品需求可通过公司需求管理平台提交，填写需求描述、优先级和期望时间后，需求会进入评审队列等待产品团队评估。",
    "keywords": ["需求", "提交", "产品", "评审", "平台"],
    "business_domain": "product",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Product FAQ",
    "source_locator": "product_faq_seed_v1#product-faq-001",
    "snippet": "产品需求可通过公司需求管理平台提交，填写需求描述、优先级和期望时间后，需求会进入评审队列。"
  },
  {
    "id": "product-faq-002",
    "title": "版本计划在哪里查看？",
    "question": "版本计划在哪里查看？",
    "answer": "版本计划可在产品管理平台或项目管理工具中查看，通常包含版本号、预计发布时间和主要内容摘要。",
    "keywords": ["版本", "计划", "发布", "查看", "项目管理"],
    "business_domain": "product",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Product FAQ",
    "source_locator": "product_faq_seed_v1#product-faq-002",
    "snippet": "版本计划可在产品管理平台或项目管理工具中查看。"
  },
  {
    "id": "product-faq-003",
    "title": "功能上线后怎么反馈问题？",
    "question": "功能上线后怎么反馈问题？",
    "answer": "功能上线后如发现问题，可在缺陷管理平台提交问题反馈，注明功能模块、问题描述和复现步骤，产品团队会跟进处理。",
    "keywords": ["反馈", "问题", "功能", "上线", "缺陷"],
    "business_domain": "product",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Product FAQ",
    "source_locator": "product_faq_seed_v1#product-faq-003",
    "snippet": "功能上线后如发现问题，可在缺陷管理平台提交问题反馈，注明功能模块、问题描述和复现步骤。"
  },
  {
    "id": "product-faq-004",
    "title": "某个功能的定位是什么？",
    "question": "某个功能的定位是什么？",
    "answer": "功能定位说明可在产品文档中心或功能说明页面查看。如果文档中没有覆盖所需信息，建议联系对应产品负责人确认。",
    "keywords": ["功能", "定位", "说明", "产品", "文档"],
    "business_domain": "product",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Product FAQ",
    "source_locator": "product_faq_seed_v1#product-faq-004",
    "snippet": "功能定位说明可在产品文档中心或功能说明页面查看。"
  },
  {
    "id": "product-faq-005",
    "title": "缺陷应该怎么提？",
    "question": "缺陷应该怎么提？",
    "answer": "提交缺陷时应包含缺陷标题、所属模块、复现步骤、预期行为和实际行为。如附上截图或日志会加快处理速度。",
    "keywords": ["缺陷", "提交", "复现", "模块", "日志"],
    "business_domain": "product",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Product FAQ",
    "source_locator": "product_faq_seed_v1#product-faq-005",
    "snippet": "提交缺陷时应包含缺陷标题、所属模块、复现步骤、预期行为和实际行为。"
  },
  {
    "id": "product-faq-006",
    "title": "需求评审流程是什么？",
    "question": "需求评审流程是什么？",
    "answer": "需求提交后，产品团队会组织评审会议，评估需求可行性、优先级和排期。评审结果会反馈至需求提交人，并在需求管理平台中更新状态。",
    "keywords": ["需求", "评审", "流程", "排期", "优先级"],
    "business_domain": "product",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Product FAQ",
    "source_locator": "product_faq_seed_v1#product-faq-006",
    "snippet": "需求提交后，产品团队会组织评审会议，评估需求可行性、优先级和排期。"
  },
  {
    "id": "product-faq-007",
    "title": "上线验收需要做什么？",
    "question": "上线验收需要做什么？",
    "answer": "上线验收通常包括确认功能是否符合需求描述、回归测试核心流程、检查数据迁移和配置是否正确。验收完成后签字确认或在线提交验收结果。",
    "keywords": ["上线", "验收", "测试", "回归", "确认"],
    "business_domain": "product",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Product FAQ",
    "source_locator": "product_faq_seed_v1#product-faq-007",
    "snippet": "上线验收通常包括确认功能是否符合需求描述、回归测试核心流程、检查数据迁移和配置是否正确。"
  },
  {
    "id": "product-faq-008",
    "title": "发布说明模板在哪里？",
    "question": "发布说明模板在哪里？",
    "answer": "发布说明模板可在产品文档中心或项目管理工具的模板库中获取，通常包含版本号、发布日期、新增功能和修复项等字段。",
    "keywords": ["发布说明", "模板", "版本", "文档", "获取"],
    "business_domain": "product",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Product FAQ",
    "source_locator": "product_faq_seed_v1#product-faq-008",
    "snippet": "发布说明模板可在产品文档中心或项目管理工具的模板库中获取。"
  },
  {
    "id": "product-faq-009",
    "title": "需求优先级怎么定的？",
    "question": "需求优先级怎么定的？",
    "answer": "需求优先级通常由产品团队根据业务影响范围、用户覆盖量和战略对齐度综合评估。部分组织会采用 P0-P3 分级标准，具体以公司需求管理规范为准。",
    "keywords": ["需求", "优先级", "分级", "业务", "评估"],
    "business_domain": "product",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Product FAQ",
    "source_locator": "product_faq_seed_v1#product-faq-009",
    "snippet": "需求优先级通常由产品团队根据业务影响范围、用户覆盖量和战略对齐度综合评估。"
  },
  {
    "id": "product-faq-010",
    "title": "产品术语表在哪里查看？",
    "question": "产品术语表在哪里查看？",
    "answer": "产品术语表通常维护在产品文档中心或内部知识库中，用于统一团队间的术语理解。如发现术语缺失或有歧义，可向产品团队提出补充建议。",
    "keywords": ["术语", "产品", "文档", "知识库", "统一"],
    "business_domain": "product",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Product FAQ",
    "source_locator": "product_faq_seed_v1#product-faq-010",
    "snippet": "产品术语表通常维护在产品文档中心或内部知识库中，用于统一团队间的术语理解。"
  },
  {
    "id": "product-faq-011",
    "title": "某个模块的负责人是谁？",
    "question": "某个模块的负责人是谁？",
    "answer": "模块负责人信息可在产品管理平台或组织架构中查看。如无法确认，建议通过产品团队公共渠道咨询。",
    "keywords": ["模块", "负责人", "产品", "团队", "咨询"],
    "business_domain": "product",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Product FAQ",
    "source_locator": "product_faq_seed_v1#product-faq-011",
    "snippet": "模块负责人信息可在产品管理平台或组织架构中查看。"
  },
  {
    "id": "product-faq-012",
    "title": "版本回滚怎么操作？",
    "question": "版本回滚怎么操作？",
    "answer": "版本回滚需按公司发布管理流程提交回滚申请，说明回滚原因和影响范围，经技术负责人审批后由运维团队执行。紧急情况下可先口头确认再补流程。",
    "keywords": ["版本", "回滚", "发布", "运维", "审批"],
    "business_domain": "product",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "Product FAQ",
    "source_locator": "product_faq_seed_v1#product-faq-012",
    "snippet": "版本回滚需按公司发布管理流程提交回滚申请，经技术负责人审批后由运维团队执行。"
  }
]
```

---

## 5. 入库说明

建议将上述 FAQ 内容按以下方式导入：

1. 每条 FAQ 作为一条独立知识条目或知识单元
2. 至少保留 `id / question / answer / keywords / source_locator / snippet`
3. 统一标记：
   - `business_domain = product`
   - `document_type = faq`
   - `source_type = manual_faq`
   - `lifecycle_status = active`
   - `access_scope = internal`
4. 如进入文档库登记层，再补齐 `document_id / title / created_at / updated_at`

---

## 6. 当前阶段说明

这份 FAQ 内容的目标是：

- 支撑第一阶段企业内部产品协同高频问答
- 让系统先具备稳定、可控、可检索的 Product FAQ 基础内容
- 为后续接入 `policy / process / guide / notice` 保留一致的元数据习惯

当前阶段不追求：

- 覆盖所有产品管理细节
- 处理高敏感产品策略
- 输出未公开路线图或竞争分析
- 代替正式产品管理流程或权限系统

一句话总结：

**本文件是一份按第一阶段 Product 业务域标准清洗后的 FAQ 种子内容，可作为 A 类输入直接进入企业内部知识问答系统的 FAQ 入库链路。**
