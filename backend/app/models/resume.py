from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base

JSON_VALUE = JSON().with_variant(JSONB, "postgresql")


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_profile_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_filename: Mapped[str] = mapped_column(String(80), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    extraction_status: Mapped[str] = mapped_column(
        String(32), default="queued", index=True
    )
    extraction_error: Mapped[str | None] = mapped_column(String(80), nullable=True)
    extraction_failure_category: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    extraction_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_diagnostic: Mapped[str | None] = mapped_column(String(300), nullable=True)
    extraction_retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    extraction_attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_data: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    confirmed_data: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    validation_report: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
