"""Behavior fingerprints, not a profile engine; historical missing values stay unknown."""
import json
from pathlib import Path
import tomllib
from pydantic import Field
from app.knowledge.contracts import CoreContract, content_hash


class RuntimeVersions(CoreContract):
    runtime_version: str | None = None
    runtime_fingerprint: str | None = None
    policy_bundle_version: str | None = None
    retrieval_profile_version: str | None = None
    model_revision: str | None = None
    parser_version: str | None = None
    prompt_version: str | None = None
    processing_configuration_version: str | None = None


def runtime_versions(signature, top_k, *, processing_configuration=None,retrieval_method="pgvector_exact_cosine",retrieval_adapter="sql"):
    app=Path(__file__).resolve().parents[1]
    root=app.parents[1]
    runtime=tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    files=('config/runtime_versions.py','retrieval/postgres_vector.py','retrieval/langchain_postgres.py','retrieval/raw_pipeline.py',
        'decision/grounded_answer.py','decision/model_call.py','providers/http.py',
        'workbench/contracts.py','workbench/repository.py','services/core_query_service.py','security/contracts.py')
    code={name:content_hash((app/name).read_bytes()) for name in files}
    policy=(app/'security/dataops.cedar').read_bytes()
    # Custom policy is server-owned and has its own content fingerprint.
    import os
    custom=os.getenv('ORIONSTACK_CEDAR_POLICY_FILE')
    if custom: policy=Path(custom).read_bytes()
    retrieval={'method':retrieval_method,'adapter':retrieval_adapter,'top_k':top_k,'authorization':'tenant_and_scope_sql_v1'}
    if retrieval_adapter=='langchain_postgres':
        from importlib.metadata import version
        retrieval['langchain_postgres']=version('langchain-postgres')
        if retrieval_method=='pgvector_hybrid_rrf':retrieval.update(rrf_k=60,fts_language='pg_catalog.simple',dense_top_k=top_k,lexical_top_k=top_k)
    return RuntimeVersions(runtime_version=runtime,runtime_fingerprint=content_hash(json.dumps(code,sort_keys=True)),
        policy_bundle_version=content_hash(policy),retrieval_profile_version=content_hash(json.dumps(retrieval,sort_keys=True)),
        model_revision=signature.revision,parser_version='document_parser_v1:chars500-overlap80-v1',
        prompt_version=code['decision/grounded_answer.py'],
        processing_configuration_version=None if processing_configuration is None else content_hash(processing_configuration))


def chat_runtime_versions(settings):
    """No embedding/parser/retrieval revision is claimed for ordinary conversation."""
    app=Path(__file__).resolve().parents[1]
    root=app.parents[1]
    runtime=tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    files=('config/runtime_versions.py','decision/general_chat.py','decision/model_call.py',
           'workbench/contracts.py','workbench/service.py','workbench/repository.py','security/contracts.py','providers/http.py')
    code={name:content_hash((app/name).read_bytes()) for name in files}
    configuration={'model':settings.deepseek_model,'api_base':settings.deepseek_api_base,
                   'timeout':settings.provider_timeout_seconds,'context_chars':20000,'max_tokens':2048}
    return RuntimeVersions(runtime_version=runtime,
        runtime_fingerprint=content_hash(json.dumps({'code':code,'configuration':configuration},sort_keys=True)),
        policy_bundle_version=code['security/contracts.py'],model_revision='provider-managed:'+settings.deepseek_model,
        prompt_version=code['decision/general_chat.py'])
