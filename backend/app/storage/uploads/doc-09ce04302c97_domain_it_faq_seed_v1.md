# 第一阶段可直接入库 FAQ 内容：IT 业务域 v1

## 1. 文档目标

本文档提供一份已按第一阶段边界清洗的 IT 业务域 FAQ 种子内容，供知识库直接入库使用。

本内容遵循当前第一阶段边界：

- 以 FAQ / 业务知识问答主链路为核心
- 适用于企业内部高频 IT 支持问答
- 当前阶段只做轻量元数据与访问范围标记
- 作为 FAQ 种子内容导入，而不是完整 IT 运维制度、资产台账或权限系统全集

---

## 2. 使用范围

本 FAQ 内容适用于以下场景：

- 企业内部知识助手的 IT 支持问答
- 作为 A 类输入直接按 `manual_faq` 导入
- 提供可检索、可引用、可回源的基础问答内容
- 支撑账号、密码、设备、网络、权限、软件等高频 IT 问题

本 FAQ 内容不用于：

- 替代正式 IT 安全制度
- 替代完整资产管理系统、工单系统或权限系统
- 输出高敏感账号安全信息或个体系统凭据
- 承担复杂权限审批逻辑或跨系统自动编排

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

- `business_domain = it`
- `document_type = faq`
- `source_type = manual_faq`
- `lifecycle_status = active`
- `access_scope = internal`
- `source_label = IT FAQ`
- `source_locator = it_faq_seed_v1#<faq-id>`

如进入文档登记层，可按第一阶段文档库最小字段表补齐 `document_id / created_at / updated_at` 等字段。

本文件属于文档接入边界中的 A 类输入，可不经过独立 cleaning adapter，直接进入 FAQ 入库链路。

---

## 4. 可入库 FAQ 内容（结构化）

下面内容可作为 FAQ 种子数据直接整理入库。

