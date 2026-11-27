"""Store searchable text for existing job listings."""

from alembic import op
import sqlalchemy as sa

revision = "20261128_01"
down_revision = "20261127_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.services.job_search_text import build_searchable_job_text

    op.add_column(
        "jobs",
        sa.Column("searchable_text", sa.Text(), nullable=True),
    )
    bind = op.get_bind()
    jobs = sa.table(
        "jobs",
        sa.column("id", sa.Integer()),
        sa.column("title", sa.String()),
        sa.column("company", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("required_skills", sa.JSON()),
        sa.column("preferred_skills", sa.JSON()),
        sa.column("responsibilities", sa.JSON()),
        sa.column("min_experience_years", sa.Integer()),
        sa.column("max_experience_years", sa.Integer()),
        sa.column("employment_type", sa.String()),
        sa.column("location", sa.String()),
        sa.column("work_mode", sa.String()),
        sa.column("searchable_text", sa.Text()),
    )
    records = bind.execute(
        sa.select(
            jobs.c.id,
            jobs.c.title,
            jobs.c.company,
            jobs.c.description,
            jobs.c.required_skills,
            jobs.c.preferred_skills,
            jobs.c.responsibilities,
            jobs.c.min_experience_years,
            jobs.c.max_experience_years,
            jobs.c.employment_type,
            jobs.c.location,
            jobs.c.work_mode,
        )
    ).mappings()
    for record in records:
        searchable_text = build_searchable_job_text(
            title=record["title"],
            company=record["company"],
            description=record["description"],
            required_skills=record["required_skills"],
            preferred_skills=record["preferred_skills"],
            responsibilities=record["responsibilities"],
            min_experience_years=record["min_experience_years"],
            max_experience_years=record["max_experience_years"],
            employment_type=record["employment_type"],
            location=record["location"],
            work_mode=record["work_mode"],
        )
        bind.execute(
            jobs.update()
            .where(jobs.c.id == record["id"])
            .values(searchable_text=searchable_text)
        )
    op.alter_column(
        "jobs",
        "searchable_text",
        existing_type=sa.Text(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("jobs", "searchable_text")
