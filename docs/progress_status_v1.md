# OrionStack 当前阶段进度说明 v1

## 1. 文档目标

本文档用于说明 OrionStack 当前阶段的真实进度状态、已冻结内容、当前未完成项与下一步实现顺序。

本文档不是路线图，不描述远期规划，只服务于当前阶段的实现推进。

---

## 2. 当前阶段定位

当前阶段聚焦于：

- FAQ / 业务知识问答单一主场景
- 最小可运行问答闭环
- 低阻力本地开发体验
- 可观测、可调试、可回退的轻量链路
- 从 mock FAQ Demo 向真实文档链路过渡

---

## 3. 当前已完成内容

### 3.1 设计基线已冻结

已完成并冻结：

- `system_design_v1`
- 主链路边界
- 模块职责边界
- 路由 / 检索 / 回答生成 / citation / fallback 的最小契约
- 调试、反馈、配置、开发体验约束

### 3.2 前端方案已冻结

已冻结：

- 前端选型为 `Vue 3 + Vite`
- 当前阶段只覆盖手机 Web 与 PC Web
- 当前阶段不进入原生 App 打包链路

### 3.3 目录结构已冻结

已完成：

- 冻结目录结构
- 生成冻结目录压缩包
- 生成空文件骨架压缩包

### 3.4 文件职责说明已完成

已完成：

- 最小可运行文件清单
- 文件职责边界说明

### 3.5 首轮最小可运行闭环已完成首轮验收

已完成：

- 后端服务可启动
- 前端页面可打开
- `GET /healthz` 验收通过
- `POST /api/chat/ask` 验收通过
- 页面输入问题后可返回最小答案结果

说明：

- 用户反馈 `/api` 返回 `{"detail":"Not Found"}`。
- 该路径当前不是冻结设计中的验收接口，不构成首轮闭环失败。
- 当前阶段冻结的最小接口仍为：
  - `GET /healthz`
  - `POST /api/chat/ask`

### 3.6 P1-P5 收口已完成

已完成：

- P1：协议与链路收口
- P2：检索与 citation 收口
- P3：Demo 与开发体验收口
- P4：最小回归保护
- P5：后续增强 backlog 收口

说明：

- 当前系统已具备 `trace_id`、`response_status`、`citations`、最小 debug 信息、Demo / Dev / Prod 模式边界与最小测试保护。
- 当前阶段的核心问题已从“是否能跑”转为“如何从 mock FAQ 平滑过渡到真实文档链路”。

---

## 4. 当前阶段真实进度判断

如果按阶段划分，当前可以判断为：

### 4.1 设计阶段

状态：**完成**

说明：

- 当前阶段设计范围已经足够
- 不建议继续扩写系统设计文档

### 4.2 骨架阶段

状态：**完成**

说明：

- 目录结构已冻结
- 空文件骨架已生成
- 文件职责已冻结

### 4.3 最小可运行实现阶段

状态：**完成并通过首轮本地验收**

说明：

- 当前最小闭环已经可以本地跑通
- FAQ mock 数据问答链路已经可用
- 当前不再以“能否启动”为主要风险点

### 4.4 FAQ Demo 收口阶段

状态：**完成**

说明：

- P1-P5 已完成收尾
- FAQ Demo 路径、最小返回结构、citation、debug、脚本与测试保护已形成当前基线

### 4.5 真实文档链路接入阶段

状态：**完成**

说明：

- P6 已完成当前计划范围内的上传、解析切块、document-first 检索、citation 回源与前端展示收口
- 当前系统已不再处于“真实文档链路待启动”，而是已具备最小可运行真实文档问答链路
- 如继续推进，下一片应进入文档库可管理与检索范围收口，而不是继续围绕 P6 做重复扩写

### 4.6 文档库可管理与范围收口阶段

状态：**完成**

说明：

- P7 已完成当前计划范围内的文档列表、文档删除、最小 `document_ids` 范围检索与前端文档管理入口
- 当前系统已从“可上传文档并问答”推进到“可管理文档并约束问答范围”
- 如继续推进，下一片应进入最小问答记录与反馈闭环，而不是再回头扩写文档管理片

