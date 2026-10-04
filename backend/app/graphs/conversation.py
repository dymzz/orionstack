"""An explicit graph; services, verified identity and secrets stay in Runtime context."""
import asyncio
from dataclasses import dataclass
from typing import Protocol
from langgraph.graph import StateGraph,MessagesState,START,END
from langgraph.runtime import Runtime
from langgraph.config import get_stream_writer
from langgraph.types import RetryPolicy,TimeoutPolicy,Command
from langgraph.errors import NodeError
from langchain_core.messages import AIMessage
from app.knowledge.contracts import AccessContext
from app.workbench.contracts import GeneralChatRequest
from app.workbench.audit_contracts import UserFeedbackRequest
from app.providers.http import ProviderError
from app.graphs.context import model_history
from app.graphs.contracts import RouteDecision


class OrionState(MessagesState):
    current_message_id: str
    route: dict | None
    retrieval: dict | None
    feedback: dict | None
    response: dict | None
    error: dict | None
    last_run_id: str | None
    pending_action: dict | None
    routing_call: dict | None
    runtime_versions: dict | None


@dataclass
class OrionRuntime:
    access: AccessContext
    thread_id: str
    allowed_turn_ids: set[str]
    judge: object
    knowledge: object
    direct_factory: object
    feedback_service: object
    audit: object
    origin: str = "user_submission"


def transient(error):
    return isinstance(error,ProviderError) and (error.code in ('timeout','transport_error')
        or error.status_code==429 or error.status_code in (502,503,504))


async def analyze(state:OrionState,runtime:Runtime[OrionRuntime]):
    get_stream_writer()({'type':'status','node':'analyze','message':'正在理解消息…'})
    history=model_history(state['messages'],runtime.context.allowed_turn_ids,state['current_message_id'])
    decision=await asyncio.to_thread(runtime.context.judge.evaluate,str(state['messages'][-1].content),history)
    from app.decision.model_call import observed_call
    return {'route':decision.model_dump(mode='json'),'routing_call':getattr(runtime.context.judge,'receipt',None) or observed_call(runtime.context.judge).model_dump(mode='json')}


async def record_feedback(state:OrionState,runtime:Runtime[OrionRuntime]):
    get_stream_writer()({'type':'status','node':'record_feedback','message':'正在保存反馈…'})
    target=state.get('last_run_id')
    if not target:
        return {'feedback':None}
    audit=await asyncio.to_thread(runtime.context.audit.read,target,runtime.context.access)
    value=state['route']['feedback_value']
    if value=='correction' and audit.run.status!='answered':
        return {'feedback':None}
    request=UserFeedbackRequest(request_id=target,event_id=audit.run.execution_feedback.retrieval_event_id,
        idempotency_key='graph-'+state['current_message_id'],kind='factual_correction' if value=='correction' else 'answer_helpfulness',
        value=value,comment=str(state['messages'][-1].content)[:2000],origin=runtime.context.origin)
    saved=await asyncio.to_thread(runtime.context.feedback_service.submit,request,runtime.context.access)
    return {'feedback':saved.feedback.model_dump(mode='json')}


def after_analyze(state):
    return 'record_feedback' if state['route']['is_feedback'] else 'decide'


def choose_next(state):
    route=state['route']
    if route['needs_retrieval']:return 'retrieve'
    if route['is_system_status'] or route['is_feedback']:return 'system'
    return 'direct'


async def decide(state:OrionState):
    return {}


async def retrieve(state:OrionState,runtime:Runtime[OrionRuntime]):
    from app.services.core_query_service import CoreQueryRequest
    get_stream_writer()({'type':'status','node':'retrieve','message':'正在查询内部资料…'})
    prepared=await asyncio.to_thread(runtime.context.knowledge.retrieve_query,
        CoreQueryRequest(query=state['route']['retrieval_query']),runtime.context.access)
    return {'retrieval':prepared.model_dump(mode='json')}


async def knowledge_answer(state:OrionState,runtime:Runtime[OrionRuntime]):
    from app.services.core_query_service import PreparedQuery
    get_stream_writer()({'type':'status','node':'knowledge_answer','message':'正在生成并核验资料回答…'})
    result=await asyncio.to_thread(runtime.context.knowledge.answer_query,
        PreparedQuery.model_validate(state['retrieval']),runtime.context.access)
    data=result.model_dump(mode='json')
    return {'response':{'kind':'knowledge','message':data['answer'],'result':data,'execution_feedback':data['execution_feedback']},
        'last_run_id':data['request_id']}


