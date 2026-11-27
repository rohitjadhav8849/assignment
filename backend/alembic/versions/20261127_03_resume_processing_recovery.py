"""Track resume extraction start times for safe stale-task recovery."""

from alembic import op
import sqlalchemy as sa

revision = "20261127_03"
down_revision = "20261127_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resume_versions",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("resume_versions", "processing_started_at")
