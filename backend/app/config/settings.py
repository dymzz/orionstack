import os
from dataclasses import dataclass, field
from pathlib import Path

# Load a `.env` file from the repo root (if present) BEFORE any Settings
# instance reads `os.environ`. This is how the project supports switching
# planner providers by uncommenting blocks in `.env` (see `.env.example`).
#
# Precedence: real shell environment variables WIN over `.env` entries
# (override=False). This preserves any value already exported in your shell,
# so CI/production setups are unaffected. To let `.env` override a shell
# value, unset the shell variable first.
try:
    from dotenv import load_dotenv as _load_dotenv  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - dotenv is a declared dependency
    _load_dotenv = None

if _load_dotenv is not None:
    # settings.py → backend/app/config → backend/app → backend → repo root
    _repo_root = Path(__file__).resolve().parents[3]
    _load_dotenv(dotenv_path=_repo_root / ".env", override=False)


def _resolve_app_mode() -> str:
    value = os.getenv("ORIONSTACK_APP_MODE", "demo").strip().lower()
    return value if value in {"demo", "dev", "prod"} else "demo"


def _resolve_cors_origins() -> tuple[str, ...]:
    raw = os.getenv("ORIONSTACK_CORS_ORIGINS", "").strip()
    if raw:
        return tuple(origin.strip() for origin in raw.split(",") if origin.strip())
    return ("http://localhost:5173", "http://127.0.0.1:5173")


def _resolve_search_backend() -> str:
    value = os.getenv("ORIONSTACK_SEARCH_BACKEND", "local").strip().lower()
    return value if value in {"local", "elasticsearch"} else "local"


def _resolve_log_level() -> str:
    value = os.getenv("ORIONSTACK_LOG_LEVEL", "INFO").strip().upper()
    return value if value in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO"


def _resolve_str(env_name: str, default: str) -> str:
    return os.getenv(env_name, default)


def _resolve_first_present(*env_names: str, default: str) -> str:
    """Return the first environment variable explicitly present in the shell.

    This keeps compatibility aliases cheap while still letting a newer
    variable name override an older one. Explicit empty strings are respected.
    """

    for env_name in env_names:
        if env_name in os.environ:
            return os.environ[env_name]
    return default


def _resolve_int(env_name: str, default: int) -> int:
    return int(os.getenv(env_name, str(default)))


def _resolve_float(env_name: str, default: float) -> float:
    return float(os.getenv(env_name, str(default)))


