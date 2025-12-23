"""
Tests for ingestion dashboard views.
"""

import pytest
from django.urls import reverse

from apps.ingest.models import IngestionBatch
from apps.users.models import User


def test_upload_requires_faculty_code_for_faculty_sheets(
    authenticated_client, tmp_path
):
    """Faculty sheets should require faculty_code."""
    # Create a dummy file
    test_file = tmp_path / "test.xlsx"
    test_file.write_bytes(b"dummy content")

    with open(test_file, "rb") as f:
        response = authenticated_client.post(
            reverse("ingest:upload"),
            {
                "source_type": "FACULTY",
                "file": f,
            },
        )

    # Should redirect back with error
    assert response.status_code == 302


@pytest.fixture
def test_user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )


@pytest.fixture
def authenticated_client(client, test_user):
    """Create an authenticated client."""
    client.login(username="testuser", password="testpass123")
    return client


@pytest.mark.django_db
class TestDashboardViews:
    """Test dashboard views."""

    def test_dashboard_requires_auth(self, client):
        """Dashboard should require authentication."""
        response = client.get(reverse("ingest:dashboard"))
        assert response.status_code == 302  # Redirect to login

    def test_dashboard_shows_stats(self, authenticated_client, test_user):
        """Dashboard should show batch statistics."""
        # Create some test batches
        IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            uploaded_by=test_user,
            status=IngestionBatch.Status.COMPLETED,
        )
        IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.FACULTY,
            uploaded_by=test_user,
            status=IngestionBatch.Status.PENDING,
        )

        response = authenticated_client.get(reverse("ingest:dashboard"))
        assert response.status_code == 200
        assert "stats" in response.context
        assert response.context["stats"]["total_batches"] == 2

    def test_upload_page_loads(self, authenticated_client):
        """Upload page should load successfully."""
        response = authenticated_client.get(reverse("ingest:upload"))
        assert response.status_code == 200
        assert b"Upload" in response.content

    def test_batch_list_loads(self, authenticated_client, test_user):
        """Batch list should load successfully."""
        # Create a test batch
        IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            uploaded_by=test_user,
        )

        response = authenticated_client.get(reverse("ingest:batch_list"))
        assert response.status_code == 200
        assert b"Batches" in response.content

    def test_batch_detail_loads(self, authenticated_client, test_user):
        """Batch detail should load successfully."""
        batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            uploaded_by=test_user,
        )

        response = authenticated_client.get(
            reverse("ingest:batch_detail", args=[batch.id])
        )
        assert response.status_code == 200
        assert f"Batch #{batch.id}".encode() in response.content

    def test_batch_status_api(self, authenticated_client, test_user):
        """Batch status API should return JSON."""
        batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            uploaded_by=test_user,
            total_rows=100,
            items_created=50,
        )

        response = authenticated_client.get(
            reverse("ingest:batch_status_api", args=[batch.id])
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == batch.id
        assert data["status"] == "PENDING"
        assert data["progress"]["total_rows"] == 100
        assert data["progress"]["items_created"] == 50


@pytest.mark.django_db
class TestUploadView:
    """Test file upload functionality."""

    def test_upload_requires_file(self, authenticated_client):
        """Upload should require a file."""
        response = authenticated_client.post(
            reverse("ingest:upload"),
            {
                "source_type": "QLIK",
            },
        )
        # Should redirect back to upload form
        assert response.status_code == 302

    def test_upload_requires_faculty_code_for_faculty_sheets(
        self, authenticated_client, tmp_path
    ):
        """Faculty sheets should require faculty_code."""
        # Create a dummy file
        test_file = tmp_path / "test.xlsx"
        test_file.write_bytes(b"dummy content")

        with open(test_file, "rb") as f:
            response = authenticated_client.post(
                reverse("ingest:upload"),
                {
                    "source_type": "FACULTY",
                    "file": f,
                },
            )

        # Should redirect back with error
        assert response.status_code == 302


@pytest.mark.django_db
def test_batch_list_filtering(authenticated_client, test_user):
    """Test batch list filtering."""
    # Create batches with different statuses
    IngestionBatch.objects.create(
        source_type=IngestionBatch.SourceType.QLIK,
        uploaded_by=test_user,
        status=IngestionBatch.Status.COMPLETED,
    )
    IngestionBatch.objects.create(
        source_type=IngestionBatch.SourceType.FACULTY,
        uploaded_by=test_user,
        status=IngestionBatch.Status.PENDING,
        faculty_code="EEMCS",
    )

    # Filter by status
    response = authenticated_client.get(
        reverse("ingest:batch_list") + "?status=COMPLETED"
    )
    assert response.status_code == 200
    assert len(response.context["batches"]) == 1

    # Filter by source type
    response = authenticated_client.get(
        reverse("ingest:batch_list") + "?source_type=FACULTY"
    )
    assert response.status_code == 200
    assert len(response.context["batches"]) == 1

    # Filter by faculty
    response = authenticated_client.get(reverse("ingest:batch_list") + "?faculty=EEMCS")
    assert response.status_code == 200
    assert len(response.context["batches"]) == 1
