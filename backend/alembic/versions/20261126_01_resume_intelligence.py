"""Add resume intelligence while preserving existing Phase 2 rows."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261126_01"
down_revision = None
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _create_candidate_profiles() -> None:
    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("skills", postgresql.JSONB(), nullable=False),
        sa.Column("experience_years", sa.Float(), nullable=True),
        sa.Column("preferred_roles", postgresql.JSONB(), nullable=False),
        sa.Column("categories", postgresql.JSONB(), nullable=False),
        sa.Column("locations", postgresql.JSONB(), nullable=False),
        sa.Column("work_modes", postgresql.JSONB(), nullable=False),
        sa.Column("employment_types", postgresql.JSONB(), nullable=False),
        sa.Column("profile_source", sa.String(length=20), nullable=False),
        sa.Column("confirmed_profile", postgresql.JSONB(), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
        sa.Column("is_configured", sa.Boolean(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def _create_jobs() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("seed_key", sa.String(length=120), nullable=False, unique=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("company", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("responsibilities", postgresql.JSONB(), nullable=False),
        sa.Column("required_skills", postgresql.JSONB(), nullable=False),
        sa.Column("preferred_skills", postgresql.JSONB(), nullable=False),
        sa.Column("min_experience_years", sa.Integer(), nullable=False),
        sa.Column("max_experience_years", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(length=160), nullable=False),
        sa.Column("work_mode", sa.String(length=40), nullable=False),
        sa.Column("employment_type", sa.String(length=40), nullable=False),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("data_source", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def _add_candidate_profile_columns() -> None:
    existing = {column["name"] for column in _inspector().get_columns("candidate_profiles")}
    additions = (
        ("confirmed_profile", postgresql.JSONB(), True),
        ("salary_min", sa.Integer(), True),
        ("salary_max", sa.Integer(), True),
        ("salary_currency", sa.String(length=3), True),
    )
    for name, column_type, nullable in additions:
        if name not in existing:
            op.add_column(
                "candidate_profiles",
                sa.Column(name, column_type, nullable=nullable),
            )


def _create_resume_versions() -> None:
    if "resume_versions" in _inspector().get_table_names():
        existing = {
            column["name"] for column in _inspector().get_columns("resume_versions")
        }
        if "confirmed_data" not in existing:
            op.add_column(
                "resume_versions",
                sa.Column("confirmed_data", postgresql.JSONB(), nullable=True),
            )
        return
    op.create_table(
        "resume_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_profile_id",
            sa.Integer(),
            sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_filename", sa.String(length=80), nullable=False, unique=True),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("extraction_status", sa.String(length=32), nullable=False),
        sa.Column("extraction_error", sa.String(length=80), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extracted_data", postgresql.JSONB(), nullable=True),
        sa.Column("confirmed_data", postgresql.JSONB(), nullable=True),
        sa.Column("validation_report", postgresql.JSONB(), nullable=True),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_resume_versions_candidate_profile_id",
        "resume_versions",
        ["candidate_profile_id"],
    )
    op.create_index(
        "ix_resume_versions_extraction_status",
        "resume_versions",
        ["extraction_status"],
    )
    op.create_index("ix_resume_versions_sha256", "resume_versions", ["sha256"])


def upgrade() -> None:
    tables = set(_inspector().get_table_names())
    if "candidate_profiles" not in tables:
        _create_candidate_profiles()
    else:
        _add_candidate_profile_columns()
    if "jobs" not in tables:
        _create_jobs()
    _create_resume_versions()


def downgrade() -> None:
    bind = op.get_bind()
    if "resume_versions" in _inspector().get_table_names():
        count = bind.execute(sa.text("SELECT count(*) FROM resume_versions")).scalar_one()
        if count:
            raise RuntimeError(
                "Resume versions exist; remove them explicitly before downgrading."
            )
        op.drop_table("resume_versions")

    if "candidate_profiles" in _inspector().get_table_names():
        columns = {column["name"] for column in _inspector().get_columns("candidate_profiles")}
        for name in ("confirmed_profile", "salary_min", "salary_max", "salary_currency"):
            if name in columns:
                used = bind.execute(
                    sa.text(
                        f'SELECT EXISTS (SELECT 1 FROM candidate_profiles '
                        f'WHERE "{name}" IS NOT NULL)'
                    )
                ).scalar_one()
                if used:
                    raise RuntimeError(
                        f"Candidate profile data exists in {name}; refusing data loss."
                    )
                op.drop_column("candidate_profiles", name)
