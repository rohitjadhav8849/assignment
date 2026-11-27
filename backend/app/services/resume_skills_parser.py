import re
from collections.abc import Iterable
from typing import Literal

from app.schemas.resumes import EvidenceSnippet, ResumeSkill
from app.services.resume_parser_common import Line

SkillCategory = Literal["technical", "non_technical"]

_TECHNICAL_SKILLS: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "Java": ("java",),
    "JavaScript": ("javascript",),
    "TypeScript": ("typescript",),
    "C#": ("c#", "c sharp"),
    "C++": ("c++", "cpp"),
    "Ruby": ("ruby",),
    "PHP": ("php",),
    "Swift": ("swift",),
    "Kotlin": ("kotlin",),
    "SQL": ("sql",),
    "HTML": ("html",),
    "CSS": ("css",),
    "React": ("react", "react.js", "reactjs"),
    "Next.js": ("next.js", "nextjs"),
    "Vue.js": ("vue.js", "vuejs"),
    "Angular": ("angular",),
    "Node.js": ("node.js", "nodejs", "node js"),
    "Express": ("express", "express.js"),
    "FastAPI": ("fastapi",),
    "Flask": ("flask",),
    "Django": ("django",),
    "Spring Boot": ("spring boot",),
    ".NET": (".net", "dotnet"),
    "PostgreSQL": ("postgresql", "postgres"),
    "MySQL": ("mysql",),
    "SQLite": ("sqlite",),
    "MongoDB": ("mongodb", "mongo db"),
    "Redis": ("redis",),
    "Elasticsearch": ("elasticsearch", "elastic search"),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure", "microsoft azure"),
    "GCP": ("gcp", "google cloud platform"),
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "Terraform": ("terraform",),
    "Jenkins": ("jenkins",),
    "Git": ("git",),
    "Linux": ("linux",),
    "GraphQL": ("graphql",),
    "Kafka": ("kafka", "apache kafka"),
    "RabbitMQ": ("rabbitmq",),
    "Airflow": ("airflow", "apache airflow"),
    "Spark": ("spark", "apache spark"),
    "Snowflake": ("snowflake",),
    "Databricks": ("databricks",),
    "Pandas": ("pandas",),
    "NumPy": ("numpy",),
    "scikit-learn": ("scikit-learn", "scikit learn"),
    "TensorFlow": ("tensorflow",),
    "PyTorch": ("pytorch",),
    "Power BI": ("power bi",),
    "Tableau": ("tableau",),
    "Excel": ("excel", "microsoft excel"),
}
_SOFT_SKILLS: dict[str, tuple[str, ...]] = {
    "Communication": ("communication",),
    "Leadership": ("leadership",),
    "Problem solving": ("problem solving", "problem-solving"),
    "Teamwork": ("teamwork", "team work"),
    "Project management": ("project management",),
    "Agile": ("agile",),
    "Collaboration": ("collaboration",),
    "Mentoring": ("mentoring",),
    "Time management": ("time management",),
}
_SKILL_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


def _pattern(alias: str) -> re.Pattern[str]:
    if alias not in _SKILL_PATTERN_CACHE:
        _SKILL_PATTERN_CACHE[alias] = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
    return _SKILL_PATTERN_CACHE[alias]


def _known_skills(
    lines: Iterable[Line],
    *,
    include_soft: bool = False,
) -> dict[str, tuple[str, SkillCategory, list[str]]]:
    facts: dict[str, tuple[str, SkillCategory, list[str]]] = {}
    vocabulary: list[tuple[SkillCategory, dict[str, tuple[str, ...]]]] = [
        ("technical", _TECHNICAL_SKILLS)
    ]
    if include_soft:
        vocabulary.append(("non_technical", _SOFT_SKILLS))
    for _, content in lines:
        line_matches: list[tuple[int, str, SkillCategory, str]] = []
        for category, skills in vocabulary:
            for name, aliases in skills.items():
                for alias in aliases:
                    match = _pattern(alias).search(content)
                    if match:
                        line_matches.append(
                            (match.start(), name, category, match.group(0))
                        )
                        break
        for _, name, category, snippet in sorted(line_matches):
            key = name.casefold()
            fact = facts.setdefault(key, (name, category, []))
            if not fact[2]:
                fact[2].append(snippet)
    return facts


def extract_known_technical_skills(lines: Iterable[Line]) -> list[ResumeSkill]:
    facts = _known_skills(lines)
    return [
        ResumeSkill(
            name=name,
            category=category,
            evidence=[EvidenceSnippet(snippet=snippet) for snippet in snippets],
        )
        for name, category, snippets in facts.values()
    ]


def extract_skills(
    sections: dict[str, list[Line]],
) -> list[ResumeSkill]:
    declared_skill_lines = [
        *sections.get("skills", []),
        *sections.get("soft_skills", []),
    ]
    facts = _known_skills(declared_skill_lines, include_soft=True)
    return [
        ResumeSkill(
            name=name,
            category=category,
            evidence=[EvidenceSnippet(snippet=snippet) for snippet in snippets],
        )
        for name, category, snippets in facts.values()
    ]
