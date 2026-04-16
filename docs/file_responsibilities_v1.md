# OrionStack 当前阶段文件职责说明 v1

## 1. 文档目标

本文档用于配合已冻结的 `system_design_v1`，说明当前阶段**最小可运行文件清单**中的各文件职责、边界与依赖方向。

本文档只服务于当前阶段的实现落地，不承担以下职责：

- 不描述未来扩展目录
- 不提前设计第二阶段文件树
- 不替代系统设计文档
- 不把“计划中的大而全平台目录”重新带回当前工程

## 2. 适用范围

本文档适用于当前阶段的最小可运行骨架，包括：

- 前端：手机 Web / PC Web 统一的 Vue 3 + Vite 前端
- 后端：FAQ / 业务知识问答主链路的最小 FastAPI 服务
- 脚本：本地 Demo 启动与最小开发辅助脚本

本文档中的文件职责，以“最小可运行闭环”为目标。

## 3. 使用原则

### 3.1 文件职责单一

每个文件只承担一类明确职责。

### 3.2 不跨层偷逻辑

- 前端组件不直接实现后端业务决策
- API 路由文件不直接堆叠业务逻辑
- 检索层不负责回答生成
- 路由层不负责复杂状态管理

### 3.3 先跑通，再细化

当前文件划分只服务于：

- `GET /healthz`
- `POST /api/chat/ask`

先完成最小闭环，再根据真实复杂度拆分。

---

## 4. 当前冻结目录与文件职责

### `README.md`

职责：

- 作为项目入口文档
- 提供前置要求、快速开始、生产部署、环境变量参考、项目结构与 API 列表
- 面向非开发用户提供最小可独立部署运行的参考

不负责：

- 不负责替代系统设计文档
- 不负责替代脚本详细参数说明（参见 `scripts/README.md`）

## 4.1 前端文件职责

### `frontend/package.json`

职责：

- 定义前端依赖
- 定义开发与构建脚本
- 作为前端工程入口配置文件

不负责：

- 不负责业务逻辑
- 不负责环境变量注入策略之外的运行时配置

### `frontend/vite.config.ts`

职责：

- 定义 Vite 构建配置
- 定义开发环境代理规则
- 定义最小前端开发行为

不负责：

- 不负责页面路由逻辑
- 不负责业务 API 封装

### `frontend/index.html`

职责：

- 提供单页应用挂载模板

不负责：

- 不负责应用逻辑

### `frontend/src/main.ts`

职责：

- 创建并挂载 Vue 应用
- 注册全局样式
- 注入当前最小根组件

不负责：

- 不负责页面业务流程

### `frontend/src/App.vue`

职责：

- 作为应用根组件承载当前单页问答入口

不负责：

- 不负责问答逻辑
- 不负责 API 调用

### `frontend/src/pages/chat/ChatPage.vue`

职责：

- 作为问答主页面
- 串联文档上传、文档列表、范围选择、删除、输入、请求、回答、引用、反馈、最近记录与调试展示

不负责：

- 不负责 HTTP 细节封装
- 不负责底层状态持久化

### `frontend/src/components/chat/ChatInput.vue`

职责：

- 接收用户输入
- 触发提交动作
- 提供固定提问范式或最小输入引导入口（如后续接入）

不负责：

- 不负责直接调用后端 API

### `frontend/src/components/chat/AnswerCard.vue`

职责：

- 展示回答正文
- 展示回答状态，如正常回答、拒答、fallback

不负责：

- 不负责 citation 数据拼装

### `frontend/src/components/chat/CitationList.vue`

职责：

- 展示 citation 列表
- 展示最小引用片段与来源定位信息
- 区分 FAQ 来源与文档来源的展示样式

不负责：

- 不负责 citation 生成逻辑

### `frontend/src/components/chat/DocumentUpload.vue`

职责：

- 提供最小文档选择与上传触发入口
- 展示当前上传状态与结果提示

不负责：

- 不负责直接发起上传请求

### `frontend/src/services/api.ts`

职责：

- 封装基础 HTTP 客户端
- 统一处理请求基址、超时、错误包装

不负责：

- 不负责具体业务接口语义

### `frontend/src/services/chat.ts`

职责：

- 封装问答接口调用
- 对接 `/api/chat/ask`、`/api/chat/feedback` 与记录查看接口

不负责：

- 不负责组件展示逻辑

### `frontend/src/services/documents.ts`

职责：

- 封装文档上传、列表、删除接口调用
- 对接 `/api/documents/upload`、`/api/documents`、`DELETE /api/documents/{document_id}`

