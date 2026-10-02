# OrionStack Wiki

OrionStack 使用教程和运维文档。

## 文档索引

| 文档 | 说明 |
|------|------|
| [认证与授权](auth-roles.md) | 角色（admin/user）、Token 机制、API 权限、前端路由守卫 |
| [发布 CI/CD](release-ci-cd.md) | 发布检查、版本发布、GitHub Actions CI 流程说明 |
| [生产部署](deployment.md) | Docker Compose 部署、环境变量配置、运维命令 |
| [备份与恢复](backup-restore.md) | 数据备份脚本、恢复流程、Docker 卷备份 |
| [健康检查端点](health-endpoints.md) | /healthz 和 /readyz 说明、就绪条件、运维场景 |

## 快速开始

### 本地开发

```bash
# 安装依赖
cd backend && pip install -e .

# 启动后端（开发模式）
python -m uvicorn backend.main:app --reload

# 启动前端（开发模式）
cd frontend && npm run dev
```

### 生产部署

```bash
cp .env.prod.example .env.prod
# 编辑 .env.prod 设置密码和密钥
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

详见 [生产部署](deployment.md)。

### 默认账号

| 角色 | 用户名 | 密码 | 权限 |
|------|--------|------|------|
| admin | `admin` | `admin` | 全部（含管理页面） |
| user | `test` | `test` | 问答、文档、反馈 |

> 生产环境必须修改默认密码！

### 发布新版本

```bash
# 1. 更新 CHANGELOG.md
# 2. 运行发布检查
python scripts/release-check.py
# 3. 执行发布
python scripts/git-release.py --version x.y.z
```

详见 [发布 CI/CD](release-ci-cd.md)。