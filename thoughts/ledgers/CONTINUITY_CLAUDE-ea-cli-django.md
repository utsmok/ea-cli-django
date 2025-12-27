# Session: ea-cli-django
Updated: 2025-12-27T17:40:23.319Z

## Goal
Modern web platform for copyright compliance management of university course materials. Refactoring legacy CLI tool (ea-cli/) into Django-based system used by Copyright Office employees and Faculty Staff.

## Constraints
- **Python 3.13** with Django 6.0 (cutting edge)
- **uv** for package management (NEVER use pip directly)
- **Hybrid Development**: Docker for DB/Redis, local Django for faster iteration
- **Async-First**: I/O-bound operations should be async with sync wrappers where needed
- **Scale**: 50k-400k items - must optimize for performance
- **Line Length**: 88 characters (ruff default)
- **Git Identity**: utsmok <s.mok@utwente.nl> - NO Claude attribution in commits
- **Reference Only**: `ea-cli/` directory is legacy reference - all new code in `src/apps/`

## Tech Stack
- **Backend**: Django 6.0, Python 3.13
- **Frontend**: HTMX + Alpine.js + DaisyUI (Tailwind CSS)
- **Database**: PostgreSQL 17
- **Task Queue**: Redis with django-tasks and django-rq
- **Data Processing**: Polars for Excel/CSV handling
- **API**: Django Shinobi (Pydantic-based schemas, v1 prefix)
- **Dev Tools**: uv, ruff, pytest
- **Monitoring**: Loguru logging, health checks, rate limiting

## Key Decisions

### Architecture Decisions
- **Model Separation**: QlikItem mirror table approach (Task 2 complete)
- **Settings System**: Database model + YAML import/export (Task 3 complete)
- **Template Partials**: Kept `{% include %}` approach over Django 6.0 partials (Task 4)
- **API Versioning**: All endpoints under `/api/v1/` prefix (Task 19 complete)
- **Caching**: Redis with two backends (default, queries) + auto-invalidation (Task 1 complete)
- **Error Handling**: Retry logic with exponential backoff for external APIs (Task 5 complete)
- **Transactions**: Atomic operations for multi-step database changes (Task 15 complete)

### Development Workflow
- **Start Dev**: `./start-dev.sh` (starts Docker DB + Redis + Django + RQ worker)
- **Testing**: `uv run pytest` (never `pytest` directly)
- **Code Quality**: `uv run ruff format src/` and `uv run ruff check src/`
- **Git Commits**: Use `/commit` skill to remove Claude attribution

### Critical Fixes Applied
- Fixed Path.open bug in PDF download (Task 14)
- Fixed race condition in enrichment status updates (Task 14)
- Removed duplicate filehash field from Document model (Task 9)
- Implemented faculty extraction from Osiris people pages (Task 18)

## State

### Implementation Status
- **Done**: All 20 high-priority tasks completed (100%)
  - [x] Task 1: Redis Caching
  - [x] Task 2: Model Separation (QlikItem mirror table)
  - [x] Task 3: Settings System
  - [x] Task 4: Template Partials (evaluated, kept includes)
  - [x] Task 5: Error Handling (retry logic)
  - [x] Task 6: Table Enhancements
  - [x] Task 7: Styling Fixes (UT brand colors)
  - [x] Task 8: Security Hardening
  - [x] Task 9: Database Schema & Indexes
  - [x] Task 10: Async/ORM Consistency
  - [x] Task 11: Error Handling & Logging
  - [x] Task 12: API Validation & Docs
  - [x] Task 13: Test Coverage Expansion
  - [x] Task 14: Critical Bug Fixes
  - [x] Task 15: Transaction Management
  - [x] Task 16: Production Readiness
  - [x] Task 17: Logging Configuration
  - [x] Task 18: Incomplete Enrichment Data
  - [x] Task 19: API & Service Layer
  - [x] Task 20: Production Testing Gap

- **Now**: Platform is production-ready with comprehensive feature set
- **Next**: Waiting for user direction on next priorities

### 7-Step Processing Pipeline
All steps have dedicated UI interfaces in `src/apps/steps/`:
1. **Ingest Qlik Export** - Import course materials from Qlik
2. **Ingest Faculty Sheet** - Update classifications from faculty edits
3. **Enrich from Osiris** - Fetch course/teacher data from UT systems
4. **Enrich from People Pages** - Scrape person information (merged with Step 3)
5. **Get PDF Status from Canvas** - Check/download PDFs from Canvas
6. **Extract PDF Details** - Parse PDFs for text and metadata
7. **Export Faculty Sheets** - Generate Excel files for faculty review

### Test Coverage
- **Total Tests**: 282 passing, 2 skipped, 25 deselected (external_api/playwright)
- **URL Tests**: 96/96 passing (100%) - Phase 3 complete
- **Test Execution Time**: 26.52s (fast tests), 136.29s (full suite)
- **Coverage Areas**: Core models, services, API validation, auth/rate limiting, async ORM, URL resolution, integration pipeline

### Testing Implementation Plan (Phases 4-5)
- **Phase 3**: URL/Endpoint Tests ✅ COMPLETE (96 tests, 100% passing)
- **Task 1**: Fix 37 failing URL tests ✅ ALREADY COMPLETE (fixed in commit 93f5ce2)
- **Phase 4**: Backend Response Tests - NOT STARTED (~50 tests planned)
- **Phase 5**: Playwright UI Tests - NOT STARTED (~30 tests planned)
- **Plan Location**: `thoughts/shared/plans/2025-12-27-testing-implementation-phases-4-5.md`

