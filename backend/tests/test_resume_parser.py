import json
from pathlib import Path

from app.services.resume_evaluation import evaluate_prediction, summarize_evaluation
from app.services.resume_parser import parse_resume_text
from app.services.resume_validation import validate_extraction


FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "resume_evaluation.json"
)


def _fixtures() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_parser_handles_standard_sections_and_verifiable_evidence() -> None:
    example = _fixtures()[0]
    extraction = parse_resume_text(example["text"])

    assert extraction.full_name.value == "Alex Morgan"
    assert extraction.email.value == "alex.morgan@example.test"
    assert extraction.phone is not None
    assert extraction.total_experience_years.value == 4
    assert extraction.work_experience[0].title == "Backend Engineer"
    assert extraction.education[0].degree == "Bachelor of Science in Computer Science"
    assert extraction.projects[0].name == "Job Board API"
    assert extraction.certifications[0].name == "AWS Certified Developer"
    report = validate_extraction(extraction, example["text"])
    assert report["unsupported_claim_count"] == 0


def test_parser_handles_alternate_headings_and_internships() -> None:
    example = _fixtures()[1]
    extraction = parse_resume_text(example["text"])

    assert extraction.full_name.value == "Taylor Lee"
    assert extraction.work_experience[0].experience_type == "internship"
    assert extraction.work_experience[0].title == "Platform Engineering Intern"
    assert extraction.work_experience[0].company == "Demo Cloud"
    assert extraction.projects[0].name == "Weather Dashboard"
    assert {skill.name for skill in extraction.skills} >= {
        "Java",
        "Spring Boot",
        "SQL",
    }
    assert "React" not in {skill.name for skill in extraction.skills}
    assert {skill.name for skill in extraction.projects[0].technologies} >= {
        "React",
        "JavaScript",
    }


def test_skills_are_deduplicated_and_project_technologies_stay_project_level() -> None:
    example = next(
        item
        for item in _fixtures()
        if item["id"] == "synthetic-duplicate-skills-and-projects"
    )
    extraction = parse_resume_text(example["text"])

    skills = {skill.name: skill for skill in extraction.skills}
    assert set(skills) == {"Node.js", "PostgreSQL", "Python"}
    assert all(len(skill.evidence) == 1 for skill in skills.values())
    snippets = [skill.evidence[0].snippet for skill in skills.values()]
    assert len(snippets) == len(set(snippets))
    assert all(snippet in example["text"] for snippet in snippets)
    assert all(len(snippet) <= 40 for snippet in snippets)
    assert "React" not in skills
    assert "FastAPI" not in skills

    assert [project.name for project in extraction.projects] == [
        "Weather API",
        "Inventory Dashboard",
    ]
    assert {skill.name for skill in extraction.projects[0].technologies} == {
        "React",
        "FastAPI",
    }
    assert all(
        project.description and len(project.description) <= 500
        for project in extraction.projects
    )
    assert all(
        "Technologies:" not in item.snippet
        for project in extraction.projects
        for item in project.evidence
    )
    assert all(
        item.snippet in example["text"]
        for project in extraction.projects
        for technology in project.technologies
        for item in technology.evidence
    )


def test_missing_name_does_not_hide_an_internship() -> None:
    example = next(
        item
        for item in _fixtures()
        if item["id"] == "synthetic-missing-name-internship"
    )
    extraction = parse_resume_text(example["text"])

    assert extraction.full_name is None
    assert extraction.email.value == "intern@example.test"
    assert extraction.total_experience_years is None
    assert len(extraction.work_experience) == 1
    assert extraction.work_experience[0].experience_type == "internship"
    assert extraction.work_experience[0].title == "Data Analyst Intern"


def test_sentences_and_project_mentions_do_not_create_profile_skills() -> None:
    extraction = parse_resume_text(
        "Skills\n"
        "Built and led cross-functional programs for internal users.\n\n"
        "Projects\n"
        "Portfolio Site\n"
        "Built with React and Node.js.\n"
    )

    assert extraction.skills == []
    assert {skill.name for skill in extraction.projects[0].technologies} == {
        "React",
        "Node.js",
    }


def test_employment_and_internship_entries_are_classified_separately() -> None:
    extraction = parse_resume_text(
        "Work Experience\n"
        "Software Engineer at Example Corp | 2022–2024\n"
        "Built backend services.\n\n"
        "Internship\n"
        "Data Analyst Intern at Demo Lab | Jun 2021 - Aug 2021\n"
        "Prepared reports.\n"
    )

    assert [item.experience_type for item in extraction.work_experience] == [
        "employment",
        "internship",
    ]
    assert [item.title for item in extraction.work_experience] == [
        "Software Engineer",
        "Data Analyst Intern",
    ]
    assert extraction.total_experience_years is None


def test_parser_leaves_missing_sections_empty() -> None:
    extraction = parse_resume_text(
        "Jordan Kim\nEmail: jordan.kim@example.test\n\nSkills\nPython"
    )

    assert extraction.full_name.value == "Jordan Kim"
    assert extraction.email.value == "jordan.kim@example.test"
    assert extraction.phone is None
    assert extraction.education == []
    assert extraction.work_experience == []
    assert extraction.projects == []
    assert extraction.certifications == []


def test_parser_flags_ambiguous_names_instead_of_choosing_one() -> None:
    extraction = parse_resume_text(
        "SYNTHETIC RESUME\nAlex Morgan\nTaylor Lee\nalex@example.test\nSkills: Python"
    )

    assert extraction.full_name is None
    assert any(item.field == "full_name" for item in extraction.uncertain_fields)


def test_offline_evaluation_reports_field_and_evidence_metrics() -> None:
    records = []
    for example in _fixtures():
        extraction = parse_resume_text(example["text"])
        records.append(
            evaluate_prediction(example["expected"], extraction, example["text"])
        )

    metrics = summarize_evaluation(records)

    assert metrics["resume_count"] == len(_fixtures())
    assert 0.0 <= metrics["skill_precision"] <= 1.0
    assert 0.0 <= metrics["skill_recall"] <= 1.0
    assert 0.0 <= metrics["skill_f1"] <= 1.0
    assert {"full_name", "email", "phone", "skills"} <= set(
        metrics["field_metrics"]
    )
    assert 0.0 <= metrics["contact_information_accuracy"] <= 1.0
    assert metrics["structured_output_validation_failure_rate"] == 0.0
    assert metrics["unsupported_claim_rate"] == 0.0
