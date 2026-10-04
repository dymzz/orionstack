"""Knowledge lifecycle only: versioned files/chunks, guarded embedding, atomic activation."""

from datetime import datetime, timezone
import json
from pathlib import PureWindowsPath
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from pydantic import Field
from app.knowledge.contracts import AccessContext, CoreContract, content_hash
from app.knowledge.embedding import create_embedding_client, normalized_vector
from app.knowledge.postgres import PostgresDatabase
from app.providers.http import ProviderError
from app.retrieval.postgres_vector import EmbeddingWriteConflict, vector_literal
from app.services.chunk_service import ChunkService
from app.services.document_parser import DocumentParser


def require_curator(access: AccessContext, scope: str | None = None):
    if "admin" not in access.roles or (scope is not None and scope not in access.allowed_scopes):
        raise PermissionError("Document maintenance requires an authorized curator")


class DocumentOrigin(CoreContract):
    """Trusted import provenance; public upload forms cannot supply these fields."""
    source_id: str = Field(min_length=1, max_length=256)
    source_system: str = Field(min_length=1, max_length=128)
    external_id: str = Field(min_length=1, max_length=128)
    source_locator: str = Field(min_length=1, max_length=2048)
    title: str = Field(default="", max_length=1024)
    metadata: dict[str, str] = Field(default_factory=dict)


def document_version(data: bytes, origin: DocumentOrigin | None = None) -> str:
    material = content_hash(data) + ":parser-v1:chars500-overlap80-v1"
    if origin is not None:
        material += ":" + json.dumps(origin.model_dump(exclude={"metadata"}),sort_keys=True,separators=(",",":"),ensure_ascii=False)
    return content_hash(material)


