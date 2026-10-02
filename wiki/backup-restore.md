# 备份与恢复指南

## 概述

OrionStack 提供两个脚本用于本地存储数据的备份和恢复：

| 脚本 | 用途 |
|------|------|
| `scripts/backup-storage.py` | 创建 tar.gz 备份包 |
| `scripts/restore-storage.py` | 从备份包恢复数据 |

备份覆盖 15 个存储目录，每个备份包含 manifest.json（含文件 SHA-256 校验）。当前脚本覆盖文件存储；下一版本 PostgreSQL 数据需另行配置数据库备份与恢复。

---

## 1. 备份 — `backup-storage.py`

### 功能

- 扫描指定存储目录下的所有文件
- 计算每个文件的 SHA-256 哈希值
- 打包为 `orionstack-storage-YYYYMMDDTHHMMSSZ.tar.gz`
- 内含 `manifest.json` 记录文件列表、大小、哈希

### 存储目录

备份包含以下目录（均在 `backend/app/storage/` 下）：

| 目录 | 内容 |
|------|------|
| `action_links` | 动作链接 |
| `chat_records` | 聊天记录 |
| `cleanup_tasks` | 生命周期清理任务 |
| `chunks` | 文档块 |
| `documents` | 原始文档 |
| `dynamic_queries` | 动态查询 |
| `extraction_candidates` | 提取候选 |
| `extracted_faqs` | 已审核发布的 FAQ |
| `extraction_tasks` | 抽取任务 |
| `feedback` | 用户反馈 |
| `hard_cases` | 硬案例 |
| `import_batches` | 导入批次 |
| `retrieval_traces` | 检索追踪 |
| `source_records` | 源记录 |
| `uploads` | 上传文件 |

### 用法

```bash
# 标准备份（输出到项目根目录下的 backups/）
python scripts/backup-storage.py

# 检查备份是否可行（不实际创建文件）
python scripts/backup-storage.py --check-only

# 排除上传文件（减小备份体积）
python scripts/backup-storage.py --no-uploads

# 自定义存储根目录
python scripts/backup-storage.py --storage-root /path/to/storage

# 自定义输出目录
python scripts/backup-storage.py --output-dir /path/to/backups

# 组合使用
python scripts/backup-storage.py --no-uploads --output-dir ./my-backups
```

### 选项说明

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--storage-root` | `backend/app/storage/` | 存储根目录 |
| `--output-dir` | `backups/` | 备份文件输出目录 |
| `--no-uploads` | 否 | 排除 uploads 目录（大文件） |
| `--check-only` | 否 | 只检查不实际创建备份 |

### 输出示例

```
[orionstack] storage backup
[orionstack] storage root : D:\workspace\python\orionstack\backend\app\storage
[orionstack] output       : D:\workspace\python\orionstack\backups\orionstack-storage-20260505T170000Z.tar.gz
[orionstack] files        : 156
[orionstack] bytes        : 12582912
[orionstack] backup written: D:\workspace\python\orionstack\backups\orionstack-storage-20260505T170000Z.tar.gz
```

### 备份文件结构

```
orionstack-storage-20260505T170000Z.tar.gz
├── manifest.json                    # 备份元数据 + 文件哈希
└── storage/
    ├── action_links/
    │   └── *.jsonl
    ├── chat_records/
    │   └── *.jsonl
    ├── ...（其他存储目录）
    └── uploads/
        └── *（上传文件）
```

---

## 2. 恢复 — `restore-storage.py`

### 功能

- 从 tar.gz 备份包恢复数据
- 支持预览模式（`--what-if`）查看将要恢复的文件
- 必须显式确认（`--confirm-restore`）才会实际写入
- 内置路径遍历防护（防止恶意备份包）
- 写入前核对 manifest 文件列表、大小和所有 SHA-256；预览也执行校验
- 拒绝归档链接、重复路径及非法路径；恢复目标必须位于指定 storage root 内
- 将 documents.jsonl 中上传文件路径重新定位到恢复目标的 uploads 目录
- 文件存在时显示 "overwrite"，不存在时显示 "create"

### 用法

```bash
# 预览恢复内容（推荐先执行！）
python scripts/restore-storage.py backups/orionstack-storage-20260505T170000Z.tar.gz --what-if

