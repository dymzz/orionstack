"""Unified chat accepts requests, never client routing, identity or graph control."""
import json
from contextlib import AsyncExitStack
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
from app.api.core_access import require_core_access
from app.api.routes.core_knowledge import translate_error, CORE_ERRORS
from app.knowledge.contracts import AccessContext
from app.knowledge.postgres import DatabaseUnavailable
from app.config.core_settings import CoreConfigurationError
from app.providers.http import ProviderError
from app.workbench.user_feedback import FeedbackConflict
from app.dataops.ports import DependencyUnavailable
from app.graphs.contracts import ChatInput, ChatOutput
from app.graphs.service import ConversationService

router=APIRouter(prefix='/api/chat',tags=['conversation'])


def get_conversation_service():
    try:return ConversationService()
    except DependencyUnavailable:raise HTTPException(503,"Authorization dependency unavailable") from None


def failure(error):
    if isinstance(error,FeedbackConflict):return HTTPException(409,'Conversation is busy or message ID conflicts')
    return translate_error(error)


@router.post('/threads',responses=CORE_ERRORS)
async def create_thread(access:AccessContext=Depends(require_core_access),service=Depends(get_conversation_service)):
    try:return await run_in_threadpool(service.repository.create,access)
    except (LookupError,DatabaseUnavailable,CoreConfigurationError) as error:raise failure(error) from None


@router.get('/threads',responses=CORE_ERRORS)
async def list_threads(access:AccessContext=Depends(require_core_access),service=Depends(get_conversation_service)):
    try:return await run_in_threadpool(service.repository.list,access)
    except (LookupError,DatabaseUnavailable,CoreConfigurationError) as error:raise failure(error) from None


@router.get('/{thread_id}/messages',responses=CORE_ERRORS)
async def transcript(thread_id:UUID,access:AccessContext=Depends(require_core_access),service=Depends(get_conversation_service)):
    try:return await run_in_threadpool(service.repository.transcript,thread_id,access)
    except (LookupError,DatabaseUnavailable,CoreConfigurationError) as error:raise failure(error) from None


@router.post('/{thread_id}/messages',response_model=ChatOutput,responses={**CORE_ERRORS,
    200:{'description':'Final JSON result, or ordered SSE status/token/result events when Accept is text/event-stream',
         'content':{'text/event-stream':{'schema':{'type':'string'}}}},
    404:{'description':'Owned conversation or current source content unavailable'},
    409:{'description':'Conversation busy, unfinished input, or idempotency conflict'}})
async def send_message(thread_id:UUID,payload:ChatInput,request:Request,
                       access:AccessContext=Depends(require_core_access),service=Depends(get_conversation_service)):
    stack=AsyncExitStack()
    try:
        events=await stack.enter_async_context(service.prepare(thread_id,payload,access))
        if 'text/event-stream' not in request.headers.get('accept',''):
            try:
                result=None
                async for event in events:
                    if event['type']=='result':result=event['data']
                if result is None:raise DatabaseUnavailable('Conversation result unavailable')
                return ChatOutput.model_validate(result)
            finally:await stack.aclose()
        first=await anext(events)
    except (LookupError,FeedbackConflict,DatabaseUnavailable,CoreConfigurationError,ProviderError) as error:
        await stack.aclose()
        raise failure(error) from None

    async def stream():
        def encode(event):return 'event: '+event['type']+'\ndata: '+json.dumps(event,ensure_ascii=False)+'\n\n'
        try:
            yield encode(first)
            async for event in events:yield encode(event)
        except (LookupError,FeedbackConflict,DatabaseUnavailable,CoreConfigurationError,ProviderError):
            yield encode({'type':'error','message':'本次处理未完成，请刷新会话核对运行状态。'})
        finally:
            await events.aclose()
            await stack.aclose()
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
