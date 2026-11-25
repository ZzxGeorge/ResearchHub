# Research Hub development

Local-only personal research software. Never upload user material or deploy without explicit authorization. Default bind is 127.0.0.1. User data MUST live outside this source tree (RESEARCH_HUB_WORKSPACE, default ~/.research-hub/workspace).

Backend: Python 3.10+, FastAPI, SQLAlchemy, SQLite, Alembic. Frontend: React/TypeScript/Vite. Run backend tests with `.venv/Scripts/python -m pytest backend/tests` on Windows or `.venv/bin/python -m pytest backend/tests` on Linux. Frontend: npm test and npm run build from frontend.

Markdown files are authoritative for body content. Immutable revisions are written atomically before committing their pointers in SQLite. Never overwrite existing revisions. Search text is a rebuildable cache. All mutations, exports and backups acquire the workspace FileLock. Use optimistic revision checks on updates. No destructive garbage collection without a separate design and user permission.

Use Alembic for schema upgrades; do not change an existing migration after release. Preserve full revision/review history and soft-deleted nodes. JSON interchange v1 is generated from Pydantic schemas via scripts/generate_protocol.py; regenerate schema and prompt together when models change. Imports use preview + explicit decisions, one transaction, append-only note merge, idempotency receipts. Do not infer semantic equivalence from titles alone.

Tests must use isolated temporary workspaces. Never seed or test against the user's actual data. Browser QA uses a separate temporary workspace. Document incomplete work and verification limits in DEVELOPMENT_STATUS.md. No mandatory paid APIs, remote fonts, analytics, or external content fetching.


## Desktop v0.2

Electron shell lives in desktop/; main process owns a PyInstaller onedir backend. Windows builds use scripts/build_windows.ps1, explicit resource allowlists, and release/. Never package any user workspace, test workspace, database, PDF or backup. Backend resource paths must work under sys._MEIPASS. Browser start.py remains supported.

Keep contextIsolation, sandbox and webSecurity enabled; nodeIntegration disabled. Preload exposes narrow, origin-checked IPC calls only, including cache operations limited to rh-theme, rh-draft-UUID and rh-capture-UUID keys. Desktop UI draft/theme state is workspace-scoped and independent of the random loopback origin. Backend token is launch-scoped, stays out of renderer/argv/logs and protects reads as well as writes. Health must match the launched instance. Bind the socket on port 0 to avoid port-selection races. Parent stdin EOF stops the backend. Only stop processes owned by the current launch.

Before any existing database upgrade, create a complete recoverable backup under the workspace lock; stop on failure. Migration 0002 adds per-attachment reading positions only; interchange v1 and its prompt must stay compatible. Test upgrades against the v0.1.0 Git tag in independent workspaces. No destructive downgrades.

Retain PDF.js and the existing split mode. PDFViewer is its official continuous viewer with text/search layers; do not enable PDF scripting, remote resources or eval. reading_positions persist page, zoom mode and offset in SQLite and travel with backups. Migration 0003 adds SourceAnchor / SourceLink / Annotation / AnnotationRevision / PaperReadingState. PDF selection stores per-page PDF user-space rectangles and an immutable attachment SHA256; validate file integrity before applying old coordinates.

Electron 45 can refuse to run unpacked executables inside this Codex workspace due to AppContainer ACLs. Do not disable the sandbox or weaken directory ACLs; test the NSIS-installed application in the ordinary current-user Programs location. Document that clean Windows 10/11 and restricted custom installation directories need separate validation.

## GitHub synchronization (user-authorized)

Canonical remote: https://github.com/ZzxGeorge/ResearchHub.git, remote name origin, primary branch main. The user has requested timely GitHub synchronization of subsequent improvements in this project. After meaningful authorized changes, run relevant checks, update README / DEVELOPMENT_STATUS as needed, commit explicit source/documentation paths and push the completed commits. Inspect remote changes first; preserve both local and remote work and never force-push. Push relevant version tags when releasing. Report push failures or authentication blockers honestly; do not claim synchronization without verifying the remote commit.

Only application source, public test examples, and documentation belong in Git. Never upload research workspaces, personal papers/notes/ideas, databases, backups, logs or credentials. Publish requested Windows installers as GitHub Release assets, not Git objects; include verification notes and SHA256. No background polling or scheduling is implied by this standing workflow.

## Interactive reading v0.3

Keep semantic relations, original source links and annotations separate. Capture uses existing NodeInput, save_node and append-only merge rules. Never reset vocabulary review states/history when adding context. Both meaning and contextual_meaning blank means no flashcard queue eligibility. Keep reading-summary v1 fully compatible; do not fabricate UUIDs, hashes or geometry in AI export.

Annotation Markdown is authoritative on disk with immutable revision paths; SQLite stores pointers and color/label snapshots. Backups must include current and historical annotation files, even soft-deleted ones, and must still work BEFORE the new tables exist during migration backup. Source/annotation delete is soft; unlink never deletes global knowledge or review logs. Manual node merge must carry forward source links.

Capture drafts / reading layout use separate paper_reading_states, never overwrite per-attachment positions. Use the latest client note body when inserting quotes; preserve optimistic note revisions, drafts and native workspace-scoped caches. Source resolve verifies attachment ownership, existence and actual SHA256. No PDF scripts, eval, OCR or remote AI service.

Additional checks: backend/tests/test_reading.py; frontend/tests/reading.test.tsx and pdf-geometry.test.ts. UI QA must use generated public fixtures and an isolated workspace. Test installed Electron in standard Programs directory; do not weaken the sandbox for QA. Document browser checks separately from actual Electron checks.
