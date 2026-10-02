"""Explicit PostgreSQL access and transactional, checksummed schema migrations."""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Any

from app.config.core_settings import CoreSettings
from app.knowledge.contracts import content_hash


class DatabaseUnavailable(RuntimeError):
    pass


class MigrationError(RuntimeError):
    pass


class PostgresDatabase:
    def __init__(self, settings: CoreSettings | None = None) -> None:
        self.settings = settings or CoreSettings()

    @contextmanager
    def connection(self) -> Iterator[Any]:
        url = self.settings.require_database_url()
        try:
            import psycopg
        except ImportError:
            raise DatabaseUnavailable("Install the psycopg[binary] project dependency") from None
        try:
            connection = psycopg.connect(
                url, connect_timeout=self.settings.database_connect_timeout_seconds,
                autocommit=True,
            )
        except psycopg.Error:
            # Driver messages may contain connection strings, passwords, or SQL data.
            raise DatabaseUnavailable("PostgreSQL connection failed") from None
        try:
            with connection:
                yield connection
        except psycopg.Error:
            raise DatabaseUnavailable("PostgreSQL operation failed; transaction rolled back") from None


@dataclass(frozen=True)
class SchemaMigration:
    version: str
    sql: str
    checksum: str


class SchemaMigrator:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or Path(__file__).parent / "migrations"

    def migrations(self) -> tuple[SchemaMigration, ...]:
        result = []
        for path in sorted(self.directory.glob("[0-9]*_*.sql")):
            # Normalize checkout line endings for portable migration checksums.
            sql = path.read_text(encoding="utf-8").replace("\r\n", "\n")
            result.append(SchemaMigration(path.stem, sql, content_hash(sql)))
        if not result:
            raise MigrationError("No PostgreSQL schema migrations found")
        return tuple(result)

    def apply(self, connection: Any) -> tuple[str, ...]:
        applied = []
        with connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(hashtext('orionstack.schema'))")
            connection.execute("CREATE SCHEMA IF NOT EXISTS core")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS core.schema_migrations (
                    version text PRIMARY KEY, checksum text NOT NULL,
                    applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            existing = dict(connection.execute(
                "SELECT version, checksum FROM core.schema_migrations"
            ).fetchall())
            migrations = self.migrations()
            if set(existing) - {migration.version for migration in migrations}:
                raise MigrationError("Database schema is newer than this migration set")
            for migration in migrations:
                if migration.version in existing:
                    if existing[migration.version] != migration.checksum:
                        raise MigrationError(f"Schema checksum mismatch: {migration.version}")
                    continue
                connection.execute(migration.sql)
                connection.execute(
                    "INSERT INTO core.schema_migrations (version, checksum) VALUES (%s, %s)",
                    (migration.version, migration.checksum),
                )
                applied.append(migration.version)
        return tuple(applied)
