-- Historical baseline proposal. Current schema: ../../services/api/alembic/versions/
-- DataPilot AI proposed PostgreSQL 15+ schema (review before production).
-- This is a starter DDL; use SQLAlchemy/Alembic migrations as implementation source of truth.
-- UUID generation requires pgcrypto on chosen PostgreSQL deployment.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    locale VARCHAR(12) NOT NULL DEFAULT 'en',
    status VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    oidc_sub TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    display_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE memberships (
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(16) NOT NULL CHECK (role IN ('owner','analyst','viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, user_id)
);

CREATE TABLE datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    created_by UUID NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    source_type VARCHAR(16) NOT NULL CHECK (source_type IN ('csv','xlsx')),
    status VARCHAR(16) NOT NULL DEFAULT 'uploaded'
      CHECK (status IN ('uploaded','validating','profiling','ready','failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id)
);
CREATE INDEX idx_datasets_org_created ON datasets(organization_id, created_at DESC);

CREATE TABLE dataset_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    dataset_id UUID NOT NULL,
    parent_version_id UUID,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    is_cleaned BOOLEAN NOT NULL DEFAULT FALSE,
    raw_object_key TEXT NOT NULL,
    parquet_object_key TEXT,
    source_sha256 CHAR(64) NOT NULL,
    schema_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    semantic_mapping_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    row_count BIGINT CHECK (row_count IS NULL OR row_count >= 0),
    column_count INTEGER CHECK (column_count IS NULL OR column_count >= 0),
    status VARCHAR(16) NOT NULL DEFAULT 'uploaded'
      CHECK (status IN ('uploaded','validating','profiling','ready','failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id,id),
    UNIQUE (dataset_id,version_number),
    CONSTRAINT fk_version_dataset FOREIGN KEY (organization_id,dataset_id)
       REFERENCES datasets(organization_id,id),
    CONSTRAINT fk_version_parent FOREIGN KEY (organization_id,parent_version_id)
       REFERENCES dataset_versions(organization_id,id)
);
CREATE INDEX idx_versions_dataset ON dataset_versions(organization_id,dataset_id,version_number DESC);

CREATE TABLE uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    created_by UUID NOT NULL REFERENCES users(id),
    original_filename TEXT NOT NULL,
    object_key TEXT NOT NULL UNIQUE,
    declared_size BIGINT NOT NULL CHECK (declared_size BETWEEN 1 AND 26214400),
    declared_sha256 CHAR(64),
    verified_sha256 CHAR(64),
    state VARCHAR(16) NOT NULL DEFAULT 'pending'
      CHECK (state IN ('pending','finalized','rejected','expired')),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id,id)
);

CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    created_by UUID REFERENCES users(id),
    dataset_version_id UUID,
    kind VARCHAR(24) NOT NULL CHECK (kind IN
      ('ingest','profile','quality','clean_preview','clean_apply','analysis','question','report','powerbi_export')),
    status VARCHAR(16) NOT NULL DEFAULT 'queued'
      CHECK (status IN ('queued','running','succeeded','failed','cancelled')),
    progress SMALLINT NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    idempotency_key TEXT,
    sanitized_error_code TEXT,
    sanitized_error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id,id),
    CONSTRAINT fk_jobs_version FOREIGN KEY (organization_id,dataset_version_id)
      REFERENCES dataset_versions(organization_id,id)
);
CREATE UNIQUE INDEX idx_jobs_idempotency ON jobs(organization_id,kind,idempotency_key)
  WHERE idempotency_key IS NOT NULL;
CREATE INDEX idx_jobs_org_created ON jobs(organization_id,created_at DESC);

CREATE TABLE quality_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    dataset_version_id UUID NOT NULL,
    rule_code VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL CHECK (severity IN ('critical','warning','info')),
    column_name TEXT,
    affected_rows BIGINT NOT NULL DEFAULT 0 CHECK (affected_rows >= 0),
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_finding_version FOREIGN KEY (organization_id,dataset_version_id)
      REFERENCES dataset_versions(organization_id,id)
);
CREATE INDEX idx_findings_version ON quality_findings(organization_id,dataset_version_id,severity);

CREATE TABLE cleaning_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    dataset_version_id UUID NOT NULL,
    new_version_id UUID,
    created_by UUID NOT NULL REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    status VARCHAR(16) NOT NULL DEFAULT 'proposed'
      CHECK (status IN ('proposed','approved','applied','rejected','failed')),
    operations_json JSONB NOT NULL,
    preview_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at TIMESTAMPTZ,
    CONSTRAINT fk_clean_source FOREIGN KEY (organization_id,dataset_version_id)
      REFERENCES dataset_versions(organization_id,id),
    CONSTRAINT fk_clean_result FOREIGN KEY (organization_id,new_version_id)
      REFERENCES dataset_versions(organization_id,id)
);

CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    dataset_version_id UUID NOT NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    question TEXT,
    status VARCHAR(16) NOT NULL DEFAULT 'queued'
      CHECK (status IN ('queued','running','completed','failed')),
    plan_json JSONB,
    metrics_json JSONB,
    results_json JSONB,
    evidence_json JSONB,
    insight_json JSONB,
    model_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    UNIQUE (organization_id,id),
    CONSTRAINT fk_analyses_version FOREIGN KEY (organization_id,dataset_version_id)
       REFERENCES dataset_versions(organization_id,id)
);
CREATE INDEX idx_analyses_org_created ON analyses(organization_id,created_at DESC);

CREATE TABLE dashboards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    analysis_id UUID NOT NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    spec_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_dash_analysis FOREIGN KEY (organization_id,analysis_id)
      REFERENCES analyses(organization_id,id)
);

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    dataset_version_id UUID NOT NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id,id),
    CONSTRAINT fk_conversations_version FOREIGN KEY (organization_id,dataset_version_id)
      REFERENCES dataset_versions(organization_id,id)
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    conversation_id UUID NOT NULL,
    role VARCHAR(16) NOT NULL CHECK (role IN ('user','assistant','system')),
    content TEXT NOT NULL,
    analysis_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_messages_conversation FOREIGN KEY (organization_id,conversation_id)
      REFERENCES conversations(organization_id,id),
    CONSTRAINT fk_messages_analysis FOREIGN KEY (organization_id,analysis_id)
      REFERENCES analyses(organization_id,id)
);
CREATE INDEX idx_messages_convo ON messages(organization_id,conversation_id,created_at);

CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    analysis_id UUID NOT NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    status VARCHAR(16) NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','ready','failed')),
    object_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_reports_analysis FOREIGN KEY (organization_id,analysis_id)
      REFERENCES analyses(organization_id,id)
);

CREATE TABLE exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    analysis_id UUID NOT NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    format VARCHAR(24) NOT NULL CHECK (format IN ('powerbi_zip','clean_csv')),
    status VARCHAR(16) NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','ready','failed')),
    object_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_exports_analysis FOREIGN KEY (organization_id,analysis_id)
      REFERENCES analyses(organization_id,id)
);

CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    actor_user_id UUID REFERENCES users(id),
    event_type VARCHAR(80) NOT NULL,
    resource_type VARCHAR(40),
    resource_id UUID,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_org_created ON audit_events(organization_id,created_at DESC);

-- Application-level enforcement and a follow-up RLS migration are mandatory
-- before production. Use org-scoped service functions for EVERY API/job query.
-- Avoid placing raw rows, secret keys or LLM prompt payloads in JSONB metadata.
