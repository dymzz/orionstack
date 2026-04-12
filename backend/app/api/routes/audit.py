from fastapi import APIRouter, Query, Request

from app.api.schemas.audit import AuditLogListResponse
from app.core.request_context import get_current_user_id
from app.governance.audit_service import AuditService

router = APIRouter(tags=["audit"])
service = AuditService()

@router.get("/audit/logs", response_model=AuditLogListResponse)
def list_audit_logs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    owner_user_id = get_current_user_id(request)
    return service.list_logs(owner_user_id=owner_user_id, limit=limit, offset=offset)