def _resolve_bool(env_name: str, default: bool = False) -> bool:
    raw = os.getenv(env_name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes"}


_INSECURE_PASSWORDS = {"", "admin", "password", "changeme", "test"}
_INSECURE_ADMIN_TOKEN_SECRETS = {
    "",
    "orionstack-dev-secret",
    "change-this-in-production",
}


@dataclass(frozen=True)
class Settings:
    app_name: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_APP_NAME", "OrionStack Demo")
    )
    host: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_HOST", "0.0.0.0")
    )
    port: int = field(default_factory=lambda: _resolve_int("ORIONSTACK_PORT", 8000))
    app_mode: str = field(default_factory=_resolve_app_mode)
    cors_origins: tuple[str, ...] = field(default_factory=_resolve_cors_origins)
    log_level: str = field(default_factory=_resolve_log_level)
    access_log_enabled: bool = field(
        default_factory=lambda: _resolve_bool("ORIONSTACK_ACCESS_LOG_ENABLED", default=True)
    )
    route_confidence_threshold: float = field(
        default_factory=lambda: _resolve_float(
            "ORIONSTACK_ROUTE_CONFIDENCE_THRESHOLD", 0.15
        )
    )
    retrieval_min_score: int = field(
        default_factory=lambda: _resolve_int("ORIONSTACK_RETRIEVAL_MIN_SCORE", 1)
    )
    chat_record_max_count: int = field(
        default_factory=lambda: _resolve_int("ORIONSTACK_CHAT_RECORD_MAX_COUNT", 200)
    )
    feedback_record_max_count: int = field(
        default_factory=lambda: _resolve_int(
            "ORIONSTACK_FEEDBACK_RECORD_MAX_COUNT", 200
        )
    )

    # Auth: admin account (full access including /admin pages).
    # Production must override password and token secret via environment variables.
    admin_username: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_ADMIN_USERNAME", "admin")
    )
    admin_password: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_ADMIN_PASSWORD", "admin")
    )
    admin_token_secret: str = field(
        default_factory=lambda: _resolve_str(
            "ORIONSTACK_ADMIN_TOKEN_SECRET", "orionstack-dev-secret"
        )
    )
    admin_token_ttl_seconds: int = field(
        default_factory=lambda: _resolve_int("ORIONSTACK_ADMIN_TOKEN_TTL_SECONDS", 28800)
    )

    # Auth: regular user account (can use Q&A and documents, cannot access /admin).
    test_user_username: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_TEST_USER_USERNAME", "test")
    )
    test_user_password: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_TEST_USER_PASSWORD", "test")
    )

    # Phase 2: search backend
    search_backend: str = field(default_factory=_resolve_search_backend)
    elastic_url: str = field(
        default_factory=lambda: _resolve_str(
            "ORIONSTACK_ELASTIC_URL", "http://localhost:9200"
        )
    )
    elastic_index: str = field(
        default_factory=lambda: _resolve_str(
            "ORIONSTACK_ELASTIC_INDEX", "knowledge_units_v1"
        )
    )
    elastic_use_ik_analyzer: bool = field(
        default_factory=lambda: _resolve_bool("ORIONSTACK_ELASTIC_USE_IK_ANALYZER")
    )

    # Phase 2: query planner
    enable_query_planner: bool = field(
        default_factory=lambda: _resolve_bool(
            "ORIONSTACK_ENABLE_QUERY_PLANNER", default=False
        )
    )
    planner_provider: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_PLANNER_PROVIDER", "local")
    )
    planner_model: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_PLANNER_MODEL", "gemma3:1b")
    )
    ollama_url: str = field(
        default_factory=lambda: _resolve_str(
            "ORIONSTACK_OLLAMA_URL", "http://localhost:11434"
        )
    )

    # Planner HTTP-provider config. The generic env names are the preferred
    # contract; Qwen-prefixed names remain compatibility aliases.
    planner_api_base: str = field(
        default_factory=lambda: _resolve_first_present(
            "ORIONSTACK_PLANNER_API_BASE",
            "ORIONSTACK_QWEN_API_BASE",
            default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    )
    planner_api_model: str = field(
        default_factory=lambda: _resolve_first_present(
            "ORIONSTACK_PLANNER_API_MODEL",
            "ORIONSTACK_QWEN_API_MODEL",
            default="qwen-plus",
        )
    )
    local_llm_base_url: str = field(
        default_factory=lambda: _resolve_str(
            "ORIONSTACK_LOCAL_LLM_BASE_URL", "http://localhost:8080/v1"
        )
    )
    local_llm_model: str = field(
        default_factory=lambda: _resolve_str(
            "ORIONSTACK_LOCAL_LLM_MODEL", "gemma-3-1b-it"
        )
    )
    planner_timeout_seconds: float = field(
        default_factory=lambda: _resolve_float(
            "ORIONSTACK_PLANNER_TIMEOUT_SECONDS", 30.0
        )
    )
    planner_cache_enabled: bool = field(
        default_factory=lambda: _resolve_bool(
            "ORIONSTACK_PLANNER_CACHE_ENABLED", default=True
        )
    )

    # Phase 2: fast track
    enable_fast_track: bool = field(
        default_factory=lambda: _resolve_bool(
            "ORIONSTACK_ENABLE_FAST_TRACK", default=False
        )
    )

    # Phase 3: sync / freshness
    default_tenant_id: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_DEFAULT_TENANT_ID", "default")
    )
    freshness_default_hours: int = field(
        default_factory=lambda: _resolve_int("ORIONSTACK_FRESHNESS_DEFAULT_HOURS", 72)
    )
    stale_default_hours: int = field(
        default_factory=lambda: _resolve_int("ORIONSTACK_STALE_DEFAULT_HOURS", 168)
    )

    extraction_provider: str = field(
        default_factory=lambda: _resolve_str(
            "ORIONSTACK_EXTRACTION_PROVIDER", "openai_compatible"
        )
    )
    extraction_api_base: str = field(
        default_factory=lambda: _resolve_first_present(
            "ORIONSTACK_EXTRACTION_API_BASE",
            "ORIONSTACK_QWEN_API_BASE",
            default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    )
    extraction_api_model: str = field(
        default_factory=lambda: _resolve_first_present(
            "ORIONSTACK_EXTRACTION_API_MODEL",
            "ORIONSTACK_QWEN_API_MODEL",
            default="qwen-plus",
        )
    )

    # Phase 3: dynamic query adapter
    dynamic_query_adapter: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_DYNAMIC_QUERY_ADAPTER", "mock")
    )
    odoo_url: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_ODOO_URL", "http://localhost:8069")
    )
    odoo_db: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_ODOO_DB", "odoo")
    )
    odoo_uid: int = field(
        default_factory=lambda: _resolve_int("ORIONSTACK_ODOO_UID", 2)
    )
    odoo_password: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_ODOO_PASSWORD", "")
    )

    @property
    def debug_response_enabled(self) -> bool:
        return self.app_mode in {"demo", "dev"}

    @property
    def chat_record_view_enabled(self) -> bool:
        return self.app_mode in {"demo", "dev"}

    @property
    def user_accounts(self) -> dict[str, tuple[str, str]]:
        return {
            self.admin_username: (self.admin_password, "admin"),
            self.test_user_username: (self.test_user_password, "user"),
        }

    def production_config_errors(self) -> list[str]:
        if self.app_mode != "prod":
            return []

        errors: list[str] = []
        if self.admin_password.strip().lower() in _INSECURE_PASSWORDS:
            errors.append(
                "ORIONSTACK_ADMIN_PASSWORD must be changed for prod mode"
            )
        if self.test_user_password.strip().lower() in _INSECURE_PASSWORDS:
            errors.append(
                "ORIONSTACK_TEST_USER_PASSWORD must be changed for prod mode"
            )
        if self.admin_token_secret.strip() in _INSECURE_ADMIN_TOKEN_SECRETS:
            errors.append(
                "ORIONSTACK_ADMIN_TOKEN_SECRET must be changed for prod mode"
            )
        if len(self.admin_token_secret.strip()) < 24:
            errors.append(
                "ORIONSTACK_ADMIN_TOKEN_SECRET must be at least 24 characters in prod mode"
            )
        if self.search_backend == "elasticsearch" and not self.elastic_url.strip():
            errors.append("ORIONSTACK_ELASTIC_URL must be set when search_backend=elasticsearch")
        if self.planner_provider not in ("local",) and not self.planner_api_base.strip():
            errors.append(
                f"ORIONSTACK_PLANNER_API_BASE must be set when planner_provider={self.planner_provider}"
            )
        if self.extraction_provider not in ("local",) and not self.extraction_api_base.strip():
            errors.append(
                f"ORIONSTACK_EXTRACTION_API_BASE must be set when extraction_provider={self.extraction_provider}"
            )
        if self.dynamic_query_adapter == "odoo" and not self.odoo_password.strip():
            errors.append("ORIONSTACK_ODOO_PASSWORD must be set when dynamic_query_adapter=odoo")
        return errors

    def startup_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.planner_provider not in ("local",) and not self.planner_api_base.strip():
            warnings.append(
                f"planner_provider={self.planner_provider} but ORIONSTACK_PLANNER_API_BASE is empty; planner calls will fail"
            )
        if self.extraction_provider not in ("local",) and not self.extraction_api_base.strip():
            warnings.append(
                f"extraction_provider={self.extraction_provider} but ORIONSTACK_EXTRACTION_API_BASE is empty; extraction calls will fail"
            )
        if self.dynamic_query_adapter == "odoo" and not self.odoo_password.strip():
            warnings.append(
                "dynamic_query_adapter=odoo but ORIONSTACK_ODOO_PASSWORD is empty; dynamic queries will return empty results"
            )
        if self.search_backend == "elasticsearch":
            warnings.append(f"search_backend=elasticsearch connecting to {self.elastic_url}")
        return warnings

    def assert_production_safe(self) -> None:
        errors = self.production_config_errors()
        if errors:
            joined = "; ".join(errors)
            raise RuntimeError(f"Unsafe production configuration: {joined}")

    @property
    def qwen_api_base(self) -> str:
        """Compatibility alias for older planner-only smoke tests/scripts."""

        return self.planner_api_base

    @property
    def qwen_api_model(self) -> str:
        """Compatibility alias for older planner-only smoke tests/scripts."""

        return self.planner_api_model


settings = Settings()
