# OrionStack 运行手册（Runbook）

本文档用于固化本项目的日常运行、测试与数据库迁移流程。

## 1. 环境约定

- Python 环境：使用项目内 `uv` 虚拟环境 `.venv`
- 依赖安装：使用 `uv add`，不要装到系统默认 Python
- 数据库：
  - 开发环境：PostgreSQL（`backend/config/database.local.yaml`）
  - 测试环境：SQLite（`backend/config/database.test.yaml`）

## 2. 首次准备

在仓库根目录执行：

```powershell
# 如果 .venv 不存在
uv venv .venv --python D:\SDE\Python\Python314\python.exe
```

如需安装/补装依赖：

```powershell
uv add fastapi uvicorn pydantic python-multipart pytest sqlalchemy psycopg[binary] pyyaml alembic httpx pypdf python-docx
```

## 3. PostgreSQL 准备

确保本地存在数据库 `orionstack`。如果不存在，可执行：

```powershell
@'
from psycopg import connect
with connect(host="127.0.0.1", port=5432, user="postgres", password="postgres", dbname="postgres", autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("CREATE DATABASE orionstack")
print("OK")
'@ | .\.venv\Scripts\python.exe -
```

本地数据库连接配置文件：

- `backend/config/database.local.yaml`
- 模板：`backend/config/database.local.yaml.example`
- 问答阈值可在 YAML 中配置：`qa.min_retrieval_score`

## 4. 启动后端

在仓库根目录执行：

```powershell
$env:ORIONSTACK_DB_CONFIG="D:\workspace\python\orionstack\backend\config\database.local.yaml"
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload
```

如需指定本地 Ollama（默认 `http://127.0.0.1:11434` + `gemma3:1b`）：

```powershell
$env:ORIONSTACK_OLLAMA_BASE_URL="http://127.0.0.1:11434"
$env:ORIONSTACK_OLLAMA_MODEL="gemma3:1b"
```

如需指定 embedding 服务（默认优先走 Ollama `/api/embed`，失败时回退本地哈希向量）：

```powershell
$env:ORIONSTACK_EMBEDDING_PROVIDER="ollama"
$env:ORIONSTACK_EMBEDDING_MODEL="bge-m3"
$env:ORIONSTACK_EMBEDDING_BATCH_SIZE="8"
```

如需指定 rerank 行为：

```powershell
$env:ORIONSTACK_RERANK_PROVIDER="auto"
$env:ORIONSTACK_RERANK_MODEL="gemma3:1b"
```

说明：

- `auto`：优先尝试 Ollama 模型重排，失败时回退规则重排
- `lexical`：只用本地规则重排
- `ollama`：强制要求 Ollama 模型重排

如需调整低置信度保护阈值（越高越保守，越容易触发“建议补充文档”）：

```powershell
$env:ORIONSTACK_QA_MIN_SCORE="0.1"
```

也可在 `backend/config/database.local.yaml` 中配置：

```yaml
qa:
  min_retrieval_score: 0.1
```

建议：

- `0.05`：更偏向“尽量回答”，可能增加幻觉风险
- `0.10`：默认平衡值
- `0.20`：更偏向“谨慎拒答”，适合高准确性场景

如需强制关闭 `pgvector`、只走可移植的内联向量存储：

```powershell
$env:ORIONSTACK_VECTOR_BACKEND="inline"
```

默认值是 `auto`：

- PostgreSQL 且已完成 `pgvector` 迁移时，优先使用 `pgvector` 检索
- SQLite 或未建 `pgvector` 后端表时，自动回退 `inline`

启动前请确保已执行：

```powershell
cd backend
$env:ORIONSTACK_DB_CONFIG="D:\workspace\python\orionstack\backend\config\database.local.yaml"
..\.venv\Scripts\python.exe -m alembic upgrade head
```

说明：应用启动不会自动建表，表结构只由 Alembic 管理。

健康检查：

```powershell
curl http://127.0.0.1:8000/healthz
```

### 4.1 一键联调（前后端同时启动）

在仓库根目录执行：

```powershell
.\scripts\dev-up.ps1
```

停止联调进程：

```powershell
.\scripts\dev-down.ps1
```

说明：

- 启动脚本会拉起后端 `8000` 与前端 `5173`，并把 PID 与日志写入 `.runtime/`
- 若已有旧进程，使用 `.\scripts\dev-up.ps1 -Restart` 重新拉起
- 后端优先使用 `.venv\Scripts\python.exe` 启动；若不存在则回退 `uv run`
- 若本机热重载权限受限，可用 `.\scripts\dev-up.ps1 -NoReload`

## 5. 测试运行

测试默认使用 `backend/config/database.test.yaml`（SQLite）：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 5.1 文档上传格式

当前支持：

- `txt`
- `md`
- `pdf`
- `docx`

说明：

