from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, event, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.services.job_search_text import build_searchable_job_text

JSON_VALUE = JSON().with_variant(JSONB, "postgresql")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seed_key: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    company: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(Text)
    searchable_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    responsibilities: Mapped[list[str]] = mapped_column(JSON_VALUE)
    required_skills: Mapped[list[str]] = mapped_column(JSON_VALUE)
    preferred_skills: Mapped[list[str]] = mapped_column(JSON_VALUE)
    min_experience_years: Mapped[int] = mapped_column(Integer, default=0)
    max_experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str] = mapped_column(String(160), index=True)
    work_mode: Mapped[str] = mapped_column(String(40), index=True)
    employment_type: Mapped[str] = mapped_column(String(40), index=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    data_source: Mapped[str] = mapped_column(
        String(40), default="SYNTHETIC DEMO", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


@event.listens_for(Job, "before_insert")
@event.listens_for(Job, "before_update")
def _refresh_searchable_text(mapper, connection, job: Job) -> None:
    job.searchable_text = build_searchable_job_text(
        title=job.title,
        company=job.company,
        description=job.description,
        required_skills=job.required_skills,
        preferred_skills=job.preferred_skills,
        responsibilities=job.responsibilities,
        min_experience_years=job.min_experience_years,
        max_experience_years=job.max_experience_years,
        employment_type=job.employment_type,
        location=job.location,
        work_mode=job.work_mode,
    )
