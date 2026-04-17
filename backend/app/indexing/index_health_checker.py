from __future__ import annotations

from elasticsearch import Elasticsearch


class IndexHealthChecker:
    def __init__(
        self, es: Elasticsearch, *, index_name: str = "knowledge_units_v1"
    ) -> None:
        self._es = es
        self._index_name = index_name

    def is_connected(self) -> bool:
        try:
            return self._es.ping()
        except Exception:
            return False

    def index_exists(self) -> bool:
        try:
            return self._es.indices.exists(index=self._index_name)
        except Exception:
            return False

    def check(self) -> dict:
        result: dict = {
            "connected": False,
            "index_exists": False,
            "doc_count": 0,
            "errors": [],
        }
        try:
            if not self._es.ping():
                result["errors"].append("Elasticsearch not reachable")
                return result
            result["connected"] = True
        except Exception as exc:
            result["errors"].append(f"Connection error: {exc}")
            return result

        try:
            if not self._es.indices.exists(index=self._index_name):
                result["errors"].append(f"Index {self._index_name} does not exist")
                return result
            result["index_exists"] = True
        except Exception as exc:
            result["errors"].append(f"Index check error: {exc}")
            return result

        try:
            count = self._es.count(index=self._index_name)
            result["doc_count"] = count.get("count", 0)
        except Exception as exc:
            result["errors"].append(f"Count error: {exc}")

        return result