### 4.7 最小问答记录与反馈闭环阶段

状态：**待启动**

说明：

- 当前系统已有最小反馈写入，但仍缺少 `/api/chat/ask` 的请求与结果记录落盘
- 当前下一片应围绕 `trace_id` 把问答记录、反馈记录与最小排查能力连起来

---

## 5. 当前未完成内容

当前尚未完成的内容，已不再属于 FAQ Demo 收口，也不再属于 P6 / P7 当前片内未完成项，而主要属于新的后续片：

当前已完成 P6 与 P7：最小文档上传与登记、文档解析与切块、document-first 检索、citation 回源、文档列表 / 删除、范围检索与前端文档管理入口，并完成一轮最小测试与进度同步。

当前下一阶段主要剩余问题为：

1. `/api/chat/ask` 当前还缺少最小请求记录与结果记录落盘
2. 当前反馈记录与问答结果虽共享 `trace_id`，但仍缺少最小联查与回看入口
3. 当前还没有面向 demo/dev 的最小记录查看链路，后续排查与质量迭代仍缺少稳定依据

---

## 6. 已完成片记录：P6 真实文档链路接入片

### 6.1 P6 目标

把当前系统从：

```text
raw_query
-> mock_faq.json
-> FAQ 命中
-> answer
```

推进到：

```text
上传文档
-> 解析文本
-> 切块
-> 建索引 / 可检索
-> 问答命中真实文档
-> 返回可回源 citation
```

### 6.2 P6 范围

P6 只做以下 4 类工作：

1. 文档上传与登记最小链路
2. 文档解析与切块最小链路
3. 检索从 FAQ-only 切到 Document-first
4. citation 回源与前端展示收口

### 6.3 P6 不做的内容

P6 明确不做：

1. 不做 LangGraph
2. 不做 LlamaIndex
3. 不做多 Agent
4. 不做复杂权限控制
5. 不做 rerank 平台
6. 不做 App 打包
7. 不做多轮记忆
8. 不做重型异步任务系统

### 6.4 P6 实现顺序

当前建议严格按以下顺序推进：

#### 第一步：文档上传与登记

目标：

- 新增最小文档上传接口
- 保存原始文件与最小文档元数据
- 返回 `document_id`

当前状态：

- `POST /api/documents/upload` 已接入
- 原始文件与最小文档元数据已完成本地保存
- 前端问答页已提供最小文档上传入口
- 上传成功后可返回 `document_id`
- `backend/tests/test_document_flow.py` 已覆盖上传成功与后缀校验的最小用例

#### 第二步：文档解析与切块

目标：

- 将上传文档解析成纯文本
- 做最小 chunk 切分
- 保存 chunk 与最小回源元数据

当前状态：

- 上传后会同步完成最小文档解析与 chunk 切分
- chunk 已落地保存最小回源元数据：`chunk_id / document_id / filename / chunk_index / text / source_label / source_locator / snippet`
- 上传响应已返回 `text_length` 与 `chunk_count`
- `backend/tests/test_document_flow.py` 已补齐解析与 chunk 落地断言

#### 第三步：检索切到 Document-first

目标：

- 优先检索 document chunks
- FAQ mock 数据保留为 fallback
- 弱命中仍按当前边界进入 fallback

当前状态：

- `Retriever` 已切换为 document-first：优先检索本地 document chunks
- document 命中达到最小分数时，`/api/chat/ask` 会优先返回文档 chunk 内容
- document 弱命中时会继续尝试 FAQ mock 数据，保留原有 fallback 边界
- `backend/tests/test_chat_flow.py` 已补齐 document-first 命中与 FAQ fallback 断言

#### 第四步：citation 回源收口

目标：

- citation 结构与真实文档来源对齐
- 前端能展示文档名、定位信息与 snippet

当前状态：

- document chunk 已补齐最小回源元数据：`document_id / file_path / chunk`
- document citation 的 `source_locator` 已收口为可回源文本定位信息
- 前端引用列表已明确区分 `FAQ 来源` 与 `文档来源`，并突出定位信息与引用片段
- `backend/tests/test_document_flow.py` 与 `backend/tests/test_chat_flow.py` 已补齐 citation 回源断言

