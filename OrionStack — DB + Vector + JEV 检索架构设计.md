# OrionStack — DB + Vector + JEV 检索架构设计

## 1. 目标

系统面向企业内部 QA、客服、流程查询和运维知识查询。

主要要求：

- 支持自然语言语义查询；
- 支持员工编号、合同号、产品型号、工单号等精确实体查询；
- 能结合结构化业务数据与非结构化文档；
- QA 不要求所有回答达到事务系统级绝对精确，但必须有可靠证据；
- 回答必须能够追溯到真实文档；
- LLM 不负责决定来源真实性；
- JEV 负责检索过程中的结构化判断；
- 数据库保存确定性事实，Vector DB 保存语义检索能力。

整体职责：

```text
Database   → truth
Embedding  → semantic representation
Vector DB  → candidate evidence
JEV        → judgment
LLM        → language
```

---

## 2. 总体架构

```text
                         User Question
                               │
                               ▼
                    ┌────────────────────┐
                    │ Query Normalization│
                    │ entity extraction  │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ Retrieval JEV      │
                    │ 路由 / 范围判断     │
                    └─────────┬──────────┘
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
      Structured DB       Vector DB        DB + Vector
      exact facts         semantic         combined
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                     Candidate Evidence
                              │
                              ▼
                     ┌────────────────┐
                     │ Evidence JEV   │
                     │ relevance      │
                     │ support        │
                     │ sufficiency    │
                     └───────┬────────┘
                             │
                             ▼
                       Evidence Set
                             │
                             ▼
                     ┌────────────────┐
                     │      LLM       │
                     │ answer synthesis│
                     └───────┬────────┘
                             │
                             ▼
                    citation validation
                             │
                             ▼
                    Answer + real source
```

---

## 3. 数据层

建议统一使用 PostgreSQL。

如果已经使用 pgvector，则不需要为了向量检索再引入独立搜索引擎。

### 3.1 结构化业务数据

例如：

```text
employees
contracts
products
orders
tickets
departments
permissions
```

用于处理：

```text
员工编号
OA 编号
合同号
产品型号
工单编号
订单状态
员工状态
组织关系
权限
金额
日期
```

例如：

```sql
SELECT *
FROM contracts
WHERE contract_no = 'OA-2026-00183';
```

这类确定性事实直接由数据库查询。

---

## 4. 文档层

### documents

```text
id
document_name
document_type
business_domain
version
source_locator
created_at
updated_at
content_hash
metadata
```

例如：

```json
{
  "id": "doc_017",
  "document_name": "员工账户管理办法.pdf",
  "document_type": "policy",
  "business_domain": "account_management",
  "version": "2026-08-01"
}
```

### document_chunks

```text
id
document_id
chunk_index
text
embedding
page
section
metadata
content_hash
```

例如：

```json
{
  "id": "doc_017_c042",
  "document_id": "doc_017",
  "text": "员工离职后，其账户应在……",
  "page": 12,
  "section": "离职账户处理",
  "embedding": [...]
}
```

关系：

```text
documents
    │
    └── document_chunks
            │
            └── embedding
```

这样来源信息天然与向量结果绑定。

---

## 5. Query Processing

用户问题首先进入轻量 Query Processing。

目标不是完整理解，而是抽取检索需要的信息。

例如：

```text
OA-2026-00183 的付款条件是什么？
```

得到：

```json
{
  "query": "OA-2026-00183 的付款条件是什么？",
  "entities": [
    {
      "type": "contract_no",
      "value": "OA-2026-00183"
    }
  ]
}
```

实体提取可以由：

- 规则；
- 数据库存在性验证；
- LLM；
- JEV；

组合完成。

其中编号类信息优先使用规则 + DB 验证，而不是依赖语义模型。

---

## 6. 第一层 JEV：Retrieval Decision

第一层 JEV 不直接搜索文档。

它决定：

> 这个问题应该从哪里找答案。

建议输出：

```json
{
  "need_db": true,
  "need_vector": true,
  "entity_scope_required": true,
  "document_scope_required": true
}
```

### Case A：纯数据库

问题：

```text
OA-2026-00183 的合同金额是多少？
```

判断：

```text
need_db     = true
need_vector = false
```

流程：

```text
Question
   ↓
DB
   ↓
Answer
```

---

### Case B：纯文档语义查询

问题：

```text
员工年假一般需要提前多久申请？
```

判断：

```text
need_db     = false
need_vector = true
```

流程：

```text
Question
   ↓
Embedding
   ↓
Vector Search
```

---

### Case C：实体 + 文档

问题：

```text
OA-2026-00183 的付款条件是什么？
```

数据库首先确定：

