# 2.8 Planner LLM 接入计划（轮 3 详细）

> 承接 `docs/2_7_planner_upgrade_plan.md §2 轮 3`，把 "LLM provider 接入" 拆成 4 个可独立 review 的子轮。定位：**实现计划**。本文件**只覆盖 QwenApiProvider**；LlamaCppProvider 由后续独立文档承接。

---

## 1. 背景与硬约束回顾

- 项目核心验证目标：LLM 在中文 FAQ 场景下的 planner 能力（`2_6 §6.2`）
- 首发 provider：`QwenApiProvider`，用户已明确选择 Qwen API 先（2026-04-21）
- 架构位置：`QueryPlanner` 通过 `PlannerProvider` Protocol 分发（`2_7 §3.1` 已就绪）
- 硬约束：
  - LLM 异常**必须**在 `QueryPlanner` 层被捕获并降级到 `LocalRuleProvider`，**绝不**传播到 `ChatService`
  - 温度 0 + 缓存保证 trace 可重现
  - 降级策略**非 confidence-based**（LocalRule confidence 不可信）
  - 不修改 `PlannerOutput` schema

---

## 2. 子轮分解

### 轮 3.1：基础设施 + prompt 设计 🔄（本文件同步执行）

- `settings.py` 新增 Qwen API / 缓存 / 超时相关字段（惰性，默认值不触发任何 LLM 调用）
- 本文件 §3 / §4 固定 prompt 文本与 JSON schema 约束
- **完成标志**：pytest 全套仍 `132 passed, 9 xfailed, 0 failed`；新 settings 字段可从环境变量读取

### 轮 3.2：QwenApiProvider 实现 ⏸

- 新建 `backend/app/query/providers/` 包，落 `qwen_api_provider.py`
- 用 `httpx`（已在 pyproject）调 DashScope OpenAI-compatible 端点
- `QueryPlanner._create_provider` 扩 `"qwen_api"` 分支
- `QueryPlanner.plan()` 加 try/except + 进程缓存 + fallback 到 `LocalRuleProvider`
- **完成标志**：全套仍全绿（QwenApiProvider 默认不被激活，`planner_provider = "local"` 不变）

### 轮 3.3：测试 ⏸

- `test_planner_qwen_api_unit.py`：mock httpx 响应，覆盖成功路径 + 5 类错误路径
- `test_planner_qwen_api_contract.py`：用 mocked "理想 LLM 响应" 跑 `2_6 §5` 五组契约，验证**解析层**能映射到合格 PlannerOutput（不是验证 LLM 本身）
- `test_planner_fallback.py`：验证任意 LLM 错误 → LocalRuleProvider 输出 + trace `fallback_reason`
- `test_planner_cache.py`：验证同 query 第二次调用不触发 httpx
- **完成标志**：全套 `(132 + N) passed, 9 xfailed, 0 failed`；`QueryPlanner` 的实际行为被不同路径的单测锁死

### 轮 3.4：真实 API smoke + hard_cases 回放 ⏸

- 用户提供 `DASHSCOPE_API_KEY`，手动把 `ORIONSTACK_PLANNER_PROVIDER=qwen_api` 跑本地 smoke
- 选 `hard_cases.jsonl` 现有 8+ 条查询 + §3.1 prompt 的代表性边界查询共约 20 条，逐条记录 `(domain_hint, lexical_terms, planner_confidence)` before/after
- 人工 review：看 9 条 xfail 契约有几条实际被 Qwen 关掉
- **完成标志**：产出一份 `docs/2_8_smoke_results.md` 或等价记录，明示"Qwen 在此场景下能/不能满足哪些契约"

---

## 3. Prompt 设计（锁定）

### 3.1 系统提示词

