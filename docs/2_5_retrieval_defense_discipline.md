# OrionStack 第二阶段检索保护纪律 v1

> 对应设计文档：`docs/designs/2_system_design.md`
> 配套进度文档：`docs/2_1_progress.md`
> 配套测试策略：`docs/2_4_test_strategy.md`
> 目标：把五轮围绕 fusion 规则做的保护性改动沉淀为一份**可被后人一次读懂**的纪律文档，覆盖层级划分、不变式、被拒绝的路径、测试到代码的映射。

---

## 1. 文档目标

这份文档不讲第二阶段检索怎么实现、也不讲整体 retrieval 教科书，只回答一个问题：

> **未来任何人改 `hybrid_retriever.py` / `reranker.py` / `chat_service.py._search_elastic` 时，必须保住哪些不变式？为什么这些不变式是这样而不是那样？**

它是五轮讨论的收尾，不是新起点。如果要继续扫 bad case，另起聚焦线。

---

## 2. 四层保护网

检索链路按职责分为四层。**每层独立担保一件事**；下游无法替上游兜底，反之亦然。

```
┌─ 召回层 (narrow)     business_domain ES filter
├─ 融合层 (fusion)     RRF + 每侧 dominance bonus
├─ rerank 层 (accept)  evidence_confidence 阈值独立决策
└─ 观测层 (attribution) 每候选归因贯穿到 debug_info + trace JSONL
```

### 2.1 召回层 (narrow)

**职责**：在进入 RRF 之前，按 `planner.domain_hint` 在 ES filter 里砍掉跨域候选。

- 代码：`app/retrieval/lexical_retriever.py`、`app/retrieval/vector_retriever.py`
- 数据流：`planner.domain_hint → ChatService.business_domain → HybridRetriever.search(business_domain=...) → 两侧 retriever.search(business_domain=...) → ES filter {"term": {"business_domain": ...}}`
- 纪律：**任何新加 retriever 侧接口必须透传 `business_domain` kwarg，并在 ES filter 中实际应用**；不允许上游拿到 domain_hint 后仅单侧 narrow。

### 2.2 融合层 (fusion)

**职责**：RRF 合并两侧候选后，给**一侧清晰赢家**一个有限的 `+0.02` 分数 bonus，防止它被"双榜都在的 noisy 候选"以累计 RRF 反超。

- 代码：`app/retrieval/hybrid_retriever.py::_fuse_hits` + `_find_dominant_side_winner_id`
- 常量（两侧各一组，共享抽象）：
  - `LEXICAL_DOMINANCE_RATIO = 3.0`、`LEXICAL_DOMINANCE_BONUS = 0.02`、`LEXICAL_DOMINANCE_ABSOLUTE_FLOOR = 1.0`
  - `VECTOR_DOMINANCE_RATIO = 3.0`、`VECTOR_DOMINANCE_BONUS = 0.02`、`VECTOR_DOMINANCE_ABSOLUTE_FLOOR = 0.5`
- 判据：`top.score >= second.score * ratio` **且** `top.score >= absolute_floor`；支持 `len(hits) == 1` 的孤点强胜者。
- 纪律：
  - **规则只用 score / rank / count**，不允许引入 `source_kind` / `business_domain` / `unit_id` 列表
  - lexical / vector 两侧**对称**，共用 `_find_dominant_side_winner_id(hits, *, ratio, absolute_floor)`
  - absolute_floor 的量级差异来自两侧 score 量纲不同（BM25 vs cosine），不是领域量身定制
  - 两侧 bonus 可叠加；一个候选若同为两侧强胜者，得 `+0.04`，是正确行为

### 2.3 rerank 层 (accept)

**职责**：用 `evidence_confidence` 判断是否把候选作为答案给用户。

- 代码：`app/retrieval/reranker.py`
- 关键性质：**`accept = evidence_confidence >= 0.15`**，与 fusion score 绝对值无关
- 纪律：**rerank accept 决策不跟随 fusion 常量变化而重校**。`+0.02` 级 bonus 只改变候选**是否进入 rerank `top_n` 窗口**，不翻转 accept/reject
- 推论：未来调整 `*_DOMINANCE_BONUS` 不需要同步改 `_ACCEPT_EVIDENCE_THRESHOLD`

### 2.4 观测层 (attribution)

