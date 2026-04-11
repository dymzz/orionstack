from time import perf_counter
from uuid import uuid4

from app.api.schemas.qa import AskQuestionRequest, AskQuestionResponse, CitationItem
from app.knowledge.retrieval.retrieval_service import RetrievalService


class QAService:
    def __init__(self) -> None:
        self.retrieval_service = RetrievalService()

    def ask(self, payload: AskQuestionRequest) -> AskQuestionResponse:
        start = perf_counter()
        chunks = self.retrieval_service.retrieve(
            question=payload.question,
            document_ids=payload.document_ids,
            top_k=payload.top_k,
        )
        citations = [
            CitationItem(
                document_id=item.get("document_id", ""),
                document_name=item.get("document_name", ""),
                chunk_id=item.get("chunk_id", ""),
                snippet=item.get("snippet", ""),
                score=float(item.get("score", 0.0)),
            )
            for item in chunks
        ]
        latency_ms = int((perf_counter() - start) * 1000)
        return AskQuestionResponse(
            answer="Placeholder answer. Implement retrieval + generation here.",
            citations=citations,
            trace_id=str(uuid4()),
            latency_ms=latency_ms,
        )