不负责：

- 不负责上传组件交互状态管理

### `frontend/src/styles/index.css`

职责：

- 定义首轮全局样式
- 提供最小响应式布局规则

不负责：

- 不负责业务主题系统

### `frontend/src/types/chat.ts`

职责：

- 定义前端问答相关请求/响应类型
- 定义前端记录查看接口的最小记录类型

不负责：

- 不负责运行时校验实现

### `frontend/src/components/chat/RecordList.vue`

职责：

- 展示开发态最近 ask / feedback 记录列表
- 负责最近记录区的最小列表渲染与状态样式展示
- 以摘要优先方式展示记录，把次要细节下沉到折叠区

不负责：

- 不负责直接调用后端 API

### `frontend/src/types/document.ts`

职责：

- 定义文档上传响应类型

不负责：

- 不负责运行时校验实现

### `frontend/src/vite-env.d.ts`

职责：

- 注入 Vite 默认类型声明

不负责：

- 不负责业务类型定义

---

## 4.2 后端文件职责

### `backend/main.py`

职责：

- 创建 FastAPI 应用
- 注册路由
- 提供服务启动入口

不负责：

- 不负责具体业务实现

### `backend/app/api/routes/health.py`

职责：

- 提供健康检查接口

不负责：

- 不负责业务状态聚合

### `backend/app/api/routes/chat.py`

职责：

- 接收问答请求
- 接收最小反馈提交请求
- 提供 demo/dev 下的最小问答记录与反馈查看入口
- 调用 `chat_service`
- 返回统一响应结构
- 生成与透传 `trace_id`

不负责：

- 不负责直接实现检索、路由、回答生成

### `backend/app/api/routes/documents.py`

职责：

- 接收文档上传请求
- 调用 `document_service`
- 返回统一文档上传响应

不负责：

- 不负责直接实现文档解析与切块

### `backend/app/schemas/request.py`

职责：

- 定义请求模型
- 固定 `raw_query`、反馈等入参结构

不负责：

- 不负责业务执行

### `backend/app/schemas/document.py`

职责：

- 定义文档上传响应模型
- 固定 `document_id / text_length / chunk_count` 等结构

不负责：

- 不负责文件落盘或元数据保存

### `backend/app/schemas/response.py`

职责：

- 定义响应模型
- 固定 `response_status / answer / citations / trace_id` 等结构
- 定义记录查看接口的最小响应模型

不负责：

- 不负责组装业务数据来源

### `backend/app/services/chat_service.py`

职责：

- 串联最小主链路：归一化 -> 路由 -> document-first 检索 -> 回答 -> citation 返回
- 作为问答业务主服务入口
- 保留 FAQ fallback 边界
- 为后续最小问答记录落盘提供统一业务写入点

不负责：

- 不负责 HTTP 协议层处理

### `backend/app/routing/contracts.py`

职责：

- 定义 `IntentDecision` 等最小路由契约

不负责：

- 不负责具体路由判断逻辑

### `backend/app/routing/resolver.py`

职责：

- 作为路由协调层入口
- 统一调用具体 parser
- 产出最小路由结果

不负责：

- 不负责复杂规划与工作流编排

### `backend/app/routing/rule_parser.py`

职责：

- 实现当前首轮规则解析器
- 优先处理规则强命中或最小 FAQ 路由判断

不负责：

- 不负责复杂 LLM 路由决策

### `backend/app/retrieval/retriever.py`

职责：

- 基于 document chunks 与 FAQ fallback 执行最小检索
- 返回候选内容与分数

不负责：

- 不负责生成最终回答

### `backend/app/retrieval/citation_mapper.py`

职责：

- 将检索命中结果映射为统一 citation 结构

不负责：

- 不负责前端展示逻辑

### `backend/app/guardrails/normalize.py`

职责：

- 对原始输入执行最小归一化
- 生成 `normalized_query`

不负责：

- 不负责完整安全策略编排

### `backend/app/storage/repositories/faq_repo.py`

职责：

- 读取 FAQ 数据源
- 提供最小 FAQ 数据访问接口

不负责：

- 不负责检索打分逻辑

### `backend/app/storage/repositories/feedback_repo.py`

职责：

- 记录最小反馈数据
- 以本地 JSONL 形式持久化反馈记录
- 为按 `trace_id` 回看反馈提供最小数据访问基础
- 提供最近反馈记录读取接口
- 保存后按 `max_count` 自动截断最旧记录

不负责：

- 不负责反馈分析与统计聚合

