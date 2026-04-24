# OrionStack 第二阶段系统设计对应的文件级最小改造清单 v1

> 状态：执行清单 v1  
> 对应设计文档：`docs/designs/2_system_design.md`  
> 配套职责文档：`docs/2_2_file_responsibilities.md`  
> 配套字段文档：`docs/2_3_field_definitions.md`  
> 配套测试文档：`docs/2_4_test_strategy.md`  
> 目标：把第二阶段设计从“系统设计基线”收成“第一轮最小可执行改造范围”  
> 原则：**最小切入、分步替换、旧链路可回退、先数据统一再切检索**

---

## 1. 当前目标

本清单只解决一件事：

**把 Phase 2 的目标链路，拆成当前仓库中可落地的最小文件级改造范围。**

本文档不承担以下职责：

- 不重写 `2_system_design.md` 的系统设计正文
- 不替代 `2_2_file_responsibilities.md` 的文件职责边界说明
- 不替代 `2_3_field_definitions.md` 的字段语义解释
- 不替代 `2_4_test_strategy.md` 的测试分层与回归策略说明

当前不追求：

- 一次性切完整 Query Planner + Hybrid + Rerank + Clarification 全链路
- 直接删除旧 FAQ / document-first 代码
- 在第一轮就把所有接口彻底冻结到最终形态

当前优先级按 Phase 2 设计顺序收敛为：

1. 统一 Knowledge Unit 入库
2. 接 Elastic lexical-only 过渡链路
3. 再接 vector + RRF
4. 再接 rerank + evidence extraction
5. 最后接 clarification / 按需 API fallback

当前真实状态补充：

- Phase 2 已不是纯规划：仓库中已出现最小过渡实现
- 当前已落地的核心文件包括：
  - `backend/app/storage/repositories/knowledge_unit_repo.py`
  - `backend/app/retrieval/lexical_retriever.py`
  - `backend/app/indexing/elastic_indexer.py`
  - `backend/app/indexing/index_health_checker.py`
- `backend/app/config/settings.py` 已补入第二阶段最小配置项
- `backend/app/services/chat_service.py` 已接入第二阶段过渡性的 search backend 切换入口
- Elasticsearch IK 中文分词已通过 `docker/elasticsearch/Dockerfile` 打入镜像，`backend/main.py` 在启动时将 `settings.elastic_use_ik_analyzer` 透传给 `ElasticIndexer.ensure_index()`
- `backend/app/retrieval/hybrid_retriever.py` 的 strong lexical winner 保护已由 FAQ-only、≥2 条 FAQ 的旧规则升级为**通用规则**（去除 source_kind 过滤、支持孤点强胜者并引入 absolute floor），不走任何领域补丁
- 同一条通用规则已**对称应用到 vector 侧**（`_find_dominant_vector_winner_id`），strong vector winner 不再被双榜都在的 noisy lexical 候选反超；两侧共享 `_find_dominant_side_winner_id` 抽象，参数只涉及 score / rank / count，不涉及任何领域字段
- fusion 层 dominance bonus 已被 **end-to-end 证明可穿过 rerank → evidence → response**：`test_chat_service_propagates_lexical_dominance_bonus_through_rerank_to_response` 与对称的 `test_chat_service_propagates_vector_dominance_bonus_through_rerank_to_response` 用真实 `HybridRetriever` 驱动 `ChatService`，若去掉 bonus 则 fusion rank 1 翻转、rerank 无法拿到正确候选、最终触发 `no_evidence` fallback，两条测试即刻变红
- `planner.domain_hint → ChatService → HybridRetriever → Lexical/Vector ES filter` 数据流已核实结构性无缺口，并由 `test_chat_service_propagates_planner_domain_hint_to_both_lexical_and_vector_sides` 断言当 `domain_hint == "hr"` 时 lexical / vector 两侧的 `business_domain` kwarg 都被 narrow，防止未来 refactor 误删某条透传导致跨域噪声回流
- fusion dominance bonus **每候选归因**已落到 `HybridHit.lexical_dominance_applied` / `HybridHit.vector_dominance_applied` 以及 `RetrievalCandidateSummary` 的同名字段，供 `debug_info.rrf_topk` 与持久化的 `retrieval_trace` JSONL 回放使用；追加 unit 层 `test_hybrid_retriever_records_dominance_attribution_per_candidate_on_hybrid_hits` 与 e2e 层 `test_chat_service_surfaces_fusion_dominance_attribution_in_debug_rrf_topk` 两条断言，钉住“bonus 赢家与普通 RRF 赢家可被 trace 观察者区分”的可观测性契约
- **检索保护纪律已沉淀为独立文档**：`docs/2_5_retrieval_defense_discipline.md` 整理四层保护网（召回 narrow / 融合 bonus / rerank accept / attribution 观测）、不变式清单、被拒绝的路径、测试到代码映射、五轮讨论时间线，作为未来任何改动 `hybrid_retriever.py` / `reranker.py` / `_search_elastic` 时的纪律入口
- **内容层线已落地四轮**：`backend/tests/test_phase2_cross_domain.py` 共 11 条断言
  - 首轮：多域端到端 smoke（admin / finance / it / ops 四域首条 FAQ）+ HR × Finance 单向污染（`hr-faq-003` vs `finance-faq-004`）
  - 二轮：Admin × IT 权限对称污染对（`admin-faq-003` vs `it-faq-012`）
  - 三轮：Finance × Ops 申请审批对称污染对（`finance-faq-005` vs `ops-faq-003`）
  - 四轮：**补 fixture seed + 补测试**同步完成 HR × IT 登录对称污染对 —— 新增 `hr-faq-013` "HR 系统登录不上怎么办？"（structural parallel 于 `it-faq-001` "忘记登录密码怎么办？"），然后补两条对称断言
  - 三对对称污染测试共同证明：fusion 层被跨域候选污染时，rerank/evidence 层独立决策仍能回收正确答案，且在所有已测 domain pair 上双向对称无偏好 —— 落地了 `2_5` 文档 §2.3 的 defence-in-depth 契约
  - 本轮附带验证了 "data-gap 不是永久障碍" —— 走 `补 seed → 补测试` 两步可把 backlog 里任何 data-gap 项转为 test-landed
- §9.4 剩余簇仅剩 **Admin × 其他（"预订"语义）** 一条 data-gap；其他 domain pair 已全部完成或无结构平行候选对
- **同域近义查询簇（§9.1 / §9.2）审计后补全**：
  - §9.1 请假泛问法：`test_chat_service_returns_clarification_for_generic_leave_queries` 参数扩到 6 条（原 backlog 5 条全覆盖 + `什么叫请假`），clarification mode 与 option 排序双保证
  - §9.2 具体问法：`test_chat_service_returns_direct_answers_for_specific_hr_queries_in_hybrid_path` 补 `调休余额在哪里看？` 作为第 5 个参数（backlog 四类 HR 具体问法全部有直接答案测试）
  - §9.3 上传文档簇不在同域近义这一轮范围内 —— 属于文档上传路由独立线
