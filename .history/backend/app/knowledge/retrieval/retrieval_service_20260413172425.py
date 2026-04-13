import math

from app.governance.user_context import UserContext
from app.knowledge.embeddings.embedding_service import EmbeddingBatch, EmbeddingService
from app.knowledge.retrieval.query_tokenizer import (
    build_query_features,
    build_text_features,
    lexical_score,
)
from app.knowledge.retrieval.rerank_service import RerankService
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.embedding_repository import EmbeddingRepository
from app.repositories.pgvector_repository import PgVectorRepository


class RetrievalService:
    """Retrieve relevant chunks for a question."""

    def __init__(self) -> None:
        self.document_repository = DocumentRepository()
        self.chunk_repository = ChunkRepository()
        self.embedding_repository = EmbeddingRepository()
        self.pgvector_repository = PgVectorRepository()
        self.embedding_service = EmbeddingService()
        self.rerank_service = RerankService()

    def retrieve(
        self,
        question: str,
        document_ids: list[str] | None = None,
        top_k: int = 5,
        use_rerank: bool = False,
        user_context: UserContext | None = None,
    ) -> list[dict]:
        allowed_document_ids = self._resolve_allowed_document_ids(
            requested_document_ids=document_ids,
            user_context=user_context,
        )
        if allowed_document_ids == []:
            return []

        documents = self.document_repository.list(
            document_ids=allowed_document_ids,
            owner_user_id=user_context.user_id if user_context is not None else None,
        )
        document_names = {document.document_id: document.name for document in documents}
        chunks = self.chunk_repository.list(
            document_ids=[document.document_id for document in documents]
        )
        candidate_top_k = max(top_k, min(top_k * 4, 20))

        ranked_groups: list[tuple[str, list[dict]]] = []

        if chunks:
            query_embedding = self.embedding_service.embed_texts([question])

            if query_embedding.vectors:
                pgvector_results = self.pgvector_repository.search(
                    query_vector=query_embedding.vectors[0],
                    embedding_model=query_embedding.model,
                    top_k=candidate_top_k,
                    document_ids=[document.document_id for document in documents],
                )
                if pgvector_results:
                    ranked_groups.append(("pgvector", pgvector_results))

                vector_results = self._retrieve_by_embeddings(
                    query_embedding=query_embedding,
                    chunks=chunks,
                    document_names=document_names,
                    top_k=candidate_top_k,
                )
                if vector_results:
                    ranked_groups.append(("embedding", vector_results))

        keyword_results = self._retrieve_by_keywords(
            question=question,
            documents=documents,
            top_k=candidate_top_k,
        )
        if keyword_results:
            ranked_groups.append(("keyword", keyword_results))

        fused_candidates = self._fuse_ranked_candidates_rrf(
            ranked_groups=ranked_groups,
            top_k=candidate_top_k,
        )

        return self._finalize_results(
            question=question,
            candidates=fused_candidates,
            top_k=top_k,
            use_rerank=use_rerank,
        )

    def _fuse_ranked_candidates_rrf(
        self,
        *,
        ranked_groups: list[tuple[str, list[dict]]],
        top_k: int,
        rrf_k: int = 60,
    ) -> list[dict]:
        if not ranked_groups:
            return []

        merged: dict[str, dict] = {}

        for source, candidates in ranked_groups:
            for rank, candidate in enumerate(candidates, start=1):
                chunk_id = str(candidate.get("chunk_id", "")).strip()
                if not chunk_id:
                    continue

                if chunk_id not in merged:
                    item = dict(candidate)
                    item["score"] = 0.0
                    item["retrieval_sources"] = [source]
                    merged[chunk_id] = item
                else:
                    item = merged[chunk_id]
                    if source not in item["retrieval_sources"]:
                        item["retrieval_sources"].append(source)

                    for field in ("document_id", "document_name", "snippet", "content"):
                        if not item.get(field) and candidate.get(field):
                            item[field] = candidate[field]

                merged[chunk_id]["score"] += 1.0 / (rrf_k + rank)

        results = list(merged.values())
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_k]

    def _retrieve_by_embeddings(
        self,
        *,
        query_embedding: EmbeddingBatch,
        chunks: list,
        document_names: dict[str, str],
        top_k: int,
    ) -> list[dict]:
        if not query_embedding.vectors:
            return []

        chunk_ids = [chunk.chunk_id for chunk in chunks]
        stored_embeddings = self.embedding_repository.list_for_chunks(
            chunk_ids,
            embedding_model=query_embedding.model,
        )
        if not stored_embeddings:
            return []

        vectors_by_chunk_id = {
            embedding.chunk_id: embedding.vector_json
            for embedding in stored_embeddings
            if embedding.vector_json
        }

        results: list[dict] = []
        query_vector = query_embedding.vectors[0]
        for chunk in chunks:
            vector = vectors_by_chunk_id.get(chunk.chunk_id)
            if not vector:
                continue
            score = self._cosine_similarity(query_vector, vector)
            if score <= 0:
                continue
            results.append(
                {
                    "document_id": chunk.document_id,
                    "document_name": document_names.get(chunk.document_id, ""),
                    "chunk_id": chunk.chunk_id,
                    "snippet": chunk.snippet,
                    "content": chunk.content,
                    "score": score,
                }
            )

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_k]

    def _finalize_results(
        self,
        *,
        question: str,
        candidates: list[dict],
        top_k: int,
        use_rerank: bool,
    ) -> list[dict]:
        if not candidates:
            return []
        if not use_rerank:
            return candidates[:top_k]
        return self.rerank_service.rerank(
            question=question, candidates=candidates, top_k=top_k
        )

    def _resolve_allowed_document_ids(
        self,
        *,
        requested_document_ids: list[str] | None,
        user_context: UserContext | None,
    ) -> list[str] | None:
        if user_context is None:
            return requested_document_ids

        if not user_context.has_permission(resource="document", action="read"):
            return []

        documents = self.document_repository.list(
            document_ids=requested_document_ids,
            owner_user_id=user_context.user_id,
        )
        return [document.document_id for document in documents]

    def _retrieve_by_keywords(
        self, question: str, documents: list, top_k: int
    ) -> list[dict]:
        query_features = build_query_features(question)
        results: list[dict] = []
        for document in documents:
            for chunk in document.chunks_json:
                content = str(chunk.get("content", ""))
                score = self._score_chunk(content, query_features=query_features)
                if score <= 0:
                    continue
                results.append(
                    {
                        "document_id": document.document_id,
                        "document_name": document.name,
                        "chunk_id": str(chunk.get("chunk_id", "")),
                        "snippet": str(chunk.get("snippet", "")),
                        "content": str(chunk.get("content", "")),
                        "score": score,
                    }
                )

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_k]

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if len(left) != len(right):
            return 0.0

        numerator = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _score_chunk(self, content: str, *, query_features) -> float:
        if not query_features.terms:
            return 0.0
        return lexical_score(
            query=query_features,
            candidate=build_text_features(content),
        )
