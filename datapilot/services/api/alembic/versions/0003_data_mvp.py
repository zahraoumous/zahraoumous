"""Enable deterministic data workflows on the existing MVP data model.

The immutable original schema already contains dataset versions, cleaning plans,
analyses, dashboards, jobs and audit tables. No destructive schema change is needed.
"""

revision = "0003_data_mvp"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