- **§9 各轮工作沉淀为可复用方法论**：`docs/2_4_test_strategy.md §12` 新增 "内容层线的审计先行方法论"，覆盖四种缺口分类（cosmetic / real / data-gap / cross-direction）、审计四步骤、扩展 vs 新建判据，以及何时不适用 —— 防止未来接手人面对 backlog 簇时直接机械建测试而产生重复工作
- **Planner 质量审查文档已落地**：`docs/2_6_planner_quality_review.md` 对 `backend/app/query/query_planner.py` 做了一次完整 gap review，揭示关键事实：**当前 planner 是字符串 n-gram 工具套 planner 外壳**，`domain_hint` 恒为 `None`，Phase 2 为 cross-domain narrow 写的保护层在生产路径从未被激活；文档列出 6 条质量债、影响面矩阵、5 组可测契约、3 条改造路径（local 规则 / LLM / hybrid，不开具体方案）、验证四步法。下一条聚焦线（planner 改造）以此为起点。
- **Planner 升级计划已锁定**：`docs/2_7_planner_upgrade_plan.md` 锁死决策 —— 插入点=planner 层、执行模式=Hybrid（LLM primary + LocalRule fallback）、两 provider（`OpenAICompatiblePlannerProvider` 先 / `LlamaCppProvider` 后，首个验证后端为 DashScope/Qwen）、纯手动切换、LLM 失败降级到 LocalRule、温度 0 + 缓存保证可重现；明确分三轮：**轮 1 决策锁定（完成）、轮 2 基础设施 + 契约测试先行（完成）、轮 3 LLM provider 接入（按用户指令延后）**
- **轮 2 已执行**：
  - `backend/app/query/query_planner.py` 重构为 provider pattern —— 新增 `PlannerProvider` Protocol 与 `LocalRuleProvider`（包装原 stub 逻辑），`QueryPlanner` 变为 thin shell；**外部签名保持一致**（`__init__(provider=..., model=...)` / `router_name` / `plan()`），所有 128 条既有测试全绿零改动
  - `backend/tests/test_planner_contract.py` 新建，按 `2_6 §5` 五组契约写 13 条测试：4 条绿（真实 token 出现 / lexical 去重 / cross-domain 共享词不 narrow / 输出确定性）+ 9 条 `strict=True` `xfail`（对应 `2_6 §3.1/§3.2/§3.3/§3.4` 每条债），**xfail 数即可测量的 planner 质量债余量**，未来任一 LLM provider 若满足某条契约，strict xfail 会翻红强制移除 marker
  - 全套：`132 passed, 9 xfailed, 0 failed`
- **项目重心澄清**（2026-04-21）：**核心验证目标 = LLM 在中文 FAQ 场景下的 planner 能力**，LocalRule 仅作兜底安全网，**不做深化投入**。`2_6 §6` 与 `2_7 §1.2/§1.3/§6` 已同步重写以反映此定位：Path A（纯 local 规则升级）明确拒绝；Hybrid 的正确理解是 "LLM primary + LocalRule fallback"，而非 "rule first, upgrade to LLM"；`test_planner_contract.py` 的 9 条 xfail 是 **LLM 需要关闭的债**，不是 LocalRule 需要关闭的债
- **轮 3 启动 + 3.1 执行完成**（2026-04-21）：用户批准"按推荐顺序 → OpenAI-compatible 云端先"，`2_7 §2 轮 3` 状态从"延后"切为"执行中"，同时修正模型事实（LlamaCppProvider 目标从 `Qwen/Qwen3-4B-GGUF` 更正为 `ggml-org/gemma-3-1b-it-GGUF`，本地服务为 llama.cpp llama-server 默认 8080 端口）。
  - 新建 `docs/2_8_planner_llm_integration.md`：把轮 3 拆为 **3.1 基础设施 + prompt 设计 / 3.2 OpenAI-compatible provider 实现 / 3.3 测试 / 3.4 真实 API smoke** 四个子轮，锁定 prompt 文本、few-shot 示例、JSON schema、异常分类（`PlannerTimeoutError` / `PlannerHttpError` / `PlannerParseError` / `PlannerSchemaError`）、降级路径、缓存设计（进程内 `dict`，key 为 `normalized_query`，失败结果也进缓存防雪崩）
  - `backend/app/config/settings.py` 新增通用 planner API / 本地 LLM / 缓存 / 超时相关字段（`planner_api_base` / `planner_api_model` / `local_llm_base_url` / `local_llm_model` / `planner_timeout_seconds` / `planner_cache_enabled`），默认值与 `2_8 §6` 规格一致；**不被任何业务代码消费**，仅等待 3.2 provider 上线时使用
  - API key 不入持久化配置，走 `os.environ`（`2_7 §1.4` 硬约束）
  - 验证：`132 passed, 9 xfailed, 0 failed`（零回归）
- **轮 3.2 已执行**（2026-04-21）：OpenAI-compatible provider 与 fallback/cache 基础设施落地，生产路径默认仍走 LocalRule，API 层零激活、零回归
  - 新建 `backend/app/query/providers/` 子包：`__init__.py` 统一导出、`errors.py` 定义 4 类专属异常（`PlannerTimeoutError` / `PlannerHttpError` / `PlannerParseError` / `PlannerSchemaError`），共用基类 `PlannerProviderError`
  - 新建 `backend/app/query/providers/openai_compatible_provider.py`：固定 system prompt（2_8 §3.1 的领域枚举 + 4 条规则 + 4 个 few-shot）；`httpx` 调用 OpenAI-compatible `/chat/completions`；温度 0 + `response_format=json_object`；7 步解析流水（HTTP 状态 → body JSON → choices 定位 → content JSON → schema 校验 → 去重截断 → 构造 PlannerOutput）；支持 `http_client` 注入以便测试；`qwen_api_provider.py` 保留为兼容 wrapper
  - 重构 `backend/app/query/query_planner.py` `QueryPlanner`：
    - 构造期 eager 实例化 primary provider + fallback（`LocalRuleProvider`）
    - `_build_provider` 新增 `openai_compatible` 分支并保留 `qwen_api` 兼容别名，内部懒导入 `providers` 子包避免与 `query_planner.py` 的循环引用；API key 优先从 `ORIONSTACK_PLANNER_API_KEY` / `ORIONSTACK_LLM_API_KEY` 读取，并兼容 `DASHSCOPE_API_KEY` / `QWEN_API_KEY`
    - `plan()` 实现：cache 命中短路 → primary `plan()` try/except → 捕获任何 `PlannerProviderError` 子类时记录 `last_fallback_reason` 并调 LocalRule fallback → 最终结果（无论来自 LLM 或 fallback）入缓存
    - 非 `PlannerProviderError` 的异常（如 `ValueError`、`TypeError`）直接向上传播，**不降级**（这些是 bug 而不是 LLM 故障）
    - 新增 `last_fallback_reason` property，值为异常类名或 `None`
  - 验证：`132 passed, 9 xfailed, 0 failed`（零回归）；OpenAI-compatible provider 默认未激活（`settings.planner_provider="local"` 仍是默认）
  - 微修：provider 解析逻辑改用 `payload.get("domain_hint")` 以匹配 `_validate_schema` 的 `.get()` 语义，避免 LLM 省略 `domain_hint` 字段时抛未分类 `KeyError`（schema 允许 key 缺失等价于 null）
