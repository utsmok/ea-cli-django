# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Easy Access Platform is a Django-based web application for managing copyright compliance of university course materials. It refactors a legacy CLI tool (`ea-cli/`) into a modern web platform used by Copyright Office employees and Faculty Staff.

**Critical**: The `ea-cli/` directory is REFERENCE ONLY. All new development must be in `src/apps/`.

## Development Commands

### Docker (Recommended)
```bash
# Start all services
docker compose up --build

# Run management commands
docker compose exec web python src/manage.py migrate
docker compose exec web python src/manage.py createsuperuser
docker compose exec web python src/manage.py runserver 0.0.0.0:8000

# Run tests
docker compose exec web pytest

# Run tests with coverage
docker compose exec web pytest --cov=src/apps
```

### Local Development
```bash
# Install dependencies (requires uv)
uv sync

# Add new dependencies
uv add <package-name>

# Run development server
uv run python src/manage.py runserver

# Database operations
uv run python src/manage.py makemigrations
uv run python src/manage.py migrate

# Run tests
uv run pytest
uv run pytest src/apps/core/tests/
```

### Code Quality
```bash
# Format code
uv run ruff format src/

# Lint code
uv run ruff check src/

# Check imports specifically
uv run ruff check src/ --select I
```

## Architecture

### Technology Stack
- **Backend**: Django 6.0, Python 3.13
- **Frontend**: HTMX + Alpine.js + DaisyUI (Tailwind CSS)
- **Database**: PostgreSQL 17
- **Task Queue**: Redis with django-tasks and django-rq
- **Data Processing**: Polars for Excel/CSV handling
- **API**: Django Shinobi (Pydantic-based schemas)
- **Dev Tools**: uv, ruff, pytest

### App Structure (`src/apps/`)

| App | Purpose |
|-----|---------|
| `core/` | Central models (CopyrightItem, Person, Course, Organization, Faculty) |
| `ingest/` | Data ingestion from Qlik exports and faculty sheets (two-phase: Stage → Process) |
| `enrichment/` | External integrations (Osiris API, Canvas API) |
| `documents/` | PDF handling, text extraction, OCR (PaddleOCR) |
| `classification/` | ML classification logic |
| `dashboard/` | Main UI views |
| `api/` | API endpoints (Django Shinobi) |
| `steps/` | Step-based UI interfaces for each processing stage |
| `users/` | User authentication |

### 7-Step Processing Pipeline

1. **Ingest Qlik Export** - Import course material data from Qlik
2. **Ingest Faculty Sheet** - Update classifications from faculty edits
3. **Enrich from Osiris** - Fetch course/teacher data from UT systems
4. **Enrich from People Pages** - Scrape person information (currently merged with Step 3)
5. **Get PDF Status from Canvas** - Check/download PDFs from Canvas
6. **Extract PDF Details** - Parse PDFs for text and metadata
7. **Export Faculty Sheets** - Generate Excel files for faculty review

### Data Flow
- **Import**: Excel files → Polars → Django ORM
- **Enrichment**: External APIs → Async tasks → Database
- **Export**: Django ORM → Excel with exact formatting

## Coding Standards

- **Line Length**: 88 characters (ruff default)
- **Python Version**: 3.13
- **Type Hints**: Use for public functions
- **Async-First**: Core logic async with sync wrappers where needed (I/O-bound operations)
- **Logging**: Use `loguru`
- **Models**: Inherit from `TimestampedModel`, use proper indexes, `JSONField` for flexible data
- **Testing**: Write unit tests for functional changes

## Environment Configuration

Required environment variables (see `.env.example`):
```env
DATABASE_URL=postgres://...
REDIS_URL=redis://...
DEBUG=True
SECRET_KEY=...
ALLOWED_HOSTS=localhost,127.0.0.1

OSIRIS_API_URL=https://...
OSIRIS_API_KEY=...
CANVAS_API_URL=https://...
CANVAS_API_TOKEN=...
```

## Key Patterns

- **HTMX**: For dynamic updates without full page reloads
- **Alpine.js**: For client-side state management
- **DaisyUI**: For consistent styling with Tailwind
- **Async Tasks**: Use Django tasks with proper status tracking
- **Bulk Operations**: Use Polars and bulk ORM operations to avoid N+1 queries

## Constraints

- **Scale**: 50k-400k items - optimize for performance
- **External Dependencies**: University internal network (VPN/Intranet), local disk storage
- **Heavy Optional Dependencies**: OCR/ML dependencies are grouped - avoid installing unless working on related features
- **Python Commands**: ALWAYS use `uv run` for Python commands locally (never `python` or `pytest` directly). Use `uv add` for dependencies (never `pip install`). Docker commands use `python` directly inside containers.

## References

- `.github/agents.md` - Comprehensive guide for AI agents
- `IMPLEMENTATION_SUMMARY.md` - Step-based UI implementation details
- `conductor/product.md` - Product vision and goals
- `conductor/tech-stack.md` - Technology stack details
- `src/apps/steps/README.md` - Step interface documentation
