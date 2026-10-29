"""Local accounts, authenticated sessions and multi-file import batches."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().exec_driver_sql("""
CREATE TABLE feature_accounts (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    email_normalized TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);
CREATE TABLE feature_sessions (
    token_hash CHAR(64) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_feature_sessions_expiry ON feature_sessions(expires_at);
CREATE TABLE feature_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    created_by UUID NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(organization_id,id)
);
CREATE TABLE feature_import_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    import_id UUID NOT NULL,
    path TEXT NOT NULL,
    filename TEXT NOT NULL,
    dataset_id UUID NOT NULL,
    dataset_version_id UUID NOT NULL,
    job_id UUID NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(organization_id,import_id,path),
    CONSTRAINT fk_feature_file_import FOREIGN KEY(organization_id,import_id)
        REFERENCES feature_imports(organization_id,id),
    CONSTRAINT fk_feature_file_dataset FOREIGN KEY(organization_id,dataset_id)
        REFERENCES datasets(organization_id,id),
    CONSTRAINT fk_feature_file_version FOREIGN KEY(organization_id,dataset_version_id)
        REFERENCES dataset_versions(organization_id,id),
    CONSTRAINT fk_feature_file_job FOREIGN KEY(organization_id,job_id)
        REFERENCES jobs(organization_id,id)
);
CREATE INDEX idx_feature_imports_org_created ON feature_imports(organization_id,created_at DESC);
CREATE INDEX idx_feature_files_import ON feature_import_files(organization_id,import_id);
""")


def downgrade() -> None:
    op.drop_table("feature_import_files")
    op.drop_table("feature_imports")
    op.drop_table("feature_sessions")
    op.drop_table("feature_accounts")