**职责**：记录每候选是否在 fusion 阶段拿到了 bonus，供未来 trace 回放时区分 "bonus 赢家" 与 "普通 RRF 赢家"。

- 字段：
  - `HybridHit.lexical_dominance_applied: bool`、`vector_dominance_applied: bool`（默认 `False`）
  - `RetrievalCandidateSummary.lexical_dominance_applied: bool | None`、`vector_dominance_applied: bool | None`（默认 `None`，只在 `rrf_topk` 项中填值）
- 贯穿链路：`_fuse_hits 写入` → `rrf_rank 二次构造转发` → `_summarize_hybrid_hits 投影到 rrf_topk` → `DebugInfo.rrf_topk` → `api/routes/chat.py 的 model_dump()` → `retrieval_traces.jsonl`
- 纪律：
  - **任何 HybridHit 的构造路径都必须转发这两个字段**（包括 `_fuse_hits` 内部的 `rrf_rank` 二次构造——默认值为 False 会静默吃掉信息）
  - 归因是**每候选**的 bool，不是全局标记
  - `lexical_topk` / `vector_topk` 故意不填（`None`），它们是召回层视图，不是融合层归因视图

---

## 3. 设计不变式（Do-not-break list）

以下每一条都有至少一条测试钉死；删除或弱化任何一条将立即导致测试红。

| # | 不变式 | 主保护测试 |
|---|---|---|
| 1 | fusion 规则只用 score / rank / count，不看 source_kind | `test_hybrid_retriever_keeps_dominant_lexical_document_chunk_ahead_of_noisy_vector_hits`、`test_hybrid_retriever_keeps_dominant_lexical_winner_when_runner_up_is_different_source_kind` |
| 2 | lexical / vector 两侧对称，共享抽象 | `test_hybrid_retriever_keeps_dominant_vector_winner_ahead_of_noisy_lexical_hits` + 其 lexical 对称版 |
| 3 | 低分孤点不触发 bonus | `test_hybrid_retriever_does_not_find_dominant_lexical_winner_below_absolute_floor`、`test_hybrid_retriever_does_not_find_dominant_vector_winner_below_absolute_floor` |
| 4 | 孤点强胜者仍然保护 | `test_hybrid_retriever_protects_lonely_strong_lexical_winner`、`test_hybrid_retriever_protects_lonely_strong_vector_winner` |
| 5 | fusion bonus 能 end-to-end 改变用户可见 answer | `test_chat_service_propagates_lexical_dominance_bonus_through_rerank_to_response`、`test_chat_service_propagates_vector_dominance_bonus_through_rerank_to_response` |
| 6 | `planner.domain_hint` 双侧 narrow | `test_chat_service_propagates_planner_domain_hint_to_both_lexical_and_vector_sides` |
| 7 | 归因是每候选 bool，不是全局标记 | `test_hybrid_retriever_records_dominance_attribution_per_candidate_on_hybrid_hits` |
| 8 | 归因能活过 rrf 二次排序并落到 debug_info | `test_chat_service_surfaces_fusion_dominance_attribution_in_debug_rrf_topk` |

所有测试位均在 `backend/tests/test_phase2_retrieval.py`。

---

## 4. 被拒绝的路径（anti-patterns considered）

这两条曾在讨论里作为备选，评估后**明确撤出路线图**，记录以防将来重新提出时重走弯路。

### 4.1 把合成 fusion 场景固化进 `hard_cases_repo`

- **原提议**：把 8 条合成 fusion 边界场景写进 `hard_cases.jsonl`，走同一套回放
- **撤下原因**：`HardCasesRepository` 的契约是 **运行时捕获的坏例**（`no_evidence` fallback / user down-vote），key 为 `trace_id`，append/upsert 语义；合成场景不是 trace，硬塞会违背基础设施的意图
- **替代方案**：已做 —— unit 层 8 条行为断言 + e2e 层 2 条贯穿断言 + attribution 层 2 条归因断言；共 12 条覆盖，远强于 hard_cases 的被动回放

### 4.2 rerank 阈值跟随 fusion 常量重校

- **原提议**：fusion 加了 `+0.02` bonus，rerank 阈值是否也该重校
- **撤下原因**：核实 `reranker.py` 后确认 `accept = evidence_confidence >= 0.15` 不依赖 fusion score 绝对值；两层在 accept 决策上天然解耦
- **推论**：未来调整任一侧 `*_DOMINANCE_BONUS` 在 0~0.1 量级内**不需要**动 rerank 常量

