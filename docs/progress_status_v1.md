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

状态：**完成**

说明：

- `/api/chat/ask` 已补齐最小请求与结果记录落盘
- 反馈记录已通过 `trace_id` 与问答记录形成最小关联
- demo/dev 下已提供最小问答记录与反馈查看接口

### 4.8 最小记录查看与开发排查体验阶段

状态：**完成**

说明：

- 当前问答页已接入开发态最近记录区
- 当前开发者已可在单页内回看最近 ask / feedback 记录
- 当前下一片应进入记录细节压缩与本地数据维护边界收口

### 4.9 本地记录数据维护与查看摘要阶段

状态：**完成**

说明：

- 当前已补本地记录清理脚本与脚本说明
- 当前最近记录区已收口为更聚焦的摘要视图
- 当前下一片应进入本地记录维护策略配置化，而不是重新扩写记录查看界面

### 4.10 本地记录维护策略配置化阶段

状态：**完成**

说明：

- 已在 `settings.py` 增加最小记录保留数量配置项
- 已在两个 repo 的保存方法中增加保留边界截断逻辑
- 已在 `scripts/README.md` 补充保留策略说明
- 当前下一片应进入生产配置调优收口

### 4.11 生产配置调优收口阶段

状态：**完成**

说明：

- 已在 `settings.py` 增加 `cors_origins` 配置项，支持环境变量覆盖
- 已新增 `.env.example` 作为全量配置参考
- 已新增 `scripts/start-backend.ps1` 生产启动脚本
- 已在 `scripts/README.md` 补充生产配置说明
- 当前系统已具备最小生产配置调优与启动方式区分能力

---

## 5. 当前未完成内容

当前尚未完成的内容，已不再属于 FAQ Demo 收口，也不再属于 P6 / P7 / P8 / P9 / P10 当前片内未完成项，而主要属于新的后续片：

当前已完成 P6、P7、P8、P9、P10、P11、P12：最小文档上传与登记、文档解析与切块、document-first 检索、citation 回源、文档列表 / 删除、范围检索、问答记录闭环、前端记录查看入口、本地记录清理脚本、记录摘要收口、记录保留策略配置化、生产配置调优收口，并完成当前阶段最小测试与文档同步。

当前下一阶段主要剩余问题为：

1. 当前记录保留策略已配置化，但长期运行下的边界校验仍需真实环境验证
2. 当前仍缺少面向非开发用户的部署与运维最小说明

---

## 16. P11 之后规划：P12 生产配置调优收口片

### 16.1 P12 目标

把当前系统从：

```text
配置散落在代码默认值与脚本参数中
-> 缺少生产环境最小可调配置边界
-> 缺少配置参考与启动方式区分
```

推进到：

```text
配置有最小环境变量承载位
-> CORS 来源可按部署域名调优
-> 生产启动方式有明确区分
-> 配置差异有明确文档
```

### 16.2 P12 范围

P12 只做以下 4 类工作：

1. CORS 来源可配置化，支持环境变量 `ORIONSTACK_CORS_ORIGINS`
2. 新增 `.env.example` 作为配置参考文件
3. 新增生产启动脚本 `scripts/start-backend.ps1`（不带 `--reload`，支持多 worker）
4. 更新脚本说明、进度文档与文件职责文档

### 16.3 P12 不做的内容

P12 明确不做：

1. 不做 Docker / 容器化配置
2. 不做 Nginx / 反向代理配置
3. 不做 HTTPS / 证书配置
4. 不做数据库化存储
5. 不做 CI/CD 流水线
6. 不做复杂运维监控平台

### 16.4 P12 建议实现顺序

#### 第一步：CORS 来源可配置化

目标：

- 在 `settings.py` 中增加 `cors_origins` 配置项
- 默认值保持当前开发来源 `http://localhost:5173` 与 `http://127.0.0.1:5173`
- 生产环境可通过 `ORIONSTACK_CORS_ORIGINS` 环境变量设置实际部署域名
- `main.py` 中 CORS 中间件从 `settings` 读取 `cors_origins`

当前状态：

- `settings.py` 已增加 `cors_origins` 配置项与 `_resolve_cors_origins` 辅助函数
- `ORIONSTACK_CORS_ORIGINS` 支持逗号分隔的多来源值
- `main.py` 已从 `settings.cors_origins` 读取 CORS 来源
- `backend/tests/test_chat_flow.py` 已补齐 CORS 配置默认值与环境变量覆盖验证

