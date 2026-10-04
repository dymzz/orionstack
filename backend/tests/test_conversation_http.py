"""Authorization/idempotency failures must be HTTP errors, before graph execution."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4
from fastapi.testclient import TestClient
import pytest
from app.api.core_access import require_core_access
from app.api.routes.conversation import get_conversation_service
from app.knowledge.contracts import AccessContext
from app.workbench.user_feedback import FeedbackConflict
from app.knowledge.postgres import DatabaseUnavailable
from main import app


@pytest.mark.parametrize('error,status',[(LookupError('unavailable'),404),(FeedbackConflict('conflict'),409),(DatabaseUnavailable('missing'),503)])
def test_prepare_failure_keeps_error_contract_and_does_not_enter_graph(error,status):
    @asynccontextmanager
    async def prepare(*args):
        raise error
        yield  # pragma: no cover
    app.dependency_overrides[require_core_access]=lambda:AccessContext(tenant_id='test',user_id='reader')
    app.dependency_overrides[get_conversation_service]=lambda:SimpleNamespace(prepare=prepare)
    try:
        response=TestClient(app).post(f'/api/chat/{uuid4()}/messages',json={'message':'hello'})
        assert response.status_code==status
        assert 'traceback' not in response.text and 'generator' not in response.text
    finally:app.dependency_overrides.clear()
