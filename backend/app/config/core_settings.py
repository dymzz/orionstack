"""Configuration for the next-generation core; credentials come from env only."""

from dataclasses import dataclass, field
import os
import math
from pathlib import Path

from dotenv import load_dotenv

# Development convenience; deployment process environment always takes precedence.
load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)


class CoreConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class CoreSettings:
    database_url: str = field(
        default_factory=lambda: os.getenv("ORIONSTACK_DATABASE_URL", ""), repr=False
    )
    typesafe_api_key: str = field(
        default_factory=lambda: os.getenv("TYPESAFE_API_KEY", ""), repr=False
    )
    deepseek_api_key: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""), repr=False
    )
    jev_api_base: str = field(
        default_factory=lambda: os.getenv("ORIONSTACK_JEV_API_BASE", "https://api.typesafe.ai/v1")
    )
    jev_model: str = field(
        default_factory=lambda: os.getenv("ORIONSTACK_JEV_MODEL", "jev-1.13.0")
    )
    deepseek_api_base: str = field(
        default_factory=lambda: os.getenv("ORIONSTACK_DEEPSEEK_API_BASE", "https://api.deepseek.com")
    )
    deepseek_model: str = field(
        default_factory=lambda: os.getenv("ORIONSTACK_DEEPSEEK_MODEL", "deepseek-flash")
    )
    provider_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("ORIONSTACK_CORE_PROVIDER_TIMEOUT_SECONDS", "30"))
    )
    database_connect_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("ORIONSTACK_DATABASE_CONNECT_TIMEOUT_SECONDS", "5"))
    )
    default_tenant_id: str = field(
        default_factory=lambda: os.getenv("ORIONSTACK_DEFAULT_TENANT_ID", "default")
    )

    def __post_init__(self) -> None:
        if (not math.isfinite(self.provider_timeout_seconds)
                or self.provider_timeout_seconds <= 0 or self.database_connect_timeout_seconds <= 0):
            raise CoreConfigurationError("Core timeouts must be positive")

    def require_database_url(self) -> str:
        if not self.database_url.strip():
            raise CoreConfigurationError("ORIONSTACK_DATABASE_URL is required")
        return self.database_url

    def require_typesafe_key(self) -> str:
        if not self.typesafe_api_key.strip():
            raise CoreConfigurationError("TYPESAFE_API_KEY is required")
        return self.typesafe_api_key

    def require_deepseek_key(self) -> str:
        if not self.deepseek_api_key.strip():
            raise CoreConfigurationError("DEEPSEEK_API_KEY is required")
        return self.deepseek_api_key

    def configuration_status(self) -> dict[str, bool]:
        return {
            "database_configured": bool(self.database_url.strip()),
            "typesafe_configured": bool(self.typesafe_api_key.strip()),
            "deepseek_configured": bool(self.deepseek_api_key.strip()),
        }
