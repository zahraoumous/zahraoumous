"""Initial metadata schema, frozen from the supplied specification."""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep the migration independent from future ORM edits.
    ddl = Path(__file__).with_name("0001_initial.sql").read_text()
    op.get_bind().exec_driver_sql(ddl)


def downgrade() -> None:
    for name in (
        "audit_events",
        "exports",
        "reports",
        "messages",
        "conversations",
        "dashboards",
        "analyses",
        "cleaning_plans",
        "quality_findings",
        "jobs",
        "uploads",
        "dataset_versions",
        "datasets",
        "memberships",
        "users",
        "organizations",
    ):
        op.drop_table(name)
    # pgcrypto may be shared by other applications; deliberately retain it.