class DocumentKnowledgeService:
    def __init__(self, database=None, embedding=None, parser=None):
        self.database = database or PostgresDatabase()
        self.embedding = embedding or create_embedding_client(self.database.settings)
        self.parser = parser or DocumentParser()

    def stage(self, filename: str, data: bytes, access: AccessContext, *,
              document_id: str | None = None, scope: str = "internal", content_type: str = "application/octet-stream",
              origin: DocumentOrigin | None = None) -> dict:
        require_curator(access, scope)
        filename = PureWindowsPath(filename).name
        if not data or len(data) > 10 * 1024 * 1024 or len(filename) > 240:
            raise ValueError("A nonempty file of at most 10 MiB is required")
        text = self.parser.parse(filename=filename, data=data)
        if not text.strip() or len(text) > 100_000:
            raise ValueError("Parsed document must contain between 1 and 100000 characters")
        chunks = ChunkService().split(text)
        digest = content_hash(data)
        version = document_version(data,origin)
        identity = document_id or "doc-" + uuid4().hex
        if not identity or len(identity) > 128:
            raise ValueError("Invalid document ID")
        source_id = origin.source_id if origin else "uploaded-document:" + identity
        locator = f"documents/{identity}/versions/{version}"
        source_locator = origin.source_locator if origin else locator
        with self.database.connection() as connection:
            with connection.transaction():
                connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (access.tenant_id + ":document:" + identity,))
                rows = connection.execute("SELECT access_scope,lifecycle_status FROM core.documents WHERE tenant_id=%s AND document_id=%s",
                                          (access.tenant_id, identity)).fetchall()
                if any(row[0] not in access.allowed_scopes for row in rows):
                    raise PermissionError("Document is outside curator scope")
                with connection.cursor(row_factory=dict_row) as cursor:
                    existing = cursor.execute("SELECT * FROM core.documents WHERE tenant_id=%s AND document_id=%s AND document_version=%s",
                                              (access.tenant_id, identity, version)).fetchone()
                if existing:
                    if existing["lifecycle_status"] not in {"pending", "active"} or existing["access_scope"] != scope:
                        raise ValueError("Existing document version cannot be republished by upload")
                    return {"document_id": identity, "document_version": version, "status": existing["lifecycle_status"]}
                metadata = {**(origin.metadata if origin else {}),"created_at": datetime.now(timezone.utc).isoformat(), "parser": "v1",
                            "chunking": "chars500-overlap80-v1", "size_bytes": len(data)}
                connection.execute("""INSERT INTO core.source_records
                    (tenant_id,source_record_id,source_version,source_system,external_id,source_locator,title,
                     raw_content,content_hash,access_scope,lifecycle_status,metadata)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s)""",
                    (access.tenant_id,source_id,version,origin.source_system if origin else 'upload',
                     origin.external_id if origin else identity,source_locator,origin.title if origin else filename,
                     text,content_hash(text),scope,Jsonb(metadata)))
                connection.execute("""INSERT INTO core.documents
                    (tenant_id,document_id,document_version,source_record_id,source_version,filename,
                     storage_locator,content_hash,access_scope,lifecycle_status,metadata)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s)""",
                    (access.tenant_id,identity,version,source_id,version,filename,locator,digest,scope,Jsonb(metadata)))
                connection.execute("INSERT INTO core.document_files VALUES (%s,%s,%s,%s,%s)",
                                   (access.tenant_id,identity,version,data,content_type))
                for index, chunk in enumerate(chunks):
                    connection.execute("""INSERT INTO core.document_chunks
                        (tenant_id,chunk_id,document_id,document_version,chunk_index,body_text,content_hash,
                         source_locator,access_scope,lifecycle_status,metadata)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s)""",
                        (access.tenant_id,f"{identity}:{version}:{index}",identity,version,index,chunk,content_hash(chunk),
                         f"{source_locator}#chunk={index+1}",scope,Jsonb({"chunking": metadata["chunking"]})))
                connection.execute("""INSERT INTO core.document_heads VALUES (%s,%s,%s)
                    ON CONFLICT (tenant_id,document_id) DO UPDATE SET target_version=EXCLUDED.target_version""",
                    (access.tenant_id,identity,version))
        return {"document_id": identity, "document_version": version, "status": "pending"}

    def _authorized_chunks(self, connection, identity, version, access):
        with connection.cursor(row_factory=dict_row) as cursor:
            return cursor.execute("""SELECT c.chunk_id,c.body_text,c.content_hash,c.embedding_signature,
                c.embedding_model,c.embedding_dimensions,c.embedding_content_hash,
                CASE WHEN c.embedding IS NOT NULL THEN 1 END AS embedding FROM core.document_chunks c
                JOIN core.documents d USING (tenant_id,document_id,document_version)
                JOIN core.source_records s ON (d.tenant_id,d.source_record_id,d.source_version)=(s.tenant_id,s.source_record_id,s.source_version)
                WHERE c.tenant_id=%s AND c.document_id=%s AND c.document_version=%s
                  AND c.access_scope=ANY(%s::text[]) AND d.access_scope=ANY(%s::text[]) AND s.access_scope=ANY(%s::text[])
                  AND c.lifecycle_status IN ('pending','active') AND d.lifecycle_status IN ('pending','active')
                  AND s.lifecycle_status IN ('pending','active') ORDER BY c.chunk_index FOR SHARE OF c,d,s""",
                (access.tenant_id,identity,version,*([list(access.allowed_scopes)]*3))).fetchall()

    def index(self, identity: str, version: str, access: AccessContext) -> dict:
        require_curator(access)
        signature = self.embedding.signature
        with self.database.connection() as connection:
            with connection.transaction():
                chunks = self._authorized_chunks(connection,identity,version,access)
        if not chunks:
            raise LookupError("Document version is unavailable")
        pending = [c for c in chunks if c["embedding_signature"] != signature.fingerprint
                   or c["embedding"] is None or c["embedding_content_hash"] != c["content_hash"]
                   or c["embedding_model"] != signature.model or c["embedding_dimensions"] != signature.dimensions]
        written = 0
        for start in range(0, len(pending), 32):
            selected = pending[start:start+32]
            batch = self.embedding.embed(tuple(c["body_text"] for c in selected))
            if (batch.signature != signature or len(batch.vectors) != len(selected)
                    or batch.input_hashes != tuple(c["content_hash"] for c in selected)):
                raise EmbeddingWriteConflict("Embedding result does not match document chunks")
            with self.database.connection() as connection:
                with connection.transaction():
                    connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(access.tenant_id+":document:"+identity,))
                    current = {c["chunk_id"]: c for c in self._authorized_chunks(connection,identity,version,access)}
                    for chunk, vector in zip(selected, batch.vectors):
                        actual = current.get(chunk["chunk_id"])
                        if not actual or actual["body_text"] != chunk["body_text"] or actual["content_hash"] != chunk["content_hash"]:
                            raise EmbeddingWriteConflict("Document changed or was revoked during embedding")
                        normalized_vector(vector,signature.dimensions)
                        connection.execute("""UPDATE core.document_chunks SET embedding=%s::vector,
                            embedding_model=%s,embedding_dimensions=%s,embedding_content_hash=%s,embedding_signature=%s
                            WHERE tenant_id=%s AND chunk_id=%s AND document_version=%s""",
                            (vector_literal(vector),signature.model,signature.dimensions,chunk["content_hash"],signature.fingerprint,
                             access.tenant_id,chunk["chunk_id"],version))
                        written += 1
        with self.database.connection() as connection:
            with connection.transaction():
                connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(access.tenant_id+":document:"+identity,))
                head = connection.execute("SELECT target_version FROM core.document_heads WHERE tenant_id=%s AND document_id=%s FOR UPDATE",
                                          (access.tenant_id,identity)).fetchone()
                if head and head[0] != version:
                    raise EmbeddingWriteConflict("A newer upload superseded this indexing request")
                current = self._authorized_chunks(connection,identity,version,access)
                if not current or any(c["embedding_signature"] != signature.fingerprint
                                      or c["embedding_content_hash"] != c["content_hash"] or c["embedding"] is None
                                      or c["embedding_model"] != signature.model or c["embedding_dimensions"] != signature.dimensions for c in current):
                    raise EmbeddingWriteConflict("Document is not fully indexed or is no longer accessible")
                source = connection.execute("SELECT source_record_id,source_version FROM core.documents WHERE tenant_id=%s AND document_id=%s AND document_version=%s",
                                            (access.tenant_id,identity,version)).fetchone()
                connection.execute("""UPDATE core.document_chunks SET lifecycle_status='superseded'
                    WHERE tenant_id=%s AND document_id=%s AND document_version<>%s AND lifecycle_status='active'""",(access.tenant_id,identity,version))
                connection.execute("""UPDATE core.documents SET lifecycle_status='superseded'
                    WHERE tenant_id=%s AND document_id=%s AND document_version<>%s AND lifecycle_status='active'""",(access.tenant_id,identity,version))
                connection.execute("UPDATE core.documents SET lifecycle_status='active' WHERE tenant_id=%s AND document_id=%s AND document_version=%s",(access.tenant_id,identity,version))
                connection.execute("UPDATE core.document_chunks SET lifecycle_status='active' WHERE tenant_id=%s AND document_id=%s AND document_version=%s",(access.tenant_id,identity,version))
                connection.execute("UPDATE core.source_records SET lifecycle_status='active' WHERE tenant_id=%s AND source_record_id=%s AND source_version=%s",(access.tenant_id,*source))
        return {"document_id": identity,"document_version": version,"status": "active","embedded_chunks": written,"chunk_count": len(current)}

    def ingest(self, filename, data, access, **kwargs):
        staged = self.stage(filename,data,access,**kwargs)
        try:
            return self.index(staged["document_id"],staged["document_version"],access)
        except ProviderError as error:
            return {**staged,"status": "pending","error_code": f"{error.provider}:{error.code}"}

    def list_documents(self, access):
        with self.database.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                return cursor.execute("""SELECT d.document_id,d.document_version,d.filename,d.lifecycle_status AS status,
                    d.access_scope,(SELECT count(*) FROM core.document_chunks c WHERE c.tenant_id=d.tenant_id
                    AND c.document_id=d.document_id AND c.document_version=d.document_version) AS chunk_count
                    FROM core.documents d JOIN core.source_records s ON
                    (d.tenant_id,d.source_record_id,d.source_version)=(s.tenant_id,s.source_record_id,s.source_version)
                    WHERE d.tenant_id=%s AND d.access_scope=ANY(%s::text[]) AND s.access_scope=ANY(%s::text[])
                    AND d.lifecycle_status IN ('active','pending') AND s.lifecycle_status IN ('active','pending')
                    ORDER BY d.document_id,d.document_version""",(access.tenant_id,list(access.allowed_scopes),list(access.allowed_scopes))).fetchall()

    def read_file(self, identity, version, access):
        with self.database.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute("""SELECT d.*,f.data FROM core.documents d
                    JOIN core.source_records s ON (d.tenant_id,d.source_record_id,d.source_version)=(s.tenant_id,s.source_record_id,s.source_version)
                    LEFT JOIN core.document_files f
                      ON (d.tenant_id,d.document_id,d.document_version)=
                         (f.tenant_id,f.document_id,f.document_version)
                    WHERE d.tenant_id=%s AND d.document_id=%s AND d.lifecycle_status='active' AND s.lifecycle_status='active'
                      AND d.access_scope=ANY(%s::text[]) AND s.access_scope=ANY(%s::text[])
                      AND (%s::text IS NULL OR d.document_version=%s) ORDER BY d.document_version LIMIT 1""",
                    (access.tenant_id,identity,list(access.allowed_scopes),list(access.allowed_scopes),version,version)).fetchone()
        if not row:
            raise LookupError("Document is unavailable")
        if row["data"] is not None:
            data = bytes(row["data"])
        else:
            from pathlib import Path
            root = (Path(__file__).resolve().parents[1] / "storage").resolve()
            path = (root / row["storage_locator"]).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise LookupError("Original document file is unavailable")
            data = path.read_bytes()
        if content_hash(data) != row["content_hash"]:
            raise LookupError("Original document file no longer matches its version")
        return row["filename"],data

    def revoke(self, identity, access):
        require_curator(access)
        with self.database.connection() as connection:
            with connection.transaction():
                connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(access.tenant_id+":document:"+identity,))
                rows = connection.execute("SELECT source_record_id,source_version,access_scope FROM core.documents WHERE tenant_id=%s AND document_id=%s FOR UPDATE",
                                          (access.tenant_id,identity)).fetchall()
                if not rows or any(r[2] not in access.allowed_scopes for r in rows):
                    raise LookupError("Document is unavailable")
                connection.execute("UPDATE core.documents SET lifecycle_status='revoked' WHERE tenant_id=%s AND document_id=%s",(access.tenant_id,identity))
                connection.execute("UPDATE core.document_chunks SET lifecycle_status='revoked' WHERE tenant_id=%s AND document_id=%s",(access.tenant_id,identity))
                # Legacy sources may be shared; revoke the document/chunks without revoking unrelated documents.
                for source_id, source_version, _ in rows:
                    if source_id == "uploaded-document:" + identity:
                        connection.execute("UPDATE core.source_records SET lifecycle_status='revoked' WHERE tenant_id=%s AND source_record_id=%s AND source_version=%s",
                                           (access.tenant_id,source_id,source_version))
        return {"document_id": identity,"status": "revoked"}
