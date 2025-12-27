"""
Playwright configuration and fixtures.

This file provides shared fixtures for Playwright UI tests.
"""

import os
from pathlib import Path
from typing import Generator

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from playwright.sync_api import Browser, BrowserContext, Page

from apps.core.models import CopyrightItem, Faculty

User = get_user_model()


# Base URL for tests - can be overridden via environment variable
BASE_URL = os.getenv("PLAYWRIGHT_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for all tests."""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
        "locale": "en-US",
        "timezone_id": "Europe/Amsterdam",
    }


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return base URL for tests."""
    return BASE_URL


@pytest.fixture
def page(base_url: str) -> Generator[Page, None, None]:
    """
    Create a Playwright page with base URL.

    This fixture is automatically used by all tests.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.set_default_timeout(10000)  # 10 second default timeout

        yield page

        context.close()
        browser.close()


@pytest.fixture
def authenticated_page(page: Page, base_url: str) -> Page:
    """
    Create a page authenticated as a staff user.

    This fixture logs in as a staff user before yielding the page.
    Note: This uses HTTP requests to the running server, not Django ORM.

    IMPORTANT: Tests must ensure the test user exists via other means
    (e.g., Django migrations, test data setup, or API calls).
    """
    # Navigate to login page
    page.goto(f"{base_url}/accounts/login/")

    # Fill in login form
    page.fill('input[name="username"]', "testuser")
    page.fill('input[name="password"]', "testpass123")

    # Click sign in button (using text selector since button has no type attribute)
    page.click('button:has-text("Sign In")')

    # Wait for navigation to complete
    page.wait_for_load_state("networkidle")

    yield page


@pytest.fixture
def sample_data() -> str:
    """
    Create sample data for UI tests via HTTP requests.

    This fixture creates test data by making HTTP requests to the running server,
    not by using Django ORM directly.

    Returns:
        str: Message indicating data creation status
    """
    # For now, skip auto-creation of data via HTTP
    # Tests that need data should create it via API calls or use authenticated_page
    # This fixture exists as a placeholder for future implementation
    return "Sample data fixture - create data via HTTP requests in tests"


@pytest.fixture
def screenshot_dir() -> Path:
    """Return directory for test screenshots."""
    path = Path("test_screenshots")
    path.mkdir(exist_ok=True)
    return path


@pytest.fixture
def take_screenshot(page: Page, screenshot_dir: Path):
    """
    Return a function that takes screenshots.

    Usage:
        take_screenshot(page, "my-test-scenario")
    """

    def _screenshot(name: str, full_page: bool = False):
        file_path = screenshot_dir / f"{name}.png"
        page.screenshot(path=str(file_path), full_page=full_page)
        return file_path

    return _screenshot


@pytest.fixture
def wait_for_toast(page: Page):
    """
    Return a function that waits for toast notifications.

    Usage:
        toast = wait_for_toast(page)
        assert toast["type"] == "success"
    """

    def _wait(timeout: int = 5000):
        """Wait for toast to appear and return its data."""
        page.wait_for_function(
            """() => {
                return window.__lastToast !== undefined;
            }""",
            timeout=timeout,
        )

        # Get toast data
        toast_data = page.evaluate("""() => window.__lastToast""")

        return toast_data

    return _wait


@pytest.fixture
def mock_external_api_calls(page: Page):
    """
    Mock external API calls to prevent real network requests.

    This fixture intercepts requests to Osiris, Canvas, and other external APIs.
    """

    def handle_route(route):
        """Mock external API routes."""
        # Return mock success response
        route.fulfill(
            status=200,
            body='{"status": "success", "data": {}}',
            headers={"Content-Type": "application/json"},
        )

    # Mock Osiris API
    page.route("**/osiris/**", handle_route)
    page.route("**/api/osiris/**", handle_route)

    # Mock Canvas API
    page.route("**/canvas/**", handle_route)
    page.route("**/api/canvas/**", handle_route)

    # Mock people pages
    page.route("**/people.utwente.nl/**", handle_route)

    return page


# Helper function to inject toast capture script
def inject_toast_capture(page: Page):
    """
    Inject JavaScript to capture toast notifications.

    This allows tests to verify toast content.
    """
    page.evaluate("""() => {
        window.addEventListener('show-toast', (event) => {
            window.__lastToast = event.detail;
        });
    }""")