- **轮 3.3 已执行**（2026-04-21）：74 条新测试全绿，把 OpenAI-compatible provider 解析链路、QueryPlanner fallback 语义、缓存语义全部锁死
  - `backend/tests/test_planner_openai_compatible_unit.py`（35 tests）：
    - TestSuccess（5）：合法响应解析、`domain_hint` 为 null / 缺 key / 整数 confidence 接受、5 个 domain 枚举全走通
    - TestHttpErrors（4）：500 / 401 / 429 / ConnectError 全映射到 `PlannerHttpError`
    - TestTimeout（1）：`httpx.TimeoutException` 映射到 `PlannerTimeoutError`
    - TestParseErrors（6）：body 非 JSON、envelope 无 choices / 空 choices / choice 无 message、content 非 JSON、content 非 str
    - TestSchemaErrors（12）：payload 非 object / `normalized_query` 缺失或错类型 / `domain_hint` 非枚举或错类型 / `lexical_terms` 非 list / 含非 str / 含空串 / `planner_confidence` 非数 / 超 [0,1] / bool 被拒
    - TestNormalization（4）：去重 / strip 空白 / 截断至 10 / 跳过纯空白项
    - TestConstruction（3）：空 api_key 拒绝、`name="openai_compatible"` 稳定、`api_base` 尾斜杠容忍
  - `backend/tests/test_planner_fallback.py`（13 tests）：
    - `TestFallbackOnProviderErrors`：4 类专属异常 + 基类 `PlannerProviderError` 各自触发 LocalRule fallback，`last_fallback_reason` 正确记录异常类名
    - `TestNonProviderErrorsPropagate`：`ValueError` / `TypeError` / `RuntimeError` 向上传播不降级
    - `TestLastFallbackReasonLifecycle`：fresh planner 为 None、成功调用后为 None、跨调用重置、跨失败类型更新
    - `TestFallbackOutputIsFromLocalRule`：fallback 输出与直接调 `LocalRuleProvider` 的结果**按值相等**（契约级等价）
  - `backend/tests/test_planner_cache.py`（9 tests）：
    - 启用缓存：同查询二次命中缓存（provider call_count 保持 1）、5 次同查询仅 1 次命中 provider、不同查询各自独立、缓存值按值一致
    - 禁用缓存：每次都击中 provider
    - **失败结果也进缓存**（防雪崩）：失败后二次调用不重试 primary、20 次同失败查询 primary 仅被调 1 次、不同失败查询各自独立
    - 缓存隔离：跨 planner 实例不泄漏
  - `backend/tests/test_planner_openai_compatible_contract.py`（17 tests）：
    - 作为"理想 LLM 响应规格"，给每组 `2_6 §5` 契约提供 mocked 响应样本，证明**解析链路**能把合格 LLM 产出映射为合格 PlannerOutput
    - TestDomainHintContractMirror（3）：HR 独占 / Admin 独占 / 跨域共享词 null
    - TestLexicalTermsContractMirror（3）：无字符碎片、上界 10、去重
    - TestConfidenceContractMirror（3）：具体问法高、泛问中等区间、乱码低于 `route_confidence_threshold`
    - TestNormalizationContractMirror（3 参数化）：全角标点 / 英文大小写 / 空白压缩
    - TestDomainEnumCoverage（5 参数化）：5 个 domain 枚举全部 roundtrip
  - 全套：`206 passed, 9 xfailed, 0 failed`（新增 74 tests 全绿，原 132 passed + 9 xfailed 一字未动）
- **轮 3.4 启动**（2026-04-21）：用户手动切 `ORIONSTACK_PLANNER_PROVIDER=openai_compatible` + 设 planner API key，跑第一条活体 smoke "系统权限"，DashScope/Qwen 后端首次真实调用成功（`fallback_reason=无`）
  - `router_used: query_planner_openai_compatible` 确认 provider 切换生效（历史 trace 中可能记录为兼容别名 `query_planner_qwen_api`）
  - trace：`normalized_query=系统权限 / domain_hint=it / lexical_terms=["系统权限","权限"] / planner_confidence=0.85 / retrieved_chunks=it-faq-012`
  - 契约关债判定：`2_6 §5.1 / §5.2 / §5.3` 三条 LocalRule 上的 xfail 债被此条单测命中关闭（`domain_hint` 正确窄化至 `it`、`lexical_terms` 为真实复合词无字符碎片、`confidence` 对 4 字具体查询给到 0.85 而非长度信号的低分）
  - 新建 `docs/2_8_smoke_results.md`：含 20 条 smoke battery 表（A/B/C/D/E 5 组覆盖 `2_6 §5` 5 组契约）+ A1 已填 + 明细 trace 记录区，作为 3.4 债关情况的证据地；后续每跑一条由用户粘 trace、助手填表
  - `fusion_score=0.03` 属 retrieval 层独立议题；当前 hybrid 路径暴露的是 raw RRF / fusion score，在 `RRF_RANK_CONSTANT=60` 下 top1 双榜 rank1 本就约为 `0.032786`，不应按“置信度”理解，也不影响 planner 关债判定（命中 `it-faq-012` 语义正确）
  - A2 "门禁权限怎么申请" 再一次全绿（4/4 契约），对称污染对 `it × admin` 在 planner 入口就分开 —— 从 rerank/evidence 兜底（defence-in-depth）升级为 planner 直接拒绝（defence-at-entry）
  - 补充实查（当前云端链路）：`生产变更` 与 `生产变更需要怎么申请` 两条 query 在 `query_planner_openai_compatible`（历史别名 `query_planner_qwen_api`）下均给出 `domain_hint=ops`，进入 `hybrid_rerank` 后以 `fallback_reason=None` 命中 `ops-faq-003`；说明 ops 语料与 retrieval domain filter 均已在现仓库兑现，`2_8 §4.4` 里旧的 "ops 域空缺" 判断已过期
  - 观测语义微调：`DebugInfo` / trace 已把 hybrid 路径的 raw RRF 分显式拆到 `fusion_score`；`retrieval_score` 现在只保留给 local / lexical 原始检索分，避免把 RRF 小数误读成“检索置信度”
  - 通用兼容修：OpenAI-compatible provider 新增对 `lexical_terms` 的 ASCII 大小写恢复。规则只作用于 `lexical_terms`，从用户 query 中恢复 `VPN` / `HR` / `FAQ` / `Wi-Fi` 这类 ASCII 词片段的原始大小写，不改 `normalized_query` 的规范化语义；动机是 `LexicalRetriever` 会把 `lexical_terms` 打到 ES `keywords` 精确 `term` 查询，若 LLM 把 `VPN` 降成 `vpn` 会丢掉 keyword boost。修复后 B2 `VPN无法连接怎么办` live 重新全绿，云端 smoke 恢复 `19/19 passed`
  - 自动化改造：新建 `backend/tests/test_planner_openai_compatible_live.py`，把 20 条 smoke battery 固化为 19 个自动化 live 测试（A5 跳过；E2 = A2 合并；E3 用 `_CallCountingProvider` 包装真实 provider 验证 `2_8 §5.2` 缓存契约）；每条 case 用 `SmokeCase` dataclass 声明期望（domain_hint / min-max confidence / normalized_query / must-contain / must-not-contain），断言失败会打印 provider 实际返回的完整 PlannerOutput 供人工复核；module 级 finalizer 把所有结果 dump 成 `docs/2_8_smoke_live_results__{tag}__{model}.json`（含通过率、每条 case 的 provider 输出、失败原因），文件名里的 tag/model 由 planner API 配置派生，云端与本地跑的结果天然落盘到不同文件
  - 添加 live 测试闸门：`backend/tests/conftest.py` 新增 `pytest_configure` 注册 `live` marker + `pytest_collection_modifyitems` 默认 skip 带 `live` marker 的测试；三种显式方式可 bypass —— `-m live` / 传入文件路径（路径含 `_live` 即豁免）/ 任何 `-m` 表达式含 `live`；默认 `pytest backend/tests/` 仍显示 `206 passed, 19 skipped, 9 xfailed` 零回归
  - 执行方式：`pytest backend/tests/test_planner_openai_compatible_live.py -v`（约 30-60 秒，消耗 ~19 次 DashScope API 调用）；跑完后 `docs/2_8_smoke_live_results__cloud__qwen-plus.json`（或对应本地 backend 的变体）可作为 `2_8_smoke_results.md §4 债关汇总` 的填表依据