```json
[
  {
    "id": "it-faq-001",
    "title": "忘记登录密码怎么办？",
    "question": "忘记登录密码怎么办？",
    "answer": "如忘记公司账号密码，可先通过统一登录页的找回密码入口自助重置。若无法自助处理，请提交 IT 支持申请，由管理员按流程协助重置。",
    "keywords": ["密码", "重置", "账号", "登录", "IT 支持"],
    "business_domain": "it",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "IT FAQ",
    "source_locator": "it_faq_seed_v1#it-faq-001",
    "snippet": "如忘记公司账号密码，可先通过统一登录页的找回密码入口自助重置。"
  },
  {
    "id": "it-faq-002",
    "title": "账号被锁定后怎么处理？",
    "question": "账号被锁定后怎么处理？",
    "answer": "账号被锁定后，可先确认是否因多次输错密码触发安全限制。若仍无法登录，请通过 IT 服务入口提交解锁申请，并按要求完成身份核验。",
    "keywords": ["账号锁定", "解锁", "登录", "身份核验", "安全限制"],
    "business_domain": "it",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "IT FAQ",
    "source_locator": "it_faq_seed_v1#it-faq-002",
    "snippet": "若仍无法登录，请通过 IT 服务入口提交解锁申请，并按要求完成身份核验。"
  },
  {
    "id": "it-faq-003",
    "title": "VPN 连不上怎么办？",
    "question": "VPN 连不上怎么办？",
    "answer": "VPN 无法连接时，可先检查网络是否正常、客户端是否已更新以及账号权限是否有效。若多次重试仍失败，请记录报错信息并联系 IT 支持处理。",
    "keywords": ["VPN", "连接失败", "网络", "客户端", "权限"],
    "business_domain": "it",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "IT FAQ",
    "source_locator": "it_faq_seed_v1#it-faq-003",
    "snippet": "VPN 无法连接时，可先检查网络是否正常、客户端是否已更新以及账号权限是否有效。"
  },
  {
    "id": "it-faq-004",
    "title": "如何申请安装办公软件？",
    "question": "如何申请安装办公软件？",
    "answer": "如需安装办公软件，应通过 IT 服务入口提交安装申请，注明软件名称、用途和设备信息。涉及授权或安全校验的软件，以审批结果和公司软件规范为准。",
    "keywords": ["软件安装", "申请", "办公软件", "授权", "审批"],
    "business_domain": "it",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "IT FAQ",
    "source_locator": "it_faq_seed_v1#it-faq-004",
    "snippet": "应通过 IT 服务入口提交安装申请，注明软件名称、用途和设备信息。"
  },
  {
    "id": "it-faq-005",
    "title": "新电脑怎么申请？",
    "question": "新电脑怎么申请？",
    "answer": "如需申请新电脑，应按公司设备管理流程提交申请，说明申请原因、岗位需求和设备类型。设备发放时间与配置标准以审批和库存情况为准。",
    "keywords": ["新电脑", "设备申请", "库存", "审批", "配置标准"],
    "business_domain": "it",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "IT FAQ",
    "source_locator": "it_faq_seed_v1#it-faq-005",
    "snippet": "应按公司设备管理流程提交申请，说明申请原因、岗位需求和设备类型。"
  },
  {
    "id": "it-faq-006",
    "title": "电脑故障怎么报修？",
    "question": "电脑故障怎么报修？",
    "answer": "电脑出现故障时，应通过 IT 工单或服务入口提交报修，填写设备编号、故障现象和紧急程度。必要时可附上报错截图，便于 IT 快速定位问题。",
    "keywords": ["电脑故障", "报修", "工单", "设备编号", "截图"],
    "business_domain": "it",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "IT FAQ",
    "source_locator": "it_faq_seed_v1#it-faq-006",
    "snippet": "应通过 IT 工单或服务入口提交报修，填写设备编号、故障现象和紧急程度。"
  },
  {
    "id": "it-faq-007",
    "title": "公司 Wi-Fi 怎么连接？",
    "question": "公司 Wi-Fi 怎么连接？",
    "answer": "连接公司 Wi-Fi 时，可使用公司统一下发的网络名称和认证方式登录。若首次接入失败，请确认账号权限、密码和设备网络设置是否正确。",
    "keywords": ["Wi-Fi", "无线网络", "连接", "认证", "账号权限"],
    "business_domain": "it",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "IT FAQ",
    "source_locator": "it_faq_seed_v1#it-faq-007",
    "snippet": "可使用公司统一下发的网络名称和认证方式登录。"
  },
  {
    "id": "it-faq-008",
    "title": "共享盘没有权限怎么办？",
    "question": "共享盘没有权限怎么办？",
    "answer": "如无法访问共享盘或共享文件夹，可先确认是否属于当前岗位可访问范围。若确需开通权限，请按流程提交权限申请，并由业务负责人或管理员审批。",
    "keywords": ["共享盘", "权限", "文件夹", "访问", "审批"],
    "business_domain": "it",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "IT FAQ",
    "source_locator": "it_faq_seed_v1#it-faq-008",
    "snippet": "若确需开通权限，请按流程提交权限申请，并由业务负责人或管理员审批。"
  },
  {
    "id": "it-faq-009",
    "title": "邮箱签名怎么修改？",
    "question": "邮箱签名怎么修改？",
    "answer": "邮箱签名通常可在邮箱设置中的签名页面修改。若公司对签名格式有统一规范，请优先按标准模板填写姓名、职位和联系方式。",
    "keywords": ["邮箱签名", "邮箱设置", "模板", "联系方式", "规范"],
    "business_domain": "it",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "IT FAQ",
    "source_locator": "it_faq_seed_v1#it-faq-009",
    "snippet": "邮箱签名通常可在邮箱设置中的签名页面修改。"
  },
  {
    "id": "it-faq-010",
    "title": "收不到验证码怎么办？",
    "question": "收不到验证码怎么办？",
    "answer": "收不到验证码时，可先确认网络状态、短信或邮件是否被拦截，以及当前绑定信息是否正确。若持续无法接收，请联系 IT 支持协助排查认证服务状态。",
    "keywords": ["验证码", "短信", "邮件", "认证", "绑定信息"],
    "business_domain": "it",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "IT FAQ",
    "source_locator": "it_faq_seed_v1#it-faq-010",
    "snippet": "可先确认网络状态、短信或邮件是否被拦截，以及当前绑定信息是否正确。"
  },
  {
    "id": "it-faq-011",
    "title": "打印机无法使用怎么办？",
    "question": "打印机无法使用怎么办？",
    "answer": "打印机无法使用时，可先检查设备电源、网络连接和打印队列状态。若问题仍未恢复，请提交 IT 报修，并注明所在位置和打印机编号。",
    "keywords": ["打印机", "无法使用", "打印队列", "网络连接", "报修"],
    "business_domain": "it",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "IT FAQ",
    "source_locator": "it_faq_seed_v1#it-faq-011",
    "snippet": "可先检查设备电源、网络连接和打印队列状态。"
  },
  {
    "id": "it-faq-012",
    "title": "如何申请系统权限开通？",
    "question": "如何申请系统权限开通？",
    "answer": "如需开通业务系统权限，应通过权限申请入口提交申请，说明系统名称、所需角色和业务用途。权限开通时间以审批流程和管理员处理结果为准。",
    "keywords": ["系统权限", "开通", "角色", "业务系统", "申请"],
    "business_domain": "it",
    "document_type": "faq",
    "source_type": "manual_faq",
    "lifecycle_status": "active",
    "access_scope": "internal",
    "source_label": "IT FAQ",
    "source_locator": "it_faq_seed_v1#it-faq-012",
    "snippet": "应通过权限申请入口提交申请，说明系统名称、所需角色和业务用途。"
  }
]
```

---

## 5. 入库说明

建议将上述 FAQ 内容按以下方式导入：

1. 每条 FAQ 作为一条独立知识条目或知识单元
2. 至少保留 `id / question / answer / keywords / source_locator / snippet`
3. 统一标记：
   - `business_domain = it`
   - `document_type = faq`
   - `source_type = manual_faq`
   - `lifecycle_status = active`
   - `access_scope = internal`
4. 如进入文档库登记层，再补齐 `document_id / title / created_at / updated_at`

---

## 6. 当前阶段说明

这份 FAQ 内容的目标是：

- 支撑第一阶段企业内部 IT 高频问答
- 让系统先具备稳定、可控、可检索的 IT FAQ 基础内容
- 为后续接入 `guide / process / notice / troubleshooting` 保留一致的元数据习惯

当前阶段不追求：

- 覆盖所有 IT 制度细节与全部设备场景
- 覆盖所有网络、账号和安全例外情况
- 处理高敏感账号凭据与个体安全配置
- 代替正式制度原文、工单系统或权限系统

一句话总结：

**本文件是一份按第一阶段 IT 业务域标准清洗后的 FAQ 种子内容，可作为 A 类输入直接进入企业内部知识问答系统的 FAQ 入库链路。**