async def direct(state:OrionState,runtime:Runtime[OrionRuntime]):
    writer=get_stream_writer()
    writer({'type':'status','node':'direct','message':'正在生成通用回答…','reset_draft':True})
    history=model_history(state['messages'],runtime.context.allowed_turn_ids,state['current_message_id'])
    service=runtime.context.direct_factory(writer)
    request=GeneralChatRequest(query=str(state['messages'][-1].content),messages=tuple(history))
    result=await asyncio.to_thread(service.chat,request,runtime.context.access)
    data=result.model_dump(mode='json')
    return {'response':{'kind':'general_chat','message':data['answer'],'result':data,
            'execution_feedback':data['execution_feedback']},'last_run_id':data['request_id']}


async def system(state:OrionState,runtime:Runtime[OrionRuntime]):
    get_stream_writer()({'type':'status','node':'system','message':'正在读取服务端运行记录…'})
    receipt=None
    if state.get('last_run_id'):
        audit=await asyncio.to_thread(runtime.context.audit.read,state['last_run_id'],runtime.context.access)
        receipt=audit.run.execution_feedback.model_dump(mode='json')
    if state['route']['is_feedback']:
        message='反馈已保存，等待复核。' if state.get('feedback') else '当前没有可关联的已返回答案，请补充要纠正的内容。'
    elif receipt:
        call=receipt['model_call']
        message=f"上一条回答的模型调用状态：{call['status']}；原因：{receipt['reason']}。"
    else:message='当前会话还没有可核对的回答运行。'
    return {'response':{'kind':'system','message':message,'execution_feedback':receipt}}


async def answer(state:OrionState):
    response=state['response']
    writer=get_stream_writer()
    if response['kind'] in ('knowledge','system'):
        # Knowledge text is streamed only after the existing quote gate succeeds.
        text=response['message']
        for offset in range(0,len(text),80):
            writer({'type':'token','text':text[offset:offset+80],'source':'verified_result' if response['kind']=='knowledge' else 'server_fact'})
    writer({'type':'status','node':'answer','message':'处理完成'})
    return {'messages':[AIMessage(content=response['message'],id=state['current_message_id']+'-answer',
            additional_kwargs={'turn_id':state['current_message_id']})]}


async def node_error(state:OrionState,error:NodeError,runtime:Runtime[OrionRuntime]):
    receipt=getattr(error.error,'execution_feedback',None)
    response={'kind':'failure','message':'本次处理未完成，可在运行记录中核对原因。',
        'error_code':getattr(error.error,'code',None) or 'node_failed',
        'execution_feedback':receipt.model_dump(mode='json') if receipt else None}
    update={'error':{'node':error.node,'code':response['error_code']},'response':response}
    if receipt:update['last_run_id']=receipt.request_id
    if error.node=='analyze':
        from app.decision.model_call import observed_call
        update['routing_call']=getattr(runtime.context.judge,'receipt',None) or observed_call(runtime.context.judge).model_dump(mode='json')
    return Command(update=update,goto='answer')


def conversation_graph(checkpointer):
    builder=StateGraph(OrionState,context_schema=OrionRuntime)
    builder.set_node_defaults(retry_policy=RetryPolicy(max_attempts=2,retry_on=transient),
        timeout=TimeoutPolicy(run_timeout=120))
    for name,node in [('analyze',analyze),('record_feedback',record_feedback),('decide',decide),
                      ('retrieve',retrieve),('knowledge_answer',knowledge_answer),('direct',direct),('system',system),('answer',answer)]:
        # Feedback is idempotent, but a business rejection never qualifies for retry.
        builder.add_node(name,node,**({"error_handler":node_error} if name!="answer" else {}))
    builder.add_edge(START,'analyze')
    builder.add_conditional_edges('analyze',after_analyze,{'record_feedback':'record_feedback','decide':'decide'})
    builder.add_edge('record_feedback','decide')
    builder.add_conditional_edges('decide',choose_next,{'retrieve':'retrieve','direct':'direct','system':'system'})
    builder.add_edge('retrieve','knowledge_answer')
    for name in ('knowledge_answer','direct','system'):builder.add_edge(name,'answer')
    builder.add_edge('answer',END)
    return builder.compile(checkpointer=checkpointer)
