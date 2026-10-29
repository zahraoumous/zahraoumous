"""Run only against an empty disposable database: applies, reverses and reapplies DDL."""

import os
import subprocess
import sys
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.features import tables  # noqa: F401 - include second migration metadata
from app.models import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration


def test_schema_and_tenant_foreign_keys():
    url = os.environ.get("DATAPILOT_TEST_DATABASE_URL")
    if not url:
        pytest.skip("DATAPILOT_TEST_DATABASE_URL must name an empty disposable database")
    environment = {**os.environ, "DATAPILOT_DATABASE_URL": url}
    engine = create_engine(url)
    try:
        assert not inspect(engine).get_table_names(), "Refusing to migrate a nonempty test database"

        def migrate(target, direction=None):
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "alembic",
                    direction or ("upgrade" if target == "head" else "downgrade"),
                    target,
                ],
                env=environment,
                check=True,
            )

        # Exercise an upgrade of the uploaded 0002 release with existing local data.
        migrate("0002", "upgrade")
        legacy_user, legacy_org, legacy_import = uuid4(), uuid4(), uuid4()
        from app.features.auth import hash_password, verify_password

        legacy_password = "migration-validation-password"
        encoded = hash_password(legacy_password)
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO users (id,oidc_sub,email) VALUES (:id,:sub,:email)"),
                {
                    "id": legacy_user,
                    "sub": "local:" + str(legacy_user),
                    "email": "preserved@example.test",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO feature_accounts (user_id,email_normalized,password_hash) "
                    "VALUES (:id,'preserved@example.test',:encoded)"
                ),
                {"id": legacy_user, "encoded": encoded},
            )
            connection.execute(
                text("INSERT INTO organizations (id,name) VALUES (:id,'Preserved workspace')"),
                {"id": legacy_org},
            )
            connection.execute(
                text(
                    "INSERT INTO memberships (organization_id,user_id,role) "
                    "VALUES (:org,:user,'owner')"
                ),
                {"org": legacy_org, "user": legacy_user},
            )
            connection.execute(
                text(
                    "INSERT INTO feature_imports (id,organization_id,created_by,name) "
                    "VALUES (:id,:org,:user,'Preserved folder import')"
                ),
                {"id": legacy_import, "org": legacy_org, "user": legacy_user},
            )
        migrate("head")
        with engine.connect() as connection:
            saved_hash = connection.execute(
                text("SELECT password_hash FROM feature_accounts WHERE user_id=:id"),
                {"id": legacy_user},
            ).scalar_one()
            assert saved_hash == encoded and verify_password(legacy_password, saved_hash)
            assert (
                connection.execute(
                    text("SELECT name FROM feature_imports WHERE id=:id"),
                    {"id": legacy_import},
                ).scalar_one()
                == "Preserved folder import"
            )
            assert (
                connection.execute(
                    text(
                        "SELECT role FROM memberships WHERE user_id=:user AND organization_id=:org"
                    ),
                    {"user": legacy_user, "org": legacy_org},
                ).scalar_one()
                == "owner"
            )
            differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
            assert differences == [], differences
        org_a, org_b, user, dataset = [uuid4() for _ in range(4)]
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO organizations (id,name) VALUES (:a,'A'),(:b,'B')"),
                {"a": org_a, "b": org_b},
            )
            connection.execute(
                text("INSERT INTO users (id,oidc_sub,email) VALUES (:u,'sub','a@example.test')"),
                {"u": user},
            )
            connection.execute(
                text(
                    "INSERT INTO datasets (id,organization_id,created_by,name,"
                    "source_type) VALUES (:d,:o,:u,'sample','csv')"
                ),
                {"d": dataset, "o": org_a, "u": user},
            )
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO dataset_versions (organization_id,dataset_id,"
                        "version_number,raw_object_key,source_sha256) VALUES (:o,:d,1,'raw',:hash)"
                    ),
                    {"o": org_b, "d": dataset, "hash": "a" * 64},
                )
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO memberships (organization_id,user_id,"
                        "role) VALUES (:o,:u,'admin')"
                    ),
                    {"o": org_a, "u": user},
                )
        migrate("base")
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
        migrate("head")
        assert len(inspect(engine).get_table_names()) == len(Base.metadata.tables) + 1
    finally:
        engine.dispose()