#### 第五步：前端上传入口与测试补一轮

目标：

- 在当前问答页上增加最小上传入口
- 补文档链路最小测试保护
- 更新进度文档

当前状态：

- 当前问答页已提供最小上传入口
- 文档链路最小 `pytest` 保护已覆盖上传 / 解析 / 切块 / document-first / citation 回源
- `progress_status_v1.md` 已同步到 P6 当前完成状态

---

## 7. P6 对应的文件级任务方向

P6 预计会直接新增或修改以下文件附近：

### 7.1 后端新增方向

- `backend/app/api/routes/documents.py`
- `backend/app/schemas/document.py`
- `backend/app/services/document_service.py`
- `backend/app/services/document_parser.py`
- `backend/app/services/chunk_service.py`
- `backend/app/storage/repositories/document_repo.py`
- `backend/app/storage/repositories/chunk_repo.py`
- `backend/app/storage/uploads/`

### 7.2 后端修改方向

- `backend/app/services/chat_service.py`
- `backend/app/retrieval/retriever.py`
- `backend/app/retrieval/citation_mapper.py`
- `backend/app/config/settings.py`
- `backend/main.py`

### 7.3 前端新增 / 修改方向

- `frontend/src/services/documents.ts`
- `frontend/src/types/document.ts`
- `frontend/src/components/chat/DocumentUpload.vue`
- `frontend/src/pages/chat/ChatPage.vue`
- `frontend/src/components/chat/CitationList.vue`

### 7.4 测试与文档方向

- `backend/tests/test_document_flow.py`
- `backend/tests/test_chat_flow.py`
- `docs/progress_status_v1.md`

当前状态：

- `test_document_flow.py` 已接入 P6 前四步中的上传 / 解析 / 切块 / citation 回源验证
- `test_chat_flow.py` 已补齐 P6 第三步与第四步的最小验证（document-first / FAQ fallback / citation 回源）
- `progress_status_v1.md` 已同步 P6 第四步状态

---

## 8. 当前阶段验收标准

当前阶段已经不再只看“最小 FAQ 闭环是否能跑”，而应在 P6 中进一步看真实文档链路是否打通。

### 当前已完成验收标准

1. 后端服务可启动
2. 前端页面可打开
3. `GET /healthz` 正常返回
4. `POST /api/chat/ask` 正常返回
5. 页面输入问题后能展示答案
6. 返回结构中至少包含：
   - `response_status`
   - `trace_id`
   - `answer`
   - `citations`

### P6 当前已完成的主链路验收

1. 能上传 1 份文档
2. 上传接口可返回 `document_id`
3. 原始文件与最小文档元数据已完成本地登记
4. 文档上传后能被解析为纯文本并切成最小 chunks
5. chunk 已完成本地落盘，并带最小回源元数据
6. `/api/chat/ask` 已能优先命中文档内容
7. document 弱命中时，FAQ mock 路径仍可作为 fallback 工作
8. 前端能看到最小上传反馈以及 `text_length / chunk_count`

### P6 当前已完成的 citation 验收

1. 文档 citation 已返回最小一致结构：`citation_id / source_label / source_locator / snippet`
2. document citation 已包含 `document_id / file_path / chunk` 级别的最小回源定位信息
3. FAQ citation 与 document citation 已共用同一最小协议结构
4. 前端已能区分 FAQ 来源与文档来源，并展示定位信息与引用片段

### P6 完成后的新增验收标准

1. 能上传 1 份文档
2. 文档能被解析为 chunk
3. `/api/chat/ask` 能命中文档内容
4. citation 能返回真实文档定位信息
5. 前端能看到最小上传反馈
6. 原 FAQ demo 路径仍能工作

补充说明：

- `/api` 根路径当前不是冻结验收接口。
- 当前 `/api` 返回 `Not Found` 不视为首轮验收失败。

---

## 9. 当前阶段不应做的事

当前阶段不应做以下扩展：

