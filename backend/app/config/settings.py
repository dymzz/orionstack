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


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("ORIONSTACK_APP_NAME", "OrionStack Demo")
    host: str = os.getenv("ORIONSTACK_HOST", "127.0.0.1")
    port: int = int(os.getenv("ORIONSTACK_PORT", "8000"))
    app_mode: str = field(default_factory=_resolve_app_mode)
    cors_origins: tuple[str, ...] = field(default_factory=_resolve_cors_origins)
    route_confidence_threshold: float = float(
        os.getenv("ORIONSTACK_ROUTE_CONFIDENCE_THRESHOLD", "0.15")
    )
    retrieval_min_score: int = int(os.getenv("ORIONSTACK_RETRIEVAL_MIN_SCORE", "1"))
    chat_record_max_count: int = int(
        os.getenv("ORIONSTACK_CHAT_RECORD_MAX_COUNT", "200")
    )
    feedback_record_max_count: int = int(
        os.getenv("ORIONSTACK_FEEDBACK_RECORD_MAX_COUNT", "200")
    )

    # Phase 2: search backend
    search_backend: str = field(default_factory=_resolve_search_backend)
    elastic_url: str = os.getenv("ORIONSTACK_ELASTIC_URL", "http://localhost:9200")
    elastic_index: str = os.getenv("ORIONSTACK_ELASTIC_INDEX", "knowledge_units_v1")
    elastic_use_ik_analyzer: bool = os.getenv(
        "ORIONSTACK_ELASTIC_USE_IK_ANALYZER", ""
    ).strip().lower() in {"1", "true", "yes"}

    # Phase 2: query planner
    enable_query_planner: bool = os.getenv(
        "ORIONSTACK_ENABLE_QUERY_PLANNER", ""
    ).strip().lower() in {"1", "true", "yes"}
    planner_provider: str = os.getenv("ORIONSTACK_PLANNER_PROVIDER", "local")
    planner_model: str = os.getenv("ORIONSTACK_PLANNER_MODEL", "gemma3:1b")
    ollama_url: str = os.getenv("ORIONSTACK_OLLAMA_URL", "http://localhost:11434")

    # Phase 2: fast track
    enable_fast_track: bool = os.getenv(
        "ORIONSTACK_ENABLE_FAST_TRACK", ""
    ).strip().lower() in {"1", "true", "yes"}

    @property
    def debug_response_enabled(self) -> bool:
        return self.app_mode in {"demo", "dev"}

    @property
    def chat_record_view_enabled(self) -> bool:
        return self.app_mode in {"demo", "dev"}


settings = Settings()
