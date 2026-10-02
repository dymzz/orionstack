# 发布 CI/CD 使用和流程说明

## 概述

OrionStack 的发布流程由三个核心组件构成：

| 组件 | 脚本/文件 | 用途 |
|------|-----------|------|
| 发布检查 | `scripts/release-check.py` | 发布前自动验证（测试、构建、配置） |
| 发布脚本 | `scripts/git-release.py` | 交互式版本发布（版本号、打标签、推送） |
| CI 流水线 | `.github/workflows/release-check.yml` | GitHub Actions 自动运行发布检查 |

---

## 1. 发布检查 — `release-check.py`

### 功能

发布检查脚本按顺序执行以下步骤：

1. **后端测试** — 运行 pytest 测试套件
2. **存储备份干运行** — 验证备份脚本能正常工作
3. **前端构建** — 运行 `npm run build` 确认前端无编译错误
4. **Compose 配置验证** — 验证 `docker-compose.prod.yml` 配置合法

### 用法

```bash
# 完整检查（运行全部后端测试）
python scripts/release-check.py

# 快速检查（只运行核心测试文件）
python scripts/release-check.py --quick

# 仅验证检查步骤定义是否正确（不实际执行）
python scripts/release-check.py --check-only

# 跳过特定步骤
python scripts/release-check.py --skip-backend
python scripts/release-check.py --skip-frontend
python scripts/release-check.py --skip-compose

# 组合使用
python scripts/release-check.py --quick --skip-compose
```

### 选项说明

| 选项 | 说明 |
|------|------|
| `--quick` | 快速模式，只运行 Phase 2 核心测试 + auth/settings 测试，而非全部后端测试 |
| `--skip-backend` | 跳过后端测试和备份干运行 |
| `--skip-frontend` | 跳过前端构建（需要 npm 可用） |
| `--skip-compose` | 跳过 Docker Compose 配置验证（需要 docker 可用） |
| `--check-only` | 仅打印将要执行的步骤，不实际运行 |

### 快速模式测试范围

快速模式（`--quick`）运行以下测试文件：

- `backend/tests/test_phase2_retrieval.py`
- `backend/tests/test_chat_flow.py`
- `backend/tests/test_phase2_trace.py`
- `backend/tests/test_phase2_hard_cases.py`
- `backend/tests/test_auth.py`
- `backend/tests/test_phase2_settings.py`

### Compose 配置验证的安全措施

验证 Compose 配置时，脚本会：

- 将所有 API 密钥环境变量置空，防止泄露到 CI 日志
- 使用 `.env.prod.example` 作为环境变量模板
- 隐藏 `docker compose config` 的输出内容

---

## 2. 发布脚本 — `git-release.py`

### 功能

交互式版本发布脚本，自动执行以下步骤：

1. 确认版本号（从 `pyproject.toml` 读取当前版本）
2. 运行 `release-check.py --quick`（可跳过）
3. 交互式确认发布
4. 更新 `pyproject.toml` 中的版本号
5. `git add --all` + `git commit` + `git tag` + `git push`

### 用法

```bash
# 交互式发布（提示输入版本号和提交信息）
python scripts/git-release.py

# 指定版本号和提交信息
python scripts/git-release.py --version 1.0.0 --commit-message "release 1.0.0"

# 跳过发布检查（不推荐）
python scripts/git-release.py --skip-release-check

# 仅验证不执行（干运行）
python scripts/git-release.py --check-only --version 1.0.0 --commit-message "test"

# 不推送到远程（本地打标签）
python scripts/git-release.py --skip-push

# 自定义标签前缀（默认 v）
python scripts/git-release.py --tag-prefix v --version 1.0.0

# 自定义远程名称（默认 origin）
python scripts/git-release.py --remote upstream --version 1.0.0
```

### 选项说明

| 选项 | 说明 |
|------|------|
| `--version` | 目标版本号（如 `1.0.0` 或 `1.0.0-rc1`），交互式提示时省略 |
| `--commit-message` | Git 提交信息 |
| `--tag-prefix` | Git 标签前缀，默认 `v`（生成 `v1.0.0` 格式标签） |
| `--remote` | Git 远程名称，默认 `origin` |
| `--skip-release-check` | 跳过发布检查直接发布（不推荐） |
| `--skip-push` | 不推送到远程，标签和提交保留在本地 |
| `--check-only` | 仅打印发布摘要，不执行任何操作 |

### 发布流程图