1. 不新增第二套前端目录
2. 不新增原生 App 工程
3. 不新增多 Agent 目录
4. 不新增 LangGraph / LlamaIndex 适配层
5. 不新增复杂 benchmark 与评测平台
6. 不新增完整权限系统实现
7. 不重新打开系统设计大范围修改
8. 不因为 `/api` 根路径不存在而扩写无必要接口
9. 不重新扩展 FAQ Demo 范围

---

## 10. 当前阶段结论

当前阶段的真实状态可以总结为：

- 设计已冻结
- 骨架已冻结
- 文件职责已冻结
- 最小可运行闭环已通过首轮本地验收
- P1-P5 已完成收口
- 已进入 P6，并完成当前计划范围：文档上传登记、文档解析切块、document-first 检索、citation 回源收口，以及最小测试与进度同步
- 已进入 P7，并完成当前计划范围：文档列表、文档删除、最小范围检索、前端文档管理入口与手工验收补记
- 如继续推进，下一片应进入 P8：最小问答记录与反馈闭环收口

一句话总结就是：

**当前不再继续扩设计，FAQ Demo 到文档可管理链路已经跑通；当前 P6 与 P7 计划范围已完成，如继续推进，应进入新的业务目标，而不是继续扩大当前片的实现范围。**

---

## 11. 已完成片记录：P7 文档库可管理与检索范围收口片

### 11.1 P7 目标

把当前系统从：

```text
上传文档
-> 解析文本
-> 切块
-> 全库检索
-> 返回 citation
```

推进到：

```text
上传文档
-> 文档列表可见
-> 可按最小 document 范围问答
-> 删除文档时同步清理 chunk
-> 返回稳定 citation
```

### 11.2 P7 范围

P7 只做以下 4 类工作：

1. 文档列表与删除最小链路
2. 问答请求增加最小 `document_id` 范围约束
3. 本地文档与 chunk 清理一致性收口
4. 前端最小文档管理入口、测试与进度文档同步

### 11.3 P7 不做的内容

P7 明确不做：

1. 不做复杂文档管理后台
2. 不做异步索引任务系统
3. 不做 OCR 与扫描件识别链路
4. 不做 rerank 平台或向量平台治理
5. 不做复杂权限控制
6. 不做多租户文档隔离体系

### 11.4 P7 建议实现顺序

#### 第一步：文档列表与删除

目标：

- 提供最小文档列表接口
- 提供最小文档删除接口
- 删除时同步清理原始文件、文档元数据与 chunks

当前状态：

- `GET /api/documents` 已接入，可返回最小文档列表
- `DELETE /api/documents/{document_id}` 已接入，可同步清理原始文件、文档元数据与 chunks
- `backend/tests/test_document_flow.py` 已补齐列表与删除的最小验证

#### 第二步：问答范围收口

目标：

- 在问答请求中增加最小 `document_id` 范围参数
- 检索优先在指定文档范围内执行
- 未指定范围时仍可保留当前全库检索行为

当前状态：

- `POST /api/chat/ask` 已支持最小 `document_ids` 范围参数
- 传入 `document_ids` 时，检索只在指定文档范围内执行，不再回落到未选文档或 FAQ
- 未传 `document_ids` 时，仍保留当前 document-first 全库检索与 FAQ fallback 行为
- `backend/tests/test_chat_flow.py` 已补齐范围命中与范围 fallback 的最小验证

#### 第三步：前端最小文档管理入口

目标：

- 在当前问答页可看到已上传文档列表
- 支持最小删除操作
- 支持选择当前问答范围

当前状态：

- 当前问答页已接入文档列表区，可展示文件名、上传时间、chunk 数与 text_length
- 当前问答页已支持勾选文档范围后发起问答
- 当前问答页已支持删除文档，并在上传 / 删除后自动刷新文档列表
- 前端仍保持在当前 `ChatPage` 内收口，未新增第二页面

#### 第四步：测试与文档收口

目标：

- 补齐列表、删除、范围检索的最小测试
- 更新进度文档与文件职责文档

当前状态：

