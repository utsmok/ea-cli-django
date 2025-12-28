# Agent Guidelines for Easy Access Platform

**Environment**: Python 3.13, Django 6.0, PostgreSQL 17, Docker Compose preferred

## Commands
```bash
# Docker (recommended)
docker compose up --build
docker compose exec web pytest                          # all tests
docker compose exec web pytest tests/test_file.py::test_function  # single test
docker compose exec web uv run ruff check src/          # lint
docker compose exec web uv run ruff format src/         # format

# Local
uv run pytest tests/test_file.py::test_function
uv run ruff check src/
uv run ruff format src/
```

## Code Style
- **Line length**: 88 chars (ruff default)
- **Imports**: standard lib → third-party → first-party → local (ruff isort)
- **Naming**: `snake_case` functions/vars, `PascalCase` classes, `ALL_CAPS` constants
- **Types**: Type hints on public functions (pragmatic, not 100% coverage)
- **Logging**: Use `loguru`
- **Async**: Async-first for I/O, sync wrappers where needed
- **Formatting**: Ruff (double quotes, 4 spaces)
- **Error handling**: No bare `except:`, specific exceptions only
- **Legacy**: `ea-cli/` is reference only - all new code in `src/apps/`
