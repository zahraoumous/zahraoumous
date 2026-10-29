"""Encrypted, per-local-account AI provider preferences."""

from alembic import op

revision = "0004_ai_mvp"
down_revision = "0003_data_mvp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().exec_driver_sql("""
CREATE TABLE feature_ai_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK(provider IN ('local','openai','anthropic','gemini')),
    model TEXT NOT NULL,
    encrypted_api_key TEXT,
    key_hint TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
""")


def downgrade() -> None:
    op.drop_table("feature_ai_settings")
