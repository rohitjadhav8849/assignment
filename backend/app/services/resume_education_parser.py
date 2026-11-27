import re

from app.schemas.resumes import ResumeEducation
from app.services.resume_parser_common import (
    DATE_RANGE,
    Line,
    evidence,
    split_blocks,
)

_DEGREE = re.compile(
    r"\b(?:bachelor(?:'s)?|master(?:'s)?|associate(?:'s)?|doctorate|"
    r"ph\.?\s*d\.?|mba|b\.?\s?sc\.?|b\.?\s?a\.?|m\.?\s?sc\.?|m\.?\s?a\.?|"
    r"b\.?\s?tech\.?|m\.?\s?tech\.?|b\.?\s?e\.?|m\.?\s?e\.?|diploma|"
    r"high school)\b",
    re.IGNORECASE,
)
_INSTITUTION = re.compile(
    r"\b(university|college|institute|school|academy|polytechnic)\b",
    re.IGNORECASE,
)


def extract_education(sections: dict[str, list[Line]]) -> list[ResumeEducation]:
    result: list[ResumeEducation] = []
    for block in split_blocks(sections.get("education", [])):
        degrees = [(raw, content) for raw, content in block if _DEGREE.search(content)]
        institutions = [
            (raw, content) for raw, content in block if _INSTITUTION.search(content)
        ]
        date_line = next(
            ((raw, content) for raw, content in block if DATE_RANGE.search(content)),
            None,
        )
        dates = DATE_RANGE.search(date_line[1]) if date_line else None
        if not degrees and not institutions:
            continue
        for degree_line in degrees or institutions[:1]:
            raw, content = degree_line
            institution = next(
                (line for line in institutions if line != degree_line),
                degree_line if _INSTITUTION.search(content) else None,
            )
            field_match = re.search(
                r"\bin\s+([A-Z][A-Za-z &/+-]{1,80})", content
            )
            snippets = [degree_line]
            if institution:
                snippets.append(institution)
            if date_line:
                snippets.append(date_line)
            result.append(
                ResumeEducation(
                    institution=institution[1] if institution else None,
                    degree=content if _DEGREE.search(content) else None,
                    field_of_study=(
                        field_match.group(1).strip(" ,.;") if field_match else None
                    ),
                    start_date=dates.group("start") if dates else None,
                    end_date=dates.group("end") if dates else None,
                    evidence=evidence(snippets),
                )
            )
    return result
