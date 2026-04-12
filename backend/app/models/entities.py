from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class SessionORM(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_created_at", "created_at"),
    )

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    scene: Mapped[str] = mapped_column(String(100), nullable=False, default="knowledge_assistant")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    qa_history: Mapped[list["QAHistoryORM"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class DocumentORM(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_created_at", "created_at"),
        Index("ix_documents_status", "status"),
    )

    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="upload")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    chunks_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    chunks: Mapped[list["DocumentChunkORM"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    index_jobs: Mapped[list["IndexJobORM"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentChunkORM(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_document_id_ordinal", "document_id", "ordinal"),
    )

    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    snippet: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    document: Mapped[DocumentORM] = relationship(back_populates="chunks")
    embeddings: Mapped[list["ChunkEmbeddingORM"]] = relationship(
        back_populates="chunk",
        cascade="all, delete-orphan",
    )


class ChunkEmbeddingORM(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        Index("ix_chunk_embeddings_chunk_id", "chunk_id"),
        Index("ix_chunk_embeddings_embedding_model", "embedding_model"),
        Index("ix_chunk_embeddings_storage_backend", "storage_backend"),
        UniqueConstraint("chunk_id", "embedding_model", name="uq_chunk_embeddings_chunk_model"),
    )

    embedding_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("document_chunks.chunk_id", ondelete="CASCADE"), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(40), nullable=False, default="inline")
    storage_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vector_json: Mapped[list[float] | None] = mapped_column(JSON, nullable=True, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    chunk: Mapped[DocumentChunkORM] = relationship(back_populates="embeddings")


class IndexJobORM(Base):
    __tablename__ = "index_jobs"
    __table_args__ = (
        Index("ix_index_jobs_document_created_at", "document_id", "created_at"),
        Index("ix_index_jobs_status", "status"),
    )

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued")
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[DocumentORM] = relationship(back_populates="index_jobs")


class QAHistoryORM(Base):
    __tablename__ = "qa_history"
    __table_args__ = (
        CheckConstraint("latency_ms >= 0", name="ck_qa_history_latency_non_negative"),
        Index("ix_qa_history_session_created_at", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    retrieval_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    refusal_reason: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    need_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    answer_provider: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    citations_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    session: Mapped[SessionORM] = relationship(back_populates="qa_history")


class FeedbackORM(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("rating IN ('up', 'down', 'neutral')", name="ck_feedback_rating_allowed"),
        Index("ix_feedback_session_created_at", "session_id", "created_at"),
        Index("ix_feedback_trace_id", "trace_id"),
    )

    feedback_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rating: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
