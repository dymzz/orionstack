from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class DatabaseSettings(BaseModel):
    url: str | None = None
    driver: str = "postgresql+psycopg"
    host: str = "127.0.0.1"
    port: int = 5432
    username: str = "postgres"
    password: str = "postgres"
    database: str = "orionstack"
    echo: bool = False

    @property
    def dsn(self) -> str:
        if self.url:
            return self.url
        return (
            f"{self.driver}://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


class QASettings(BaseModel):
    min_retrieval_score: float = Field(default=0.1, ge=0.0, le=1.0)


class Settings(BaseModel):
    app_name: str = "OrionStack API"
    app_env: str = "dev"
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    vector_backend: str = "auto"
    vector_distance: str = "cosine"
    qa: QASettings = Field(default_factory=QASettings)


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "database.local.yaml"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Database config file not found: {path}. "
            "Create backend/config/database.local.yaml from database.local.yaml.example."
        )
    with path.open("r", encoding="utf-8") as fp:
        content = yaml.safe_load(fp) or {}
    if not isinstance(content, dict):
        raise ValueError(f"Invalid YAML structure in {path}")
    _normalize_database_url(content, path)
    return content


def _normalize_database_url(content: dict, config_path: Path) -> None:
    database = content.get("database")
    if not isinstance(database, dict):
        return

    url = database.get("url")
    if not isinstance(url, str):
        return

    if not url.startswith("sqlite"):
        return

    marker = ":///"
    marker_index = url.find(marker)
    if marker_index < 0:
        return

    raw_path = url[marker_index + len(marker) :]
    if not raw_path.startswith("."):
        return

    backend_root = config_path.parent.parent
    absolute_path = (backend_root / raw_path).resolve()
    normalized_path = absolute_path.as_posix()
    database["url"] = f"sqlite+pysqlite:///{normalized_path}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    config_path = Path(os.getenv("ORIONSTACK_DB_CONFIG", str(_default_config_path())))
    raw = _load_yaml(config_path)
    _apply_env_overrides(raw)
    return Settings(**raw)


def _apply_env_overrides(raw: dict) -> None:
    if "vector_backend" not in raw and os.getenv("ORIONSTACK_VECTOR_BACKEND"):
        raw["vector_backend"] = os.getenv("ORIONSTACK_VECTOR_BACKEND")
    if "vector_distance" not in raw and os.getenv("ORIONSTACK_VECTOR_DISTANCE"):
        raw["vector_distance"] = os.getenv("ORIONSTACK_VECTOR_DISTANCE")

    qa_min_score = os.getenv("ORIONSTACK_QA_MIN_SCORE") or os.getenv("ORIONSTACK_QA_MIN_RETRIEVAL_SCORE")
    if not qa_min_score:
        return

    qa = raw.get("qa")
    if not isinstance(qa, dict):
        qa = {}
    qa["min_retrieval_score"] = float(qa_min_score)
    raw["qa"] = qa