## Open Questions
- None at this time - awaiting user direction

## Working Set
- **Branch**: `main`
- **Recent Commits**:
  - `ea1ab29` docs: add comprehensive test coverage report
  - `f7a6124` fix(tests): resolve OneToOneField conflicts in async ORM tests
  - `1e16e5d` docs: finalize all implementation plans and mark 20/20 tasks complete
  - `77f4e3d` feat(api): add v1 prefix and refactor dashboard views
  - `59b4a72` feat(logging): standardize logging with loguru

- **Modified Files**:
  - `.claude/settings.local.json` (local tool approvals)
  - `.gitignore` (cache exclusion)

- **Test Command**: `uv run pytest`
- **Dev Command**: `./start-dev.sh`
- **URL**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/v1/docs/

## App Structure
```
src/apps/
├── api/          # Django Shinobi API endpoints (/api/v1/)
├── classification/ # ML classification logic
├── core/         # Central models (CopyrightItem, Person, Course, etc.)
├── dashboard/    # Main UI views
├── documents/    # PDF handling, text extraction, OCR
├── enrichment/   # External integrations (Osiris, Canvas)
├── ingest/       # Data ingestion (Qlik, faculty sheets)
├── settings/     # Platform configuration management
├── steps/        # Step-based UI interfaces for 7 processing stages
└── users/        # User authentication
```

## Critical Files Reference

### Settings & Config
- `src/config/settings.py` - CACHES, security, connection pooling
- `src/config/asgi.py` - ASGI configuration for production
- `src/config/wsgi.py` - WSGI configuration

### Services (Core Business Logic)
- `src/apps/core/services/cache_service.py` - Cache utilities
- `src/apps/core/services/cache_invalidation.py` - Django signals
- `src/apps/core/services/retry_logic.py` - Retry decorator
- `src/apps/core/services/canvas.py` - Canvas API integration
- `src/apps/core/services/osiris.py` - Osiris API integration (with faculty extraction)
- `src/apps/core/services/transactions.py` - Atomic operations wrapper
- `src/apps/dashboard/services/query_service.py` - Dashboard queries

### Models
- `src/apps/core/models.py` - CopyrightItem, Person, Course, Organization, Faculty, QlikItem
- `src/apps/documents/models.py` - Document model (PDF metadata)
- `src/apps/ingest/models.py` - Qlik/Faculty ingestion batch tracking
- `src/apps/enrichment/models.py` - Enrichment batch tracking
- `src/apps/settings/models.py` - Setting model

### API
- `src/apps/api/views.py` - API endpoints (health, readiness, dashboard, enrichment)
- `src/apps/api/schemas.py` - Pydantic schemas
- `src/apps/api/urls.py` - URL routing with v1 prefix

### Frontend
- `src/apps/steps/views.py` - Step interface views
- `src/apps/steps/templates/steps/` - Step templates (7 interfaces)
- `src/apps/dashboard/views.py` - Main dashboard views

## Documentation
- `CLAUDE.md` - Project instructions for AI agents
- `README.md` - Development setup and quick start
- `IMPLEMENTATION_SUMMARY.md` - Step-based UI implementation details
- `docs/plans/README.md` - Implementation plans (20 tasks, all complete)
- `docs/TEST_COVERAGE_REPORT.md` - Comprehensive test analysis
- `.github/agents.md` - Comprehensive agent guide
- `src/apps/steps/README.md` - Step interface documentation

## Known Issues
- 11 failing tests related to transaction/enrichment (need investigation)
- GPU hardcoding in `src/apps/documents/services/parse.py:68` (Task 17)
- Step 4 (People Pages) currently redirects to Step 3 (planned separation)

## Future Enhancements
- Separate People Page enrichment from Osiris (Step 4)
- Fix 11 failing tests
- Add POST endpoint tests with mocked tasks
- Add integration workflow tests
- Add frontend/HTMX interaction tests
- Batch scheduling and queuing
- Step chaining (run multiple steps in sequence)
- Progress notifications (email, Slack)
- Result export (CSV, JSON)
- Audit logging for all operations

## Agent Reports

### onboard (2025-12-26T21:51:52.750Z)
- Task: 
- Summary: 
- Output: `.claude/cache/agents/onboard/latest-output.md`

### onboard (2025-12-26T21:30:46.290Z)
- Task: 
- Summary: 
- Output: `.claude/cache/agents/onboard/latest-output.md`

### onboard (2025-12-26T21:15:37.553Z)
- Task: 
- Summary: 
- Output: `.claude/cache/agents/onboard/latest-output.md`

### onboard (2025-12-26T21:15:33.843Z)
- Task: 
- Summary: 
- Output: `.claude/cache/agents/onboard/latest-output.md`

### onboard (2025-12-26T21:10:34.508Z)
- Task: 
- Summary: 
- Output: `.claude/cache/agents/onboard/latest-output.md`

### onboard (2025-12-26T20:38:52.208Z)
- Task: 
- Summary: 
- Output: `.claude/cache/agents/onboard/latest-output.md`

### onboard (2025-12-26T20:31:53.198Z)
- Task: 
- Summary: 
- Output: `.claude/cache/agents/onboard/latest-output.md`