#### 第二步：配置参考文件

目标：

- 新增 `.env.example` 列出所有可用环境变量及其默认值
- 为生产部署提供最小配置参考

当前状态：

- `.env.example` 已创建，包含所有 `ORIONSTACK_*` 环境变量及其说明

#### 第三步：生产启动脚本

目标：

- 新增 `scripts/start-backend.ps1`，以生产配置启动后端
- 与 `dev-backend.ps1` 的差异：不带 `--reload`，默认 `prod` 模式，支持 `-Workers` 参数

当前状态：

- `scripts/start-backend.ps1` 已创建
- 默认 `prod` 模式，不带 `--reload`
- 支持 `-Workers` 参数启动多 worker 进程

#### 第四步：文档收口

目标：

- 更新 `scripts/README.md` 补充生产配置说明、环境变量参考表与启动脚本说明
- 更新进度文档与文件职责文档

当前状态：

- `scripts/README.md` 已补充 `start-backend.ps1` 说明、生产配置说明、环境变量参考表与 CORS 来源说明
- `progress_status_v1.md` 已同步 P12 当前状态
- `file_responsibilities_v1.md` 已同步 `settings.py`、`start-backend.ps1` 与 `.env.example` 职责变化

### 16.5 P12 对应的文件级任务方向

#### 后端配置方向

- `backend/app/config/settings.py`
- `backend/main.py`

#### 配置与脚本方向

- `.env.example`
- `scripts/start-backend.ps1`
- `scripts/README.md`

#### 测试与文档方向

- `backend/tests/test_chat_flow.py`
- `docs/progress_status_v1.md`
- `docs/file_responsibilities_v1.md`

### 16.6 P12 可开工配置清单

#### 16.6.1 CORS 来源配置项

配置项：

- `ORIONSTACK_CORS_ORIGINS`

默认值（不设置时）：

- `http://localhost:5173,http://127.0.0.1:5173`

设置方式：

```powershell
$env:ORIONSTACK_CORS_ORIGINS = "https://app.example.com,https://admin.example.com"
```

#### 16.6.2 生产启动参数

脚本：

- `scripts/start-backend.ps1`

关键参数：

- `-AppMode prod`（默认）
- `-Workers 1`（默认）
- 不带 `--reload`

#### 16.6.3 环境变量参考

参见 `.env.example` 文件。

### 16.7 P12 可开工测试清单

#### 16.7.1 后端最小验证清单

应完成以下最小验证：

1. CORS 来源默认值包含开发环境来源
2. CORS 来源通过环境变量可自定义
3. CORS 来源为空时回退到默认开发来源
4. 生产启动脚本可正常启动（`-CheckOnly` 模式）

#### 16.7.2 文档要求

应同步以下内容：

1. `scripts/README.md` 补充生产配置与启动脚本说明
2. `progress_status_v1.md` 更新 P12 实际状态
3. `file_responsibilities_v1.md` 更新配置与脚本职责变化

### 16.8 P12 阶段结论目标

P12 完成后，应达成以下结论：

1. 生产环境 CORS 来源可通过环境变量配置，不再硬编码
2. 所有环境变量有明确参考文件与默认值
3. 生产启动方式与开发启动方式有明确区分
4. 配置差异（demo/dev/prod）有明确文档

### 16.9 P12 当前结论

当前 P12 的真实结论为：

1. `settings.py` 已增加 `cors_origins` 配置项，支持环境变量 `ORIONSTACK_CORS_ORIGINS` 覆盖
2. `.env.example` 已列出所有环境变量及其默认值与说明
3. `scripts/start-backend.ps1` 已提供生产启动入口，默认 `prod` 模式，不带 `--reload`
4. `scripts/README.md` 已补充生产配置说明、环境变量参考表与 CORS 来源说明

一句话总结：

**P12 计划范围已完成，当前系统已具备最小生产配置调优与启动方式区分能力。**

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
- 已进入 P8，并完成当前计划范围：ask 记录落盘、feedback 按 trace_id 关联、demo/dev 记录查看接口与最小测试收口
- 已进入 P9，并完成当前计划范围：前端最近记录区、开发态单页回看、前端构建与文档同步
- 已进入 P10，并完成当前计划范围：本地记录清理脚本、脚本说明、记录摘要收口与文档同步
- 已进入 P10，并完成当前计划范围：本地记录清理脚本、记录摘要收口与策略配置化
- 已进入 P11，并完成当前计划范围：本地记录维护策略配置化与自动截断
- 已进入 P12，并完成当前计划范围：CORS 来源可配置化、配置参考文件、生产启动脚本与配置说明收口

