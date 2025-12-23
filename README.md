# Easy Access Platform

Django-based web application for managing copyright compliance of university course materials.

## Development Setup

Choose your development environment:

### Option 1: WSL/Linux - Docker DB + Local Django (Recommended for Linux)

Run PostgreSQL and Redis in Docker, while running Django directly with `uv` for faster iteration.

**Prerequisites:**
- Docker Desktop
- `uv` package manager
- WSL2 (Windows) or native Linux

**Quick Start:**
```bash
# One command to start everything
./start-dev.sh
```

**Manual Setup:**
```bash
# 1. Start Docker containers (db + redis)
docker compose up -d

# 2. Install dependencies
uv sync

# 3. Set environment variables (already in .env)
export $(cat .env | grep -v '^#' | xargs)

# 4. Run migrations
uv run python src/manage.py migrate

# 5. Start Django server
uv run python src/manage.py runserver

# 6. In another terminal, start RQ worker
export $(cat .env | grep -v '^#' | xargs)
uv run python src/manage.py rqworker --job-class django_tasks.backends.rq.Job default
```

**Stop Services:**
- `Ctrl+C` to stop Django and RQ worker
- `docker compose down` to stop database and Redis

---

### Option 2: Windows/macOS - 100% Docker

Run everything in Docker containers using the custom-built image.

**Prerequisites:**
- Docker Desktop
- Copy `.env.example` to `.env` and configure

**Quick Start:**
```bash
# Start all services (db, redis, web, worker)
docker compose -f docker-compose.yml -f docker-compose-web-worker.yml up --build

# Or start in detached mode
docker compose -f docker-compose.yml -f docker-compose-web-worker.yml up --build -d
```

**View Logs:**
```bash
# Follow all logs
docker compose -f docker-compose.yml -f docker-compose-web-worker.yml logs -f

# Specific service
docker compose -f docker-compose.yml -f docker-compose-web-worker.yml logs -f web
docker compose -f docker-compose.yml -f docker-compose-web-worker.yml logs -f worker
```

**Run Management Commands:**
```bash
# Migrations
docker compose exec web python src/manage.py migrate

# Create superuser
docker compose exec web python src/manage.py createsuperuser

# Shell
docker compose exec web python src/manage.py shell

# Tests
docker compose exec web pytest
```

**Stop Services:**
```bash
docker compose -f docker-compose.yml -f docker-compose-web-worker.yml down
```

---

## Environment Configuration

Required environment variables (see `.env`):

```env
# Database
DATABASE_URL=postgres://admin:dev_password@localhost:5432/copyright_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Django
DEBUG=True
SECRET_KEY=change-me-in-production
ALLOWED_HOSTS=localhost,127.0.0.1

# External APIs (optional for development)
OSIRIS_API_URL=https://osiris.example.nl/api
OSIRIS_API_KEY=your-key
CANVAS_API_URL=https://canvas.example.nl/api/v1
CANVAS_API_TOKEN=your-token
```

**Note for Docker-only setup:** Update `DATABASE_URL` and `REDIS_URL` to use Docker service names (`db` and `redis` instead of `localhost`). The `.env.example` already has the correct values for Docker.

---

## Architecture

### Tech Stack
- **Backend:** Django 6.0, Python 3.13
- **Frontend:** HTMX + Alpine.js + DaisyUI (Tailwind CSS)
- **Database:** PostgreSQL 17
- **Task Queue:** Redis with django-tasks and django-rq
- **Data Processing:** Polars for Excel/CSV handling
- **API:** Django Shinobi (Pydantic-based schemas)

### App Structure (`src/apps/`)

| App | Purpose |
|-----|---------|
| `core/` | Central models (CopyrightItem, Person, Course, Organization, Faculty) |
| `ingest/` | Data ingestion from Qlik exports and faculty sheets |
| `enrichment/` | External integrations (Osiris API, Canvas API) |
| `documents/` | PDF handling, text extraction, OCR |
| `classification/` | ML classification logic |
| `dashboard/` | Main UI views |
| `api/` | API endpoints |
| `steps/` | Step-based UI interfaces for each processing stage |
| `users/` | User authentication |

---

## Docker Compose Files

- **`docker-compose.yml`** - Base services (PostgreSQL, Redis)
- **`docker-compose-web-worker.yml`** - Django web server and RQ worker (extends base)

Use both files together for full Docker setup:
```bash
docker compose -f docker-compose.yml -f docker-compose-web-worker.yml [command]
```

---

## Code Quality

```bash
# Format code
uv run ruff format src/

# Lint code
uv run ruff check src/

# Type check
uv run pyright src/
```

---

## Project Documentation

- `CLAUDE.md` - Project instructions for AI agents
- `.github/agents.md` - Comprehensive agent guide
- `IMPLEMENTATION_SUMMARY.md` - Step-based UI implementation
- `conductor/` - Product vision, technical specs, and workflow docs
- `src/apps/steps/README.md` - Step interface documentation
