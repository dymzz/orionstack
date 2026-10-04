"""General conversation and owner-only run receipts use the existing identity boundary."""
from fastapi import APIRouter, Depends, HTTPException
from app.api.core_access import require_core_access
from app.api.routes.core_knowledge import CORE_ERRORS, translate_error, feedback_error_response
from app.config.core_settings import CoreConfigurationError
from app.knowledge.contracts import AccessContext
from app.knowledge.postgres import DatabaseUnavailable
from app.providers.http import ProviderError
from app.workbench.contracts import GeneralChatRequest, GeneralChatResponse, FeedbackResponse
from app.workbench.repository import WorkbenchRunRepository
from app.workbench.service import GeneralChatService

router=APIRouter(prefix='/api',tags=['workbench'])


def get_general_chat_service():
    return GeneralChatService()


def get_workbench_repository():
    return WorkbenchRunRepository()


@router.post('/chat',response_model=GeneralChatResponse,responses=CORE_ERRORS)
def general_chat(payload:GeneralChatRequest,access:AccessContext=Depends(require_core_access),
                 service=Depends(get_general_chat_service)):
    try:
        return service.chat(payload,access)
    except (CoreConfigurationError,ProviderError,DatabaseUnavailable) as error:
        if getattr(error,'execution_feedback',None) is not None:
            return feedback_error_response(error)
        raise translate_error(error) from None


@router.get('/workbench/runs/{request_id}/feedback',response_model=FeedbackResponse,
            responses={**CORE_ERRORS,404:{'description':'Receipt is unavailable to this authenticated actor'}})
def run_feedback(request_id:str,access:AccessContext=Depends(require_core_access),repository=Depends(get_workbench_repository)):
    if not request_id or len(request_id)>128:
        raise HTTPException(404,'Run receipt is unavailable')
    try:
        return repository.feedback(request_id,access)
    except (LookupError,DatabaseUnavailable,CoreConfigurationError) as error:
        raise translate_error(error) from None
