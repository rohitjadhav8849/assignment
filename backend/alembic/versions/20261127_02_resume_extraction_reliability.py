"""Persist safe extraction diagnostics and retry state."""

from alembic import op
import sqlalchemy as sa

revision = "20261127_02"
down_revision = "20261126_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resume_versions",
        sa.Column("extraction_failure_category", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "resume_versions",
        sa.Column("extraction_http_status", sa.Integer(), nullable=True),
    )
    op.add_column(
        "resume_versions",
        sa.Column("extraction_diagnostic", sa.String(length=300), nullable=True),
    )
    op.add_column(
        "resume_versions",
        sa.Column("extraction_retryable", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "resume_versions",
        sa.Column(
            "extraction_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("resume_versions", "extraction_attempts")
    op.drop_column("resume_versions", "extraction_retryable")
    op.drop_column("resume_versions", "extraction_diagnostic")
    op.drop_column("resume_versions", "extraction_http_status")
    op.drop_column("resume_versions", "extraction_failure_category")
