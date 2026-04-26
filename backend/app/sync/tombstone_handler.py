from __future__ import annotations

from app.storage.repositories.source_record_repo import SourceRecordRepo
from app.storage.repositories.action_link_repo import ActionLinkRepo
from app.storage.repositories.dynamic_query_repo import DynamicQueryRepo


_DYNAMIC_QUERY_TOMBSTONE_STATUS = "revoked"


def handle_tombstone(
    source_record_id: str,
    new_status: str,
    source_record_repo: SourceRecordRepo,
    action_link_repo: ActionLinkRepo | None = None,
    dynamic_query_repo: DynamicQueryRepo | None = None,
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

    return affected_ids
