import json
from psycopg.types.json import Jsonb
from app.knowledge.contracts import content_hash
from app.knowledge.postgres import PostgresDatabase
from app.workbench.contracts import FeedbackResponse, RunFeedback


class WorkbenchRunRepository:
    def __init__(self, database=None):
        self.database = database or PostgresDatabase()

    @staticmethod
    def save(connection, access, payload, response):
        feedback = RunFeedback.model_validate(response['execution_feedback'])
        material = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        connection.execute('''INSERT INTO qa.workbench_runs
            (tenant_id,id,user_id,access_snapshot,mode,request_payload,request_hash,status,retrieval_event_id,response)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (access.tenant_id, feedback.request_id, access.user_id, Jsonb(access.model_dump(mode='json')), feedback.mode, Jsonb(payload), content_hash(material),
             feedback.outcome, feedback.retrieval_event_id, Jsonb(response)))

    def feedback(self, request_id, access):
        # This narrow receipt endpoint is owner-only, including administrators.
        with self.database.connection() as connection:
            row = connection.execute('''SELECT response->'execution_feedback' FROM qa.workbench_runs
                WHERE tenant_id=%s AND id=%s AND user_id=%s''', (access.tenant_id, request_id, access.user_id)).fetchone()
        if not row:
            raise LookupError('Run receipt is unavailable')
        return FeedbackResponse(tenant_id=access.tenant_id, user_id=access.user_id,
                                execution_feedback=RunFeedback.model_validate(row[0]))
