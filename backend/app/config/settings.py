import os
from dataclasses import dataclass


def _resolve_app_mode() -> str:
    value = os.getenv("ORIONSTACK_APP_MODE", "demo").strip().lower()
    return value if value in {"demo", "dev", "prod"} else "demo"


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("ORIONSTACK_APP_NAME", "OrionStack Demo")
    host: str = os.getenv("ORIONSTACK_HOST", "127.0.0.1")
    port: int = int(os.getenv("ORIONSTACK_PORT", "8000"))
    app_mode: str = _resolve_app_mode()
    route_confidence_threshold: float = float(
        os.getenv("ORIONSTACK_ROUTE_CONFIDENCE_THRESHOLD", "0.6")
    )
    retrieval_min_score: int = int(os.getenv("ORIONSTACK_RETRIEVAL_MIN_SCORE", "2"))
    chat_record_max_count: int = int(
        os.getenv("ORIONSTACK_CHAT_RECORD_MAX_COUNT", "200")
    )
    feedback_record_max_count: int = int(
        os.getenv("ORIONSTACK_FEEDBACK_RECORD_MAX_COUNT", "200")
    )

    @property
    def debug_response_enabled(self) -> bool:
        return self.app_mode in {"demo", "dev"}

    @property
    def chat_record_view_enabled(self) -> bool:
        return self.app_mode in {"demo", "dev"}


settings = Settings()
