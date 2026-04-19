# 第一阶段可直接入库 FAQ 内容：HR 业务域 v1

## 1. 文档目标

本文档提供一份已按第一阶段边界清洗的 HR 业务域 FAQ 种子内容，供知识库直接入库使用。

本内容遵循当前第一阶段边界：

- 以 FAQ / 业务知识问答主链路为核心
- 适用于企业内部高频 HR 问答
- 当前阶段只做轻量元数据与访问范围标记
- 作为 FAQ 种子内容导入，而不是完整 HR 制度文档全集

---

## 2. 使用范围

本 FAQ 内容适用于以下场景：

- 企业内部知识助手的 HR 问答
- 作为 A 类输入直接按 `manual_faq` 导入
- 提供可检索、可引用、可回源的基础问答内容
- 支撑请假、考勤、入离职、福利、证明等高频 HR 问题

本 FAQ 内容不用于：

- 替代正式员工手册
- 替代完整制度原文
- 输出高敏感个体人事数据
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

- `business_domain = hr`
- `document_type = faq`
- `source_type = manual_faq`
- `lifecycle_status = active`
- `access_scope = internal`
- `source_label = HR FAQ`
- `source_locator = hr_faq_seed_v1#<faq-id>`

如进入文档登记层，可按第一阶段文档库最小字段表补齐 `document_id / created_at / updated_at` 等字段。

本文件属于文档接入边界中的 A 类输入，可不经过独立 cleaning adapter，直接进入 FAQ 入库链路。

---

## 4. 可入库 FAQ 内容（结构化）

下面内容可作为 FAQ 种子数据直接整理入库。

