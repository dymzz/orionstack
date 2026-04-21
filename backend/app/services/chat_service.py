from __future__ import annotations

from app.config.settings import settings
from app.guardrails.normalize import normalize_query
from app.query.query_planner import PlannerOutput, QueryPlanner
from app.retrieval.citation_mapper import map_citation
from app.retrieval.retriever import Retriever
from app.routing.contracts import IntentDecision
from app.routing.resolver import RouteResolver
from app.schemas.request import ChatAskRequest
from app.schemas.response import (
    ChatAskResponse,
    ClarificationInfo,
    ClarificationOption,
    DebugInfo,
    RetrievalCandidateSummary,
)
from app.storage.repositories.chunk_repo import ChunkRepository
from app.storage.repositories.faq_repo import FAQRepository
from app.storage.repositories.knowledge_unit_repo import KnowledgeUnitRepository


class ChatService:
    _ELASTIC_FAQ_PREFERENCE_MAX_SCORE_GAP = 0.35
    _CLARIFICATION_MAX_RERANK_SCORE_GAP = 0.15
    _ELASTIC_REQUEST_TIMEOUT_SECONDS = 2
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

        es = Elasticsearch(
            settings.elastic_url,
            request_timeout=self._ELASTIC_REQUEST_TIMEOUT_SECONDS,
            retry_on_timeout=False,
            max_retries=0,
        )
        return LexicalRetriever(es, index_name=settings.elastic_index)

    def _create_hybrid_retriever(self):
        from app.retrieval.hybrid_retriever import HybridRetriever
        from app.retrieval.lexical_retriever import LexicalRetriever
        from app.retrieval.vector_retriever import VectorRetriever
        from elasticsearch import Elasticsearch

        es = Elasticsearch(
            settings.elastic_url,
            request_timeout=self._ELASTIC_REQUEST_TIMEOUT_SECONDS,
            retry_on_timeout=False,
            max_retries=0,
        )
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
        from app.retrieval.lexical_retriever import RetrievalBackendError

        retrieval_mode = "lexical_only"
        lexical_topk = None
        vector_topk = None
        rrf_topk = None
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

        used_hybrid = planner_output is not None and self._hybrid_retriever is not None
        try:
            if used_hybrid:
                retrieval_mode = "hybrid"
                hits = self._hybrid_retriever.search(
                    lexical_query=search_query,
                    vector_query=base_query,
                    lexical_terms=lexical_terms,
                    business_domain=business_domain,
                    lifecycle_status="active",
                    size=5,
                )
                lexical_topk, vector_topk, rrf_topk = self._summarize_hybrid_hits(hits)
            else:
                hits = self._lexical_retriever.search(
                    search_query,
                    lexical_terms=lexical_terms,
                    min_score=0.1,
                    business_domain=business_domain,
                    lifecycle_status="active",
                    size=5,
                )
                lexical_topk = self._summarize_lexical_hits(hits)
        except RetrievalBackendError as error:
            return ChatAskResponse(
                response_status="fallback",
                trace_id=trace_id,
                answer="当前检索后端暂时不可用，请稍后重试。",
                citations=[],
                debug_info=self._build_debug_info(
                    debug_enabled,
                    normalized_query,
                    route_result="faq_qa_elastic",
                    chunk_ids=[],
                    router_used=router_used,
                    route_confidence=None,
                    retrieval_score=None,
                    fallback_reason=f"{error.stage}_backend_error",
                    planner_output=planner_output,
                    retrieval_mode=retrieval_mode,
                    lexical_topk=lexical_topk,
                    vector_topk=vector_topk,
                    rrf_topk=rrf_topk,
                    **self._summarize_rerank_decision(
                        None,
                        reject_reason=error.cause_name,
                    ),
                ),
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
                    retrieval_mode=retrieval_mode,
                    lexical_topk=lexical_topk,
                    vector_topk=vector_topk,
                    rrf_topk=rrf_topk,
                    **self._summarize_rerank_decision(None),
                ),
            )

        evidence_spans = []
        selected_reranked = None
        if used_hybrid and self._reranker is not None:
            retrieval_mode = "hybrid_rerank"
            reranked_hits = self._reranker.rerank(search_query, hits, top_n=len(hits))
            clarification_reranked_hits = reranked_hits
            if normalized_query != search_query:
                clarification_reranked_hits = self._reranker.rerank(
                    normalized_query,
                    hits,
                    top_n=len(hits),
                )
            clarification_response = self._build_clarification_response(
                normalized_query=normalized_query,
                reranked_hits=clarification_reranked_hits,
                router_used=router_used,
                trace_id=trace_id,
                debug_enabled=debug_enabled,
                planner_output=planner_output,
                lexical_topk=lexical_topk,
                vector_topk=vector_topk,
                rrf_topk=rrf_topk,
                rerank_reject_reason="multiple_close_faq_candidates",
            )
            if clarification_response is not None:
                return clarification_response

            reranked = self._select_reranked_hit(reranked_hits)
            if reranked is None:
                top_reranked = None if not reranked_hits else reranked_hits[0]
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
                        fusion_score=None if top_reranked is None else top_reranked.hit.score,
                        fallback_reason="no_evidence",
                        planner_output=planner_output,
                        retrieval_mode=retrieval_mode,
                        lexical_topk=lexical_topk,
                        vector_topk=vector_topk,
                        rrf_topk=rrf_topk,
                        **self._summarize_rerank_decision(
                            top_reranked,
                            reject_reason="evidence_below_threshold",
                        ),
                    ),
                )
            best = reranked.hit
            evidence_spans = reranked.evidence_spans
            selected_reranked = reranked
        else:
            best = self._select_elastic_hit(hits)

        answer = best.answer or best.body_text
        snippet = answer[:160] if not evidence_spans else evidence_spans[0].text
        citation = self._build_hit_citation(best, snippet)

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
                retrieval_score=None if used_hybrid else best.score,
                fusion_score=best.score if used_hybrid else None,
                planner_output=planner_output,
                retrieval_mode=retrieval_mode,
                lexical_topk=lexical_topk,
                vector_topk=vector_topk,
                rrf_topk=rrf_topk,
                **self._summarize_rerank_decision(selected_reranked),
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

    def _select_reranked_hit(self, reranked_hits):
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

    def _build_clarification_response(
        self,
        *,
        normalized_query: str,
        reranked_hits,
        router_used: str,
        trace_id: str,
        debug_enabled: bool,
        planner_output: PlannerOutput | None,
        lexical_topk: list[RetrievalCandidateSummary] | None,
        vector_topk: list[RetrievalCandidateSummary] | None,
        rrf_topk: list[RetrievalCandidateSummary] | None,
        rerank_reject_reason: str,
    ) -> ChatAskResponse | None:
        clarification_candidates = self._collect_clarification_candidates(reranked_hits)
        if len(clarification_candidates) < 2:
            return None

        top_candidate = clarification_candidates[0]
        second_candidate = clarification_candidates[1]
        score_gap = top_candidate.rerank_score - second_candidate.rerank_score
        if score_gap > self._CLARIFICATION_MAX_RERANK_SCORE_GAP:
            return None

        if top_candidate.hit.question == second_candidate.hit.question:
            return None

        citations = [
            self._build_hit_citation(
                candidate.hit,
                candidate.evidence_spans[0].text
                if candidate.evidence_spans
                else (candidate.hit.answer or candidate.hit.body_text)[:160],
            )
            for candidate in clarification_candidates[:2]
        ]
        options = [
            ClarificationOption(
                option_id=candidate.hit.unit_id,
                label=candidate.hit.question or candidate.hit.source_label,
            )
            for candidate in clarification_candidates[:2]
        ]
        return ChatAskResponse(
            response_status="ok",
            trace_id=trace_id,
            answer="当前问题还不够具体，请先确认您想了解的具体规则方向。",
            citations=citations,
            clarification=ClarificationInfo(
                clarification_required=True,
                question="您更想了解以下哪一项？",
                options=options,
                conflict_reason="multiple_close_faq_candidates",
            ),
            debug_info=self._build_debug_info(
                debug_enabled,
                normalized_query,
                route_result="faq_qa_elastic",
                chunk_ids=[candidate.hit.unit_id for candidate in clarification_candidates[:2]],
                router_used=router_used,
                route_confidence=None,
                retrieval_score=None,
                fusion_score=top_candidate.hit.score,
                fallback_reason="conflict_requires_clarification",
                planner_output=planner_output,
                retrieval_mode="clarification",
                lexical_topk=lexical_topk,
                vector_topk=vector_topk,
                rrf_topk=rrf_topk,
                **self._summarize_rerank_decision(
                    top_candidate,
                    reject_reason=rerank_reject_reason,
                ),
            ),
        )

    @staticmethod
    def _collect_clarification_candidates(reranked_hits):
        return [
            item
            for item in reranked_hits
            if item.accept
            and item.hit.source_kind == "faq"
            and item.evidence_spans
            and (item.hit.answer or item.hit.body_text)
        ]

    @staticmethod
    def _build_hit_citation(hit, snippet: str):
        return map_citation(
            {
                "id": hit.unit_id,
                "answer": hit.answer or hit.body_text,
                "source_label": hit.source_label,
                "source_locator": hit.source_locator,
                "snippet": snippet,
            }
        )

    @staticmethod
    def _summarize_lexical_hits(
        hits, *, limit: int = 3
    ) -> list[RetrievalCandidateSummary]:
        return [
            RetrievalCandidateSummary(
                unit_id=hit.unit_id,
                score=float(hit.score),
                source_kind=hit.source_kind,
            )
            for hit in hits[:limit]
        ]

    @classmethod
    def _summarize_hybrid_hits(
        cls, hits, *, limit: int = 3
    ) -> tuple[
        list[RetrievalCandidateSummary],
        list[RetrievalCandidateSummary],
        list[RetrievalCandidateSummary],
    ]:
        lexical_topk = [
            RetrievalCandidateSummary(
                unit_id=hit.unit_id,
                score=float(hit.bm25_score or 0.0),
                source_kind=hit.source_kind,
            )
            for hit in sorted(
                (item for item in hits if item.lexical_rank is not None),
                key=lambda item: item.lexical_rank or 0,
            )[:limit]
        ]
        vector_topk = [
            RetrievalCandidateSummary(
                unit_id=hit.unit_id,
                score=float(hit.vector_score or 0.0),
                source_kind=hit.source_kind,
            )
            for hit in sorted(
                (item for item in hits if item.vector_rank is not None),
                key=lambda item: item.vector_rank or 0,
            )[:limit]
        ]
        rrf_topk = [
            RetrievalCandidateSummary(
                unit_id=hit.unit_id,
                score=float(hit.score),
                source_kind=hit.source_kind,
                lexical_dominance_applied=hit.lexical_dominance_applied,
                vector_dominance_applied=hit.vector_dominance_applied,
            )
            for hit in sorted(hits, key=lambda item: item.rrf_rank)[:limit]
        ]
        return lexical_topk, vector_topk, rrf_topk

    @staticmethod
    def _summarize_rerank_decision(
        reranked_hit,
        *,
        reject_reason: str | None = None,
    ) -> dict[str, bool | float | int | str | None]:
        if reranked_hit is None:
            return {
                "rerank_accept": None,
                "rerank_score": None,
                "evidence_confidence": None,
                "evidence_span_count": None,
                "reject_reason": reject_reason,
            }

        return {
            "rerank_accept": reranked_hit.accept,
            "rerank_score": float(reranked_hit.rerank_score),
            "evidence_confidence": float(reranked_hit.evidence_confidence),
            "evidence_span_count": len(reranked_hit.evidence_spans),
            "reject_reason": reject_reason,
        }

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
        fusion_score: float | None = None,
        fallback_reason: str | None = None,
        planner_output: PlannerOutput | None = None,
        retrieval_mode: str | None = None,
        lexical_topk: list[RetrievalCandidateSummary] | None = None,
        vector_topk: list[RetrievalCandidateSummary] | None = None,
        rrf_topk: list[RetrievalCandidateSummary] | None = None,
        rerank_accept: bool | None = None,
        rerank_score: float | None = None,
        evidence_confidence: float | None = None,
        evidence_span_count: int | None = None,
        reject_reason: str | None = None,
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
            fusion_score=fusion_score,
            fallback_reason=fallback_reason,
            domain_hint=None if planner_output is None else planner_output.domain_hint,
            lexical_terms=None if planner_output is None else planner_output.lexical_terms,
            planner_confidence=None
            if planner_output is None
            else planner_output.planner_confidence,
            retrieval_mode=retrieval_mode,
            lexical_topk=lexical_topk,
            vector_topk=vector_topk,
            rrf_topk=rrf_topk,
            rerank_accept=rerank_accept,
            rerank_score=rerank_score,
            evidence_confidence=evidence_confidence,
            evidence_span_count=evidence_span_count,
            reject_reason=reject_reason,
        )