---

## 5. 测试到代码映射

```
召回层
  app/retrieval/lexical_retriever.py  ─┐
  app/retrieval/vector_retriever.py   ─┼─ test_chat_service_propagates_planner_domain_hint_to_both_lexical_and_vector_sides
  app/retrieval/hybrid_retriever.py   ─┘

融合层
  app/retrieval/hybrid_retriever.py
    _find_dominant_side_winner_id      ── test_hybrid_retriever_keeps_dominant_*
                                          test_hybrid_retriever_protects_lonely_*
                                          test_hybrid_retriever_does_not_find_dominant_*_below_absolute_floor
    _fuse_hits (bonus 应用)            ── test_chat_service_propagates_*_dominance_bonus_through_rerank_to_response

rerank 层
  app/retrieval/reranker.py            ── 由已有 reranker 单测 + 上述 e2e 间接覆盖
                                          （accept 阈值与 fusion 解耦已在本文档 §2.3 作为结论记录）

观测层
  app/retrieval/hybrid_retriever.py
    HybridHit dominance 字段            ── test_hybrid_retriever_records_dominance_attribution_per_candidate_on_hybrid_hits
  app/schemas/response.py
    RetrievalCandidateSummary           ─┐
  app/services/chat_service.py          ─┼─ test_chat_service_surfaces_fusion_dominance_attribution_in_debug_rrf_topk
    _summarize_hybrid_hits              ─┘
  app/api/routes/chat.py
    model_dump() 序列化路径             ── 由 Pydantic 默认行为 + test_phase2_trace 间接覆盖
```

---

## 6. 五轮讨论时间线

保留讨论路径，供未来读者理解为什么规则长成现在这样。

1. **第 1 轮 · 通用化 lexical dominance**
   原规则是 FAQ-only、要求至少 2 条 FAQ 的 source_kind 补丁。升级为共享抽象 `_find_dominant_side_winner_id`，只看 score / rank / count，支持孤点强胜者，并引入 `LEXICAL_DOMINANCE_ABSOLUTE_FLOOR`。

2. **第 2 轮 · 对称 vector dominance**
   同一抽象对称应用到 vector 侧。`VECTOR_DOMINANCE_ABSOLUTE_FLOOR = 0.5` 的量级差异来自 cosine 相似度 vs BM25 的量纲差。两侧共享 `_find_dominant_side_winner_id(hits, *, ratio, absolute_floor)`，不引入任何 side-specific 分支。

3. **第 3 轮 · lexical e2e 贯穿证明**
   用真实 `HybridRetriever` 包裹 fake 两侧 retriever 驱动 `ChatService`，证明删掉 lexical bonus → fusion rank 翻转 → rerank 拿不到正确候选 → `no_evidence` fallback。中途发现 `reranker.accept` 与 fusion score 解耦，决定**不做 rerank 重校**。

4. **第 4 轮 · vector e2e 贯穿 + domain_hint narrow 核实**
   对称补 vector 侧 e2e。顺带核实 `planner.domain_hint → ChatService → HybridRetriever → 两侧 retriever` 数据流结构性完整（源代码本身无缺口），补一条回归测试钉死两跳 kwarg 透传。

5. **第 5 轮 · 每候选归因可观测性**
   给 `HybridHit` 和 `RetrievalCandidateSummary` 加 `lexical_dominance_applied` / `vector_dominance_applied`。**中途发现** `_fuse_hits` 内部 `rrf_rank` 二次构造循环若不转发新字段会被 `False` 默认值静默吃掉——这是加 dataclass 新字段时最容易漏的点，也写进断言。

---

## 7. 已知未走方向（明确 defer）

以下方向属于**换一条聚焦线**，不是本纪律链路的遗漏：

- **planner hard case 扫描**：对真实模糊查询（"请假怎么弄"、"我病了"等）审查 planner.domain_hint / lexical_terms 的合理性——换到 planner 质量线
- **各领域清洗文档 fixture 扫描**：`docs/2_4` 第 6 节列出的"各领域清洗文档进入测试资产"——换到内容层
- **retrieval trace UI 回放工具**：基于已落地的归因字段做 trace 可视化——工具侧工作，不是保护纪律

这些不在本纪律文档覆盖范围内。如果未来选择做其中任一条，请在对应方向起新文档而非混入此文件。