```text
你是一个查询理解组件，任务是把用户的中文自然语言查询解析为结构化的 planner 输出。

已知的业务领域（business_domain）**枚举**：
- hr: 人事、请假、考勤、薪酬、合同、入离职
- finance: 财务、报销、付款、预算、发票
- admin: 行政、门禁、办公用品、会议室、差旅预订
- it: 技术支持、账号、系统登录、权限、设备
- ops: 运营、生产变更、值班、事件处理

输出要求（严格 JSON，不要任何前后缀文字）：
{
  "normalized_query": string,       // 规范化后的查询文本，保留原意
  "domain_hint": string | null,     // 必须是上面枚举之一，或 null
  "lexical_terms": string[],        // 真正的词项（非字符碎片），最多 10 个
  "planner_confidence": number      // [0.0, 1.0]，对本次解析的置信度
}

规则：
1. domain_hint 只在查询明确包含单一领域专属词时给出；跨域共享词（"申请"、"审批"、"提交"）必须返回 null
2. lexical_terms 必须是完整语义的词或短语，不能是字符碎片（如"假审"、"批进"是禁止的）
3. normalized_query 做以下规范化：全角标点转半角、英文转小写、连续空白压缩为单个
4. planner_confidence 反映"本条解析的可信度"：具体完整的问句高（0.8+），模糊泛问低（0.3-0.5），乱码或多意图混合低于 0.15
```

### 3.2 用户消息模板

```text
查询：{raw_normalized_query}
```

### 3.3 Few-shot 示例（包含在 system prompt 末尾）

```text
示例：

输入：如何申请年假？
输出：{"normalized_query":"如何申请年假?","domain_hint":"hr","lexical_terms":["申请年假","年假","申请"],"planner_confidence":0.92}

输入：怎么提交申请
输出：{"normalized_query":"怎么提交申请","domain_hint":null,"lexical_terms":["提交申请","申请"],"planner_confidence":0.45}

输入：请假
输出：{"normalized_query":"请假","domain_hint":"hr","lexical_terms":["请假"],"planner_confidence":0.38}

输入：xxyyzz 乱码输入 asdfq
输出：{"normalized_query":"xxyyzz 乱码输入 asdfq","domain_hint":null,"lexical_terms":["乱码输入"],"planner_confidence":0.08}
```

### 3.4 调用参数

- `temperature: 0`（确定性必需）
- `top_p: 1`（temperature=0 时 top_p 无实际影响，保留兜底）
- `response_format: {"type": "json_object"}`（若 API 支持；DashScope OpenAI-compatible 目前支持）
- `max_tokens: 256`（输出结构简单，不需要长输出）

---

## 4. 解析与 schema 约束

### 4.1 JSON schema（内部校验）

解析步骤（`QwenApiProvider` 内部执行）：

1. **HTTP 成功检查**：status_code 200；其他 → `PlannerHttpError`
2. **响应 body JSON 解析**：`json.loads(resp.text)`；失败 → `PlannerParseError`
3. **取 message.content**：按 OpenAI 格式 `choices[0].message.content`；缺失 → `PlannerParseError`
4. **content 再 JSON 解析**：`json.loads(content)`；失败 → `PlannerParseError`
5. **字段校验**：
   - `normalized_query: str`
   - `domain_hint: str | None`，且若为 str 必须 ∈ `{"hr","finance","admin","it","ops"}`
   - `lexical_terms: list[str]`，每项非空字符串
   - `planner_confidence: float`，`0.0 <= x <= 1.0`
   - 任何一项不符 → `PlannerSchemaError`
6. **规范化补偿**：
   - `lexical_terms` 截断至 10 条
   - 去除空白项与重复项
7. **构造 `PlannerOutput`** 返回

### 4.2 异常分类（`backend/app/query/providers/errors.py`）

```text
PlannerProviderError          基类
├── PlannerTimeoutError       超时（httpx.TimeoutException 映射）
├── PlannerHttpError          连接失败 / 4xx / 5xx
├── PlannerParseError         响应非 JSON / content 非 JSON / choices 缺失
└── PlannerSchemaError        字段类型错 / domain_hint 枚举外 / confidence 越界
```

`QueryPlanner.plan()` 捕获 `PlannerProviderError` → fallback 到 `LocalRuleProvider`，并在 trace `fallback_reason` 字段记录异常类名。

---

## 5. 降级与缓存

### 5.1 降级路径

```text
ChatService.ask(query)
  └─► QueryPlanner.plan(query)
        ├─► [cache hit] → return cached PlannerOutput
        ├─► [cache miss] provider.plan(query)
        │     ├─► [成功] → cache & return
        │     └─► [PlannerProviderError] → log + fallback:
        │           └─► LocalRuleProvider().plan(query) → cache & return
        └─► return PlannerOutput（上游无感知来源）
```

### 5.2 缓存设计