一句话总结就是：

**当前不再继续扩设计，FAQ Demo 到生产配置调优闭环链路已经跑通；当前 P6、P7、P8、P9、P10、P11、P12 计划范围已完成，如继续推进，应进入新的业务目标，而不是继续扩大当前片的实现范围。**

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

- `/api/chat/ask` 已在返回后写入最小问答记录
- 当前最小记录字段已包含：`trace_id / raw_query / response_status / retrieved_chunk_ids / created_at`
- `backend/tests/test_chat_flow.py` 已补齐 ask 记录写入验证

#### 第二步：反馈与问答记录关联

目标：

- 保持反馈继续写入本地 JSONL
- 通过 `trace_id` 让反馈记录可回指对应问答记录
- 避免 ask 与 feedback 两条链路语义漂移

当前状态：

- 反馈记录仍写入本地 JSONL
- 提交反馈后会按 `trace_id` 回写对应问答记录的最小反馈摘要
- `backend/tests/test_chat_flow.py` 已补齐 feedback 与 ask 记录关联验证

#### 第三步：最小记录查看接口

目标：

- 在 demo/dev 模式下提供最小最近记录查看接口
- 只服务开发排查与质量回看，不扩成后台

当前状态：

- `GET /api/chat/records?limit=50` 已接入
- `GET /api/chat/feedback?limit=50` 已接入
- 记录查看接口默认只在 demo/dev 模式开放，prod 下返回 `404`

#### 第四步：测试与文档收口

目标：

- 补齐 ask 记录、feedback 关联、记录查看接口的最小测试
- 更新进度文档与文件职责文档

当前状态：

- `backend/tests/test_chat_flow.py` 已补齐 ask 记录、feedback 关联、记录查看接口与 prod 暴露边界验证
- `progress_status_v1.md` 与 `file_responsibilities_v1.md` 已同步 P8 当前状态

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

### 12.8 P8 当前结论

当前 P8 的真实结论为：

1. ask 与 feedback 已通过 `trace_id` 形成最小记录闭环
2. demo/dev 模式下已可通过后端接口回看最近记录与最近反馈
3. prod 模式下记录查看接口默认不暴露
4. 后端最小测试已覆盖当前片的主路径与环境边界

一句话总结：

**P8 计划范围已完成，当前系统已具备最小问答记录与反馈闭环。**

---

## 13. P8 之后规划：P9 最小记录查看与开发排查体验收口片

### 13.1 P9 目标

把当前系统从：

```text
后端记录已落盘
-> 只能通过接口或文件查看
```

推进到：

```text
后端记录已落盘
-> 前端可最小查看最近记录
-> 开发排查路径更短
```

### 13.2 P9 范围

P9 只做以下 4 类工作：

1. 在当前前端增加最小记录查看区
2. 让开发者可按最近记录快速定位 ask / feedback 链路
3. 维持 demo/dev 可见、prod 隐藏的记录查看边界
4. 补手工验收与最小回归说明

### 13.3 P9 不做的内容

P9 明确不做：

1. 不新增第二个前端页面或路由系统
2. 不做完整日志后台或评测看板
3. 不做复杂筛选、搜索、分页与统计图表
4. 不做记录编辑、记录回放或请求重放
5. 不做生产环境默认暴露记录内容

### 13.4 P9 建议实现顺序

#### 第一步：前端记录接口接入

目标：

- 在前端服务层接入 `GET /api/chat/records` 与 `GET /api/chat/feedback`
- 定义前端最小记录类型

当前状态：

- `frontend/src/services/chat.ts` 已接入 `GET /api/chat/records` 与 `GET /api/chat/feedback`
- `frontend/src/types/chat.ts` 已补齐最小记录类型

#### 第二步：记录查看区接入当前问答页

目标：

- 在当前 `ChatPage` 中新增最小记录查看区
- 至少展示最近 ask 记录与反馈摘要

当前状态：

- 当前 `ChatPage` 已接入最近记录区
- 最近记录区已展示 ask 记录与 feedback 摘要
- 未新增第二页面

#### 第三步：开发排查交互收口

目标：

