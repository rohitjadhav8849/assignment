from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CandidateProfileInput(BaseModel):
    full_name: str = Field(default="Candidate", min_length=1, max_length=120)
    skills: list[str] = Field(default_factory=list, max_length=100)
    experience_years: float | None = Field(default=None, ge=0, le=60)
    preferred_roles: list[str] = Field(default_factory=list, max_length=50)
    categories: list[str] = Field(default_factory=list, max_length=50)
    locations: list[str] = Field(default_factory=list, max_length=50)
    work_modes: list[str] = Field(default_factory=list, max_length=10)
    employment_types: list[str] = Field(default_factory=list, max_length=10)
    profile_source: Literal["manual"] = "manual"

    model_config = ConfigDict(str_strip_whitespace=True)


class CandidateProfileResponse(CandidateProfileInput):
    is_configured: bool
    profile_source: str

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class MatchedSkillEvidence(BaseModel):
    skill: str
    source: Literal["resume", "manual"]
    evidence: list[str]


class MatchBreakdownItem(BaseModel):
    key: str
    label: str
    score: int
    weight: float
    contribution: float
    evidence: list[str]


class JobMatch(BaseModel):
    score: int
    score_breakdown: list[MatchBreakdownItem]
    matched_skills: list[str]
    missing_required_skills: list[str]
    matching_preferences: list[str]
    reasons: list[str]
    evidence_source: str
    skill_evidence: list[MatchedSkillEvidence] = Field(default_factory=list)


class JobCard(BaseModel):
    id: int
    title: str
    company: str
    category: str
    location: str
    work_mode: str
    employment_type: str
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    required_skills: list[str]
    preferred_skills: list[str]
    is_synthetic: bool
    data_source: str
    match: JobMatch

    model_config = ConfigDict(from_attributes=True)


class PicksResponse(BaseModel):
    profile_configured: bool
    total: int
    jobs: list[JobCard]


class RetrievalJobResult(BaseModel):
    id: int
    title: str
    company: str
    score: float


class RetrievalSearchResponse(BaseModel):
    profile_configured: bool
    query_available: bool
    score_type: Literal["bm25", "semantic_similarity", "rrf"]
    total: int
    jobs: list[RetrievalJobResult]


class SimilarJob(BaseModel):
    id: int
    title: str
    company: str
    category: str
    location: str
    work_mode: str

    model_config = ConfigDict(from_attributes=True)


class JobDetail(JobCard):
    description: str
    responsibilities: list[str]
    min_experience_years: int
    max_experience_years: int | None
    profile_evidence: list[str]
    evidence_notice: str
    similar_jobs: list[SimilarJob]
