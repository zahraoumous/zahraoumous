from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    metadata = MetaData()


organizations = Table(
    "organizations",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("name", Text, nullable=False),
    Column("locale", String(12), nullable=False, server_default=text("'en'")),
    Column(
        "status",
        String(16),
        CheckConstraint("status IN ('active','suspended')"),
        nullable=False,
        server_default=text("'active'"),
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
)

users = Table(
    "users",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("oidc_sub", Text, nullable=False, unique=True),
    Column("email", Text, nullable=False),
    Column("display_name", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
)

memberships = Table(
    "memberships",
    Base.metadata,
    Column(
        "organization_id",
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    ),
    Column(
        "role", String(16), CheckConstraint("role IN ('owner','analyst','viewer')"), nullable=False
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    PrimaryKeyConstraint("organization_id", "user_id"),
)

datasets = Table(
    "datasets",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("created_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column(
        "source_type", String(16), CheckConstraint("source_type IN ('csv','xlsx')"), nullable=False
    ),
    Column(
        "status",
        String(16),
        CheckConstraint("status IN ('uploaded','validating','profiling','ready','failed')"),
        nullable=False,
        server_default=text("'uploaded'"),
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("organization_id", "id"),
)

dataset_versions = Table(
    "dataset_versions",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("dataset_id", UUID(as_uuid=True), nullable=False),
    Column("parent_version_id", UUID(as_uuid=True)),
    Column("version_number", Integer, CheckConstraint("version_number > 0"), nullable=False),
    Column("is_cleaned", Boolean, nullable=False, server_default=text("FALSE")),
    Column("raw_object_key", Text, nullable=False),
    Column("parquet_object_key", Text),
    Column("source_sha256", CHAR(64), nullable=False),
    Column("schema_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("semantic_mapping_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("row_count", BigInteger, CheckConstraint("row_count IS NULL OR row_count >= 0")),
    Column("column_count", Integer, CheckConstraint("column_count IS NULL OR column_count >= 0")),
    Column(
        "status",
        String(16),
        CheckConstraint("status IN ('uploaded','validating','profiling','ready','failed')"),
        nullable=False,
        server_default=text("'uploaded'"),
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("organization_id", "id"),
    UniqueConstraint("dataset_id", "version_number"),
    ForeignKeyConstraint(
        ["organization_id", "dataset_id"],
        ["datasets.organization_id", "datasets.id"],
        name="fk_version_dataset",
    ),
    ForeignKeyConstraint(
        ["organization_id", "parent_version_id"],
        ["dataset_versions.organization_id", "dataset_versions.id"],
        name="fk_version_parent",
    ),
)

uploads = Table(
    "uploads",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("created_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
    Column("original_filename", Text, nullable=False),
    Column("object_key", Text, nullable=False, unique=True),
    Column(
        "declared_size",
        BigInteger,
        CheckConstraint("declared_size BETWEEN 1 AND 26214400"),
        nullable=False,
    ),
    Column("declared_sha256", CHAR(64)),
    Column("verified_sha256", CHAR(64)),
    Column(
        "state",
        String(16),
        CheckConstraint("state IN ('pending','finalized','rejected','expired')"),
        nullable=False,
        server_default=text("'pending'"),
    ),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("organization_id", "id"),
)

jobs = Table(
    "jobs",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("created_by", UUID(as_uuid=True), ForeignKey("users.id")),
    Column("dataset_version_id", UUID(as_uuid=True)),
    Column(
        "kind",
        String(24),
        CheckConstraint(
            "kind IN ('ingest','profile','quality','clean_preview',"
            "'clean_apply','analysis','question','report','powerbi_export')"
        ),
        nullable=False,
    ),
    Column(
        "status",
        String(16),
        CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')"),
        nullable=False,
        server_default=text("'queued'"),
    ),
    Column(
        "progress",
        SmallInteger,
        CheckConstraint("progress BETWEEN 0 AND 100"),
        nullable=False,
        server_default=text("0"),
    ),
    Column(
        "attempt_count",
        Integer,
        CheckConstraint("attempt_count >= 0"),
        nullable=False,
        server_default=text("0"),
    ),
    Column("idempotency_key", Text),
    Column("sanitized_error_code", Text),
    Column("sanitized_error_message", Text),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("organization_id", "id"),
    ForeignKeyConstraint(
        ["organization_id", "dataset_version_id"],
        ["dataset_versions.organization_id", "dataset_versions.id"],
        name="fk_jobs_version",
    ),
)

quality_findings = Table(
    "quality_findings",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("dataset_version_id", UUID(as_uuid=True), nullable=False),
    Column("rule_code", String(64), nullable=False),
    Column(
        "severity",
        String(16),
        CheckConstraint("severity IN ('critical','warning','info')"),
        nullable=False,
    ),
    Column("column_name", Text),
    Column(
        "affected_rows",
        BigInteger,
        CheckConstraint("affected_rows >= 0"),
        nullable=False,
        server_default=text("0"),
    ),
    Column("details_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    ForeignKeyConstraint(
        ["organization_id", "dataset_version_id"],
        ["dataset_versions.organization_id", "dataset_versions.id"],
        name="fk_finding_version",
    ),
)

cleaning_plans = Table(
    "cleaning_plans",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("dataset_version_id", UUID(as_uuid=True), nullable=False),
    Column("new_version_id", UUID(as_uuid=True)),
    Column("created_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
    Column("approved_by", UUID(as_uuid=True), ForeignKey("users.id")),
    Column(
        "status",
        String(16),
        CheckConstraint("status IN ('proposed','approved','applied','rejected','failed')"),
        nullable=False,
        server_default=text("'proposed'"),
    ),
    Column("operations_json", JSONB, nullable=False),
    Column("preview_json", JSONB),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("approved_at", DateTime(timezone=True)),
    ForeignKeyConstraint(
        ["organization_id", "dataset_version_id"],
        ["dataset_versions.organization_id", "dataset_versions.id"],
        name="fk_clean_source",
    ),
    ForeignKeyConstraint(
        ["organization_id", "new_version_id"],
        ["dataset_versions.organization_id", "dataset_versions.id"],
        name="fk_clean_result",
    ),
)

analyses = Table(
    "analyses",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("dataset_version_id", UUID(as_uuid=True), nullable=False),
    Column("created_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
    Column("question", Text),
    Column(
        "status",
        String(16),
        CheckConstraint("status IN ('queued','running','completed','failed')"),
        nullable=False,
        server_default=text("'queued'"),
    ),
    Column("plan_json", JSONB),
    Column("metrics_json", JSONB),
    Column("results_json", JSONB),
    Column("evidence_json", JSONB),
    Column("insight_json", JSONB),
    Column("model_version", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("completed_at", DateTime(timezone=True)),
    UniqueConstraint("organization_id", "id"),
    ForeignKeyConstraint(
        ["organization_id", "dataset_version_id"],
        ["dataset_versions.organization_id", "dataset_versions.id"],
        name="fk_analyses_version",
    ),
)

dashboards = Table(
    "dashboards",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("analysis_id", UUID(as_uuid=True), nullable=False),
    Column("created_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
    Column("title", Text, nullable=False),
    Column("spec_json", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    ForeignKeyConstraint(
        ["organization_id", "analysis_id"],
        ["analyses.organization_id", "analyses.id"],
        name="fk_dash_analysis",
    ),
)

conversations = Table(
    "conversations",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("dataset_version_id", UUID(as_uuid=True), nullable=False),
    Column("created_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("organization_id", "id"),
    ForeignKeyConstraint(
        ["organization_id", "dataset_version_id"],
        ["dataset_versions.organization_id", "dataset_versions.id"],
        name="fk_conversations_version",
    ),
)

messages = Table(
    "messages",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("conversation_id", UUID(as_uuid=True), nullable=False),
    Column(
        "role", String(16), CheckConstraint("role IN ('user','assistant','system')"), nullable=False
    ),
    Column("content", Text, nullable=False),
    Column("analysis_id", UUID(as_uuid=True)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    ForeignKeyConstraint(
        ["organization_id", "conversation_id"],
        ["conversations.organization_id", "conversations.id"],
        name="fk_messages_conversation",
    ),
    ForeignKeyConstraint(
        ["organization_id", "analysis_id"],
        ["analyses.organization_id", "analyses.id"],
        name="fk_messages_analysis",
    ),
)

reports = Table(
    "reports",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("analysis_id", UUID(as_uuid=True), nullable=False),
    Column("created_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
    Column(
        "status",
        String(16),
        CheckConstraint("status IN ('queued','running','ready','failed')"),
        nullable=False,
        server_default=text("'queued'"),
    ),
    Column("object_key", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    ForeignKeyConstraint(
        ["organization_id", "analysis_id"],
        ["analyses.organization_id", "analyses.id"],
        name="fk_reports_analysis",
    ),
)

exports = Table(
    "exports",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("analysis_id", UUID(as_uuid=True), nullable=False),
    Column("created_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
    Column(
        "format",
        String(24),
        CheckConstraint("format IN ('powerbi_zip','clean_csv')"),
        nullable=False,
    ),
    Column(
        "status",
        String(16),
        CheckConstraint("status IN ('queued','running','ready','failed')"),
        nullable=False,
        server_default=text("'queued'"),
    ),
    Column("object_key", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    ForeignKeyConstraint(
        ["organization_id", "analysis_id"],
        ["analyses.organization_id", "analyses.id"],
        name="fk_exports_analysis",
    ),
)

audit_events = Table(
    "audit_events",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
    Column("actor_user_id", UUID(as_uuid=True), ForeignKey("users.id")),
    Column("event_type", String(80), nullable=False),
    Column("resource_type", String(40)),
    Column("resource_id", UUID(as_uuid=True)),
    Column("metadata_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
)

Index("idx_datasets_org_created", datasets.c.organization_id, datasets.c.created_at.desc())
Index(
    "idx_versions_dataset",
    dataset_versions.c.organization_id,
    dataset_versions.c.dataset_id,
    dataset_versions.c.version_number.desc(),
)
Index(
    "idx_jobs_idempotency",
    jobs.c.organization_id,
    jobs.c.kind,
    jobs.c.idempotency_key,
    unique=True,
    postgresql_where=text("idempotency_key IS NOT NULL"),
)
Index("idx_jobs_org_created", jobs.c.organization_id, jobs.c.created_at.desc())
Index(
    "idx_findings_version",
    quality_findings.c.organization_id,
    quality_findings.c.dataset_version_id,
    quality_findings.c.severity,
)
Index("idx_analyses_org_created", analyses.c.organization_id, analyses.c.created_at.desc())
Index(
    "idx_messages_convo",
    messages.c.organization_id,
    messages.c.conversation_id,
    messages.c.created_at,
)
Index("idx_audit_org_created", audit_events.c.organization_id, audit_events.c.created_at.desc())


class Organization(Base):
    __table__ = organizations


class User(Base):
    __table__ = users


class Membership(Base):
    __table__ = memberships


class Dataset(Base):
    __table__ = datasets


class DatasetVersion(Base):
    __table__ = dataset_versions


class Upload(Base):
    __table__ = uploads


class Job(Base):
    __table__ = jobs


class QualityFinding(Base):
    __table__ = quality_findings


class CleaningPlan(Base):
    __table__ = cleaning_plans


class Analysis(Base):
    __table__ = analyses


class Dashboard(Base):
    __table__ = dashboards


class Conversation(Base):
    __table__ = conversations


class Message(Base):
    __table__ = messages


class Report(Base):
    __table__ = reports


class Export(Base):
    __table__ = exports


class AuditEvent(Base):
    __table__ = audit_events