- 支持最小刷新操作
- 支持快速查看 `trace_id / raw_query / response_status / feedback_label`
- 保持仅在 demo/dev 可见

当前状态：

- 记录区已支持手动刷新
- 记录区已展示 `trace_id / raw_query / response_status / feedback_label`
- 当前区域仅在前端开发态显示

#### 第四步：手工验收与文档收口

目标：

- 补一轮前端最小手工验收记录
- 更新进度文档与文件职责文档

当前状态：

- `progress_status_v1.md` 与 `file_responsibilities_v1.md` 已同步 P9 当前状态
- 待补一轮前端最小手工验收记录

### 13.5 P9 对应的文件级任务方向

P9 预计会直接新增或修改以下文件附近：

#### 前端方向

- `frontend/src/pages/chat/ChatPage.vue`
- `frontend/src/services/chat.ts`
- `frontend/src/types/chat.ts`
- `frontend/src/styles/index.css`
- `frontend/src/components/chat/RecordList.vue`

#### 测试与文档方向

- `docs/progress_status_v1.md`
- `docs/file_responsibilities_v1.md`

### 13.6 P9 可开工接口清单

#### 13.6.1 最近问答记录接口

接口：

- `GET /api/chat/records?limit=20`

前端最小展示字段：

- `trace_id`
- `raw_query`
- `response_status`
- `retrieved_chunk_ids`
- `created_at`
- `feedback_label`

前端最小行为：

- 页面初始化后可手动或自动拉取最近记录
- 默认只展示最近少量记录，不做分页

#### 13.6.2 最近反馈记录接口

接口：

- `GET /api/chat/feedback?limit=20`

前端最小展示字段：

- `trace_id`
- `raw_query`
- `feedback_label`
- `response_status`
- `created_at`

说明：

- 如实现中发现反馈单独列表价值有限，可只保留最近问答记录列表，并把反馈摘要直接展示在同一面板内

### 13.7 P9 最小前端交互建议

当前建议仍在 `ChatPage` 单页收口，不新增页面。

建议最小交互：

1. 在 demo/dev 显示“最近记录”面板
2. 支持点击刷新记录
3. 每条记录展示问题、状态、时间、trace_id 与反馈摘要
4. 记录条目风格应与当前 Debug / 文档库区域保持一致
5. prod 模式下不展示该区域

### 13.8 P9 可开工测试清单

#### 13.8.1 前端最小手工验收清单

应完成以下手工验收：

1. demo/dev 模式下页面可看到最近记录区
2. prod 模式下页面不展示最近记录区
3. 发起一次 ask 后，最近记录区能看到新记录
4. 对 ask 提交 feedback 后，最近记录区能看到反馈摘要更新
5. 点击刷新后，记录区内容与后端接口结果一致

#### 13.8.2 回归保护要求

P9 完成后，以下旧能力不得回退：

1. 当前问答主链路与文档库管理功能保持可用
2. 当前 Debug 区域保持可用
3. 后端记录查看接口在 demo/dev 仍可用、prod 仍默认不暴露
4. 前端不新增第二页面或新的路由体系

### 13.9 P9 当前结论

当前 P9 的真实结论为：

1. 最近 ask / feedback 记录已进入前端单页可视区
2. 当前开发态排查路径已从“查文件 / 调接口”缩短到“页面直接查看”
3. 前端仍保持单页结构，未新增路由与后台页面

一句话总结：

**P9 计划范围已完成，当前系统已具备最小前端记录查看与开发排查体验。**

---

## 14. P9 之后规划：P10 本地记录数据维护与查看摘要收口片

### 14.1 P10 目标

把当前系统从：

```text
记录已能写入并查看
-> 但记录会持续累积
-> 查看信息仍偏散
```

推进到：

```text
记录已能写入并查看
-> 本地记录有最小维护边界
-> 最近记录展示更聚焦关键摘要
```

### 14.2 P10 范围

P10 只做以下 3 类工作：

1. 明确本地记录文件的最小保留与清理边界
2. 补最小维护脚本或说明
3. 收口最近记录展示字段，减少开发态噪音

### 14.3 P10 不做的内容

P10 明确不做：

1. 不做数据库化日志存储
2. 不做复杂统计图表与聚合报表
3. 不做自动归档到外部对象存储
4. 不做多环境统一日志治理平台
5. 不做生产环境默认开放记录维护接口

### 14.4 P10 建议实现顺序

