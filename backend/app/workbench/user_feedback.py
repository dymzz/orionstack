"""Idempotent user signals bind only to the server's actual run and raw candidates."""
import json
from uuid import uuid4
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from app.knowledge.contracts import content_hash
from app.workbench.audit import RunAuditRepository, feedback_entry
from app.workbench.audit_contracts import UserFeedbackResponse


class FeedbackConflict(RuntimeError):
    pass


class UserFeedbackRepository:
    def __init__(self, database=None, authorizer=None):
        self.audit=RunAuditRepository(database,authorizer)
        self.database=self.audit.database

    def submit(self, request, access):
        material=request.model_dump(mode='json',exclude={'idempotency_key'})
        digest=content_hash(json.dumps(material,sort_keys=True,separators=(',',':'),ensure_ascii=False))
        with self.database.connection() as connection:
            row=self.audit.run_row(connection,request.request_id,access,'SubmitFeedback')
            event_id=row['retrieval_event_id']
            if request.event_id is not None and request.event_id!=event_id:
                raise ValueError('Feedback event does not belong to this run')
            with connection.transaction():
                available,raw=self.audit.content(connection,row,access)
                if not available: raise LookupError('Run content is no longer accessible')
                if request.candidate_id is not None and (raw is None or request.candidate_id not in
                        {candidate.candidate_id for candidate in raw.candidates}):
                    raise ValueError('Feedback candidate does not belong to this raw event')
                if request.kind=='factual_correction' and row['status']!='answered':
                    raise ValueError('A correction requires an actual returned answer')
                connection.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                    (access.tenant_id+':'+access.user_id+':feedback:'+request.idempotency_key,))
                with connection.cursor(row_factory=dict_row) as cursor:
                    existing=cursor.execute('''SELECT * FROM qa.user_feedback
                        WHERE tenant_id=%s AND actor_user_id=%s AND idempotency_key=%s''',
                        (access.tenant_id,access.user_id,request.idempotency_key)).fetchone()
                    if existing:
                        if existing['payload_hash']!=digest:
                            raise FeedbackConflict('Idempotency key already refers to different feedback')
                        return UserFeedbackResponse(feedback=feedback_entry(existing),replayed=True)
                    feedback_id=uuid4().hex
                    saved=cursor.execute('''INSERT INTO qa.user_feedback
                        (tenant_id,id,request_id,actor_user_id,idempotency_key,payload_hash,event_id,candidate_id,
                         kind,value,comment,origin,policy_version)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                        (access.tenant_id,feedback_id,request.request_id,access.user_id,request.idempotency_key,digest,
                         event_id,request.candidate_id,request.kind,request.value,request.comment,request.origin,
                         self.audit.authorizer.version)).fetchone()
                    # Answer votes and corrections never relabel all retrieved chunks.
                    if request.kind=='candidate_relevance':
                        connection.execute('''INSERT INTO retrieval.retrieval_evaluation
                            (tenant_id,event_id,id,candidate_id,evaluator,evaluator_version,decision,reason,details,created_at)
                            VALUES (%s,%s,%s,%s,'user_feedback','user_feedback_v1',%s,%s,%s,%s)''',
                            (access.tenant_id,event_id,feedback_id,request.candidate_id,request.value,request.comment,
                             Jsonb({'feedback_id':feedback_id,'request_id':request.request_id,'actor_user_id':access.user_id,
                                    'origin':request.origin,'review_state':'unreviewed','training_eligible':False}),saved['created_at']))
                    return UserFeedbackResponse(feedback=feedback_entry(saved),replayed=False)
