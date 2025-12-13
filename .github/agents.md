## Agents (LLM) Developer Guide

Purpose
-------
Guidance for using LLM-based agents to assist development, refactoring, tests, and documentation in this repository. Agents should be used as assistants — output must be reviewed, tested, and approved by a human developer before merging.

Repository context & legacy note
-------------------------------
- This repo contains a legacy codebase under `ea-cli/` (reference implementation). **ALL code inside `ea-cli/` is legacy reference material and must be treated as pre-refactor: it should NEVER be extended in-place or modified except for adding migration notes or extracting reference-only snippets.** All new development and redesigned implementations belong in the completely new Django-based platform described in `.github/refactor-plan.md` (see the "Easy Access Platform (v2.0)" plan).
- The new implementation is a web-based Django 6.0 platform with HTMX, Alpine.js, and DaisyUI, replacing the legacy CLI tool. The target structure is under `src/` with Django apps for core functionality.

Coding preferences (apply to repo)
---------------------------------
- Ruff/formatting: repo uses `ruff` with an 88-character line length and targets Python 3.12 (see `pyproject.toml`). Keep formatting consistent with existing config.
- Typing: add or improve type hints pragmatically. Prefer readable, explicit types for public functions. Full coverage is very nice but not required for especially complex function signatures (although these should be avoided anyway).
- Logging: `loguru` is used.
- Async-first: As the codebase is I/O-bound (DB, HTTP, file), prefer async implementations with sync wrappers if needed. Use Django built-in async functionality for this where possible.
- Django patterns: Follow Django best practices, including proper model relationships, migrations, and view patterns. Use Django Shinobi for API schemas where applicable.

Project architecture (refactor targets)
--------------------------------------
- **Tech Stack:** Django 6.0, Python 3.12+, PostgreSQL 17, Docker, HTMX, Alpine.js, DaisyUI.
- **Backend:** Django 6.0 with native tasks and async support.
- **API:** Django Shinobi (Pydantic-based API schemas).
- **Data Processing:** Polars for high-performance Excel/CSV processing.
- **Frontend:** HTMX (server interaction) + Alpine.js (client state) + DaisyUI (Tailwind CSS components).
- **Infrastructure:** Docker Compose, VS Code Dev Containers.
- **Target Structure:** As outlined in `.github/refactor-plan.md`, with `src/apps/` containing Django apps: `api/`, `core/`, `dashboard/`, `documents/`, `enrichment/`, `ingest/`.
- Key components in new implementation:
  - `src/apps/core/`: Models & shared logic.
  - `src/apps/dashboard/`: UI views (HTMX).
  - `src/apps/ingest/`: Polars logic & file watching.
  - `src/apps/enrichment/`: External integrations (OSIRIS, Canvas).
  - `src/apps/documents/`: PDF logic.
  - `src/apps/api/`: Shinobi endpoints.

Common patterns & solutions
--------------------------
- Async + sync wrappers: Implement core logic as async and expose sync wrappers for CLI or synchronous contexts. Use Django's async views and tasks.
- Django models: Use proper foreign keys, JSONField for flexible data, and indexes for performance.
- File watching and ingestion: Use `watchfiles` for monitoring directories, enqueue Django tasks for processing.
- Frontend: Use HTMX for dynamic updates, Alpine.js for client-side state, DaisyUI for styling.
- Data processing: Use Polars for Excel/CSV handling, bulk DB operations to avoid N+1 queries.
- Settings: Use `django-environ` for environment variables.

Constraints & environment
------------------------
- Python 3.12.x (keep CI and local dev interpreters aligned).
- Django 6.0 with PostgreSQL 17.
- Use Docker Compose for development environment (see `.github/refactor-plan.md`).
- Heavy optional deps (OCR/LLM/PyTorch) are grouped — avoid installing unless working on related features.
- Scale: 50k - 400k items; optimize for performance.
- Environment: Internal University Network (VPN/Intranet); local disk storage for PDFs.

Agent rules & expectations
-------------------------
- Treat the agent as a suggestion engine: all changes from an agent require a human review and tests before merge.
- **Do not modify `ea-cli/` files except to add explicit migration notes or to extract reference-only snippets into the new Django implementation; new functionality must be implemented under `src/apps/` according to the refactor plan.**
- Never commit secrets. Use `.env` for local secrets and `.env.example` with placeholders. CI must use environment variables.
- Require the agent to return either an apply_patch-style diff or full file contents with exact paths.
- Require unit tests for any functional change; if tests are infeasible, the agent must provide a short rationale and suggested manual test steps.

Prompt templates for developer use
---------------------------------
- System prompt (suggested):
  "You are a precise software engineer assistant for the Django-based Easy Access Platform refactor. Produce minimal, well-typed edits targeting Python 3.12 and Django 6.0. Always include unit tests and a list of files changed."
- User prompt (task):
  1) One-line goal. 2) Target package/file paths (under `src/apps/`). 3) Constraints (tools, Python version, Django version, formatting). 4) Required outputs (apply_patch diff, tests). 5) Run & test instructions.

What to check in generated code
------------------------------
- Type hints and docstrings for new public functions.
- No hard-coded credentials or absolute paths.
- Respect ruff/format settings and existing import ordering.
- Added/updated tests should be small, deterministic, and fast.

Running & validating agent changes locally
-----------------------------------------
1. Start the development environment using Docker Compose:

```bash
docker compose up --build
```

   - This starts: Web Server (8000), Worker, File Watcher, DB, Redis.

2. Access the system:
   - Frontend: `http://localhost:8000`
   - API Docs: `http://localhost:8000/api/docs` (Shinobi auto-docs)

3. Run targeted tests (example):

```bash
docker compose exec web python src/manage.py test
```

4. For CLI/manual runs:

```bash
docker compose exec web python src/manage.py <command>
```

5. Applying changes:
   - If you change models: Run migrations inside the container.
   - If you add dependencies: Update `pyproject.toml` and rebuild Docker.

Safety, security & review
-------------------------
- Do not allow an agent to run unchecked shell commands; require human approval for any environment modifications.
- Use code reviews to catch hallucinated APIs, unsafe DB migrations, or file operations that could delete user data.
- For external API integrations, require integration tests or clear mocking strategies.

PR workflow for agent-generated changes
--------------------------------------
1. Agent produces an apply_patch diff or full file contents. 2. Developer applies patch locally and runs tests. 3. Create a feature branch and open a PR including the agent prompt and a short human review note. 4. Tag the PR as "agent-assisted" and assign a reviewer.

Appendix: practical checklist for agent PRs
-----------------------------------------
- [ ] Agent prompt included in PR description
- [ ] apply_patch/diff attached or branch created
- [ ] Unit tests added/updated and passing locally
- [ ] No secrets or env vars leaked in the diff
- [ ] Human reviewer assigned and approval obtained

---
Last updated: December 8, 2025
