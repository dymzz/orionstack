"""Cedar is the PDP. Entities are made solely from server-side AccessContext."""
import json
import hashlib
import os
from pathlib import Path
from functools import lru_cache
from app.dataops.ports import DependencyUnavailable


class CedarAuthorizer:
    def __init__(self, policies: str | None = None):
        try:
            from cedarpy import PolicySet
            path = os.getenv('ORIONSTACK_CEDAR_POLICY_FILE')
            policies = policies if policies is not None else (Path(path) if path else
                Path(__file__).with_name('dataops.cedar')).read_text(encoding='utf-8')
            self.policies = PolicySet.from_str(policies)
            self.version = hashlib.sha256(policies.encode()).hexdigest()
        except Exception:
            raise DependencyUnavailable('Cedar policy is unavailable') from None

    def allows(self, access, action, resource_type, resource_id, *, owner='', tenant_id=None):
        from cedarpy import is_authorized, Decision
        # Cluster backups contain all tenants. Tenant admin alone is insufficient.
        operators = set(filter(None, os.getenv('ORIONSTACK_BACKUP_OPERATORS', '').split(',')))
        from app.account.settings import IdentitySettings
        from app.config.core_settings import CoreSettings
        if IdentitySettings().mode == 'demo':
            operators.add(CoreSettings().default_tenant_id + ':admin')
        principal = {'type': 'Principal', 'id': access.user_id}
        resource = {'type': resource_type, 'id': resource_id}
        entities = [
            {'uid': {'__entity': principal}, 'attrs': {'id': access.user_id, 'tenant': access.tenant_id,
                'roles': list(access.roles), 'backup_operator': access.tenant_id + ':' + access.user_id in operators}, 'parents': []},
            {'uid': {'__entity': resource}, 'attrs': {'tenant': tenant_id or access.tenant_id,
                'owner': owner}, 'parents': []},
        ]
        try:
            result = is_authorized({'principal': principal, 'action': {'type': 'Action', 'id': action},
                'resource': resource, 'context': {}}, self.policies, entities)
            return result.decision == Decision.Allow and not result.diagnostics.errors
        except Exception:
            raise DependencyUnavailable('Cedar evaluation is unavailable') from None

    def require(self, *args, **kwargs):
        if not self.allows(*args, **kwargs): raise PermissionError('Cedar denied this operation')


@lru_cache(maxsize=1)
def dataops_authorizer(): return CedarAuthorizer()
