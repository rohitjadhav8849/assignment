import argparse

from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

from app.database.session import engine
from app.models import Base, Job

COMPANIES = [
    "Aster Grove Labs",
    "Bluefern Systems",
    "Cedarline Software",
    "Daybreak Analytics",
    "Everwell Digital",
    "Fieldstone Cloud",
    "Greenbridge Technology",
    "Harborlight Data",
    "Indigo Current",
    "Juniper Vale Systems",
    "Keystone Orbit",
    "Larkspur Networks",
    "Maplewave Engineering",
    "Northwind Studio",
    "Oak & Ember Technology",
    "Pinecone Harbor",
    "Quiet River Labs",
    "Redwood Signal",
    "Silverline Works",
    "Tandem Meadow",
    "Umber Peak Digital",
    "Valleycraft Software",
    "Westward Field",
    "Yellowfin Logic",
    "Zephyr Ridge Labs",
]

LOCATIONS = [
    "New York, NY",
    "Austin, TX",
    "Seattle, WA",
    "Chicago, IL",
    "Denver, CO",
    "Toronto, ON",
    "Boston, MA",
    "Portland, OR",
    "Atlanta, GA",
    "San Francisco, CA",
]

ROLE_TEMPLATES = [
    {
        "key": "backend",
        "category": "Backend Engineering",
        "title": "Backend Engineer",
        "required": ["Python", "REST APIs", "PostgreSQL", "Docker"],
        "preferred": ["FastAPI", "Redis", "AWS", "Kubernetes"],
        "responsibilities": [
            "Design and maintain versioned services and APIs.",
            "Improve database performance, reliability, and observability.",
            "Partner with product and frontend teams to deliver user-facing features.",
        ],
        "description": "Build dependable backend services for customer-facing products. You will work with a collaborative engineering team to design APIs, evolve data models, and improve production reliability.",
        "min_years": 2,
        "max_years": 7,
    },
    {
        "key": "software",
        "category": "Software Engineering",
        "title": "Software Engineer",
        "required": ["Python", "JavaScript", "Git", "SQL"],
        "preferred": ["TypeScript", "React", "Docker", "AWS"],
        "responsibilities": [
            "Deliver well-tested product features across the application stack.",
            "Review code and contribute to technical design discussions.",
            "Improve development tooling and engineering documentation.",
        ],
        "description": "Help deliver thoughtful software for a growing product team. The role balances feature work, code quality, and close collaboration with design and product partners.",
        "min_years": 1,
        "max_years": 6,
    },
    {
        "key": "ml",
        "category": "AI / Machine Learning",
        "title": "Machine Learning Engineer",
        "required": ["Python", "PyTorch", "SQL", "Model evaluation"],
        "preferred": ["scikit-learn", "MLflow", "AWS", "Kubernetes"],
        "responsibilities": [
            "Build and evaluate machine-learning models for product workflows.",
            "Develop reproducible training and inference pipelines.",
            "Work with data and product teams to define measurable outcomes.",
        ],
        "description": "Turn applied machine-learning research into reliable product capabilities. You will collaborate across engineering and analytics to evaluate models and ship maintainable inference services.",
        "min_years": 2,
        "max_years": 8,
    },
    {
        "key": "data",
        "category": "Data Engineering",
        "title": "Data Engineer",
        "required": ["Python", "SQL", "Apache Spark", "Airflow"],
        "preferred": ["dbt", "Snowflake", "Kafka", "AWS"],
        "responsibilities": [
            "Build dependable batch and streaming data pipelines.",
            "Improve data quality checks and warehouse performance.",
            "Partner with analysts to make trusted datasets easier to use.",
        ],
        "description": "Create well-documented data foundations for product and business teams. You will operate pipelines, improve data quality, and make analytical datasets dependable.",
        "min_years": 2,
        "max_years": 7,
    },
    {
        "key": "platform",
        "category": "Platform Engineering",
        "title": "Platform Engineer",
        "required": ["Kubernetes", "Docker", "Terraform", "Linux"],
        "preferred": ["AWS", "Go", "Prometheus", "GitHub Actions"],
        "responsibilities": [
            "Build paved paths that make product teams more effective.",
            "Automate infrastructure and improve deployment safety.",
            "Improve service observability and operational documentation.",
        ],
        "description": "Help engineering teams ship reliably by improving shared infrastructure and developer tooling. The team values practical automation, clear ownership, and sustainable operations.",
        "min_years": 3,
        "max_years": 9,
    },
    {
        "key": "fullstack",
        "category": "Software Engineering",
        "title": "Full Stack Engineer",
        "required": ["JavaScript", "React", "Node.js", "SQL"],
        "preferred": ["TypeScript", "Python", "PostgreSQL", "AWS"],
        "responsibilities": [
            "Build accessible user interfaces and supporting APIs.",
            "Work with design to refine product workflows.",
            "Maintain automated tests and improve application performance.",
        ],
        "description": "Join a small product team building a clear, accessible web experience. You will contribute across the frontend and backend, with room to deepen expertise in either area.",
        "min_years": 2,
        "max_years": 7,
    },
    {
        "key": "ai",
        "category": "AI / Machine Learning",
        "title": "Applied AI Engineer",
        "required": ["Python", "Machine learning", "REST APIs", "SQL"],
        "preferred": ["PyTorch", "NLP", "Vector databases", "AWS"],
        "responsibilities": [
            "Prototype and productionize applied AI capabilities.",
            "Evaluate quality and reliability against representative examples.",
            "Design service interfaces with clear monitoring and fallback behavior.",
        ],
        "description": "Explore practical AI applications and help bring useful capabilities into production. You will work with product engineers to test assumptions and measure system quality.",
        "min_years": 2,
        "max_years": 8,
    },
    {
        "key": "analytics",
        "category": "Data Engineering",
        "title": "Analytics Engineer",
        "required": ["SQL", "dbt", "Data modeling", "Git"],
        "preferred": ["Snowflake", "Python", "Airflow", "Looker"],
        "responsibilities": [
            "Model clean, tested datasets for reporting and analysis.",
            "Establish shared metric definitions with business partners.",
            "Improve documentation and the reliability of analytics workflows.",
        ],
        "description": "Make organizational data easier to trust and understand. You will bridge data engineering and analytics through careful modeling, testing, and clear documentation.",
        "min_years": 2,
        "max_years": 7,
    },
    {
        "key": "mlops",
        "category": "AI / Machine Learning",
        "title": "MLOps Engineer",
        "required": ["Python", "Docker", "Kubernetes", "MLflow"],
        "preferred": ["PyTorch", "Terraform", "Prometheus", "AWS"],
        "responsibilities": [
            "Maintain reproducible model training and release workflows.",
            "Build monitoring for model services and data quality.",
            "Partner with researchers to improve deployment practices.",
        ],
        "description": "Build the systems that help machine-learning teams develop and operate models responsibly. The role focuses on reproducibility, deployment, monitoring, and practical tooling.",
        "min_years": 3,
        "max_years": 9,
    },
    {
        "key": "qa",
        "category": "Quality Engineering",
        "title": "Quality Automation Engineer",
        "required": ["Python", "Playwright", "API testing", "Git"],
        "preferred": ["TypeScript", "Docker", "CI/CD", "PostgreSQL"],
        "responsibilities": [
            "Develop maintainable automated checks for product workflows.",
            "Work with engineers to prevent regressions earlier in delivery.",
            "Improve test reporting and identify high-value coverage gaps.",
        ],
        "description": "Help product teams release confidently through thoughtful automation and clear quality signals. You will collaborate across the lifecycle rather than treating testing as a final gate.",
        "min_years": 2,
        "max_years": 7,
    },
    {
        "key": "security",
        "category": "Security Engineering",
        "title": "Product Security Engineer",
        "required": ["Python", "OWASP", "Linux", "Cloud security"],
        "preferred": ["AWS", "Terraform", "Kubernetes", "Go"],
        "responsibilities": [
            "Partner with teams to make secure design a normal part of delivery.",
            "Improve application security reviews and developer guidance.",
            "Help prioritize remediations with clear risk context.",
        ],
        "description": "Work alongside product engineers to improve application and cloud security. The focus is pragmatic risk reduction, useful tooling, and constructive collaboration.",
        "min_years": 3,
        "max_years": 9,
    },
    {
        "key": "cloud",
        "category": "Cloud Infrastructure",
        "title": "Cloud Infrastructure Engineer",
        "required": ["AWS", "Terraform", "Linux", "Networking"],
        "preferred": ["Kubernetes", "Python", "Prometheus", "GitHub Actions"],
        "responsibilities": [
            "Design and maintain secure cloud infrastructure.",
            "Improve infrastructure-as-code modules and operational runbooks.",
            "Help teams manage reliability and cloud costs responsibly.",
        ],
        "description": "Support product teams with stable, well-documented cloud infrastructure. You will improve automation, reliability practices, and the clarity of operational ownership.",
        "min_years": 2,
        "max_years": 8,
    },
]

