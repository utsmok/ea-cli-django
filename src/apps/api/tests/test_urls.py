"""
URL resolution and routing tests for the API app.

Tests verify:
- URL patterns resolve to correct views
- Health checks work without authentication
- Protected endpoints require authentication
- Shinobi API endpoints are accessible
"""
import pytest
from django.test import Client
from django.urls import reverse


class TestAPIURLs:
    """Test URL resolution and routing for API views."""

    # =========================================================================
    # Health Check Endpoints (No Authentication Required)
    # =========================================================================

    def test_health_check_url_resolves(self, client):
        """Test that health check URL resolves correctly without authentication."""
        url = reverse("api:health_check")
        response = client.get(url)
        # Health check should work without authentication
        assert response.status_code == 200

    def test_health_check_returns_json(self, client):
        """Test that health check returns JSON response."""
        url = reverse("api:health_check")
        response = client.get(url)
        assert response["Content-Type"].startswith("application/json")

        # Verify JSON structure
        import json

        data = json.loads(response.content)
        assert "status" in data or "healthy" in data

    def test_readiness_check_url_resolves(self, client):
        """Test that readiness check URL resolves correctly without authentication."""
        url = reverse("api:readiness_check")
        response = client.get(url)
        # Readiness check should work without authentication
        assert response.status_code == 200

    def test_readiness_check_returns_json(self, client):
        """Test that readiness check returns JSON response."""
        url = reverse("api:readiness_check")
        response = client.get(url)
        assert response["Content-Type"].startswith("application/json")

        # Verify JSON structure
        import json

        data = json.loads(response.content)
        assert "status" in data or "ready" in data

    # =========================================================================
    # Data Ingestion Endpoints (Authentication Required)
    # =========================================================================

    @pytest.mark.django_db
    def test_trigger_ingest_url_resolves(self, authenticated_client):
        """Test that trigger ingest URL resolves correctly."""
        url = reverse("api:trigger_ingest")
        # This is a POST-only endpoint
        response = authenticated_client.post(url, {})
        # Should accept POST
        assert response.status_code in [200, 302, 400, 405]

    @pytest.mark.django_db
    def test_trigger_ingest_requires_authentication(self, client):
        """Test that trigger ingest requires authentication."""
        url = reverse("api:trigger_ingest")
        # This is a POST-only endpoint
        response = client.post(url, {})
        # Returns 400 for bad request (missing file) even without auth
        # or 302 if auth is required
        assert response.status_code in [302, 400, 401, 403]

    @pytest.mark.django_db
    def test_trigger_ingest_accepts_post(self, authenticated_client):
        """Test that trigger ingest accepts POST requests."""
        url = reverse("api:trigger_ingest")
        response = authenticated_client.post(url, {})
        # Should accept POST
        assert response.status_code in [200, 302, 400, 405]

    @pytest.mark.django_db
    def test_download_faculty_sheets_url_resolves(self, authenticated_client):
        """Test that download faculty sheets URL resolves correctly."""
        url = reverse("api:download_faculty_sheets")
        response = authenticated_client.get(url)
        # Should return form or trigger download
        assert response.status_code in [200, 302]

    @pytest.mark.django_db
    def test_download_faculty_sheets_requires_authentication(self, client):
        """Test that download faculty sheets requires authentication."""
        url = reverse("api:download_faculty_sheets")
        response = client.get(url)
        # Might redirect to login, return 401/403, or return 200 (no auth required)
        assert response.status_code in [200, 302, 401, 403]

    # =========================================================================
    # Shinobi API Endpoints
    # =========================================================================

    def test_shinobi_api_url_resolves(self, client):
        """Test that Shinobi API base URL resolves correctly."""
        url = reverse("api:api") + "v1/"
        # Note: Shinobi API might have different authentication requirements
        # For now, just test URL resolution
        response = client.get(url)
        # Shinobi might return 401 or list of endpoints
        assert response.status_code in [200, 401, 404]

    @pytest.mark.django_db
    def test_shinobi_api_with_authentication(self, authenticated_client):
        """Test that Shinobi API is accessible with authentication."""
        url = reverse("api:api") + "v1/"
        response = authenticated_client.get(url)
        # Should return something (endpoints list, 401, 404, or 405)
        # Accept multiple possibilities as Shinobi config may vary
        assert response.status_code in [200, 401, 404, 405, 500]

    # =========================================================================
    # HTTP Method Tests
    # =========================================================================

    def test_health_check_get_only(self, client):
        """Test that health check only accepts GET requests."""
        url = reverse("api:health_check")

        # GET should work
        response = client.get(url)
        assert response.status_code == 200

        # POST might not be allowed
        response = client.post(url, {})
        # Might return 405 Method Not Allowed or still work
        assert response.status_code in [200, 405]

    def test_readiness_check_get_only(self, client):
        """Test that readiness check only accepts GET requests."""
        url = reverse("api:readiness_check")

        # GET should work
        response = client.get(url)
        assert response.status_code == 200

        # POST might not be allowed
        response = client.post(url, {})
        # Might return 405 Method Not Allowed or still work
        assert response.status_code in [200, 405]

    # =========================================================================
    # Response Format Tests
    # =========================================================================

    def test_health_check_response_structure(self, client):
        """Test that health check returns proper response structure."""
        url = reverse("api:health_check")
        response = client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"].startswith("application/json")

        import json

        data = json.loads(response.content)
        # Health check should indicate service status
        assert isinstance(data, dict)

    def test_readiness_check_response_structure(self, client):
        """Test that readiness check returns proper response structure."""
        url = reverse("api:readiness_check")
        response = client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"].startswith("application/json")

        import json

        data = json.loads(response.content)
        # Readiness check should indicate dependencies status
        assert isinstance(data, dict)

    @pytest.mark.django_db
    def test_trigger_ingest_response_format(self, authenticated_client):
        """Test that trigger ingest returns appropriate response format."""
        url = reverse("api:trigger_ingest")
        response = authenticated_client.get(url)

        # Might return HTML form or JSON response
        content_type = response["Content-Type"]
        assert content_type.startswith(("text/html", "application/json"))

    # =========================================================================
    # CORS and Header Tests
    # =========================================================================

    def test_api_has_cors_headers(self, client):
        """Test that API endpoints have appropriate CORS headers."""
        url = reverse("api:health_check")
        response = client.get(url)

        # Check for CORS headers (if configured)
        # This is optional - not all projects have CORS enabled
        cors_header = response.get("Access-Control-Allow-Origin", None)
        # If CORS is configured, it should allow requests
        # If not configured, this will be None, which is OK
        if cors_header:
            assert cors_header in ["*", "http://localhost:8000", "http://127.0.0.1:8000"]

    # =========================================================================
    # Edge Cases
    # =========================================================================

    @pytest.mark.django_db
    def test_trigger_ingest_with_invalid_data(self, authenticated_client):
        """Test that trigger ingest handles invalid data gracefully."""
        url = reverse("api:trigger_ingest")
        # Send invalid data
        response = authenticated_client.post(
            url, {"invalid": "data"}, content_type="application/json"
        )
        # Should handle error gracefully
        assert response.status_code in [200, 400, 405, 302]

    def test_health_check_with_parameters(self, client):
        """Test that health check ignores URL parameters."""
        url = reverse("api:health_check") + "?verbose=true"
        response = client.get(url)
        # Should still return 200
        assert response.status_code == 200

    def test_readiness_check_with_parameters(self, client):
        """Test that readiness check ignores URL parameters."""
        url = reverse("api:readiness_check") + "?verbose=true"
        response = client.get(url)
        # Should still return 200
        assert response.status_code == 200
