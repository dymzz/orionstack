# 2.6 Planner 质量审查

> 本文件定位：**审查**（review），不是设计。目的是对 `backend/app/query/query_planner.py` 当前实现做一次诚实的现状分析，列出质量债，给下一位接手 planner 改造的人一个信息完备的起点。
>
> 本文件**不开具体代码方案**。具体改造路径由后续聚焦线（例如 `2_7_planner_upgrade.md` 或同名的 milestone 工作）承接。

---

## 1. Planner 在 Phase 2 架构中的角色

`QueryPlanner.plan(normalized_query) -> PlannerOutput` 是 `ChatService._resolve_decision` 进入检索链前的**第一个语义处理节点**。它产生四个下游字段：

| 字段 | 下游消费者 | 作用 |
|---|---|---|
| `normalized_query` | `_search_elastic` | 作为 `lexical_query` / `vector_query` 的主干 |
| `lexical_terms` | `LexicalRetriever` / `HybridRetriever` 的 `should` 子句 | BM25 关键词匹配侧的扩展条件 |
| `domain_hint` | 两侧 ES filter 的 `business_domain` term | **跨域 narrow 的唯一触发源** |
| `planner_confidence` | `IntentDecision.confidence` + router 选择 | 决定走 `query_planner_local` 路径还是 fallback 到 `rule_parser` |

Phase 2 fusion 纪律（见 `docs/2_5`）保护的四层网里，至少两层直接依赖 planner 输出：

- **召回 narrow**（§2.1 of `2_5`）—— 依赖 `domain_hint`
- **词项扩展**（lexical recall）—— 依赖 `lexical_terms`

换言之：**planner 输出质量是整个检索保护网的上游前提**。上游出垃圾，下游再精密的融合/rerank 也只是在垃圾基础上整理秩序。

---

## 2. 现状实现审计

文件 `backend/app/query/query_planner.py` 当前 57 行，全部逻辑可逐字引用：

```python
def plan(self, normalized_query: str) -> PlannerOutput:
    query = normalized_query.strip()
    if not query:
        return PlannerOutput(normalized_query="", domain_hint=None,
                             lexical_terms=[], planner_confidence=0.0)

    lexical_terms = _extract_lexical_terms(query)
    planner_confidence = 0.88 if len(query) >= 2 else 0.05

    return PlannerOutput(
        normalized_query=query,
        domain_hint=None,
        lexical_terms=lexical_terms,
        planner_confidence=planner_confidence,
    )
```

其中 `_extract_lexical_terms` 是字符 n-gram 切分：

```python
def _extract_lexical_terms(query: str) -> list[str]:
    terms = [query]
    if len(query) > 2:
        for index in range(len(query) - 1):
            bigram = query[index : index + 2]
            if bigram not in terms:
                terms.append(bigram)
    if len(query) > 4:
        for index in range(len(query) - 2):
            trigram = query[index : index + 3]
            if trigram not in terms:
                terms.append(trigram)
    return terms
```

这不是 "planner"，是一个**按字符长度产生 n-gram 的字符串工具**，套了 planner 接口的外壳。

另需注意 `settings.planner_provider="local"` / `planner_model="gemma3:1b"` 配置项虽然存在，但在当前实现里**从未被读取**。LLM 路径是空 placeholder。

---

## 3. 质量债清单

把 §2 的观察转成具体可追踪的项：

### 3.1 `domain_hint` 恒为 `None`

- **症状**：无论输入什么查询，planner 永远不产生 domain hint
- **后果**：整个 cross-domain narrow 能力在生产路径**从未被激活**。`HybridRetriever` 里 `business_domain` filter 永远传入 `None`，意味着任何查询都会召回**全部域**的候选
- **矛盾点**：`docs/2_5` §2.1 把 "召回 narrow" 列为四层保护网的第一层。我们在 fusion 纪律里写了一条 `test_chat_service_propagates_planner_domain_hint_to_both_lexical_and_vector_sides` 测试，这条测试只能证明 "如果 planner 产生了 domain_hint，那它会被透传"；但它**无法证明** planner 实际会产生 domain_hint
- **影响的 §9.4 对称污染对**：所有 9 条 cross-domain 测试的前置条件是 fusion rank 1 被跨域候选污染。如果 planner 能产生正确的 domain_hint，这些污染场景在生产路径根本不会出现 —— 目前 rerank 回收能力**在每一个查询上都被过度使用**，而不是作为最后防线

