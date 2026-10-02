from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.auth import require_admin
from app.extract.candidate_reviewer import review_candidate, publish_candidate
from app.extract.extraction_service import ExtractionService
from app.extract.providers import build_extraction_provider
from app.config.settings import settings
from app.schemas.extraction import (
    ExtractRequest,
    ExtractResponse,
    ReviewRequest,
    ReviewResponse,
    CandidateItem,
    CandidateListResponse,
)
from app.storage.repositories.extraction_candidate_repo import ExtractionCandidateRepo
from app.storage.repositories.extracted_faq_repo import ExtractedFaqRepo
from app.storage.repositories.knowledge_unit_repo import KnowledgeUnit
from app.storage.repositories.source_record_repo import SourceRecordRepo

router = APIRouter(
    prefix="/api/v1/extraction",
    tags=["extraction"],
    dependencies=[Depends(require_admin)],
)

_candidate_repo = ExtractionCandidateRepo()
_source_record_repo = SourceRecordRepo()
_extracted_faq_repo = ExtractedFaqRepo()
_extraction_service = ExtractionService(
    candidate_repo=_candidate_repo,
    provider=build_extraction_provider(settings.extraction_provider, settings),
)


def get_candidate_repo() -> ExtractionCandidateRepo:
    return _candidate_repo


def get_source_record_repo() -> SourceRecordRepo:
    return _source_record_repo


def get_extraction_service() -> ExtractionService:
    return _extraction_service


@router.post("/extract", response_model=ExtractResponse)
def extract_from_source(request: ExtractRequest) -> ExtractResponse:
    sr = _source_record_repo.get(request.source_record_id)
    if sr is None:
        raise HTTPException(status_code=404, detail="source_record not found")

    candidates = _extraction_service.extract_from_record(sr, candidate_types=request.candidate_types)

    items = [
        CandidateItem(
            candidate_id=c.candidate_id,
            tenant_id=c.tenant_id,
            source_record_id=c.source_record_id,
            candidate_type=c.candidate_type,
            payload_json=c.payload_json,
            extractor_model=c.extractor_model,
            prompt_version=c.prompt_version,
            source_span=c.source_span,
            source_span_hash=c.source_span_hash,
            review_status=c.review_status,
            created_at=c.created_at,
            reviewed_by=c.reviewed_by,
            reviewed_at=c.reviewed_at,
        )
        for c in candidates
    ]

    return ExtractResponse(
        source_record_id=request.source_record_id,
        extracted_count=len(items),
        candidates=items,
    )


@router.post("/review", response_model=ReviewResponse)
def review_extraction_candidate(request: ReviewRequest, req: Request) -> ReviewResponse:
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
            result = publish_candidate(
                reviewed, sr, extracted_faq_repo=_extracted_faq_repo
            )
            if result is not None:
                published_type = type(result).__name__
                _try_incremental_index(result, req)

    return ReviewResponse(
        candidate_id=request.candidate_id,
        review_status=reviewed.review_status,
        reviewed_by=reviewed.reviewed_by,
        reviewed_at=reviewed.reviewed_at,
        published_type=published_type,
    )


@router.get("/candidates", response_model=CandidateListResponse)
def list_candidates(status: str | None = None) -> CandidateListResponse:
    if status:
        candidates = _candidate_repo.list_by_review_status(status)
    else:
        candidates = _candidate_repo.list_by_review_status("pending")

    return CandidateListResponse(
        items=[
            CandidateItem(
                candidate_id=c.candidate_id,
                tenant_id=c.tenant_id,
                source_record_id=c.source_record_id,
                candidate_type=c.candidate_type,
                payload_json=c.payload_json,
                extractor_model=c.extractor_model,
                prompt_version=c.prompt_version,
                source_span=c.source_span,
                source_span_hash=c.source_span_hash,
                review_status=c.review_status,
                created_at=c.created_at,
                reviewed_by=c.reviewed_by,
                reviewed_at=c.reviewed_at,
            )
            for c in candidates
        ]
    )


def get_extracted_faq_repo() -> ExtractedFaqRepo:
    return _extracted_faq_repo


def _try_incremental_index(published_result, req: Request) -> None:
    if not isinstance(published_result, KnowledgeUnit):
        return
    if settings.search_backend != "elasticsearch":
        return
    es_client = getattr(req.app.state, "es_client", None)
    if es_client is None:
        return
    try:
        from app.indexing.elastic_indexer import ElasticIndexer

        indexer = ElasticIndexer(es_client, index_name=settings.elastic_index)
        indexer.index_unit(published_result)
    except Exception:
        pass
