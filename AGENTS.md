# Research Hub development

Local-only personal research software. Never upload user material or deploy without explicit authorization. Default bind is 127.0.0.1. User data MUST live outside this source tree (RESEARCH_HUB_WORKSPACE, default ~/.research-hub/workspace).

Backend: Python 3.10+, FastAPI, SQLAlchemy, SQLite, Alembic. Frontend: React/TypeScript/Vite. Run backend tests with `.venv/Scripts/python -m pytest backend/tests` on Windows or `.venv/bin/python -m pytest backend/tests` on Linux. Frontend: npm test and npm run build from frontend.

Markdown files are authoritative for body content. Immutable revisions are written atomically before committing their pointers in SQLite. Never overwrite existing revisions. Search text is a rebuildable cache. All mutations, exports and backups acquire the workspace FileLock. Use optimistic revision checks on updates. No destructive garbage collection without a separate design and user permission.

Use Alembic for schema upgrades; do not change an existing migration after release. Preserve full revision/review history and soft-deleted nodes. JSON interchange v1 is generated from Pydantic schemas via scripts/generate_protocol.py; regenerate schema and prompt together when models change. Imports use preview + explicit decisions, one transaction, append-only note merge, idempotency receipts. Do not infer semantic equivalence from titles alone.

Tests must use isolated temporary workspaces. Never seed or test against the user's actual data. Browser QA uses a separate temporary workspace. Document incomplete work and verification limits in DEVELOPMENT_STATUS.md. No mandatory paid APIs, remote fonts, analytics, or external content fetching.
