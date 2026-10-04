"""Training examples require explicit, approved labels; raw ranks never become labels."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.knowledge.contracts import AccessContext, CoreContract
from app.retrieval.raw_contracts import RawCandidate, RawRetrievalRecord, new_id, utc_now


class ApprovedLabel(CoreContract):
    candidate_id: str = Field(min_length=1)
    label: Literal["positive", "negative"]
    evaluator: Literal["human", "user_feedback", "known_answer"]
    provenance_id: str = Field(min_length=1)
    approved: bool = Field(strict=True)


class TrainingExample(CoreContract):
    id: str = Field(default_factory=new_id)
    tenant_id: str
    dataset_version: str = Field(min_length=1)
    event_id: str
    query: str
    positives: tuple[RawCandidate, ...]
    hard_negatives: tuple[RawCandidate, ...]
    label_provenance: tuple[ApprovedLabel, ...]
    created_at: datetime = Field(default_factory=utc_now)


def derive_training_example(record: RawRetrievalRecord, access: AccessContext,
                            dataset_version: str, labels: tuple[ApprovedLabel, ...]) -> TrainingExample:
    record.require_access(access)
    if "admin" not in access.roles:
        raise PermissionError("Training dataset derivation requires a curator principal")
    by_id = {candidate.candidate_id: candidate for candidate in record.candidates}
    if (not labels or any(not label.approved for label in labels)
            or len({label.candidate_id for label in labels}) != len(labels)
            or any(label.candidate_id not in by_id for label in labels)):
        raise ValueError("Training labels must be approved, unique and belong to this raw event")
    positives = tuple(by_id[label.candidate_id] for label in labels if label.label == "positive")
    negatives = tuple(by_id[label.candidate_id] for label in labels if label.label == "negative")
    if not positives or not negatives:
        raise ValueError("Training examples require both a confirmed positive and a hard negative")
    if {candidate.content_hash for candidate in positives} & {candidate.content_hash for candidate in negatives}:
        raise ValueError("Identical training text cannot receive opposite labels for the same query")
    return TrainingExample(tenant_id=access.tenant_id, dataset_version=dataset_version,
                           event_id=record.event.id, query=record.event.query,
                           positives=positives, hard_negatives=negatives, label_provenance=labels)


class PostgresTrainingRepository:
    def __init__(self, database=None):
        from app.knowledge.postgres import PostgresDatabase
        self.database = database or PostgresDatabase()

    def save(self, record: RawRetrievalRecord, example: TrainingExample, access: AccessContext) -> None:
        from psycopg.types.json import Jsonb
        from app.retrieval.raw_journal import PostgresRawJournal
        if PostgresRawJournal(self.database).load_raw(record.event.id, access) != record:
            raise ValueError("Training input differs from the persisted raw retrieval record")
        # Re-derive from trusted raw facts and approved labels before persisting.
        derived = derive_training_example(record, access, example.dataset_version, example.label_provenance)
        if (example.tenant_id != derived.tenant_id or example.event_id != derived.event_id
                or example.query != derived.query or example.positives != derived.positives
                or example.hard_negatives != derived.hard_negatives):
            raise ValueError("Training data must be derived from its raw event and label provenance")
        with self.database.connection() as connection:
            with connection.transaction():
                connection.execute("""
                    INSERT INTO retrieval.training_example
                        (tenant_id, id, dataset_version, event_id, query, positives, hard_negatives,
                         label_provenance, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (access.tenant_id, example.id, example.dataset_version, record.event.id, example.query,
                      Jsonb([candidate.model_dump(mode="json") for candidate in example.positives]),
                      Jsonb([candidate.model_dump(mode="json") for candidate in example.hard_negatives]),
                      Jsonb([label.model_dump() for label in example.label_provenance]), example.created_at))