- `txt/md` 直接解析
- `pdf` 依赖 `pypdf`
- `docx` 依赖 `python-docx`
- 如果缺少解析依赖，上传接口会返回明确错误而不是静默写入乱码
- 上传成功后会先返回 `queued` 或 `indexing`，真正的切块与向量化在后台线程里完成
- 可通过 `/api/v1/documents/{document_id}/index-job` 或 `/api/v1/index-jobs/{job_id}` 查询最新索引任务详情
- 可通过 `/api/v1/index-jobs/{job_id}/stream` 订阅索引任务的 SSE 实时状态流
- 文档状态会保持在 `queued/indexing/indexed/failed` 这些用户态；更细的 `chunking/embedding/persisting/syncing` 只出现在索引任务里
- 索引任务还会返回 `error_code`，用于区分 `chunk_generation_failed`、`embedding_generation_failed`、`vector_sync_failed` 等具体失败类型

## 6. Alembic 迁移

在 `backend` 目录执行：

```powershell
cd backend
```

设置数据库配置路径（PostgreSQL）：

```powershell
$env:ORIONSTACK_DB_CONFIG="D:\workspace\python\orionstack\backend\config\database.local.yaml"
```

常用命令：

```powershell
# 生成迁移
..\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "change_name"

# 应用迁移
..\.venv\Scripts\python.exe -m alembic upgrade head

# 查看当前版本
..\.venv\Scripts\python.exe -m alembic current
```

说明：

- 新增了 `document_chunks` 与 `chunk_embeddings` 两张表，用于将“切块”和“向量存储”解耦
- 新增了 `pgvector_chunk_embeddings` 作为 PostgreSQL 专用向量加速层；逻辑真源仍在 `chunk_embeddings`
- 升级后，历史文档建议执行一次 `POST /api/v1/documents/{document_id}/reindex`，把新表补齐
- `CREATE EXTENSION IF NOT EXISTS vector` 已在 PostgreSQL Alembic 迁移里处理
- 问答接口里的 `use_rerank` 现在已生效，默认会在召回候选上做一次混合重排

## 6.1 迁移回滚（最小操作集）

回滚一个版本（推荐优先使用）：

```powershell
cd backend
$env:ORIONSTACK_DB_CONFIG="D:\workspace\python\orionstack\backend\config\database.local.yaml"
..\.venv\Scripts\python.exe -m alembic downgrade -1
```

回滚到指定版本：

```powershell
cd backend
$env:ORIONSTACK_DB_CONFIG="D:\workspace\python\orionstack\backend\config\database.local.yaml"
..\.venv\Scripts\python.exe -m alembic downgrade <revision_id>
```

仅修正版本号（不执行 DDL，谨慎使用）：

```powershell
cd backend
$env:ORIONSTACK_DB_CONFIG="D:\workspace\python\orionstack\backend\config\database.local.yaml"
..\.venv\Scripts\python.exe -m alembic stamp <revision_id>
```

## 6.2 迁移升降级冒烟（推荐每次大改后执行）

在 `backend` 目录执行：

```powershell
cd backend
$env:ORIONSTACK_DB_CONFIG="D:\workspace\python\orionstack\backend\config\database.local.yaml"

# 记录当前版本（应看到 head）
..\.venv\Scripts\python.exe -m alembic current

# 回滚一个版本再升回 head，验证 upgrade/downgrade 均可执行
..\.venv\Scripts\python.exe -m alembic downgrade -1
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m alembic current
```

## 7. 故障排查

1. `psql` 命令不可用：
- 不影响项目运行。项目使用 `psycopg` 直连，不依赖 `psqlODBC`。

2. `database "orionstack" does not exist`：
- 先创建数据库，再执行应用启动或迁移。

3. `DuplicateTable`（迁移报表已存在）：
- 说明历史曾用 `create_all` 建过表，可先 `alembic stamp head` 对齐版本。

4. `uv` 缓存目录权限问题：
- 设置 `UV_CACHE_DIR` 到项目内目录再执行。

## 8. Step 3（权限与治理）最小使用说明

当前最小用户隔离方式：

- 通过请求头 `X-User-Id` 传入用户标识
- 未传时默认使用 `demo-user`

示例：

```powershell
curl -H "X-User-Id: user-a" http://127.0.0.1:8000/api/v1/sessions
curl -H "X-User-Id: user-a" "http://127.0.0.1:8000/api/v1/audit/logs?limit=20&offset=0"
```

审计日志覆盖的关键事件（最小版）：

- `session_created`
- `document_uploaded` / `document_deleted` / `document_reindexed`
- `qa_asked` / `qa_ask_failed` / `qa_stream_failed`
- `feedback_submitted`

### 8.1 Step 3 回归最小清单（建议提交前执行）

在仓库根目录执行：

```powershell
# 使用项目内 uv 缓存目录，避免系统目录权限问题
$env:UV_CACHE_DIR="D:\workspace\python\orionstack\.uv-cache"
uv run pytest backend/tests -q
```

重点关注以下回归点：

- 多用户隔离：`sessions/documents/qa/feedback/audit`
- 问答失败回退契约：`/api/v1/qa/ask` 与 `/api/v1/qa/ask-stream`
- Alembic：`upgrade -> downgrade -1 -> upgrade head`
