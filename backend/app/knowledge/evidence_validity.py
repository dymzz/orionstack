"""Current source/version/scope checks, performed before and after model generation."""

import json

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.knowledge.contracts import AccessContext, content_hash
from app.knowledge.postgres import PostgresDatabase
from app.retrieval.raw_contracts import RawCandidate


class EvidenceValidityRepository:
    def __init__(self, database=None):
        self.database = database or PostgresDatabase()

    def valid_candidates(self, connection, candidates: tuple[RawCandidate, ...], access: AccessContext,
                         *, lock: bool = False) -> tuple[RawCandidate, ...]:
        valid = []
        with connection.cursor(row_factory=dict_row) as cursor:
            for candidate in candidates:
                row = cursor.execute("""SELECT c.body_text,c.content_hash,c.source_locator,d.source_record_id,d.source_version
                    FROM core.document_chunks c JOIN core.documents d USING (tenant_id,document_id,document_version)
                    JOIN core.source_records s ON (d.tenant_id,d.source_record_id,d.source_version)=(s.tenant_id,s.source_record_id,s.source_version)
                    WHERE c.tenant_id=%s AND c.document_id=%s AND c.document_version=%s AND c.chunk_id=%s
                      AND c.lifecycle_status='active' AND d.lifecycle_status='active' AND s.lifecycle_status='active'
                      AND c.access_scope=ANY(%s::text[]) AND d.access_scope=ANY(%s::text[]) AND s.access_scope=ANY(%s::text[])
                """ + (" FOR SHARE OF c,d,s" if lock else ""),
                    (access.tenant_id,candidate.document_id,candidate.document_version,candidate.chunk_id,
                     *([list(access.allowed_scopes)]*3))).fetchone()
                if (row and row["body_text"] == candidate.text and row["content_hash"] == candidate.content_hash
                        and content_hash(row["body_text"]) == candidate.content_hash
                        and row["source_record_id"] == candidate.source.source_id
                        and row["source_version"] == candidate.source.source_version
                        and row["source_locator"] == candidate.source.source_locator):
                    valid.append(candidate)
        return tuple(valid)

    def before_generation(self, candidates, access):
        with self.database.connection() as connection:
            return self.valid_candidates(connection,candidates,access)

    def source_observations(self, connection, candidates, access):
        """Read only authorized origin facts; active alone does not establish latest."""
        observations = {}
        with connection.cursor(row_factory=dict_row) as cursor:
            for candidate in candidates:
                row = cursor.execute("""SELECT s.source_record_id AS source_id,s.source_version,
                    s.source_system,s.external_id,
                    (SELECT newest.source_version FROM core.document_heads h
                     JOIN core.documents newest ON (h.tenant_id,h.document_id,h.target_version)=
                         (newest.tenant_id,newest.document_id,newest.document_version)
                     JOIN core.source_records newest_source ON
                         (newest.tenant_id,newest.source_record_id,newest.source_version)=
                         (newest_source.tenant_id,newest_source.source_record_id,newest_source.source_version)
                     WHERE h.tenant_id=d.tenant_id AND h.document_id=d.document_id
                       AND newest.source_record_id=s.source_record_id
                       AND newest.access_scope=ANY(%s::text[]) AND newest_source.access_scope=ANY(%s::text[])
                       AND newest.lifecycle_status IN ('active','pending')
                       AND newest_source.lifecycle_status IN ('active','pending')) AS latest_source_version
                    FROM core.documents d JOIN core.source_records s ON
                        (d.tenant_id,d.source_record_id,d.source_version)=(s.tenant_id,s.source_record_id,s.source_version)
                    WHERE d.tenant_id=%s AND d.document_id=%s AND d.document_version=%s
                      AND d.access_scope=ANY(%s::text[]) AND s.access_scope=ANY(%s::text[])
                      AND d.lifecycle_status='active' AND s.lifecycle_status='active'""",
                    (list(access.allowed_scopes),list(access.allowed_scopes),access.tenant_id,
                     candidate.document_id,candidate.document_version,
                     list(access.allowed_scopes),list(access.allowed_scopes))).fetchone()
                if row:
                    observations[candidate.candidate_id] = row
        return observations

    @staticmethod
    def save_answer(connection, event_id, request_id, access, response):
        connection.execute("""INSERT INTO retrieval.answer_runs
            (tenant_id,event_id,id,user_id,status,response) VALUES (%s,%s,%s,%s,%s,%s)""",
            (access.tenant_id,event_id,request_id,access.user_id,response["status"],Jsonb(response)))
