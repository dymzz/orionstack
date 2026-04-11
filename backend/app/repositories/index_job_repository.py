from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from app.core.database import session_scope
from app.models.entities import IndexJobORM


class IndexJobRepository:
    def create(self, document_id: str, status: str = "queued", progress_pct: int = 0) -> IndexJobORM:
        with session_scope() as db:
            job = IndexJobORM(
                job_id=str(uuid4()),
                document_id=document_id,
                status=status,
                progress_pct=progress_pct,
                error_code="",
                error_message="",
                created_at=datetime.now(UTC),
            )
            db.add(job)
            db.flush()
            db.refresh(job)
            return job

    def get(self, job_id: str) -> IndexJobORM | None:
        with session_scope() as db:
            return db.get(IndexJobORM, job_id)

    def get_latest_for_document(self, document_id: str) -> IndexJobORM | None:
        with session_scope() as db:
            stmt = (
                select(IndexJobORM)
                .where(IndexJobORM.document_id == document_id)
                .order_by(IndexJobORM.created_at.desc())
                .limit(1)
            )
            return db.scalar(stmt)

    def update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress_pct: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        started: bool = False,
        finished: bool = False,
    ) -> IndexJobORM | None:
        with session_scope() as db:
            job = db.get(IndexJobORM, job_id)
            if job is None:
                return None
            if status is not None:
                job.status = status
            if progress_pct is not None:
                job.progress_pct = progress_pct
            if error_code is not None:
                job.error_code = error_code
            if error_message is not None:
                job.error_message = error_message
            if started and job.started_at is None:
                job.started_at = datetime.now(UTC)
            if finished:
                job.finished_at = datetime.now(UTC)
            db.flush()
            db.refresh(job)
            return job