LEVELS = [
    ("Associate", 0),
    ("", 0),
    ("Senior", 2),
]
WORK_MODES = ["Remote", "Hybrid", "On-site"]
EMPLOYMENT_TYPES = ["Full-time", "Full-time", "Contract"]


def build_jobs(count: int = 300) -> list[dict]:
    jobs = []
    for role_index, role in enumerate(ROLE_TEMPLATES):
        for company_index, company in enumerate(COMPANIES):
            if len(jobs) >= count:
                return jobs
            level, experience_bonus = LEVELS[company_index % len(LEVELS)]
            minimum = role["min_years"] + experience_bonus
            maximum = role["max_years"] + experience_bonus
            work_mode = WORK_MODES[(company_index + role_index) % len(WORK_MODES)]
            salary_min = 75000 + ((company_index * 1700 + role_index * 4200) % 85000)
            jobs.append(
                {
                    "seed_key": f"{role['key']}:{company_index:02d}",
                    "title": f"{level} {role['title']}".strip(),
                    "company": f"{company} (Demo)",
                    "category": role["category"],
                    "description": (
                        f"{role['description']} This is a synthetic demonstration "
                        f"listing for {company} (Demo), created only for the "
                        "Job Intelligence Platform prototype."
                    ),
                    "responsibilities": list(role["responsibilities"]),
                    "required_skills": list(role["required"]),
                    "preferred_skills": list(role["preferred"]),
                    "min_experience_years": minimum,
                    "max_experience_years": maximum,
                    "location": LOCATIONS[(company_index * 3 + role_index) % len(LOCATIONS)],
                    "work_mode": work_mode,
                    "employment_type": EMPLOYMENT_TYPES[
                        (company_index + role_index) % len(EMPLOYMENT_TYPES)
                    ],
                    "salary_min": salary_min,
                    "salary_max": salary_min + 35000,
                    "salary_currency": "USD",
                    "is_synthetic": True,
                    "data_source": "SYNTHETIC DEMO",
                }
            )
    return jobs


