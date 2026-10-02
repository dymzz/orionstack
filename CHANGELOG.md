# Changelog

All notable OrionStack changes are tracked here. The format follows a lightweight Keep a Changelog style.

## Unreleased

### Added

- Minimal admin authentication for `/admin/*` and management APIs, with HMAC Bearer tokens and production safety checks.
- Production Docker Compose deployment: frontend Nginx SPA, FastAPI backend with local retrieval, persistent named volumes, and default JSONL bootstrap for ActionLink / DynamicQuery.
- `/readyz` readiness endpoint with app version, app mode, production config safety, and Elasticsearch indexing startup status.
- Unified release check script: `python scripts/release-check.py` for backend tests, frontend build, storage backup dry-run, and production compose config validation.
- GitHub Actions workflow `.github/workflows/release-check.yml` that runs the same release check on PRs and `main` / `master` pushes.
- Runtime logging setup with startup, request, exception, Elasticsearch indexing, and admin auth events.
- Storage backup and restore scripts: `scripts/backup-storage.py` and `scripts/restore-storage.py` with manifest and restore preview support.
- Single-database PostgreSQL + pgvector schema, tenant/version foreign keys, embedding metadata constraints, and checksummed transactional schema/legacy migration with read-only previews.
- Core Query/Access/Evidence and Action/Event contracts; standalone TypeSafe Jev and DeepSeek clients with response validation, scope checks, and backend citation identity resolution.
- `scripts/check-core-providers.py` for redacted configuration checks and explicit synthetic live API smoke tests; M1 runbook in `docs/designs/5_core_foundation_runbook.md`.

### Changed

- Admin extraction API and frontend contract are aligned around candidate list and review payloads.
- Production healthcheck now uses `/readyz` rather than process-only `/healthz`.
- Documentation now prioritizes Docker Compose production deployment, release checks, readiness checks, logs, and backup / restore runbooks.
- Extracted FAQ publication, reload and local retrieval now share canonical `unit_id`, with legacy `id` compatibility and duplicate publication recovery.
- Retrieval defaults to local during migration; production compose no longer starts Elasticsearch. The next release targets one PostgreSQL database with pgvector and TypeSafe Jev.
- Next-release plans use a stable Integration Boundary for external data; n8n/workflow connectors and orchestration stay outside the core retrieval path.
- Production volumes and backups include extracted FAQs, import batches, extraction tasks and cleanup tasks.
- Restore verifies the manifest and all file checksums before writing, and relocates document upload paths to the restore target.
- Backend version comes from `pyproject.toml`; test storage uses isolated, bounded temporary paths; quick release checks include P0 regressions.

### Security

- Production startup refuses default admin password, default token secret, or token secrets shorter than 24 characters.
- Access logs avoid request bodies, passwords, and Bearer tokens.
- Compose config validation in `release-check.py` hides output and overrides local API key variables to avoid leaking secrets into CI logs.
- New core credentials read native environment variables only; Docker build context excludes actual `.env` files and provider/database errors omit sensitive payloads.

### Verified

- `python scripts/release-check.py` passes locally.
- Current baseline (2026-10-02): `516 passed, 22 skipped, 9 xfailed` for full backend tests; frontend build, backup dry-run and production compose config checks also pass. M1 adds 68 passing tests; one Windows symlink test is skipped.
- Runtime storage file hashes remain unchanged after the full release check.
- Synthetic live Jev routing request returned `jev-1.13.0 / structured`; PostgreSQL SQL syntax parsed successfully. Actual PostgreSQL and DeepSeek integration remain unverified because their environment variables are unavailable; two extracted FAQ source references block the current legacy import preview.

## 0.3.34 - 2026-05-02

### Baseline

- Phase 1-3 first-round implementation is complete.
- Provider bad-case main path has no open items.
- Phase 3 includes SourceRecord / ImportBatch / ExtractionCandidate, ActionLink, DynamicQuery, extraction pipeline, freshness, trace provenance, and hard-case classification.
