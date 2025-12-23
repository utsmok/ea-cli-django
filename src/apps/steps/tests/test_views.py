"""
Tests for steps app views.

Tests the UI for each processing step.
"""

import pytest
from django.test import Client
from django.urls import reverse

from apps.core.models import CopyrightItem
from apps.users.models import User


@pytest.fixture
def client():
    """Django test client."""
    return Client()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )


@pytest.fixture
def authenticated_client(client, user):
    """Client authenticated with test user."""
    client.login(username="testuser", password="testpass123")
    return client


@pytest.mark.django_db
class TestStepsIndex:
    """Tests for steps index page."""

    def test_steps_index_requires_login(self, client):
        """Steps index requires authentication."""
        url = reverse("steps:index")
        response = client.get(url)
        assert response.status_code == 302  # Redirect to login

    def test_steps_index_authenticated(self, authenticated_client):
        """Authenticated user can access steps index."""
        url = reverse("steps:index")
        response = authenticated_client.get(url)
        assert response.status_code == 200
        assert b"Processing Steps" in response.content


@pytest.mark.django_db
class TestIngestQlikStep:
    """Tests for Qlik ingestion step."""

    def test_ingest_qlik_requires_login(self, client):
        """Qlik ingestion step requires authentication."""
        url = reverse("steps:ingest_qlik")
        response = client.get(url)
        assert response.status_code == 302

    def test_ingest_qlik_authenticated(self, authenticated_client):
        """Authenticated user can access Qlik ingestion step."""
        url = reverse("steps:ingest_qlik")
        response = authenticated_client.get(url)
        assert response.status_code == 200
        assert b"Ingest Qlik Export" in response.content
        assert b"Upload Qlik Export File" in response.content


@pytest.mark.django_db
class TestIngestFacultyStep:
    """Tests for Faculty sheet ingestion step."""

    def test_ingest_faculty_requires_login(self, client):
        """Faculty ingestion step requires authentication."""
        url = reverse("steps:ingest_faculty")
        response = client.get(url)
        assert response.status_code == 302

    def test_ingest_faculty_authenticated(self, authenticated_client):
        """Authenticated user can access Faculty ingestion step."""
        url = reverse("steps:ingest_faculty")
        response = authenticated_client.get(url)
        assert response.status_code == 200
        assert b"Ingest Faculty Sheet" in response.content
        assert b"Faculty Code" in response.content


@pytest.mark.django_db
class TestEnrichOsirisStep:
    """Tests for Osiris enrichment step."""

    def test_enrich_osiris_requires_login(self, client):
        """Osiris enrichment step requires authentication."""
        url = reverse("steps:enrich_osiris")
        response = client.get(url)
        assert response.status_code == 302

    def test_enrich_osiris_authenticated(self, authenticated_client):
        """Authenticated user can access Osiris enrichment step."""
        url = reverse("steps:enrich_osiris")
        response = authenticated_client.get(url)
        assert response.status_code == 200
        assert b"Enrich from Osiris" in response.content

    def test_enrich_osiris_shows_items(self, authenticated_client):
        """Osiris enrichment step shows items that need enrichment."""
        # Create test items
        CopyrightItem.objects.create(
            material_id=1, title="Test Item 1", course_code="123456789"
        )
        CopyrightItem.objects.create(
            material_id=2, title="Test Item 2", course_code="987654321"
        )

        url = reverse("steps:enrich_osiris")
        response = authenticated_client.get(url)
        assert response.status_code == 200
        assert b"Test Item 1" in response.content or b"123456789" in response.content


@pytest.mark.django_db
class TestPDFCanvasStatusStep:
    """Tests for PDF Canvas status step."""

    def test_pdf_canvas_status_requires_login(self, client):
        """PDF Canvas status step requires authentication."""
        url = reverse("steps:pdf_canvas_status")
        response = client.get(url)
        assert response.status_code == 302

    def test_pdf_canvas_status_authenticated(self, authenticated_client):
        """Authenticated user can access PDF Canvas status step."""
        url = reverse("steps:pdf_canvas_status")
        response = authenticated_client.get(url)
        assert response.status_code == 200
        assert b"Get PDF Status from Canvas" in response.content


@pytest.mark.django_db
class TestPDFExtractStep:
    """Tests for PDF extraction step."""

    def test_pdf_extract_requires_login(self, client):
        """PDF extraction step requires authentication."""
        url = reverse("steps:pdf_extract")
        response = client.get(url)
        assert response.status_code == 302

    def test_pdf_extract_authenticated(self, authenticated_client):
        """Authenticated user can access PDF extraction step."""
        url = reverse("steps:pdf_extract")
        response = authenticated_client.get(url)
        assert response.status_code == 200
        assert b"Extract PDF Details" in response.content


@pytest.mark.django_db
class TestExportFacultyStep:
    """Tests for faculty export step."""

    def test_export_faculty_requires_login(self, client):
        """Faculty export step requires authentication."""
        url = reverse("steps:export_faculty")
        response = client.get(url)
        assert response.status_code == 302

    def test_export_faculty_authenticated(self, authenticated_client):
        """Authenticated user can access faculty export step."""
        url = reverse("steps:export_faculty")
        response = authenticated_client.get(url)
        assert response.status_code == 200
        assert b"Export Faculty Sheets" in response.content
