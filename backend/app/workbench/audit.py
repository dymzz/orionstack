"""Bounded owner-only domain audit, rechecked against current document access."""
import base64
import json
from datetime import datetime, timezone
from functools import lru_cache
from uuid import uuid4
from psycopg.rows import dict_row
from app.knowledge.postgres import PostgresDatabase, DatabaseUnavailable
from app.knowledge.evidence_validity import EvidenceValidityRepository
from app.retrieval.raw_journal import PostgresRawJournal
from app.retrieval.raw_contracts import ProcessingRun, RetrievalEvaluation
from app.security.cedar import CedarAuthorizer
from app.workbench.contracts import RunFeedback
from app.workbench.audit_contracts import (RunSummary, RunList, RunAudit, AuditAnswer,
    UserFeedbackEntry, AuthorizationEvent, RetrievalAudit)


@lru_cache(maxsize=1)
def workbench_authorizer():
    return CedarAuthorizer()


def encode_cursor(row):
    created=row['created_at']
    if isinstance(created,str): created=datetime.fromisoformat(created)
    body=json.dumps({'time':created.isoformat(),'id':row['id']},separators=(',',':')).encode()
    return base64.urlsafe_b64encode(body).decode().rstrip('=')


def decode_cursor(cursor):
    try:
        if len(cursor)>512: raise ValueError
        body=json.loads(base64.b64decode(cursor+'='*((-len(cursor))%4),altchars=b'-_',validate=True))
        if not isinstance(body,dict) or set(body)!={'time','id'}: raise ValueError
        time=datetime.fromisoformat(body['time'])
        if time.utcoffset() is None or not isinstance(body['id'],str) or not 0<len(body['id'])<=128: raise ValueError
        return time,body['id']
    except (ValueError,KeyError,TypeError,UnicodeError):
        raise ValueError('Invalid audit pagination cursor') from None


def feedback_entry(row, *, visible=True):
    fields={name:row[name] for name in UserFeedbackEntry.model_fields}
    if not visible: fields['comment']=None
    return UserFeedbackEntry(**fields)


