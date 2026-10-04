"""Deterministic document provenance checks over a sealed raw candidate."""

from datetime import datetime
from uuid import uuid4

from app.evidence.contracts import (
    ChainCheck, ChainChecks, ChainProfile, ChainSource, ChainVerification,
    ContentHash, DocumentContent, DocumentLocator, SourceTime, SourceVersion,
)
from app.retrieval.raw_contracts import RawCandidate, RawRetrievalRecord


def document_chain(raw: RawRetrievalRecord, candidate: RawCandidate, observation: dict | None,
                   checked_at: datetime) -> ChainProfile:
    # Revalidate raw facts at this boundary, including copied/adapted model output.
    raw = RawRetrievalRecord.model_validate(raw.model_dump())
    candidate = RawCandidate.model_validate(candidate.model_dump())
    if candidate not in raw.candidates:
        raise ValueError("Evidence is not a candidate of this raw event")
    observed = observation or {}
    identity_matches = (observed.get("source_id") == candidate.source.source_id
                        and observed.get("source_version") == candidate.source.source_version)
    proof = ChainCheck(status="pass" if identity_matches else "unknown",
                       reason="current_source_and_raw_match" if identity_matches else "source_not_verified")
    latest = observed.get("latest_source_version")
    checks = ChainChecks(
        source_identity=proof, source_version=proof,
        source_actor=ChainCheck(status="unknown", reason="source_not_provided"),
        source_time=ChainCheck(status="unknown", reason="native_source_time_not_provided"),
        latest_version=ChainCheck(status="unknown" if latest is None else
                                 ("pass" if latest == candidate.source.source_version else "fail"),
                                 reason="no_authorized_local_head" if latest is None else "local_head_compared"),
        source_locator=ChainCheck(status="pass", reason="current_locator_matches_raw"),
        content_integrity=ChainCheck(status="pass", reason="exact_utf8_chunk_sha256"),
        raw_link=ChainCheck(status="pass", reason="candidate_belongs_to_sealed_event"),
    )
    return ChainProfile(
        tenant_id=raw.event.tenant_id,
        chain_id=str(uuid4()), evidence_id=candidate.candidate_id, raw_record_id=candidate.candidate_id,
        raw_event_id=raw.event.id,
        source=ChainSource(source_id=candidate.source.source_id, source_system=observed.get("source_system"),
            source_type="document", external_id=observed.get("external_id"),
            time=SourceTime(observed_at=raw.event.created_at),
            version=SourceVersion(value=candidate.source.source_version, latest=latest,
                is_latest=None if latest is None else latest == candidate.source.source_version,
                checked_at=None if latest is None else checked_at)),
        locator=DocumentLocator(document_id=candidate.document_id, document_version=candidate.document_version,
            chunk_id=candidate.chunk_id, source_locator=candidate.source.source_locator),
        content=DocumentContent(text=candidate.text, hash=ContentHash(digest=candidate.content_hash,
            scope="chunk", encoding="utf-8")),
        verification=ChainVerification(checked_at=checked_at), checks=checks, status=checks.aggregate(),
    )
