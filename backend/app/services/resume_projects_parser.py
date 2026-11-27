import re

from app.schemas.resumes import ResumeProject
from app.services.resume_parser_common import Line, evidence
from app.services.resume_skills_parser import extract_known_technical_skills

_PROJECT_LABEL = re.compile(r"^project(?:\s+(?:name|title))?\s*:\s*(.+)$", re.I)
_TECHNOLOGIES_LABEL = re.compile(
    r"^(?:technologies|technology|tech(?:nologies)? stack|tech|tools)\s*[:\-]",
    re.I,
)
_DESCRIPTION_LABEL = re.compile(r"^(?:description|summary)\s*:\s*", re.I)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_MAX_DESCRIPTION_CHARS = 500


def _project_blocks(lines: list[Line]) -> list[list[Line]]:
    blocks: list[list[Line]] = []
    current: list[Line] = []
    for raw, content in lines:
        if not content:
            if current:
                blocks.append(current)
                current = []
            continue
        if _PROJECT_LABEL.match(content) and current:
            blocks.append(current)
            current = []
        current.append((raw, content))
    if current:
        blocks.append(current)
    return blocks


def _description(lines: list[Line]) -> str | None:
    sentences: list[str] = []
    seen: set[str] = set()
    for _, content in lines:
        if _TECHNOLOGIES_LABEL.match(content):
            continue
        cleaned = _DESCRIPTION_LABEL.sub("", content).strip()
        for sentence in _SENTENCE_BREAK.split(cleaned):
            sentence = sentence.strip()
            key = re.sub(r"\s+", " ", sentence).casefold()
            if sentence and key not in seen:
                sentences.append(sentence)
                seen.add(key)
            if len(sentences) == 3:
                break
        if len(sentences) == 3:
            break
    result = " ".join(sentences)
    if len(result) > _MAX_DESCRIPTION_CHARS:
        result = result[:_MAX_DESCRIPTION_CHARS].rsplit(" ", 1)[0].rstrip(" ,;:")
    return result or None

def extract_projects(sections: dict[str, list[Line]]) -> list[ResumeProject]:
    result: list[ResumeProject] = []
    for block in _project_blocks(sections.get("projects", [])):
        if not block:
            continue
        _, first = block[0]
        explicit = _PROJECT_LABEL.match(first)
        name = explicit.group(1).strip() if explicit else first
        description_lines = block[1:]
        detail_lines = [
            line for line in description_lines if not _TECHNOLOGIES_LABEL.match(line[1])
        ]
        result.append(
            ResumeProject(
                name=name[:200],
                description=_description(detail_lines),
                technologies=extract_known_technical_skills(block),
                evidence=evidence(
                    [block[0], *detail_lines[:3]],
                    name,
                ),
            )
        )
    return result
