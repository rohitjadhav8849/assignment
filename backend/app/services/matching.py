import re
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.models.candidate import CandidateProfile
from app.models.job import Job


@dataclass(frozen=True)
class ScoreWeight:
    key: str
    label: str
    value: float


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", value.casefold()).strip()


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip()
        normalized = _normalize(clean)
        if clean and normalized not in seen:
            result.append(clean)
            seen.add(normalized)
    return result


def _skill_match(candidate_skills: list[str], job_skills: list[str]) -> list[str]:
    candidate_by_key = {_normalize(skill): skill for skill in candidate_skills}
    return [candidate_by_key[_normalize(skill)] for skill in job_skills if _normalize(skill) in candidate_by_key]


def _skill_evidence(
    candidate: CandidateProfile, matched_skills: list[str]
) -> list[dict[str, object]]:
    confirmed = candidate.confirmed_profile or {}
    resume_skills = confirmed.get("skills", [])
    manual_skills = {
        _normalize(skill) for skill in confirmed.get("manual_skills", [])
    }
    results = []
    for skill in matched_skills:
        normalized = _normalize(skill)
        claim = next(
            (
                item
                for item in resume_skills
                if _normalize(item.get("value", "")) == normalized
            ),
            None,
        )
        if claim:
            results.append(
                {
                    "skill": skill,
                    "source": claim.get("source", "manual"),
                    "evidence": [
                        item["snippet"]
                        for item in claim.get("evidence", [])
                        if isinstance(item, dict) and item.get("snippet")
                    ],
                }
            )
        elif normalized in manual_skills or candidate.profile_source != "resume_confirmed":
            results.append({"skill": skill, "source": "manual", "evidence": []})
    return results


def _role_score(preferred_roles: list[str], job: Job) -> tuple[int, list[str]]:
    targets = [job.title, job.category]
    best_score = 0
    matched: list[str] = []
    for role in preferred_roles:
        role_words = set(_normalize(role).split())
        if not role_words:
            continue
        for target in targets:
            target_words = set(_normalize(target).split())
            overlap = role_words & target_words
            score = round(100 * len(overlap) / len(role_words))
            if score > best_score:
                best_score = score
                matched = [role] if overlap else []
    return best_score, matched


def _experience_score(candidate_years: float | None, job: Job) -> tuple[int, list[str]]:
    if candidate_years is None:
        return 0, []
    minimum = job.min_experience_years
    maximum = job.max_experience_years
    if candidate_years < minimum:
        shortfall = minimum - candidate_years
        return max(0, round(100 - shortfall * 30)), [
            f"Your profile lists {candidate_years:g} years; this role asks for {minimum}+"
        ]
    if maximum is not None and candidate_years > maximum:
        excess = candidate_years - maximum
        return max(0, round(100 - excess * 15)), [
            f"Your profile lists {candidate_years:g} years; this role lists {minimum}–{maximum} years"
        ]
    return 100, [
        f"{candidate_years:g} years in your profile is within the listed experience range"
    ]


def _location_matches(preferences: list[str], job: Job) -> list[str]:
    job_location = _normalize(job.location)
    job_mode = _normalize(job.work_mode)
    matches = [
        preference
        for preference in preferences
        if _normalize(preference) == job_location
        or (
            _normalize(preference) in {"remote", "anywhere", "work from anywhere"}
            and job_mode == "remote"
        )
    ]
    return _unique(matches)


def _weights(settings: Settings) -> list[ScoreWeight]:
    return [
        ScoreWeight("required_skills", "Required skills", settings.match_weight_required_skills),
        ScoreWeight("preferred_skills", "Preferred skills", settings.match_weight_preferred_skills),
        ScoreWeight("experience", "Experience", settings.match_weight_experience),
        ScoreWeight("role", "Role relevance", settings.match_weight_role),
        ScoreWeight("location", "Location", settings.match_weight_location),
        ScoreWeight("work_mode", "Work mode", settings.match_weight_work_mode),
        ScoreWeight("employment_type", "Employment type", settings.match_weight_employment_type),
    ]


