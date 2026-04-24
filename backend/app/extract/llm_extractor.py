from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.storage.models.extraction_candidate import ExtractionCandidate
from app.storage.models.source_record import SourceRecord


def extract_candidates(
    source_record: SourceRecord,
    candidate_type: str,
    payloads: list[dict[str, Any]],
    extractor_model: str = "openai_compatible",
    prompt_version: str = "v1",
    tenant_id: str = "default",
) -> list[ExtractionCandidate]:
    candidates: list[ExtractionCandidate] = []
    now = datetime.now(timezone.utc).isoformat()
    for payload in payloads:
        span = payload.pop("_source_span", "")[:200]
        candidates.append(
            ExtractionCandidate(
                candidate_id=f"ec-{uuid4().hex[:12]}",
                tenant_id=tenant_id,
                source_record_id=source_record.source_record_id,
                candidate_type=candidate_type,
                payload_json=__import__("json").dumps(payload, ensure_ascii=False),
                extractor_model=extractor_model,
                prompt_version=prompt_version,
                source_span=span,
                source_span_hash=hashlib.sha256(span.encode()).hexdigest()[:16],
                review_status="pending",
                created_at=now,
            )
        )
    return candidates