class RunAuditRepository:
    def __init__(self, database=None, authorizer=None):
        self.database=database or PostgresDatabase()
        self.authorizer=authorizer or workbench_authorizer()
        self.journal=PostgresRawJournal(self.database)
        self.validity=EvidenceValidityRepository(self.database)

    def authorize(self, connection, access, action, resource_id, owner):
        allowed=self.authorizer.allows(access,action,'WorkbenchRun',resource_id,owner=owner)
        connection.execute('''INSERT INTO qa.authorization_events
            (tenant_id,id,principal_id,action,resource_id,decision,policy_version)
            VALUES (%s,%s,%s,%s,%s,%s,%s)''',
            (access.tenant_id,uuid4().hex,access.user_id,action,resource_id,
             'allow' if allowed else 'deny',self.authorizer.version))
        if not allowed: raise LookupError('Run is unavailable to this principal')

    def run_row(self, connection, request_id, access, action='ReadRunAudit'):
        # Do not load other actors' payloads to decide whether they may be read.
        with connection.cursor(row_factory=dict_row) as cursor:
            row=cursor.execute('''SELECT r.*,(SELECT count(*) FROM qa.user_feedback f
                WHERE (f.tenant_id,f.request_id)=(r.tenant_id,r.id)) AS feedback_count
                FROM qa.workbench_runs r WHERE r.tenant_id=%s AND r.id=%s AND r.user_id=%s''',
                (access.tenant_id,request_id,access.user_id)).fetchone()
        self.authorize(connection,access,action,request_id,row['user_id'] if row else '')
        if not row: raise LookupError('Run is unavailable')
        return row

    @staticmethod
    def summary(row):
        return RunSummary(request_id=row['id'],actor_user_id=row['user_id'],mode=row['mode'],status=row['status'],
            created_at=row['created_at'],execution_feedback=RunFeedback.model_validate(row['response']['execution_feedback']),
            feedback_count=row['feedback_count'])

    def content(self, connection, row, access, *, lock=True):
        if row['retrieval_event_id'] is None: return True,None
        try:
            raw=self.journal.load_raw(row['retrieval_event_id'],access)
        except PermissionError:
            return False,None
        except ValueError:
            raise DatabaseUnavailable('Stored raw integrity check failed') from None
        current=self.validity.valid_candidates(connection,raw.candidates,access,lock=lock)
        if len(current)!=len(raw.candidates): return False,None
        return True,raw

    @staticmethod
    def processing(connection, event_id, access):
        with connection.cursor(row_factory=dict_row) as cursor:
            evaluations=cursor.execute('''SELECT * FROM retrieval.retrieval_evaluation
                WHERE tenant_id=%s AND event_id=%s ORDER BY created_at,id LIMIT 501''',
                (access.tenant_id,event_id)).fetchall()
            # Refuse an incomplete audit, rather than imply a truncated set is complete.
            if len(evaluations)>500: raise DatabaseUnavailable('Audit evaluation limit exceeded')
            values=tuple(RetrievalEvaluation(**{name:row[name] for name in
                ('id','candidate_id','evaluator','evaluator_version','decision','score','reason','created_at')},
                details_json=json.dumps(row['details'],ensure_ascii=False)) for row in evaluations)
            rows=cursor.execute('''SELECT * FROM retrieval.processing_run
                WHERE tenant_id=%s AND event_id=%s ORDER BY created_at,id LIMIT 101''',
                (access.tenant_id,event_id)).fetchall()
            if len(rows)>100: raise DatabaseUnavailable('Audit processing limit exceeded')
            runs=[]
            for row in rows:
                selected=cursor.execute('''SELECT candidate_id FROM retrieval.processing_result
                    WHERE tenant_id=%s AND event_id=%s AND processing_run_id=%s ORDER BY rank''',
                    (access.tenant_id,event_id,row['id'])).fetchall()
                policy=row['policy']
                runs.append(ProcessingRun(id=row['id'],event_id=event_id,processors=tuple(policy['processors']),
                    configuration_json=json.dumps(policy.get('configuration',[]),ensure_ascii=False),
                    final_top_k=policy.get('final_top_k'),status=row['status'],error_code=row['error_code'],
                    selected_candidate_ids=tuple(item['candidate_id'] for item in selected),
                    evaluations=tuple(value for original,value in zip(evaluations,values)
                                      if original['processing_run_id']==row['id']),created_at=row['created_at']))
        return tuple(runs),values

    def list_runs(self, access, *, limit=20, cursor=None, mode=None, status=None):
        if not 1<=limit<=50: raise ValueError('Audit page size is outside the allowed range')
        before=decode_cursor(cursor) if cursor else None
        clauses=['r.tenant_id=%s','r.user_id=%s'];params=[access.tenant_id,access.user_id]
        if before:
            clauses.append('(r.created_at,r.id)<(%s,%s)');params.extend(before)
        if mode:
            if mode not in ('knowledge','general_chat'): raise ValueError('Unknown audit mode')
            clauses.append('r.mode=%s');params.append(mode)
        if status:
            if status not in ('answered','insufficient_evidence','failed'): raise ValueError('Unknown audit status')
            clauses.append('r.status=%s');params.append(status)
        params.append(limit+1)
        with self.database.connection() as connection:
            self.authorize(connection,access,'ListRunAudit','mine',access.user_id)
            with connection.cursor(row_factory=dict_row) as db_cursor:
                rows=db_cursor.execute('''SELECT r.id,r.user_id,r.mode,r.status,r.created_at,
                    jsonb_build_object('execution_feedback',r.response->'execution_feedback') AS response,
                    (SELECT count(*) FROM qa.user_feedback f WHERE (f.tenant_id,f.request_id)=(r.tenant_id,r.id)) AS feedback_count
                    FROM qa.workbench_runs r WHERE '''+' AND '.join(clauses)+
                    ' ORDER BY r.created_at DESC,r.id DESC LIMIT %s',tuple(params)).fetchall()
        page=rows[:limit]
        return RunList(tenant_id=access.tenant_id,items=tuple(self.summary(row) for row in page),
                       next_cursor=encode_cursor(page[-1]) if len(rows)>limit else None)

    def read(self, request_id, access):
        with self.database.connection() as connection:
            row=self.run_row(connection,request_id,access)
            with connection.transaction():
                available,raw=self.content(connection,row,access)
                processing,evaluations=self.processing(connection,raw.event.id,access) if raw else ((),())
                with connection.cursor(row_factory=dict_row) as cursor:
                    signals=cursor.execute('''SELECT * FROM qa.user_feedback WHERE tenant_id=%s AND request_id=%s
                        ORDER BY created_at DESC,id DESC LIMIT 101''',(access.tenant_id,request_id)).fetchall()
                    authorization=cursor.execute('''SELECT id,principal_id,action,resource_id,decision,policy_version,created_at
                        FROM qa.authorization_events WHERE tenant_id=%s AND principal_id=%s AND resource_id=%s
                        ORDER BY created_at DESC,id DESC LIMIT 50''',(access.tenant_id,access.user_id,request_id)).fetchall()
                response=row['response'];payload=row['request_payload']
                answer=AuditAnswer(**{key:response[key] for key in AuditAnswer.model_fields if key in response}) if available else None
                return RunAudit(tenant_id=access.tenant_id,run=self.summary(row),content_access='available' if available else 'withheld',
                    query=payload.get('query') if available else None,messages=tuple(payload.get('messages',())) if available else (),
                    raw=raw,processing=processing,evaluations=evaluations,answer=answer,
                    feedback=tuple(feedback_entry(signal,visible=available) for signal in signals[:100]),
                    feedback_truncated=len(signals)>100,authorization=tuple(AuthorizationEvent(**item) for item in authorization),
                    checked_at=datetime.now(timezone.utc))

    def read_event(self, event_id, access):
        with self.database.connection() as connection:
            row=connection.execute('''SELECT id FROM qa.workbench_runs WHERE tenant_id=%s AND user_id=%s
                AND retrieval_event_id=%s ORDER BY created_at DESC,id DESC LIMIT 1''',
                (access.tenant_id,access.user_id,event_id)).fetchone()
        if not row: raise LookupError('Retrieval event is unavailable')
        audit=self.read(row[0],access)
        return RetrievalAudit(tenant_id=access.tenant_id,event_id=event_id,request_id=audit.run.request_id,
            content_access=audit.content_access,raw=audit.raw,processing=audit.processing,
            evaluations=audit.evaluations,checked_at=audit.checked_at)