```text
contract_no
↓
contract_id
↓
associated_document_id
```

然后：

```text
semantic query = "付款条件"
filter = document_id IN (...)
```

最终：

```text
DB exact scope
+
Vector semantic search
```

这是企业 QA 中非常重要的一种查询。

---

### Case D：结构化事实 + 企业规则

问题：

```text
OA-2026-00183 是否符合公司的长期合同付款规定？
```

需要：

```text
合同数据
+
公司制度文档
```

流程：

```text
DB
 └─ 当前合同事实

Vector
 └─ 公司付款规定

        ↓

Evidence JEV
        ↓
      LLM
```

---

## 7. Vector Recall

Vector Search 的任务只有一个：

> 从可能很大的知识库中快速找出候选证据。

例如：

```text
query embedding
      ↓
pgvector
      ↓
top_k = 10~20
```

返回：

```text
chunk_01   0.84
chunk_02   0.82
chunk_03   0.79
...
chunk_15   0.66
```

Embedding similarity 只表示语义接近程度。

它不代表：

```text
这个 chunk 一定能回答问题
```

所以这里不直接交给 LLM。

---

## 8. 第二层 JEV：Evidence Judgment

JEV 对候选证据进行业务意义上的判断。

建议至少判断三个维度：

```text
relevant
supports_answer
sufficient
```

### relevant

判断 chunk 是否真正与问题相关。

例如：

问题：

```text
年假最多可以连续休多少天？
```

Chunk A：

```text
员工申请年假需要通过 OA 系统。
```

Chunk B：

```text
单次连续年假原则上不得超过 10 个工作日。
```

两个 chunk embedding 都可能比较高。

但：

```text
Chunk A:
relevant = false / low

Chunk B:
relevant = true / high
```

---

### supports_answer

即使内容相关，也不一定能作为答案证据。

例如：

```text
员工离职需要执行账户清理流程。
```

对于：

```text
离职后多久删除账户？
```

属于相关内容，但没有给出时间。

因此：

```text
relevant       = true
supports_answer = false
```

---

### sufficient

判断当前证据是否已经足够回答。

例如：

```text
当前只有：
“账户应及时关闭”
```

无法回答：

```text
多少天内必须关闭？
```

则：

```text
sufficient = false
```

系统可以：

```text
扩大 Vector top_k
↓
换 query
↓
增加 document scope
↓
查询其他数据源
```

而不是让 LLM 猜。

---

## 9. JEV 不替代 Embedding

两者职责不同：

```text
Embedding
    ↓
从 50 万 chunks 中找到 20 个候选

JEV
    ↓
判断这 20 个候选里哪些真正有用
```

因此：

```text
Embedding = recall

JEV = judgment
```

JEV 可以参与：

```text
retrieval routing
candidate filtering
reranking
evidence sufficiency
conflict detection
```

但不承担大规模语义向量搜索。

---

## 10. Rerank 设计

可以使用：

```text
Embedding recall
       ↓
JEV rerank
```

或者：

```text
Embedding recall
       ↓
Cross Encoder reranker
       ↓
JEV evidence judgment
```

两者不冲突。

Cross Encoder 更偏：

```text
query ↔ document relevance
```

JEV 更适合：

```text
这个证据是否真正回答当前业务问题？
```

因此未来可以组合：

```text
Vector Recall
    ↓
Reranker
    ↓
JEV
    ↓
Evidence Set
```

初期也可以直接：

```text
Vector
↓
JEV
```

---

## 11. Source Attribution

来源必须绑定 retrieval result，而不是由 LLM 自由生成。

候选证据：

```json
{
  "evidence_id": "E1",
  "chunk_id": "doc_017_c042",
  "text": "...",
  "source": {
    "document_id": "doc_017",
    "document_name": "员工账户管理办法.pdf",
    "page": 12,
    "section": "离职账户处理"
  }
}
```

给 LLM：

```text
[E1]
员工离职后……

[E2]
……
```

要求 LLM 输出：

```json
{
  "answer": "员工离职后……",
  "citations": ["E1"]
}
```

但最终来源由后端解析：

```text
E1
↓
retrieval result
↓
document_id
↓
document_name/page/section
```

最终：

```text
员工离职后……

来源：
《员工账户管理办法》
第 12 页 · 离职账户处理
```

LLM 没有权限创造：

```text
document_name
page
source URL
document_id
```

---

## 12. Citation Validation

最终输出前增加确定性校验：

```text
citation id 是否真实存在？
        │
        ├── yes → 映射真实 metadata
        │
        └── no  → 删除 citation / 拒绝回答
```

还可以检查：

```text
LLM 使用的 citation
⊆
当前 evidence set
```

从结构上杜绝：