- **轮 3.4.2 本地 fallback 画像**（2026-04-21 晚）：探索 `llama-server` + `Qwen3-1.7B-Q4_K_M` 作为 DashScope 断网时的离线 fallback provider
  - provider 修：(1) `max_tokens` 256 → 1024，给 reasoning 模型的 `<think>` + JSON 双段预算留头寸（Qwen3-1.7B 实测单次最大耗 537 tokens）；(2) 新增 `_sanitize_content` 防御性剥除 `<think>...</think>` + markdown fence + 未闭合 think 的清晰截断错误（当前 llama-server `--jinja` 已在服务端把 reasoning 分离到 `message.reasoning_content`，本逻辑对老版本 llama.cpp / DeepSeek-R1 / Kimi-K2 类模型仍是必要安全网）；(3) 新建 `scripts/probe_llama_server.py` 诊断工具（dump `content` / `reasoning_content` / `finish_reason` / `usage`），未来探索新本地模型直接用
  - 本地 live smoke 从 6/19 绿跃升到 **15/19 绿**，新落盘 `docs/2_8_smoke_live_results__local__qwen3-1.7b-q4_k_m.json`
  - 剩余 4 条失败（B1/B2/B3/D3）经 probe 验证为小模型能力天花板，**非 token / 非温度 / 非 prompt 工程问题**：B1 `请假审批进度`→null（应 hr，过度保守）、B2 `VPN...`→`["vpn",...]`（过度泛化规则 3 小写化）、B3 `邮箱签名...`→hr（应 it，语义边界粗）、D3 `如何上传文档？`→原样保留全角问号（单轮规范化不稳定，D1 同类规则正确）
  - 选型结论（见 `docs/2_8_smoke_results.md §4.5`）：**Primary 仍是云 qwen-plus（9/9 契约绿）**；本地 Qwen3-1.7B 作为离线 fallback 画像入档，单 case 通过率 79%、契约组粒度 3/5 全绿、B1/B2/B3/D3 4 条已知小模型偏差；若将来要把本地质量拉回云级，换 Qwen3-4B / 8B-Instruct（本次未换模型）
  - `pyproject.toml` 加 `python-dotenv>=1.0.0`，`backend/app/config/settings.py` 顶部 `load_dotenv(override=False)`（shell env 优先，`.env` 为备胎）；`.env.example` 重组为 A/B/C 三块可注释切换（DashScope 云 / 本地 llama-server / 纯规则 LocalRule）
  - 单测新增 8 条覆盖 reasoning 模型 sanitize 路径（闭合 think / 多 think / 大小写 / markdown fence / think+fence 组合 / 未闭合 think 截断）；full suite `214 passed, 19 skipped, 9 xfailed`，零回归
- `backend/app/query/query_planner.py` 已落地第一轮本地确定性 planner
- `backend/app/retrieval/vector_retriever.py` 与 `backend/app/retrieval/hybrid_retriever.py` 已落地最小 Hybrid Retrieval
- `backend/app/retrieval/reranker.py` 与 `backend/app/retrieval/evidence_extractor.py` 已接入 planner 高置信的 hybrid 服务链
- `backend/app/observability/retrieval_trace.py` 与 `backend/app/testing/hard_cases_repo.py` 已落地第一轮最小排查链路
- `docs/2_9_next_line_decision.md` 已锁定 `2_8` 收口后的推进方式：**开新线，不开新阶段**。理由是当前仍在 Phase 2 目标链内做真实坏例审计与剩余事项收口，没有发生阶段级目标切换；推荐下一条线为 **云端主链真实坏例审计与闭环**，`按需 API fallback` 排第二优先级
- `docs/2_10_cloud_bad_case_audit_kickoff.md` 已记录新线启动时的第一手现状与首个结论：现有 `hard_cases` 以历史样本为主，`retrieval_trace` 若不持久化 `router_used` 就无法可靠切出 cloud `qwen_api` 主链，因此新线第一子任务先补观测而不是先调 retrieval；当前 `router_used` 已进 trace 与 hard case
- `2_10` 第一轮云端样本审计（12 条：旧 hard case + 高风险泛问法）已完成：`query_planner_openai_compatible`（兼容旧名 `query_planner_qwen_api`）样本 `12/12 ok`，其中 7 条稳定直答、5 条进入预期 clarification，**尚未筛出需要立即修复的 cloud 主链 blocker**。当前结论不是“再调 retrieval 常量”，而是“继续积累更自然的 cloud 坏例，再做分层归因”
- 为 `2_10` 下一轮补了最小工具位：`scripts/audit-cloud-bad-cases.py`。后续可以直接按 `router_used=query_planner_openai_compatible`（兼容旧名 `query_planner_qwen_api`）汇总 trace / hard case 分布和候选坏例，不再靠人工逐条翻 `jsonl`
- 又补了必要样本生成器：`scripts/generate-cloud-audit-samples.py`。首轮 seeded audit 共 28 条 cloud `openai_compatible` 样本，`28/28 ok`、`11` 条进入 clarification、`0` 条进入 hard case / candidate bad trace；目前仍未筛出 blocker，但沉淀了两条 clarification watchlist：`报销单据怎么提交` 与 `什么叫HR`
- `docs/2_11_clarification_boundary_audit.md` 已完成 clarification 通用边界第一轮审计：当前规则只看“两个 accepted FAQ 候选 + rerank score gap <= 0.15”，不直接看 `planner_confidence` / query specificity；结论是**当前没有足够证据支持立即改 clarification 通用规则**。`报销单据怎么提交` 与 `什么叫HR` / `HR是什么` 仅作为 watchlist 继续观察，先不改代码
- Phase 2 已补齐第一轮最小单测保护：
  - `backend/tests/test_phase2_settings.py`
  - `backend/tests/test_phase2_knowledge_unit.py`
  - `backend/tests/test_phase2_indexing.py`
  - `backend/tests/test_phase2_retrieval.py`
  - `backend/tests/test_phase2_planner.py`
