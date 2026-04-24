# 2.7 Planner 升级计划（锁决策 + 分轮执行）

> 本文件定位：**执行计划**（plan），不是审查。`docs/2_6_planner_quality_review.md` 已完成 planner 质量债盘点并列出三条候选路径（A local rule / B LLM / C hybrid）。本文件**锁死本项目的选择**、**定分轮边界**、**明确哪些事当前做 / 哪些延后**。
>
> 本文件的决策由本次讨论一次性锁定，后续聚焦线工作不再重新讨论决策本身，只讨论执行。

---

## 1. 锁定的决策清单

### 1.1 插入点

- **Planner 层**，不在 reranker / evidence 提取 / 答案生成层引入 LLM
- 依据：`2_6 §4` 影响面矩阵 —— planner 是当前唯一真正缺语义能力的层；其他层已有足够 defence-in-depth

### 1.2 执行模式：LLM primary with LocalRule fallback

> **项目定位澄清**（2026-04-21）：本项目的核心验证目标是**LLM 在 FAQ 场景下的 planner 能力**。LocalRule 不是质量竞争者，只是 LLM 失败时的兜底安全网。**不对 LocalRule 做任何深化投入**（见 `2_6 §6.1` 拒绝路径）。

- **LLM Provider primary**：生产路径默认走选定的 LLM provider（`settings.planner_provider` 决定用 OpenAI-compatible HTTP provider 还是 llama.cpp）
- **LocalRuleProvider fallback**：LLM 调用失败 / 超时 / 解析错误时自动降级；不依赖 LocalRule 的 confidence 做升级判断（其 confidence 只是长度信号，不可信）
- **failure mode**：任何 LLM 异常都必须被 `QueryPlanner` 捕获并降级，**绝不能让异常传播到 `ChatService`**
- **切换**：通过 `settings.planner_provider = "local" | "openai_compatible" | "qwen_api" | "llama_cpp"` 手动切，不做自动切换；`qwen_api` 是兼容别名

### 1.3 Provider 角色与优先级

| Provider | 角色 | name | 接入顺序 | 维护投入 |
|---|---|---|---|---|
| `LocalRuleProvider` | **兜底安全网**（LLM 失败降级目标） | `"local"` | 轮 2 完成（包装现有 stub） | **冻结**：不深化、不修复 `2_6 §3.x` 债 |
| `OpenAICompatiblePlannerProvider` | **项目核心验证目标**（在线 LLM；首个实测后端为 DashScope/Qwen） | `"openai_compatible"` | 轮 3 首发 | 持续投入，prompt 工程、解析稳定性 |
| `LlamaCppProvider` | **离线替代**（本地 GGUF 模型，当前运行 `ggml-org/gemma-3-1b-it-GGUF`）| `"llama_cpp"` | 轮 3 后续 | 与 Qwen API 并列，共享 prompt |

LocalRule **只需要存在**，不需要变好。它的 9 条 xfail（`test_planner_contract.py`）是 LLM 需要关闭的债，**不是 LocalRule 需要关闭的债**。

### 1.4 切换方式

- **纯手动**，通过 `settings.planner_provider` 配置项切
- **不做自动降级延迟验证**（本项目是验证环境，非生产）
- 4B 模型即便 ~4000ms 也接受；延迟由用户自行判断是否可接受
- API key 走 `os.environ`（优先 `ORIONSTACK_PLANNER_API_KEY` / `ORIONSTACK_LLM_API_KEY`，兼容 `DASHSCOPE_API_KEY` / `QWEN_API_KEY`），不进持久化配置

### 1.5 缓存策略

- 允许对 `normalized_query -> PlannerOutput` 做内存缓存
- 缓存 key：normalized_query 本身；缓存生命周期：进程生命周期
- 温度 0 + 缓存 = LLM 路径的确定性 + trace 可重现性保证

### 1.6 关于 API key / 配置

配置示例：