def seed_jobs(count: int = 300) -> tuple[int, int]:
    if count < 1:
        raise ValueError("Job count must be at least one.")
    if count > len(ROLE_TEMPLATES) * len(COMPANIES):
        raise ValueError(
            f"At most {len(ROLE_TEMPLATES) * len(COMPANIES)} synthetic jobs are available."
        )
    return seed_jobs_into(engine, count)


def seed_jobs_into(target_engine: Engine, count: int = 300) -> tuple[int, int]:
    if count < 1 or count > len(ROLE_TEMPLATES) * len(COMPANIES):
        raise ValueError("Requested job count is outside the available synthetic dataset.")
    Base.metadata.create_all(bind=target_engine)
    session_factory = sessionmaker(bind=target_engine, autoflush=False, autocommit=False)
    records = build_jobs(count)
    inserted = 0
    updated = 0
    with session_factory() as session:
        for record in records:
            existing = session.scalar(
                select(Job).where(Job.seed_key == record["seed_key"])
            )
            if existing is None:
                session.add(Job(**record))
                inserted += 1
            else:
                for field, value in record.items():
                    setattr(existing, field, value)
                updated += 1
        session.commit()
    return inserted, updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic demo job listings.")
    parser.add_argument("--count", type=int, default=300)
    arguments = parser.parse_args()
    inserted, updated = seed_jobs(arguments.count)
    print(
        f"Synthetic demo jobs seeded: {inserted} inserted, "
        f"{updated} updated (requested {arguments.count})."
    )
    from app.index_jobs import main as index_existing_jobs

    index_existing_jobs()


if __name__ == "__main__":
    main()
