# Testing Guide

This guide explains how to run tests effectively for the Easy Access Platform.

## Quick Start

### Run Fast Tests (Recommended for Development)
```bash
# Run all fast tests (default behavior)
uv run pytest

# Explicitly run fast subset
uv run pytest -m "not slow and not external_api"
```

**Expected time**: 20-30 seconds

### Run All Tests (Including Slow/External)
```bash
# Run everything except playwright
uv run pytest -m "not playwright"

# Run including external API tests (requires network/VPN)
uv run pytest -m "not playwright" --override-ini="addopts="

# Run ONLY external API tests
uv run pytest -m "external_api"
```

**Expected time**: 2-5 minutes (depending on network latency)

## Test Markers

The test suite uses markers to categorize tests:

| Marker | Description | Default Behavior |
|--------|-------------|------------------|
| `slow` | Tests that take >10 seconds (usually due to `transaction=True`) | **Skipped** - run with `-m "slow"` |
| `external_api` | Tests that call real external APIs (Osiris, Canvas, people pages) | **Skipped** - run with `-m "external_api"` |
| `playwright` | Browser automation tests | **Skipped** - run with `-m "playwright"` |
| `unit` | Fast unit tests | **Run by default** |
| `integration` | Integration tests with database | **Run by default** |
| `e2e` | End-to-end pipeline tests | **Skipped** (marked as `external_api`) |
| `pipeline` | Pipeline-specific tests | **Skipped** (marked as `external_api`) |

## Test Execution Patterns

### During Active Development (TDD Workflow)
```bash
# Fast feedback loop - run only unit tests
uv run pytest -m "unit" -v

# Run tests for specific app
uv run pytest src/apps/core/tests/ -v

# Run with automatic test discovery on file changes
uv run pytest -f  # requires pytest-xdist installed
```

### Before Committing
```bash
# Run all fast tests (comprehensive but no external APIs)
uv run pytest -v

# Run with coverage report
uv run pytest --cov=src/apps --cov-report=term-missing
```

### CI/CD Pipeline
```bash
# Run full test suite
uv run pytest -v

# Or parallel execution
uv run pytest -n auto -v
```

## Performance Profile

### Fast Tests (< 1s each)
- Model tests
- Service tests
- URL resolution tests
- Form validation tests

### Medium Tests (1-10s each)
- `test_task_execution.py`: 7 tests in ~23s (database transaction overhead)
- Integration tests with `transaction=True` marker

### Slow Tests (> 10s each)
- `test_ingest_faculty_sheets`: ~40s (processes large Excel files)
- External API tests: 5-30s each (network latency)
- E2E pipeline tests: 60s+ (full pipeline with external APIs)

## Configuration

### Default Settings (pytest.ini)
```ini
addopts =
    -ra                              # Show summary of all test results
    -m "not playwright and not external_api"  # Skip slow tests by default
    --strict-markers                 # Validate marker usage
    --tb=short                       # Shorter traceback format
    --maxfail=5                      # Stop after 5 failures
    --durations=10                   # Show 10 slowest tests
    --timeout=10                     # Fail tests taking >10s
    --timeout_method=thread          # Use thread-based timeout
```

### Per-Test Timeouts

Different test classes have custom timeouts:
- `TestTaskExecution`: 30s (database transaction overhead)
- `TestBaseCasePipeline`: 60s (external API calls)
- `TestFacultyIngestion`: 60s (large Excel processing)
- `TestRoundTripExportImport`: 30s (export/import with transactions)

## External API Tests

Tests marked with `@pytest.mark.external_api` make real network calls to:
- **Osiris API**: `https://utwente.osiris-student.nl` (University course system)
- **Canvas API**: `https://utwente.instructure.com` (Learning management system)
- **People Pages**: `https://people.utwente.nl` (University directory)

### Requirements for External API Tests
- VPN or university network connection
- Valid API credentials in environment variables:
  - `OSIRIS_API_URL`
  - `OSIRIS_API_KEY`
  - `CANVAS_API_URL`
  - `CANVAS_API_TOKEN`

### Skipping External API Tests
```bash
# Already skipped by default, but explicit:
uv run pytest -m "not external_api"

# Run only fast tests during development
uv run pytest -m "not external_api and not slow"
```

## Troubleshooting

### Tests Timing Out
If tests fail with timeout errors:
```bash
# Run with increased timeout
uv run pytest --timeout=30

# Or run specific test without timeout
uv run pytest --timeout=0 tests/path/to/test.py
```

### Database Transaction Errors
Some tests use `@pytest.mark.django_db(transaction=True)` which:
- Creates fresh database for each test
- Cannot use rollback optimization
- Adds ~3-5s overhead per test

### External API Failures
```bash
# Check if you're on VPN/uni network
curl -I https://utwente.osiris-student.nl

# Check credentials
env | grep -E "(OSIRIS|CANVAS)"

# Skip external API tests
uv run pytest -m "not external_api"
```

## Coverage Reports

### Generate HTML Coverage Report
```bash
# Run tests with coverage
uv run pytest --cov=src/apps --cov-report=html

# View report
firefox htmlcov/index.html
```

### Generate Terminal Coverage
```bash
# Show missing lines
uv run pytest --cov=src/apps --cov-report=term-missing
```

## Running Specific Tests

### By File
```bash
uv run pytest src/apps/core/tests/test_cache_service.py -v
```

### By Class
```bash
uv run pytest src/apps/core/tests/test_cache_service.py::TestCacheService -v
```

### By Test Name
```bash
uv run pytest -k "test_cache_decorator_hit" -v
```

### By Marker
```bash
# Run only slow tests
uv run pytest -m "slow" -v

# Run only unit tests
uv run pytest -m "unit" -v

# Run only integration tests
uv run pytest -m "integration" -v
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]

jobs:
  fast-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run fast tests
        run: uv run pytest -m "not slow and not external_api" --cov

  full-tests:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run all tests
        run: uv run pytest -v --cov
```

## Best Practices

1. **Run fast tests frequently** during development (TDD workflow)
2. **Run medium tests** before committing
3. **Run slow/external tests** in CI or before major releases
4. **Use markers** to categorize new tests appropriately
5. **Set timeouts** for tests that may hang
6. **Mock external APIs** where possible for faster, deterministic tests

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-django documentation](https://pytest-django.readthedocs.io/)
- [pytest-timeout documentation](https://github.com/pytest-dev/pytest-timeout)
- Test coverage report: `htmlcov/index.html` (after running with `--cov`)
