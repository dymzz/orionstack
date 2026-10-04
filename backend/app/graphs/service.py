"""Conversation HTTP orchestration; LangGraph owns checkpoints and execution state."""
import asyncio
import hashlib
from contextlib import asynccontextmanager
from uuid import UUID
import psycopg
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages import HumanMessage
from app.config.core_settings import CoreSettings
from app.knowledge.postgres import DatabaseUnavailable
from app.services.core_query_service import CoreQueryService
from app.workbench.service import GeneralChatService
from app.workbench.user_feedback import UserFeedbackRepository, FeedbackConflict
from app.graphs.repository import ConversationRepository
from app.graphs.conversation import conversation_graph, OrionRuntime
from app.graphs.judge import DeepSeekJudge
from app.graphs.streaming_model import StreamingGeneralChatClient
from app.graphs.contracts import ChatOutput


@asynccontextmanager
async def checkpoint_connection(settings):
    try:
        connection=await psycopg.AsyncConnection.connect(settings.require_database_url(),
            autocommit=True,prepare_threshold=0,row_factory=dict_row,
            connect_timeout=settings.database_connect_timeout_seconds,
            options='-c search_path=conversation_checkpoint,pg_catalog,public')
        async with connection:
            row=await (await connection.execute("SELECT to_regclass('conversation_checkpoint.checkpoints') AS present")).fetchone()
            if not row['present']: raise DatabaseUnavailable('Conversation checkpointer is not configured')
            yield connection
    except psycopg.Error:
        raise DatabaseUnavailable('Conversation checkpoint operation failed') from None


class ConversationService:
    def __init__(self,repository=None,settings=None,runtime_factory=None):
        self.settings=settings or CoreSettings()
        self.repository=repository or ConversationRepository()
        self.runtime_factory=runtime_factory or self.runtime

    def runtime(self,access,thread_id,allowed,origin):
        database=self.repository.database
        from app.graphs.jev_judge import JevRouteJudge
        judge=JevRouteJudge(self.settings) if self.settings.chat_judge=='jev' else DeepSeekJudge(self.settings)
        return OrionRuntime(access=access,thread_id=str(thread_id),allowed_turn_ids=allowed,
            judge=judge,knowledge=CoreQueryService(database=database,settings=self.settings),
            direct_factory=lambda writer:GeneralChatService(database,
                StreamingGeneralChatClient(writer,self.settings),self.settings),
            feedback_service=UserFeedbackRepository(database),audit=self.repository.audit,origin=origin)

    @asynccontextmanager
    async def prepare(self,thread_id:UUID,payload,access):
        # Ownership and Cedar gate run before checkpoint loading. The session lock
        # serializes this conversation, without holding a transaction over a model call.
        manager=self.repository.database.connection()
        connection=await asyncio.to_thread(manager.__enter__)
        lock=int.from_bytes(hashlib.sha256((access.tenant_id+':'+str(thread_id)).encode()).digest()[:8],'big',signed=True)
        acquired=False
        try:
            await asyncio.to_thread(self.repository.require_thread,connection,thread_id,access)
            acquired=(await asyncio.to_thread(lambda:connection.execute('SELECT pg_try_advisory_lock(%s)',(lock,)).fetchone()))[0]
            if not acquired:raise FeedbackConflict('Conversation is processing another message')
            existing=await asyncio.to_thread(self.repository.input,connection,thread_id,payload,access)
            if existing:
                output=ChatOutput.model_validate(existing[0])
                if not await asyncio.to_thread(self.repository.visible,existing[0],access):raise LookupError('Conversation content unavailable')
                yield self.replay(output)
            else:
                transcript=await asyncio.to_thread(self.repository.transcript,thread_id,access)
                allowed={item['client_message_id'] for item in transcript['items'] if item['response'] and item['content_access']=='available'}
                runtime=self.runtime_factory(access,thread_id,allowed,payload.origin)
                async with checkpoint_connection(self.settings) as checkpoint:
                    graph=conversation_graph(AsyncPostgresSaver(checkpoint))
                    config={'configurable':{'thread_id':str(thread_id)}}
                    saved=await graph.aget_state(config)
                    prior=saved.values.get('current_message_id')
                    if saved.next and prior!=str(payload.client_message_id):
                        raise FeedbackConflict('Resume the unfinished message before sending another')
                    material=None if saved.next else {
                        'messages':[HumanMessage(content=payload.message,id=str(payload.client_message_id),
                            additional_kwargs={'turn_id':str(payload.client_message_id)})],
                        'current_message_id':str(payload.client_message_id),'route':None,'retrieval':None,
                        'feedback':None,'response':None,'error':None,'routing_call':None,'pending_action':None,
                        'runtime_versions':self.versions()}
                    completed=prior==str(payload.client_message_id) and not saved.next and saved.values.get('response')
                    yield self.execute(graph,config,runtime,material,completed,connection,thread_id,payload,access)
        finally:
            try:
                if acquired: await asyncio.to_thread(connection.execute,'SELECT pg_advisory_unlock(%s)',(lock,))
            finally: await asyncio.to_thread(manager.__exit__,None,None,None)

    async def replay(self,output):
        yield {'type':'result','data':output.model_copy(update={'replayed':True}).model_dump(mode='json')}

    def versions(self):
        from app.graphs.versions import conversation_versions
        return conversation_versions(self.settings,self.repository.audit.authorizer.version)

    async def execute(self,graph,config,runtime,material,completed,connection,thread_id,payload,access):
        if not completed:
            try:
                async for mode,data in graph.astream(material,config,context=runtime,stream_mode=['custom']):
                    if mode=='custom':yield data
            except Exception:
                # LangGraph 1.2 custom streams can re-raise a handled node error
                # after the error handler has checkpointed its final response.
                saved=await graph.aget_state(config)
                if saved.next or (saved.values.get('response') or {}).get('kind')!='failure':raise
        state=(await graph.aget_state(config)).values
        response=state.get('response')
        if not response:raise DatabaseUnavailable('Conversation did not produce a final result')
        output=ChatOutput(thread_id=thread_id,client_message_id=payload.client_message_id,
            route=state.get('route'),routing_call=state.get('routing_call'),feedback=state.get('feedback'),
            conversation_versions=state.get('runtime_versions') or {},**response)
        body=output.model_dump(mode='json')
        # Recheck current source access before publishing or storing a reusable body.
        if not await asyncio.to_thread(self.repository.visible,body,access):raise LookupError('Conversation content unavailable')
        await asyncio.to_thread(self.repository.output,connection,thread_id,payload.client_message_id,body,access)
        yield {'type':'result','data':body}
