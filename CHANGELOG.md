# Changelog

All notable OrionStack changes are tracked here. The format follows a lightweight Keep a Changelog style.

## Unreleased

### Added

- Chat Workbench replaces standalone QA and document-scope UI; DataOps uses file/folder selection and Uppy S3 direct-upload contracts with mandatory hash/Tika/ClamAV quarantine, immutable Asset versions and tenant-scoped metadata. Actual external services are pending deployment.
- Cedar gates DataOps assets, cluster-backup operators and redacted diagnostics; Alembic 006/007 add metadata and immutable runtime configuration snapshots. pgBackRest provides repository status/file interfaces; combined database/object recovery and retention execution remain pending.

- P1-0/P1-1 runtime: independent Account/QA/DataOps/Logs modules and public compositions; new core query/document API, per-evidence typed ChainProfile persisted with answer runs, server correlation IDs and honest unavailable feedback/audit/backup states.
- External OIDC BFF adapter with Code + PKCE S256, signed ID-token verification, opaque HttpOnly server sessions, Origin/CSRF checks and stable issuer/subject principal mapping; local memberships are authoritative and unknown identities receive no default grants. Real IdP deployment validation is pending.
- Alembic adopts checked 001–004 migration history and adds 005 account/session schema; official migration CLI and future benchmark ingestion use Alembic. OpenBao consumption examples and OWASP/OTel/Cedar/backup boundary design added; no secret vault, telemetry engine, risk/credit or workflow runtime added.

- Per-evidence ChainProfile design for source identity, actor/time facts, version, scoped latest check, locator, original content/hash and immutable raw linkage; document DTO/API implemented, structured raw remains P1-3. Permission and semantic evaluation remain separate.
- Independent Account, QA, DataOps and Logs web-module design with composed workspaces; revised P1-0 through P1-4 contracts, feedback/audit/labels, structured read-only evidence, semantic evaluation and isolated backup restoration goals.
- Explicit architecture-pattern boundaries: replaceable adapters, minimal strategies/contracts, explicit pipelines and append-only journals; lightweight read/write separation without Event Sourcing or full CQRS. Credit/risk decisions and workflow/rollback implementation are deferred until the other modules are ready.
- Explicitly scoped existing-document DeepSeek acceptance mode, requiring live execution and document IDs; real HR/Qwen3/PostgreSQL acceptance passed with two checked excerpts and persistent raw/answer records.
- Browser verification guide and fixed synthetic upload sample; legacy IT-scope false answer and hardcoded HR provenance recorded for frontend migration acceptance.
- P0-3/4 local-Qwen3 acceptance: exact query text in raw records, no-provider empty-evidence path, bounded revalidated citations, duplicate-excerpt rejection and consistent optional Jev settings; real ASGI/PG acceptance with local answer transport plus fixed synthetic DeepSeek validation and full test-row rollback.
- Default local Qwen3-Embedding-0.6B ONNX Runtime provider with exact document input, query instruction, last-token pooling, L2 normalization, artifact-bound signatures and bounded shared sessions; Workers AI remains an explicit alternative.
- Read-only same-model PostgreSQL vector comparison CLI checks input hashes, float32 storage noise, batch padding stability and sample neighbor consistency.
- Pinned EnterpriseRAG-Bench Confluence ingestion: original dsid/path provenance, byte-exact originals, immutable dataset manifests, separate benchmark tenant, bounded parallel Workers AI batches and resumable activation.
- Corpus regressions cover portable identities, input changes, partial indexing/resume, permission/version changes during inference and idempotent repeated ingestion; quick release checks include them.

- P0 authenticated `/api/query`: immutable raw retrieval precedes optional Jev; DeepSeek selects verbatim excerpts, backend binds citations and rechecks current scope/version/revocation before separate answer audit.
- PostgreSQL document lifecycle APIs: scoped listing, admin upload/index/revoke, immutable original upload bytes, pending activation, version guards and authenticated downloads.
- Explicit hash-bound legacy quarantine manifest: preserve 7 historical missing-source payloads outside retrieval; complete real import of 5 documents, 94 chunks and 99 knowledge units, with Workers AI vectors and idempotent rerun.
- P0 SQL/auth/output regression coverage, runtime Knowledge OpenAPI contract and runbook; full release checks pass with 593 tests.

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
- Workers AI REST embeddings using CF_API_TOKEN / CF_ACCOUNT_ID, with strict vector validation, input hashes and application configuration signatures.
- Additive raw retrieval migration: immutable event/candidate snapshots, separate processing runs, evaluations, final rankings and approved training examples.
- Default raw pgvector pipeline with optional Jev, injected reranker and rules; independent authenticated feedback and curated training derivation.
- Bounded PostgreSQL embedding maintenance and raw query CLIs; isolated PGlite + pgvector SQL integration test runtime installed in CI, excluded from Docker.

### Changed

- Legacy web controls now follow the existing admin-only API permissions; ordinary users no longer see the admin link or unusable question/document controls, and invalid-login errors display readable Chinese messages.
- Admin extraction API and frontend contract are aligned around candidate list and review payloads.
- Production healthcheck now uses `/readyz` rather than process-only `/healthz`.
- Documentation now prioritizes Docker Compose production deployment, release checks, readiness checks, logs, and backup / restore runbooks.
- Extracted FAQ publication, reload and local retrieval now share canonical `unit_id`, with legacy `id` compatibility and duplicate publication recovery.
- Retrieval defaults to local during migration; production compose no longer starts Elasticsearch. The next release targets one PostgreSQL database with pgvector and TypeSafe Jev.
- Next-release plans use a stable Integration Boundary for external data; n8n/workflow connectors and orchestration stay outside the core retrieval path.
- Jev is an optional downstream processor. Retrieval commits the complete raw candidate set before processing; online corrections preserve original errors, ranks, scores and provenance.
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
- Current baseline (2026-10-03): `626 passed, 22 skipped, 9 xfailed` for full backend tests; frontend build, backup dry-run and production compose config checks also pass. Includes corpus ingestion and P0 query/document regressions.
- Runtime storage file hashes remain unchanged after the full release check.
- Synthetic live Jev routing returned `jev-1.13.0 / structured`; Workers AI returned two 1024-dimensional embeddings for synthetic Chinese texts. Isolated PostgreSQL + pgvector tests verify raw sealing, permission filters, signature separation, transaction rollback, processing and training derivation.
- Target PostgreSQL 17 / pgvector 0.8.2 connects after enabling LOGIN on the configured role. Both schema migrations applied successfully and repeat as a no-op. A Workers AI + PostgreSQL synthetic smoke verified vector writes, raw snapshot roundtrips, mutation rejection, separate processing/feedback/training, and complete test-row rollback.
- P0 completion supersedes earlier M1/M2 integration limitations: DeepSeek live query/citations passed, the two missing-source FAQ histories were explicitly quarantined, and authenticated core HTTP APIs are registered. The old web chat still uses its legacy API.

## 0.3.34 - 2026-05-02

### Baseline

- Phase 1-3 first-round implementation is complete.
- Provider bad-case main path has no open items.
- Phase 3 includes SourceRecord / ImportBatch / ExtractionCandidate, ActionLink, DynamicQuery, extraction pipeline, freshness, trace provenance, and hard-case classification.