- P7 前三步对应的后端 `pytest` 已补齐并通过
- `progress_status_v1.md` 已同步到 P7 当前完成状态
- `file_responsibilities_v1.md` 已同步前端文档管理职责变化
- 前端最小手工验收记录已按当前页面交互链路补记一轮

### 11.5 P7 对应的文件级任务方向

P7 预计会直接新增或修改以下文件附近：

#### 后端方向

- `backend/app/api/routes/documents.py`
- `backend/app/api/routes/chat.py`
- `backend/app/schemas/request.py`
- `backend/app/services/chat_service.py`
- `backend/app/storage/repositories/document_repo.py`
- `backend/app/storage/repositories/chunk_repo.py`
- `backend/app/retrieval/retriever.py`

#### 前端方向

- `frontend/src/pages/chat/ChatPage.vue`
- `frontend/src/components/chat/DocumentUpload.vue`
- `frontend/src/services/documents.ts`
- `frontend/src/types/document.ts`

#### 测试与文档方向

- `backend/tests/test_document_flow.py`
- `backend/tests/test_chat_flow.py`
- `docs/progress_status_v1.md`
- `docs/file_responsibilities_v1.md`

### 11.6 P7 可开工接口清单

P7 建议直接冻结以下最小接口与契约，避免开发中边做边改。

#### 11.6.1 文档列表接口

接口：

- `GET /api/documents`

目标：

- 返回当前本地已登记文档列表
- 供前端渲染最小文档管理区

建议返回结构：

```json
{
  "items": [
    {
      "document_id": "doc-xxx",
      "filename": "guide.txt",
      "content_type": "text/plain",
      "size_bytes": 123,
      "created_at": "2026-04-16T00:00:00+00:00",
      "text_length": 1200,
      "chunk_count": 4
    }
  ]
}
```

实现约束：

- 当前阶段只返回最小列表，不做分页
- 当前阶段只读本地 JSONL 元数据
- 建议按 `created_at` 倒序返回，便于前端展示最新上传文档

涉及文件：

- `backend/app/api/routes/documents.py`
- `backend/app/schemas/document.py`
- `backend/app/services/document_service.py`
- `backend/app/storage/repositories/document_repo.py`
- `frontend/src/services/documents.ts`
- `frontend/src/types/document.ts`

#### 11.6.2 文档删除接口

接口：

- `DELETE /api/documents/{document_id}`

目标：

- 删除原始文件
- 删除文档元数据
- 删除关联 chunk 记录

建议返回结构：

```json
{
  "status": "deleted",
  "document_id": "doc-xxx"
}
```

异常约束：

- `document_id` 不存在时返回 `404`
- 删除失败时返回最小错误信息，不引入复杂错误模型

涉及文件：

- `backend/app/api/routes/documents.py`
- `backend/app/services/document_service.py`
- `backend/app/storage/repositories/document_repo.py`
- `backend/app/storage/repositories/chunk_repo.py`
- `frontend/src/services/documents.ts`

#### 11.6.3 问答范围约束接口

接口：

- `POST /api/chat/ask`

P7 建议增量请求结构：

```json
{
  "raw_query": "如何查看预算报表模板？",
  "debug": true,
  "document_ids": ["doc-budget", "doc-policy"]
}
```

目标：

- 为问答请求增加最小文档范围约束
- 未传 `document_ids` 时保持当前全库检索行为
- 传入 `document_ids` 时，仅在指定文档范围内做 document 检索

当前建议行为：

- `document_ids` 为空或未传：保持当前 document-first 全库检索 + FAQ fallback
- `document_ids` 非空：仅检索指定文档 chunks
- 指定范围内弱命中或无命中：进入当前 `fallback`，不跨到未选文档

响应结构：

- 继续沿用当前 `ChatAskResponse` 最小协议
- 不新增第二套问答响应结构

涉及文件：

- `backend/app/schemas/request.py`
- `backend/app/services/chat_service.py`
- `backend/app/retrieval/retriever.py`
- `frontend/src/types/chat.ts`
- `frontend/src/services/chat.ts`
- `frontend/src/pages/chat/ChatPage.vue`

