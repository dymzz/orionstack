from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config.settings import Settings


def test_settings_phase2_search_backend_accepts_elasticsearch(monkeypatch) -> None:
    monkeypatch.setenv("ORIONSTACK_SEARCH_BACKEND", "elasticsearch")

    phase2_settings = Settings()

    assert phase2_settings.search_backend == "elasticsearch"


def test_settings_phase2_search_backend_falls_back_to_local_for_invalid_value(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ORIONSTACK_SEARCH_BACKEND", "unsupported")

    phase2_settings = Settings()

    assert phase2_settings.search_backend == "local"


def test_settings_phase2_boolean_flags_parse_truthy_values(monkeypatch) -> None:
    monkeypatch.setenv("ORIONSTACK_ELASTIC_USE_IK_ANALYZER", "true")
    monkeypatch.setenv("ORIONSTACK_ENABLE_QUERY_PLANNER", "yes")
    monkeypatch.setenv("ORIONSTACK_ENABLE_FAST_TRACK", "1")

    phase2_settings = Settings()

    assert phase2_settings.elastic_use_ik_analyzer is True
    assert phase2_settings.enable_query_planner is True
    assert phase2_settings.enable_fast_track is True


def test_settings_phase2_custom_endpoints_and_models_are_read_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ORIONSTACK_ELASTIC_URL", "http://elastic:9200")
    monkeypatch.setenv("ORIONSTACK_ELASTIC_INDEX", "knowledge_units_test")
    monkeypatch.setenv("ORIONSTACK_PLANNER_PROVIDER", "ollama")
    monkeypatch.setenv("ORIONSTACK_PLANNER_MODEL", "gemma3:4b")
    monkeypatch.setenv("ORIONSTACK_OLLAMA_URL", "http://ollama:11434")

    phase2_settings = Settings()

    assert phase2_settings.elastic_url == "http://elastic:9200"
    assert phase2_settings.elastic_index == "knowledge_units_test"
    assert phase2_settings.planner_provider == "ollama"
    assert phase2_settings.planner_model == "gemma3:4b"
    assert phase2_settings.ollama_url == "http://ollama:11434"
