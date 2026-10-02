# 生产部署指南

## 概述

OrionStack 使用 Docker Compose 进行生产部署，包含三个服务：

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| `elasticsearch` | `orionstack-elasticsearch:8.17.0-ik` | 9200（内部） | 中文搜索后端（IK 分词器） |
| `backend` | `orionstack-backend:prod` | 8000（内部） | FastAPI 后端服务 |
| `frontend` | `orionstack-frontend:prod` | 80→8080 | Nginx 静态文件 + 反向代理 |

---

## 1. 快速开始

### 前置条件

- Docker + Docker Compose
- 至少 2GB 可用内存（Elasticsearch 需要）

### 部署步骤

```bash
# 1. 克隆仓库
git clone <repo-url> && cd orionstack

# 2. 创建生产环境配置
cp .env.prod.example .env.prod

# 3. 编辑 .env.prod（必须修改以下变量！）
#    ORIONSTACK_ADMIN_PASSWORD=<强密码>
#    ORIONSTACK_ADMIN_TOKEN_SECRET=<至少24位随机字符串>
#    DASHSCOPE_API_KEY=<你的 API 密钥>（如需 LLM 功能）

# 4. 构建并启动
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build

# 5. 检查服务状态
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
curl http://localhost:8080/readyz
```

### 首次启动

后端容器首次启动时，`backend-entrypoint.sh` 会自动将默认的 ActionLink 和 DynamicQuery JSONL 数据复制到空的持久卷中。已有数据不会被覆盖。

---

## 2. 环境变量配置

### 必需配置（生产环境）

| 变量 | 说明 | 示例 |
|------|------|------|
| `ORIONSTACK_ADMIN_PASSWORD` | 管理员密码，**不能使用默认值** | `myStr0ng!Passw0rd` |
| `ORIONSTACK_ADMIN_TOKEN_SECRET` | Token 签名密钥，**至少 24 位** | `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6` |
| `ORIONSTACK_TEST_USER_PASSWORD` | 测试用户密码，**不能使用默认值** | `myStr0ng!Test1` |

> 生产模式（`ORIONSTACK_APP_MODE=prod`）启动时会拒绝默认密码和短密钥，直接报错退出。

### 可选配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ORIONSTACK_HTTP_PORT` | `8080` | 前端对外端口 |
| `ORIONSTACK_CORS_ORIGINS` | `http://localhost:8080` | CORS 允许的源（逗号分隔） |
| `ORIONSTACK_LOG_LEVEL` | `INFO` | 日志级别：DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `ORIONSTACK_ACCESS_LOG_ENABLED` | `true` | 是否启用访问日志 |
| `ORIONSTACK_ADMIN_USERNAME` | `admin` | 管理员用户名 |
| `ORIONSTACK_ADMIN_TOKEN_TTL_SECONDS` | `28800` | Token 有效期（秒），默认 8 小时 |
| `ORIONSTACK_TEST_USER_USERNAME` | `test` | 测试用户用户名 |
| `ORIONSTACK_ENABLE_QUERY_PLANNER` | `true` | 启用查询规划器 |
| `ORIONSTACK_ENABLE_FAST_TRACK` | `true` | 启用快速通道 |
| `ORIONSTACK_DYNAMIC_QUERY_ADAPTER` | `mock` | 动态查询适配器（mock/odoo） |
| `ORIONSTACK_PLANNER_PROVIDER` | `local` | 规划器提供者（local/openai_compatible） |
| `ORIONSTACK_PLANNER_API_KEY` | 空 | 规划器 API 密钥 |
| `ORIONSTACK_EXTRACTION_API_KEY` | 空 | 提取 API 密钥 |
| `DASHSCOPE_API_KEY` | 空 | 通义千问 API 密钥（fallback） |
| `ORIONSTACK_ES_JAVA_OPTS` | `-Xms512m -Xmx512m` | Elasticsearch JVM 堆内存 |

### LLM 提供者配置

OrionStack 支持多种 LLM 提供者组合：

**纯本地模式（不需要 API 密钥）：**
```env
ORIONSTACK_PLANNER_PROVIDER=local
ORIONSTACK_DYNAMIC_QUERY_ADAPTER=mock
```

**通义千问（Qwen）模式：**
```env
ORIONSTACK_PLANNER_PROVIDER=openai_compatible
ORIONSTACK_PLANNER_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
ORIONSTACK_PLANNER_API_MODEL=qwen-plus
ORIONSTACK_PLANNER_API_KEY=<your-key>
ORIONSTACK_EXTRACTION_PROVIDER=openai_compatible
ORIONSTACK_EXTRACTION_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
ORIONSTACK_EXTRACTION_API_MODEL=qwen-plus
ORIONSTACK_EXTRACTION_API_KEY=<your-key>
```

**Ollama 本地模式：**
```env
ORIONSTACK_PLANNER_PROVIDER=ollama
ORIONSTACK_OLLAMA_URL=http://localhost:11434
ORIONSTACK_PLANNER_MODEL=gemma3:1b
```

---

## 3. 架构说明

