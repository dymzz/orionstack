"""Routing uses independent flags and checkpoints only serializable business state."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace
import pytest
import httpx
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import ValidationError
from app.graphs.conversation import conversation_graph, OrionRuntime
from app.graphs.contracts import ChatInput, RouteDecision
from app.graphs.context import model_history
from app.graphs.streaming_model import StreamingTransport
from app.providers.http import ProviderError
from app.knowledge.contracts import AccessContext


class Dump(dict):
    def model_dump(self,**kwargs):return dict(self)


def runtime(route,events):
    class Judge:
        def evaluate(self,message,history):events.append('analyze');return route
    class Knowledge:
        def query(self,request,access):
            events.append('retrieve')
            return Dump(answer='checked excerpt',request_id='next-run',retrieval_event_id='event',
                processing_run_id='processing',status='answered',final_candidate_count=1,execution_feedback={})
    class Feedback:
        def submit(self,request,access):
            events.append(('feedback',request.request_id,request.origin))
            return SimpleNamespace(feedback=Dump(id='feedback'))
    audit=SimpleNamespace(read=lambda id,access:SimpleNamespace(run=SimpleNamespace(status='answered',
        execution_feedback=SimpleNamespace(retrieval_event_id='old-event'))))
    return OrionRuntime(AccessContext(tenant_id='test',user_id='user'), 'thread', set(),Judge(),Knowledge(),None,Feedback(),audit)


def route(**changes):return RouteDecision(needs_retrieval=True,is_feedback=False,retrieval_query='standalone question',reason='criteria',**changes)


def run_graph(rt,initial=None):
    async def execute():
        graph=conversation_graph(InMemorySaver());config={'configurable':{'thread_id':'test'}}
        result=await graph.ainvoke({'messages':[HumanMessage(content='correct that and check the policy',id='input',additional_kwargs={'turn_id':'input'})],
            'current_message_id':'input','last_run_id':'old-run',**(initial or {})},config,context=rt)
        return result,(await graph.aget_state(config)).values
    return asyncio.run(execute())


def test_feedback_and_retrieval_are_both_executed_in_order():
    events=[];rt=runtime(RouteDecision(needs_retrieval=True,is_feedback=True,feedback_value='correction',retrieval_query='current policy',reason='both'),events)
    result,saved=run_graph(rt)
    assert events==['analyze',('feedback','old-run','user_submission'),'retrieve']
    assert result['feedback']['id']=='feedback' and result['last_run_id']=='next-run'
    assert saved['response']['kind']=='knowledge' and isinstance(saved['messages'][-1],AIMessage)
    assert not any(name in saved for name in ('access','judge','db','provider','api_key'))


def test_native_retry_only_retries_transient_dependency_errors():
    events=[];rt=runtime(route(),events)
    class Retry:
        def evaluate(self,message,history):
            events.append('attempt')
            if len(events)==1:raise ProviderError('deepseek','http_error',429)
            return route()
    rt.judge=Retry();result,_=run_graph(rt)
    assert events==['attempt','attempt','retrieve'] and result['response']['kind']=='knowledge'


@pytest.mark.parametrize('code',['invalid_response','unverified_excerpt_response'])
def test_unverified_or_invalid_output_fails_without_retry_or_fake_answer(code):
    events=[];rt=runtime(route(),events)
    class Broken:
        def evaluate(self,message,history):events.append('once');raise ProviderError('deepseek',code)
    rt.judge=Broken();result,_=run_graph(rt)
    assert events==['once'] and result['response']['kind']=='failure'
    assert result['error']=={'node':'analyze','code':code}


def test_context_filters_revoked_turns_and_trims_without_mutating_state():
    history=[HumanMessage(content='sensitive',additional_kwargs={'turn_id':'old'}),
        AIMessage(content='private policy',additional_kwargs={'turn_id':'old'}),
        HumanMessage(content='remember code',additional_kwargs={'turn_id':'allowed'}),
        AIMessage(content='CODE',additional_kwargs={'turn_id':'allowed'}),HumanMessage(content='now',additional_kwargs={'turn_id':'current'})]
    before=[m.content for m in history]
    filtered=model_history(history,{'allowed'},'current')
    assert filtered==[{'role':'user','content':'remember code'},{'role':'assistant','content':'CODE'}]
    assert [m.content for m in history]==before


@pytest.mark.parametrize('extra',[{'mode':'knowledge'},{'tenant_id':'other'},{'roles':['admin']},{'checkpoint_id':'x'},{'message':'  '}])
def test_unified_request_forbids_caller_control(extra):
    with pytest.raises(ValidationError):ChatInput.model_validate({'message':'hello',**extra})


def test_stream_adapter_preserves_real_tokens_and_checks_stop():
    events=[]
    body='data: {"model":"deepseek-test","choices":[{"delta":{"role":"assistant","content":"hello"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{"content":" world"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
    transport=StreamingTransport(events.append,httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,text=body))))
    result=transport.post('https://example.test',content=b'{}',headers={},timeout=1)
    assert result.json()['choices'][0]['message']['content']=='hello world'
    assert [e['text'] for e in events]==['hello',' world']


@pytest.mark.parametrize('body',['data: [DONE]\n\n','data: {"choices":[{"delta":{"tool_calls":[{}]},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'])
def test_stream_never_accepts_incomplete_or_tool_output(body):
    transport=StreamingTransport(lambda _:None,httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,text=body))))
    with pytest.raises(ProviderError):transport.post('https://example.test',content=b'{}',headers={},timeout=1)
