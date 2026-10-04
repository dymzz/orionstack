from dataclasses import dataclass, field
import os
from urllib.parse import urlsplit

from app.config.core_settings import CoreConfigurationError


@dataclass(frozen=True)
class IdentitySettings:
    # Local demo stays explicit; deployed environments default to OIDC.
    mode: str = field(default_factory=lambda: os.getenv("ORIONSTACK_AUTH_MODE", "demo" if os.getenv("ORIONSTACK_APP_MODE", "demo") in {"demo", "dev"} else "oidc"))
    public_origin: str = field(default_factory=lambda: os.getenv("ORIONSTACK_PUBLIC_ORIGIN", "http://127.0.0.1:5173"))
    issuer: str = field(default_factory=lambda: os.getenv("ORIONSTACK_OIDC_ISSUER", ""))
    client_id: str = field(default_factory=lambda: os.getenv("ORIONSTACK_OIDC_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("ORIONSTACK_OIDC_CLIENT_SECRET", ""), repr=False)
    session_seconds: int = field(default_factory=lambda: int(os.getenv("ORIONSTACK_SESSION_SECONDS", "28800")))
    allow_local_http: bool = field(default_factory=lambda: os.getenv("ORIONSTACK_OIDC_ALLOW_LOCAL_HTTP", "false").lower() == "true")

    @property
    def secure_cookie(self):
        return self.public_origin.startswith("https://")

    @property
    def cookie_name(self):
        return "__Host-orionstack_session" if self.secure_cookie else "orionstack_session"

    @property
    def flow_cookie_name(self):
        return "__Host-orionstack_oidc_flow" if self.secure_cookie else "orionstack_oidc_flow"

    @property
    def callback_url(self):
        return self.public_origin + "/api/auth/callback"

    def validate(self):
        if self.mode not in {"demo", "oidc"} or not 60 <= self.session_seconds <= 86400:
            raise CoreConfigurationError("Invalid identity/session configuration")
        origin = urlsplit(self.public_origin)
        if (origin.scheme not in {"http", "https"} or not origin.hostname or origin.username
                or origin.password or origin.path or origin.query or origin.fragment):
            raise CoreConfigurationError("ORIONSTACK_PUBLIC_ORIGIN must be an exact origin")
        if os.getenv("ORIONSTACK_APP_MODE", "demo") == "prod" and (self.mode != "oidc" or not self.secure_cookie or self.allow_local_http):
            raise CoreConfigurationError("Production requires OIDC, HTTPS and secure cookies")
        if self.mode == "oidc":
            if not self.client_id.strip():
                raise CoreConfigurationError("ORIONSTACK_OIDC_CLIENT_ID is required")
            self.validate_provider_url(self.issuer)
        return self

    def validate_provider_url(self, value):
        if not isinstance(value,str) or not value:
            raise CoreConfigurationError("OIDC endpoint is missing")
        url = urlsplit(value)
        local = self.allow_local_http and url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost", "::1"}
        if (not url.hostname or url.username or url.password or url.fragment
                or (url.scheme != "https" and not local)):
            raise CoreConfigurationError("OIDC endpoints require HTTPS (loopback HTTP is development-only)")
