"""
URL resolution and routing tests for the ingest app.

Tests verify:
- URL patterns resolve to correct views
- Authentication requirements are enforced
- Batch operations work correctly
- Status API endpoints return proper JSON
"""
import pytest
from django.test import Client
from django.urls import reverse

from apps.ingest.models import IngestionBatch


class TestIngestURLs:
    """Test URL resolution and routing for ingest views."""

    # =========================================================================
    # URL Resolution Tests
    # =========================================================================

    @pytest.mark.django_db
    def test_ingest_dashboard_url_resolves(self, authenticated_client):
        """Test that ingest dashboard URL resolves correctly."""
        url = reverse("ingest:dashboard")
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_ingest_upload_url_resolves(self, authenticated_client):
        """Test that ingest upload URL resolves correctly."""
        url = reverse("ingest:upload")
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_batch_list_url_resolves(self, authenticated_client):
        """Test that batch list URL resolves correctly."""
        url = reverse("ingest:batch_list")
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_batch_detail_url_resolves(self, authenticated_client, staff_user):
        """Test that batch detail URL resolves correctly."""
        batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            source_file="test.xlsx",
            uploaded_by=staff_user,
        )

        url = reverse("ingest:batch_detail", kwargs={"batch_id": batch.id})
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_batch_process_url_resolves(self, authenticated_client, staff_user):
        """Test that batch process URL resolves correctly."""
        batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            source_file="test.xlsx",
            uploaded_by=staff_user,
        )

        url = reverse("ingest:batch_process", kwargs={"batch_id": batch.id})
        # This is likely POST-only
        response = authenticated_client.post(url)
        assert response.status_code in [200, 302, 400]

    @pytest.mark.django_db
    def test_batch_status_api_url_resolves(self, authenticated_client, staff_user):
        """Test that batch status API URL resolves correctly."""
        batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            source_file="test.xlsx",
            uploaded_by=staff_user,
        )

        url = reverse("ingest:batch_status_api", kwargs={"batch_id": batch.id})
        response = authenticated_client.get(url)
        # Should return JSON response
        assert response.status_code == 200
        assert response["Content-Type"].startswith("application/json")

    @pytest.mark.django_db
    def test_batch_status_partial_url_resolves(self, authenticated_client, staff_user):
        """Test that batch status partial URL resolves correctly."""
        batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            source_file="test.xlsx",
            uploaded_by=staff_user,
        )

        url = reverse("ingest:batch_status_partial", kwargs={"batch_id": batch.id})
        response = authenticated_client.get(url)
        # Should return HTML partial for HTMX
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_export_faculty_sheets_url_resolves(self, authenticated_client):
        """Test that export faculty sheets URL resolves correctly."""
        url = reverse("ingest:export_faculty_sheets")
        response = authenticated_client.get(url)
        assert response.status_code in [200, 302]

    @pytest.mark.django_db
    def test_download_export_url_resolves(self, authenticated_client):
        """Test that download export URL resolves correctly."""
        # Note: This requires an actual export file to exist
        # For now, just test URL resolution
        url = reverse(
            "ingest:download_export",
            kwargs={"faculty": "EEMCS", "filename": "test_export.xlsx"},
        )
        response = authenticated_client.get(url)
        # Will return 404 if file doesn't exist, which is expected
        assert response.status_code in [200, 404]

    # =========================================================================
    # Authentication Tests
    # =========================================================================

    @pytest.mark.django_db
    def test_ingest_dashboard_requires_authentication(self, client):
        """Test that ingest dashboard redirects anonymous users to login."""
        url = reverse("ingest:dashboard")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    @pytest.mark.django_db
    def test_batch_list_requires_authentication(self, client):
        """Test that batch list requires authentication."""
        url = reverse("ingest:batch_list")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    @pytest.mark.django_db
    def test_batch_operations_require_authentication(self, client, staff_user):
        """Test that batch operations require authentication."""
        batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            source_file="test.xlsx",
            uploaded_by=staff_user,
        )

        url = reverse("ingest:batch_detail", kwargs={"batch_id": batch.id})
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    # =========================================================================
    # Invalid Parameter Tests
    # =========================================================================

    @pytest.mark.django_db
    def test_nonexistent_batch_returns_404(self, authenticated_client):
        """Test that requesting a non-existent batch returns 404."""
        url = reverse("ingest:batch_detail", kwargs={"batch_id": 99999})
        response = authenticated_client.get(url)
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_nonexistent_batch_status_api_returns_404(self, authenticated_client):
        """Test that status API for non-existent batch returns 404."""
        url = reverse("ingest:batch_status_api", kwargs={"batch_id": 99999})
        response = authenticated_client.get(url)
        assert response.status_code == 404

    # =========================================================================
    # HTTP Method Tests
    # =========================================================================

    @pytest.mark.django_db
    def test_batch_process_accepts_post(self, authenticated_client, staff_user):
        """Test that batch process accepts POST requests."""
        batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            source_file="test.xlsx",
            uploaded_by=staff_user,
        )

        url = reverse("ingest:batch_process", kwargs={"batch_id": batch.id})
        response = authenticated_client.post(url)
        # Should return 302 (redirect after processing) or 200
        assert response.status_code in [200, 302]

    @pytest.mark.django_db
    def test_upload_accepts_post(self, authenticated_client):
        """Test that upload accepts POST requests with file."""
        url = reverse("ingest:upload")
        # GET should work
        response = authenticated_client.get(url)
        assert response.status_code == 200

        # POST without file should return error or redirect
        response = authenticated_client.post(url, {})
        assert response.status_code in [200, 302, 400]

    # =========================================================================
    # Status API Tests
    # =========================================================================

    @pytest.mark.django_db
    def test_batch_status_api_returns_json(self, authenticated_client, staff_user):
        """Test that batch status API returns JSON response."""
        batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            source_file="test.xlsx",
            uploaded_by=staff_user,
            status=IngestionBatch.Status.STAGED,
        )

        url = reverse("ingest:batch_status_api", kwargs={"batch_id": batch.id})
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"].startswith("application/json")

        # Verify JSON structure
        import json

        data = json.loads(response.content)
        assert "batch_id" in data or "status" in data

    @pytest.mark.django_db
    def test_batch_status_partial_returns_html(self, authenticated_client, staff_user):
        """Test that batch status partial returns HTML fragment."""
        batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            source_file="test.xlsx",
            uploaded_by=staff_user,
        )

        url = reverse("ingest:batch_status_partial", kwargs={"batch_id": batch.id})
        response = authenticated_client.get(url)

        assert response.status_code == 200
        # Should return HTML (not JSON)
        assert response["Content-Type"].startswith("text/html")
