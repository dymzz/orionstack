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
- 注入路由与状态管理

不负责：

- 不负责页面业务流程

### `frontend/src/App.vue`

职责：

- 作为应用根组件承载页面结构

不负责：

- 不负责问答逻辑
- 不负责 API 调用

### `frontend/src/pages/chat/ChatPage.vue`

职责：

- 作为问答主页面
- 串联输入、请求、回答、引用与调试展示

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

不负责：

- 不负责 citation 生成逻辑

### `frontend/src/services/api.ts`

职责：

- 封装基础 HTTP 客户端
- 统一处理请求基址、超时、错误包装

不负责：

- 不负责具体业务接口语义

### `frontend/src/services/chat.ts`

职责：

- 封装问答接口调用
- 对接 `/api/chat/ask`

不负责：

- 不负责组件展示逻辑

### `frontend/src/styles/index.css`

职责：

- 定义首轮全局样式
- 提供最小响应式布局规则

不负责：

- 不负责业务主题系统

### `frontend/src/types/chat.ts`

职责：

- 定义前端问答相关请求/响应类型

不负责：

- 不负责运行时校验实现

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
- 调用 `chat_service`
- 返回统一响应结构

不负责：

- 不负责直接实现检索、路由、回答生成

### `backend/app/schemas/request.py`

职责：

- 定义请求模型
- 固定 `raw_query` 等入参结构

不负责：

- 不负责业务执行

### `backend/app/schemas/response.py`

职责：

- 定义响应模型
- 固定 `response_status / answer / citations / trace_id` 等结构

不负责：

- 不负责组装业务数据来源

### `backend/app/services/chat_service.py`

职责：

- 串联最小主链路：归一化 -> 路由 -> 检索 -> 回答 -> citation 返回
- 作为问答业务主服务入口

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

- 基于 FAQ / mock 数据执行最小检索
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

### `backend/app/storage/seed/mock_faq.json`

职责：

- 作为 Demo 模式最小数据源
- 支持本地一秒启动闭环

不负责：

- 不负责正式环境数据来源

### `backend/app/config/settings.py`

职责：

- 定义最小配置读取入口
- 维护默认配置与环境变量覆盖规则

不负责：

- 不负责业务逻辑

### `backend/app/runtime/trace.py`

职责：

- 生成与透传 `trace_id`
- 支撑最小链路追踪

不负责：

- 不负责复杂观测平台集成

---

## 4.3 脚本文件职责

### `scripts/dev-backend.ps1`

职责：

- 启动后端开发服务

### `scripts/dev-frontend.ps1`

职责：

- 启动前端开发服务

### `scripts/dev-demo.ps1`

职责：

- 作为本地 Demo 一键启动入口
- 串联前后端开发启动流程

---

## 5. 当前最小依赖方向

当前阶段建议保持以下依赖方向：

```text
frontend/page -> frontend/components -> frontend/services -> backend api
backend api -> backend services -> routing / retrieval / guardrails / storage
storage -> seed/mock data
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
