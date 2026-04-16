import json
from pathlib import Path
from typing import Any


class FAQRepository:
    def __init__(self) -> None:
        self._path = Path(__file__).resolve().parents[1] / "seed" / "mock_faq.json"

    def list_all(self) -> list[dict[str, Any]]:
        return json.loads(self._path.read_text(encoding="utf-8"))
