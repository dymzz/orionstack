from datetime import UTC, datetime
import json
import os
from time import perf_counter
from uuid import uuid4

import httpx
from app.api.schemas.qa import AskQuestionRequest, AskQuestionResponse, CitationItem, QAHistoryItemResponse, QAHistoryResponse
from app.knowledge.retrieval.retrieval_service import RetrievalService
from app.models.entities import QAHistoryORM
from app.repositories.qa_history_repository import QAHistoryRepository


class QAService:
    def __init__(self) -> None:
        self.retrieval_service = RetrievalService()
        self.history_repository = QAHistoryRepository()
        self.ollama_base_url = os.getenv("ORIONSTACK_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.ollama_model = os.getenv("ORIONSTACK_OLLAMA_MODEL", "gemma3:1b")

    def ask(self, payload: AskQuestionRequest) -> AskQuestionResponse:
        start = perf_counter()
        trace_id = str(uuid4())
        citations = self._retrieve_citations(payload)
        answer = self._generate_answer(payload.question, citations)
        latency_ms = int((perf_counter() - start) * 1000)
        response = AskQuestionResponse(
            answer=answer,
            citations=citations,
            trace_id=trace_id,
            latency_ms=latency_ms,
        )
        self._append_history(payload, response)
        return response

    def ask_stream_events(self, payload: AskQuestionRequest):
        start = perf_counter()
        trace_id = str(uuid4())
        citations = self._retrieve_citations(payload)
        yield self._sse_event(
            {
                "type": "meta",
                "trace_id": trace_id,
                "citations": [citation.model_dump() for citation in citations],
            }
        )

        prompt = self._build_prompt(payload.question, citations)
        collected_answer: list[str] = []
        stream_succeeded = False

        try:
            with httpx.stream(
                "POST",
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": True,
                },
                timeout=45.0,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    packet = json.loads(line)
                    token = str(packet.get("response", ""))
                    if token:
                        collected_answer.append(token)
                        yield self._sse_event({"type": "token", "token": token})
                stream_succeeded = True
        except Exception:
            fallback_answer = self._build_answer(payload.question, citations)
            for token in fallback_answer.split():
                yield self._sse_event({"type": "token", "token": token + " "})
            collected_answer = [fallback_answer]

        answer = "".join(collected_answer).strip()
        if not answer:
            answer = self._build_answer(payload.question, citations)
        else:
            answer = self._normalize_answer(answer, citations)

        latency_ms = int((perf_counter() - start) * 1000)
        final_response = AskQuestionResponse(
            answer=answer,
            citations=citations,
            trace_id=trace_id,
            latency_ms=latency_ms,
        )
        self._append_history(payload, final_response)
        yield self._sse_event(
            {
                "type": "done",
                "stream_provider": "ollama" if stream_succeeded else "fallback",
                **final_response.model_dump(),
            }
        )

    def _append_history(self, payload: AskQuestionRequest, response: AskQuestionResponse) -> None:
        self.history_repository.append(
            QAHistoryORM(
                trace_id=response.trace_id,
                session_id=payload.session_id,
                question=payload.question,
                answer=response.answer,
                latency_ms=response.latency_ms,
                created_at=datetime.now(UTC),
                citations_json=[citation.model_dump() for citation in response.citations],
            )
        )

    def list_history(self, session_id: str) -> QAHistoryResponse:
        items = [
            QAHistoryItemResponse(
                trace_id=item.trace_id,
                question=item.question,
                answer=item.answer,
                latency_ms=item.latency_ms,
                created_at=item.created_at,
                citations=[CitationItem(**citation) for citation in item.citations_json],
            )
            for item in self.history_repository.list_by_session(session_id)
        ]
        return QAHistoryResponse(session_id=session_id, items=items)

    def _retrieve_citations(self, payload: AskQuestionRequest) -> list[CitationItem]:
        chunks = self.retrieval_service.retrieve(
            question=payload.question,
            document_ids=payload.document_ids,
            top_k=payload.top_k,
            use_rerank=payload.use_rerank,
        )
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

    def _generate_answer(self, question: str, citations: list[CitationItem]) -> str:
        prompt = self._build_prompt(question, citations)
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                answer = str(data.get("response", "")).strip()
                if answer:
                    return self._normalize_answer(answer, citations)
        except Exception:
            pass
        return self._build_answer(question, citations)

    def _build_prompt(self, question: str, citations: list[CitationItem]) -> str:
        context_lines: list[str] = []
        for idx, citation in enumerate(citations, start=1):
            context_lines.append(
                f"[{idx}] {citation.document_name}#{citation.chunk_id}: {citation.snippet}"
            )

        context_text = "\n".join(context_lines) if context_lines else "No indexed context available."
        return (
            "You are a concise enterprise knowledge assistant.\n"
            "Answer in Chinese.\n"
            "If context is insufficient, say so clearly.\n\n"
            f"Question:\n{question}\n\n"
            f"Context:\n{context_text}\n\n"
            "Answer:"
        )

    def _build_answer(self, question: str, citations: list[CitationItem]) -> str:
        if not citations:
            return f'No relevant indexed content found for "{question}". Try uploading or reindexing a document first.'

        top_citation = citations[0]
        return (
            f'Based on "{top_citation.document_name}", the most relevant passage is: '
            f'{top_citation.snippet}'
        )

    def _normalize_answer(self, answer: str, citations: list[CitationItem]) -> str:
        if not citations:
            return answer

        top_citation = citations[0]
        if top_citation.document_name in answer:
            return answer

        return f'Based on "{top_citation.document_name}", {answer}'

    def _sse_event(self, payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
