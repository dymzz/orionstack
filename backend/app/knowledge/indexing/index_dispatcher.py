from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from queue import Empty, Queue
import os
from threading import Lock

from app.knowledge.indexing.index_service import IndexService, IndexingStageError
from app.repositories.document_repository import DocumentRepository
from app.repositories.index_job_repository import IndexJobRepository


class IndexDispatcher:
    def __init__(self) -> None:
        max_workers = int(os.getenv("ORIONSTACK_INDEX_WORKERS", "2"))
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="orion-index")
        self.repository = DocumentRepository()
        self.index_job_repository = IndexJobRepository()
        self.service = IndexService()
        self._futures: dict[str, Future] = {}
        self._subscribers: dict[str, list[Queue]] = {}
        self._lock = Lock()

    def submit(self, document_id: str):
        with self._lock:
            existing = self._futures.get(document_id)
            if existing and not existing.done():
                return self.index_job_repository.get_latest_for_document(document_id)

            self.repository.set_status(document_id, "queued")
            job = self.index_job_repository.create(document_id=document_id, status="queued", progress_pct=0)
            future = self.executor.submit(self._run_reindex, document_id)
            self._futures[document_id] = future
            future.add_done_callback(lambda _: self._cleanup(document_id))
            future.job_id = job.job_id  # type: ignore[attr-defined]
            return job

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=False)

    def subscribe(self, job_id: str) -> Queue:
        queue: Queue = Queue()
        with self._lock:
            self._subscribers.setdefault(job_id, []).append(queue)
        current = self.index_job_repository.get(job_id)
        if current is not None:
            queue.put(self._serialize_job(current))
        return queue

    def unsubscribe(self, job_id: str, queue: Queue) -> None:
        with self._lock:
            subscribers = self._subscribers.get(job_id, [])
            if queue in subscribers:
                subscribers.remove(queue)
            if not subscribers and job_id in self._subscribers:
                self._subscribers.pop(job_id, None)

    def next_event(self, queue: Queue, timeout: float = 15.0):
        try:
            return queue.get(timeout=timeout)
        except Empty:
            return None

    def _run_reindex(self, document_id: str) -> None:
        latest_job = self.index_job_repository.get_latest_for_document(document_id)
        job_id = latest_job.job_id if latest_job is not None else None

        def report(status: str, progress_pct: int) -> None:
            self.repository.set_status(document_id, self._document_status_for(status))
            if job_id is None:
                return

            updated = self.index_job_repository.update(
                job_id,
                status=status,
                progress_pct=progress_pct,
                error_code="",
                error_message="",
                started=(status == "indexing"),
                finished=(status in {"indexed", "failed", "missing"}),
            )
            if updated is not None:
                self._publish(job_id, self._serialize_job(updated))

        try:
            report("indexing", 5)
            document = self.service.reindex(document_id, progress_callback=report)
            if document is None:
                self.repository.set_status(document_id, "missing")
                if job_id is not None:
                    updated = self.index_job_repository.update(
                        job_id,
                        status="missing",
                        progress_pct=100,
                        error_code="document_missing",
                        error_message="Document not found during indexing.",
                        finished=True,
                    )
                    if updated is not None:
                        self._publish(job_id, self._serialize_job(updated))
        except Exception as exc:
            self.repository.set_status(document_id, "failed")
            if job_id is not None:
                error_code = "indexing_failed"
                error_message = "Indexing failed. Check backend logs for details."
                failed_status = "failed"
                if isinstance(exc, IndexingStageError):
                    error_code = exc.error_code
                    error_message = exc.message
                    failed_status = exc.stage
                updated = self.index_job_repository.update(
                    job_id,
                    status=failed_status,
                    progress_pct=100,
                    error_code=error_code,
                    error_message=error_message,
                    finished=True,
                )
                if updated is not None:
                    self._publish(job_id, self._serialize_job(updated))
            raise

    def _cleanup(self, document_id: str) -> None:
        with self._lock:
            self._futures.pop(document_id, None)

    def _publish(self, job_id: str, payload: dict) -> None:
        with self._lock:
            subscribers = list(self._subscribers.get(job_id, []))
        for queue in subscribers:
            queue.put(payload)

    def _serialize_job(self, job) -> dict:
        return {
            "job_id": job.job_id,
            "document_id": job.document_id,
            "status": job.status,
            "progress_pct": job.progress_pct,
            "error_code": job.error_code,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }

    def _document_status_for(self, job_status: str) -> str:
        if job_status in {"queued", "indexed", "failed", "missing"}:
            return job_status
        return "indexing"


index_dispatcher = IndexDispatcher()