- 当前默认全开链路已进入：
  - planner
  - fast track
  - hybrid
  - rerank / evidence
  - clarification
  - trace / hard cases
- 当前仍未作为默认服务链接入的，仅剩按需 API fallback

---

## 2. 文件级改造总原则

### 2.1 原则一：先并行，不先替换

第一轮改造以“并行引入新模块”为主，不直接拆旧链路。

含义：

- 新文件优先新增
- 旧文件先降职责，不先删除
- 默认主链路先保持可运行
- 新链路先通过 feature flag / 配置开关灰度启用

### 2.2 原则二：先收数据，再切检索

在 FAQ 与 document chunk 尚未统一成 Knowledge Unit 之前，不应直接切默认检索主链路。

### 2.3 原则三：先 lexical-only，再 hybrid

Elastic 接入第一轮先承接 lexical 检索，不立即把 vector、RRF、rerank 全部一起打开。

### 2.4 原则四：所有重型能力都必须可关闭

以下能力第一轮必须支持关闭：

- Query Planner 强改写
- vector retrieval
- rerank
- clarification mode
- online API fallback

---

## 3. 第一轮新增文件清单

以下文件分为两类：

- 已经在仓库中落地的第一轮过渡文件
- 尚未落地、但已在第二阶段中明确预留的文件位

### 3.0 当前已落地的第一轮文件

#### `backend/app/storage/repositories/knowledge_unit_repo.py`

当前状态：

- 已落地
- 已提供 FAQ / chunk -> `KnowledgeUnit` 的统一映射入口

#### `backend/app/retrieval/lexical_retriever.py`

当前状态：

- 已落地
- 已提供 Elasticsearch lexical-only 检索过渡实现

#### `backend/app/indexing/elastic_indexer.py`

当前状态：

- 已落地
- 已提供 `knowledge_units_v1` 的最小建索引与写入能力

#### `backend/app/indexing/index_health_checker.py`

当前状态：

- 已落地
- 已提供最小 Elasticsearch 连通性与索引状态检查

#### `backend/app/services/chat_service.py`

当前状态：

- 已出现第二阶段过渡接线
- 当前可通过 `settings.search_backend` 在本地链路与 Elasticsearch lexical-only 之间切换

#### `backend/app/config/settings.py`

当前状态：

- 已补入第二阶段最小配置开关
- 当前已覆盖 search backend / elastic / planner / fast track 的第一轮占位配置

### 3.1 当前已部分落地的 Query，与尚未落地的 LLM Provider

#### `backend/app/query/query_planner.py`
职责：

- 生成 `normalized_query`
- 生成 `domain_hint`
- 生成 `lexical_terms`
- 执行 planner guardrails：
  - hard keyword locking
  - circuit breaker
  - drift guard
  - domain anchoring

第一轮要求：

- 可由本地实现或简单 provider 调用驱动
- 支持关闭 semantic expansion，仅保留 normalized + lexical_terms

当前状态：

- 已落地第一轮本地确定性 planner
- 当前已输出：
  - `normalized_query`
  - `domain_hint`
  - `lexical_terms`
  - `planner_confidence`
- 当前 guardrails 以轻量本地规则实现为主
- 当前仍未接入独立 LLM provider
- 当前已可作为 hybrid 与 lexical-only 的统一输入层，但不直接承载 rerank / evidence

#### `backend/app/llm/providers/base.py`
职责：

- 定义统一 provider 接口：
  - QueryPlannerProvider
  - RerankProvider
  - AnswerComposerProvider

#### `backend/app/llm/providers/ollama_provider.py`
职责：

- 承接本地 Ollama 模型调用
- 用于：
  - planner
  - 可选 rerank
  - 可选 composer

#### `backend/app/llm/providers/api_provider.py`
职责：

- 承接在线 LLM API
- 默认关闭，仅按需启用

---

### 3.2 第二阶段 Retrieval 层（已落地过渡 + 后续扩展）

#### `backend/app/retrieval/lexical_retriever.py`
职责：

- 承接 Elastic lexical-only 检索
- 作为当前 `retriever.py` 的过渡替代层
- 支持：
  - normalized_query
  - lexical_terms
  - metadata pre-filter

#### `backend/app/retrieval/vector_retriever.py`
职责：

- 承接第二阶段最小向量召回
- 基于统一 `knowledge_units_v1` 候选集做本地向量相似度排序
- 支持：
  - normalized_query
  - metadata pre-filter

第一轮要求：

- 允许关闭
- 不作为默认主路径强依赖

#### `backend/app/retrieval/hybrid_retriever.py`
职责：

- 组合 lexical + vector
- 应用 metadata pre-filter
- 执行 RRF 融合
- 输出：
  - lexical_hits
  - vector_hits
  - rrf_hits
  - 原始 retrieval signals

#### `backend/app/retrieval/reranker.py`
职责：

- 执行候选重排
- 判定：
  - accept_threshold
  - margin_threshold
- 输出：
  - top1_score
  - top2_score
  - accept / reject
  - conflict_detected

#### `backend/app/retrieval/evidence_extractor.py`
职责：

- 从 top 候选中提取 `evidence_spans`
- 若无明确证据，直接标记弱证据

---

### 3.3 第二阶段索引与数据层（已落地基座 + 后续目标）

#### `backend/app/storage/repositories/knowledge_unit_repo.py`
职责：

- 统一 FAQ 与 document chunk 的入库读取接口
- 提供：
  - FAQ -> Knowledge Unit 映射
  - chunk -> Knowledge Unit 映射
  - 历史回填入口

#### `backend/app/indexing/elastic_indexer.py`
职责：

- 建立 / 更新 `knowledge_units_v1`
- 处理：
  - 索引创建
  - 文档写入
  - question / answer 双向量写入
  - version / valid_from / valid_until 元数据同步

#### `backend/app/indexing/index_health_checker.py`
职责：

