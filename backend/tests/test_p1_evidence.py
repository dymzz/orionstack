"""P1 provenance: immutable facts, scoped latest, typed snapshots and independent semantics."""

import json

import pytest
from pydantic import ValidationError

from app.api.auth import create_token
from app.api.core_access import require_core_access
from app.api.routes.core_knowledge import get_core_query_service
from app.decision.grounded_answer import CheckedCitation, GroundedAnswer, insufficient_answer
from app.evidence.chain_profile import document_chain
from app.evidence.contracts import ChainProfile, DocumentContent, StructuredContent, StructuredLocator
from app.knowledge.contracts import AccessContext, content_hash
from app.providers.http import ProviderError
from app.services.core_query_service import CoreQueryRequest, CoreQueryService
from test_p0_core import ADMIN, api_client
from test_p0_query_acceptance import setup
from test_raw_postgres_integration import database
from main import app


class QuoteAnswer:
    def generate(self, context, candidates, access):
        candidate = candidates[0]
        return GroundedAnswer(status="answered",answer=candidate.text,
            citations=(CheckedCitation(evidence_id=candidate.evidence_id,quote=candidate.text,source=candidate.source),))


def test_chain_is_per_evidence_real_latest_and_persisted_without_changing_raw(database):
    _, documents, first, journal, pipeline = setup(database)
    second = documents.ingest("second.txt",b"Medical certificate is required.",ADMIN)
    result = CoreQueryService(database,pipeline,QuoteAnswer()).query(CoreQueryRequest(query="medical certificate"),ADMIN)
    raw = journal.load_raw(result.retrieval_event_id,ADMIN)
    assert len(result.evidence_bundle.items) == 2
    chains = [item.chain for item in result.evidence_bundle.items]
    assert len({chain.source.source_id for chain in chains}) == 2
    assert len({chain.chain_id for chain in chains}) == 2
    assert all(chain.status == "pass" and chain.source.version.is_latest for chain in chains)
    assert all(chain.source.time.created_at is None and chain.source.actor.owner is None for chain in chains)
    assert all(chain.checks.source_actor.status == "unknown" and chain.checks.source_time.status == "unknown" for chain in chains)
    assert result.evidence_bundle.conflict_status == result.evidence_bundle.coverage_status == "not_checked"
    for item in result.evidence_bundle.items:
        candidate = next(c for c in raw.candidates if c.candidate_id == item.evidence_id)
        assert item.chain.content.text == candidate.text and item.chain.content.hash.digest == candidate.content_hash
        assert item.raw_rank == candidate.rank and item.vector_score == candidate.similarity_score
        assert item.chain.raw_record_id == candidate.candidate_id
    assert database.bridge.execute("SELECT response FROM retrieval.answer_runs").fetchone()[0] == result.model_dump(mode="json")
    assert journal.load_raw(result.retrieval_event_id,ADMIN) == raw


def test_latest_is_not_active_and_hidden_head_does_not_leak(database):
    _, documents, first, _, pipeline = setup(database)
    new = documents.stage("policy.txt",b"New policy awaits indexing.",ADMIN,document_id=first["document_id"])
    service = CoreQueryService(database,pipeline,QuoteAnswer())
    result = service.query(CoreQueryRequest(query="medical certificate"),ADMIN)
    chain = result.evidence_bundle.items[0].chain
    assert chain.status == "pass" and chain.source.version.is_latest is False
    assert chain.checks.latest_version.status == "fail"
    assert chain.source.version.latest == new["document_version"]
    with database.bridge.transaction():
        database.bridge.execute("UPDATE core.documents SET access_scope='restricted' WHERE document_version=%s",(new["document_version"],))
        database.bridge.execute("UPDATE core.source_records SET access_scope='restricted' WHERE source_version=%s",(new["document_version"],))
    ordinary = AccessContext(tenant_id=ADMIN.tenant_id,user_id="reader")
    hidden = service.query(CoreQueryRequest(query="medical certificate"),ordinary).evidence_bundle.items[0].chain
    assert hidden.source.version.latest is None and hidden.source.version.is_latest is None
    assert hidden.checks.latest_version.status == "unknown"
    assert new["document_version"] not in hidden.model_dump_json()


def test_chain_cannot_mask_missing_required_checks_or_exempt_them(database):
    _, _, _, _, pipeline = setup(database)
    result = CoreQueryService(database,pipeline,QuoteAnswer()).query(CoreQueryRequest(query="policy"),ADMIN)
    data = result.evidence_bundle.items[0].chain.model_dump(mode="json")
    data["checks"]["source_identity"] = {"status":"unknown","reason":"missing"}
    with pytest.raises(ValidationError): ChainProfile.model_validate(data)
    data["status"] = "unknown"
    assert ChainProfile.model_validate(data).status == "unknown"
    data["checks"]["source_identity"]["status"] = "not_applicable"
    with pytest.raises(ValidationError): ChainProfile.model_validate(data)


def test_candidate_cannot_attach_to_a_different_raw_event(database):
    _, _, _, _, pipeline = setup(database)
    first = pipeline.retrieve(CoreQueryRequest(query="one"),ADMIN).raw
    second = pipeline.retrieve(CoreQueryRequest(query="two"),ADMIN).raw
    with pytest.raises(ValueError,match="not a candidate"):
        document_chain(second,first.candidates[0],None,second.event.created_at)


def test_document_hash_and_structured_scalar_types_are_not_coerced():
    with pytest.raises(ValidationError):
        DocumentContent(text="changed",hash={"digest":content_hash("original"),"scope":"chunk","encoding":"utf-8"})
    fields = [{"name":"balance","value":7},{"name":"approved","value":False}]
    material = json.dumps(sorted(fields,key=lambda f:f["name"]),sort_keys=True,separators=(",",":"),ensure_ascii=False)
    data = {"kind":"structured_record","fields":fields,
            "hash":{"digest":content_hash(material),"scope":"authorized_fields","encoding":"typed_fields_json_v1"}}
    parsed = StructuredContent.model_validate(data)
    assert type(parsed.fields[0].value) is int and type(parsed.fields[1].value) is bool
    data["fields"][0]["value"] = "7"
    with pytest.raises(ValidationError): StructuredContent.model_validate(data)


@pytest.mark.parametrize("key,fields",[
    ([{"name":"employee_id","value":None}],["balance"]),
    ([{"name":"employee_id","value":"E1"},{"name":"employee_id","value":"E2"}],["balance"]),
    ([{"name":"employee_id","value":"E1"}],["balance","balance"]),
])
def test_structured_locator_rejects_incomplete_or_ambiguous_identity(key,fields):
    with pytest.raises(ValidationError):
        StructuredLocator(table="employee_leave",primary_key=key,fields=fields)


def test_optional_source_checks_cannot_claim_missing_facts_passed(database):
    _, _, _, _, pipeline = setup(database)
    result = CoreQueryService(database,pipeline,QuoteAnswer()).query(CoreQueryRequest(query="policy"),ADMIN)
    data = result.evidence_bundle.items[0].chain.model_dump(mode="json")
    for name in ("source_actor","source_time"):
        broken = json.loads(json.dumps(data))
        broken["checks"][name] = {"status":"pass","reason":"invented"}
        with pytest.raises(ValidationError): ChainProfile.model_validate(broken)


def test_provenance_pass_does_not_turn_irrelevant_evidence_into_an_answer(database):
    _, documents, _, journal, pipeline = setup(database)
    it = documents.ingest("IT.txt",b"Password reset requires the IT portal.",ADMIN)
    class Irrelevant:
        def generate(self, context, candidates, access):
            assert all(c.source.document_id == it["document_id"] for c in candidates)
            return insufficient_answer()
    result = CoreQueryService(database,pipeline,Irrelevant()).query(
        CoreQueryRequest(query="medical certificate",document_ids=(it["document_id"],)),ADMIN)
    assert result.status == "insufficient_evidence" and not result.citations
    assert result.evidence_bundle.items[0].chain.status == "pass"
    assert all(c.document_id == it["document_id"] for c in journal.load_raw(result.retrieval_event_id,ADMIN).candidates)


def test_access_context_is_server_bound_and_unimplemented_permissions_are_false(api_client):
    assert api_client.get("/api/access-context").status_code == 401
    for role,name in (("user","test"),("admin","admin")):
        response = api_client.get("/api/access-context",headers={"Authorization":"Bearer "+create_token(name,role)})
        assert response.status_code == 200
        value = response.json()
        assert value["user_id"] == name and value["roles"] == [role]
        assert value["permissions"]["documents_maintain"] == (role == "admin")
        assert value["permissions"]["query"] and value["permissions"]["documents_read"]
        assert not any(value["permissions"][key] for key in ("accounts_manage","backups_manage","audit_read"))


def test_failed_query_exposes_only_ids_matching_its_persisted_audit(database,api_client):
    _, _, _, journal, pipeline = setup(database)
    class FailingAnswer:
        def generate(self,*args): raise ProviderError("deepseek","timeout")
    app.dependency_overrides[require_core_access] = lambda: ADMIN
    app.dependency_overrides[get_core_query_service] = lambda: CoreQueryService(database,pipeline,FailingAnswer())
    response = api_client.post("/api/query",json={"query":"policy"},headers={"X-Request-ID":"client-forged"})
    assert response.status_code == 503 and response.json()['detail'] == 'Core query dependency is unavailable'
    feedback=response.json()['execution_feedback']
    assert feedback['outcome']=='failed' and feedback['model_call']['status']=='unknown'
    assert response.headers["X-Request-ID"] != "client-forged"
    request_id = response.headers["X-Core-Request-ID"]
    event_id = response.headers["X-Retrieval-Event-ID"]
    assert feedback['request_id']==request_id and feedback['retrieval_event_id']==event_id
    assert database.bridge.execute("SELECT id,event_id,status FROM retrieval.answer_runs").fetchone() == (request_id,event_id,"failed")
    assert len(journal.load_raw(event_id,ADMIN).candidates) == 1
