# 认证与授权说明

## 概述

OrionStack 使用基于角色的 HMAC Bearer Token 认证机制，支持两种角色：

| 角色 | 权限 | 默认账号 |
|------|------|----------|
| `admin` | 全部 API（包括管理页面） | `admin` / `admin` |
| `user` | 问答、反馈、文档管理 | `test` / `test` |

### 认证流程

```
┌──────────┐    POST /api/auth/login     ┌──────────┐
│  前端     │ ──────────────────────────→  │  后端     │
│  /login   │    {username, password}       │  FastAPI  │
│           │                              │           │
│           │ ←──────────────────────────  │           │
│           │    {token, role, expires_in}  │           │
│           │                              │           │
│           │    GET /api/auth/me           │           │
│           │ ──────────────────────────→  │           │
│           │    Authorization: Bearer xxx │           │
│           │ ←──────────────────────────  │           │
│           │    {username, role}          │           │
└──────────┘                              └──────────┘
```

---

## 1. API 端点

### 登录

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your-password"
}
```

成功响应（200）：
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 28800,
  "username": "admin",
  "role": "admin"
}
```

失败响应（401）：
```json
{
  "detail": "Invalid username or password"
}
```

### 查询认证状态

```http
GET /api/auth/me
Authorization: Bearer <token>
```

成功响应（200）：
```json
{
  "authenticated": true,
  "username": "admin",
  "role": "admin"
}
```

### 登出

```http
POST /api/auth/logout
Authorization: Bearer <token>
```

成功响应（200）：
```json
{
  "status": "logged_out"
}
```

---

## 2. 受保护的 API 端点

### 需要管理员认证（仅 `admin` 角色）

| 端点前缀 | 说明 |
|----------|------|
| `POST /api/chat/ask` | 问答接口 |
| `POST /api/chat/feedback` | 反馈提交 |
| `GET /api/documents` | 文档列表 |
| `POST /api/documents/upload` | 文档上传 |
| `DELETE /api/documents/{id}` | 文档删除 |
| `GET /api/chat/records` | 聊天记录查询 |
| `GET /api/chat/feedback` | 反馈记录查询 |
| `GET /api/chat/traces/{id}` | 检索追踪查看 |
| `GET /api/chat/hard-cases` | 硬案例查看 |
| `/api/extraction/*` | 提取相关所有端点 |

### 公开端点（无需认证）

| 端点前缀 | 说明 |
|----------|------|
| `GET /api/action-links` | 动作链接查询 |
| `GET /api/dynamic-query` | 动态查询 |
| `GET /healthz` | 存活检查 |
| `GET /readyz` | 就绪检查 |

### 错误响应

| 状态码 | 含义 |
|--------|------|
| 401 | 未认证（缺少或无效的 Token） |
| 403 | 权限不足（非管理员访问仅限管理员的端点） |

---

## 3. 角色与 Token 机制

### Token 结构

Token 格式为 `<payload>.<signature>`，其中：

- `payload`：Base64url 编码的 JSON，包含 `sub`（用户名）、`role`（角色）、`iat`（签发时间）、`exp`（过期时间）
- `signature`：对 payload 使用 HMAC-SHA256 签名的 Base64url 编码

### 角色分配

系统内置两个账号，角色由配置决定：

| 环境变量 | 默认值 | 角色 |
|----------|--------|------|
| `ORIONSTACK_ADMIN_USERNAME` | `admin` | `admin` |
| `ORIONSTACK_ADMIN_PASSWORD` | `admin` | — |
| `ORIONSTACK_TEST_USER_USERNAME` | `test` | `user` |
| `ORIONSTACK_TEST_USER_PASSWORD` | `test` | — |

### 安全特性

- 使用 HMAC-SHA256 签名，密钥为 `ORIONSTACK_ADMIN_TOKEN_SECRET`
- 使用 `hmac.compare_digest()` 防止时序攻击
- Token 过期后自动失效
- 密码比较也使用 `hmac.compare_digest()`

### Token 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `ORIONSTACK_ADMIN_TOKEN_SECRET` | `orionstack-dev-secret` | Token 签名密钥（**生产环境必须修改，至少 24 位**） |
| `ORIONSTACK_ADMIN_TOKEN_TTL_SECONDS` | `28800` | Token 有效期（秒），默认 8 小时 |

---

## 4. 前端认证

### 登录页面

- 所有页面和 API 需要登录才可访问
- 登录页面 `/login` 输入用户名和密码
- 登录成功后 Token 和角色存储在 `localStorage`
- 自动跳转回之前尝试访问的页面

### 路由守卫

- 所有页面（含首页 `/`）需要认证
- `/admin/*` 路由额外需要 `admin` 角色
- 非 `admin` 用户访问 `/admin/*` 时重定向到首页 `/`
- 401 响应自动触发登出并清除 Token
- 403 响应由页面自行处理

### 导航栏

- 已登录用户显示：**问答**、**管理入口**（仅 admin）、**退出 username**
- 已登录普通用户显示：**问答**、**退出 username**

---

## 5. 生产环境安全

### 自动检查

生产模式（`ORIONSTACK_APP_MODE=prod`）启动时会检查：

- ❌ 拒绝默认管理员密码（`admin`、`password`、`changeme`、`test`、空密码）
- ❌ 拒绝默认测试用户密码（同上）
- ❌ 拒绝默认密钥（`orionstack-dev-secret`、`change-this-in-production`、空密钥）
- ❌ 拒绝短于 24 位的密钥

检查失败时后端直接报错退出。

### 日志安全

- 登录成功事件记录角色（不含密码）
- 登录失败事件记录用户名（不含密码）
- 访问日志不含请求体和 Bearer Token
- 登出事件记录用户名和角色

---

## 6. 常见问题

### Q: test 用户能做什么？

test 用户（`user` 角色）目前只能查询自身认证状态和登出。所有 Q&A、文档、记录管理功能都需要 `admin` 角色。

如需开通更多权限给 `user` 角色，可通过修改后端路由的 `dependencies=[Depends(require_user)]` 来实现。

### Q: 如何修改密码？

修改环境变量（如 `ORIONSTACK_ADMIN_PASSWORD` 或 `ORIONSTACK_TEST_USER_PASSWORD`）后重启服务。所有现有 Token 仍然有效直到过期。

### Q: 如何使所有 Token 失效？

修改 `ORIONSTACK_ADMIN_TOKEN_SECRET` 后重启服务。所有基于旧密钥签发的 Token 都将无效。

### Q: admin 用户和 test 用户使用同一个密钥吗？

是的，所有 Token 使用 `ORIONSTACK_ADMIN_TOKEN_SECRET` 签名。角色信息编码在 Token 的 `role` 字段中。

---

## 7. 相关文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/api/auth.py` | Token 创建/验证、`require_user`/`require_admin` 依赖 |
| `backend/app/api/routes/auth.py` | 认证 API 端点 |
| `backend/app/schemas/auth.py` | 认证请求/响应 Schema（含 `role` 字段） |
| `backend/app/config/settings.py` | 认证配置、`user_accounts` 属性、安全检查 |
| `frontend/src/services/auth.ts` | 前端认证服务（含角色状态） |
| `frontend/src/services/api.ts` | 前端 API 客户端（Bearer 头 + 401 处理 + `deleteJson`） |
| `frontend/src/pages/LoginPage.vue` | 登录页面 |
| `frontend/src/router.ts` | 全局路由守卫 + admin 角色检查 |
| `frontend/src/App.vue` | 导航栏（admin 角色条件显示） |