"""Decision evidence guard and compatible imports of the shared HTTP transport."""

from app.knowledge.contracts import AccessContext, EvidenceCandidate
from app.providers.http import ProviderError, parse_json, post_json


def authorized_evidence(candidates: tuple[EvidenceCandidate, ...], access: AccessContext) -> None:
    """Defense at the model boundary; database queries must also apply these filters."""
    if len({candidate.evidence_id for candidate in candidates}) != len(candidates):
        raise ValueError("Duplicate evidence ID")
    if any(candidate.tenant_id != access.tenant_id or candidate.access_scope not in access.allowed_scopes
           for candidate in candidates):
        raise PermissionError("Evidence is outside the authenticated principal's scope")