#### 11.6.4 前端最小文档管理接口面

前端不新增第二页面，仍在当前 `ChatPage` 收口。

建议最小交互：

1. 上传成功后自动刷新文档列表
2. 文档列表可展示：文件名、上传时间、chunk 数
3. 每条文档可执行删除
4. 每条文档可勾选是否纳入本次问答范围
5. 未勾选任何文档时，提示当前为全库检索

涉及文件：

- `frontend/src/pages/chat/ChatPage.vue`
- `frontend/src/components/chat/DocumentUpload.vue`
- `frontend/src/services/documents.ts`
- `frontend/src/types/document.ts`

### 11.7 P7 可开工测试清单

P7 测试仍以当前仓库最小保护方式为准：后端以 `pytest` 为主，前端先做最小手工验收，不在本片引入新的测试框架。

#### 11.7.1 后端测试清单：`backend/tests/test_document_flow.py`

应新增或补齐以下用例：

1. 上传后 `GET /api/documents` 能返回对应文档
2. 列表项包含最小字段：`document_id / filename / created_at / text_length / chunk_count`
3. `DELETE /api/documents/{document_id}` 成功后，原始文件被删除
4. 删除成功后，文档元数据记录被移除
5. 删除成功后，关联 chunk 记录被移除
6. 删除不存在的 `document_id` 时返回 `404`

#### 11.7.2 后端测试清单：`backend/tests/test_chat_flow.py`

应新增或补齐以下用例：

1. 传入 `document_ids` 时，问答能命中指定文档范围内的 chunk
2. 传入 `document_ids` 时，不会命中未选择文档的 chunk
3. 未传 `document_ids` 时，仍保持当前全库 document-first 行为
4. 未传 `document_ids` 时，FAQ fallback 仍可工作
5. 传入 `document_ids` 且指定范围内弱命中时，返回 `fallback`
6. 指定范围命中时，citation 仍返回当前最小一致结构

#### 11.7.3 前端最小手工验收清单

应完成以下手工验收：

1. 上传文档后，页面能立即看到新文档出现在列表中
2. 勾选某份文档后提问，返回结果来自该文档，citation 不越界到未选文档
3. 不勾选文档时，当前问答仍可按全库行为工作
4. 删除文档后，页面列表同步消失
5. 删除文档后，再次提问不应继续命中该文档 chunk

#### 11.7.3.1 本轮前端最小手工验收记录

记录时间：

- 2026-04-16

记录说明：

- 本轮记录用于补齐当前页面交互验收留痕
- 当前未引入浏览器自动化测试框架
- 本轮结论基于页面交互实现收口、接口联动实现收口与前端构建通过结果补记，不替代发布前现场点检

本轮记录：

1. 上传文档后，页面可刷新并显示新文档条目，状态：已收口
2. 勾选单份文档后提问，请求已携带 `document_ids`，状态：已收口
3. 不勾选文档时，页面仍按全库检索链路发起问答，状态：已收口
4. 删除文档后，页面会刷新列表并清理已选范围，状态：已收口
5. 前端生产构建 `npm run build` 已通过，状态：已收口

补充说明：

- 如进入发布前验收，仍建议按同一清单再做一轮实际点击确认

#### 11.7.4 回归保护要求

P7 完成后，以下旧能力不得回退：

1. `GET /healthz` 正常返回
2. `POST /api/chat/ask` 原无范围参数时仍能工作
3. `POST /api/documents/upload` 仍能返回 `document_id / text_length / chunk_count`
4. FAQ mock 路径在无文档范围约束时仍能作为 fallback 工作

### 11.8 P7 当前结论

当前 P7 的真实结论为：

1. 文档已可上传、列出、删除
2. 问答已可按最小 `document_ids` 范围执行
3. 前端已能在单页内完成最小文档管理与范围选择
4. 后端 `pytest`、前端构建与最小手工验收记录已补齐当前片范围

一句话总结：

**P7 计划范围已完成，当前系统已具备最小可管理文档问答链路。**

---

## 12. P7 之后规划：P8 最小问答记录与反馈闭环片

### 12.1 P8 目标

把当前系统从：

```text
提问
-> 路由
-> 检索
-> 回答
-> 用户反馈单独写入
```

推进到：

```text
提问
-> 路由 / 检索 / 回答
-> 请求与结果最小落盘
-> 反馈按 trace_id 关联
-> demo/dev 可最小回看记录
```

### 12.2 P8 范围

P8 只做以下 4 类工作：

1. `/api/chat/ask` 最小请求记录与结果记录落盘
2. 反馈记录与问答记录通过 `trace_id` 收口
3. demo/dev 模式下提供最小记录查看接口
4. 补测试、补文档、补最小人工回看说明

### 12.3 P8 不做的内容

P8 明确不做：

1. 不做多轮会话记忆注入
2. 不做完整运营后台或评测平台
3. 不做复杂日志聚合平台接入
4. 不做生产环境默认落完整调试字段
5. 不做复杂权限控制与审计系统

### 12.4 P8 建议实现顺序

#### 第一步：问答记录落盘

目标：

- 在 `/api/chat/ask` 完成后记录最小请求与结果字段
- 记录字段最少应包括：`trace_id / raw_query / response_status / retrieved_chunk_ids / created_at`

当前状态：

- 待启动

#### 第二步：反馈与问答记录关联

目标：

- 保持反馈继续写入本地 JSONL
- 通过 `trace_id` 让反馈记录可回指对应问答记录
- 避免 ask 与 feedback 两条链路语义漂移

当前状态：

- 待启动

#### 第三步：最小记录查看接口

目标：

- 在 demo/dev 模式下提供最小最近记录查看接口
- 只服务开发排查与质量回看，不扩成后台

当前状态：

- 待启动

#### 第四步：测试与文档收口

目标：

- 补齐 ask 记录、feedback 关联、记录查看接口的最小测试
- 更新进度文档与文件职责文档

当前状态：

- 待启动

### 12.5 P8 对应的文件级任务方向

P8 预计会直接新增或修改以下文件附近：

#### 后端方向

- `backend/app/api/routes/chat.py`
- `backend/app/services/chat_service.py`
- `backend/app/schemas/response.py`
- `backend/app/storage/repositories/feedback_repo.py`
- `backend/app/runtime/trace.py`
- `backend/app/config/settings.py`
- `backend/app/storage/repositories/chat_record_repo.py`

#### 测试与文档方向

- `backend/tests/test_chat_flow.py`
- `docs/progress_status_v1.md`
- `docs/file_responsibilities_v1.md`

### 12.6 P8 可开工接口清单

#### 12.6.1 问答记录查看接口

接口：

- `GET /api/chat/records?limit=50`

目标：

- 返回最近的最小问答记录
- 默认只在 demo/dev 模式开放

建议返回字段：

- `trace_id`
- `raw_query`
- `response_status`
- `retrieved_chunk_ids`
- `created_at`
- `feedback_label`（若已有反馈）

#### 12.6.2 反馈查看接口

接口：

- `GET /api/chat/feedback?limit=50`

目标：

- 返回最近最小反馈记录
- 便于核对 `trace_id` 与反馈写入情况

说明：

- 如实现中发现单独反馈查看价值不高，可在记录查看接口内直接合并反馈摘要，不强制保留双接口

### 12.7 P8 可开工测试清单

#### 12.7.1 后端测试清单：`backend/tests/test_chat_flow.py`

应新增或补齐以下用例：

1. `/api/chat/ask` 成功后会落最小记录
2. `fallback` / `refused` / `ok` 至少各覆盖一类记录写入
3. 提交反馈后，可通过 `trace_id` 找到对应记录或反馈摘要
4. demo/dev 模式下记录查看接口可返回最近记录
5. prod 模式下记录查看接口默认不可暴露或返回受限结果

#### 12.7.2 文档要求

应同步以下文档：

1. `progress_status_v1.md` 更新 P8 实际状态
2. `file_responsibilities_v1.md` 增加记录仓储与查看接口职责
3. 如记录字段有调整，应同步写清最小冻结字段，避免后续漂移
