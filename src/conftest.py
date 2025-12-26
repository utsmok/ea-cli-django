"""
Central pytest configuration and shared fixtures.

This file provides common fixtures for all tests in the project.
Fixtures are available to all test files automatically.
"""
import os
from pathlib import Path
from typing import Generator

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

# Get the User model
User = get_user_model()


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def clean_db(db) -> Generator[None, None, None]:
    """
    Provide a clean database for each test.

    This fixture automatically cleans up after the test.
    The actual cleanup is handled by pytest-django's transaction rollback.
    """
    yield
    # Cleanup is automatic via pytest-django's transaction rollback


# ============================================================================
# Path Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_data_dir(project_root: Path) -> Path:
    """Return the path to the test_data directory."""
    test_data = project_root / "test_data"
    assert test_data.exists(), f"test_data directory not found at {test_data}"
    return test_data


@pytest.fixture(scope="session")
def e2e_test_data_dir(test_data_dir: Path) -> Path:
    """Return the path to the e2e test data directory."""
    e2e_dir = test_data_dir / "e2e"
    # Create if it doesn't exist
    e2e_dir.mkdir(parents=True, exist_ok=True)
    return e2e_dir


# ============================================================================
# User Fixtures
# ============================================================================

@pytest.fixture
def admin_user(db) -> User:
    """
    Create a superuser with all permissions.

    Use this for tests that require unrestricted access.
    """
    user = User.objects.create_superuser(
        username="admin",
        email="admin@test.local",
        password="adminpass123",
        first_name="Admin",
        last_name="User",
    )
    return user


@pytest.fixture
def staff_user(db) -> User:
    """
    Create a staff user (can access dashboard).

    This represents a Copyright Office employee.
    """
    user = User.objects.create_user(
        username="staff",
        email="staff@test.local",
        password="staffpass123",
        first_name="Staff",
        last_name="User",
        is_staff=True,
    )
    return user


@pytest.fixture
def faculty_user(db) -> User:
    """
    Create a regular faculty user with limited permissions.

    This represents a faculty member who can only view/edit their own items.
    """
    user = User.objects.create_user(
        username="faculty",
        email="faculty@test.local",
        password="facultypass123",
        first_name="Faculty",
        last_name="User",
        is_staff=False,
    )
    return user


# ============================================================================
# Client Fixtures
# ============================================================================

@pytest.fixture
def authenticated_client(client: Client, staff_user: User) -> Client:
    """
    Return a Django test client that is already authenticated as a staff user.

    This is the most commonly used client for testing dashboard functionality.
    """
    client.force_login(staff_user)
    return client


@pytest.fixture
def admin_client(client: Client, admin_user: User) -> Client:
    """
    Return a Django test client that is already authenticated as an admin user.

    Use this for tests that require admin privileges.
    """
    client.force_login(admin_user)
    return client


@pytest.fixture
def faculty_client(client: Client, faculty_user: User) -> Client:
    """
    Return a Django test client that is already authenticated as a faculty user.

    Use this for testing permission-restricted functionality.
    """
    client.force_login(faculty_user)
    return client


# ============================================================================
# External API Credential Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def osiris_test_credentials() -> dict:
    """
    Return real Osiris test API credentials from environment variables.

    These credentials point to the actual Osiris test environment.
    Tests that use these should be marked with @pytest.mark.external_api.

    To skip tests that require external APIs:
        pytest -m "not external_api"
    """
    return {
        "base_url": os.getenv(
            "TEST_OSIRIS_URL",
            "https://utwente.osiris-student.nl"
        ),
        "test_course_code": os.getenv("TEST_OSIRIS_COURSE_CODE", "191154340"),
    }


@pytest.fixture(scope="session")
def canvas_test_credentials() -> dict:
    """
    Return real Canvas test API credentials from environment variables.

    These credentials point to the actual Canvas test environment.
    Tests that use these should be marked with @pytest.mark.external_api.

    To skip tests that require external APIs:
        pytest -m "not external_api"
    """
    token = os.getenv("TEST_CANVAS_API_TOKEN")
    if not token:
        # Fallback to production token (not recommended for automated tests)
        token = os.getenv("CANVAS_API_TOKEN", "")

    return {
        "base_url": os.getenv(
            "TEST_CANVAS_API_URL",
            "https://utwente.instructure.com/api/v1"
        ),
        "token": token,
    }


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def base_case_5_file(e2e_test_data_dir: Path) -> Path:
    """
    Return the path to the base case test file with 5 items.

    This file should be created by running:
        python scripts/create_test_data.py

    If the file doesn't exist, the test will be skipped.
    """
    file_path = e2e_test_data_dir / "base_case_5.xlsx"
    return file_path


# ============================================================================
# Test Markers Documentation
# ============================================================================

def pytest_configure(config):
    """
    Configure custom pytest markers.

    This makes the markers available to all tests and allows
    pytest to validate marker usage with --strict-markers.
    """
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers",
        "external_api: marks tests that hit real external APIs "
        "(requires network and credentials)"
    )
    config.addinivalue_line(
        "markers",
        "pipeline: marks end-to-end pipeline tests"
    )
    config.addinivalue_line(
        "markers",
        "unit: marks fast unit tests"
    )
    config.addinivalue_line(
        "markers",
        "integration: marks integration tests"
    )
    config.addinivalue_line(
        "markers",
        "e2e: marks full end-to-end tests"
    )
    config.addinivalue_line(
        "markers",
        "htmx: marks HTMX-specific tests"
    )
    config.addinivalue_line(
        "markers",
        "playwright: marks browser UI tests (skipped by default)"
    )
