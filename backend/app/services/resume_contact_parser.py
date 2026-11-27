import re

from app.schemas.resumes import EvidenceValue, UncertainField
from app.services.resume_parser_common import Line, evidence

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[\s().-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?"
    r"\d{3,4}[\s.-]?\d{3,4}(?:\s*(?:ext\.?|x)\s*\d+)?(?!\w)",
    re.IGNORECASE,
)
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
_NON_NAME_WORDS = {"candidate", "curriculum", "demo", "profile", "resume", "synthetic", "vitae"}


def _person_name(value: str) -> str | None:
    candidate = re.sub(r"\s+", " ", value.split("|", 1)[0].strip(" ,;:-"))
    words = candidate.split()
    if not 2 <= len(words) <= 4 or len(candidate) > 80 or "," in candidate:
        return None
    if any(word.casefold().strip(".,") in _NON_NAME_WORDS for word in words):
        return None
    if any(re.search(r"\d", word) for word in words):
        return None
    if any(word.casefold().strip(".,") in _ROLE_WORDS for word in words):
        return None
    if not all(re.fullmatch(r"[A-Za-z][A-Za-z'.-]*|[A-Z]\.", word) for word in words):
        return None
    return candidate


def extract_contact(
    sections: dict[str, list[Line]],
) -> tuple[
    EvidenceValue | None,
    EvidenceValue | None,
    EvidenceValue | None,
    list[UncertainField],
]:
    contact = [
        (raw, content)
        for section in ("preamble", "contact")
        for raw, content in sections.get(section, [])
        if content
    ]
    uncertain: list[UncertainField] = []
    labelled_name = next(
        (
            (raw, match.group(1).strip())
            for raw, content in contact
            if (match := re.match(r"^(?:full\s+)?name\s*[:\-]\s*(.+)$", content, re.I))
        ),
        None,
    )
    name_candidates = [labelled_name] if labelled_name else []
    if not labelled_name:
        for raw, content in contact[:12]:
            if _EMAIL.search(content) or _PHONE.search(content):
                continue
            candidate = _person_name(content)
            if candidate:
                name_candidates.append((raw, candidate))

    name = None
    unique_names = {value.casefold() for _, value in name_candidates}
    if len(unique_names) == 1:
        raw, value = name_candidates[0]
        name = EvidenceValue(value=value, evidence=evidence([(raw, value)], value))
    elif unique_names:
        uncertain.append(
            UncertainField(
                field="full_name",
                value="; ".join(value for _, value in name_candidates[:4]),
                reason="Multiple plausible names appear in the contact section.",
            )
        )

    email_matches = [
        (raw, match.group(0))
        for raw, content in contact
        for match in _EMAIL.finditer(content)
    ]
    phone_matches = []
    for raw, content in contact:
        for match in _PHONE.finditer(content):
            value = match.group(0).strip(" .,-")
            if 7 <= sum(character.isdigit() for character in value) <= 15:
                phone_matches.append((raw, value))

    def unique(matches: list[tuple[str, str]]) -> list[tuple[str, str]]:
        result: dict[str, tuple[str, str]] = {}
        for raw, value in matches:
            result.setdefault(re.sub(r"\D", "", value) or value.casefold(), (raw, value))
        return list(result.values())

    email_matches = unique(email_matches)
    phone_matches = unique(phone_matches)
    email = (
        EvidenceValue(value=email_matches[0][1], evidence=evidence([email_matches[0]]))
        if email_matches
        else None
    )
    phone = (
        EvidenceValue(value=phone_matches[0][1], evidence=evidence([phone_matches[0]]))
        if phone_matches
        else None
    )
    for field, matches in (("email", email_matches), ("phone", phone_matches)):
        if len(matches) > 1:
            uncertain.append(
                UncertainField(
                    field=field,
                    value="; ".join(value for _, value in matches[:4]),
                    reason=f"Multiple {field} values appear in the contact section.",
                )
            )
    return name, email, phone, uncertain
