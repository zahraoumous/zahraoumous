"""Shared disposable PostgreSQL setup for authenticated integration workflows."""

import os
import subprocess
import sys
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, inspect


@pytest.fixture(scope="session")
def flow_app():
    url = os.environ.get("DATAPILOT_FLOW_DATABASE_URL")
    if not url:
        pytest.skip("DATAPILOT_FLOW_DATABASE_URL must name an empty disposable PostgreSQL database")
    engine = create_engine(url)
    assert not inspect(engine).get_table_names(), "Refusing to use a nonempty flow-test database"
    environment = {
        "DATAPILOT_DATABASE_URL": url,
        "DATAPILOT_REDIS_URL": "redis://localhost:6379/15",
        "DATAPILOT_S3_ENDPOINT": "http://localhost:9000",
        "DATAPILOT_S3_ACCESS_KEY": "test-local-key",
        "DATAPILOT_S3_SECRET_KEY": "test-local-secret",
        "DATAPILOT_APP_ORIGIN": "http://localhost:3000",
        "DATAPILOT_COOKIE_SECURE": "false",
    }
    with patch.dict(os.environ, environment):
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
        from app.core.config import get_settings
        from app.features.db import get_engine
        from app.main import app

        get_settings.cache_clear()
        get_engine.cache_clear()
        yield app
        get_engine().dispose()
        get_engine.cache_clear()
        get_settings.cache_clear()
    engine.dispose()
