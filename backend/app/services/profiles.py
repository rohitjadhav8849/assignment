from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate import CandidateProfile
from app.schemas.jobs import CandidateProfileInput

DEMO_CANDIDATE_ID = 1


def _clean_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        key = item.casefold()
        if item and key not in seen:
            cleaned.append(item)
            seen.add(key)
    return cleaned


def get_candidate_profile(session: Session) -> CandidateProfile:
    profile = session.get(CandidateProfile, DEMO_CANDIDATE_ID)
    if profile is None:
        profile = CandidateProfile(id=DEMO_CANDIDATE_ID, full_name="Candidate")
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def update_candidate_profile(
    session: Session,
    profile_data: CandidateProfileInput,
) -> CandidateProfile:
    profile = get_candidate_profile(session)
    profile.full_name = profile_data.full_name or "Candidate"
    profile.skills = _clean_list(profile_data.skills)
    profile.experience_years = profile_data.experience_years
    profile.preferred_roles = _clean_list(profile_data.preferred_roles)
    profile.categories = _clean_list(profile_data.categories)
    profile.locations = _clean_list(profile_data.locations)
    profile.work_modes = _clean_list(profile_data.work_modes)
    profile.employment_types = _clean_list(profile_data.employment_types)
    profile.profile_source = "manual"
    profile.confirmed_profile = None
    profile.is_configured = any(
        (
            profile.skills,
            profile.experience_years is not None,
            profile.preferred_roles,
            profile.categories,
            profile.locations,
            profile.work_modes,
            profile.employment_types,
        )
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile
