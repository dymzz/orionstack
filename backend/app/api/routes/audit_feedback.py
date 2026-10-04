"""Core-domain user signals and current-access audit; legacy JSONL routes are separate."""
from typing import Literal
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from app.api.core_access import require_core_access
from app.api.routes.core_knowledge import CORE_ERRORS, translate_error
from app.config.core_settings import CoreConfigurationError
from app.knowledge.contracts import AccessContext
from app.knowledge.postgres import DatabaseUnavailable
from app.dataops.ports import DependencyUnavailable
from app.workbench.audit import RunAuditRepository
from app.workbench.user_feedback import UserFeedbackRepository, FeedbackConflict
from app.workbench.audit_contracts import UserFeedbackRequest, UserFeedbackResponse, RunList, RunAudit, RetrievalAudit

router=APIRouter(prefix='/api',tags=['domain-audit'])
AUDIT_ERRORS={**CORE_ERRORS,404:{'description':'Run is unavailable to this current principal'},
              400:{'description':'Invalid feedback target or pagination cursor'}}


def get_run_audit_repository():
    try: return RunAuditRepository()
    except DependencyUnavailable:
        raise HTTPException(503,'Authorization dependency is unavailable') from None


def get_user_feedback_repository():
    try: return UserFeedbackRepository()
    except DependencyUnavailable:
        raise HTTPException(503,'Authorization dependency is unavailable') from None


def audit_error(error):
    if isinstance(error,FeedbackConflict): return HTTPException(409,'Idempotency key refers to different feedback')
    if isinstance(error,DependencyUnavailable): return HTTPException(503,'Authorization dependency is unavailable')
    return translate_error(error)


@router.post('/feedback',response_model=UserFeedbackResponse,status_code=201,
    responses={**AUDIT_ERRORS,200:{'description':'Same feedback replayed without another write'},409:{'description':'Idempotency conflict'}})
def user_feedback(payload:UserFeedbackRequest,response:Response,access:AccessContext=Depends(require_core_access),
                  repository=Depends(get_user_feedback_repository)):
    try:
        result=repository.submit(payload,access)
        response.status_code=200 if result.replayed else 201
        return result
    except (LookupError,ValueError,FeedbackConflict,DatabaseUnavailable,CoreConfigurationError,DependencyUnavailable) as error:
        raise audit_error(error) from None


@router.get('/query-runs',response_model=RunList,responses=AUDIT_ERRORS)
def list_runs(access:AccessContext=Depends(require_core_access),repository=Depends(get_run_audit_repository),
              limit:int=Query(default=20,ge=1,le=50),cursor:str|None=Query(default=None,max_length=512),
              mode:Literal['knowledge','general_chat']|None=None,
              status:Literal['answered','insufficient_evidence','failed']|None=None):
    try: return repository.list_runs(access,limit=limit,cursor=cursor,mode=mode,status=status)
    except (LookupError,ValueError,DatabaseUnavailable,CoreConfigurationError,DependencyUnavailable) as error:
        raise audit_error(error) from None


@router.get('/query-runs/{request_id}',response_model=RunAudit,responses=AUDIT_ERRORS)
def read_run(request_id:str,access:AccessContext=Depends(require_core_access),repository=Depends(get_run_audit_repository)):
    if not 0<len(request_id)<=128: raise HTTPException(404,'Run is unavailable')
    try: return repository.read(request_id,access)
    except (LookupError,ValueError,DatabaseUnavailable,CoreConfigurationError,DependencyUnavailable) as error:
        raise audit_error(error) from None


@router.get('/retrieval-events/{event_id}',response_model=RetrievalAudit,responses=AUDIT_ERRORS)
def read_event(event_id:str,access:AccessContext=Depends(require_core_access),repository=Depends(get_run_audit_repository)):
    if not 0<len(event_id)<=128: raise HTTPException(404,'Event is unavailable')
    try: return repository.read_event(event_id,access)
    except (LookupError,ValueError,DatabaseUnavailable,CoreConfigurationError,DependencyUnavailable) as error:
        raise audit_error(error) from None
