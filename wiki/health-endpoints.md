# 健康检查端点说明

## 概述

OrionStack 提供两个健康检查端点：

| 端点 | 用途 | 检查内容 |
|------|------|----------|
| `GET /healthz` | 存活检查（Liveness） | 进程是否在运行 |
| `GET /readyz` | 就绪检查（Readiness） | 进程 + 配置安全 + Elasticsearch |

---

## 1. `/healthz` — 存活检查

最简单的健康检查，只确认进程在运行。

### 请求

```http
GET /healthz
```

### 响应

```json
{
  "status": "ok"
}
```

始终返回 200，除非进程崩溃。

### 使用场景

- Docker/容器编排判断进程是否存活
- 负载均衡器剔除已崩溃的实例

---

## 2. `/readyz` — 就绪检查

完整的服务就绪检查，确认后端能正常处理请求。

### 请求

```http
GET /readyz
```

### 成功响应（200）

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

### 失败响应（503）

当配置不安全或 Elasticsearch 索引失败时返回 503：

```json
{
  "status": "not_ready",
  "app_name": "OrionStack Demo",
  "app_version": "0.3.34",
  "app_mode": "prod",
  "search_backend": "elasticsearch",
  "config": {
    "production_safe": false,
    "errors": [
      "ORIONSTACK_ADMIN_PASSWORD must be changed for prod mode",
      "ORIONSTACK_ADMIN_TOKEN_SECRET must be at least 24 characters in prod mode"
    ]
  },
  "elasticsearch": {
    "enabled": true,
    "index_name": "knowledge_units_v1",
    "indexed_count": 0,
    "indexing_error": "Connection refused",
    "errors": ["Connection refused"]
  }
}
```

### 就绪条件

服务返回 200（`ready`）必须满足：

1. **配置安全** — 生产模式下没有配置错误（无默认密码、无短密钥）
2. **Elasticsearch 可用** — 如果搜索后端是 Elasticsearch，索引必须成功创建

任何一项失败都会导致 503（`not_ready`）。

---

## 3. Docker 健康检查配置

生产 Docker Compose 使用 `/readyz` 作为健康检查：

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2)"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 30s
```

### Nginx 代理

Nginx 配置将两个端点都代理到后端：

```nginx
location /healthz {
    proxy_pass http://backend:8000;
    # ... proxy headers
}

location /readyz {
    proxy_pass http://backend:8000;
    # ... proxy headers
}
```

---

## 4. 各模式下的行为

### Demo/Dev 模式

| 端点 | 行为 |
|------|------|
| `/healthz` | 始终 200 |
| `/readyz` | 配置安全检查不强制执行；Elasticsearch 失败则 503 |

### Prod 模式

| 端点 | 行为 |
|------|------|
| `/healthz` | 始终 200 |
| `/readyz` | 配置安全检查强制执行（默认密码/短密钥 → 503）；Elasticsearch 失败 → 503 |

---

## 5. 运维场景

### 检查服务是否完全就绪

```bash
curl -s http://localhost:8080/readyz | python -m json.tool
```

### 只检查进程存活

```bash
curl -s http://localhost:8080/healthz
```

### 在部署脚本中等待就绪

```bash
# 等待服务就绪（最多 60 次，每次 2 秒）
for i in $(seq 1 60); do
  if curl -sf http://localhost:8080/readyz > /dev/null; then
    echo "Service is ready"
    exit 0
  fi
  sleep 2
done
echo "Service failed to become ready"
exit 1
```

---

## 6. 相关文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/api/routes/health.py` | 健康检查端点实现 |
| `backend/app/config/settings.py` | `production_config_errors()` 安全检查 |
| `backend/main.py` | lifespan 中的 Elasticsearch 索引状态 |
| `docker-compose.prod.yml` | Docker 健康检查配置 |
| `docker/nginx/orionstack.conf` | Nginx 代理 /healthz 和 /readyz |