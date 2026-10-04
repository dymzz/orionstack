from datetime import datetime, timezone
from typing import Literal
from pydantic import Field, model_validator
from app.config.runtime_versions import RuntimeVersions
from app.decision.model_call import ModelCallReceipt
from app.knowledge.contracts import CoreContract

WorkbenchMode = Literal['knowledge', 'general_chat']


class RunFeedback(CoreContract):
    request_id: str = Field(min_length=1)
    mode: WorkbenchMode
    outcome: Literal['answered', 'insufficient_evidence', 'failed']
    reason: Literal['answered', 'general_response', 'no_raw_candidates', 'processing_filtered_all',
                    'sources_unavailable', 'model_insufficient_evidence', 'unverified_answer', 'source_changed',
                    'provider_failed', 'configuration_missing', 'retrieval_failed', 'audit_unavailable']
    model_call: ModelCallReceipt
    retrieval_event_id: str | None = None
    processing_run_id: str | None = None
    raw_candidate_count: int | None = Field(default=None, ge=0)
    final_candidate_count: int | None = Field(default=None, ge=0)
    audit_status: Literal['stored', 'unavailable'] = 'stored'
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    runtime_versions: RuntimeVersions = Field(default_factory=RuntimeVersions)

    @model_validator(mode='after')
    def boundaries(self):
        if self.recorded_at.utcoffset() is None:
            raise ValueError('Feedback time must include timezone')
        if self.mode == 'general_chat' and any(x is not None for x in (
                self.retrieval_event_id, self.processing_run_id, self.raw_candidate_count, self.final_candidate_count)):
            raise ValueError('General chat must not claim retrieval facts')
        return self


class ChatMessage(CoreContract):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=4000)


class GeneralChatRequest(CoreContract):
    query: str = Field(min_length=1, max_length=4000)
    messages: tuple[ChatMessage, ...] = Field(default=(), max_length=10)

    @model_validator(mode='after')
    def limits(self):
        if not self.query.strip() or any(not m.content.strip() for m in self.messages):
            raise ValueError('Chat messages must not be blank')
        if len(self.query) + sum(len(m.content) for m in self.messages) > 20_000:
            raise ValueError('Chat context exceeds 20000 characters')
        return self


class GeneralChatResponse(CoreContract):
    tenant_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    mode: Literal['general_chat'] = 'general_chat'
    status: Literal['answered'] = 'answered'
    answer: str = Field(min_length=1, max_length=12000)
    validation: Literal['unverified_general_response'] = 'unverified_general_response'
    model: str = Field(min_length=1, max_length=128)
    execution_feedback: RunFeedback

    @model_validator(mode='after')
    def consistent(self):
        if (self.execution_feedback.mode != self.mode or self.execution_feedback.request_id != self.request_id
                or self.execution_feedback.outcome != self.status):
            raise ValueError('Chat and server feedback disagree')
        return self


class FeedbackResponse(CoreContract):
    tenant_id: str
    user_id: str
    execution_feedback: RunFeedback


class WorkbenchFailureResponse(CoreContract):
    detail: str
    execution_feedback: RunFeedback | None = None
