import os
from dataclasses import dataclass, field


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


def _resolve_str(env_name: str, default: str) -> str:
    return os.getenv(env_name, default)


def _resolve_int(env_name: str, default: int) -> int:
    return int(os.getenv(env_name, str(default)))


def _resolve_float(env_name: str, default: float) -> float:
    return float(os.getenv(env_name, str(default)))


def _resolve_bool(env_name: str) -> bool:
    return os.getenv(env_name, "").strip().lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class Settings:
    app_name: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_APP_NAME", "OrionStack Demo")
    )
    host: str = field(
        default_factory=lambda: _resolve_str("ORIONSTACK_HOST", "127.0.0.1")
    )
    port: int = field(default_factory=lambda: _resolve_int("ORIONSTACK_PORT", 8000))
    app_mode: str = field(default_factory=_resolve_app_mode)
    cors_origins: tuple[str, ...] = field(default_factory=_resolve_cors_origins)
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
        default_factory=lambda: _resolve_bool("ORIONSTACK_ENABLE_QUERY_PLANNER")
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

    # Phase 2: fast track
    enable_fast_track: bool = field(
        default_factory=lambda: _resolve_bool("ORIONSTACK_ENABLE_FAST_TRACK")
    )

    @property
    def debug_response_enabled(self) -> bool:
        return self.app_mode in {"demo", "dev"}

    @property
    def chat_record_view_enabled(self) -> bool:
        return self.app_mode in {"demo", "dev"}


settings = Settings()
