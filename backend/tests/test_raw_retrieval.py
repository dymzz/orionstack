import json
from pathlib import Path
import subprocess
import sys

import httpx
import pytest
from pydantic import ValidationError

from app.config.core_settings import CoreConfigurationError, CoreSettings
from app.decision.jev import JevClient
from app.decision.retrieval_processors import JevRetrievalProcessor, RuleRetrievalProcessor, ScoreRerankProcessor
from app.knowledge.contracts import AccessContext, QueryContext, SourceRef, content_hash
from app.knowledge.embedding import EmbeddingBatch, EmbeddingSignature, WorkersAIEmbeddingClient
from app.providers.http import ProviderError
from app.retrieval.raw_contracts import RawCandidate, RawRetrievalEvent, RawRetrievalRecord, RetrievalEvaluation
from app.retrieval.raw_pipeline import ProcessorResult, RawRetrievalPipeline
from app.retrieval.training import ApprovedLabel, derive_training_example


ACCESS = AccessContext(tenant_id="tenant-1", user_id="user-1")
CURATOR = AccessContext(tenant_id="tenant-1", user_id="curator", roles=("admin",))
QUERY = QueryContext(query="病假需要什么材料？")


def signature(dimensions=2):
    return EmbeddingSignature(model="@cf/baai/bge-m3", revision="test-revision", dimensions=dimensions)


def raw_record():
    candidates = []
    for rank, text in enumerate(("病假不需要医疗证明。", "病假需要医疗证明并提交审批。"), 1):
        chunk_id = f"chunk-{rank}"
        digest = content_hash(text)
        candidates.append(RawCandidate(
            candidate_id=f"candidate-{rank}", document_id=f"doc-{rank}", document_version="v1", chunk_id=chunk_id,
            content_hash=digest, rank=rank, similarity_score=1.0 - 0.1 * rank, text=text,
            access_scopes=("internal",),
            source=SourceRef(source_id=f"source-{rank}", source_version="v1", source_locator=f"uploads/policy-{rank}.md",
                             document_id=f"doc-{rank}", document_version="v1", chunk_id=chunk_id, content_hash=digest),
        ))
    return RawRetrievalRecord(event=RawRetrievalEvent(
        id="event-1", tenant_id=ACCESS.tenant_id, user_id=ACCESS.user_id, query=QUERY.query,
        query_hash=content_hash(QUERY.query), embedding_configuration=signature(), query_vector=(1.0, 0.0),
        top_k=20, candidate_count=2, allowed_scopes=("internal",),
    ), candidates=tuple(candidates))


class MemoryJournal:
    def __init__(self, record=None):
        self.raw = record
        self.runs = []
    def save_processing(self, raw, run, access):
        assert self.raw == raw, "Raw data must already be persisted"
        self.runs.append(run)


class EmbeddingStub:
    def embed(self, texts):
        assert texts == (QUERY.query,)
        return EmbeddingBatch(signature=signature(), vectors=((1.0, 0.0),),
                              input_hashes=(content_hash(texts[0]),))


class RetrievalStub:
    def __init__(self, journal):
        self.journal = journal
    def retrieve_and_record(self, context, access, batch, top_k):
        assert self.journal.raw is None
        self.journal.raw = raw_record()
        return self.journal.raw


def pipeline(processors=()):
    journal = MemoryJournal()
    return RawRetrievalPipeline(EmbeddingStub(), RetrievalStub(journal), journal, processors), journal


def test_core_default_does_not_import_jev_or_legacy_connectors():
    code = "import sys; sys.path.insert(0, 'backend'); from app.retrieval.raw_pipeline import RawRetrievalPipeline; assert 'app.decision.jev' not in sys.modules; assert not any('adapter' in name or 'n8n' in name for name in sys.modules if name.startswith('app.'))"
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_default_raw_path_needs_no_jev_key_and_has_no_training_labels(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "")
    service, journal = pipeline()
    response = service.retrieve(QUERY, ACCESS)
    assert response.processing.processors == ()
    assert response.processing.evaluations == ()
    assert response.processing.status == "completed"
    assert response.final_candidates == response.raw.candidates
    assert journal.raw.model_dump_json() == response.raw.model_dump_json()
    assert not {"decision", "evaluator", "positive", "relevance"} & RawCandidate.model_fields.keys()


