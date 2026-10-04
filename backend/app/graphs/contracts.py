from typing import Literal
from uuid import UUID, uuid4
from pydantic import Field, field_validator, model_validator
from app.knowledge.contracts import CoreContract
from app.services.core_query_service import CoreQueryResponse
from app.workbench.contracts import GeneralChatResponse, RunFeedback
from app.workbench.audit_contracts import UserFeedbackEntry


class ChatInput(CoreContract):
    message: str = Field(min_length=1,max_length=4000)
    client_message_id: UUID = Field(default_factory=uuid4)
    origin: Literal["user_submission", "automated_test"] = "user_submission"

    @field_validator("message")
    @classmethod
    def meaningful(cls, value):
        if not value.strip(): raise ValueError("Empty message")
        return value


class RouteDecision(CoreContract):
    needs_retrieval: bool = Field(strict=True)
    is_feedback: bool = Field(strict=True)
    is_system_status: bool = Field(default=False,strict=True)
    needs_workflow: Literal[False] = False
    retrieval_query: str = Field(default='',max_length=4000)
    feedback_value: Literal['helpful','not_helpful','correction','none'] = 'none'
    reason: str = Field(min_length=1,max_length=300)

    @model_validator(mode='after')
    def axis_consistency(self):
        if self.needs_retrieval and not self.retrieval_query.strip():raise ValueError('Retrieval needs a query')
        if self.is_feedback and self.feedback_value=='none':raise ValueError('Feedback needs a value')
        return self


class ChatOutput(CoreContract):
    thread_id: UUID
    client_message_id: UUID
    kind: Literal['knowledge','general_chat','system','failure']
    message: str
    route: RouteDecision | None = None
    routing_call: dict | None = None
    conversation_versions: dict = Field(default_factory=dict)
    result: CoreQueryResponse | GeneralChatResponse | None = None
    execution_feedback: RunFeedback | None = None
    feedback: UserFeedbackEntry | None = None
    error_code: str | None = None
    replayed: bool = False
