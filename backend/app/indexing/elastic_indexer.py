from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch

from app.storage.repositories.knowledge_unit_repo import KnowledgeUnit

INDEX_NAME = "knowledge_units_v1"

MAPPING = {
    "mappings": {
        "properties": {
            "unit_id": {"type": "keyword"},
            "source_kind": {"type": "keyword"},
            "question": {
                "type": "text",
                "analyzer": "ik_max_word",
                "search_analyzer": "ik_smart",
            },
            "answer": {
                "type": "text",
                "analyzer": "ik_max_word",
                "search_analyzer": "ik_smart",
            },
            "body_text": {
                "type": "text",
                "analyzer": "ik_max_word",
                "search_analyzer": "ik_smart",
            },
            "keywords": {"type": "keyword"},
            "business_domain": {"type": "keyword"},
            "document_type": {"type": "keyword"},
            "source_type": {"type": "keyword"},
            "source_label": {"type": "keyword"},
            "source_locator": {"type": "keyword"},
            "access_scope": {"type": "keyword"},
            "lifecycle_status": {"type": "keyword"},
            "valid_from": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis",
                "ignore_malformed": True,
            },
            "valid_until": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis",
                "ignore_malformed": True,
            },
            "version": {"type": "keyword"},
            "created_at": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis",
                "ignore_malformed": True,
            },
            "tenant_id": {"type": "keyword"},
            "source_record_id": {"type": "keyword"},
            "import_batch_id": {"type": "keyword"},
            "unit_version": {"type": "integer"},
            "source_updated_at": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis",
                "ignore_malformed": True,
            },
            "fresh_until": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis",
                "ignore_malformed": True,
            },
            "stale_after": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis",
                "ignore_malformed": True,
            },
            "published_at": {
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis",
                "ignore_malformed": True,
            },
        }
    }
}

MAPPING_FALLBACK = {
    "mappings": {
        "properties": {
            "unit_id": {"type": "keyword"},
            "source_kind": {"type": "keyword"},
            "question": {"type": "text"},
            "answer": {"type": "text"},
            "body_text": {"type": "text"},
            "keywords": {"type": "keyword"},
            "business_domain": {"type": "keyword"},
            "document_type": {"type": "keyword"},
            "source_type": {"type": "keyword"},
            "source_label": {"type": "keyword"},
            "source_locator": {"type": "keyword"},
            "access_scope": {"type": "keyword"},
            "lifecycle_status": {"type": "keyword"},
            "valid_from": {"type": "keyword"},
            "valid_until": {"type": "keyword"},
            "version": {"type": "keyword"},
            "created_at": {"type": "keyword"},
            "tenant_id": {"type": "keyword"},
            "source_record_id": {"type": "keyword"},
            "import_batch_id": {"type": "keyword"},
            "unit_version": {"type": "integer"},
            "source_updated_at": {"type": "keyword"},
            "fresh_until": {"type": "keyword"},
            "stale_after": {"type": "keyword"},
            "published_at": {"type": "keyword"},
        }
    }
}


class ElasticIndexer:
    def __init__(self, es: Elasticsearch, *, index_name: str = INDEX_NAME) -> None:
        self._es = es
        self._index_name = index_name

    def ensure_index(self, *, use_ik_analyzer: bool = False) -> None:
        if self._es.indices.exists(index=self._index_name):
            return
        mapping = MAPPING if use_ik_analyzer else MAPPING_FALLBACK
        self._es.indices.create(index=self._index_name, body=mapping)

    def index_units(self, units: list[KnowledgeUnit]) -> int:
        indexed = 0
        for unit in units:
            doc = unit.to_elasticsearch_doc()
            self._es.index(index=self._index_name, id=unit.unit_id, body=doc)
            indexed += 1
        self._es.indices.refresh(index=self._index_name)
        return indexed

    def update_status_by_source_record(
        self, source_record_id: str, lifecycle_status: str
    ) -> dict[str, Any]:
        body = {
            "script": {
                "source": "ctx._source.lifecycle_status = params.lifecycle_status",
                "lang": "painless",
                "params": {"lifecycle_status": lifecycle_status},
            },
            "query": {"term": {"source_record_id": source_record_id}},
        }
        return self._es.update_by_query(
            index=self._index_name,
            body=body,
            refresh=True,
            conflicts="proceed",
        )

    def delete_by_source_record(self, source_record_id: str) -> dict[str, Any]:
        body = {"query": {"term": {"source_record_id": source_record_id}}}
        return self._es.delete_by_query(
            index=self._index_name,
            body=body,
            refresh=True,
            conflicts="proceed",
        )

    def delete_index(self) -> None:
        if self._es.indices.exists(index=self._index_name):
            self._es.indices.delete(index=self._index_name)
