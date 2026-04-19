from __future__ import annotations

from app.config.settings import settings
from app.guardrails.normalize import normalize_query
from app.query.query_planner import PlannerOutput, QueryPlanner
from app.retrieval.citation_mapper import map_citation
from app.retrieval.retriever import Retriever
from app.routing.contracts import IntentDecision
from app.routing.resolver import RouteResolver
from app.schemas.request import ChatAskRequest
from app.schemas.response import ChatAskResponse, DebugInfo
from app.storage.repositories.chunk_repo import ChunkRepository
from app.storage.repositories.faq_repo import FAQRepository
from app.storage.repositories.knowledge_unit_repo import KnowledgeUnitRepository


class ChatService:
    _ELASTIC_FAQ_PREFERENCE_MAX_SCORE_GAP = 0.35
    _SMALL_QUERY_RULES = (
        {
            "queries": ("请假", "怎么请假", "如何请假"),
            "search_query": "请假 申请 审批 流程",
            "lexical_terms": ("请假", "申请", "审批", "流程"),
            "business_domain": "hr",
        },
        {
            "queries": ("病假材料",),
            "search_query": "病假 证明 材料 提交",
            "lexical_terms": ("病假", "证明", "材料", "提交"),
            "business_domain": "hr",
        },
        {
            "queries": ("请假进度怎么看",),
            "search_query": "请假 进度 审批 记录 查询",
            "lexical_terms": ("请假", "进度", "审批", "记录", "查询"),
            "business_domain": "hr",
        },
    )
    _REFUSAL_TERMS = {
        "unsafe_request": (
            "炸弹",
            "爆炸物",
            "攻击系统",
            "木马",
            "勒索",
            "窃取密码",
            "毒品",
            "伪造证件",
            "自杀",
        )
    }

    def __init__(self) -> None:
        self._faq_repo = FAQRepository()
        self._chunk_repo = ChunkRepository()
        self._ku_repo = KnowledgeUnitRepository(
            faq_repo=self._faq_repo, chunk_repo=self._chunk_repo
        )
        self._retriever = Retriever(self._faq_repo, self._chunk_repo)
        self._resolver = RouteResolver()
        self._query_planner = None
        if settings.enable_query_planner:
            self._query_planner = self._create_query_planner()
        self._lexical_retriever = None
        self._hybrid_retriever = None
        self._reranker = None
        if settings.search_backend == "elasticsearch":
            self._lexical_retriever = self._create_lexical_retriever()
            self._hybrid_retriever = self._create_hybrid_retriever()
            if self._hybrid_retriever is not None:
                self._reranker = self._create_reranker()

    def _create_query_planner(self) -> QueryPlanner:
        return QueryPlanner(
            provider=settings.planner_provider,
            model=settings.planner_model,
        )

    def _create_lexical_retriever(self):
        from app.retrieval.lexical_retriever import LexicalRetriever
        from elasticsearch import Elasticsearch

        es = Elasticsearch(settings.elastic_url)
        return LexicalRetriever(es, index_name=settings.elastic_index)

    def _create_hybrid_retriever(self):
        from app.retrieval.hybrid_retriever import HybridRetriever
        from app.retrieval.lexical_retriever import LexicalRetriever
        from app.retrieval.vector_retriever import VectorRetriever
        from elasticsearch import Elasticsearch

        es = Elasticsearch(settings.elastic_url)
        lexical_retriever = LexicalRetriever(es, index_name=settings.elastic_index)
        vector_retriever = VectorRetriever(es, index_name=settings.elastic_index)
        return HybridRetriever(lexical_retriever, vector_retriever)

    def _create_reranker(self):
        from app.retrieval.reranker import Reranker

        return Reranker()

    def ask(
        self, payload: ChatAskRequest, *, trace_id: str, debug_enabled: bool
    ) -> ChatAskResponse:
        normalized_query = normalize_query(payload.raw_query)
        document_ids = [
            document_id.strip()
            for document_id in payload.document_ids
            if document_id.strip()
        ]
        if not normalized_query:
            return ChatAskResponse(
                response_status="refused",
                trace_id=trace_id,
                answer="请输入更明确的问题后再试。",
                citations=[],
                debug_info=self._build_debug_info(
                    debug_enabled,
                    normalized_query,
                    route_result="refused",
                    chunk_ids=[],
                    router_used="rule_parser",
                    route_confidence=0.0,
                    fallback_reason="empty_after_normalization",
                ),
            )

        refusal_reason = self._match_refusal_reason(normalized_query)
        if refusal_reason is not None:
            return ChatAskResponse(
                response_status="refused",
                trace_id=trace_id,
                answer="当前请求超出 FAQ 知识问答的安全边界，暂不提供回答。",
                citations=[],
                debug_info=self._build_debug_info(
                    debug_enabled,
                    normalized_query,
                    route_result="refused",
                    chunk_ids=[],
                    router_used="rule_parser",
                    route_confidence=0.0,
                    fallback_reason=refusal_reason,
                ),
            )

        decision, planner_output, router_used = self._resolve_decision(normalized_query)

        if (
            decision.route != "faq_qa"
            or decision.confidence < settings.route_confidence_threshold
        ):
            return ChatAskResponse(
                response_status="fallback",
                trace_id=trace_id,
                answer="当前请求未进入标准 FAQ 路径，请先尝试更直接的提问方式。",
                citations=[],
                debug_info=self._build_debug_info(
                    debug_enabled,
                    normalized_query,
                    route_result=decision.route,
                    chunk_ids=[],
                    router_used=router_used,
                    route_confidence=decision.confidence,
                    fallback_reason="route_not_confident_enough",
                    planner_output=planner_output,
                ),
            )

        if (
            settings.search_backend == "elasticsearch"
            and self._lexical_retriever is not None
        ):
            return self._search_elastic(
                normalized_query,
                planner_output=planner_output,
                router_used=router_used,
                trace_id=trace_id,
                debug_enabled=debug_enabled,
            )

        return self._search_local(
            decision,
            normalized_query=normalized_query,
            planner_output=planner_output,
            document_ids=document_ids,
            router_used=router_used,
            trace_id=trace_id,
            debug_enabled=debug_enabled,
        )

    def _search_elastic(
        self,
        normalized_query: str,
        *,
        planner_output: PlannerOutput | None,
        router_used: str,
        trace_id: str,
        debug_enabled: bool,
    ) -> ChatAskResponse:
        base_query = (
            normalized_query
            if planner_output is None
            else planner_output.normalized_query
        )
        search_query = base_query
        lexical_terms = (
            planner_output.lexical_terms
            if planner_output is not None and planner_output.lexical_terms
            else self._extract_lexical_terms(search_query)
        )
        business_domain = None if planner_output is None else planner_output.domain_hint

        if settings.enable_fast_track:
            small_query_rule = self._match_small_query_rule(normalized_query)
            if small_query_rule is not None:
                search_query = small_query_rule["search_query"]
                lexical_terms = self._merge_lexical_terms(
                    lexical_terms,
                    [normalized_query, search_query, *small_query_rule["lexical_terms"]],
                )
                business_domain = small_query_rule["business_domain"]

        used_hybrid = planner_output is not None and self._hybrid_retriever is not None
        if used_hybrid:
            hits = self._hybrid_retriever.search(
                lexical_query=search_query,
                vector_query=base_query,
                lexical_terms=lexical_terms,
                business_domain=business_domain,
                lifecycle_status="active",
                size=5,
            )
        else:
            hits = self._lexical_retriever.search(
                search_query,
                lexical_terms=lexical_terms,
                min_score=0.1,
                business_domain=business_domain,
                lifecycle_status="active",
                size=5,
            )

        if not hits:
            return ChatAskResponse(
                response_status="fallback",
                trace_id=trace_id,
                answer="当前知识库中未命中足够依据，请尝试使用更明确的关键词提问。",
                citations=[],
                debug_info=self._build_debug_info(
                    debug_enabled,
                    normalized_query,
                    route_result="faq_qa_elastic",
                    chunk_ids=[],
                    router_used=router_used,
                    route_confidence=None,
                    retrieval_score=None,
                    fallback_reason="retrieval_no_hit",
                    planner_output=planner_output,
                ),
            )

        evidence_spans = []
        if used_hybrid and self._reranker is not None:
            reranked = self._select_reranked_hit(base_query, hits)
            if reranked is None:
                return ChatAskResponse(
                    response_status="fallback",
                    trace_id=trace_id,
                    answer="当前知识库中未命中足够依据，请尝试使用更明确的关键词提问。",
                    citations=[],
                    debug_info=self._build_debug_info(
                        debug_enabled,
                        normalized_query,
                        route_result="faq_qa_elastic",
                        chunk_ids=[],
                        router_used=router_used,
                        route_confidence=None,
                        retrieval_score=None,
                        fallback_reason="no_evidence",
                        planner_output=planner_output,
                    ),
                )
            best = reranked.hit
            evidence_spans = reranked.evidence_spans
        else:
            best = self._select_elastic_hit(hits)

        answer = best.answer or best.body_text
        snippet = answer[:160] if not evidence_spans else evidence_spans[0].text
        citation = map_citation(
            {
                "id": best.unit_id,
                "answer": answer,
                "source_label": best.source_label,
                "source_locator": best.source_locator,
                "snippet": snippet,
            }
        )

        return ChatAskResponse(
            response_status="ok",
            trace_id=trace_id,
            answer=answer,
            citations=[citation],
            debug_info=self._build_debug_info(
                debug_enabled,
                normalized_query,
                route_result="faq_qa_elastic",
                chunk_ids=[best.unit_id],
                router_used=router_used,
                route_confidence=None,
                retrieval_score=best.score,
                planner_output=planner_output,
            ),
        )

    @classmethod
    def _select_elastic_hit(cls, hits):
        best = hits[0]
        if best.source_kind == "faq":
            return best

        faq_candidate = next(
            (
                hit
                for hit in hits
                if hit.source_kind == "faq" and (hit.answer or hit.body_text)
            ),
            None,
        )
        if faq_candidate is None:
            return best

        score_gap = best.score - faq_candidate.score
        if score_gap <= cls._ELASTIC_FAQ_PREFERENCE_MAX_SCORE_GAP:
            return faq_candidate
        return best

    def _select_reranked_hit(self, query: str, hits):
        reranked_hits = self._reranker.rerank(query, hits, top_n=min(len(hits), 3))
        accepted_hits = [
            item
            for item in reranked_hits
            if item.accept and (item.hit.answer or item.hit.body_text)
        ]
        if not accepted_hits:
            return None

        best = accepted_hits[0]
        if best.hit.source_kind == "faq":
            return best

        faq_candidate = next(
            (item for item in accepted_hits if item.hit.source_kind == "faq"),
            None,
        )
        if faq_candidate is None:
            return best

        score_gap = best.rerank_score - faq_candidate.rerank_score
        if score_gap <= self._ELASTIC_FAQ_PREFERENCE_MAX_SCORE_GAP:
            return faq_candidate
        return best

    @classmethod
    def _match_small_query_rule(
        cls, normalized_query: str
    ) -> dict[str, str | tuple[str, ...]] | None:
        for rule in cls._SMALL_QUERY_RULES:
            if normalized_query in rule["queries"]:
                return rule
        return None

    @staticmethod
    def _merge_lexical_terms(
        base_terms: list[str], extra_terms: list[str]
    ) -> list[str]:
        merged = list(base_terms)
        for term in extra_terms:
            if term and term not in merged:
                merged.append(term)
        return merged

    def _search_local(
        self,
        decision: IntentDecision,
        *,
        normalized_query: str,
        planner_output: PlannerOutput | None,
        document_ids: list[str],
        router_used: str,
        trace_id: str,
        debug_enabled: bool,
    ) -> ChatAskResponse:
        hit = self._retriever.search(
            decision.query_for_search,
            min_score=settings.retrieval_min_score,
            document_ids=document_ids or None,
        )
        if hit is None or hit.score < settings.retrieval_min_score:
            return ChatAskResponse(
                response_status="fallback",
                trace_id=trace_id,
                answer="当前知识库中未命中足够依据，请尝试使用更明确的关键词提问。",
                citations=[],
                debug_info=self._build_debug_info(
                    debug_enabled,
                    normalized_query,
                    route_result=decision.route,
                    chunk_ids=[] if hit is None else [hit.item["id"]],
                    router_used=router_used,
                    route_confidence=decision.confidence,
                    retrieval_score=None if hit is None else float(hit.score),
                    fallback_reason="retrieval_score_below_threshold"
                    if hit is not None
                    else "retrieval_no_hit",
                    planner_output=planner_output,
                ),
            )

        citation = map_citation(hit.item)
        return ChatAskResponse(
            response_status="ok",
            trace_id=trace_id,
            answer=hit.item["answer"],
            citations=[citation],
            debug_info=self._build_debug_info(
                debug_enabled,
                normalized_query,
                route_result=decision.route,
                chunk_ids=[hit.item["id"]],
                router_used=router_used,
                route_confidence=decision.confidence,
                retrieval_score=float(hit.score),
                planner_output=planner_output,
            ),
        )

    def _resolve_decision(
        self, normalized_query: str
    ) -> tuple[IntentDecision, PlannerOutput | None, str]:
        if self._query_planner is None:
            decision = self._resolver.resolve(normalized_query)
            return decision, None, "rule_parser"

        try:
            planner_output = self._query_planner.plan(normalized_query)
        except Exception:
            decision = self._resolver.resolve(normalized_query)
            return decision, None, "rule_parser"

        if (
            not planner_output.normalized_query
            or not planner_output.lexical_terms
            or planner_output.planner_confidence < settings.route_confidence_threshold
        ):
            decision = self._resolver.resolve(normalized_query)
            return decision, None, "rule_parser"

        decision = IntentDecision(
            route="faq_qa",
            confidence=planner_output.planner_confidence,
            query_for_search=planner_output.normalized_query,
        )
        return decision, planner_output, self._query_planner.router_name

    @staticmethod
    def _extract_lexical_terms(query: str) -> list[str]:
        terms = [query]
        if len(query) > 2:
            for i in range(len(query) - 1):
                bigram = query[i : i + 2]
                if bigram not in terms:
                    terms.append(bigram)
        if len(query) > 4:
            for i in range(len(query) - 2):
                trigram = query[i : i + 3]
                if trigram not in terms:
                    terms.append(trigram)
        return terms

    @staticmethod
    def _match_refusal_reason(normalized_query: str) -> str | None:
        lowered_query = normalized_query.lower()
        for reason, terms in ChatService._REFUSAL_TERMS.items():
            if any(term in lowered_query for term in terms):
                return reason
        return None

    @staticmethod
    def _build_debug_info(
        enabled: bool,
        normalized_query: str,
        route_result: str,
        chunk_ids: list[str],
        *,
        router_used: str,
        route_confidence: float | None,
        retrieval_score: float | None = None,
        fallback_reason: str | None = None,
        planner_output: PlannerOutput | None = None,
    ) -> DebugInfo | None:
        if not enabled:
            return None
        return DebugInfo(
            normalized_query=normalized_query,
            route_result=route_result,
            router_used=router_used,
            retrieved_chunks=chunk_ids,
            route_confidence=route_confidence,
            retrieval_score=retrieval_score,
            fallback_reason=fallback_reason,
        )
