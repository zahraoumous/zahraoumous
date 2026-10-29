import os

from alembic import context
from app.features import ai_mvp, tables  # noqa: F401 - register feature metadata
from app.models import Base
from sqlalchemy import create_engine, pool

url = os.environ["DATAPILOT_DATABASE_URL"]
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