- 结构：`dict[str, PlannerOutput]`，进程内全局
- Key：`normalized_query`（由调用方传入，已 strip 过，planner 不二次 normalize）
- Value：最终返回的 `PlannerOutput`（无论来自 LLM 还是 fallback）
- 失效：进程生命周期（无 TTL、无上限 —— 验证环境够用，生产化再改）
- 开关：`settings.planner_cache_enabled`（默认 `True`）
- **注意**：fallback 结果也写缓存 → 同一 query 不会反复重试失败的 LLM，避免雪崩

### 5.3 降级的可观测性

- `PlannerOutput` schema 不扩字段（硬约束）
- `trace` 侧（`retrieval_trace.py`）新增一列 `planner_fallback_reason: str | None`，值来自 `PlannerProviderError` 子类名
- `router_used` 保持 `query_planner_{provider.name}`；fallback 后是否改为 `query_planner_local`，放到 3.2 实现时决定（倾向"保留原 provider 名 + fallback_reason 分离"，以便分析"谁在什么时候降级")

---

## 6. 轮 3.1 待落地的 settings 字段

按本文件 §1 硬约束 + `2_7 §1.6` 配置示例，`settings.py` 新增：

| 字段 | 默认值 | env var | 用途 |
|---|---|---|---|
| `qwen_api_base` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `ORIONSTACK_QWEN_API_BASE` | Qwen OpenAI-compatible 端点 |
| `qwen_api_model` | `qwen-plus` | `ORIONSTACK_QWEN_API_MODEL` | 模型 id |
| `local_llm_base_url` | `http://localhost:8080/v1` | `ORIONSTACK_LOCAL_LLM_BASE_URL` | llama.cpp llama-server 端点（轮 3 后续使用） |
| `local_llm_model` | `gemma-3-1b-it` | `ORIONSTACK_LOCAL_LLM_MODEL` | 本地模型 id |
| `planner_timeout_seconds` | `30` | `ORIONSTACK_PLANNER_TIMEOUT_SECONDS` | LLM 调用超时 |
| `planner_cache_enabled` | `True` | `ORIONSTACK_PLANNER_CACHE_ENABLED` | 是否启用进程缓存 |

**API key 不进 settings**：`DASHSCOPE_API_KEY`（DashScope）直接由 `QwenApiProvider` 从 `os.environ` 读取。

---

## 7. 验证策略

### 7.1 单测层（轮 3.2 + 3.3）

- 目标：锁死**解析链路 + 降级链路 + 缓存语义**
- 不验证：**LLM 本身的输出质量**（那是 3.4 的人工任务）
- 所有 LLM 调用必须 mock（`pytest-httpx` 或手工 `httpx.MockTransport`）

### 7.2 契约镜像（轮 3.3）

- 新建 `test_planner_qwen_api_contract.py`
- 不 mock `QwenApiProvider`，而是 mock 它内部的 httpx 响应
- 构造 9 份"理想 LLM 响应"JSON，验证每份都能被解析为满足对应 xfail 契约的 `PlannerOutput`
- **这测的是解析代码的完备性，不是 LLM 的输出质量**

### 7.3 活体 smoke（轮 3.4，手动）

- 需要 `DASHSCOPE_API_KEY`
- 手动触发：`ORIONSTACK_PLANNER_PROVIDER=qwen_api uv run python -m backend.app.main`
- 输入 ~20 条查询跑一遍，导出 trace → `docs/2_8_smoke_results.md`
- **这是对 "LLM 在本场景有效" 的唯一真实信号**

---

## 8. 不在本文件范围

- **LlamaCppProvider 实现**：独立一轮（2_9）
- **Prompt 精调迭代**：本文件锁 v1 prompt，若 3.4 smoke 发现质量不足，起 prompt v2 的 ADR
- **`PlannerOutput` schema 扩展**：硬禁
- **答案生成侧 LLM**：长期禁（`2_7 §6`）
- **全链路 e2e 测试**：`ChatService` + `QwenApiProvider` + 真实 ES，不在本轮

---

## 9. 一句话总结

**LLM 在 planner 层接入分 4 子轮，prompt 锁定为"JSON-only 结构化输出"，异常全部被 QueryPlanner 捕获降级到 LocalRuleProvider，进程内缓存保证重复查询 trace 可重现；轮 3.1 只动 settings 与本文件，不碰 provider 代码。**
