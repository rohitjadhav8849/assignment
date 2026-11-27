from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.schemas.jobs import (
    JobCard,
    JobDetail,
    PicksResponse,
    RetrievalJobResult,
    RetrievalSearchResponse,
    SimilarJob,
)
from app.services.job_search import (
    search_jobs_bm25,
    search_jobs_hybrid,
    search_jobs_semantic,
)
from app.services.matching import score_job
from app.services.profiles import get_candidate_profile

RetrievalMode = Literal["bm25", "semantic", "hybrid"]


def _job_card(job: Job, candidate: CandidateProfile) -> JobCard:
    return JobCard.model_validate(
        {
            **{
                field: getattr(job, field)
                for field in (
                    "id",
                    "title",
                    "company",
                    "category",
                    "location",
                    "work_mode",
                    "employment_type",
                    "salary_min",
                    "salary_max",
                    "salary_currency",
                    "required_skills",
                    "preferred_skills",
                    "is_synthetic",
                    "data_source",
                )
            },
            "match": score_job(job, candidate),
        }
    )


def get_job_picks(session: Session, limit: int = 50) -> PicksResponse:
    candidate = get_candidate_profile(session)
    if not candidate.is_configured:
        return PicksResponse(profile_configured=False, total=0, jobs=[])

    jobs = list(session.scalars(select(Job)).all())
    ranked = [_job_card(job, candidate) for job in jobs]
    ranked.sort(key=lambda job: (-job.match.score, job.title.casefold(), job.id))
    return PicksResponse(
        profile_configured=True,
        total=len(ranked),
        jobs=ranked[:limit],
    )


def build_candidate_search_query(candidate: CandidateProfile) -> str:
    """Build stable retrieval text without using candidate contact details."""
    values: list[str] = []
    seen: set[str] = set()

    def add_text(value: object) -> None:
        if isinstance(value, dict):
            value = value.get("value")
        if not isinstance(value, str):
            return
        cleaned = " ".join(value.split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            values.append(cleaned)
            seen.add(key)

    for value in candidate.skills or []:
        add_text(value)
    for value in candidate.preferred_roles or []:
        add_text(value)
    for value in candidate.categories or []:
        add_text(value)

    if candidate.experience_years is not None:
        add_text(f"{float(candidate.experience_years):g} years experience")

    confirmed = candidate.confirmed_profile
    if not isinstance(confirmed, dict):
        return " ".join(values)

    for skill in confirmed.get("skills") or []:
        add_text(skill)
    for skill in confirmed.get("manual_skills") or []:
        add_text(skill)

    for project in confirmed.get("projects") or []:
        if not isinstance(project, dict):
            continue
        add_text(project.get("name"))
        add_text(project.get("description"))
        for technology in project.get("technologies") or []:
            add_text(technology)

    for experience in confirmed.get("work_experience") or []:
        if not isinstance(experience, dict):
            continue
        add_text(experience.get("title"))
        add_text(experience.get("description"))
        for technology in experience.get("technologies") or []:
            add_text(technology)

    for certification in confirmed.get("certifications") or []:
        if isinstance(certification, dict):
            add_text(certification.get("name"))

    return " ".join(values)


def get_job_retrieval(
    session: Session,
    mode: RetrievalMode,
    top_k: int = 10,
) -> RetrievalSearchResponse:
    candidate = get_candidate_profile(session)
    score_type = {
        "bm25": "bm25",
        "semantic": "semantic_similarity",
        "hybrid": "rrf",
    }[mode]

    if not candidate or not candidate.is_configured:
        return RetrievalSearchResponse(
            profile_configured=False,
            query_available=False,
            score_type=score_type,
            total=0,
            jobs=[],
        )

    query = build_candidate_search_query(candidate)
    if not query:
        return RetrievalSearchResponse(
            profile_configured=True,
            query_available=False,
            score_type=score_type,
            total=0,
            jobs=[],
        )

    if mode == "bm25":
        results = search_jobs_bm25(query, top_k=top_k)
        jobs = [
            RetrievalJobResult(
                id=result.job_id,
                title=result.title,
                company=result.company,
                score=result.score,
            )
            for result in results
        ]
    elif mode == "semantic":
        results = search_jobs_semantic(query, top_k=top_k)
        jobs = [
            RetrievalJobResult(
                id=result.job_id,
                title=result.title,
                company=result.company,
                score=result.similarity_score,
            )
            for result in results
        ]
    else:
        results = search_jobs_hybrid(query, top_k=top_k)
        jobs = [
            RetrievalJobResult(
                id=result.job_id,
                title=result.title,
                company=result.company,
                score=result.rrf_score,
            )
            for result in results
        ]

    return RetrievalSearchResponse(
        profile_configured=True,
        query_available=True,
        score_type=score_type,
        total=len(jobs),
        jobs=jobs,
    )


def get_job_detail(session: Session, job_id: int) -> JobDetail | None:
    job = session.get(Job, job_id)
    if job is None:
        return None

    candidate = get_candidate_profile(session)
    card = _job_card(job, candidate)
    profile_evidence = []
    for item in card.match.skill_evidence:
        if item.source == "resume":
            profile_evidence.extend(
                f"Resume evidence for {item.skill}: {snippet}"
                for snippet in item.evidence
            )
        else:
            profile_evidence.append(f"Manually entered skill: {item.skill}")
    if candidate.experience_years is not None:
        experience = (candidate.confirmed_profile or {}).get("experience_years")
        if experience and experience.get("source") == "resume":
            profile_evidence.extend(
                f"Resume evidence for experience: {item['snippet']}"
                for item in experience.get("evidence", [])
                if item.get("snippet")
            )
        else:
            profile_evidence.append(
                f"Manually entered experience: {candidate.experience_years:g} years"
            )

    candidates = session.scalars(
        select(Job).where(Job.id != job.id, Job.category == job.category)
    ).all()
    job_skill_keys = {skill.casefold() for skill in job.required_skills}
    similar = sorted(
        candidates,
        key=lambda other: (
            -len(job_skill_keys & {skill.casefold() for skill in other.required_skills}),
            other.title.casefold(),
            other.id,
        ),
    )[:3]

    return JobDetail.model_validate(
        {
            **card.model_dump(),
            "description": job.description,
            "responsibilities": job.responsibilities,
            "min_experience_years": job.min_experience_years,
            "max_experience_years": job.max_experience_years,
            "profile_evidence": profile_evidence,
            "evidence_notice": (
                "Candidate-confirmed resume facts include source snippets. "
                "Manually added profile facts are labeled as manual."
                if candidate.profile_source == "resume_confirmed"
                else (
                    "Match evidence uses manually entered profile information. "
                    "No confirmed resume profile is active."
                )
            ),
            "similar_jobs": [
                SimilarJob.model_validate(other) for other in similar
            ],
        }
    )
