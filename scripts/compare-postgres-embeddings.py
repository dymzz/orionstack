"""Read-only comparison of persisted vectors against the exact selected embedding model."""

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import numpy as np
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from app.config.core_settings import CoreSettings, CoreConfigurationError
from app.knowledge.contracts import content_hash
from app.knowledge.embedding import create_embedding_client
from app.knowledge.postgres import PostgresDatabase, DatabaseUnavailable
from app.providers.http import ProviderError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant-id', required=True)
    parser.add_argument('--scope', action='append')
    parser.add_argument('--sample-size', type=int, default=32)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--embedding-provider', choices=('onnx', 'cloudflare_workers_ai'))
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if not 2 <= args.sample_size <= 1024 or not 1 <= args.batch_size <= 32:
        parser.error('sample-size=2..1024; batch-size=1..32')
    started = time.monotonic()
    try:
        settings = CoreSettings()
        if args.embedding_provider: settings = replace(settings,embedding_provider=args.embedding_provider)
        embedding = create_embedding_client(settings)
        signature = embedding.signature
        scopes = args.scope or ['internal']
        with PostgresDatabase(settings).connection() as connection:
            with connection.transaction():
                connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                inventory = connection.execute('''SELECT embedding_model,embedding_signature,count(*)
                    FROM core.document_chunks WHERE tenant_id=%s AND embedding IS NOT NULL GROUP BY 1,2 ORDER BY 1,2''',
                    (args.tenant_id,)).fetchall()
                with connection.cursor(row_factory=dict_row) as cursor:
                    rows = cursor.execute('''SELECT c.document_id,c.document_version,c.chunk_id,c.body_text,
                        c.content_hash,c.embedding_content_hash,c.embedding::text AS vector
                        FROM core.document_chunks c JOIN core.documents d USING(tenant_id,document_id,document_version)
                        JOIN core.source_records s ON (d.tenant_id,d.source_record_id,d.source_version)=
                            (s.tenant_id,s.source_record_id,s.source_version)
                        WHERE c.tenant_id=%s AND c.embedding IS NOT NULL AND c.embedding_signature=%s
                          AND c.embedding_model=%s AND c.embedding_dimensions=%s
                          AND c.access_scope=ANY(%s::text[]) AND d.access_scope=ANY(%s::text[]) AND s.access_scope=ANY(%s::text[])
                          AND c.lifecycle_status IN ('active','pending') AND d.lifecycle_status IN ('active','pending')
                          AND s.lifecycle_status IN ('active','pending')
                        ORDER BY md5(c.document_id||':'||c.document_version||':'||c.chunk_id),c.chunk_id LIMIT %s''',
                        (args.tenant_id,signature.fingerprint,signature.model,signature.dimensions,scopes,scopes,scopes,
                         args.sample_size)).fetchall()
        report = {'created_at':datetime.now(timezone.utc).isoformat(),'tenant_id':args.tenant_id,
            'database_access':'read_only','signature':signature.model_dump(),'signature_hash':signature.fingerprint,
            'inventory':inventory,'sample_size':len(rows),'requested_sample_size':args.sample_size,
            'batch_size':args.batch_size,'sampling':'deterministic md5 document/version/chunk ordering',
            'limitations':'Same-model numerical/storage check. Sample neighbor consistency is not benchmark relevance accuracy.'}
        if len(rows) < 2:
            report.update(status='insufficient_matching_vectors',elapsed_seconds=round(time.monotonic()-started,3))
        else:
            if any(content_hash(r['body_text']) != r['content_hash'] or r['embedding_content_hash'] != r['content_hash'] for r in rows):
                raise ValueError('Stored embedding content hashes do not match original text')
            persisted = np.asarray([json.loads(r['vector']) for r in rows],dtype=np.float64)
            fresh = []
            for start in range(0,len(rows),args.batch_size):
                texts = tuple(r['body_text'] for r in rows[start:start+args.batch_size])
                batch = embedding.embed(texts)
                if batch.input_hashes != tuple(content_hash(t) for t in texts) or batch.signature != signature:
                    raise ValueError('Local comparison signature or original input changed')
                fresh.extend(batch.vectors)
                print(json.dumps({'phase':'recomputing','completed':min(start+args.batch_size,len(rows)),
                    'total':len(rows)},ensure_ascii=True),flush=True)
            fresh = np.asarray(fresh,dtype=np.float64)
            if not np.isfinite(persisted).all() or persisted.shape != fresh.shape:
                raise ValueError('Persisted vector dimensions or values are invalid')
            persisted /= np.linalg.norm(persisted,axis=1,keepdims=True)
            cosine = np.einsum('ij,ij->i',persisted,fresh)
            loss = np.maximum(0,1-cosine)
            difference = np.abs(persisted-fresh)
            self_scores_old = persisted @ persisted.T
            self_scores_new = fresh @ fresh.T
            np.fill_diagonal(self_scores_old,-np.inf); np.fill_diagonal(self_scores_new,-np.inf)
            k = min(5,len(rows)-1)
            old_top = np.argsort(-self_scores_old,axis=1,kind='stable')[:,:k]
            new_top = np.argsort(-self_scores_new,axis=1,kind='stable')[:,:k]
            overlap = [len(set(a)&set(b))/k for a,b in zip(old_top,new_top)]
            # Recompute a short text alone, then padded beside the longest sample.
            short = min(rows,key=lambda r:len(r['body_text']))['body_text']
            long = max(rows,key=lambda r:len(r['body_text']))['body_text']
            solo = np.asarray(embedding.embed((short,)).vectors[0])
            padded = np.asarray(embedding.embed((short,long)).vectors[0])
            repeat = np.asarray(embedding.embed((short,)).vectors[0])
            stability = {'repeat_cosine':float(solo@repeat),'repeat_max_abs_difference':float(np.max(np.abs(solo-repeat))),
                'padded_batch_cosine':float(solo@padded),'padded_batch_max_abs_difference':float(np.max(np.abs(solo-padded)))}
            # Tolerances allow float32 inference/storage noise and reject meaningful embedding drift.
            passed = (float(loss.max()) <= 1e-6 and float(difference.max()) <= 1e-4
                      and stability['padded_batch_max_abs_difference'] <= 1e-4)
            report.update(status='passed' if passed else 'drift_detected',input_hashes_verified=True,
                cosine={'min':float(cosine.min()),'mean':float(cosine.mean()),'max_loss':float(loss.max())},
                absolute_difference={'max':float(difference.max()),'p99':float(np.quantile(difference,0.99))},
                sample_neighbors={'k':k,'mean_overlap':float(np.mean(overlap)),
                    'top1_agreement':float(np.mean(old_top[:,0]==new_top[:,0]))},stability=stability,
                sample_identity_hash=content_hash(json.dumps([(r['document_id'],r['document_version'],r['chunk_id'],r['content_hash'])
                    for r in rows],ensure_ascii=False,separators=(',',':'))),
                tolerances={'max_cosine_loss':1e-6,'max_abs_difference':1e-4},
                elapsed_seconds=round(time.monotonic()-started,3))
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
        return 0 if report['status']=='passed' else 3
    except (CoreConfigurationError,DatabaseUnavailable,ProviderError,ValueError,OSError) as error:
        print(f'[orionstack] {error}',file=sys.stderr)
        return 2


if __name__ == '__main__': raise SystemExit(main())
