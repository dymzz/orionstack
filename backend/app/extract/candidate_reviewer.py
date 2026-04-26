from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from app.storage.models.extraction_candidate import ExtractionCandidate
from app.storage.models.source_record import SourceRecord
from app.storage.repositories.extraction_candidate_repo import ExtractionCandidateRepo
from app.storage.repositories.knowledge_unit_repo import (
    KnowledgeUnit,
    map_faq_item_to_knowledge_unit,
)
from app.storage.repositories.source_record_repo import SourceRecordRepo
from app.storage.repositories.action_link_repo import ActionLinkRepo
from app.storage.repositories.dynamic_query_repo import DynamicQueryRepo
from app.storage.models.action_link import ActionLink
from app.storage.models.dynamic_query import DynamicQuery


def review_candidate(
    candidate_id: str,
    approved: bool,
    reviewer: str = "system",
    candidate_repo: ExtractionCandidateRepo | None = None,
) -> ExtractionCandidate | None:
    repo = candidate_repo or ExtractionCandidateRepo()
    new_status = "approved" if approved else "rejected"
    return repo.update_review_status(candidate_id, new_status, reviewed_by=reviewer)


def publish_candidate(
    candidate: ExtractionCandidate,
    source_record: SourceRecord,
    candidate_repo: ExtractionCandidateRepo | None = None,
    action_link_repo: ActionLinkRepo | None = None,
    dynamic_query_repo: DynamicQueryRepo | None = None,
) -> KnowledgeUnit | ActionLink | DynamicQuery | None:
    payload = json.loads(candidate.payload_json)
    candidate_type = payload.get("candidate_type", candidate.candidate_type)

    if candidate_type == "faq":
        return _publish_faq(candidate, source_record, payload)
    elif candidate_type == "action_link":
        return _publish_action_link(candidate, source_record, payload, action_link_repo=action_link_repo)
    elif candidate_type == "dynamic_query":
        return _publish_dynamic_query(candidate, source_record, payload, dynamic_query_repo=dynamic_query_repo)

    if candidate.candidate_type == "faq":
        return _publish_faq(candidate, source_record, payload)

    return None


def _publish_faq(
    candidate: ExtractionCandidate,
    source_record: SourceRecord,
    payload: dict[str, Any],
) -> KnowledgeUnit:
    item = {
        "id": f"ku-extracted-{candidate.candidate_id[:16]}",
        "question": payload.get("question", ""),
        "answer": payload.get("answer", ""),
        "body_text": payload.get("answer", ""),
        "keywords": payload.get("keywords", []),
        "business_domain": payload.get("business_domain", ""),
        "document_type": "faq",
        "source_type": "extracted",
        "source_label": f"Extracted ({candidate.extractor_model})",
        "source_locator": source_record.source_locator,
        "access_scope": source_record.access_scope,
        "lifecycle_status": "active",
        "source_record_id": source_record.source_record_id,
    }
    unit = map_faq_item_to_knowledge_unit(item, default_domain="")
    unit = replace(
        unit,
        tenant_id=candidate.tenant_id,
        source_record_id=source_record.source_record_id,
        unit_version=1,
        published_at=datetime.now(timezone.utc).isoformat(),
    )
    return unit


def _publish_action_link(
    candidate: ExtractionCandidate,
    source_record: SourceRecord,
    payload: dict[str, Any],
    action_link_repo: ActionLinkRepo | None = None,
) -> ActionLink:
    now = datetime.now(timezone.utc).isoformat()
    link = ActionLink(
        action_link_id=f"al-extracted-{candidate.candidate_id[:12]}",
        tenant_id=candidate.tenant_id,
        source_record_id=source_record.source_record_id,
        label=payload.get("label", ""),
        system_type=source_record.source_system,
        url=payload.get("url", ""),
        resource_type=payload.get("resource_type", ""),
        access_scope=source_record.access_scope,
        status="active",
        published_at=now,
        business_domains=tuple(
            payload.get("business_domains")
            or ([payload["business_domain"]] if payload.get("business_domain") else [])
        ),
    )
    repo = action_link_repo or ActionLinkRepo()
    repo.upsert(link)
    return link


def _publish_dynamic_query(
    candidate: ExtractionCandidate,
    source_record: SourceRecord,
    payload: dict[str, Any],
    dynamic_query_repo: DynamicQueryRepo | None = None,
) -> DynamicQuery:
    dq = DynamicQuery(
        dynamic_query_id=f"dq-extracted-{candidate.candidate_id[:12]}",
        tenant_id=candidate.tenant_id,
        query_key=payload.get("query_key", ""),
        resource_type=payload.get("resource_type", ""),
        action="read",
        scope_type=payload.get("scope_type", "self"),
        status="active",
        description=payload.get("description", ""),
        detect_patterns=tuple(payload.get("detect_patterns", [])),
        source_record_id=source_record.source_record_id,
    )
    repo = dynamic_query_repo or DynamicQueryRepo()
    repo.upsert(dq)
    return dq


def publish_approved_faq_candidate(
    candidate: ExtractionCandidate,
    source_record: SourceRecord,
) -> KnowledgeUnit:
    result = publish_candidate(candidate, source_record)
    if isinstance(result, KnowledgeUnit):
        return result
    raise ValueError("Expected KnowledgeUnit from faq candidate")
