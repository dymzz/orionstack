from pydantic import BaseModel


class ExtractRequest(BaseModel):
    source_record_id: str
    candidate_types: list[str] | None = None


class CandidateItem(BaseModel):
    candidate_id: str
    candidate_type: str
    payload_json: str
    review_status: str
    created_at: str


class ExtractResponse(BaseModel):
    source_record_id: str
    extracted_count: int
    candidates: list[CandidateItem]


class ReviewRequest(BaseModel):
    candidate_id: str
    approved: bool
    reviewer: str | None = None


class ReviewResponse(BaseModel):
    candidate_id: str
    review_status: str
    reviewed_by: str | None
    reviewed_at: str | None
    published_type: str | None = None