def test_reranking_only_changes_final_order_and_keeps_raw_error_evidence():
    def scorer(query, texts):
        assert query == QUERY.query
        assert texts[0] == "病假不需要医疗证明。"
        return (0.1, 0.9)
    service, journal = pipeline((ScoreRerankProcessor(scorer, "reranker-test-v1"),))
    response = service.retrieve(QUERY, ACCESS, final_top_k=1)
    assert response.final_candidates[0].candidate_id == "candidate-2"
    assert response.final_candidates[0].rank == 2
    assert response.final_candidates[0].similarity_score == 0.8
    assert response.raw.candidates[0].rank == 1
    assert response.raw.candidates[0].similarity_score == 0.9
    assert response.raw.candidates[0].text == "病假不需要医疗证明。"
    assert journal.raw == response.raw
    assert response.processing.evaluations[0].score == 0.1


def test_jev_is_optional_downstream_and_excluded_chunk_stays_in_raw():
    service, journal = pipeline()
    def handler(request):
        assert journal.raw is not None, "Jev must run after raw commit"
        body = json.loads(request.content)
        answers = {}
        for index in range(2):
            levels = body["questions"][f"relevance_{index}"]["criteria"]
            probabilities = {str(i): float(i == (3 if index else 0)) for i in range(4)}
            answers[f"relevance_{index}"] = {"type": "score", "score": 3.0 if index else 0.0,
                                               "legend": {str(i): value for i, value in enumerate(levels)},
                                               "probabilities": probabilities, "confidence": 1.0}
            answers[f"support_{index}"] = {"type": "noul", "noul": 0.95 if index else 0.05}
        return httpx.Response(200, json={"model": "jev-1.13.0", "answers": answers,
                                        "usage": {"input_tokens": 100, "output_tokens": 10}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        service.processors = (JevRetrievalProcessor(JevClient(CoreSettings(typesafe_api_key="fake-key"), client)),)
        response = service.retrieve(QUERY, ACCESS)
    assert response.processing.selected_candidate_ids == ("candidate-2",)
    assert len(response.raw.candidates) == 2
    assert response.raw.candidates[0].text == "病假不需要医疗证明。"
    assert response.processing.evaluations[0].decision == "excluded"
    assert response.processing.evaluations[0].evaluator == "jev"


@pytest.mark.parametrize("failure", [ProviderError("jev", "timeout"), RuntimeError("private-secret")])
def test_optional_processor_failure_preserves_raw_and_returns_explicit_fallback(failure):
    class FailingProcessor:
        name = "other_evaluator"
        def configuration(self): return {"version": "1"}
        def process(self, raw, ids, access): raise failure
    service, journal = pipeline((FailingProcessor(),))
    response = service.retrieve(QUERY, ACCESS)
    assert response.processing.status == "raw_fallback"
    assert response.final_candidates == response.raw.candidates
    assert "private-secret" not in response.processing.model_dump_json()
    assert journal.raw == response.raw
    assert len(journal.runs) == 1


@pytest.mark.parametrize("bad_ids", [("invented",), ("candidate-1", "candidate-1")])
def test_processors_cannot_invent_or_duplicate_candidate_ids(bad_ids):
    class BadProcessor:
        name = "other_evaluator"
        def configuration(self): return {}
        def process(self, raw, ids, access): return ProcessorResult(selected_candidate_ids=bad_ids)
    service, journal = pipeline((BadProcessor(),))
    response = service.retrieve(QUERY, ACCESS)
    assert response.processing.status == "raw_fallback"
    assert response.raw == journal.raw


def test_attempted_raw_rewrite_cannot_reach_archive_or_final_results():
    class MutatingProcessor:
        name = "other_evaluator"
        def configuration(self): return {}
        def process(self, raw, ids, access):
            object.__setattr__(raw.candidates[0], "text", "rewritten evidence")
            return ProcessorResult(selected_candidate_ids=ids)
    service, journal = pipeline((MutatingProcessor(),))
    response = service.retrieve(QUERY, ACCESS)
    assert response.processing.status == "raw_fallback"
    assert response.raw.candidates[0].text == "病假不需要医疗证明。"
    assert journal.raw.candidates[0].text == response.raw.candidates[0].text


def test_security_denial_is_not_converted_to_successful_raw_fallback():
    class DeniedProcessor:
        name = "other_evaluator"
        def configuration(self): return {}
        def process(self, raw, ids, access): raise PermissionError("Denied")
    service, journal = pipeline((DeniedProcessor(),))
    with pytest.raises(PermissionError):
        service.retrieve(QUERY, ACCESS)
    assert journal.raw is not None
    assert not journal.runs


def test_raw_persistence_failure_prevents_optional_processing():
    class BrokenRetriever:
        def retrieve_and_record(self, *args): raise RuntimeError("journal unavailable")
    service = RawRetrievalPipeline(EmbeddingStub(), BrokenRetriever(), MemoryJournal())
    with pytest.raises(RuntimeError, match="journal unavailable"):
        service.retrieve(QUERY, ACCESS)


def test_rule_filter_has_separate_evaluation_and_raw_stays_complete():
    processor = RuleRetrievalProcessor(lambda query, candidate: candidate.rank == 2, "rule-test-v1")
    service, journal = pipeline((processor,))
    response = service.retrieve(QUERY, ACCESS)
    assert len(response.final_candidates) == 1
    assert len(response.raw.candidates) == 2
    assert response.processing.evaluations[0].evaluator == "rule"
    assert journal.raw == response.raw


@pytest.mark.parametrize("access", [
    AccessContext(tenant_id="other", user_id="user-1"),
    AccessContext(tenant_id="tenant-1", user_id="other-user"),
    AccessContext(tenant_id="tenant-1", user_id="user-1", allowed_scopes=()),
])
def test_reprocessing_cannot_bypass_tenant_owner_or_scopes(access):
    record = raw_record()
    with pytest.raises(PermissionError):
        RawRetrievalPipeline(journal=MemoryJournal(record)).process(record, access)


def test_raw_contract_is_frozen_and_snapshots_cannot_be_rewritten():
    record = raw_record()
    with pytest.raises(ValidationError): record.candidates[0].rank = 2
    payload = record.model_dump(mode="json")
    payload["candidates"][0]["text"] = "modified"
    with pytest.raises(ValidationError): RawRetrievalRecord.model_validate(payload)
    payload = record.model_dump(mode="json")
    payload["event"]["query_hash"] = "f" * 64
    with pytest.raises(ValidationError): RawRetrievalRecord.model_validate(payload)


@pytest.mark.parametrize("ranks", [(2, 1), (1, 3), (1, 1)])
def test_raw_rank_must_be_original_contiguous_order(ranks):
    payload = raw_record().model_dump(mode="json")
    for candidate, rank in zip(payload["candidates"], ranks): candidate["rank"] = rank
    with pytest.raises(ValidationError): RawRetrievalRecord.model_validate(payload)


def labels(approved=True):
    return (ApprovedLabel(candidate_id="candidate-2", label="positive", evaluator="known_answer",
                          provenance_id="answer-v1", approved=approved),
            ApprovedLabel(candidate_id="candidate-1", label="negative", evaluator="human",
                          provenance_id="review-1", approved=approved))


def test_training_uses_confirmed_labels_and_preserves_raw_hard_negative():
    raw = raw_record()
    before = raw.model_dump_json()
    example = derive_training_example(raw, CURATOR, "dataset-v1", labels())
    assert example.positives[0].candidate_id == "candidate-2"
    assert example.hard_negatives[0].candidate_id == "candidate-1"
    assert example.hard_negatives[0].rank == 1
    assert example.label_provenance[0].provenance_id == "answer-v1"
    assert raw.model_dump_json() == before


@pytest.mark.parametrize("training_labels", [(), labels(False), labels()[:1]])
def test_raw_or_unapproved_or_positive_only_data_is_not_training_example(training_labels):
    with pytest.raises(ValueError): derive_training_example(raw_record(), CURATOR, "v1", training_labels)


def test_model_scores_cannot_self_approve_training_labels():
    with pytest.raises(ValidationError):
        ApprovedLabel(candidate_id="candidate-1", label="positive", evaluator="jev", provenance_id="model-score", approved=True)
    with pytest.raises(PermissionError): derive_training_example(raw_record(), ACCESS, "v1", labels())
    class ImpersonatingProcessor:
        name = "human"
    with pytest.raises(ValueError): RawRetrievalPipeline(processors=(ImpersonatingProcessor(),))


def test_cloudflare_env_keys_are_native_and_redacted(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "private-cf-key")
    monkeypatch.setenv("CF_ACCOUNT_ID", "private-account")
    settings = CoreSettings()
    assert settings.require_cloudflare() == ("private-account", "private-cf-key")
    assert settings.configuration_status()["cloudflare_configured"]
    assert "private-cf-key" not in repr(settings)
    assert "private-account" not in repr(settings)


def test_workers_ai_rest_preserves_input_order_disables_truncation_and_normalizes():
    def handler(request):
        assert str(request.url) == "https://api.cloudflare.com/client/v4/accounts/fake-account/ai/run/@cf/baai/bge-m3"
        assert request.headers["authorization"] == "Bearer fake-cf-key"
        assert json.loads(request.content) == {"text": ["query", "document"], "truncate_inputs": False}
        return httpx.Response(200, json={"success": True, "errors": [], "result": {"shape": [2, 2], "data": [[3, 4], [0, 2]]}})
    settings = CoreSettings(cf_account_id="fake-account", cf_api_token="fake-cf-key", embedding_dimensions=2)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        batch = WorkersAIEmbeddingClient(settings, client).embed(("query", "document"))
    assert batch.vectors == ((0.6, 0.8), (0.0, 1.0))
    assert batch.input_hashes == (content_hash("query"), content_hash("document"))


@pytest.mark.parametrize("result", [
    {"shape": [1, 2], "data": [[0, 0]]}, {"shape": [1, 3], "data": [[1, 2, 3]]},
    {"shape": [1, 2], "data": [[1]]}, {"shape": [1, 2], "data": [[True, 1]]},
    {"shape": [1, 2], "data": [[float("nan"), 1]]}, {"shape": [1, 2], "data": []},
])
def test_invalid_embedding_results_are_rejected_without_sending_to_vector_search(result):
    settings = CoreSettings(cf_account_id="fake", cf_api_token="fake", embedding_dimensions=2)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=json.dumps({"success": True, "result": result})))) as client:
        with pytest.raises(ProviderError): WorkersAIEmbeddingClient(settings, client).embed(("query",))


def test_workers_ai_failure_does_not_expose_account_or_token():
    settings = CoreSettings(cf_account_id="private-account", cf_api_token="private-token")
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(403, text="private-account private-token"))) as client:
        with pytest.raises(ProviderError) as error: WorkersAIEmbeddingClient(settings, client).embed(("query",))
    assert "private" not in str(error.value)


@pytest.mark.parametrize("settings,name", [
    (CoreSettings(cf_account_id="", cf_api_token="key"), "CF_ACCOUNT_ID"),
    (CoreSettings(cf_account_id="id", cf_api_token=""), "CF_API_TOKEN"),
])
def test_missing_cloudflare_credentials_fail_without_network(settings, name):
    with pytest.raises(CoreConfigurationError, match=name): WorkersAIEmbeddingClient(settings).embed(("query",))


def test_embedding_signature_changes_for_model_revision_dimension():
    baseline = signature()
    assert len(baseline.fingerprint) == 64
    assert baseline.fingerprint != baseline.model_copy(update={"revision": "v2"}).fingerprint
    assert baseline.fingerprint != baseline.model_copy(update={"model": "other-model"}).fingerprint
    assert baseline.fingerprint != signature(3).fingerprint