```
开始
  │
  ▼
读取 pyproject.toml 当前版本
  │
  ▼
确认目标版本号 ──→ 已存在？──→ 报错退出
  │
  ▼
运行 release-check.py --quick ──→ 失败？──→ 报错退出
  │
  ▼
打印发布摘要
  │
  ▼
交互确认 (y/N) ──→ 否 ──→ 退出
  │
  ▼
更新 pyproject.toml 版本号
  │
  ▼
git add --all
  │
  ▼
git commit -m <message>
  │
  ▼
git tag -a <tag> -m "release <tag>"
  │
  ▼
git push origin <branch>
git push origin <tag>
  │
  ▼
完成
```

---

## 3. GitHub Actions CI — `release-check.yml`

### 触发条件

- **Pull Request**（所有分支）
- **Push** 到 `main` 或 `master` 分支

### 流水线步骤

```yaml
jobs:
  release-check:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - Checkout
      - Set up Python 3.14
      - Install Python dependencies (from pyproject.toml)
      - Set up Node.js 22
      - Install frontend dependencies (npm ci)
      - Run release-check.py (完整模式)
```

### 注意事项

- CI 运行的是**完整模式**（非 `--quick`），即运行全部后端测试
- Python 依赖从 `pyproject.toml` 的 `[project].dependencies` 安装
- 前端使用 `npm ci` 安装依赖（需要 `package-lock.json`）
- 如果需要 API 密钥的集成测试会跳过或使用 mock

---

## 4. 完整发布流程

### 推荐发布步骤

```
1. 更新 CHANGELOG.md（记录本次版本变更内容）
2. 运行发布检查：python scripts/release-check.py
3. 确认无错误后执行发布：python scripts/git-release.py
4. 确认 GitHub Actions CI 通过
5. 合并 PR（如适用）
```

### 示例：发布 v1.0.0

```bash
# 步骤 1：更新 CHANGELOG
# 编辑 CHANGELOG.md，在 Unreleased 下方添加：
# ## 1.0.0 - 2026-05-05
# ### Added
# - ...

# 步骤 2：运行完整发布检查
python scripts/release-check.py

# 步骤 3：执行发布
python scripts/git-release.py --version 1.0.0 --commit-message "release v1.0.0"
# 脚本会自动：
#   1. 运行 release-check.py --quick
#   2. 提示确认发布摘要
#   3. 更新 pyproject.toml 版本号
#   4. git add/commit/tag/push

# 步骤 4：确认 CI 通过
# 访问 GitHub Actions 页面确认 release-check workflow 全绿
```

### 快速修补发布

```bash
# 修补版本：快速检查 + 本地标签（不推送）
python scripts/release-check.py --quick
python scripts/git-release.py --version 1.0.1 --skip-push
# 手动推送
git push origin main v1.0.1
```

---

## 5. 常见问题

### Q: `release-check.py` 找不到 Python 或 npm？

脚本使用 `shutil.which()` 查找命令。Windows 上会额外查找 `.cmd` 和 `.exe` 后缀。确保：
- Python 在 PATH 中或项目有 `.venv/Scripts/python.exe`
- npm 在 PATH 中

### Q: CI 中 Docker Compose 配置验证失败？

检查 `.env.prod.example` 中的必需变量是否已填写模板值。CI 环境中所有 API 密钥会被置空，这是正常行为。

### Q: `git-release.py` 提示 "Tag already exists"？

版本标签已存在，需要换一个版本号或删除旧标签（`git tag -d vx.y.z` + `git push origin :refs/tags/vx.y.z`）。

### Q: 如何跳过发布检查直接发布？

```bash
python scripts/git-release.py --skip-release-check --version 1.0.0
```

**不推荐**，仅用于紧急情况。

### Q: 版本号有什么规则？

版本号必须符合语义化版本格式：`MAJOR.MINOR.PATCH`，可选预发布标识如 `1.0.0-rc1`。脚本会自动去掉 `v` 前缀（如果输入了的话）。

---

## 6. 相关文件索引

| 文件 | 说明 |
|------|------|
| `scripts/release-check.py` | 发布检查脚本 |
| `scripts/git-release.py` | 交互式版本发布脚本 |
| `.github/workflows/release-check.yml` | GitHub Actions CI 流水线 |
| `CHANGELOG.md` | 版本变更记录 |
| `pyproject.toml` | 项目版本号来源 |
| `docker-compose.prod.yml` | 生产 Compose 配置 |
| `.env.prod.example` | 生产环境变量模板 |
| `backend/app/storage/` | 本地存储目录（备份脚本的目标） |