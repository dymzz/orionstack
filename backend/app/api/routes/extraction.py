from typing import Any

from fastapi import APIRouter, HTTPException

from app.extract.candidate_reviewer import review_candidate, publish_candidate
from app.extract.extraction_service import ExtractionService
from app.schemas.extraction import (
    ExtractRequest,
    ExtractResponse,
    ReviewRequest,
    ReviewResponse,
    CandidateItem,
)
from app.storage.repositories.extraction_candidate_repo import ExtractionCandidateRepo
from app.storage.repositories.source_record_repo import SourceRecordRepo

router = APIRouter(prefix="/api/extraction", tags=["extraction"])

_candidate_repo = ExtractionCandidateRepo()
_source_record_repo = SourceRecordRepo()


@router.post("/extract", response_model=ExtractResponse)
def extract_from_source(request: ExtractRequest) -> ExtractResponse:
    sr = _source_record_repo.get(request.source_record_id)
    if sr is None:
        raise HTTPException(status_code=404, detail="source_record not found")

    service = ExtractionService()
    candidates = service.extract_from_record(sr, candidate_types=request.candidate_types)

    items = [
        CandidateItem(
            candidate_id=c.candidate_id,
            candidate_type=c.candidate_type,
            payload_json=c.payload_json,
            review_status=c.review_status,
            created_at=c.created_at,
        )
        for c in candidates
    ]

    return ExtractResponse(
        source_record_id=request.source_record_id,
        extracted_count=len(items),
        candidates=items,
    )


@router.post("/review", response_model=ReviewResponse)
def review_extraction_candidate(request: ReviewRequest) -> ReviewResponse:
    candidate = _candidate_repo.get(request.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="candidate not found")

    reviewed = review_candidate(
        candidate_id=request.candidate_id,
        approved=request.approved,
        reviewer=request.reviewer or "api",
        candidate_repo=_candidate_repo,
    )
    if reviewed is None:
        raise HTTPException(status_code=500, detail="review failed")

    published_type: str | None = None
    if request.approved:
        sr = _source_record_repo.get(reviewed.source_record_id)
        if sr is not None:
            result = publish_candidate(reviewed, sr)
            if result is not None:
                published_type = type(result).__name__

    return ReviewResponse(
        candidate_id=request.candidate_id,
        review_status=reviewed.review_status,
        reviewed_by=reviewed.reviewed_by,
        reviewed_at=reviewed.reviewed_at,
        published_type=published_type,
    )


@router.get("/candidates", response_model=list[CandidateItem])
def list_candidates(status: str | None = None) -> list[CandidateItem]:
    if status:
        candidates = _candidate_repo.list_by_review_status(status)
    else:
        candidates = _candidate_repo.list_by_review_status("pending")

    return [
        CandidateItem(
            candidate_id=c.candidate_id,
            candidate_type=c.candidate_type,
            payload_json=c.payload_json,
            review_status=c.review_status,
            created_at=c.created_at,
        )
        for c in candidates
    ]
