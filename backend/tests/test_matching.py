from app.core.config import Settings
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.services.matching import score_job


def make_job(**overrides) -> Job:
    values = {
        "id": 1,
        "seed_key": "test:1",
        "title": "Backend Engineer",
        "company": "Demo Company",
        "category": "Backend Engineering",
        "description": "Build backend services.",
        "responsibilities": [],
        "required_skills": ["Python", "PostgreSQL"],
        "preferred_skills": ["Docker"],
        "min_experience_years": 3,
        "max_experience_years": 8,
        "location": "Seattle, WA",
        "work_mode": "Remote",
        "employment_type": "Full-time",
        "is_synthetic": True,
        "data_source": "SYNTHETIC DEMO",
    }
    values.update(overrides)
    return Job(**values)


def make_candidate(**overrides) -> CandidateProfile:
    values = {
        "id": 1,
        "full_name": "Candidate",
        "skills": ["python", "PostgreSQL", "Docker"],
        "experience_years": 4,
        "preferred_roles": ["Backend Engineer"],
        "categories": [],
        "locations": ["Seattle, WA"],
        "work_modes": ["Remote"],
        "employment_types": ["Full-time"],
        "profile_source": "manual",
        "is_configured": True,
    }
    values.update(overrides)
    return CandidateProfile(**values)


def test_matching_returns_skill_gaps_and_explainable_preferences() -> None:
    result = score_job(make_job(), make_candidate())

    assert result["score"] == 100
    assert result["matched_skills"] == ["python", "PostgreSQL", "Docker"]
    assert result["missing_required_skills"] == []
    assert "Location: Seattle, WA" in result["matching_preferences"]
    assert result["evidence_source"] == "manual_profile"


def test_changing_candidate_skills_changes_match_score() -> None:
    job = make_job()
    full_match = score_job(job, make_candidate())
    no_skill_match = score_job(
        job,
        make_candidate(skills=["Excel"], preferred_roles=[], locations=[], work_modes=[], employment_types=[]),
    )

    assert full_match["score"] > no_skill_match["score"]
    assert no_skill_match["missing_required_skills"] == ["Python", "PostgreSQL"]


def test_matching_weights_are_configurable() -> None:
    result = score_job(
        make_job(),
        make_candidate(skills=["Python"]),
        Settings(
            match_weight_required_skills=1,
            match_weight_preferred_skills=0,
            match_weight_experience=0,
            match_weight_role=0,
            match_weight_location=0,
            match_weight_work_mode=0,
            match_weight_employment_type=0,
        ),
    )

    assert result["score"] == 50
    assert result["score_breakdown"][0]["weight"] == 1


def test_experience_range_is_part_of_compatibility() -> None:
    within_range = score_job(make_job(), make_candidate(experience_years=5))
    above_range = score_job(make_job(), make_candidate(experience_years=10))

    within_experience = next(
        item for item in within_range["score_breakdown"] if item["key"] == "experience"
    )
    above_experience = next(
        item for item in above_range["score_breakdown"] if item["key"] == "experience"
    )
    assert within_experience["score"] == 100
    assert above_experience["score"] == 70


def test_missing_candidate_skills_do_not_create_skill_score_penalties() -> None:
    result = score_job(
        make_job(),
        make_candidate(
            skills=[],
            preferred_roles=["Backend Engineer"],
            locations=["Seattle, WA"],
        ),
    )

    assert result["score"] > 0
    assert result["missing_required_skills"] == ["Python", "PostgreSQL"]
    assert "required_skills" not in {
        item["key"] for item in result["score_breakdown"]
    }
