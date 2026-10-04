"""User feedback is an unreviewed signal; audit DTOs expose server-owned facts."""
from datetime import datetime
from typing import Literal
from pydantic import Field, model_validator
from app.knowledge.contracts import CoreContract
from app.decision.grounded_answer import CheckedCitation
from app.evidence.contracts import EvidenceBundle
from app.retrieval.raw_contracts import RawRetrievalRecord, ProcessingRun, RetrievalEvaluation
from app.workbench.contracts import RunFeedback, ChatMessage, WorkbenchMode


class UserFeedbackRequest(CoreContract):
    request_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r'^[A-Za-z0-9_.:-]+$')
    event_id: str | None = Field(default=None, min_length=1, max_length=128)
    candidate_id: str | None = Field(default=None, min_length=1, max_length=128)
    kind: Literal['answer_helpfulness', 'candidate_relevance', 'factual_correction']
    value: Literal['helpful', 'not_helpful', 'relevant', 'not_relevant', 'correction']
    comment: str = Field(default='', max_length=2000)
    # A caller may mark test traffic for exclusion, never mark itself human/approved.
    origin: Literal['user_submission', 'automated_test'] = 'user_submission'

    @model_validator(mode='after')
    def kind_matches_target(self):
        if self.kind == 'answer_helpfulness':
            valid = self.value in ('helpful', 'not_helpful') and self.candidate_id is None
        elif self.kind == 'candidate_relevance':
            valid = self.value in ('relevant', 'not_relevant') and self.candidate_id is not None and self.event_id is not None
        else:
            valid = self.value == 'correction' and bool(self.comment.strip())
        if not valid or (self.candidate_id is not None and self.event_id is None):
            raise ValueError('Feedback type, value and target disagree')
        return self


class UserFeedbackEntry(CoreContract):
    tenant_id: str
    id: str
    request_id: str
    actor_user_id: str
    event_id: str | None
    candidate_id: str | None
    kind: Literal['answer_helpfulness', 'candidate_relevance', 'factual_correction']
    value: str
    comment: str | None
    origin: Literal['user_submission', 'automated_test']
    evaluator: Literal['user_feedback'] = 'user_feedback'
    review_state: Literal['unreviewed'] = 'unreviewed'
    training_eligible: Literal[False] = False
    policy_version: str
    created_at: datetime


class UserFeedbackResponse(CoreContract):
    feedback: UserFeedbackEntry
    replayed: bool = Field(strict=True)


class RunSummary(CoreContract):
    request_id: str
    actor_user_id: str
    mode: WorkbenchMode
    status: Literal['answered', 'insufficient_evidence', 'failed']
    created_at: datetime
    execution_feedback: RunFeedback
    feedback_count: int = Field(ge=0)


class RunList(CoreContract):
    tenant_id: str
    scope: Literal['mine'] = 'mine'
    items: tuple[RunSummary, ...]
    next_cursor: str | None = None


class AuditAnswer(CoreContract):
    status: Literal['answered', 'insufficient_evidence', 'failed']
    answer: str | None = None
    validation: Literal['source_and_quote_checked', 'no_verified_answer', 'unverified_general_response'] | None = None
    model: str | None = None
    citations: tuple[CheckedCitation, ...] = ()
    evidence_bundle: EvidenceBundle | None = None


class AuthorizationEvent(CoreContract):
    id: str
    principal_id: str
    action: str
    resource_id: str
    decision: Literal['allow', 'deny']
    policy_version: str
    created_at: datetime


class RunAudit(CoreContract):
    tenant_id: str
    run: RunSummary
    content_access: Literal['available', 'withheld']
    query: str | None = None
    messages: tuple[ChatMessage, ...] = ()
    raw: RawRetrievalRecord | None = None
    processing: tuple[ProcessingRun, ...] = ()
    evaluations: tuple[RetrievalEvaluation, ...] = ()
    answer: AuditAnswer | None = None
    feedback: tuple[UserFeedbackEntry, ...] = ()
    authorization: tuple[AuthorizationEvent, ...] = ()
    feedback_truncated: bool = False
    checked_at: datetime


class RetrievalAudit(CoreContract):
    tenant_id: str
    event_id: str
    request_id: str
    content_access: Literal['available', 'withheld']
    raw: RawRetrievalRecord | None = None
    processing: tuple[ProcessingRun, ...] = ()
    evaluations: tuple[RetrievalEvaluation, ...] = ()
    checked_at: datetime