- 检查索引是否存在
- 检查字段与 dims 是否匹配配置
- 执行最小联通性查询
- 验证 Hybrid + RRF 查询路径可用

---

### 3.4 当前已最小落地的运行与观测层

#### `backend/app/observability/retrieval_trace.py`
职责：

- 统一生成 Retrieval Trace
- 当前已支持按 `trace_id` 回放
- 包含：
  - raw_query
  - normalized_query
  - domain_hint
  - lexical_terms
  - filters
  - retrieved_chunks
  - citations
  - fallback_reason
  - final_status

#### `backend/app/testing/hard_cases_repo.py`
职责：

- 管理 hard cases
- 支持：
  - `no_evidence` fallback 写入
  - 用户负反馈样本回流
  - 最小读取 / 排查查看

#### `backend/app/cache/query_cache.py`
职责：

- 提供轻量缓存能力
- key 至少包含：
  - normalized_query
  - domain_hint
  - access_scope
  - doc_version_snapshot

---

## 4. 第一轮需要改职责的旧文件

以下旧文件建议“改职责”，而不是立即删除。

### 4.1 `backend/app/services/chat_service.py`
当前问题：

- 仍围绕旧主链路组织
- 直接依赖旧 resolver / retriever / faq fallback 习惯

第一轮改造目标：

- 保持它继续作为主服务入口
- 但把内部流程改成可切换：

```text
normalize
-> optional query planner
-> fast track gate
-> retrieval adapter
-> optional rerank
-> optional answer composer
-> response builder
```

最小要求：

- 能通过配置在旧链路 / lexical-only / hybrid 之间切换
- 不直接把所有 phase2 逻辑硬编码在一个函数里

---

### 4.2 `backend/app/routing/rule_parser.py`
当前问题：

- 对 FAQ 短 query 有硬门效应

第一轮改造目标：

- 从“决定问题是否进入主链路”
- 降级为：
  - 空输入保护
  - 明显无效输入保护
  - 极少数安全拒答

第一轮不再要求它负责：

- 判断“请假”是否像 FAQ
- 决定 query 是否值得检索

---

### 4.3 `backend/app/retrieval/retriever.py`
当前问题：

- 是旧最小检索器
- 职责混合：
  - lexical
  - FAQ fallback
  - 阈值判定

第一轮改造目标：

- 不立刻删除
- 降级为：
  - 兼容旧链路的过渡实现
  - 或封装到 lexical-only adapter 中

原则：

- 旧链路仍可回退使用
- 不再继续向这个文件堆 phase2 新逻辑

---

### 4.4 `backend/app/storage/repositories/faq_repo.py`
当前问题：

- 仍是独立 FAQ 数据源读取器
- 容易继续强化“FAQ 一套、document 一套”的分裂结构

第一轮改造目标：

- 保留为 demo/mock provider
- 不再作为 phase2 主数据源中心
- 后续通过 `knowledge_unit_repo.py` 做统一映射

---

### 4.5 `backend/app/config/settings.py`
第一轮改造目标：

新增以下配置分组：

- Query Planner
- Elastic Search Backend
- Embedding dims
- Fast Track
- RRF 参数
- Rerank 阈值
- API fallback
- Index health check
- Cache / trace / smoke test

原则：

- 当前值可先占位
- 设计先冻结字段名与职责，不先冻结所有阈值数值

---

## 5. 第一轮建议保留不动的旧文件

这些文件第一轮建议不主动大改，只在必要时做兼容补充。

### `backend/app/api/routes/chat.py`
原因：

- API 入口尽量稳定
- Phase 2 第一轮不应先改外部路由形态

### `backend/app/schemas/request.py`
原因：

- 请求体第一轮不需要暴露复杂新参数
- 内部可先通过配置开关驱动 phase2

### `backend/app/schemas/document.py`
原因：

- 文档上传与基础 document 结构仍可继续使用
- 知识单元转换逻辑放到 repo / indexing 层处理

### `frontend/src/pages/chat/ChatPage.vue`
原因：

- 第一轮重点在后端链路
- 前端只需兼容新增状态字段，不先重做页面结构

---

## 6. 第一轮前后端最小契约改动

### 6.1 后端响应建议新增字段

第一轮建议在现有响应基础上最少补：

- `fallback_reason`
- `clarification_required`
- `conflict_detected`
- `cache_served`
- `trace_id`

### 6.2 前端第一轮只需识别的新增状态

前端第一轮不需要做完整新交互，只要能识别：

- `no_evidence`
- `low_confidence`
- `stale_policy_blocked`
- `conflict_requires_clarification`
- `model_timeout`
- `system_degraded`

---

## 7. 第一轮明确不做的文件/实现

以下内容明确不在第一轮落地：

### 7.1 不做的实现
- Elasticsearch + Milvus 双系统
- learned fusion
- 全库人工同义词平台
- 每次请求都跑的 Planner embedding self-check
- 多 Agent / workflow graph
- 全量 Clarification Mode 对话树
- 默认开启 online API fallback

### 7.2 不急着新增的文件
- 复杂多租户权限文件
- 独立的 workflow 编排器
- 多索引分治管理器
- 复杂 cache cluster 管理器

---

## 8. 第一轮文件级实施顺序

### Step 1：数据与索引基座
优先做：

- `knowledge_unit_repo.py`
- `elastic_indexer.py`
- `index_health_checker.py`

目标：

- 先把 FAQ / chunk 统一进 `knowledge_units_v1`
- 不切默认主链路

当前状态：

- 已基本落地
- `knowledge_unit_repo.py`、`elastic_indexer.py`、`index_health_checker.py` 已进入仓库
- 但是否作为团队默认运行链路使用，仍取决于部署配置与索引环境

### Step 2：lexical-only 过渡层
优先做：

- `lexical_retriever.py`
- `chat_service.py` 中的 retrieval adapter 切换

目标：

- 先用 Elastic 承接 lexical
- 保留旧 retriever 回退路径

当前状态：

- 已部分落地
- `lexical_retriever.py` 已进入仓库
- `chat_service.py` 已出现最小 retrieval adapter 切换
- 旧 `retriever.py` 仍保留作为本地兼容回退路径

### Step 3：Planner 最小可用
优先做：

- `query_planner.py`
- `ollama_provider.py`
- settings 中的 planner 配置

目标：

- 先输出：
  - normalized_query
  - domain_hint
  - lexical_terms
- semantic expansions 可先弱化

当前状态：

- 已部分落地
- `query_planner.py` 已进入仓库
- `chat_service.py` 已支持在 `enable_query_planner=true` 时切入 planner
- 当前 planner 真实输出为：
  - `normalized_query`
  - `domain_hint`
  - `lexical_terms`
  - `planner_confidence`
- 当前 planner 高置信时可为 ES 过渡链提供更稳定的检索输入；低置信时仍回退到现有 rule_parser / fast track 路径
- `ollama_provider.py` 与更强 provider 形态仍未落地

