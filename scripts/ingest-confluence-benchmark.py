"""Preview, stage and resumably embed the pinned EnterpriseRAG-Bench Confluence corpus."""

import argparse
from dataclasses import replace
import json
import logging
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))

from app.config.core_settings import CoreSettings, CoreConfigurationError
from app.knowledge.benchmark_ingestion import CorpusPlan, CorpusIngestion, DATASET_ID
from app.knowledge.contracts import AccessContext
from app.knowledge.postgres import SchemaMigrator, PostgresDatabase, DatabaseUnavailable, MigrationError
from app.providers.http import ProviderError
from app.retrieval.postgres_vector import EmbeddingWriteConflict


def save_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(temporary,path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT/'data/EnterpriseRAG-Bench/confluence')
    parser.add_argument('--tenant-id',default='enterprise-rag-bench')
    parser.add_argument('--scope',default='internal')
    parser.add_argument('--dataset-version',default='v1.0.0')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--preview',action='store_true',help='Explicit local-only preview; no database or model calls')
    mode.add_argument('--apply',action='store_true',help='Write schema/manifest/documents and run the selected embedding provider')
    parser.add_argument('--stage-only',action='store_true',help='Save original bytes and pending chunks without embedding')
    parser.add_argument('--index-only',action='store_true',help='Resume vectors for an already staged snapshot')
    parser.add_argument('--workers',type=int,default=None,help='Defaults to 1 for local ONNX, 8 for Workers AI')
    parser.add_argument('--embedding-provider',choices=('onnx','cloudflare_workers_ai'))
    parser.add_argument('--batch-size',type=int,default=32)
    parser.add_argument('--max-batches',type=int,default=None,help='Optional explicit bound; partial is reported until vectors are complete')
    parser.add_argument('--provider-timeout',type=float,default=None,help='Override request timeout for this bulk job only, in seconds')
    parser.add_argument('--report-dir',type=Path,default=ROOT/'.runtime/benchmarks/enterprise-rag-bench-confluence')
    args=parser.parse_args()
    if args.stage_only and args.index_only: parser.error('Choose stage-only or index-only, not both')
    if (args.workers is not None and not 1<=args.workers<=16) or not 1<=args.batch_size<=32 or (args.max_batches is not None and args.max_batches<1):
        parser.error('workers=1..16; batch-size=1..32; max-batches must be positive')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    report={"dataset_id":DATASET_ID,"tenant_id":args.tenant_id,"status":"planning"}
    started=time.monotonic();last_report=0
    def progress(event):
        nonlocal last_report
        report.update(event);report['elapsed_seconds']=round(time.monotonic()-started,1)
        now=time.monotonic()
        if event['phase']!='embedding' or now-last_report>=5:
            print(json.dumps(event,ensure_ascii=True),flush=True)
            save_json(args.report_dir/'status.json',report)
            last_report=now
    try:
        settings=CoreSettings()
        if args.embedding_provider:
            settings=replace(settings,embedding_provider=args.embedding_provider)
        if args.workers is None:
            args.workers=1 if settings.embedding_provider=='onnx' else 8
        if args.provider_timeout is not None:
            settings=replace(settings,provider_timeout_seconds=args.provider_timeout)
        plan=CorpusPlan.build(args.root,args.tenant_id,args.scope,args.dataset_version)
        access=AccessContext(tenant_id=args.tenant_id,user_id='benchmark-ingestion',roles=('admin',),allowed_scopes=(args.scope,))
        manifest_file=args.report_dir/f'manifest-{plan.snapshot_hash}.json'
        save_json(manifest_file,{"snapshot_hash":plan.snapshot_hash,"manifest":plan.manifest})
        report.update({"mode":"applied" if args.apply else "preview","status":"ready_to_apply","snapshot_hash":plan.snapshot_hash,
            "source_root":str(plan.root),"expected_documents":len(plan.documents),"expected_chunks":plan.chunk_count,
            "bytes":sum(d.size_bytes for d in plan.documents),"text_characters":sum(d.text_length for d in plan.documents),
            "workers":args.workers,"batch_size":args.batch_size,"manifest_file":str(manifest_file)})
        ingestion=CorpusIngestion(PostgresDatabase(settings))
        report['embedding_signature']=ingestion.embedding.signature.fingerprint
        report['embedding_model']=ingestion.embedding.signature.model
        report['embedding_provider']=ingestion.embedding.signature.provider
        print(json.dumps(report,ensure_ascii=True),flush=True)
        if not args.apply:
            save_json(args.report_dir/'status.json',report)
            return 0
        from app.knowledge.alembic_migrations import migration_connection, upgrade_database
        with migration_connection(settings) as (connection, _):
            report['applied_schema']=upgrade_database(connection)
        with ingestion.repository.maintenance_lock(plan,access):
            if not args.index_only:
                ingestion.stage(plan,access,progress)
            if args.stage_only:
                report.update(ingestion.repository.status(plan,access,ingestion.embedding.signature))
                report['status']='staged'
            else:
                report.update(ingestion.index(plan,access,workers=args.workers,batch_size=args.batch_size,
                    max_batches=args.max_batches,progress=progress))
        report['elapsed_seconds']=round(time.monotonic()-started,1)
        save_json(args.report_dir/'status.json',report)
        print(json.dumps(report,ensure_ascii=True),flush=True)
        return 0
    except (CoreConfigurationError,DatabaseUnavailable,MigrationError,ProviderError,EmbeddingWriteConflict,ValueError,OSError,PermissionError,LookupError) as error:
        report.update({"status":"failed","error_code":f'{error.provider}:{error.code}' if isinstance(error,ProviderError) else type(error).__name__,
                       "elapsed_seconds":round(time.monotonic()-started,1)})
        if isinstance(error,ProviderError): report['provider_http_status']=error.status_code
        try:
            save_json(args.report_dir/'status.json',report)
        except OSError:
            print('[orionstack] Progress report could not be written',file=sys.stderr)
        print(json.dumps(report,ensure_ascii=True),flush=True)
        print(f'[orionstack] {error}',file=sys.stderr)
        return 2


if __name__=='__main__': raise SystemExit(main())