def score_job(
    job: Job,
    candidate: CandidateProfile,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    candidate_skills = _unique(candidate.skills or [])
    required_matches = _skill_match(candidate_skills, job.required_skills or [])
    preferred_matches = _skill_match(candidate_skills, job.preferred_skills or [])
    required_keys = {_normalize(skill) for skill in required_matches}
    missing_required = [
        skill for skill in (job.required_skills or []) if _normalize(skill) not in required_keys
    ]

    role_preferences = _unique(
        (candidate.preferred_roles or []) + (candidate.categories or [])
    )
    role_score, matching_roles = _role_score(role_preferences, job)
    experience_score, experience_evidence = _experience_score(
        candidate.experience_years, job
    )
    matching_locations = _location_matches(candidate.locations or [], job)
    matching_modes = [
        value
        for value in (candidate.work_modes or [])
        if _normalize(value) == _normalize(job.work_mode)
    ]
    matching_employment = [
        value
        for value in (candidate.employment_types or [])
        if _normalize(value) == _normalize(job.employment_type)
    ]

    values = {
        "required_skills": (
            round(100 * len(required_matches) / len(job.required_skills))
            if job.required_skills
            else 0
        ),
        "preferred_skills": (
            round(100 * len(preferred_matches) / len(job.preferred_skills))
            if job.preferred_skills
            else 0
        ),
        "experience": experience_score,
        "role": role_score,
        "location": 100 if matching_locations else 0,
        "work_mode": 100 if matching_modes else 0,
        "employment_type": 100 if matching_employment else 0,
    }

    active_keys: set[str] = set()
    if candidate_skills and job.required_skills:
        active_keys.add("required_skills")
    if candidate_skills and job.preferred_skills:
        active_keys.add("preferred_skills")
    if candidate.experience_years is not None:
        active_keys.add("experience")
    if role_preferences:
        active_keys.add("role")
    if candidate.locations:
        active_keys.add("location")
    if candidate.work_modes:
        active_keys.add("work_mode")
    if candidate.employment_types:
        active_keys.add("employment_type")

    weights = [weight for weight in _weights(settings) if weight.key in active_keys]
    weight_total = sum(weight.value for weight in weights)
    breakdown = []
    for weight in weights:
        contribution = (
            weight.value * values[weight.key] / weight_total if weight_total else 0
        )
        evidence: list[str] = []
        if weight.key == "required_skills":
            evidence = [f"Profile skill: {skill}" for skill in required_matches]
            evidence.extend(f"Not listed in profile: {skill}" for skill in missing_required)
        elif weight.key == "preferred_skills":
            evidence = [f"Profile skill: {skill}" for skill in preferred_matches]
        elif weight.key == "experience":
            evidence = experience_evidence
        elif weight.key == "role":
            evidence = [f"Preferred role: {role}" for role in matching_roles]
        elif weight.key == "location":
            evidence = [f"Preferred location: {value}" for value in matching_locations]
        elif weight.key == "work_mode":
            evidence = [f"Preferred work mode: {value}" for value in matching_modes]
        elif weight.key == "employment_type":
            evidence = [
                f"Preferred employment type: {value}" for value in matching_employment
            ]
        breakdown.append(
            {
                "key": weight.key,
                "label": weight.label,
                "score": values[weight.key],
                "weight": weight.value,
                "contribution": round(contribution, 2),
                "evidence": evidence,
            }
        )

    score = round(sum(item["contribution"] for item in breakdown))
    matching_preferences = _unique(
        [f"Role: {role}" for role in matching_roles]
        + [f"Location: {location}" for location in matching_locations]
        + [f"Work mode: {mode}" for mode in matching_modes]
        + [f"Employment: {kind}" for kind in matching_employment]
    )
    reasons = []
    if candidate.experience_years is not None and experience_score >= 70:
        reasons.append(
            f"Your {candidate.experience_years:g} years align with the listed experience range"
        )
    if candidate.experience_years is not None and experience_score < 70:
        reasons.append("The listed experience range differs from your profile")
    if required_matches:
        reasons.append(f"Matches {len(required_matches)} required skill(s)")
    if preferred_matches:
        reasons.append(f"Includes {len(preferred_matches)} of your listed skills as preferred")
    if matching_roles:
        reasons.append(f"Relevant to your preferred role: {matching_roles[0]}")
    if matching_locations:
        reasons.append(f"Location matches: {matching_locations[0]}")
    if matching_modes:
        reasons.append(f"Work mode matches your preference: {job.work_mode}")
    if matching_employment:
        reasons.append(f"Employment type matches your preference: {job.employment_type}")
    if not reasons:
        reasons.append(
            "No configured matching criteria overlap with the profile information available"
        )

    return {
        "score": score,
        "score_breakdown": breakdown,
        "matched_skills": _unique(required_matches + preferred_matches),
        "missing_required_skills": _unique(missing_required),
        "matching_preferences": matching_preferences,
        "reasons": reasons[:3],
        "evidence_source": (
            "confirmed_resume"
            if candidate.profile_source == "resume_confirmed"
            else "manual_profile"
        ),
        "skill_evidence": _skill_evidence(
            candidate, _unique(required_matches + preferred_matches)
        ),
    }
