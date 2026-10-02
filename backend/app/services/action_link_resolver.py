from __future__ import annotations

from app.schemas.response import ActionLinkItem
from app.storage.repositories.action_link_repo import ActionLinkRepo


class ActionLinkResolver:
    def __init__(self, repo: ActionLinkRepo | None = None) -> None:
        self._repo = repo or ActionLinkRepo()

    def find_by_resource_type(self, resource_type: str) -> list[ActionLinkItem]:
        links = self._repo.list_by_resource_type(resource_type)
        return [
            ActionLinkItem(
                action_link_id=link.action_link_id,
                label=link.label,
                url=link.url,
                system_type=link.system_type,
                resource_type=link.resource_type,
            )
            for link in links
        ]

    def find_by_source_record(self, source_record_id: str | None) -> list[ActionLinkItem]:
        if not source_record_id:
            return []
        links = self._repo.list_by_source_record(source_record_id)
        return [
            ActionLinkItem(
                action_link_id=link.action_link_id,
                label=link.label,
                url=link.url,
                system_type=link.system_type,
                resource_type=link.resource_type,
            )
            for link in links
        ]

    def find_by_domain(self, business_domain: str | None) -> list[ActionLinkItem]:
        if business_domain is None:
            return []
        links = self._repo.list_by_domain(business_domain)
        return [
            ActionLinkItem(
                action_link_id=link.action_link_id,
                label=link.label,
                url=link.url,
                system_type=link.system_type,
                resource_type=link.resource_type,
            )
            for link in links
        ]