```text
ORIONSTACK_PLANNER_PROVIDER=local         # or "openai_compatible" / "qwen_api" / "llama_cpp"
ORIONSTACK_PLANNER_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
ORIONSTACK_PLANNER_API_MODEL=qwen-plus    # 轮 3 首发使用的示例模型
ORIONSTACK_LOCAL_LLM_BASE_URL=http://localhost:8080/v1    # llama.cpp llama-server OpenAI-compatible 端点（默认 8080）
ORIONSTACK_LOCAL_LLM_MODEL=gemma-3-1b-it  # 轮 3 后续接入；当前 llama-server 加载 ggml-org/gemma-3-1b-it-GGUF
ORIONSTACK_PLANNER_TIMEOUT_SECONDS=30     # LLM 调用超时，验证环境容忍较长延迟
ORIONSTACK_PLANNER_CACHE_ENABLED=true     # normalized_query -> PlannerOutput 进程缓存
ORIONSTACK_PLANNER_API_KEY=xxx            # env-only, 不在持久化配置
```

## 2. 分轮边界

### 轮 1：决策锁定 ✅（本文件）

**完成标志**：`docs/2_7_planner_upgrade_plan.md` 落地。

### 轮 2：基础设施 + 契约测试先行 ✅（本轮将执行）

**范围**：

- 重构 `backend/app/query/query_planner.py`：
  - 引入 `PlannerProvider` Protocol
  - `LocalRuleProvider` 包装现有 stub 逻辑
  - `QueryPlanner` 变成"接受 provider 名的壳"，行为不变
- 新建 `backend/tests/test_planner_contract.py`：
  - 对应 `2_6 §5` 的 5 组契约（5.1 ~ 5.5）
  - 已知不满足的契约标 `@pytest.mark.xfail`，附 reason 引用 `2_6 §3.x`
  - 已满足的契约直接断言（作为未来回归保护）

**明确不做的**：

- 不加 HTTP provider / `LlamaCppProvider` 任何实现
- 不改 `settings.py` 新增字段
- 不改 `ChatService` 调用 planner 的方式
- 不写 `httpx` / `openai` / `llama-cpp-python` 等依赖

**完成标志**：

- `uv run python -m pytest backend/tests/ -q` 产出 `N passed, M xfailed, 0 failed`
- `xfailed` 数量即"可测量的 planner 质量债"

### 轮 3：LLM provider 接入 🔄 执行中（2026-04-21 启动）

**触发**：用户明确批准"按推荐顺序 → OpenAI-compatible 云端先"；首个验证后端为 DashScope/Qwen。

**范围**：

- 先 `OpenAICompatiblePlannerProvider` 后 `LlamaCppProvider`
- `QueryPlanner` 内捕获 LLM 异常并降级到 `LocalRuleProvider`（非 confidence-based，见 §1.2）
- 接入后对 `test_planner_contract.py` 的 xfail 不直接 un-mark（那是 LocalRuleProvider 的契约），而是在 LLM provider 侧新增**平行契约测试**跑相同 5 组契约

**详细分解**：由 `docs/2_8_planner_llm_integration.md` 承接，分 4 个子轮（3.1 基础设施 + prompt / 3.2 OpenAI-compatible provider 实现 / 3.3 测试 / 3.4 真实 API smoke）。

---

## 3. 轮 2 执行细则（即将执行）

### 3.1 Provider 抽象形状

```python
from typing import Protocol

class PlannerProvider(Protocol):
    name: str
    def plan(self, normalized_query: str) -> PlannerOutput: ...
```

`name` 字段用于 trace 里的 `router_used` 后缀（`query_planner_{provider.name}`）。

### 3.2 LocalRuleProvider 范围

包装现有 `query_planner.py` 内 `plan()` 全部逻辑与 `_extract_lexical_terms()`：

```python
class LocalRuleProvider:
    name: str = "local"
    def plan(self, normalized_query: str) -> PlannerOutput:
        # 照搬现有 plan() 主体
```

**保留现有行为完全不变**，所有既有测试全部绿。

### 3.3 QueryPlanner 壳

```python
class QueryPlanner:
    def __init__(self, *, provider: str = "local", model: str = "") -> None:
        self._provider_name = provider
        self._model = model
        self._impl = self._create_provider(provider, model)

    def _create_provider(self, name: str, model: str) -> PlannerProvider:
        if name == "local":
            return LocalRuleProvider()
        raise ValueError(f"unknown planner provider: {name!r}")

    @property
    def router_name(self) -> str:
        return f"query_planner_{self._provider_name}"

    def plan(self, normalized_query: str) -> PlannerOutput:
        return self._impl.plan(normalized_query)
```

**外部签名与当前一致**（`QueryPlanner(provider=..., model=...)`），所有 callsite 无需改动。

