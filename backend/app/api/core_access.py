"""Server-side binding of existing signed accounts to tenant and scopes."""

from fastapi import Depends, HTTPException

from app.api.auth import require_user
from app.config.core_settings import CoreSettings, CoreConfigurationError
from app.knowledge.contracts import AccessContext


def require_core_access(user: dict = Depends(require_user)) -> AccessContext:
    try:
        if "trusted_context" in user:
            return user["trusted_context"].access
        # CLI compatibility is restricted to demo identity mode by require_user.
        return CoreSettings().access_for_user(user["username"],user["role"])
    except PermissionError:
        raise HTTPException(status_code=403,detail="Account has no core access binding") from None
    except CoreConfigurationError:
        raise HTTPException(status_code=503,detail="Core access configuration is unavailable") from None
