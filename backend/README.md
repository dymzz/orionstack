# backend

后端骨架基于：

- FastAPI：API 接入层
- LangGraph：工作流编排层
- LlamaIndex：知识与文档能力层

## 目录说明

- `app/api/routes/`: 路由入口
- `app/api/schemas/`: 请求 / 响应模型
- `app/workflows/knowledge_assistant/`: 首期知识助手工作流
- `app/knowledge/ingestion/`: 文档接入
- `app/knowledge/indexing/`: 文档索引
- `app/knowledge/retrieval/`: 检索问答
- `app/services/`: 业务服务
- `app/repositories/`: 数据访问层
- `app/models/`: ORM / 数据模型
- `app/integrations/`: 外部系统与模型集成
- `app/governance/`: 日志、审计、反馈
- `app/core/`: 配置、依赖注入、公共工具
