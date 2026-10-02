# M1 核心基础与联调入口

更新日期：2026-10-02。以根目录《OrionStack — DB + Vector + JEV 检索架构设计.md》为准。

本阶段实现单 PostgreSQL + pgvector schema、显式迁移入口、统一证据与边界契约，以及 Jev/DeepSeek 客户端。现有 `/api/chat/ask` 仍运行原本地链路；四个新 API 尚未注册，embedding 和数据库检索将在 M2 接入。

## 环境配置

连接及凭据只从进程环境读取，沿用 `.env` 加载且 `override=False`；进程已有值优先。代码没有密钥默认值，也不把旧 provider 的 key 当作新服务 key。

| 环境变量 | 用途 | 默认值 |
| --- | --- | --- |
| `ORIONSTACK_DATABASE_URL` | 单一 PostgreSQL 连接串 | 无，实际迁移时必需 |
| `TYPESAFE_API_KEY` | TypeSafe Jev Bearer key | 无 |
| `DEEPSEEK_API_KEY` | DeepSeek Bearer key | 无 |
| `ORIONSTACK_JEV_API_BASE` | Jev 服务地址 | `https://api.typesafe.ai/v1` |
| `ORIONSTACK_JEV_MODEL` | Jev 固定版本 | `jev-1.13.0` |
| `ORIONSTACK_DEEPSEEK_API_BASE` | DeepSeek 服务地址 | `https://api.deepseek.com` |
| `ORIONSTACK_DEEPSEEK_MODEL` | 答案模型 | `deepseek-flash` |
| `ORIONSTACK_CORE_PROVIDER_TIMEOUT_SECONDS` | 每次模型调用超时 | `30` |
| `ORIONSTACK_DATABASE_CONNECT_TIMEOUT_SECONDS` | 数据库连接超时 | `5` |

依赖已加入 `pyproject.toml` 与 `uv.lock`，先运行 `uv sync`。生产 Compose 传入上述环境变量；构建上下文排除实际 `.env` 文件。配置检查仅显示是否设置，不输出值。

```powershell
.venv\Scripts\python.exe scripts/check-core-providers.py
```

## 数据模型与迁移

同一连接包含 `core`、`business`、`retrieval`、`integration` schema。来源、文档和知识单元保留稳定 ID 及版本，跨表使用含 tenant 的复合外键。chunk 引用文档版本，文档引用来源版本；实体与文档通过关联表连接。实体目录不替代后续的有确定字段的领域业务表。

文件和文本分别计算完整 SHA-256；旧短 hash 保存在 metadata。相同内容不能合并不同来源、租户或权限。原内容不进行隐式换行/空白规范化。证据快照表用于后续保存一次回答实际采用的内容和出处。