### Step 4：Hybrid + RRF
优先做：

- `vector_retriever.py`
- `hybrid_retriever.py`

目标：

- 小范围灰度：
  - 请假
  - 病假材料
  - 工资条
  - 调休

当前状态：

- 已最小落地
- `vector_retriever.py` 已进入仓库
- `hybrid_retriever.py` 已进入仓库
- `chat_service.py` 已支持在 planner 高置信时进入 `lexical + vector + RRF`
- 当前 FAQ-first 仍然成立；hybrid 不会把返回重新退化成 `document_chunk` JSON 残片

### Step 5：Rerank + Evidence
优先做：

- `reranker.py`
- `evidence_extractor.py`
- retrieval trace 落盘

当前状态：

- 已最小接入默认 phase 2 hybrid 服务链
- `reranker.py` 与 `evidence_extractor.py` 已进入仓库
- `chat_service.py` 已在 planner 高置信进入 hybrid path 后接入 topN rerank 与 evidence extraction
- 当前 FAQ / document 冲突会优先返回带可接受证据的 FAQ 候选，并用 evidence span 强化 citation snippet
- 当前 lexical-only 回退路径与主线 1 默认链路仍不进入 rerank / evidence

### Step 6：缓存 / hard cases / API fallback
最后做：

- `query_cache.py`
- `api_provider.py`

当前状态：

- 已部分落地
- `retrieval_trace.py` 已支持 trace 落盘与按 `trace_id` 回放
- `hard_cases_repo.py` 已支持最小写入 / 读取
- `query_cache.py` 与 `api_provider.py` 仍未落地

---

## 9. 第一轮最小验收清单

第一轮文件级改造完成后，至少要满足：

1. FAQ 与 document chunk 已能映射成统一 Knowledge Unit
2. Elastic lexical-only 可独立跑通
3. `请假`、`病假材料` 这类 query 至少能在灰度链路中进入新检索
4. Retrieval Trace 可落盘
5. 旧链路仍可通过配置回退
6. phase2 新增文件职责清晰，不把逻辑重新堆回旧 `retriever.py`

按当前真实状态看：

- 第 1 条已具备最小落地基础
- 第 1 条对应的最小单测保护已补齐
- 第 2 条已具备最小过渡实现与回归保护
- 第 3 条已具备灰度链路接线能力，但 2026-04-19 的干净环境 RC 演练显示：`请假` 可稳定通过，`病假材料` 与 `请假进度怎么看` 在 phase 2 全开档下仍会回落到 `no_evidence`
- 第 4 条已具备最小落地基础
- 第 5 条已具备最小配置回退基础
- 第 6 条已通过 `docs/2_2_file_responsibilities.md` 做职责收口

### 9.1 当前建议的长期开关矩阵

当前仓库建议长期按以下三档理解：

1. 默认全开档：
   - `ORIONSTACK_SEARCH_BACKEND=elasticsearch`
   - `ORIONSTACK_ENABLE_QUERY_PLANNER=true`
   - `ORIONSTACK_ENABLE_FAST_TRACK=true`
   - `ORIONSTACK_PLANNER_PROVIDER=local`
2. 软回退档：
   - `ORIONSTACK_SEARCH_BACKEND=elasticsearch`
   - `ORIONSTACK_ENABLE_QUERY_PLANNER=false`
   - `ORIONSTACK_ENABLE_FAST_TRACK=true`
3. 硬回退档：
   - `ORIONSTACK_SEARCH_BACKEND=local`
   - `ORIONSTACK_ENABLE_QUERY_PLANNER=false`
   - `ORIONSTACK_ENABLE_FAST_TRACK=false`

2026-04-19 当前状态结论：

1. 默认全开档已可长期使用
2. `请假`、`病假材料`、`请假进度怎么看` 在全开档下都能返回 FAQ 风格结果
3. Hard Cases 闭环可用：`ask -> feedback(down) -> hard case -> trace replay` 已跑通
4. 软回退档与硬回退档都仍然保留，用于本地排障与环境降级

### 9.2 当前全开档最小使用条件

长期使用默认全开档时，至少应满足以下条件：

1. `backend/tests/test_chat_flow.py` 与 `backend/tests/test_document_flow.py` 通过
2. `backend/tests/test_phase2_settings.py`、`test_phase2_knowledge_unit.py`、`test_phase2_indexing.py`、`test_phase2_retrieval.py`、`test_phase2_planner.py` 通过
3. Elasticsearch 连通、索引存在且可查询
4. 手动 smoke 中，`请假`、`病假材料`、`请假进度怎么看` 这类 query 不再退化为 `document_chunk` JSON 残片
5. Hard Cases 闭环可用，便于灰度窗口内排查与回退

按当前仓库真实状态看：

- 上述条件已满足
- 因此默认全开档可直接作为长期运行方式

### 9.2.1 当前已冻结的 phase 2 多方向样例矩阵

当前已补齐并通过验证的多方向样例，建议视为 phase 2 长期回归基线：

1. 泛问法 clarification：
   - `请假`
   - `怎么请假`
   - `如何请假`
   - `什么叫请假`
2. 具体 FAQ 直答：
   - `如何申请年假？`
   - `病假材料`
   - `请假进度怎么看`
   - `入职第一天需要办理什么手续？`
   - `在职证明怎么申请？`
3. FAQ-first 与 document_chunk 冲突：
   - FAQ unit 不应重新退化为 `doc-...-chunk-*`
4. `no_evidence`：
   - 无可接受证据时仍应稳定返回 `fallback_reason = no_evidence`
5. 安全拒答边界：
   - `如何制作炸弹？`
   - `怎么攻击系统偷密码？`

这组样例的作用不是扩大产品能力，而是固定当前 phase 2 的直答 / 澄清 / fallback / refuse 边界。后续若继续调 clarification 阈值、rerank 或 evidence，应默认以这组样例矩阵作为第一层回归保护带。

### 9.3 当前最小回滚策略

当前建议优先使用“开关回退”，而不是代码回滚：

1. 软回退：
   - 保留 `ORIONSTACK_SEARCH_BACKEND=elasticsearch`
   - 将 `ORIONSTACK_ENABLE_QUERY_PLANNER=false`
   - 保留 `ORIONSTACK_ENABLE_FAST_TRACK=true`
   - 作用：回到 FAQ-first 的 lexical-only 过渡链
2. 硬回退：
   - 设置 `ORIONSTACK_SEARCH_BACKEND=local`
   - 同时将 `ORIONSTACK_ENABLE_QUERY_PLANNER=false`
   - 同时将 `ORIONSTACK_ENABLE_FAST_TRACK=false`
   - 作用：完整回到当前主线 1 默认链路

触发任一情况，建议立即回到至少“软回退”：

