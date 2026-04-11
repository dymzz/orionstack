from fastapi import APIRouter

router = APIRouter(tags=["audit"])


@router.get("/audit/logs")
def list_audit_logs() -> dict:
    return {"items": []}
