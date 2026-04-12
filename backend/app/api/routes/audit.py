from fastapi import APIRouter, Query, Request

from app.api.schemas.audit import AuditLogListResponse
from app.core.request_context import get_current_user_context
from app.governance.activity_service import ActivityService
from app.governance.authorization import require_permission

router = APIRouter(tags=["audit"])
service = ActivityService()

@router.get("/audit/logs", response_model=AuditLogListResponse)
def list_audit_logs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    user_context = get_current_user_context(request)
    owner_user_id = user_context.user_id
    require_permission(user_context, resource="audit", action="read")
    return service.list_audit_logs(owner_user_id=owner_user_id, limit=limit, offset=offset)
