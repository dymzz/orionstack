"""Owned product transcript and idempotency journal, never a session/checkpoint store."""
from uuid import uuid4
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from app.knowledge.postgres import PostgresDatabase
from app.knowledge.contracts import content_hash
from app.workbench.audit import RunAuditRepository
from app.workbench.user_feedback import FeedbackConflict


class ConversationRepository:
    def __init__(self,database=None):
        self.database=database or PostgresDatabase()
        self.audit=RunAuditRepository(self.database)

    def create(self,access):
        id=uuid4()
        with self.database.connection() as connection:
            self.audit.authorize(connection,access,'CreateConversation',str(id),access.user_id)
            connection.execute('INSERT INTO qa.conversation_threads(tenant_id,id,owner_id) VALUES (%s,%s,%s)',
                (access.tenant_id,id,access.user_id))
        return {'thread_id':str(id)}

    def require_thread(self,connection,thread_id,access):
        row=connection.execute('SELECT owner_id FROM qa.conversation_threads WHERE tenant_id=%s AND id=%s AND owner_id=%s',
            (access.tenant_id,thread_id,access.user_id)).fetchone()
        self.audit.authorize(connection,access,'UseConversation',str(thread_id),row[0] if row else '')
        if row is None:raise LookupError('Conversation unavailable')

    def list(self,access):
        with self.database.connection() as connection:
            self.audit.authorize(connection,access,'ListConversation','mine',access.user_id)
            rows=connection.execute('SELECT id,created_at FROM qa.conversation_threads WHERE tenant_id=%s AND owner_id=%s ORDER BY created_at DESC,id DESC LIMIT 50',
                (access.tenant_id,access.user_id)).fetchall()
        return {'items':[{'thread_id':str(row[0]),'created_at':row[1].isoformat()} for row in rows]}

    def input(self,connection,thread_id,payload,access):
        digest=content_hash(payload.message + "\0" + payload.origin)
        existing=connection.execute('SELECT payload_hash FROM qa.conversation_inputs WHERE tenant_id=%s AND thread_id=%s AND id=%s',
            (access.tenant_id,thread_id,payload.client_message_id)).fetchone()
        if existing and existing[0]!=digest:raise FeedbackConflict('Message ID reused with different content')
        connection.execute('INSERT INTO qa.conversation_inputs(tenant_id,thread_id,id,owner_id,message,payload_hash,policy_version) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
            (access.tenant_id,thread_id,payload.client_message_id,access.user_id,payload.message,digest,self.audit.authorizer.version))
        return connection.execute('SELECT response FROM qa.conversation_outputs WHERE tenant_id=%s AND thread_id=%s AND input_id=%s',
            (access.tenant_id,thread_id,payload.client_message_id)).fetchone()

    def output(self,connection,thread_id,input_id,response,access):
        run_id=(response.get('result') or {}).get('request_id')
        if run_id is None:run_id=(response.get('execution_feedback') or {}).get('request_id')
        connection.execute('INSERT INTO qa.conversation_outputs(tenant_id,thread_id,input_id,run_id,response) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
            (access.tenant_id,thread_id,input_id,run_id,Jsonb(response)))

    def visible(self,response,access):
        ids=set(filter(None,[(response.get("result") or {}).get("request_id"),
            (response.get("execution_feedback") or {}).get("request_id"),
            (response.get("feedback") or {}).get("request_id")]))
        return all(self.audit.read(id,access).content_access=="available" for id in ids)

    def transcript(self,thread_id,access):
        with self.database.connection() as connection:
            self.require_thread(connection,thread_id,access)
            with connection.cursor(row_factory=dict_row) as cursor:
                rows=cursor.execute('SELECT i.id,i.message,i.created_at,o.response,o.run_id FROM qa.conversation_inputs i LEFT JOIN qa.conversation_outputs o ON (o.tenant_id,o.thread_id,o.input_id)=(i.tenant_id,i.thread_id,i.id) WHERE i.tenant_id=%s AND i.thread_id=%s ORDER BY i.created_at DESC,i.id DESC LIMIT 100',
                    (access.tenant_id,thread_id)).fetchall()
        result=[]
        for row in reversed(rows):
            available=True
            if row['run_id']:
                available=self.visible(row['response'],access)
            result.append({'client_message_id':str(row['id']),'message':row['message'] if available else None,
                'response':row['response'] if available else None,'content_access':'available' if available else 'withheld',
                'created_at':row['created_at'].isoformat()})
        return {'thread_id':str(thread_id),'items':result}