#### 第一步：本地记录维护边界收口

目标：

- 明确 `chat_records.jsonl` 与 `feedback_records.jsonl` 的最小保留策略
- 明确保留条数或清理方式的默认边界

当前状态：

- 本地记录文件边界已明确为 `chat_records.jsonl` 与 `feedback_records.jsonl`
- 当前维护能力保持在本地文件层，不扩成服务端管理接口

#### 第二步：维护脚本或说明接入

目标：

- 在 `scripts/` 下提供最小本地记录清理脚本，或给出同等明确的操作说明
- 保持脚本只作用于本地记录文件，不触碰业务数据文件

当前状态：

- `scripts/clean-local-records.ps1` 已接入
- `scripts/README.md` 已补齐本地记录清理脚本说明

#### 第三步：最近记录摘要收口

目标：

- 收口 `RecordList` 的默认展示字段
- 优先突出 `trace_id / raw_query / response_status / feedback_label / created_at`
- 把次要细节降为次层信息，减少开发态噪音

当前状态：

- `RecordList` 默认展示已收口为摘要字段优先
- chunk 细节已下沉到折叠区，不再占用默认主视图

#### 第四步：手工验收与文档同步

目标：

- 补一轮本地记录维护与摘要查看的最小手工验收
- 更新进度文档、文件职责文档与脚本说明

当前状态：

- `progress_status_v1.md`、`file_responsibilities_v1.md` 与 `scripts/README.md` 已同步 P10 当前状态
- 待补一轮前端最小手工验收记录

### 14.5 P10 对应的文件级任务方向

P10 预计会直接新增或修改以下文件附近：

#### 前端方向

- `frontend/src/components/chat/RecordList.vue`
- `frontend/src/pages/chat/ChatPage.vue`
- `frontend/src/styles/index.css`

#### 后端与存储方向

- `backend/app/storage/repositories/chat_record_repo.py`
- `backend/app/storage/repositories/feedback_repo.py`
- `backend/app/config/settings.py`

#### 脚本与文档方向

- `scripts/clean-local-records.ps1`
- `scripts/README.md`
- `docs/progress_status_v1.md`
- `docs/file_responsibilities_v1.md`

### 14.6 P10 可开工接口 / 脚本清单

#### 14.6.1 本地记录清理脚本

建议脚本：

- `scripts/clean-local-records.ps1`

目标：

- 清理本地 `chat_records.jsonl` 与 `feedback_records.jsonl`
- 提供最小确认或 `-WhatIf` / `-CheckOnly` 风格保护

说明：

- 当前更适合脚本而不是开放后端删除接口
- 避免把本地维护需求扩成服务端管理能力

#### 14.6.2 最近记录摘要展示

目标：

- `RecordList` 默认收起低价值细节
- 保持最近记录区更适合“快速扫一眼排查”

建议摘要字段：

- `trace_id`
- `raw_query`
- `response_status`
- `feedback_label`
- `created_at`

### 14.7 P10 可开工测试清单

#### 14.7.1 前端最小手工验收清单

应完成以下手工验收：

1. 最近记录区在开发态仍可正常展示最近 ask / feedback
2. 最近记录默认摘要字段更聚焦，页面噪音减少
3. 清理本地记录后，最近记录区可正确反映空状态
4. 主问答、文档管理、Debug 区域不受记录清理影响

#### 14.7.2 脚本与文档要求

应同步以下内容：

1. `scripts/README.md` 增加本地记录清理脚本说明
2. `file_responsibilities_v1.md` 增加新脚本职责
3. `progress_status_v1.md` 更新 P10 实际状态

### 14.8 P10 阶段结论目标

P10 完成后，应达成以下结论：

1. 本地记录文件有明确维护边界
2. 最近记录区更适合作为开发排查入口
3. 本地维护能力不扩张为后端管理接口

### 14.9 P10 当前结论

当前 P10 的真实结论为：

1. 本地记录已具备最小清理脚本入口
2. 最近记录区已收口为更适合快速排查的摘要视图
3. 记录维护能力仍保持在本地脚本层，不扩张为服务端管理能力

一句话总结：

**P10 计划范围已完成，当前系统已具备最小本地记录维护与摘要查看能力。**

---

## 15. P10 之后规划：P11 本地记录维护策略配置化片

### 15.1 P11 目标

把当前系统从：