### 3.4 契约测试布局

文件：`backend/tests/test_planner_contract.py`

每组契约一个测试类，xfail 标在**方法级**而不是类级，便于未来逐项 un-mark：

```text
TestDomainHintContract          (§5.1)
├── test_hr_exclusive_query_gets_hr_hint                 [xfail → 2_6 §3.1]
├── test_admin_exclusive_query_gets_admin_hint           [xfail → 2_6 §3.1]
└── test_cross_domain_shared_tokens_get_no_hint          [green]
TestLexicalTermsContract        (§5.2)
├── test_real_tokens_appear                              [green]
├── test_no_meaningless_character_fragments              [xfail → 2_6 §3.2]
├── test_lexical_terms_bounded_above                     [xfail → 2_6 §3.2]
└── test_lexical_terms_deduplicated                      [green]
TestConfidenceContract          (§5.3)
├── test_specific_query_higher_confidence_than_pan_query [xfail → 2_6 §3.3]
└── test_nonsense_query_low_confidence                   [xfail → 2_6 §3.3]
TestNormalizationContract       (§5.4)
├── test_fullwidth_punct_normalized                      [xfail → 2_6 §3.4]
├── test_english_case_normalized                         [xfail → 2_6 §3.4]
└── test_whitespace_collapsed                            [xfail → 2_6 §3.4]
TestStabilityContract           (§5.5)
└── test_determinism                                     [green]
```

约 13 条测试，其中 ~9 条 xfail、~4 条 green。xfail 数即**轮 2 末端的可测量债余量**。

### 3.5 不做的具体事项

- **不合并** `test_planner_contract.py` 到 `test_phase2_planner.py` —— 前者测输出**质量契约**，后者测**连线是否通**，主题不同，按 `2_4 §12` 方法论应分文件
- **不改** `test_phase2_planner.py` —— 它的 `planner_confidence=0.88 / 0.05` 值是针对现 stub 行为的有效断言
- **不在本轮修** `ChatService` 对 planner 的 import / 使用方式

---

## 4. 验证与回归

轮 2 完成后必须满足：

- [ ] `uv run python -m pytest backend/tests/ -q` passed 数 = 当前 128（**不减**）
- [ ] xfailed 数 > 0（代表债项被记录）
- [ ] 无 failed
- [ ] `git status` 仅改动：`backend/app/query/query_planner.py` / 新建 `backend/tests/test_planner_contract.py` / 文档文件

任何 ChatService / HybridRetriever / Reranker / EvidenceExtractor 的代码改动都是**越界**，应拒绝。

---

## 5. 与既有文档的关系

- **`docs/2_6_planner_quality_review.md`**：审查文档，本文件 §1 / §2 决策锁定它提出的选项空间
- **`docs/2_4_test_strategy.md § 12`**：审计先行方法论，本文件 §3.4 / §3.5 遵循其"扩展 vs 新建判据"
- **`docs/2_5_retrieval_defense_discipline.md`**：本文件不修改其任何约束；planner 升级后 `2_5 §2.1` 的 narrow 层才会真正被激活
- **`docs/2_1_progress.md`**：本文件完成后追加一条索引

---

## 6. 不在本计划范围的事（显式拒绝清单）

- **改 `PlannerOutput` schema**：四字段设计已被深度依赖
- **删除 rule_parser fallback**：稳定性底线
- **深化 LocalRuleProvider**（包括加 IK 分词、加字典、改 confidence 算法等任何质量提升）：**项目核心不在此方向**（见 `2_6 §6.1`），LocalRule 仅作兜底安全网存在
- **延迟压测**：用户明确声明当前为验证环境，不做
- **答案生成侧引入 LLM**：本项目长期保持 verbatim 输出（幻觉免疫）
- **LLM prompt 设计细节**：本计划锁定架构，prompt engineering 放到轮 3 实际接入时讨论

这些事**不是坏事**，只是本计划不承接。未来要做时另起计划文档。

---

## 7. 一句话总结

**本计划锁定："LLM 是 FAQ planner 的主路径与项目验证核心（先 Qwen API 后本地 llama.cpp，手动切换、失败降级到冻结的 LocalRule、温度 0 + 缓存去非确定性）"；轮 2 只做 provider pattern 重构 + 契约测试先行；LocalRule 不深化；LLM 接入延后至批准后再起。**