### `backend/app/storage/repositories/chat_record_repo.py`

职责：

- 保存 `/api/chat/ask` 的最小请求与结果记录
- 提供最近问答记录的本地读取接口
- 为反馈与问答记录的 `trace_id` 对齐提供落盘基础
- 为本地记录维护边界收口提供存储入口
- 保存后按 `max_count` 自动截断最旧记录

不负责：

- 不负责检索、回答生成或复杂日志分析

### `backend/app/services/document_service.py`

职责：

- 串联文档上传、解析、切块与落盘保存流程
- 返回文档上传最小结果

不负责：

- 不负责问答检索逻辑

### `backend/app/services/document_parser.py`

职责：

- 将 `.txt / .md / .pdf / .docx` 解析为纯文本

不负责：

- 不负责 chunk 切分与持久化

### `backend/app/services/chunk_service.py`

职责：

- 对解析后的文本执行最小 chunk 切分

不负责：

- 不负责文件读取与存储

### `backend/app/storage/repositories/document_repo.py`

职责：

- 保存原始上传文件
- 保存最小文档元数据记录

不负责：

- 不负责解析文档内容

### `backend/app/storage/repositories/chunk_repo.py`

职责：

- 保存文档 chunks 与最小回源元数据
- 提供本地 chunk 列表读取接口

不负责：

- 不负责检索排序与回答生成

### `backend/app/storage/seed/mock_faq.json`

职责：

- 作为 Demo 模式最小数据源
- 支持本地一秒启动闭环

不负责：

- 不负责正式环境数据来源

### `backend/app/config/settings.py`

职责：

- 定义最小配置读取入口
- 维护默认配置、阈值与环境变量覆盖规则
- 为记录查看接口维护 demo/dev 与 prod 的暴露边界开关
- 维护本地记录保留数量配置项
- 维护 CORS 来源配置项

不负责：

- 不负责业务逻辑
- 不负责复杂治理策略编排

### `backend/app/runtime/trace.py`

职责：

- 生成与透传 `trace_id`
- 支撑最小链路追踪
- 为后续 ask 记录与 feedback 记录关联提供统一标识基础

不负责：

- 不负责复杂观测平台集成

---

## 4.3 脚本文件职责

### `scripts/dev-backend.py`

职责：

- 启动后端开发服务（带 `--reload`）

### `scripts/start-backend.py`

职责：

- 以生产配置启动后端服务（不带 `--reload`，支持多 worker）

### `scripts/dev-frontend.py`

职责：

- 启动前端开发服务

### `scripts/dev-demo.py`

职责：

- 作为本地 Demo 一键启动入口
- 串联前后端开发启动流程

### `scripts/git-release.py`

职责：

- 提供交互式版本发布脚本入口
- 同步 `pyproject.toml` 版本、git commit 与 git tag
- 执行当前分支 push 与 tag push

不负责：

- 不负责替代发布说明编写
- 不负责复杂多分支发布流程编排

### `scripts/clean-local-records.py`

职责：

- 清理本地问答记录与反馈记录文件
- 为开发态记录维护提供最小脚本入口
- 提供最小检查与预演保护

不负责：

- 不负责清理文档上传数据
- 不负责替代服务端管理接口

### `scripts/README.md`

职责：

- 汇总 `scripts/` 目录下各脚本的用途、参数与示例
- 汇总生产配置说明与环境变量参考

不负责：

- 不负责替代项目级 README

### `.env.example`

职责：

- 作为环境变量配置参考文件
- 列出所有可用环境变量及其默认值

不负责：

- 不负责自动加载环境变量
- 不负责替代运行时配置

---

## 5. 当前最小依赖方向

当前阶段建议保持以下依赖方向：

```text
frontend/page -> frontend/components -> frontend/services -> backend api
backend api -> backend services -> routing / retrieval / guardrails / storage
storage -> local jsonl data / seed/mock data
```

当前阶段不建议出现：

- 前端组件直接拼接后端响应协议细节
- API 路由文件直接读取 mock 数据
- 检索层反向依赖回答生成层
- 路由层依赖前端输入控件结构

---

## 6. 当前阶段结论

当前文件职责冻结的核心目标是：

1. 先把最小可运行文件集写清楚
2. 避免同一逻辑在多个文件之间来回漂移
3. 保持目录与职责一一对应
4. 为实现阶段提供可直接开工的边界

一句话总结就是：

**当前文件职责说明只服务于最小可运行闭环，不预埋第二阶段的大型目录和重型职责。**
