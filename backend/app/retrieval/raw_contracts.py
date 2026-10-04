"""Raw retrieval facts contain no evaluator decisions or rewritten ranking."""

from datetime import datetime, timezone
import json
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import Field, field_validator, model_validator

from app.knowledge.contracts import AccessContext, CoreContract, EvidenceCandidate, SourceRef, content_hash
from app.knowledge.embedding import EmbeddingSignature
from app.config.runtime_versions import RuntimeVersions

FiniteFloat = Annotated[float, Field(allow_inf_nan=False, strict=True)]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RawCandidate(CoreContract):
    candidate_id: str = Field(default_factory=new_id)
    document_id: str = Field(min_length=1)
    document_version: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    content_hash: Hash
    rank: int = Field(ge=1, strict=True)
    similarity_score: FiniteFloat
    retrieval_scores: dict[str, FiniteFloat] | None = Field(default=None,exclude_if=lambda value:value is None)
    retrieval_method: Literal["pgvector_exact_cosine","pgvector_hybrid_rrf"] | None = Field(default=None,exclude_if=lambda value:value is None)
    text: str = Field(min_length=1)
    source: SourceRef
    access_scopes: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check_provenance(self):
        if (content_hash(self.text) != self.content_hash
                or self.source.document_id != self.document_id
                or self.source.document_version != self.document_version
                or self.source.chunk_id != self.chunk_id
                or self.source.content_hash != self.content_hash):
            raise ValueError("Raw candidate snapshot does not match its content and provenance")
        return self

    def evidence(self, tenant_id: str, retrieved_at: datetime) -> EvidenceCandidate:
        return EvidenceCandidate(
            evidence_id=self.candidate_id, evidence_kind="document_chunk", tenant_id=tenant_id,
            access_scope=self.access_scopes[0], source=self.source, text=self.text,
            retrieved_at=retrieved_at, retrieval_method=self.retrieval_method or "pgvector_exact_cosine",
            retrieval_score=self.similarity_score,
        )

    @property
    def snapshot_hash(self) -> str:
        return content_hash(json.dumps(self.model_dump(mode="json"), sort_keys=True,
                                       separators=(",", ":"), ensure_ascii=False))


class RawRetrievalEvent(CoreContract):
    runtime_versions: RuntimeVersions = Field(default_factory=RuntimeVersions)
    id: str = Field(default_factory=new_id)
    tenant_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    query_hash: Hash
    embedding_configuration: EmbeddingSignature
    query_vector: tuple[FiniteFloat, ...]
    document_ids: tuple[str, ...] = ()
    allowed_scopes: tuple[str, ...] = ()
    top_k: int = Field(ge=1, le=100, strict=True)
    candidate_count: int = Field(ge=0, strict=True)
    retrieval_method: Literal["pgvector_exact_cosine","pgvector_hybrid_rrf"] = "pgvector_exact_cosine"
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def embedding_signature(self) -> str:
        return self.embedding_configuration.fingerprint

    @model_validator(mode="after")
    def check_event(self):
        if (self.query_hash != content_hash(self.query) or self.candidate_count > self.top_k
                or len(self.query_vector) != self.embedding_configuration.dimensions
                or not any(self.query_vector)
                or self.created_at.tzinfo is None or self.created_at.utcoffset() is None):
            raise ValueError("Raw event fingerprint, dimensions, count or timestamp is invalid")
        return self


class RawRetrievalRecord(CoreContract):
    event: RawRetrievalEvent
    candidates: tuple[RawCandidate, ...]

    @model_validator(mode="after")
    def check_candidate_set(self):
        if (len(self.candidates) != self.event.candidate_count
                or tuple(candidate.rank for candidate in self.candidates) != tuple(range(1, len(self.candidates) + 1))
                or len({candidate.candidate_id for candidate in self.candidates}) != len(self.candidates)
                or len({(c.document_id, c.document_version, c.chunk_id) for c in self.candidates}) != len(self.candidates)
                or any(not set(c.access_scopes).issubset(self.event.allowed_scopes) for c in self.candidates)
                or any(self.event.document_ids and c.document_id not in self.event.document_ids for c in self.candidates)):
            raise ValueError("Raw retrieval candidate count, identity, scope or rank is invalid")
        return self

    def require_access(self, access: AccessContext) -> None:
        if (access.tenant_id != self.event.tenant_id
                or (access.user_id != self.event.user_id and "admin" not in access.roles)
                or any(not set(c.access_scopes).issubset(access.allowed_scopes) for c in self.candidates)):
            raise PermissionError("Raw retrieval record is outside the authenticated principal's scope")


class RetrievalEvaluation(CoreContract):
    id: str = Field(default_factory=new_id)
    candidate_id: str | None = None
    evaluator: str = Field(min_length=1)
    evaluator_version: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    score: FiniteFloat | None = None
    reason: str = ""
    details_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("details_json")
    @classmethod
    def check_details(cls, value):
        from app.providers.http import parse_json
        if not isinstance(parse_json(value), dict):
            raise ValueError("Evaluation details must be a JSON object")
        return value


class ProcessingRun(CoreContract):
    id: str = Field(default_factory=new_id)
    event_id: str
    processors: tuple[str, ...]
    configuration_json: str = "[]"
    final_top_k: int | None = Field(default=None, ge=1, le=100)
    status: Literal["completed", "raw_fallback"] = "completed"
    error_code: str | None = None
    selected_candidate_ids: tuple[str, ...]
    evaluations: tuple[RetrievalEvaluation, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("configuration_json")
    @classmethod
    def check_configuration(cls, value):
        from app.providers.http import parse_json
        if not isinstance(parse_json(value), list):
            raise ValueError("Processing configuration must be a JSON array")
        return value


class RetrievalResponse(CoreContract):
    raw: RawRetrievalRecord
    processing: ProcessingRun

    @model_validator(mode="after")
    def check_results(self):
        known = {candidate.candidate_id for candidate in self.raw.candidates}
        ids = self.processing.selected_candidate_ids
        if (self.processing.event_id != self.raw.event.id or len(set(ids)) != len(ids)
                or not set(ids).issubset(known)
                or any(e.candidate_id is not None and e.candidate_id not in known for e in self.processing.evaluations)):
            raise ValueError("Processing results must reference this raw retrieval event")
        return self

    @property
    def final_candidates(self) -> tuple[RawCandidate, ...]:
        by_id = {candidate.candidate_id: candidate for candidate in self.raw.candidates}
        return tuple(by_id[identity] for identity in self.processing.selected_candidate_ids)
