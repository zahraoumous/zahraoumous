from sqlalchemy import (
    CHAR,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base

feature_accounts = Table(
    "feature_accounts",
    Base.metadata,
    Column(
        "user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("email_normalized", Text, nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
)
feature_sessions = Table(
    "feature_sessions",
    Base.metadata,
    Column("token_hash", CHAR(64), primary_key=True),
    Column(
        "user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    ),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
Index("idx_feature_sessions_expiry", feature_sessions.c.expires_at)
feature_imports = Table(
    "feature_imports",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("created_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("organization_id", "id"),
)
feature_import_files = Table(
    "feature_import_files",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("import_id", UUID(as_uuid=True), nullable=False),
    Column("path", Text, nullable=False),
    Column("filename", Text, nullable=False),
    Column("dataset_id", UUID(as_uuid=True), nullable=False),
    Column("dataset_version_id", UUID(as_uuid=True), nullable=False),
    Column("job_id", UUID(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("organization_id", "import_id", "path"),
    UniqueConstraint("job_id"),
    ForeignKeyConstraint(
        ["organization_id", "import_id"],
        ["feature_imports.organization_id", "feature_imports.id"],
        name="fk_feature_file_import",
    ),
    ForeignKeyConstraint(
        ["organization_id", "dataset_id"],
        ["datasets.organization_id", "datasets.id"],
        name="fk_feature_file_dataset",
    ),
    ForeignKeyConstraint(
        ["organization_id", "dataset_version_id"],
        ["dataset_versions.organization_id", "dataset_versions.id"],
        name="fk_feature_file_version",
    ),
    ForeignKeyConstraint(
        ["organization_id", "job_id"],
        ["jobs.organization_id", "jobs.id"],
        name="fk_feature_file_job",
    ),
)
Index(
    "idx_feature_imports_org_created",
    feature_imports.c.organization_id,
    feature_imports.c.created_at.desc(),
)
Index(
    "idx_feature_files_import",
    feature_import_files.c.organization_id,
    feature_import_files.c.import_id,
)