### 3.2 `lexical_terms` 是字符 n-gram，不是词项

- **症状**：对中文查询，`请假审批进度` 会产生 `请假审批进度`, `请假`, `假审`, `审批`, `批进`, `进度`, `请假审`, `假审批`, `审批进`, `批进度`
- **后果**：其中 `假审`, `批进`, `假审批`, `批进` 这些是**无语义的字符碎片**，它们作为 BM25 `should` 条件会引入**非真实意图的词项加权**。这些碎片在索引里以 IK 分词结果对照后，理论上不会匹配任何文档，但仍然污染了 query 的 token 空间
- **好的一面**：真正有效的 token（`请假`, `审批`, `进度`）也在列表里，所以检索还是能工作。但 planner 对**词项边界的识别**没有做任何事
- **性质**：这不是 bug，是**没实现**。planner 现在是字符串工具，不是真正的 lexical term extractor

### 3.3 `planner_confidence` 是长度信号

- **症状**：`len(query) >= 2` → 0.88，否则 0.05
- **后果**：
  - 任何 2 字以上的查询（包括纯噪声、乱码、跨语言混写）都被标为 "高置信" 走 planner 路径
  - 阈值 `route_confidence_threshold = 0.15`（`settings.py:54`）意味着这个信号**只能区分空字符串 vs 其他**，没有分辨力
  - 下游 `router_used == "query_planner_local"` 标签因此在 trace 里失去意义 —— 它几乎等于 "非空查询"
- **矛盾点**：`test_chat_service_falls_back_to_rule_parser_when_planner_confidence_is_low` 用 `planner_confidence=0.05` 触发 fallback，但这种低置信 **在生产 stub 实现里只有单字符查询才会出现**

### 3.4 `normalized_query` 只 strip

- **症状**：除了去首尾空白，没有任何 normalization
- **后果**：
  - 半角/全角标点未统一（`? / ？`, `, / ，`）
  - 英文大小写未统一
  - 连续空白未压缩
  - 典型缩写未展开（如 `HR` vs `人力资源`）
- **局部缓解**：有独立的 `app/guardrails/normalize.py::normalize_query` 在 `ChatService.ask()` 入口处被调用，但那是**通道层**的 normalize，planner 自己不做任何语义层 normalize

### 3.5 LLM 接口是空壳

- **症状**：`settings.planner_provider` / `planner_model` / `settings.ollama_url` 配置就位，但 `QueryPlanner.__init__` 只把 `provider` 存成字段，`plan()` 里从不使用
- **后果**：当前**没有** LLM fallback 或 LLM-first 路径。想要升级到 LLM-based planner 的同事会发现除了配置字段，其他都要从零写

### 3.6 既有测试都是连线测试，不是质量测试

- **症状**：3 条 planner 测试（见 `test_phase2_planner.py`）全部验证 **"planner 输出被 chat_service 正确使用"**，没有一条验证**"planner 输出对给定查询是合理的"**
- **后果**：planner 可以产生任何垃圾，测试仍然绿。没有回归保护阻止后续 planner 改动意外降低输出质量

---

## 4. 影响面矩阵

各项质量债对 Phase 2 其他保护机制的影响，用于 prioritization：

| 质量债 | 影响 `2_5` 四层保护网 | 影响 §9.4 cross-domain 测试 | 影响用户可感知质量 |
|---|---|---|---|
| 3.1 domain_hint=None | **核心**：让第一层 narrow 形同虚设 | 让所有对称测试的假设场景成为日常 | 高：跨域污染答案偶发 |
| 3.2 n-gram lexical | 第二层词项扩展被噪声化 | 无直接影响（测试 mock 了 planner） | 中：BM25 召回偶发不准 |
| 3.3 bogus confidence | router fallback 失效 | 无直接影响 | 低：trace 标签误导，但检索行为无差 |
| 3.4 弱 normalization | 间接影响所有层（全角标点查询降级） | 无直接影响 | 中：边界查询偶发 no_hit |
| 3.5 LLM 壳 | 不影响（因为从未激活） | 无 | 无（未来才出现） |
| 3.6 测试缺口 | 不影响（但阻碍任何改造的信心） | 无 | 无（开发侧风险） |

