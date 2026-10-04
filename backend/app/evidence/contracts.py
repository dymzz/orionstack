"""Core evidence contracts; provenance grants neither access nor execution rights."""

from datetime import datetime
import json
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

from app.knowledge.contracts import CoreContract, SourceRef, content_hash
from app.retrieval.raw_contracts import RetrievalEvaluation

CheckStatus = Literal["pass", "fail", "unknown", "not_applicable"]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Scalar = StrictStr | StrictBool | StrictInt | Annotated[StrictFloat, Field(allow_inf_nan=False)] | None
REQUIRED_CHECKS = ("source_identity", "source_version", "source_locator", "content_integrity", "raw_link")


class ChainCheck(CoreContract):
    status: CheckStatus
    reason: str = Field(min_length=1)


class ChainChecks(CoreContract):
    source_identity: ChainCheck
    source_actor: ChainCheck
    source_time: ChainCheck
    source_version: ChainCheck
    latest_version: ChainCheck
    source_locator: ChainCheck
    content_integrity: ChainCheck
    raw_link: ChainCheck

    def aggregate(self) -> CheckStatus:
        states = tuple(getattr(self, name).status for name in REQUIRED_CHECKS)
        if "not_applicable" in states:
            raise ValueError("Required provenance checks cannot be exempted")
        if "fail" in states:
            return "fail"
        return "unknown" if "unknown" in states else "pass"


class SourceActor(CoreContract):
    owner: str | None = None
    published_by: str | None = None


class SourceTime(CoreContract):
    created_at: datetime | None = None
    updated_at: datetime | None = None
    observed_at: datetime

    @model_validator(mode="after")
    def aware_times(self):
        if any(value is not None and value.utcoffset() is None
               for value in (self.created_at,self.updated_at,self.observed_at)):
            raise ValueError("Source times must include timezone")
        return self


class SourceVersion(CoreContract):
    value: str = Field(min_length=1)
    latest: str | None = Field(default=None,min_length=1)
    is_latest: bool | None = None
    checked_at: datetime | None = None
    scope: Literal["local_catalog"] = "local_catalog"

    @model_validator(mode="after")
    def latest_consistent(self):
        if self.latest is None:
            if self.is_latest is not None or self.checked_at is not None:
                raise ValueError("Unknown latest version cannot claim a check")
        elif (self.checked_at is None or self.checked_at.utcoffset() is None
              or self.is_latest != (self.value == self.latest)):
            raise ValueError("Latest version facts disagree")
        return self


class ChainSource(CoreContract):
    source_id: str = Field(min_length=1)
    source_system: str | None = None
    source_type: Literal["document", "structured_record"]
    external_id: str | None = None
    actor: SourceActor = Field(default_factory=SourceActor)
    time: SourceTime
    version: SourceVersion


class DocumentLocator(CoreContract):
    kind: Literal["document"] = "document"
    document_id: str = Field(min_length=1)
    document_version: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)


class FieldSnapshot(CoreContract):
    name: str = Field(min_length=1)
    value: Scalar


class StructuredLocator(CoreContract):
    kind: Literal["structured_record"] = "structured_record"
    table: str = Field(min_length=1)
    primary_key: tuple[FieldSnapshot, ...] = Field(min_length=1)
    fields: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def stable_key_and_fields(self):
        if (len({field.name for field in self.primary_key}) != len(self.primary_key)
                or any(field.value is None or field.value == "" for field in self.primary_key)
                or len(set(self.fields)) != len(self.fields) or any(not name for name in self.fields)):
            raise ValueError("Structured locator requires a complete unique key and fields")
        return self


class ContentHash(CoreContract):
    algorithm: Literal["sha256"] = "sha256"
    digest: Digest
    scope: Literal["chunk", "authorized_fields"]
    encoding: Literal["utf-8", "typed_fields_json_v1"]


class DocumentContent(CoreContract):
    kind: Literal["document"] = "document"
    text: str = Field(min_length=1)
    hash: ContentHash

    @model_validator(mode="after")
    def content_matches(self):
        if (self.hash.scope != "chunk" or self.hash.encoding != "utf-8"
                or self.hash.digest != content_hash(self.text)):
            raise ValueError("Document snapshot hash or scope is invalid")
        return self


class StructuredContent(CoreContract):
    kind: Literal["structured_record"] = "structured_record"
    fields: tuple[FieldSnapshot, ...] = Field(min_length=1)
    hash: ContentHash

    @model_validator(mode="after")
    def structured_scope(self):
        if self.hash.scope != "authorized_fields" or self.hash.encoding != "typed_fields_json_v1":
            raise ValueError("Structured snapshot requires its own hash scope")
        if len({field.name for field in self.fields}) != len(self.fields):
            raise ValueError("Snapshot field names must be unique")
        material = json.dumps([field.model_dump(mode="json") for field in
                               sorted(self.fields,key=lambda field:field.name)],
                              sort_keys=True,separators=(",",":"),ensure_ascii=False)
        if self.hash.digest != content_hash(material):
            raise ValueError("Structured snapshot hash is invalid")
        return self


class ChainVerification(CoreContract):
    profile: Literal["source_trace_v1"] = "source_trace_v1"
    required_checks: tuple[str, ...] = REQUIRED_CHECKS
    checked_at: datetime

    @model_validator(mode="after")
    def fixed_profile(self):
        if self.required_checks != REQUIRED_CHECKS or self.checked_at.utcoffset() is None:
            raise ValueError("Verification profile and time must be explicit")
        return self


class ChainProfile(CoreContract):
    tenant_id: str = Field(min_length=1)
    schema_version: Literal["1"] = "1"
    chain_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    raw_record_id: str = Field(min_length=1)
    raw_event_id: str = Field(min_length=1)
    source: ChainSource
    locator: Annotated[DocumentLocator | StructuredLocator, Field(discriminator="kind")]
    content: Annotated[DocumentContent | StructuredContent, Field(discriminator="kind")]
    verification: ChainVerification
    checks: ChainChecks
    status: CheckStatus

    @model_validator(mode="after")
    def consistent_chain(self):
        if self.source.source_type != self.locator.kind or self.locator.kind != self.content.kind:
            raise ValueError("Provenance types disagree")
        if self.status != self.checks.aggregate():
            raise ValueError("Provenance status does not match required checks")
        if self.checks.source_actor.status == "pass" and not any(self.source.actor.model_dump().values()):
            raise ValueError("Source actor pass requires an observed native actor")
        if self.checks.source_time.status == "pass" and not (self.source.time.created_at or self.source.time.updated_at):
            raise ValueError("Source time pass cannot use only ingestion/observation time")
        if self.checks.latest_version.status == "pass" and self.source.version.is_latest is not True:
            raise ValueError("Latest pass requires a checked matching version")
        if isinstance(self.locator, StructuredLocator):
            if set(self.locator.fields) != {field.name for field in self.content.fields}:
                raise ValueError("Structured locator and snapshot fields disagree")
        return self


class EvidenceItem(CoreContract):
    tenant_id: str = Field(min_length=1)
    evidence_id: str
    evidence_kind: Literal["document_chunk", "structured_record"] = "document_chunk"
    source: SourceRef
    raw_rank: int | None = Field(default=None,ge=1)
    vector_score: float | None = Field(default=None,allow_inf_nan=False)
    chain: ChainProfile
    evaluations: tuple[RetrievalEvaluation, ...] = ()

    @model_validator(mode="after")
    def linked(self):
        if (self.tenant_id != self.chain.tenant_id or self.evidence_id != self.chain.evidence_id
                or self.source.source_id != self.chain.source.source_id
                or self.source.source_version != self.chain.source.version.value):
            raise ValueError("Evidence and provenance identity disagree")
        if isinstance(self.chain.locator, DocumentLocator):
            locator = self.chain.locator
            if (self.evidence_kind != "document_chunk" or self.raw_rank is None or self.vector_score is None
                    or self.evidence_id != self.chain.raw_record_id
                    or (self.source.document_id, self.source.document_version, self.source.chunk_id, self.source.source_locator)
                    != (locator.document_id, locator.document_version, locator.chunk_id, locator.source_locator)
                    or self.source.content_hash != self.chain.content.hash.digest):
                raise ValueError("Evidence locator and hash disagree")
        elif (self.evidence_kind != "structured_record" or self.vector_score is not None
              or not self.source.record_id or self.source.content_hash != self.chain.content.hash.digest):
            raise ValueError("Structured evidence cannot claim a vector score")
        if any(e.candidate_id not in (None, self.evidence_id) for e in self.evaluations):
            raise ValueError("Evaluation belongs to another evidence")
        return self


class EvidenceBundle(CoreContract):
    tenant_id: str = Field(min_length=1)
    schema_version: Literal["1"] = "1"
    retrieval_event_id: str
    processing_run_id: str
    items: tuple[EvidenceItem, ...] = ()
    conflict_status: Literal["not_checked"] = "not_checked"
    coverage_status: Literal["not_checked"] = "not_checked"

    @model_validator(mode="after")
    def linked(self):
        if (len({e.evidence_id for e in self.items}) != len(self.items)
                or any(e.tenant_id != self.tenant_id or e.chain.raw_event_id != self.retrieval_event_id for e in self.items)):
            raise ValueError("Evidence bundle must reference one raw event")
        return self