```text
LLM 编造文件名
LLM 编造页码
LLM 引用未召回文档
```

---

## 13. DB 与 Vector 的关系

结构化数据库与向量知识库不是两个互斥系统。

例如合同：

```text
contracts
├─ contract_id
├─ contract_no
├─ customer
├─ amount
├─ status
└─ signed_at
```

合同文件：

```text
documents
├─ document_id
├─ contract_id
└─ filename
```

合同正文：

```text
document_chunks
├─ document_id
├─ chunk_text
└─ embedding
```

因此：

```text
OA-2026-00183
     ↓
contracts
     ↓
contract_id
     ↓
documents
     ↓
document_id
     ↓
Vector Search
```

精确实体可以天然成为 Vector Search 的 filter。

---

## 14. 权限

企业 QA 的检索结果必须先满足权限范围。

流程应该是：

```text
user
 ↓
permission scope
 ↓
DB / document scope
 ↓
Vector Search
```

而不是：

```text
全库 Vector Search
↓
最后再隐藏
```

Vector metadata 至少保留：

```text
business_domain
department
access_scope
document_type
document_id
```

用于 filter。

---

## 15. 冲突信息

如果不同文档出现冲突：

```text
Document A:
30 天

Document B:
15 天
```

不能简单让 LLM自己选择。

可以交给 JEV 判断：

```text
same_rule
conflicting
newer_version
authoritative_source
```

再结合数据库 metadata：

```text
version
effective_date
document_status
document_type
```

选择当前有效版本。

无法确定时直接返回：

```text
检测到两个有效来源存在冲突
```

并同时显示来源。

---

## 16. 无充分证据

JEV 判断：

```text
sufficient = false
```

系统不应该继续要求 LLM生成确定答案。

可以回答：

```text
当前知识库中没有找到足够信息回答该问题。

已检索：
- 员工账户管理办法
- IT 系统权限管理规范
```

这也是系统健壮性的组成部分。

---

## 17. 推荐主链路

最终主链路：

```text
Question
   │
   ▼
Query Processing
   │
   ▼
Retrieval JEV
   │
   ├──────── DB lookup ──────────────┐
   │                                 │
   └──────── Vector retrieval ───────┤
                                     │
                                     ▼
                             Candidate Evidence
                                     │
                                     ▼
                               Evidence JEV
                                     │
                             relevant/support/
                               sufficient
                                     │
                                     ▼
                               Evidence Set
                                     │
                                     ▼
                                    LLM
                                     │
                                     ▼
                            Citation Validation
                                     │
                                     ▼
                          Answer + Verified Source
```

---

## 18. 组件职责最终划分

| Component | Responsibility |
|---|---|
| PostgreSQL | 企业事实、实体、关系、权限、metadata |
| pgvector | semantic recall |
| Embedding Model | query/document vectorization |
| Reranker | relevance ranking，可选 |
| Retrieval JEV | 决定查 DB、Vector 或组合 |
| Evidence JEV | relevance、support、sufficiency 等判断 |
| LLM | 问题理解与自然语言答案生成 |
| Citation Validator | 来源完整性和真实性验证 |

---

## 19. ES 的位置

当前架构中 ES 不作为核心依赖。

原因不是单纯为了减少组件，而是现有能力已经分别由更合适的模块覆盖：

```text
精确结构化查询
→ PostgreSQL

语义检索
→ Embedding + Vector

业务相关性判断
→ JEV

自然语言输出
→ LLM
```

如果未来出现明确的新需求，例如非常复杂的大规模全文检索、搜索分析或独立搜索产品需求，再单独评估 ES。

不需要为了理论上的 Hybrid Search 预留 ES。

---

## 20. 核心设计原则

整个系统最终遵循：

```text
Database decides facts.

Vector retrieves evidence.

JEV judges evidence.

LLM explains evidence.

Backend verifies citations.
```

对应中文：

> **数据库提供事实，向量检索发现证据，JEV 判断证据，LLM 组织答案，后端保证来源真实。**

这可以作为 OrionStack 下一阶段 QA / RAG / JEV 化的主架构。

---

## 21. Integration Boundary（2026-10-02 补充）

外部连接能力交给 n8n / 其他 workflow 系统，OrionStack 只保留稳定的 Action Contract、数据与事件接入边界。workflow 不侵入核心检索链路。

```text
外部系统 / 文件
       ↓
n8n / workflow：连接、编排、同步、审批、通知
       ↓
Integration Boundary：契约、身份、来源、版本、幂等校验
       ↓
OrionStack PostgreSQL + pgvector
       ↑
用户提问 → Retrieval JEV → DB / Vector → Evidence JEV → LLM → Citation Validation
```

