from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EvidenceSnippet(StrictSchema):
    snippet: str = Field(min_length=1, max_length=600)


class EvidenceValue(StrictSchema):
    value: str = Field(min_length=1, max_length=300)
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class EvidenceNumber(StrictSchema):
    value: float = Field(ge=0, le=60)
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class ResumeSkill(StrictSchema):
    name: str = Field(min_length=1, max_length=100)
    category: Literal["technical", "non_technical"]
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class ResumeEducation(StrictSchema):
    institution: str | None = Field(default=None, max_length=200)
    degree: str | None = Field(default=None, max_length=160)
    field_of_study: str | None = Field(default=None, max_length=160)
    start_date: str | None = Field(default=None, max_length=40)
    end_date: str | None = Field(default=None, max_length=40)
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class ResumeExperience(StrictSchema):
    title: str = Field(min_length=1, max_length=160)
    company: str | None = Field(default=None, max_length=200)
    experience_type: Literal["employment", "internship"]
    start_date: str | None = Field(default=None, max_length=40)
    end_date: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=2000)
    technologies: list[ResumeSkill] = Field(default_factory=list, max_length=60)
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class ResumeProject(StrictSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    technologies: list[ResumeSkill] = Field(default_factory=list, max_length=60)
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class ResumeCertification(StrictSchema):
    name: str = Field(min_length=1, max_length=200)
    issuer: str | None = Field(default=None, max_length=200)
    date: str | None = Field(default=None, max_length=40)
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class ResumeAchievement(StrictSchema):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class UncertainField(StrictSchema):
    field: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=500)


class ResumeExtraction(StrictSchema):
    full_name: EvidenceValue | None = None
    email: EvidenceValue | None = None
    phone: EvidenceValue | None = None
    total_experience_years: EvidenceNumber | None = None
    skills: list[ResumeSkill] = Field(default_factory=list, max_length=100)
    education: list[ResumeEducation] = Field(default_factory=list, max_length=40)
    work_experience: list[ResumeExperience] = Field(default_factory=list, max_length=80)
    projects: list[ResumeProject] = Field(default_factory=list, max_length=100)
    certifications: list[ResumeCertification] = Field(default_factory=list, max_length=80)
    achievements: list[ResumeAchievement] = Field(default_factory=list, max_length=100)
    uncertain_fields: list[UncertainField] = Field(default_factory=list, max_length=100)


class ConfirmedFact(StrictSchema):
    value: str = Field(min_length=1, max_length=4000)
    source: Literal["resume", "manual"]
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class ConfirmedNumberFact(StrictSchema):
    value: float = Field(ge=0, le=60)
    source: Literal["resume", "manual"]
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class ConfirmedSkill(ConfirmedFact):
    category: Literal["technical", "non_technical"] = "technical"


class ConfirmedEducation(StrictSchema):
    source: Literal["resume", "manual"]
    institution: ConfirmedFact | None = None
    degree: ConfirmedFact | None = None
    field_of_study: ConfirmedFact | None = None
    start_date: ConfirmedFact | None = None
    end_date: ConfirmedFact | None = None
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class ConfirmedExperience(StrictSchema):
    source: Literal["resume", "manual"]
    title: ConfirmedFact
    company: ConfirmedFact | None = None
    experience_type: Literal["employment", "internship"]
    start_date: ConfirmedFact | None = None
    end_date: ConfirmedFact | None = None
    description: ConfirmedFact | None = None
    technologies: list[ConfirmedSkill] = Field(default_factory=list, max_length=60)
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class ConfirmedProject(StrictSchema):
    source: Literal["resume", "manual"]
    name: ConfirmedFact
    description: ConfirmedFact | None = None
    technologies: list[ConfirmedSkill] = Field(default_factory=list, max_length=60)
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class ConfirmedCertification(StrictSchema):
    source: Literal["resume", "manual"]
    name: ConfirmedFact
    issuer: ConfirmedFact | None = None
    date: ConfirmedFact | None = None
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class ConfirmedAchievement(StrictSchema):
    source: Literal["resume", "manual"]
    title: ConfirmedFact
    description: ConfirmedFact | None = None
    evidence: list[EvidenceSnippet] = Field(default_factory=list, max_length=10)


class ConfirmedCandidateProfile(StrictSchema):
    full_name: ConfirmedFact | None = None
    email: ConfirmedFact | None = None
    phone: ConfirmedFact | None = None
    experience_years: ConfirmedNumberFact | None = None
    skills: list[ConfirmedSkill] = Field(default_factory=list, max_length=100)
    manual_skills: list[str] = Field(default_factory=list, max_length=100)
    education: list[ConfirmedEducation] = Field(default_factory=list, max_length=40)
    work_experience: list[ConfirmedExperience] = Field(default_factory=list, max_length=80)
    projects: list[ConfirmedProject] = Field(default_factory=list, max_length=100)
    certifications: list[ConfirmedCertification] = Field(default_factory=list, max_length=80)
    achievements: list[ConfirmedAchievement] = Field(default_factory=list, max_length=100)


class ResumeListItem(StrictSchema):
    id: int
    original_filename: str
    size_bytes: int
    extraction_status: str
    extraction_error: str | None
    failure_category: str | None = None
    http_status: int | None = None
    diagnostic: str | None = None
    retryable: bool = False
    attempts: int = 0
    is_confirmed: bool
    uploaded_at: datetime
    extracted_at: datetime | None
    confirmed_at: datetime | None


class ResumeDetail(ResumeListItem):
    extracted_data: ResumeExtraction | None
    validation_report: dict | None
    review_profile: ConfirmedCandidateProfile | None
    message: str | None = None


class CandidatePreferences(StrictSchema):
    locations: list[str] = Field(default_factory=list, max_length=50)
    work_modes: list[Literal["Remote", "Hybrid", "On-site"]] = Field(
        default_factory=list, max_length=3
    )
    employment_types: list[Literal["Full-time", "Part-time", "Contract", "Internship"]] = Field(
        default_factory=list, max_length=4
    )
    salary_min: int | None = Field(default=None, ge=0, le=10_000_000)
    salary_max: int | None = Field(default=None, ge=0, le=10_000_000)
    salary_currency: str = Field(
        default="USD", min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$"
    )

    @model_validator(mode="after")
    def validate_salary_range(self) -> "CandidatePreferences":
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("Minimum salary cannot exceed maximum salary.")
        return self
