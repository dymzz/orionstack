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
    cf_api_token: str = field(default_factory=lambda: os.getenv("CF_API_TOKEN", ""), repr=False)
    cf_account_id: str = field(default_factory=lambda: os.getenv("CF_ACCOUNT_ID", ""), repr=False)
    embedding_provider: str = field(
        default_factory=lambda: os.getenv("ORIONSTACK_EMBEDDING_PROVIDER", "onnx")
    )
    onnx_dir: str = field(default_factory=lambda: os.getenv(
        "ORIONSTACK_ONNX_DIR",
        r"D:\workspace\models\Qwen--Qwen3-Embedding-0.6B\Qwen3-Embedding-0.6B-ONNX",
    ))
    onnx_model: str = field(default_factory=lambda: os.getenv(
        "ORIONSTACK_ONNX_MODEL", "Qwen/Qwen3-Embedding-0.6B"
    ))
    onnx_threads: int = field(default_factory=lambda: int(os.getenv("ORIONSTACK_ONNX_THREADS", "8")))
    onnx_max_tokens: int = field(default_factory=lambda: int(os.getenv("ORIONSTACK_ONNX_MAX_TOKENS", "8192")))
    embedding_model: str = field(
        default_factory=lambda: os.getenv("ORIONSTACK_EMBEDDING_MODEL", "@cf/baai/bge-m3")
    )
    embedding_dimensions: int = field(
        default_factory=lambda: int(os.getenv("ORIONSTACK_EMBEDDING_DIMENSIONS", "1024"))
    )
    embedding_revision: str = field(
        default_factory=lambda: os.getenv("ORIONSTACK_EMBEDDING_REVISION", "provider-managed")
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

    retrieval_mode: str = field(default_factory=lambda: os.getenv("ORIONSTACK_RETRIEVAL_MODE", "dense"))
    retrieval_adapter: str = field(default_factory=lambda: os.getenv("ORIONSTACK_RETRIEVAL_ADAPTER", "langchain_postgres"))
    chat_judge: str = field(default_factory=lambda: os.getenv("ORIONSTACK_CHAT_JUDGE", "deepseek"))

    query_use_jev: bool = field(default_factory=lambda: os.getenv("ORIONSTACK_QUERY_USE_JEV", "false").lower() == "true")
    principal_bindings_json: str = field(default_factory=lambda: os.getenv("ORIONSTACK_CORE_PRINCIPALS", "{}") or "{}", repr=False)

    def __post_init__(self) -> None:
        if self.retrieval_mode not in {"dense","hybrid"} or self.retrieval_adapter not in {"langchain_postgres","sql"} or self.chat_judge not in {"deepseek","jev"}:
            raise CoreConfigurationError("Invalid retrieval adapter/mode or chat judge")
        if (not math.isfinite(self.provider_timeout_seconds)
                or self.provider_timeout_seconds <= 0 or self.database_connect_timeout_seconds <= 0):
            raise CoreConfigurationError("Core timeouts must be positive")
        if self.embedding_dimensions <= 0 or not self.embedding_revision.strip():
            raise CoreConfigurationError("Embedding dimensions and revision must be configured")
        if self.embedding_provider not in {"onnx", "cloudflare_workers_ai"}:
            raise CoreConfigurationError("ORIONSTACK_EMBEDDING_PROVIDER must be onnx or cloudflare_workers_ai")
        if (self.onnx_threads <= 0 or not 1 <= self.onnx_max_tokens <= 32768
                or not self.onnx_dir.strip() or not self.onnx_model.strip()):
            raise CoreConfigurationError("Local ONNX directory, model, threads and token limit must be configured")

    def access_for_user(self, username: str, role: str):
        import json
        from app.knowledge.contracts import AccessContext
        try:
            bindings = json.loads(self.principal_bindings_json)
            if not isinstance(bindings, dict):
                raise ValueError
            if bindings and username not in bindings:
                raise PermissionError("Authenticated account has no core principal binding")
            binding = bindings.get(username, {"tenant_id": self.default_tenant_id, "allowed_scopes": ["internal"]})
            if (not isinstance(binding, dict) or set(binding) != {"tenant_id", "allowed_scopes"}
                    or not isinstance(binding["allowed_scopes"], list)
                    or not binding["allowed_scopes"] or not all(isinstance(s, str) and s.strip() for s in binding["allowed_scopes"])
                    or not isinstance(binding["tenant_id"], str) or not binding["tenant_id"].strip()):
                raise ValueError
            return AccessContext(tenant_id=binding["tenant_id"],user_id=username,roles=(role,),
                                 allowed_scopes=tuple(binding["allowed_scopes"]))
        except (ValueError,TypeError,KeyError):
            raise CoreConfigurationError("Invalid server-side core principal bindings") from None

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

    def require_cloudflare(self) -> tuple[str, str]:
        if not self.cf_api_token.strip():
            raise CoreConfigurationError("CF_API_TOKEN is required")
        if not self.cf_account_id.strip():
            raise CoreConfigurationError("CF_ACCOUNT_ID is required")
        return self.cf_account_id, self.cf_api_token

    def configuration_status(self) -> dict[str, bool]:
        return {
            "database_configured": bool(self.database_url.strip()),
            "typesafe_configured": bool(self.typesafe_api_key.strip()),
            "deepseek_configured": bool(self.deepseek_api_key.strip()),
            "cloudflare_configured": bool(self.cf_api_token.strip() and self.cf_account_id.strip()),
        }
