"""Authenticated core query: persisted raw retrieval, quote-grounded output, current-source checks."""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import Field, ValidationError, model_validator

from app.config.core_settings import CoreSettings, CoreConfigurationError
from app.decision.grounded_answer import GroundedAnswer, GroundedAnswerClient, insufficient_answer
from app.evidence.contracts import EvidenceBundle, EvidenceItem
from app.evidence.chain_profile import document_chain
from app.knowledge.contracts import CoreContract, QueryContext, AccessContext
from app.knowledge.evidence_validity import EvidenceValidityRepository
from app.knowledge.postgres import PostgresDatabase, DatabaseUnavailable
from app.knowledge.embedding import create_embedding_client
from app.providers.http import ProviderError
from app.retrieval.postgres_vector import PostgresVectorRetriever
from app.retrieval.raw_journal import PostgresRawJournal
from app.retrieval.raw_pipeline import RawRetrievalPipeline
from app.config.runtime_versions import RuntimeVersions, runtime_versions
from app.decision.model_call import observed_call, skipped_call
from app.workbench.contracts import RunFeedback
from app.workbench.repository import WorkbenchRunRepository


class CoreQueryRequest(QueryContext):
    document_ids: tuple[str, ...] = Field(default=(),max_length=50)
    top_k: int = Field(default=20,ge=1,le=100,strict=True)
    final_top_k: int = Field(default=5,ge=1,le=5,strict=True)


class PreparedQuery(CoreContract):
    request_id: str
    request: CoreQueryRequest
    event_id: str
    processing_run_id: str


class CoreQueryResponse(GroundedAnswer):
    tenant_id: str = Field(min_length=1)
    runtime_versions: RuntimeVersions = Field(default_factory=RuntimeVersions)
    request_id: str
    retrieval_event_id: str
    processing_run_id: str
    processing_status: str
    raw_candidate_count: int
    final_candidate_count: int
    checked_at: datetime
    # Additive for existing P0 clients/adapters; the real service always supplies it.
    evidence_bundle: EvidenceBundle | None = None
    execution_feedback: RunFeedback | None = None

    @model_validator(mode='after')
    def same_tenant(self):
        if self.evidence_bundle and self.evidence_bundle.tenant_id != self.tenant_id:
            raise ValueError('Answer and evidence must share a tenant')
        if self.execution_feedback and (self.execution_feedback.request_id != self.request_id
                or self.execution_feedback.mode != 'knowledge' or self.execution_feedback.outcome != self.status):
            raise ValueError('Knowledge answer and run feedback disagree')
        return self


