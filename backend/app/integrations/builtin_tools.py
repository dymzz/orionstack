from __future__ import annotations

from app.integrations.tool_gateway import ToolCallRequest, ToolCallResult, ToolGateway
from app.repositories.document_repository import DocumentRepository
from app.repositories.index_job_repository import IndexJobRepository


def register_builtin_tools(gateway: ToolGateway) -> None:
    document_repository = DocumentRepository()
    index_job_repository = IndexJobRepository()

    def list_visible_documents(request: ToolCallRequest, user_context) -> ToolCallResult:
        documents = document_repository.list(owner_user_id=user_context.user_id)
        items = [
            {
                "document_id": document.document_id,
                "name": document.name,
                "status": document.status,
                "source_type": document.source_type,
            }
            for document in documents
        ]
        return ToolCallResult(
            ok=True,
            data={
                "documents": items,
                "count": len(items),
            },
            raw={"tool_name": request.tool_name, "documents": items},
        )

    def get_document_status_by_name(request: ToolCallRequest, user_context) -> ToolCallResult:
        document_name = str(request.arguments.get("document_name", "")).strip()
        if not document_name:
            return ToolCallResult(
                ok=False,
                error_code="invalid_arguments",
                error_message="document_name is required",
            )

        documents = document_repository.list(owner_user_id=user_context.user_id)
        normalized_name = document_name.casefold()
        matched = next(
            (
                document
                for document in documents
                if document.name.strip().casefold() == normalized_name
                or normalized_name in document.name.strip().casefold()
            ),
            None,
        )
        if matched is None:
            return ToolCallResult(
                ok=False,
                error_code="document_not_found",
                error_message=f"Document not found: {document_name}",
                raw={"tool_name": request.tool_name, "document_name": document_name},
            )

        latest_job = index_job_repository.get_latest_for_document(matched.document_id)
        data = {
            "document": {
                "document_id": matched.document_id,
                "name": matched.name,
                "status": matched.status,
                "source_type": matched.source_type,
            },
            "latest_index_job": (
                {
                    "job_id": latest_job.job_id,
                    "status": latest_job.status,
                    "progress_pct": latest_job.progress_pct,
                    "error_code": latest_job.error_code,
                    "error_message": latest_job.error_message,
                }
                if latest_job is not None
                else None
            ),
        }
        return ToolCallResult(
            ok=True,
            data=data,
            raw={"tool_name": request.tool_name, **data},
        )

    gateway.register("document.list_visible", list_visible_documents)
    gateway.register("document.get_status_by_name", get_document_status_by_name)