**结论**：3.1 > 3.2 ≈ 3.4 > 3.3 > 3.6 > 3.5。3.1 是优先级最高的真实生产质量债。

---

## 5. 评审标准（What "good planner" means，可测契约）

任何未来的 planner 改造，应通过以下可测契约来验收。这些契约与具体实现路径（local 规则 / LLM / 混合）正交：

### 5.1 domain_hint 契约

- **Positive**：对明确包含域专属词的查询（"请假" / "门禁" / "付款申请" / "生产变更"），`domain_hint` 必须是对应域
- **Negative**：对跨域共享词的查询（"申请" / "审批" / "提交"），`domain_hint` 应为 `None`（避免误 narrow）
- **Edge**：对混合域查询（"入职账号怎么开通"）`domain_hint` 应为 `None` 或保守选择一个，不应自信 narrow 到单一域

### 5.2 lexical_terms 契约

- **词项完整性**：真实词项（`请假`, `审批`）必须出现
- **无碎片污染**：不应出现无语义字符拼接（`假审`, `批进`）
- **上界**：单查询 `lexical_terms` 数量应 ≤ 10（否则 BM25 信号会被稀释）
- **去重**：不应有重复项

### 5.3 confidence 契约

- **对真实差异有分辨力**：完整具体问句（"如何申请年假？"）应显著高于模糊泛问法（"请假"）
- **对噪声查询应低**：乱码、纯标点、纯英文乱输入应低于 `route_confidence_threshold`
- **对 multi-intent 应低**：同时问两个不同意图的长句（如 "怎么请假同时怎么报销"）应低，触发 fallback

### 5.4 normalization 契约

- 全角/半角标点统一
- 英文统一小写
- 连续空白压缩为单个
- 保留原意（不展开缩写，不做翻译）

### 5.5 稳定性契约

- 同一查询的 planner 输出必须**确定性**（多次调用产出一致）。LLM 路径也需通过温度 0 / 缓存等方式满足
- 否则 trace 可重现性被破坏

---

## 6. 改造路径选项

> **项目定位澄清**（2026-04-21 讨论决定）：**本项目的核心目标是验证 LLM 在 FAQ 场景下的应用**，不是验证 local rule 或其可靠性。Local rule 的唯一角色是**兜底安全网**（LLM 失败时的 fallback），不是质量竞争者。以下三条路径的评估按这一定位重写。

### 6.1 路径 A：纯 local 规则升级 —— **拒绝**

- 原描述：`_extract_lexical_terms` 改为 IK / jieba 分词、加字典式 `domain_hint`、confidence 基于覆盖率
- **拒绝理由**：
  - 与项目核心目标（验证 LLM）无关；投入在 local rule 上是**方向错误**
  - 即便做到最优，也只是模仿 LLM 能做的一小部分；没有 long-tail 查询理解能力
  - 规则字典随域增长线性膨胀，是维护债
- **仅保留的最小部分**：现有字符 n-gram stub 继续作为**fallback 安全网**存在，不再深化

### 6.2 路径 B：引入 LLM —— **项目核心路径**

- **做什么**：`OpenAICompatiblePlannerProvider` 与 `LlamaCppProvider` 两套 provider 实现 `PlannerProvider` Protocol；prompt 设计让模型输出结构化 `{"domain_hint": ..., "lexical_terms": [...], "planner_confidence": ...}`；温度 0 + 缓存保证可重现
- **收益**：直接关闭 `2_6 §3.1/§3.2/§3.3/§3.4` 四条质量债；验证 LLM 在中文 FAQ 场景下的 planner 能力
- **风险**：LLM 非确定性（缓解：温度 0 + 缓存）、延迟（缓解：验证环境接受秒级，不做压测）、解析失败（缓解：降级到 LocalRuleProvider）
- **这是本项目验证的核心**

### 6.3 路径 C：Hybrid —— **路径 B 的必然形态**