class CoreQueryService:
    def __init__(self, database=None, pipeline=None, answer_client=None, validity=None, settings=None):
        settings = settings or CoreSettings()
        self.database = database or PostgresDatabase(settings)
        journal = PostgresRawJournal(self.database)
        processors = ()
        if settings.query_use_jev:
            from app.decision.retrieval_processors import JevRetrievalProcessor
            from app.decision.jev import JevClient
            processors = (JevRetrievalProcessor(JevClient(settings)),)
        if settings.retrieval_adapter=="langchain_postgres":
            from app.retrieval.langchain_postgres import LangChainPostgresRetriever
            retriever=LangChainPostgresRetriever(self.database,journal,settings)
        else:retriever=PostgresVectorRetriever(self.database,journal)
        self.pipeline = pipeline or RawRetrievalPipeline(embedding=create_embedding_client(settings),
                                                        retriever=retriever,
                                                        journal=journal,processors=processors)
        self.answer_client = answer_client or GroundedAnswerClient(settings)
        self.validity = validity or EvidenceValidityRepository(self.database)

    def query(self, request: CoreQueryRequest, access: AccessContext) -> CoreQueryResponse:
        request_id,context,retrieved=self._retrieve(request,access)
        return self._answer(request,access,request_id,context,retrieved)

    def retrieve_query(self,request:CoreQueryRequest,access:AccessContext) -> PreparedQuery:
        request_id,_,retrieved=self._retrieve(request,access)
        return PreparedQuery(request_id=request_id,request=request,event_id=retrieved.raw.event.id,
            processing_run_id=retrieved.processing.id)

    def answer_query(self,prepared:PreparedQuery,access:AccessContext) -> CoreQueryResponse:
        from app.workbench.audit import RunAuditRepository
        from app.retrieval.raw_contracts import RetrievalResponse
        raw=PostgresRawJournal(self.database).load_raw(prepared.event_id,access)
        if raw.event.user_id!=access.user_id:raise PermissionError('Prepared query is not owned by this principal')
        with self.database.connection() as connection:
            runs,_=RunAuditRepository.processing(connection,prepared.event_id,access)
        processing=next((run for run in runs if run.id==prepared.processing_run_id),None)
        if processing is None:raise LookupError('Prepared processing run unavailable')
        request=prepared.request
        if (request.query!=raw.event.query or request.document_ids!=raw.event.document_ids or request.top_k!=raw.event.top_k
                or request.final_top_k!=processing.final_top_k):raise ValueError('Prepared query parameters do not match sealed retrieval')
        retrieved=RetrievalResponse(raw=raw,processing=processing)
        return self._answer(request,access,prepared.request_id,
            QueryContext(query=request.query,document_ids=request.document_ids,entities=request.entities),retrieved)

    def _retrieve(self,request,access):
        request_id = str(uuid4())
        context = QueryContext(query=request.query,document_ids=request.document_ids,entities=request.entities)
        try:
            retrieved = self.pipeline.retrieve(context,access,top_k=request.top_k,final_top_k=request.final_top_k)
        except (ProviderError,CoreConfigurationError,DatabaseUnavailable) as error:
            feedback=RunFeedback(request_id=request_id,mode='knowledge',outcome='failed',reason='retrieval_failed',
                                 model_call=skipped_call('retrieval_failed'))
            self._record_failure(request,access,feedback,error)
            raise
        retrieved.raw.require_access(access)
        return request_id,context,retrieved

    def _answer(self,request,access,request_id,context,retrieved):
        retrieved.raw.require_access(access)
        event = retrieved.raw.event
        versions=runtime_versions(event.embedding_configuration,event.top_k,
                                  processing_configuration=retrieved.processing.configuration_json,retrieval_method=event.retrieval_method)
        versions=versions.model_copy(update={"retrieval_profile_version":event.runtime_versions.retrieval_profile_version})
        try:
            candidates = self.validity.before_generation(retrieved.final_candidates,access)
        except (DatabaseUnavailable,CoreConfigurationError) as error:
            feedback=RunFeedback(request_id=request_id,mode='knowledge',outcome='failed',reason='sources_unavailable',
                model_call=skipped_call('sources_unavailable'),retrieval_event_id=event.id,
                processing_run_id=retrieved.processing.id,raw_candidate_count=len(retrieved.raw.candidates),runtime_versions=versions)
            self._record_failure(request,access,feedback,error)
            raise
        reason=('no_raw_candidates' if not retrieved.raw.candidates else
                'processing_filtered_all' if not retrieved.final_candidates else 'sources_unavailable')
        call=skipped_call(reason)
        try:
            if not candidates:
                draft = insufficient_answer()
            else:
                generated = self.answer_client.generate(context,
                    tuple(c.evidence(access.tenant_id,event.created_at) for c in candidates),access)
                call=observed_call(self.answer_client)
                try:
                    # Revalidate at the core boundary, including model_copy/adapter output.
                    material = generated.model_dump(warnings=False) if isinstance(generated,GroundedAnswer) else generated
                    draft = GroundedAnswer.model_validate(material)
                except (ValidationError,TypeError,ValueError):
                    raise ProviderError("deepseek","invalid_grounded_answer") from None
        except (ProviderError,CoreConfigurationError) as error:
            feedback=RunFeedback(request_id=request_id,mode='knowledge',outcome='failed',
                reason='configuration_missing' if isinstance(error,CoreConfigurationError) else
                       'unverified_answer' if error.code in {'unverified_excerpt_response','invalid_grounded_answer'} else 'provider_failed',
                model_call=observed_call(self.answer_client),retrieval_event_id=event.id,
                processing_run_id=retrieved.processing.id,raw_candidate_count=len(retrieved.raw.candidates),
                final_candidate_count=len(candidates),runtime_versions=versions)
            self._record_failure(request,access,feedback,error)
            raise
        # Treat even injected clients as untrusted: recheck quote identity before returning.
        known = {c.candidate_id:c for c in candidates}
        if draft.status != "answered":
            draft = insufficient_answer().model_copy(update={"model":draft.model})
            if candidates:
                reason='model_insufficient_evidence'
        elif (not draft.citations
                or draft.answer != "\n\n".join(c.quote for c in draft.citations)
                or len({(c.evidence_id,c.quote) for c in draft.citations}) != len(draft.citations)
                or any(c.evidence_id not in known or c.source != known[c.evidence_id].source
                       or not c.quote.strip() or c.quote not in known[c.evidence_id].text for c in draft.citations)):
            draft = insufficient_answer()
            reason='unverified_answer'
        else:
            draft = draft.model_copy(update={"validation":"source_and_quote_checked"})
            reason='answered'
        try:
            return self._complete(request,access,retrieved,candidates,draft,request_id,versions,call,reason)
        except (DatabaseUnavailable,CoreConfigurationError) as error:
            error.request_id=request_id
            error.retrieval_event_id=event.id
            error.execution_feedback=RunFeedback(request_id=request_id,mode='knowledge',outcome='failed',reason='audit_unavailable',
                model_call=call,retrieval_event_id=event.id,processing_run_id=retrieved.processing.id,
                raw_candidate_count=len(retrieved.raw.candidates),final_candidate_count=len(candidates),
                runtime_versions=versions,audit_status='unavailable')
            raise

    def _complete(self,request,access,retrieved,candidates,draft,request_id,versions,call,reason):
        event=retrieved.raw.event
        with self.database.connection() as connection:
            with connection.transaction():
                current = self.validity.valid_candidates(connection,candidates,access,lock=True)
                current_ids = {c.candidate_id for c in current}
                if any(c.evidence_id not in current_ids for c in draft.citations):
                    draft = insufficient_answer().model_copy(update={'model':draft.model})
                    reason='source_changed'
                checked_at = datetime.now(timezone.utc)
                observations = self.validity.source_observations(connection,current,access)
                bundle = EvidenceBundle(tenant_id=access.tenant_id,retrieval_event_id=event.id,processing_run_id=retrieved.processing.id,
                    items=tuple(EvidenceItem(tenant_id=access.tenant_id,evidence_id=c.candidate_id,source=c.source,raw_rank=c.rank,
                        vector_score=c.similarity_score,chain=document_chain(retrieved.raw,c,
                            observations.get(c.candidate_id),checked_at),
                        evaluations=tuple(e for e in retrieved.processing.evaluations
                                          if e.candidate_id in (None,c.candidate_id))) for c in current))
                feedback=RunFeedback(request_id=request_id,mode='knowledge',outcome=draft.status,reason=reason,
                    model_call=call,retrieval_event_id=event.id,processing_run_id=retrieved.processing.id,
                    raw_candidate_count=len(retrieved.raw.candidates),final_candidate_count=len(current),runtime_versions=versions)
                result = CoreQueryResponse(**draft.model_dump(),tenant_id=access.tenant_id,
                    runtime_versions=versions,
                    request_id=request_id,retrieval_event_id=event.id,
                    processing_run_id=retrieved.processing.id,processing_status=retrieved.processing.status,
                    raw_candidate_count=len(retrieved.raw.candidates),final_candidate_count=len(current),
                    checked_at=checked_at,evidence_bundle=bundle,execution_feedback=feedback)
                self.validity.save_answer(connection,event.id,request_id,access,result.model_dump(mode="json"))
                WorkbenchRunRepository.save(connection,access,request.model_dump(mode='json'),result.model_dump(mode='json'))
        return result

    def _record_failure(self,request,access,feedback,error):
        error.request_id=feedback.request_id
        error.retrieval_event_id=feedback.retrieval_event_id
        error.execution_feedback=feedback
        response={'status':'failed','error_code':f'{error.provider}:{error.code}' if isinstance(error,ProviderError) else
                  'configuration_error' if isinstance(error,CoreConfigurationError) else 'database_unavailable',
                  'execution_feedback':feedback.model_dump(mode='json')}
        try:
            with self.database.connection() as connection:
                with connection.transaction():
                    if feedback.retrieval_event_id:
                        self.validity.save_answer(connection,feedback.retrieval_event_id,feedback.request_id,access,response)
                    WorkbenchRunRepository.save(connection,access,request.model_dump(mode='json'),response)
        except (DatabaseUnavailable,CoreConfigurationError):
            error.execution_feedback=feedback.model_copy(update={'audit_status':'unavailable'})