# 确认恢复
python scripts/restore-storage.py backups/orionstack-storage-20260505T170000Z.tar.gz --confirm-restore

# 自定义存储根目录
python scripts/restore-storage.py backup.tar.gz --storage-root /path/to/storage --what-if
```

### 选项说明

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `backup_path`（位置参数） | 无 | 备份 tar.gz 文件路径 |
| `--storage-root` | `backend/app/storage/` | 恢复目标目录 |
| `--what-if` | 否 | 预览模式，只显示将要恢复的文件 |
| `--confirm-restore` | 否 | 确认实际恢复（必须显式指定） |

> 恢复是破坏性操作！必须指定 `--what-if` 或 `--confirm-restore` 之一。

### 安全防护

恢复脚本会检查每个备份文件的路径：

- 拒绝以 `/` 或 `\` 开头的绝对路径
- 拒绝包含 `..` 的路径遍历攻击
- 只恢复 `storage/` 前缀的文件

---

## 3. 推荐备份策略

### 定期备份

```bash
# 每日备份（排除上传文件以节省空间）
python scripts/backup-storage.py --no-uploads

# 定期完整备份
python scripts/backup-storage.py
```

### 发布前备份

```bash
# 在发布新版本前备份
python scripts/backup-storage.py --check-only  # 先检查
python scripts/backup-storage.py               # 确认无误后备份
```

### 恢复流程

```bash
# 步骤 1：预览备份内容
python scripts/restore-storage.py backups/orionstack-storage-latest.tar.gz --what-if

# 步骤 2：确认预览内容正确后恢复
python scripts/restore-storage.py backups/orionstack-storage-latest.tar.gz --confirm-restore

# 步骤 3：验证恢复结果
# 启动服务后访问 http://localhost:8080/readyz 检查
```

### Docker 卷备份

使用生产 Compose 时，在后端停止写入后复制完整 storage 并在宿主机打包：

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml stop backend
docker compose --env-file .env.prod -f docker-compose.prod.yml cp backend:/app/backend/app/storage ./prod-storage-snapshot
python scripts/backup-storage.py --storage-root ./prod-storage-snapshot --output-dir backups
docker compose --env-file .env.prod -f docker-compose.prod.yml start backend
```

生产镜像不包含 scripts。恢复时用一次性 backend 容器挂载全部生产卷和宿主机恢复材料，并直接在容器的 storage 路径运行脚本。以下 `<仓库绝对路径>` 需替换为当前仓库路径，`<备份文件名>` 需替换为真实文件名：

```text
docker compose --env-file .env.prod -f docker-compose.prod.yml stop backend
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm --no-deps --entrypoint python -v "<仓库绝对路径>:/restore:ro" backend /restore/scripts/restore-storage.py /restore/backups/<备份文件名> --storage-root /app/backend/app/storage --what-if
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm --no-deps --entrypoint python -v "<仓库绝对路径>:/restore:ro" backend /restore/scripts/restore-storage.py /restore/backups/<备份文件名> --storage-root /app/backend/app/storage --confirm-restore
docker compose --env-file .env.prod -f docker-compose.prod.yml start backend
```

恢复前先备份当前目标数据，并停止所有 storage 写入者。恢复会覆盖包内同名文件，不会清除目标中包内没有的文件；需要精确恢复时应使用已准备好的空卷。不能把在 Windows 宿主机恢复后含本地路径的 documents.jsonl 原样拷入 Linux 容器。

---

## 4. 相关文件索引

| 文件 | 说明 |
|------|------|
| `scripts/backup-storage.py` | 备份脚本 |
| `scripts/restore-storage.py` | 恢复脚本 |
| `scripts/release-check.py` | 发布检查（包含备份干运行验证） |
| `backend/app/storage/` | 默认存储根目录 |
| `docker-compose.prod.yml` | 生产部署（命名卷定义） |
