from datetime import UTC, datetime
import json
from time import perf_counter
from uuid import uuid4

from app.api.schemas.qa import AskQuestionRequest, AskQuestionResponse, CitationItem, QAHistoryItemResponse, QAHistoryResponse
from app.governance.audit_service import AuditService
from app.models.entities import QAHistoryORM
from app.repositories.qa_history_repository import QAHistoryRepository
from app.workflows.knowledge_assistant.workflow import KnowledgeAssistantWorkflow


class QAService:
    def __init__(self) -> None:
        self.workflow = KnowledgeAssistantWorkflow()
        self.history_repository = QAHistoryRepository()
        self.audit_service = AuditService()

    def ask(self, payload: AskQuestionRequest, *, owner_user_id: str) -> AskQuestionResponse:
        start = perf_counter()
        trace_id = str(uuid4())

        try:
            workflow_state = self.workflow.run(self._build_state(payload, trace_id))
            citations = self._citations_from_state(workflow_state)
            answer = str(workflow_state.get("answer", "")).strip()
            if not answer:
                answer = self.workflow.build_fallback_answer(workflow_state)
            answer_provider = self._resolve_answer_provider(
                should_refuse=bool(workflow_state.get("should_refuse", False)),
                has_answer=bool(answer),
            )
            latency_ms = int((perf_counter() - start) * 1000)
            response = AskQuestionResponse(
                answer=answer,
                citations=citations,
                trace_id=trace_id,
                latency_ms=latency_ms,
                retrieval_confidence=float(workflow_state.get("retrieval_confidence", 0.0)),
                refusal_reason=workflow_state.get("refusal_reason"),
                need_human_review=bool(workflow_state.get("need_human_review", False)),
                answer_provider=answer_provider,
            )
        except Exception:
            latency_ms = int((perf_counter() - start) * 1000)
            response = AskQuestionResponse(
                answer="当前无法生成回答，请稍后重试。",
                citations=[],
                trace_id=trace_id,
                latency_ms=latency_ms,
                retrieval_confidence=0.0,
                refusal_reason="system_error",
                need_human_review=True,
                answer_provider="error_fallback",
            )
            self.audit_service.log(
                owner_user_id=owner_user_id,
                event_type="qa_ask_failed",
                trace_id=trace_id,
                payload={"session_id": payload.session_id},
            )

        self._append_history(payload, response, owner_user_id=owner_user_id)
        self.audit_service.log(
            owner_user_id=owner_user_id,
            event_type="qa_asked",
            trace_id=response.trace_id,
            payload={
                "session_id": payload.session_id,
                "citations_count": len(response.citations),
                "answer_provider": response.answer_provider or "",
                "stream": False,
            },
        )
        return response

    def ask_stream_events(self, payload: AskQuestionRequest, *, owner_user_id: str):
        start = perf_counter()
        trace_id = str(uuid4())
        citations: list[CitationItem] = []
        state: dict | None = None

        try:
            state = self.workflow.prepare(self._build_state(payload, trace_id))
            citations = self._citations_from_state(state)
        except Exception:
            state = None

        yield self._sse_event(
            {
                "type": "meta",
                "trace_id": trace_id,
                "citations": [citation.model_dump() for citation in citations],
            }
        )

        if state is None:
            fallback_answer = "当前无法生成回答，请稍后重试。"
            for token in fallback_answer.split():
                yield self._sse_event({"type": "token", "token": token + " "})
            latency_ms = int((perf_counter() - start) * 1000)
            final_response = AskQuestionResponse(
                answer=fallback_answer,
                citations=[],
                trace_id=trace_id,
                latency_ms=latency_ms,
                retrieval_confidence=0.0,
                refusal_reason="system_error",
                need_human_review=True,
                answer_provider="error_fallback",
            )
            self._append_history(payload, final_response, owner_user_id=owner_user_id)
            self.audit_service.log(
                owner_user_id=owner_user_id,
                event_type="qa_stream_failed",
                trace_id=trace_id,
                payload={"session_id": payload.session_id},
            )
            yield self._sse_event({"type": "done", "stream_provider": "error_fallback", **final_response.model_dump()})
            return

        try:
            collected_answer: list[str] = []
            stream_provider = "ollama_fallback"

            for token in self.workflow.stream_generate_tokens(state):
                collected_answer.append(token)
                yield self._sse_event({"type": "token", "token": token})

            raw_answer = "".join(collected_answer).strip()
            finalized_state = self.workflow.finalize(state, raw_answer)
            answer = str(finalized_state.get("answer", "")).strip()
            if not answer:
                answer = self.workflow.build_fallback_answer(finalized_state)
            if state.get("should_refuse"):
                stream_provider = "guard_refusal"
            elif raw_answer:
                stream_provider = "langchain_or_ollama"

            latency_ms = int((perf_counter() - start) * 1000)
            final_response = AskQuestionResponse(
                answer=answer,
                citations=citations,
                trace_id=trace_id,
                latency_ms=latency_ms,
                retrieval_confidence=float(finalized_state.get("retrieval_confidence", 0.0)),
                refusal_reason=finalized_state.get("refusal_reason"),
                need_human_review=bool(finalized_state.get("need_human_review", False)),
                answer_provider=stream_provider,
            )
        except Exception:
            fallback_answer = "当前无法生成回答，请稍后重试。"
            for token in fallback_answer.split():
                yield self._sse_event({"type": "token", "token": token + " "})
            latency_ms = int((perf_counter() - start) * 1000)
            final_response = AskQuestionResponse(
                answer=fallback_answer,
                citations=citations,
                trace_id=trace_id,
                latency_ms=latency_ms,
                retrieval_confidence=0.0,
                refusal_reason="system_error",
                need_human_review=True,
                answer_provider="error_fallback",
            )
            self.audit_service.log(
                owner_user_id=owner_user_id,
                event_type="qa_stream_failed",
                trace_id=trace_id,
                payload={"session_id": payload.session_id},
            )

        self._append_history(payload, final_response, owner_user_id=owner_user_id)
        self.audit_service.log(
            owner_user_id=owner_user_id,
            event_type="qa_asked",
            trace_id=final_response.trace_id,
            payload={
                "session_id": payload.session_id,
                "citations_count": len(final_response.citations),
                "answer_provider": final_response.answer_provider or "",
                "stream": True,
            },
        )
        yield self._sse_event(
            {
                "type": "done",
                "stream_provider": final_response.answer_provider or "fallback",
                **final_response.model_dump(),
            }
        )

    def _append_history(
        self,
        payload: AskQuestionRequest,
        response: AskQuestionResponse,
        *,
        owner_user_id: str,
    ) -> None:
        self.history_repository.append(
            QAHistoryORM(
                trace_id=response.trace_id,
                owner_user_id=owner_user_id,
                session_id=payload.session_id,
                question=payload.question,
                answer=response.answer,
                latency_ms=response.latency_ms,
                retrieval_confidence=float(response.retrieval_confidence or 0.0),
                refusal_reason=str(response.refusal_reason or ""),
                need_human_review=bool(response.need_human_review),
                answer_provider=str(response.answer_provider or ""),
                created_at=datetime.now(UTC),
                citations_json=[citation.model_dump() for citation in response.citations],
            )
        )

    def list_history(
        self,
        session_id: str,
        *,
        owner_user_id: str,
        limit: int = 20,
        offset: int = 0,
        order: str = "desc",
    ) -> QAHistoryResponse:
        safe_limit = max(1, min(limit, 200))
        safe_offset = max(0, offset)
        normalized_order = "asc" if order == "asc" else "desc"
        total = self.history_repository.count_by_session(session_id, owner_user_id=owner_user_id)
        rows = self.history_repository.list_by_session(
            session_id,
            limit=safe_limit,
            offset=safe_offset,
            order=normalized_order,
            owner_user_id=owner_user_id,
        )
        items = [
            QAHistoryItemResponse(
                trace_id=item.trace_id,
                question=item.question,
                answer=item.answer,
                latency_ms=item.latency_ms,
                retrieval_confidence=item.retrieval_confidence,
                refusal_reason=item.refusal_reason or None,
                need_human_review=item.need_human_review,
                answer_provider=item.answer_provider or None,
                created_at=item.created_at,
                citations=[CitationItem(**citation) for citation in item.citations_json],
            )
            for item in rows
        ]
        return QAHistoryResponse(
            session_id=session_id,
            total=total,
            limit=safe_limit,
            offset=safe_offset,
            order=normalized_order,
            has_more=(safe_offset + len(items)) < total,
            items=items,
        )

    def _build_state(self, payload: AskQuestionRequest, trace_id: str) -> dict:
        return {
            "trace_id": trace_id,
            "session_id": payload.session_id,
            "question": payload.question,
            "document_ids": payload.document_ids,
            "top_k": payload.top_k,
            "use_rerank": payload.use_rerank,
        }

    def _citations_from_state(self, state: dict) -> list[CitationItem]:
        chunks = state.get("citations", [])
        return [
            CitationItem(
                document_id=item.get("document_id", ""),
                document_name=item.get("document_name", ""),
                chunk_id=item.get("chunk_id", ""),
                snippet=item.get("snippet", ""),
                score=float(item.get("score", 0.0)),
            )
            for item in chunks
        ]

    def _sse_event(self, payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def _resolve_answer_provider(self, *, should_refuse: bool, has_answer: bool) -> str:
        if should_refuse:
            return "guard_refusal"
        if has_answer:
            return "langchain_or_ollama"
        return "fallback"
