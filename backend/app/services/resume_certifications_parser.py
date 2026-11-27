import re

from app.schemas.resumes import ResumeCertification
from app.services.resume_parser_common import Line, evidence, split_blocks

_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def extract_certifications(
    sections: dict[str, list[Line]],
) -> list[ResumeCertification]:
    result: list[ResumeCertification] = []
    for block in split_blocks(sections.get("certifications", [])):
        if not block:
            continue
        raw, content = block[0]
        name = re.sub(
            r"^(?:certification|certificate)\s*:\s*",
            "",
            content,
            flags=re.IGNORECASE,
        )
        issuer = re.search(r"\b(?:issued|certified)\s+by\s+(.+)$", name, re.I)
        date = _YEAR.search(content)
        result.append(
            ResumeCertification(
                name=name,
                issuer=issuer.group(1).strip(" ,;") if issuer else None,
                date=date.group(0) if date else None,
                evidence=evidence([*block, (raw, content)], name),
            )
        )
    return result
