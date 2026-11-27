import re
from collections import defaultdict
from collections.abc import Callable, Iterable

from app.schemas.resumes import EvidenceSnippet

Line = tuple[str, str]

SECTION_ALIASES = {
    "contact": {"contact", "contact information", "personal information"},
    "skills": {
        "skills",
        "technical skills",
        "core skills",
        "core competencies",
        "technical competencies",
        "technologies",
        "tools and technologies",
        "technical expertise",
        "key skills",
        "tech stack",
        "technical toolkit",
        "tools",
        "technology stack",
    },
    "soft_skills": {"soft skills", "interpersonal skills"},
    "education": {
        "education",
        "academic background",
        "education and training",
        "qualifications",
    },
    "experience": {
        "experience",
        "work experience",
        "work experience and internships",
        "work experience internships",
        "experience and internships",
        "professional experience",
        "employment history",
        "work history",
        "career history",
    },
    "internship": {"internship", "internships", "internship experience"},
    "projects": {"projects", "personal projects", "academic projects"},
    "certifications": {
        "certifications",
        "certificates",
        "licenses",
        "licenses and certifications",
    },
}
_HEADING_LOOKUP = {
    re.sub(r"[^a-z0-9]+", " ", alias.casefold()).strip(): section
    for section, aliases in SECTION_ALIASES.items()
    for alias in aliases
}
_BULLET_PREFIX = re.compile(r"^\s*(?:[-*•▪◦‣]|\d+[.)])\s*")
_PROJECT_TECH_LINE = re.compile(
    r"^\s*(?:technologies|technology|tech(?:\s+stack)?|tools)\s*[:|—–-]",
    re.IGNORECASE,
)
_DATE_PART = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\.?\s+\d{4}|\d{4}"
)
DATE_RANGE = re.compile(
    rf"(?P<start>{_DATE_PART})\s*(?:-|–|—|to)\s*"
    rf"(?P<end>{_DATE_PART}|present|current|now)",
    re.IGNORECASE,
)


def clean_line(value: str) -> str:
    return _BULLET_PREFIX.sub("", value).strip()


def _heading(value: str) -> tuple[str, str] | None:
    cleaned = clean_line(value)
    candidates = [(cleaned, "")]
    for separator in (":", "|", "—", "–", " - "):
        if separator in cleaned:
            label, inline = cleaned.split(separator, 1)
            candidates.append((label, inline.strip()))
    for label, inline in candidates:
        normalized = re.sub(r"[^a-z0-9]+", " ", label.casefold()).strip()
        if normalized in _HEADING_LOOKUP:
            return _HEADING_LOOKUP[normalized], inline
    return None


def split_sections(text: str) -> dict[str, list[Line]]:
    sections: dict[str, list[Line]] = defaultdict(list)
    current = "preamble"
    for raw in text.splitlines():
        found = _heading(raw)
        if (
            current == "projects"
            and found
            and found[0] == "skills"
            and _PROJECT_TECH_LINE.match(raw)
        ):
            sections[current].append((raw, clean_line(raw)))
            continue
        if found:
            current, inline = found
            if inline:
                sections[current].append((raw, clean_line(inline)))
            continue
        sections[current].append((raw, clean_line(raw)))
    return sections


def evidence(lines: Iterable[Line], value: str | None = None) -> list[EvidenceSnippet]:
    result: list[EvidenceSnippet] = []
    seen: set[str] = set()
    for raw, _ in lines:
        snippet = raw.strip()
        if len(snippet) > 600:
            index = snippet.casefold().find(value.casefold()) if value else -1
            start = max(0, min(index - 200, len(snippet) - 600)) if index >= 0 else 0
            snippet = snippet[start : start + 600]
        key = re.sub(r"\s+", " ", snippet).casefold()
        if snippet and key not in seen:
            result.append(EvidenceSnippet(snippet=snippet))
            seen.add(key)
        if len(result) == 10:
            break
    return result


def split_blocks(lines: list[Line]) -> list[list[Line]]:
    blocks: list[list[Line]] = []
    current: list[Line] = []
    for line in lines:
        if not line[1]:
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def entry_blocks(
    lines: list[Line],
    starts_entry: Callable[[str], bool],
) -> list[list[Line]]:
    blocks: list[list[Line]] = []
    current: list[Line] = []
    for line in lines:
        raw, content = line
        if not content:
            if current:
                blocks.append(current)
                current = []
            continue
        if starts_entry(content) and current:
            blocks.append(current)
            current = []
        current.append((raw, content))
    if current:
        blocks.append(current)
    return blocks