n8n 已有的能力不在 OrionStack 内重建：

- SaaS / ERP / CRM connector
- Webhook trigger
- 定时任务
- OAuth / credential 管理
- API 调用编排
- retry / error branch
- 邮件、Slack、Teams 通知
- 文件传输
- 数据同步
- 人工审批节点

OrionStack 不继续扩展旧的“匹配 → 识别系统 → 调接口”外接方式。核心结构化检索直接访问已入库的事实；workflow 通过接入契约提交规范化事实、文件或状态事件。

边界保留 schema version、调用身份与租户、外部记录键、内部来源 ID 映射、版本、幂等键、trace、受理状态与生命周期校验。核心负责文档解析、chunk/embedding、知识有效性、权限范围、证据判断与引用校验。

用户提问不触发 workflow，不等待外部流程临时取数，不让 workflow 选择检索路径、组装候选证据或生成答案。workflow 不可用时，已有知识仍可查询；同步时间与过期状态由内部 metadata 表达。

详细交付顺序与 ID/hash 建议见 [下一版本交付计划](docs/designs/4_postgresql_jev_architecture.md)。

## 22. 三层划分与稳定接口（2026-10-02 补充）

```text
Knowledge Layer
  PostgreSQL + pgvector + Embedding
  事实、实体、文档、chunk、来源、版本与知识生命周期

Decision Layer
  JEV + LLM + permissions + citation
  检索决策、证据判断、答案组织、授权与来源校验

Integration Layer
  Action Contract → n8n / workflow
  动作分发、标准事件入口与 workflow 适配
```

稳定的边界接口：

| 接口 | 职责 |
| --- | --- |
| `POST /api/actions/execute` | 校验并提交标准业务动作，由 Integration Layer 委托 workflow 执行 |
| `POST /api/events` | 接收 workflow 的规范化数据、状态或完成事件，校验后更新核心数据 |
| `GET /api/entities/{type}/{id}` | 按权限读取核心数据库中的标准实体 |
| `POST /api/query` | 进入核心 DB/Vector/JEV/LLM/citation 问答链，不触发 workflow |

Action Schema 保持业务语义，不包含 n8n 节点、供应商凭据或外部系统调用细节：

```json
{
  "action": "create_ticket",
  "entity": {
    "type": "employee",
    "id": "EMP-00128"
  },
  "parameters": {
    "category": "account_access",
    "priority": "normal"
  },
  "context": {
    "request_id": "req_xxx"
  }
}
```

权限和租户上下文由后端认证确定，不信任客户端自行声明的角色。request_id 用于链路追踪和动作幂等；同一幂等键提交不同参数应拒绝。动作受理与执行完成分别表示，执行状态通过事件与请求 ID 关联。

动作执行是独立的业务操作入口，不是检索步骤。query 可以返回证据与业务动作建议，但不通过外部 workflow 临时获取检索候选。workflow 负责实际连接器、执行编排、重试、审批和通知。

以后可替换 n8n 为 Temporal、Make、Zapier 或企业自建 workflow engine。Action/Event/Entity 契约与 Knowledge/Decision Core 保持稳定，Integration Layer 的适配与配置随引擎变化。以上接口是下一版本目标，目前尚未注册到运行 API。

## 23. M1 实现与联调入口（2026-10-02）

单一数据库连接固定读取 `ORIONSTACK_DATABASE_URL`；Jev 和 DeepSeek 分别读取 `TYPESAFE_API_KEY`、`DEEPSEEK_API_KEY` 环境变量。密钥没有源码默认值，不落入日志或 Docker 构建上下文。

本阶段已建立单库 schema（来源、版本化文档/chunk/FAQ、实体目录、证据快照、Action/Event 台账）、事务迁移与默认只读预览，以及 QueryContext、AccessContext、EvidenceCandidate 和 Action/Event 契约。ID 用于来源身份与外键，完整 SHA-256 用于内容版本；embedding 带模型、维度和内容 hash 约束，模型选择后再建立相应索引。

Jev 已实现路由、逐条 relevance/support 和证据集合 sufficiency 客户端，完成一次虚构发票问题的真实调用，返回 `jev-1.13.0 / structured`。DeepSeek 已实现证据约束的 JSON 答案与引用 ID 检查，来源元数据由后端填写；完整语义核验与来源撤销复查将在后续阶段实现。

现有问答尚未切换到新核心。PostgreSQL/DeepSeek 的真实联调需要相应环境变量；当前文件迁移预览发现两条抽取 FAQ 缺少真实来源，会阻断整批导入，原数据保留。运行命令、实现范围与下一阶段验收见 [M1 运行说明](docs/designs/5_core_foundation_runbook.md)。
