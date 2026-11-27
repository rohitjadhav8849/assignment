import re
from collections.abc import Iterable

from app.schemas.resumes import EvidenceNumber, ResumeExperience
from app.services.resume_parser_common import DATE_RANGE, Line, entry_blocks, evidence
from app.services.resume_skills_parser import extract_known_technical_skills

_ROLE_WORDS = {
    "administrator",
    "analyst",
    "architect",
    "consultant",
    "designer",
    "director",
    "engineer",
    "intern",
    "lead",
    "manager",
    "scientist",
    "specialist",
    "developer",
    "programmer",
    "researcher",
    "technician",
    "nurse",
    "teacher",
}
_YEARS = re.compile(
    r"(?:total\s+|professional\s+)?experience(?:\s+of)?\s*[:=-]?\s*"
    r"(?P<years>\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b|"
    r"(?P<reverse>\d+(?:\.\d+)?)\s*\+?\s+years?\s+of\s+experience\b",
    re.IGNORECASE,
)


def extract_experience_years(lines: Iterable[Line]) -> EvidenceNumber | None:
    for raw, content in lines:
        match = _YEARS.search(raw) or _YEARS.search(content)
        if match:
            years = float(match.group("years") or match.group("reverse"))
            return EvidenceNumber(
                value=years,
                evidence=evidence([(raw, content)], match.group(0)),
            )
    return None


def _is_role(content: str) -> bool:
    words = set(re.findall(r"[a-z]+", content.casefold()))
    return bool(words & _ROLE_WORDS)


def _parse_block(block: list[Line], *, internship: bool) -> ResumeExperience | None:
    title_line = next(
        ((raw, content) for raw, content in block if _is_role(content)),
        None,
    )
    if title_line is None:
        return None
    raw_title, title = title_line
    date_line = next(
        ((raw, content) for raw, content in block if DATE_RANGE.search(content)),
        None,
    )
    date_match = DATE_RANGE.search(date_line[1]) if date_line else None
    company_line = next(
        (
            (raw, re.sub(r"^company\s*:\s*", "", content, flags=re.I).strip())
            for raw, content in block
            if re.match(r"^company\s*:", content, re.I)
        ),
        None,
    )

    company = None
    at_match = re.search(r"\s+(?:at|@)\s+(.+)$", title, re.IGNORECASE)
    if at_match:
        company = DATE_RANGE.sub("", at_match.group(1)).strip(" ,;|-–—")
        title = title[: at_match.start()].strip(" ,;|-–—")
    else:
        separator = re.search(r"\s+(?:\||—|–)\s+", title)
        if separator:
            remainder = title[separator.end() :].strip()
            title = title[: separator.start()].strip()
            company = DATE_RANGE.sub("", remainder).strip(" ,;|-–—") or None
    if company_line:
        company = company_line[1]

    description_lines = [
        (raw, content)
        for raw, content in block
        if content
        and (raw, content) != title_line
        and (raw, content) != date_line
        and (raw, content) != company_line
    ]
    evidence_lines = [title_line, *description_lines]
    if date_line:
        evidence_lines.append(date_line)
    if company_line:
        evidence_lines.append(company_line)
    return ResumeExperience(
        title=DATE_RANGE.sub("", title).strip(" ,;|-–—") or raw_title,
        company=company,
        experience_type=(
            "internship"
            if internship or "intern" in raw_title.casefold()
            else "employment"
        ),
        start_date=date_match.group("start") if date_match else None,
        end_date=date_match.group("end") if date_match else None,
        description=" ".join(content for _, content in description_lines) or None,
        technologies=extract_known_technical_skills(block),
        evidence=evidence(evidence_lines, title),
    )


def extract_experience(
    sections: dict[str, list[Line]],
) -> list[ResumeExperience]:
    result: list[ResumeExperience] = []
    for section, internship in (("experience", False), ("internship", True)):
        blocks = entry_blocks(
            sections.get(section, []),
            lambda content: _is_role(content) and not _YEARS.search(content),
        )
        for block in blocks:
            item = _parse_block(block, internship=internship)
            if item:
                result.append(item)
    return result
