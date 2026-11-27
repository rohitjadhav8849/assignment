from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

JSON_VALUE = JSON().with_variant(JSONB, "postgresql")


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), default="Candidate")
    skills: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    experience_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    preferred_roles: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    categories: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    locations: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    work_modes: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    employment_types: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    profile_source: Mapped[str] = mapped_column(String(20), default="manual")
    confirmed_profile: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    is_configured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
