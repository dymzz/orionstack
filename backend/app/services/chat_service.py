from __future__ import annotations

from app.config.settings import settings
from app.guardrails.normalize import normalize_query
from app.retrieval.citation_mapper import map_citation
from app.retrieval.retriever import Retriever
from app.routing.resolver import RouteResolver
from app.schemas.request import ChatAskRequest
from app.schemas.response import ChatAskResponse, DebugInfo
from app.storage.repositories.chunk_repo import ChunkRepository
from app.storage.repositories.faq_repo import FAQRepository
from app.storage.repositories.knowledge_unit_repo import KnowledgeUnitRepository


class ChatService:
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
        self._lexical_retriever = None
        if settings.search_backend == "elasticsearch":
            self._lexical_retriever = self._create_lexical_retriever()

    def _create_lexical_retriever(self):
        from app.retrieval.lexical_retriever import LexicalRetriever
        from elasticsearch import Elasticsearch

        es = Elasticsearch(settings.elastic_url)
        return LexicalRetriever(es, index_name=settings.elastic_index)

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
                    route_confidence=0.0,
                    fallback_reason=refusal_reason,
                ),
            )

        decision = self._resolver.resolve(normalized_query)

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
                    route_confidence=decision.confidence,
                    fallback_reason="route_not_confident_enough",
                ),
            )

        if (
            settings.search_backend == "elasticsearch"
            and self._lexical_retriever is not None
        ):
            return self._search_elastic(
                normalized_query, trace_id=trace_id, debug_enabled=debug_enabled
            )

        return self._search_local(
            decision,
            normalized_query,
            document_ids=document_ids,
            trace_id=trace_id,
            debug_enabled=debug_enabled,
        )

    def _search_elastic(
        self, normalized_query: str, *, trace_id: str, debug_enabled: bool
    ) -> ChatAskResponse:
        hits = self._lexical_retriever.search(
            normalized_query,
            lexical_terms=self._extract_lexical_terms(normalized_query),
            min_score=0.1,
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
                    route_confidence=None,
                    retrieval_score=None,
                    fallback_reason="retrieval_no_hit",
                ),
            )

        best = hits[0]
        answer = best.answer or best.body_text
        citation = map_citation(
            {
                "id": best.unit_id,
                "answer": answer,
                "source_label": best.source_label,
                "source_locator": best.source_locator,
                "snippet": answer[:160],
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
                route_confidence=None,
                retrieval_score=best.score,
            ),
        )

    def _search_local(
        self,
        decision,
        normalized_query: str,
        *,
        document_ids: list[str],
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
                    route_confidence=decision.confidence,
                    retrieval_score=None if hit is None else float(hit.score),
                    fallback_reason="retrieval_score_below_threshold"
                    if hit is not None
                    else "retrieval_no_hit",
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
                route_confidence=decision.confidence,
                retrieval_score=float(hit.score),
            ),
        )

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
        route_confidence: float | None,
        retrieval_score: float | None = None,
        fallback_reason: str | None = None,
    ) -> DebugInfo | None:
        if not enabled:
            return None
        return DebugInfo(
            normalized_query=normalized_query,
            route_result=route_result,
            router_used="rule_parser",
            retrieved_chunks=chunk_ids,
            route_confidence=route_confidence,
            retrieval_score=retrieval_score,
            fallback_reason=fallback_reason,
        )