```text
记录可手动清理
-> 但默认保留边界主要靠人工约定
```

推进到：

```text
记录可手动清理
-> 默认保留策略有最小配置边界
-> 开发态维护说明更明确
```

### 15.2 P11 范围

P11 只做以下 3 类工作：

1. 为本地记录保留数量增加最小配置承载位
2. 明确保留策略的默认值与环境边界
3. 更新脚本说明与进度文档

### 15.3 P11 不做的内容

P11 明确不做：

1. 不做自动定时清理任务
2. 不做复杂归档或导出能力
3. 不做多环境统一保留策略管理
4. 不做基于时间戳或容量阈值的复杂清理策略
5. 不做生产环境默认开放记录保留配置接口

### 15.4 P11 建议实现顺序

#### 第一步：配置承载位补齐

目标：

- 在 `settings.py` 中增加最小记录保留数量配置项
- 明确默认值与环境边界

当前状态：

- 已增加 `ORIONSTACK_CHAT_RECORD_MAX_COUNT` 与 `ORIONSTACK_FEEDBACK_RECORD_MAX_COUNT`
- 默认值均为 200
- demo/dev 环境下默认生效

#### 第二步：保存时边界截断

目标：

- 在 `chat_record_repo` 与 `feedback_repo` 的保存方法中增加保留数量边界逻辑
- 超出默认保留数量时自动截断最旧记录

当前状态：

- 两个 repo 的 `save` 方法已增加 `_truncate_if_needed`
- 超出 `max_count` 时自动截断最旧记录

#### 第三步：脚本与文档说明收口

目标：

- 更新 `scripts/README.md` 补充保留策略说明
- 更新进度文档和文件职责文档

当前状态：

- `scripts/README.md` 已补充保留策略配置项说明
- `progress_status_v1.md` 与 `file_responsibilities_v1.md` 已同步 P11 当前状态

#### 第四步：最小验证与文档同步

目标：

- 补一轮配置生效后的最小验证
- 更新进度文档状态

当前状态：

- `backend/tests/test_chat_flow.py` 已补齐截断行为与零值边界验证

### 15.5 P11 对应的文件级任务方向

P11 预计会直接新增或修改以下文件附近：

#### 后端配置与存储方向

- `backend/app/config/settings.py`
- `backend/app/storage/repositories/chat_record_repo.py`
- `backend/app/storage/repositories/feedback_repo.py`

#### 脚本与文档方向

- `scripts/README.md`
- `docs/progress_status_v1.md`
- `docs/file_responsibilities_v1.md`

### 15.6 P11 可开工配置清单

#### 15.6.1 记录保留数量配置项

建议配置项：

- `ORIONSTACK_CHAT_RECORD_MAX_COUNT`
- `ORIONSTACK_FEEDBACK_RECORD_MAX_COUNT`

默认值建议：

- `chat_record_max_count`: 200
- `feedback_record_max_count`: 200

环境边界：

- demo/dev 环境下默认生效
- prod 环境下可按需调整或关闭记录落盘

#### 15.6.2 保存时边界截断逻辑

建议行为：

- 每次保存新记录后检查当前记录总数
- 超出 `max_count` 时删除最旧记录
- 保持记录总数不超过配置上限

### 15.7 P11 可开工测试清单

#### 15.7.1 后端最小验证清单

应完成以下最小验证：

1. 修改配置后，保存记录能正确截断超量记录
2. 默认保留数量下记录总数不超过上限
3. 配置关闭记录落盘时，保存操作不产生本地文件

#### 15.7.2 脚本与文档要求

应同步以下内容：

1. `scripts/README.md` 增加保留策略说明
2. `file_responsibilities_v1.md` 更新配置职责描述
3. `progress_status_v1.md` 更新 P11 实际状态

### 15.8 P11 阶段结论目标

P11 完成后，应达成以下结论：

1. 本地记录有明确的保留数量配置边界
2. 记录总数不再无限累积
3. 配置化边界不扩张为复杂治理平台

### 15.9 P11 当前结论

当前 P11 的真实结论为：

1. `settings.py` 已增加 `chat_record_max_count` 与 `feedback_record_max_count` 配置项，默认 200
2. 两个 repo 的 `save` 方法已在写入后自动截断超量记录
3. 配置为 0 时保留默认上限，不关闭落盘

一句话总结：

**P11 计划范围已完成，当前系统已具备最小记录保留策略配置化与自动截断能力。**