- **实际含义**（更新后）：
  - **LLM primary**：生产路径默认走选定的 LLM provider（Qwen API 或 llama.cpp）
  - **LocalRule fallback**：LLM 调用失败、超时、解析错误时降级到 LocalRuleProvider
  - **非 "规则先，LLM 升级"**：LocalRule 的 confidence 信号不可信（长度信号），不能作为升级门控
- **架构上等于路径 B**：没有独立的第三种实现；C 只是 B 的**稳定性配置**
- **成本**：与 B 并列，不额外增加

### 结论

可选路径收敛到 **路径 B（LLM primary with LocalRule fallback）**。`docs/2_7_planner_upgrade_plan.md` 锁定的即此路径。

---

## 7. 验证方案

任何路径改造后，以下验证**必须全绿**才能合入：

### 7.1 回归保证

- `backend/tests/` 全套 128 条必须全绿
- 特别是 `test_phase2_cross_domain.py` 11 条 —— 如果改造真正生效，部分测试的 mock 前提（"fusion rank 1 被跨域污染"）应变得不自然，但测试仍应绿（因为它们 mock 了 planner）

### 7.2 新增 planner 质量测试

在 `test_phase2_planner.py` 里加一组**端到端不 mock planner** 的测试，验证 §5 各条契约。最小集合：

- `test_planner_produces_domain_hint_for_hr_exclusive_query`
- `test_planner_refuses_domain_hint_for_cross_domain_shared_tokens`
- `test_planner_lexical_terms_contain_real_tokens_not_character_fragments`
- `test_planner_confidence_distinguishes_specific_from_pan_query`

### 7.3 hard_cases 回放

- `backend/app/storage/hard_cases/hard_cases.jsonl` 里已有的 8+ 条真实查询，逐条跑一遍新 planner
- 记录 before/after 的 `domain_hint`, `lexical_terms`, `planner_confidence` 三元组，人工 review
- 这一步是质量回归的**唯一真实信号** —— 所有单测都可能绿，而生产查询仍然差

### 7.4 debug_info.rrf_topk 回放

- 选 §9.4 cross-domain 测试里的 3 对对称查询，在真实 ES 数据上用新 planner 跑一遍
- 如果 3.1 被真正修复，跨域污染候选应 **不再出现在 fusion top-5 里**（被 narrow 过滤掉）—— 这是最直接的视觉验证

---

## 8. 不做的选择

显式列出**不建议改的方向**，避免未来聚焦线走偏：

- **不改 `PlannerOutput` schema**：四字段设计已被 `ChatService` 深度依赖，改 schema 会触发大量 downstream refactor，得不偿失
- **不删除 rule_parser fallback**：即便 planner 升级为 LLM，低置信 fallback 仍是稳定性底线
- **不引入 planner 侧的业务词典配置**：让 planner 知道哪些 token 属于哪些 domain 是 coupling，应由 seeds 的 `business_domain` 字段反推（见路径 A 的字典可从 seeds 自动构建）
- **不把 planner 质量问题与 reranker 质量问题捆绑**：这是两条独立聚焦线；planner 做语义识别，reranker 做候选排序，混在一起会让 bug 归因混乱
- **不在本审查文档里确定路径**：选 A / B / C 需要产品侧对延迟/成本的判断，本文件只陈述选项

---

## 9. 交叉引用

- **`docs/2_4_test_strategy.md` §12**：审计先行方法论 —— 本文件 §2 / §3 就是该方法论在 planner 线上的一次应用
- **`docs/2_5_retrieval_defense_discipline.md` §2.1 / §2.2**：下游保护层，本文件 §1 / §4 的影响面分析引用其层次结构
- **`backend/app/query/query_planner.py`**：被审查对象
- **`backend/tests/test_phase2_planner.py`**：§3.6 诊断对象
- **`backend/app/storage/hard_cases/hard_cases.jsonl`**：§7.3 验证回放数据源

---

## 10. 一句话总结

**当前 planner 是一个字符串 n-gram 工具套了 planner 外壳；Phase 2 的 domain narrow 保护网因此在生产路径从未真正激活。本项目以"验证 LLM 在 FAQ 场景的 planner 能力"为核心，LocalRule 仅作兜底安全网，不做质量方向的深化。**