chunk embedding 初始为空；一旦写入，模型、维度和内容 hash 必须完整且与当前 chunk 一致。`vector` 暂不固定维度，待 embedding 模型确定后建立对应索引，不能跨模型混用距离。[pgvector 官方说明](https://github.com/pgvector/pgvector)

默认迁移命令只读取文件并生成预览，不连接数据库、不修改 JSONL：

```powershell
.venv\Scripts\python.exe scripts/migrate-postgres.py
.venv\Scripts\python.exe scripts/migrate-postgres.py --schema-only
```

在配置好数据库、确认预览没有错误后，显式执行：

```powershell
.venv\Scripts\python.exe scripts/migrate-postgres.py --schema-only --apply
.venv\Scripts\python.exe scripts/migrate-postgres.py --apply
```

目标数据库需已安装 pgvector 扩展文件，迁移角色需具备建 schema/table 和 `CREATE EXTENSION vector` 的权限；也可由 DBA 预先创建扩展。应用启动不自动迁移。`--apply` 的 schema 与数据导入在同一事务中提交，任何错误回滚；已提交的变更需要数据库备份或单独迁移恢复，脚本不提供破坏性自动回退。

迁移用 advisory lock 串行化，记录脚本校验和并拒绝已执行脚本被改写。相同快照重复导入返回 `duplicate`；相同版本 ID 已存在但内容或状态不同则拒绝，不能覆盖较新的数据。未来运行时更新和撤销由生命周期服务处理。

预览保留 legacy `unit_id`，兼容旧 `id`，历史抽取 JSONL 同一 canonical ID 取最后一条，避免恢复已撤销的旧版本。上传文件按 basename 映射到选定 storage 的 `uploads`，解析路径必须仍在 storage 根目录内；缺失文件、跨租户引用、孤立 chunk、来源版本不匹配和非法状态都阻断整批导入。

旧文档/FAQ 缺少 scope 时继承来源的 scope，chunk 缺少 scope 时继承文档范围。后续检索需同时检查来源、文档、chunk 的权限与生命周期，任一受限或撤销条件都不能被较宽的子对象 scope 绕过。

`--storage-root` 可指向恢复后的 storage；`--tenant-id` 仅为缺失 tenant 的旧记录提供默认值，已有 tenant 不改写。`--no-seed` 用于只迁移实际上传/抽取记录，不纳入内置 JSON/Markdown FAQ。

当前真实存储预览发现 5 个文档、94 个 chunk 和 99 条可转换 FAQ；另有两条有效抽取 FAQ 引用了缺失来源（原 JSONL 第 6、7 行）。因此当前整批导入被阻断，原文件保持原样。应先恢复真实来源或通过明确的数据修复流程处理这些记录，再重新预览；不填充虚假来源，也不静默跳过。

## 模型客户端与证据边界

Jev 使用 `/v1/systemone`，校验问题与答案键、Choice 选项、概率分布、Score 等级和加权分数，以及 Noul 的范围。Score 是按等级加权的值，不是统一的 0–1 概率。[TypeSafe API](https://docs.typesafe.ai/api)

`decide()` 返回 structured/vector/both；`judge_evidence()` 分别判断候选的 relevance/support；`sufficiency()` 评估选定证据集合。输入预算和候选批量有上限，错误输出、超时、HTTP 错误和重定向会成为明确的 provider error，不泄露响应内容或凭据。路由阈值、中文质量评测和检索降级策略属于 M3。

DeepSeek 使用 `/chat/completions` 的 JSON 输出模式，只生成状态、答案和 evidence ID 列表；当前默认模型与调用参数来自官方文档，可通过环境变量覆盖。[DeepSeek API](https://api-docs.deepseek.com/api/create-chat-completion/)

模型边界再次检查 tenant/scope，拒绝重复或伪造 evidence ID、无引用的有据回答、模型补写来源字段和截断输出；引用元数据从后端证据对象还原。没有可访问证据时直接返回证据不足，不调用模型。此阶段验证的是证据身份与元数据绑定；断言语义支持、精确值比对及回答前的来源撤销复查仍需 M4 完成，不能将身份检查称为完整的语义核验。

默认检查不调用外部服务。以下命令会使用虚构测试材料发起少量真实请求：

```powershell
.venv\Scripts\python.exe scripts/check-core-providers.py --live-jev
.venv\Scripts\python.exe scripts/check-core-providers.py --live-deepseek
```

2026-10-02 已验证 Jev 真实路由请求，返回 `jev-1.13.0 / structured`，用量 416 input tokens、38 output tokens；这验证 API 契约，不代表中文检索质量已验收。执行环境尚未读到 `DEEPSEEK_API_KEY` 和 `ORIONSTACK_DATABASE_URL`，DeepSeek 与 PostgreSQL 的真实联调未完成。SQL 已通过 PostgreSQL 语法解析器，实际扩展、外键和向量约束仍须在目标 PostgreSQL 上验证。

## 后续验收目标

1. 配置隔离的 PostgreSQL + pgvector 环境，验证 schema、复合外键、embedding 约束、事务回滚和重复迁移；处理上述来源缺失后核对导入结果。
2. M2 实现参数化精确查询、embedding 入库与 pgvector 召回，将租户/权限/生命周期/模型版本约束放入 SQL；实现只读 entities 与 query 数据链路。
3. M3 把现有 Jev 客户端接入检索编排并标定中文决策/排序阈值；M4 接入 DeepSeek 并完成语义引用核验、撤销复查和 trace。
4. Integration Layer 独立实现动作/事件受理、权限、幂等与适配契约；Knowledge/Decision 层不导入 n8n、workflow SDK 或连接器。

代码入口：`backend/app/config/core_settings.py`、`backend/app/knowledge/`、`backend/app/decision/`、`backend/app/integration/contracts.py`。运行时四接口语义继续以 [OpenAPI 草案](integration_boundary.openapi.json) 为准。