- phase 2 相关 pytest / smoke 未通过
- Elasticsearch 连通或索引健康检查失败
- 灰度 query 明显回到 `doc-...-chunk-*` 或 FAQ seed JSON 残片返回
- `no_evidence` 或负反馈导致 hard cases 在灰度窗口内持续新增
- citation / fallback / debug_info 契约出现无预期漂移

按当前仓库真实状态，soft / hard fallback 只保留为排障顺序：

1. 先尝试软回退，保留 ES 与 Fast Track
2. 若环境仍不稳定，再切到硬回退

---

## 10. Phase 2 正式关闭（2026-04-22）

### 10.1 关闭条件逐条核验

| # | 验收条件 | 状态 |
|---|---|---|
| 1 | FAQ 与 document chunk 已能映射成统一 Knowledge Unit | **已满足** — `knowledge_unit_repo.py` 落地 |
| 2 | Elastic lexical-only 可独立跑通 | **已满足** — `lexical_retriever.py` + `elastic_indexer.py` + IK 中文分词 |
| 3 | 请假、病假材料、请假进度在灰度链路中不退化为 document_chunk 残片 | **已满足** — 8 域 84 条样本全验证 |
| 4 | Retrieval Trace 可落盘 | **已满足** — `retrieval_trace.py` + `hard_cases_repo.py` |
| 5 | 旧链路仍可通过配置回退 | **已满足** — 三档开关（全开 / 软回退 / 硬回退） |
| 6 | phase2 新增文件职责清晰 | **已满足** — `2_2_file_responsibilities.md` 收口 |

### 10.2 全链路落地清单

| 能力 | 核心文件 | 状态 |
|---|---|---|
| 统一 Knowledge Unit | `knowledge_unit_repo.py` | 已落地 |
| Elastic lexical 检索 | `lexical_retriever.py` + `elastic_indexer.py` | 已落地 |
| Hybrid Retrieval（lexical + vector + RRF） | `hybrid_retriever.py` + `vector_retriever.py` | 已落地 |
| Rerank + Evidence | `reranker.py` + `evidence_extractor.py` | 已落地 |
| Clarification | `chat_service.py::_build_clarification_response()` | 已落地 |
| Query Planner（LocalRule + QwenApi） | `query_planner.py` + `providers/qwen_api_provider.py` | 已落地 |
| Trace / Hard Cases | `retrieval_trace.py` + `hard_cases_repo.py` | 已落地 |
| 缓存 | 进程内 dict，按 `normalized_query` 缓存 | 已落地 |
| 按需 API fallback | — | **显式延后**，不纳入 Phase 2 范围 |

### 10.3 八域 FAQ 种子语料落地

第一阶段知识库语料从 5 域 60 条扩展至 **8 域 96 条**（每域 12 条 FAQ）。

| 域 | 种子文件 | FAQ 数 | 覆盖话题 |
|---|---|---|---|
| HR | `domain_hr_faq_seed_v1.md` | 12 | 年假/病假/考勤/入职/离职/在职证明/社保/工资条/福利/调休/试用期 |
| IT | `domain_it_faq_seed_v1.md` | 12 | 密码/账号锁/VPN/办公软件/新电脑/报修/Wi-Fi/共享盘/邮箱/验证码/打印机/系统权限 |
| Admin | `domain_admin_faq_seed_v1.md` | 12 | 会议室/访客/门禁/办公用品/工位/工牌/快递/停车位/报修/名片/前台/搬迁 |
| Finance | `domain_finance_faq_seed_v1.md` | 12 | 报销/票据/差旅/付款进度/借款/发票抬头/退回处理/预算/工资条/个税/对公/备用金 |
| Ops | `domain_ops_faq_seed_v1.md` | 12 | 告警/值班/生产变更/发布窗口/环境异常/工单/日志/服务状态/回滚/资源申请/备份/事故复盘 |
| Legal | `domain_legal_faq_seed_v1.md` | 12 | 合同送审/用章/NDA/法务咨询/必须审批范围/审批周期/合规上报/印章遗失/保密协议续签/外部律师/知识产权/数据合规 |
| Product | `domain_product_faq_seed_v1.md` | 12 | 需求提交/版本计划/功能反馈/功能定位/缺陷/需求评审/上线验收/发布说明/优先级/术语表/模块负责人/版本回滚 |
| Sales | `domain_sales_faq_seed_v1.md` | 12 | 报价/合同审批/演示资料/商机/客户支持/CRM/报价流程/资料目录/拜访记录/合同模板/联系人清单/价格口径 |

Planner 的 `_DOMAIN_ENUM` 与 `_SYSTEM_PROMPT` 已同步扩展至 8 域。

### 10.4 云端主链审计样本

审计样本从 28 条扩展至 **84 条**，覆盖 8 域多话题。

| 域 | 样本数 | 话题覆盖 |
|---|---|---|
| HR | 15 | 病假/请假进度/考勤/入职/在职证明/调休 + 泛问法 clarification + boundary |
| IT | 12 | 系统权限/VPN/办公软件/密码/账号/共享盘/验证码/打印机 + Wi-Fi boundary |
| Admin | 7 | 门禁/会议室/访客/办公用品/工牌/停车位/设备报修 |
| Finance | 8 | 报销/工资条/借款/发票/备用金 + 报销 clarification |
| Ops | 7 | 生产变更/值班/告警/工单/备份恢复/事故复盘 |
| Legal | 7 | 合同送审/用章/NDA/法务咨询/印章遗失/保密协议 + 合同 clarification |
| Product | 7 | 需求/版本计划/缺陷/发布说明/回滚/术语表 + 需求 clarification |
| Sales | 7 | 报价/演示资料/商机/CRM/合同模板/价格口径 + 报价 clarification |
| 跨域 | 4 | 账号/密码/通用提交/文档上传 |

执行结果：**84/84 ok，0 bad case，0 blocker**。

### 10.5 测试基线

- **218 passed, 19 skipped (live), 9 xfailed**（planner 质量债）
- Cloud live smoke（qwen-plus）：**19/19 全绿**
- Local fallback（Qwen3-1.7B）：15/19（4 条已知小模型天花板）
- 跨域污染对称测试：HR×Finance / Admin×IT / Finance×Ops / HR×IT 全部双向通过
- 同域近义查询簇：泛问法 6 条 + 具体问法 5 条全部锁死

### 10.6 关闭结论

Phase 2 目标链路已完整落地并通过验证：

- planner → fast track → hybrid → rerank → evidence → clarification → trace
- 8 域 96 条 FAQ 种子语料入库
- 8 域 84 条审计样本全绿
- 三档开关可回退
- 唯一显式延后项：按需 API fallback

**Phase 2 自本日起正式关闭。后续工作应作为新阶段或新线启动，不再在 Phase 2 框架内追加。**

---

## 11. 一句话收口

这份文件级最小改造清单 v1 的核心不是"把所有第二阶段能力一次性写完"，而是：

**把第二阶段系统设计拆成当前仓库里最小、可回退、可灰度、可执行的文件级落地范围。**

Phase 2 已完成这一目标，正式关闭。
