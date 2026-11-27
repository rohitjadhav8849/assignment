import re
from collections.abc import Iterator
from typing import Any

from app.schemas.resumes import (
    ConfirmedCandidateProfile,
    ConfirmedEducation,
    ConfirmedExperience,
    ConfirmedFact,
    ConfirmedNumberFact,
    ConfirmedProject,
    ConfirmedSkill,
    ResumeExtraction,
)


class UnsupportedEvidenceError(ValueError):
    """A resume-sourced confirmed fact lacks verifiable source text."""


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).casefold().strip()


def _evidence_matches(snippet: str, source_text: str) -> bool:
    normalized_snippet = _normalized_text(snippet)
    return bool(normalized_snippet) and normalized_snippet in _normalized_text(source_text)


def _iter_extracted_claims(
    value: Any, path: str = ""
) -> Iterator[tuple[str, str, list[str]]]:
    if isinstance(value, dict):
        evidence = value.get("evidence")
        if isinstance(evidence, list):
            snippets = [
                item["snippet"]
                for item in evidence
                if isinstance(item, dict) and isinstance(item.get("snippet"), str)
            ]
            claim_fields = (
                "value",
                "name",
                "title",
                "institution",
                "degree",
                "field_of_study",
                "company",
                "start_date",
                "end_date",
                "description",
                "issuer",
                "date",
            )
            for key in claim_fields:
                claim = value.get(key)
                if isinstance(claim, (str, int, float)) and str(claim).strip():
                    claim_path = f"{path}.{key}" if path else key
                    yield claim_path, str(claim), snippets
        for key, child in value.items():
            if key != "evidence":
                child_path = f"{path}.{key}" if path else key
                yield from _iter_extracted_claims(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_extracted_claims(child, f"{path}[{index}]")


def validate_extraction(
    extraction: ResumeExtraction, source_text: str
) -> dict[str, Any]:
    claims = []
    for path, value, snippets in _iter_extracted_claims(
        extraction.model_dump(mode="json")
    ):
        supported_snippets = [
            snippet for snippet in snippets if _evidence_matches(snippet, source_text)
        ]
        claims.append(
            {
                "path": path,
                "value": value,
                "supported": bool(supported_snippets),
                "evidence": supported_snippets,
            }
        )
    supported_count = sum(claim["supported"] for claim in claims)
    claim_count = len(claims)
    unsupported = [claim for claim in claims if not claim["supported"]]
    return {
        "claims": claims,
        "supported_claim_count": supported_count,
        "claim_count": claim_count,
        "evidence_coverage": (
            round(supported_count / claim_count, 4) if claim_count else 0.0
        ),
        "unsupported_claim_count": len(unsupported),
        "requires_review": True,
    }


def _fact(
    value: str | None, evidence: list[dict[str, str]]
) -> ConfirmedFact | None:
    if value is None:
        return None
    return ConfirmedFact(
        value=value,
        source="resume",
        evidence=[{"snippet": item["snippet"]} for item in evidence],
    )


def _confirmed_skill(skill: dict[str, Any]) -> ConfirmedSkill:
    return ConfirmedSkill(
        value=skill["name"],
        category=skill["category"],
        source="resume",
        evidence=skill.get("evidence", []),
    )


def build_review_profile(extraction: ResumeExtraction) -> ConfirmedCandidateProfile:
    data = extraction.model_dump(mode="python")

    education = []
    for item in data["education"]:
        evidence = item.get("evidence", [])
        education.append(
            ConfirmedEducation(
                source="resume",
                institution=_fact(item.get("institution"), evidence),
                degree=_fact(item.get("degree"), evidence),
                field_of_study=_fact(item.get("field_of_study"), evidence),
                start_date=_fact(item.get("start_date"), evidence),
                end_date=_fact(item.get("end_date"), evidence),
                evidence=evidence,
            )
        )

    experience = []
    for item in data["work_experience"]:
        evidence = item.get("evidence", [])
        experience.append(
            ConfirmedExperience(
                source="resume",
                title=_fact(item["title"], evidence),
                company=_fact(item.get("company"), evidence),
                experience_type=item["experience_type"],
                start_date=_fact(item.get("start_date"), evidence),
                end_date=_fact(item.get("end_date"), evidence),
                description=_fact(item.get("description"), evidence),
                technologies=[
                    _confirmed_skill(skill) for skill in item.get("technologies", [])
                ],
                evidence=evidence,
            )
        )

    projects = []
    for item in data["projects"]:
        evidence = item.get("evidence", [])
        projects.append(
            ConfirmedProject(
                source="resume",
                name=_fact(item["name"], evidence),
                description=_fact(item.get("description"), evidence),
                technologies=[
                    _confirmed_skill(skill) for skill in item.get("technologies", [])
                ],
                evidence=evidence,
            )
        )

    certifications = []
    for item in data["certifications"]:
        evidence = item.get("evidence", [])
        certifications.append(
            {
                "source": "resume",
                "name": _fact(item["name"], evidence),
                "issuer": _fact(item.get("issuer"), evidence),
                "date": _fact(item.get("date"), evidence),
                "evidence": evidence,
            }
        )

    achievements = []
    for item in data["achievements"]:
        evidence = item.get("evidence", [])
        achievements.append(
            {
                "source": "resume",
                "title": _fact(item["title"], evidence),
                "description": _fact(item.get("description"), evidence),
                "evidence": evidence,
            }
        )

    full_name = data.get("full_name")
    email = data.get("email")
    phone = data.get("phone")
    experience_years = data.get("total_experience_years")
    return ConfirmedCandidateProfile(
        full_name=_fact(full_name["value"], full_name["evidence"]) if full_name else None,
        email=_fact(email["value"], email["evidence"]) if email else None,
        phone=_fact(phone["value"], phone["evidence"]) if phone else None,
        experience_years=(
            ConfirmedNumberFact(
                value=experience_years["value"],
                source="resume",
                evidence=experience_years.get("evidence", []),
            )
            if experience_years
            else None
        ),
        skills=[_confirmed_skill(skill) for skill in data["skills"]],
        education=education,
        work_experience=experience,
        projects=projects,
        certifications=certifications,
        achievements=achievements,
    )


def validate_confirmed_profile(
    profile: ConfirmedCandidateProfile, source_text: str
) -> None:
    data = profile.model_dump(mode="json")
    for path, value, snippets in _iter_confirmed_resume_claims(data):
        if not snippets:
            raise UnsupportedEvidenceError(
                f"Resume-sourced field '{path}' must include source evidence."
            )
        if not all(_evidence_matches(snippet, source_text) for snippet in snippets):
            raise UnsupportedEvidenceError(
                f"Resume-sourced field '{path}' has evidence not found in the uploaded PDF."
            )


def _iter_confirmed_resume_claims(
    value: Any, path: str = ""
) -> Iterator[tuple[str, str, list[str]]]:
    if isinstance(value, dict):
        if value.get("source") == "resume" and "value" in value:
            raw_evidence = value.get("evidence", [])
            snippets = [
                item["snippet"]
                for item in raw_evidence
                if isinstance(item, dict) and isinstance(item.get("snippet"), str)
            ]
            yield path, str(value.get("value", "")), snippets
        for key, child in value.items():
            if key not in {"evidence", "source"}:
                child_path = f"{path}.{key}" if path else key
                yield from _iter_confirmed_resume_claims(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_confirmed_resume_claims(child, f"{path}[{index}]")
