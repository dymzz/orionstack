"""Build/check a synthetic example using the same runtime evidence contracts."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "backend"))

from app.decision.grounded_answer import CheckedCitation
from app.evidence.chain_profile import document_chain
from app.evidence.contracts import EvidenceBundle, EvidenceItem
from app.knowledge.contracts import SourceRef, content_hash
from app.knowledge.embedding import EmbeddingSignature
from app.retrieval.raw_contracts import RawCandidate, RawRetrievalEvent, RawRetrievalRecord
from app.services.core_query_service import CoreQueryResponse


def example():
    now = datetime(2026,10,3,12,0,tzinfo=timezone.utc)
    query,text = "病假需要什么材料？","病假需提交医院证明。"
    source = SourceRef(source_id="src_fixture_hr",source_version="1",source_locator="fixture://hr/sick-leave",
        document_id="doc_fixture_hr",document_version="1",chunk_id="chunk_fixture_1",content_hash=content_hash(text))
    candidate = RawCandidate(candidate_id="candidate_fixture_1",document_id=source.document_id,
        document_version=source.document_version,chunk_id=source.chunk_id,content_hash=source.content_hash,
        rank=1,similarity_score=0.82,text=text,source=source,access_scopes=("internal",))
    raw = RawRetrievalRecord(event=RawRetrievalEvent(id="event_fixture_1",tenant_id="tenant_fixture",user_id="usr_fixture",
        query=query,query_hash=content_hash(query),embedding_configuration=EmbeddingSignature(provider="onnxruntime",
            model="Qwen/Qwen3-Embedding-0.6B",revision="contract-fixture-v1",dimensions=2,
            preprocessing="qwen3_last_token_query_instruction_v1"),query_vector=(1.0,0.0),allowed_scopes=("internal",),
        top_k=20,candidate_count=1,created_at=now),candidates=(candidate,))
    chain = document_chain(raw,candidate,{"source_id":source.source_id,"source_version":"1",
        "source_system":"synthetic_fixture","external_id":"fixture_hr","latest_source_version":"1"},now)
    # Deterministic fixture identity; production chain IDs are generated for each verification.
    chain = chain.model_copy(update={"chain_id":"chain_fixture_1"})
    item = EvidenceItem(tenant_id=raw.event.tenant_id,evidence_id=candidate.candidate_id,source=source,raw_rank=1,vector_score=0.82,chain=chain)
    bundle = EvidenceBundle(tenant_id=raw.event.tenant_id,retrieval_event_id=raw.event.id,processing_run_id="processing_fixture_1",items=(item,))
    return CoreQueryResponse(tenant_id=raw.event.tenant_id,status="answered",answer=text,
        citations=(CheckedCitation(evidence_id=candidate.candidate_id,quote=text,source=source),),
        validation="source_and_quote_checked",model="synthetic_fixture",request_id="request_fixture_1",
        retrieval_event_id=raw.event.id,processing_run_id=bundle.processing_run_id,processing_status="completed",
        raw_candidate_count=1,final_candidate_count=1,checked_at=now,evidence_bundle=bundle).model_dump(mode="json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--check",action="store_true")
    args = parser.parse_args(); path = ROOT / "docs/examples/p1_core_query_response.json"
    expected = example()
    if args.check:
        actual = json.loads(path.read_text(encoding="utf-8"))
        CoreQueryResponse.model_validate(actual)
        if actual != expected: raise SystemExit("Evidence example is stale")
        print("Synthetic EvidenceBundle/ChainProfile example matches runtime contracts")
    else:
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(expected,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("Updated docs/examples/p1_core_query_response.json")
