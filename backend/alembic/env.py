"""Online-only PostgreSQL migrations, reusing the caller's transaction when supplied."""

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.config.core_settings import CoreSettings
from app.knowledge.alembic_migrations import validate_history


def run(connection):
    connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS core")
    connection.exec_driver_sql("SELECT pg_advisory_xact_lock(hashtext('orionstack.schema'))")
    validate_history(connection)
    context.configure(connection=connection,version_table="alembic_version",version_table_schema="core",
                      transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Use the preview CLI; offline SQL cannot verify the installed migration history")
elif context.config.attributes.get("connection") is not None:
    run(context.config.attributes["connection"])
else:
    # SQLAlchemy URL normalization must preserve escaped credentials/query parameters.
    from sqlalchemy.engine import make_url
    url = make_url(CoreSettings().require_database_url()).set(drivername="postgresql+psycopg")
    engine = create_engine(url,poolclass=NullPool,hide_parameters=True,echo=False)
    try:
        with engine.begin() as connection:
            run(connection)
    finally:
        engine.dispose()
