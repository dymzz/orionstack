"""Alembic owns upgrades; preserved SQL history detects changes to installed revisions."""

from pathlib import Path
from contextlib import contextmanager

from alembic import command, op
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.knowledge.postgres import DatabaseUnavailable, MigrationError, SchemaMigrator


def validate_history(connection):
    known = {migration.version:migration for migration in SchemaMigrator().migrations()}
    exists = connection.exec_driver_sql("SELECT to_regclass('core.schema_migrations')").scalar()
    if not exists:
        return
    existing = dict(connection.exec_driver_sql("SELECT version,checksum FROM core.schema_migrations").fetchall())
    if set(existing) - set(known):
        raise MigrationError("Database schema is newer than this revision set")
    for version,checksum in existing.items():
        if known[version].checksum != checksum:
            raise MigrationError("Schema checksum mismatch: "+version)
    # Existing installations must have a complete prefix before Alembic adopts them.
    ordered = list(known)
    if set(existing) != set(ordered[:len(existing)]):
        raise MigrationError("Installed migration history is not a complete prefix")


def apply_revision(version):
    connection = op.get_bind()
    migration = next(m for m in SchemaMigrator().migrations() if m.version == version)
    connection.exec_driver_sql("""CREATE TABLE IF NOT EXISTS core.schema_migrations (
        version text PRIMARY KEY,checksum text NOT NULL,applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    row = connection.exec_driver_sql("SELECT checksum FROM core.schema_migrations WHERE version=%s",(version,)).fetchone()
    if row:
        if row[0] != migration.checksum:
            raise MigrationError("Schema checksum mismatch: "+version)
        return
    connection.exec_driver_sql(migration.sql)
    connection.exec_driver_sql("INSERT INTO core.schema_migrations (version,checksum) VALUES (%s,%s)",(version,migration.checksum))


@contextmanager
def migration_connection(settings):
    """SQLAlchemy owns one transaction; legacy import may borrow its psycopg connection."""
    engine = None
    try:
        url = make_url(settings.require_database_url()).set(drivername="postgresql+psycopg")
        engine = create_engine(url,poolclass=NullPool,hide_parameters=True,echo=False,
                               connect_args={"connect_timeout":settings.database_connect_timeout_seconds})
        with engine.begin() as connection:
            yield connection,connection.connection.driver_connection
    except SQLAlchemyError:
        raise DatabaseUnavailable("PostgreSQL migration failed; transaction rolled back") from None
    finally:
        if engine is not None:
            engine.dispose()


def upgrade_database(connection):
    """The standard Alembic command adopts checked legacy revisions and upgrades to head."""
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "alembic.ini"))
    before = dict(connection.exec_driver_sql("SELECT version,checksum FROM core.schema_migrations").fetchall()) if connection.exec_driver_sql(
        "SELECT to_regclass('core.schema_migrations')").scalar() else {}
    config.attributes["connection"] = connection
    command.upgrade(config,"head")
    return tuple(m.version for m in SchemaMigrator().migrations() if m.version not in before)
