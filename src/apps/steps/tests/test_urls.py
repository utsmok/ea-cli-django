"""
URL resolution and routing tests for the steps app.

Tests verify:
- URL patterns resolve to correct views
- Authentication requirements are enforced
- All 7 processing steps have correct routes
- Run and status endpoints work correctly
"""
import pytest
from django.urls import reverse


class TestStepsURLs:
    """Test URL resolution and routing for steps views."""

    # =========================================================================
    # Steps Index
    # =========================================================================

    @pytest.mark.django_db
    def test_steps_index_url_resolves(self, authenticated_client):
        """Test that steps index URL resolves correctly."""
        url = reverse("steps:index")
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_steps_index_requires_authentication(self, client):
        """Test that steps index requires authentication."""
        url = reverse("steps:index")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    # =========================================================================
    # Step 1: Ingest Qlik Export
    # =========================================================================

    @pytest.mark.django_db
    def test_ingest_qlik_step_url_resolves(self, authenticated_client):
        """Test that ingest Qlik step URL resolves correctly."""
        url = reverse("steps:ingest_qlik")
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_ingest_qlik_requires_authentication(self, client):
        """Test that ingest Qlik step requires authentication."""
        url = reverse("steps:ingest_qlik")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    # =========================================================================
    # Step 2: Ingest Faculty Sheet
    # =========================================================================

    @pytest.mark.django_db
    def test_ingest_faculty_step_url_resolves(self, authenticated_client):
        """Test that ingest faculty step URL resolves correctly."""
        url = reverse("steps:ingest_faculty")
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_ingest_faculty_requires_authentication(self, client):
        """Test that ingest faculty step requires authentication."""
        url = reverse("steps:ingest_faculty")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    # =========================================================================
    # Step 3: Enrich from Osiris
    # =========================================================================

    @pytest.mark.django_db
    def test_enrich_osiris_step_url_resolves(self, authenticated_client):
        """Test that enrich Osiris step URL resolves correctly."""
        url = reverse("steps:enrich_osiris")
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_run_enrich_osiris_url_resolves(self, authenticated_client):
        """Test that run enrich Osiris URL resolves correctly."""
        url = reverse("steps:run_enrich_osiris")
        response = authenticated_client.post(url)
        # POST should trigger enrichment (or 400 if params missing)
        assert response.status_code in [200, 302, 202, 400]

    @pytest.mark.django_db
    def test_enrich_osiris_status_url_resolves(self, authenticated_client):
        """Test that enrich Osiris status URL resolves correctly."""
        url = reverse("steps:enrich_osiris_status")
        response = authenticated_client.get(url)
        # Should return status (JSON or HTML partial) or 400 if missing params
        assert response.status_code in [200, 400]

    @pytest.mark.django_db
    def test_enrich_osiris_requires_authentication(self, client):
        """Test that enrich Osiris requires authentication."""
        url = reverse("steps:enrich_osiris")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    # =========================================================================
    # Step 4: Enrich from People Pages
    # =========================================================================

    @pytest.mark.django_db
    def test_enrich_people_step_url_resolves(self, authenticated_client):
        """Test that enrich people step URL resolves correctly."""
        url = reverse("steps:enrich_people")
        response = authenticated_client.get(url)
        # Might redirect if previous steps not complete
        assert response.status_code in [200, 302]

    @pytest.mark.django_db
    def test_run_enrich_people_url_resolves(self, authenticated_client):
        """Test that run enrich people URL resolves correctly."""
        url = reverse("steps:run_enrich_people")
        response = authenticated_client.post(url)
        # POST should trigger enrichment (or 400 if params missing)
        assert response.status_code in [200, 302, 202, 400]

    @pytest.mark.django_db
    def test_enrich_people_status_url_resolves(self, authenticated_client):
        """Test that enrich people status URL resolves correctly."""
        url = reverse("steps:enrich_people_status")
        response = authenticated_client.get(url)
        # Should return status (JSON or HTML partial) or 400 if missing params
        assert response.status_code in [200, 400]

    @pytest.mark.django_db
    def test_enrich_people_requires_authentication(self, client):
        """Test that enrich people requires authentication."""
        url = reverse("steps:enrich_people")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    # =========================================================================
    # Step 5: Get PDF Status from Canvas
    # =========================================================================

    @pytest.mark.django_db
    def test_pdf_canvas_status_step_url_resolves(self, authenticated_client):
        """Test that PDF Canvas status step URL resolves correctly."""
        url = reverse("steps:pdf_canvas_status")
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_run_pdf_canvas_status_url_resolves(self, authenticated_client):
        """Test that run PDF Canvas status URL resolves correctly."""
        url = reverse("steps:run_pdf_canvas_status")
        response = authenticated_client.post(url)
        # POST should trigger Canvas check (or 400 if params missing)
        assert response.status_code in [200, 302, 202, 400]

    @pytest.mark.django_db
    def test_pdf_canvas_status_status_url_resolves(self, authenticated_client):
        """Test that PDF Canvas status status URL resolves correctly."""
        url = reverse("steps:pdf_canvas_status_status")
        response = authenticated_client.get(url)
        # Should return status (JSON or HTML partial)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_pdf_canvas_status_requires_authentication(self, client):
        """Test that PDF Canvas status requires authentication."""
        url = reverse("steps:pdf_canvas_status")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    # =========================================================================
    # Step 6: Extract PDF Details
    # =========================================================================

    @pytest.mark.django_db
    def test_pdf_extract_step_url_resolves(self, authenticated_client):
        """Test that PDF extract step URL resolves correctly."""
        url = reverse("steps:pdf_extract")
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_run_pdf_extract_url_resolves(self, authenticated_client):
        """Test that run PDF extract URL resolves correctly."""
        url = reverse("steps:run_pdf_extract")
        response = authenticated_client.post(url)
        # POST should trigger extraction (or 400 if params missing)
        assert response.status_code in [200, 302, 202, 400]

    @pytest.mark.django_db
    def test_pdf_extract_status_url_resolves(self, authenticated_client):
        """Test that PDF extract status URL resolves correctly."""
        url = reverse("steps:pdf_extract_status")
        response = authenticated_client.get(url)
        # Should return status (JSON or HTML partial)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_pdf_extract_requires_authentication(self, client):
        """Test that PDF extract requires authentication."""
        url = reverse("steps:pdf_extract")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    # =========================================================================
    # Step 7: Export Faculty Sheets
    # =========================================================================

    @pytest.mark.django_db
    def test_export_faculty_step_url_resolves(self, authenticated_client):
        """Test that export faculty step URL resolves correctly."""
        url = reverse("steps:export_faculty")
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_run_export_faculty_url_resolves(self, authenticated_client):
        """Test that run export faculty URL resolves correctly."""
        url = reverse("steps:run_export_faculty")
        response = authenticated_client.post(url)
        # POST should trigger export (or 400 if params missing)
        assert response.status_code in [200, 302, 202, 400]

    @pytest.mark.django_db
    def test_download_export_file_url_resolves(self, authenticated_client):
        """Test that download export file URL resolves correctly."""
        # Note: This requires an actual export to exist
        # For now, just test URL resolution
        url = reverse("steps:download_export_file", kwargs={"export_id": 1, "file_index": 0})
        response = authenticated_client.get(url)
        # Will return 404 if export doesn't exist, which is expected
        assert response.status_code in [200, 404]

    @pytest.mark.django_db
    def test_download_export_file_invalid_parameters(self, authenticated_client):
        """Test that download export file with invalid parameters returns 404."""
        url = reverse(
            "steps:download_export_file", kwargs={"export_id": 99999, "file_index": 0}
        )
        response = authenticated_client.get(url)
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_export_faculty_requires_authentication(self, client):
        """Test that export faculty requires authentication."""
        url = reverse("steps:export_faculty")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    # =========================================================================
    # HTTP Method Tests
    # =========================================================================

    @pytest.mark.django_db
    def test_all_step_pages_accept_get(self, authenticated_client):
        """Test that all step pages accept GET requests."""
        step_urls = [
            "steps:ingest_qlik",
            "steps:ingest_faculty",
            "steps:enrich_osiris",
            "steps:enrich_people",
            "steps:pdf_canvas_status",
            "steps:pdf_extract",
            "steps:export_faculty",
        ]

        for url_name in step_urls:
            url = reverse(url_name)
            response = authenticated_client.get(url)
            assert response.status_code in [200, 302], f"Failed for {url_name}"

    @pytest.mark.django_db
    def test_all_run_endpoints_accept_post(self, authenticated_client):
        """Test that all run endpoints accept POST requests."""
        run_urls = [
            "steps:run_enrich_osiris",
            "steps:run_enrich_people",
            "steps:run_pdf_canvas_status",
            "steps:run_pdf_extract",
            "steps:run_export_faculty",
        ]

        for url_name in run_urls:
            url = reverse(url_name)
            response = authenticated_client.post(url)
            # Should accept POST (might return 302 redirect, 200, or 202)
            assert response.status_code in [200, 302, 202, 400], f"Failed for {url_name}"

    @pytest.mark.django_db
    def test_all_status_endpoints_accept_get(self, authenticated_client):
        """Test that all status endpoints accept GET requests."""
        status_urls = [
            "steps:enrich_osiris_status",
            "steps:enrich_people_status",
            "steps:pdf_canvas_status_status",
            "steps:pdf_extract_status",
        ]

        for url_name in status_urls:
            url = reverse(url_name)
            response = authenticated_client.get(url)
            assert response.status_code in [200, 400], f"Failed for {url_name}"

    # =========================================================================
    # Response Format Tests
    # =========================================================================

    @pytest.mark.django_db
    def test_status_endpoints_return_json_or_html(self, authenticated_client):
        """Test that status endpoints return appropriate response format."""
        status_urls = [
            "steps:enrich_osiris_status",
            "steps:enrich_people_status",
            "steps:pdf_canvas_status_status",
            "steps:pdf_extract_status",
        ]

        for url_name in status_urls:
            url = reverse(url_name)
            response = authenticated_client.get(url)

            # Should return either JSON or HTML
            content_type = response["Content-Type"]
            assert content_type.startswith(
                ("application/json", "text/html")
            ), f"Invalid content type for {url_name}: {content_type}"