### 网络拓扑

```
                    ┌──────────────────────────┐
                    │  用户浏览器               │
                    └────────────┬─────────────┘
                                 │ :8080
                    ┌────────────▼─────────────┐
                    │  frontend (Nginx)        │
                    │  - SPA 静态文件           │
                    │  - /api/* → backend:8000  │
                    │  - /healthz → backend     │
                    │  - /readyz → backend      │
                    └────────────┬─────────────┘
                                 │ :8000
                    ┌────────────▼─────────────┐
                    │  backend (FastAPI)        │
                    │  - 问答 API               │
                    │  - 管理员 API              │
                    │  - 健康检查                │
                    └────────────┬─────────────┘
                                 │ :9200
                    ┌────────────▼─────────────┐
                    │  elasticsearch           │
                    │  - 中文 IK 分词索引        │
                    └──────────────────────────┘
```

### 数据持久化

Docker Compose 使用命名卷持久化数据：

| 卷名 | 挂载路径 | 内容 |
|------|----------|------|
| `es_data` | ES 数据目录 | Elasticsearch 索引 |
| `backend_chat_records` | `/app/backend/app/storage/chat_records` | 聊天记录 |
| `backend_feedback` | `/app/backend/app/storage/feedback` | 用户反馈 |
| `backend_retrieval_traces` | `/app/backend/app/storage/retrieval_traces` | 检索追踪 |
| `backend_hard_cases` | `/app/backend/app/storage/hard_cases` | 硬案例 |
| `backend_documents` | `/app/backend/app/storage/documents` | 文档 |
| `backend_chunks` | `/app/backend/app/storage/chunks` | 文档块 |
| `backend_uploads` | `/app/backend/app/storage/uploads` | 上传文件 |
| `backend_source_records` | `/app/backend/app/storage/source_records` | 源记录 |
| `backend_extraction_candidates` | `/app/backend/app/storage/extraction_candidates` | 提取候选 |
| `backend_action_links` | `/app/backend/app/storage/action_links` | 动作链接 |
| `backend_dynamic_queries` | `/app/backend/app/storage/dynamic_queries` | 动态查询 |

---

## 4. 常用运维命令

```bash
# 查看服务状态
docker compose --env-file .env.prod -f docker-compose.prod.yml ps

# 查看后端日志
docker compose --env-file .env.prod -f docker-compose.prod.yml logs backend

# 查看前端日志
docker compose --env-file .env.prod -f docker-compose.prod.yml logs frontend

# 重启后端（不影响数据）
docker compose --env-file .env.prod -f docker-compose.prod.yml restart backend

# 重新构建并启动
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build

# 停止所有服务
docker compose --env-file .env.prod -f docker-compose.prod.yml down

# 停止并删除数据卷（危险！会清除所有数据）
docker compose --env-file .env.prod -f docker-compose.prod.yml down -v
```

### 健康检查

```bash
# 存活检查（进程是否在运行）
curl http://localhost:8080/healthz

# 就绪检查（服务是否完全可用）
curl http://localhost:8080/readyz
```

`/readyz` 返回示例：
```json
{
  "status": "ready",
  "app_name": "OrionStack Demo",
  "app_version": "0.3.34",
  "app_mode": "prod",
  "search_backend": "elasticsearch",
  "config": {
    "production_safe": true,
    "errors": []
  },
  "elasticsearch": {
    "enabled": true,
    "index_name": "knowledge_units_v1",
    "indexed_count": 42,
    "indexing_error": null,
    "errors": []
  }
}
```

---

## 5. 安全注意事项

### 生产环境必须配置

- **管理员密码**：不能使用 `admin`、`password`、`changeme`、`test` 或空密码
- **测试用户密码**：同上，不能使用不安全的默认值
- **Token 密钥**：不能使用 `orionstack-dev-secret` 或 `change-this-in-production`，且至少 24 位
- 以上检查在 `ORIONSTACK_APP_MODE=prod` 时由后端自动执行，不合规将直接拒绝启动

### 日志安全

- 访问日志不记录请求体、密码和 Bearer Token
- Compose 配置验证时自动将 API 密钥置空

### 网络安全

- 对外只暴露前端端口（默认 8080）
- 后端和 Elasticsearch 只在 Docker 内部网络可达
- 建议 HTTPS 部署（在 Nginx 前面加反向代理或负载均衡器）

---

## 6. 相关文件索引

| 文件 | 说明 |
|------|------|
| `docker-compose.prod.yml` | 生产 Docker Compose 配置 |
| `docker/backend.Dockerfile` | 后端镜像构建文件 |
| `docker/frontend.Dockerfile` | 前端镜像构建文件 |
| `docker/backend-entrypoint.sh` | 后端启动脚本（默认数据初始化） |
| `docker/nginx/orionstack.conf` | Nginx 配置 |
| `docker/elasticsearch/` | Elasticsearch + IK 镜像构建 |
| `.env.prod.example` | 生产环境变量模板 |
| `backend/app/config/settings.py` | 后端配置类（含安全检查） |