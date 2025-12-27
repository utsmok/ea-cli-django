# Playwright UI Tests

This directory contains end-to-end browser tests using Playwright.

## Test Files

- `conftest.py` - Playwright fixtures and configuration
- `test_dashboard_ui.py` - Dashboard interface tests (8 tests)
- `test_ingestion_ui.py` - File upload and ingestion tests (7 tests)
- `test_steps_ui.py` - Processing steps UI tests (10 tests)
- `test_visual_regression.py` - Screenshot tests for visual baseline (5 tests)
- `test_legacy_ui.py` - Original UI tests (16 tests)

**Total: 46 tests**

## Running Tests

### Prerequisites

1. **Install Playwright browsers** (first time only):
   ```bash
   uv run playwright install chromium
   ```

2. **Start Django development server** (in a separate terminal):
   ```bash
   uv run python src/manage.py runserver
   ```

### Run All Playwright Tests

```bash
# Run with server already running
uv run pytest src/tests/playwright/ -v

# Run with coverage
uv run pytest src/tests/playwright/ --cov=src/apps --cov-report=term-missing
```

### Run Specific Test Files

```bash
# Dashboard UI tests only
uv run pytest src/tests/playwright/test_dashboard_ui.py -v

# Ingestion UI tests only
uv run pytest src/tests/playwright/test_ingestion_ui.py -v

# Steps UI tests only
uv run pytest src/tests/playwright/test_steps_ui.py -v

# Visual regression tests (takes screenshots)
uv run pytest src/tests/playwright/test_visual_regression.py -v
```

### Run Specific Tests

```bash
# Run single test
uv run pytest src/tests/playwright/test_dashboard_ui.py::TestDashboardLayout::test_dashboard_loads -v

# Run all tests in a class
uv run pytest src/tests/playwright/test_dashboard_ui.py::TestDashboardLayout -v
```

## Screenshots

Visual regression tests save screenshots to `test_screenshots/`:

- `dashboard_default_view.png` - Default dashboard view
- `dashboard_filtered_view.png` - Dashboard with filters applied
- `dashboard_detail_panel.png` - Dashboard with detail panel open
- `steps_index.png` - Steps index page
- `step_*.png` - Individual step pages
- `modal_upload.png` - Upload modal dialog
- `dashboard_mobile_*.png` - Responsive design screenshots

## Fixtures

### `authenticated_page`
Creates a Playwright page with an authenticated staff user.

### `sample_data`
Creates test data (3 faculties, 20 copyright items) for UI tests.

### `screenshot_dir`
Provides path to `test_screenshots/` directory.

### `take_screenshot`
Helper function to take screenshots:
```python
def test_example(page, take_screenshot):
    take_screenshot(page, "my-scenario")
```

### `wait_for_toast`
Waits for toast notifications and returns their data:
```python
def test_example(page, wait_for_toast):
    # Trigger action that shows toast
    page.click("button")

    # Wait for and verify toast
    toast = wait_for_toast()
    assert toast["type"] == "success"
```

## Test Structure

Tests are organized by UI component:

### Dashboard UI Tests
- Page layout and containers
- Workflow tabs (ToDo/InProgress/Done/All)
- Faculty dropdown
- Search functionality
- Pagination controls
- Inline editing
- Item detail panel
- Table rendering

### Ingestion UI Tests
- Upload modal
- File upload
- Source type selection
- Faculty code input
- Batch status
- Error handling

### Steps UI Tests
- Steps index page (all 7 steps)
- Step navigation
- Individual step pages
- Step descriptions and metadata

### Visual Regression Tests
- Full page screenshots
- Modal screenshots
- Responsive design (mobile/tablet)
- UI component screenshots

## Best Practices

1. **Use `wait_for_load_state("networkidle")`** after navigation
2. **Use `wait_for_timeout()` for HTMX debouncing** (typically 500-1500ms)
3. **Use soft checks** for optional elements:
   ```python
   if element.count() > 0 and element.is_visible():
       expect(element).to_be_visible()
   ```
4. **Mock external APIs** to prevent real network requests
5. **Use specific locators** (CSS selectors, text content)
6. **Set appropriate timeouts** for dynamic content (default 10s)

## Debugging Failed Tests

### Headed Mode (Watch Browser)

Run tests with `PLAYWRIGHT_HEADLESS=false`:

```bash
PLAYWRIGHT_HEADLESS=false uv run pytest src/tests/playwright/test_dashboard_ui.py::test_dashboard_loads -v
```

### Slow Motion

Run tests in slow motion to see interactions:

```bash
PLAYWRIGHT_SLOW_MO=1000 uv run pytest src/tests/playwright/test_dashboard_ui.py::test_dashboard_loads -v
```

### Debug with Breakpoints

Add `page.pause()` in test code to open Playwright Inspector:

```python
def test_debugging(page):
    page.goto("http://localhost:8000/dashboard/")
    page.pause()  # Opens Playwright Inspector
    # Continue test...
```

### Screenshots on Failure

Playwright automatically takes screenshots on test failure.

## CI/CD Integration

Add to CI pipeline:

```yaml
- name: Install Playwright browsers
  run: uv run playwright install chromium

- name: Start Django server
  run: |
    uv run python src/manage.py migrate
    uv run python src/manage.py runserver &
    sleep 5

- name: Run Playwright tests
  run: uv run pytest src/tests/playwright/ -v
```

## Base URL Configuration

Tests use `http://localhost:8000` by default. Override via environment variable:

```bash
PLAYWRIGHT_BASE_URL=http://localhost:8080 uv run pytest src/tests/playwright/ -v
```

## Markers

All tests in this directory are marked with:
- `@pytest.mark.playwright` - Skip with `-m "not playwright"` (default)
- `@pytest.mark.slow` - Skip with `-m "not slow"`

## Known Limitations

1. **Server must be running** - Tests need live Django server
2. **No external API calls** - Osiris/Canvas should be mocked
3. **Timing-dependent** - HTMX updates may need adjusted timeouts
4. **Database state** - Tests use real database, not in-memory

## Future Improvements

- [ ] Add automated visual diffing (e.g., Playwright compare screenshots)
- [ ] Add accessibility audit tests
- [ ] Add performance metrics (LCP, FID, CLS)
- [ ] Add multi-browser testing (Firefox, WebKit)
- [ ] Add API mocking for external services
- [ ] Add video recording for failed tests
