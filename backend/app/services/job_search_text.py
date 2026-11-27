from collections.abc import Sequence


def _clean(value: str | None) -> str:
    return " ".join(value.split()) if value else ""


def _unique_values(values: Sequence[str] | None) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        cleaned = _clean(value)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            unique.append(cleaned)
            seen.add(key)
    return unique


def _experience_text(
    minimum: int | None,
    maximum: int | None,
) -> str:
    if minimum is not None and minimum > 0:
        if maximum is not None:
            return f"{minimum}-{maximum} years"
        return f"{minimum}+ years"
    if maximum is not None and maximum > 0:
        return f"Up to {maximum} years"
    if minimum == 0 and maximum == 0:
        return "0 years"
    return ""


def build_searchable_job_text(
    *,
    title: str | None,
    company: str | None,
    description: str | None,
    required_skills: Sequence[str] | None,
    preferred_skills: Sequence[str] | None,
    responsibilities: Sequence[str] | None,
    min_experience_years: int | None,
    max_experience_years: int | None,
    employment_type: str | None,
    location: str | None,
    work_mode: str | None,
) -> str:
    """Build labeled search text from fields already stored on a job."""
    sections: list[str] = []
    content_seen: set[str] = set()

    def add_text(label: str, value: str | None, *, deduplicate: bool = False) -> None:
        cleaned = _clean(value)
        key = cleaned.casefold()
        if not cleaned or (deduplicate and key in content_seen):
            return
        sections.append(f"{label}: {cleaned}")
        content_seen.add(key)

    add_text("Title", title)
    add_text("Company", company)
    add_text("Description", description, deduplicate=True)

    required = _unique_values(required_skills)
    if required:
        sections.append(f"Required skills: {', '.join(required)}")

    preferred = _unique_values(preferred_skills)
    if preferred:
        sections.append(f"Preferred skills: {', '.join(preferred)}")

    responsibilities_text = [
        item
        for item in _unique_values(responsibilities)
        if item.casefold() not in content_seen
    ]
    if responsibilities_text:
        sections.append(
            "Responsibilities:\n"
            + "\n".join(f"- {item}" for item in responsibilities_text)
        )
        content_seen.update(item.casefold() for item in responsibilities_text)

    add_text(
        "Experience",
        _experience_text(min_experience_years, max_experience_years),
    )
    add_text("Employment type", employment_type)
    add_text("Work mode", work_mode)
    add_text("Location", location)
    return "\n".join(sections)
