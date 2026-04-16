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

状态：**待启动**

说明：

- 当前下一片应进入真实文档链路，而不是继续围绕 mock FAQ 做小修小补
- 当前工作重点应切换到：上传文档、解析切块、真实检索与 citation 回源

---

## 5. 当前未完成内容

当前尚未完成的内容，已不再属于 FAQ Demo 收口，而主要属于真实文档链路接入：

当前已完成 P6 前四步：最小文档上传与登记、文档解析与切块、document-first 检索、citation 回源与前端展示收口，并完成一轮最小测试与进度同步。

当前 P6 计划范围内未完成项已基本清空。

---

## 6. 下一片规划：P6 真实文档链路接入片

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
9. 不在 P6 前重新扩展 FAQ Demo 范围

---

## 10. 当前阶段结论

当前阶段的真实状态可以总结为：

- 设计已冻结
- 骨架已冻结
- 文件职责已冻结
- 最小可运行闭环已通过首轮本地验收
- P1-P5 已完成收口
- 已进入 P6，并完成当前计划范围：文档上传登记、文档解析切块、document-first 检索、citation 回源收口，以及最小测试与进度同步

一句话总结就是：

**当前不再继续扩设计，FAQ Demo 闭环已经跑通；当前 P6 计划范围已完成，如继续推进，应进入新的业务目标，而不是继续扩大当前片的实现范围。**
