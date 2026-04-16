from app.config.settings import settings
from app.guardrails.normalize import normalize_query
from app.retrieval.citation_mapper import map_citation
from app.retrieval.retriever import Retriever
from app.routing.resolver import RouteResolver
from app.schemas.request import ChatAskRequest
from app.schemas.response import ChatAskResponse, DebugInfo
from app.storage.repositories.chunk_repo import ChunkRepository
from app.storage.repositories.faq_repo import FAQRepository


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
        self._retriever = Retriever(self._faq_repo, self._chunk_repo)
        self._resolver = RouteResolver()

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

        hit = self._retriever.search(
            decision.query_for_search,
            min_score=settings.retrieval_min_score,
            document_ids=document_ids,
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