```json
[
  {
    "id": "hr-faq-001",
    "title": "如何申请年假？",
    "question": "如何申请年假？",
    "answer": "进入公司请假入口后选择年假，填写请假时间与原因并提交审批。审批通过后，请假记录会同步到考勤系统。",
    "keywords": ["年假", "请假", "申请", "审批", "考勤"],
    "business_domain": "hr",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "HR FAQ",
    "source_locator": "hr_faq_seed_v1#hr-faq-001",
    "snippet": "进入公司请假入口后选择年假，填写请假时间与原因并提交审批。"
  },
  {
    "id": "hr-faq-002",
    "title": "病假需要提交什么材料？",
    "question": "病假需要提交什么材料？",
    "answer": "病假通常需要提交医院证明或诊断材料。具体提交方式以公司请假流程要求为准，建议在提交请假申请时一并上传。",
    "keywords": ["病假", "材料", "医院证明", "诊断", "请假"],
    "business_domain": "hr",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "HR FAQ",
    "source_locator": "hr_faq_seed_v1#hr-faq-002",
    "snippet": "病假通常需要提交医院证明或诊断材料。"
  },
  {
    "id": "hr-faq-003",
    "title": "请假审批进度在哪里查看？",
    "question": "请假审批进度在哪里查看？",
    "answer": "请假提交后，可在请假申请记录或审批记录页面查看当前审批状态。若长时间未处理，可按流程联系直属上级或 HR。",
    "keywords": ["请假", "审批", "进度", "状态", "查看"],
    "business_domain": "hr",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "HR FAQ",
    "source_locator": "hr_faq_seed_v1#hr-faq-003",
    "snippet": "可在请假申请记录或审批记录页面查看当前审批状态。"
  },
  {
    "id": "hr-faq-004",
    "title": "考勤异常怎么申诉？",
    "question": "考勤异常怎么申诉？",
    "answer": "发现迟到、缺卡或工时异常后，应在考勤系统中发起异常申诉，并按要求补充说明或附件。申诉通过后，考勤记录会被更新。",
    "keywords": ["考勤", "异常", "申诉", "缺卡", "工时"],
    "business_domain": "hr",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "HR FAQ",
    "source_locator": "hr_faq_seed_v1#hr-faq-004",
    "snippet": "应在考勤系统中发起异常申诉，并按要求补充说明或附件。"
  },
  {
    "id": "hr-faq-005",
    "title": "入职第一天需要办理什么手续？",
    "question": "入职第一天需要办理什么手续？",
    "answer": "入职第一天通常需要完成报到登记、资料提交、账号开通确认、劳动资料签署及入职说明阅读。具体以公司入职通知为准。",
    "keywords": ["入职", "报到", "资料提交", "账号开通", "手续"],
    "business_domain": "hr",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "HR FAQ",
    "source_locator": "hr_faq_seed_v1#hr-faq-005",
    "snippet": "入职第一天通常需要完成报到登记、资料提交、账号开通确认等手续。"
  },
  {
    "id": "hr-faq-006",
    "title": "离职流程怎么走？",
    "question": "离职流程怎么走？",
    "answer": "提出离职后，应按公司流程提交离职申请，完成审批、工作交接、资产归还与离职手续办理。离职生效时间以审批和流程结果为准。",
    "keywords": ["离职", "流程", "交接", "资产归还", "审批"],
    "business_domain": "hr",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "HR FAQ",
    "source_locator": "hr_faq_seed_v1#hr-faq-006",
    "snippet": "应按公司流程提交离职申请，完成审批、工作交接、资产归还与离职手续办理。"
  },
  {
    "id": "hr-faq-007",
    "title": "在职证明怎么申请？",
    "question": "在职证明怎么申请？",
    "answer": "如需开具在职证明，可通过 HR 服务入口提交申请，填写用途和收件方式。证明开具时间与领取方式以公司规则为准。",
    "keywords": ["在职证明", "申请", "HR 服务", "证明", "开具"],
    "business_domain": "hr",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "HR FAQ",
    "source_locator": "hr_faq_seed_v1#hr-faq-007",
    "snippet": "可通过 HR 服务入口提交申请，填写用途和收件方式。"
  },
  {
    "id": "hr-faq-008",
    "title": "社保和公积金从什么时候开始缴纳？",
    "question": "社保和公积金从什么时候开始缴纳？",
    "answer": "社保和公积金的缴纳起始时间通常按公司制度和当地政策执行。具体起缴月份与生效时间请以 HR 通知或员工服务入口信息为准。",
    "keywords": ["社保", "公积金", "缴纳", "起缴", "员工服务"],
    "business_domain": "hr",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "HR FAQ",
    "source_locator": "hr_faq_seed_v1#hr-faq-008",
    "snippet": "社保和公积金的缴纳起始时间通常按公司制度和当地政策执行。"
  },
  {
    "id": "hr-faq-009",
    "title": "工资条在哪里查看？",
    "question": "工资条在哪里查看？",
    "answer": "工资条通常可在员工自助服务平台、薪酬系统或公司指定入口查看。如未显示，请先确认账号权限或联系 HR。",
    "keywords": ["工资条", "查看", "员工自助", "薪酬系统", "HR"],
    "business_domain": "hr",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "HR FAQ",
    "source_locator": "hr_faq_seed_v1#hr-faq-009",
    "snippet": "工资条通常可在员工自助服务平台、薪酬系统或公司指定入口查看。"
  },
  {
    "id": "hr-faq-010",
    "title": "公司福利信息在哪里查看？",
    "question": "公司福利信息在哪里查看？",
    "answer": "公司福利信息通常在员工手册、HR 服务入口或福利说明页面中查看。若福利政策有调整，以最新正式通知为准。",
    "keywords": ["福利", "员工手册", "HR 服务", "说明页面", "通知"],
    "business_domain": "hr",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "HR FAQ",
    "source_locator": "hr_faq_seed_v1#hr-faq-010",
    "snippet": "公司福利信息通常在员工手册、HR 服务入口或福利说明页面中查看。"
  },
  {
    "id": "hr-faq-011",
    "title": "调休余额在哪里看？",
    "question": "调休余额在哪里看？",
    "answer": "调休余额通常可在考勤或请假系统中查看。如系统数据与实际不符，应按流程发起异常申诉或联系 HR。",
    "keywords": ["调休", "余额", "考勤", "请假系统", "申诉"],
    "business_domain": "hr",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "HR FAQ",
    "source_locator": "hr_faq_seed_v1#hr-faq-011",
    "snippet": "调休余额通常可在考勤或请假系统中查看。"
  },
  {
    "id": "hr-faq-012",
    "title": "试用期考核结果在哪里确认？",
    "question": "试用期考核结果在哪里确认？",
    "answer": "试用期考核结果通常通过员工系统、直属上级通知或 HR 通知确认。具体时间和确认方式以公司试用期流程为准。",
    "keywords": ["试用期", "考核", "结果", "员工系统", "HR 通知"],
    "business_domain": "hr",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "HR FAQ",
    "source_locator": "hr_faq_seed_v1#hr-faq-012",
    "snippet": "试用期考核结果通常通过员工系统、直属上级通知或 HR 通知确认。"
  }
]
```

---

## 5. 入库说明

建议将上述 FAQ 内容按以下方式导入：

1. 每条 FAQ 作为一条独立知识条目或知识单元
2. 至少保留 `id / question / answer / keywords / source_locator / snippet`
3. 统一标记：
   - `business_domain = hr`
   - `document_type = faq`
   - `source_type = manual_faq`
   - `lifecycle_status = active`
   - `access_scope = internal`
4. 如进入文档库登记层，再补齐 `document_id / title / created_at / updated_at`

---

## 6. 当前阶段说明

这份 FAQ 内容的目标是：

- 支撑第一阶段企业内部 HR 高频问答
- 让系统先具备稳定、可控、可检索的 HR FAQ 基础内容
- 为后续接入 `policy / process / guide / notice` 保留一致的元数据习惯

当前阶段不追求：

- 覆盖所有 HR 制度细节
- 覆盖所有地方政策差异
- 处理高敏感个体人事信息
- 代替正式制度原文、审批系统或权限系统

一句话总结：

**本文件是一份按第一阶段 HR 业务域标准清洗后的 FAQ 种子内容，可作为 A 类输入直接进入企业内部知识问答系统的 FAQ 入库链路。**
