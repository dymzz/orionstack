"""Preview first; --apply explicitly migrates the configured PostgreSQL database."""

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config.core_settings import CoreConfigurationError, CoreSettings
from app.knowledge.legacy_migration import LegacySnapshotPlanner, apply_legacy_snapshot
from app.knowledge.postgres import DatabaseUnavailable, MigrationError, PostgresDatabase, SchemaMigrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or apply PostgreSQL + pgvector schema and legacy import")
    parser.add_argument("--storage-root", type=Path, default=REPO_ROOT / "backend/app/storage")
    parser.add_argument("--tenant-id", default=None, help="Fallback tenant only for records missing tenant_id")
    parser.add_argument("--apply", action="store_true", help="Write to ORIONSTACK_DATABASE_URL in one transaction")
    parser.add_argument("--schema-only", action="store_true", help="Do not scan or import legacy storage")
    parser.add_argument("--no-seed", action="store_true", help="Exclude seed/mock and Markdown FAQ fixtures")
    args = parser.parse_args()
    try:
        settings = CoreSettings()
        migrator = SchemaMigrator()
        migrations = migrator.migrations()
        plan = None if args.schema_only else LegacySnapshotPlanner(
            args.storage_root, args.tenant_id or settings.default_tenant_id,
        ).build(include_seed=not args.no_seed)
        report = plan.summary() if plan is not None else {"mode": "preview", "ready_to_apply": True}
        report["schema_migrations"] = [{"version": migration.version, "checksum": migration.checksum}
                                       for migration in migrations]
        if args.apply:
            if plan is not None and plan.errors:
                print(json.dumps(report, ensure_ascii=False, indent=2))
                raise MigrationError("Fix preview errors before --apply; no database writes performed")
            with PostgresDatabase(settings).connection() as connection:
                # Schema and imported data either both commit or both roll back.
                with connection.transaction():
                    report["applied_schema"] = migrator.apply(connection)
                    report["import_status"] = apply_legacy_snapshot(connection, plan) if plan is not None else "not_requested"
            report["mode"] = "applied"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ready_to_apply"] else 2
    except (CoreConfigurationError, MigrationError, DatabaseUnavailable) as error:
        print(f"[orionstack] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
