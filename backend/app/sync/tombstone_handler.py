from __future__ import annotations

from app.storage.repositories.source_record_repo import SourceRecordRepo
from app.storage.repositories.action_link_repo import ActionLinkRepo
from app.storage.repositories.cleanup_task_repo import CleanupTaskRepo
from app.storage.repositories.dynamic_query_repo import DynamicQueryRepo
from app.storage.repositories.knowledge_unit_repo import KnowledgeUnitRepository


_DYNAMIC_QUERY_TOMBSTONE_STATUS = "revoked"
_KNOWLEDGE_UNIT_TOMBSTONE_STATUS = "revoked"
_CLEANUP_TASK_REASONS = {
    "deleted": "source_record_deleted",
    "revoked": "source_record_revoked",
}


def handle_tombstone(
    source_record_id: str,
    new_status: str,
    source_record_repo: SourceRecordRepo,
    action_link_repo: ActionLinkRepo | None = None,
    dynamic_query_repo: DynamicQueryRepo | None = None,
    knowledge_unit_repo: KnowledgeUnitRepository | None = None,
    cleanup_task_repo: CleanupTaskRepo | None = None,
    elastic_indexer=None,
) -> list[str]:
    source_record_repo.update_status(source_record_id, new_status)
    affected_ids = [source_record_id]

    if action_link_repo is not None:
        affected_ids.extend(
            action_link_repo.update_status_by_source_record(
                source_record_id,
                new_status,
            )
        )

    if dynamic_query_repo is not None:
        # DynamicQuery currently supports active/revoked. A deleted source
        # still revokes the runtime query so it cannot be matched or executed.
        affected_ids.extend(
            dynamic_query_repo.update_status_by_source_record(
                source_record_id,
                _DYNAMIC_QUERY_TOMBSTONE_STATUS,
            )
        )

    if knowledge_unit_repo is not None:
        affected_ids.extend(
            knowledge_unit_repo.update_status_by_source_record(
                source_record_id,
                _KNOWLEDGE_UNIT_TOMBSTONE_STATUS,
            )
        )

    if elastic_indexer is not None:
        elastic_indexer.update_status_by_source_record(
            source_record_id,
            _KNOWLEDGE_UNIT_TOMBSTONE_STATUS,
        )

    if cleanup_task_repo is not None and new_status in _CLEANUP_TASK_REASONS:
        record = source_record_repo.get(source_record_id)
        if record is not None:
            cleanup_task_repo.enqueue_for_source_record(
                record,
                reason=_CLEANUP_TASK_REASONS[new_status],
                source_status=new_status,
            )

    return affected_ids
