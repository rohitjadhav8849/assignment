from app.schemas.resumes import ResumeExtraction
from app.services.resume_certifications_parser import extract_certifications
from app.services.resume_contact_parser import extract_contact
from app.services.resume_education_parser import extract_education
from app.services.resume_experience_parser import (
    extract_experience,
    extract_experience_years,
)
from app.services.resume_parser_common import split_sections
from app.services.resume_projects_parser import extract_projects
from app.services.resume_skills_parser import extract_skills


def parse_resume_text(text: str) -> ResumeExtraction:
    """Parse explicit resume facts locally and keep their source evidence."""
    sections = split_sections(text)
    all_lines = [line for section in sections.values() for line in section]
    full_name, email, phone, uncertain_fields = extract_contact(sections)
    return ResumeExtraction(
        full_name=full_name,
        email=email,
        phone=phone,
        total_experience_years=extract_experience_years(all_lines),
        skills=extract_skills(sections),
        education=extract_education(sections),
        work_experience=extract_experience(sections),
        projects=extract_projects(sections),
        certifications=extract_certifications(sections),
        uncertain_fields=uncertain_fields,
    )
