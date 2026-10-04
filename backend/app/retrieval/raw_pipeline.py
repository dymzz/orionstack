"""Raw retrieval completes and commits before optional downstream processing."""

import json
from typing import Protocol

from app.knowledge.contracts import AccessContext, CoreContract, QueryContext
from app.knowledge.embedding import create_embedding_client
from app.providers.http import ProviderError
from app.retrieval.postgres_vector import PostgresVectorRetriever
from app.retrieval.raw_contracts import ProcessingRun, RawRetrievalRecord, RetrievalEvaluation, RetrievalResponse
from app.retrieval.raw_journal import PostgresRawJournal


class ProcessorResult(CoreContract):
    selected_candidate_ids: tuple[str, ...]
    evaluations: tuple[RetrievalEvaluation, ...] = ()


class DownstreamProcessor(Protocol):
    name: str

    def configuration(self) -> dict: ...

    def process(self, record: RawRetrievalRecord, candidate_ids: tuple[str, ...],
                access: AccessContext) -> ProcessorResult: ...


class RawRetrievalPipeline:
    def __init__(self, embedding=None, retriever=None, journal=None,
                 processors: tuple[DownstreamProcessor, ...] = ()) -> None:
        self.embedding = embedding or create_embedding_client()
        self.journal = journal or PostgresRawJournal()
        self.retriever = retriever or PostgresVectorRetriever(journal=self.journal)
        self.processors = processors
        if any(not processor.name or processor.name in {"human", "user_feedback", "known_answer"}
               for processor in processors):
            raise ValueError("Automated processors cannot claim human or known-answer label provenance")

    def retrieve(self, context: QueryContext, access: AccessContext, *, top_k: int = 20,
                 final_top_k: int | None = None) -> RetrievalResponse:
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
            raise ValueError("top_k must be between 1 and 100")
        self._validate_final_limit(final_top_k)
        if context.entities:
            raise ValueError("Resolve entity document scope before vector retrieval")
        # Test/custom implementations predating query prompting retain their document-only API.
        batch = (self.embedding.embed_query(context.query) if hasattr(self.embedding, "embed_query")
                 else self.embedding.embed((context.query,)))
        raw = self.retriever.retrieve_and_record(context, access, batch, top_k)
        return self.process(raw, access, final_top_k=final_top_k)

    def process(self, raw: RawRetrievalRecord, access: AccessContext, *,
                final_top_k: int | None = None) -> RetrievalResponse:
        self._validate_final_limit(final_top_k)
        raw.require_access(access)
        stable_json = raw.model_dump_json()
        raw = RawRetrievalRecord.model_validate_json(stable_json)
        original_ids = tuple(candidate.candidate_id for candidate in raw.candidates)
        current = original_ids
        evaluations = []
        configurations = []
        status = "completed"
        error_code = None
        try:
            for processor in self.processors:
                configuration = {**processor.configuration(), "evaluator": processor.name}
                json.dumps(configuration, allow_nan=False)
                configurations.append(configuration)
                processor_input = RawRetrievalRecord.model_validate_json(stable_json)
                result = processor.process(processor_input, current, access)
                if processor_input.model_dump_json() != stable_json:
                    raise ValueError("Processor attempted to rewrite raw retrieval facts")
                if (len(set(result.selected_candidate_ids)) != len(result.selected_candidate_ids)
                        or not set(result.selected_candidate_ids).issubset(current)
                        or any(evaluation.evaluator != processor.name
                               or (evaluation.candidate_id is not None and evaluation.candidate_id not in current)
                               for evaluation in result.evaluations)):
                    raise ValueError("Processor must return IDs and evaluations belonging to its raw input")
                # Only IDs can affect final ordering; returned data never replaces raw snapshots.
                current = result.selected_candidate_ids
                evaluations.extend(result.evaluations)
        except PermissionError:
            raise
        except Exception as error:
            current = original_ids
            status = "raw_fallback"
            error_code = (f"{error.provider}:{error.code}" if isinstance(error, ProviderError)
                          else type(error).__name__)
        run = ProcessingRun(
            event_id=raw.event.id, processors=tuple(processor.name for processor in self.processors),
            configuration_json=json.dumps(configurations, ensure_ascii=False, allow_nan=False),
            final_top_k=final_top_k, status=status, error_code=error_code,
            selected_candidate_ids=current[:final_top_k] if final_top_k is not None else current,
            evaluations=tuple(evaluations),
        )
        response = RetrievalResponse(raw=raw, processing=run)
        self.journal.save_processing(raw, run, access)
        return response

    @staticmethod
    def _validate_final_limit(value):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100):
            raise ValueError("final_top_k must be between 1 and 100 when supplied")
