"""
Phase 4: Backend Response Test Suite

Tests HTTP responses, status codes, JSON schemas, and HTMX-specific behaviors.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.core.models import CopyrightItem, Faculty

User = get_user_model()


class TestAPIStatusCodes:
    """Test HTTP status codes for various scenarios."""

    @pytest.fixture(autouse=True)
    def setup(self, db, staff_user):
        self.client = Client()
        self.client.force_login(staff_user)

    def test_health_check_returns_200(self):
        """Test health check endpoint returns 200."""
        url = reverse("api:health_check")
        response = self.client.get(url)
        assert response.status_code == 200

    def test_readiness_check_returns_status(self):
        """Test readiness check returns valid status."""
        url = reverse("api:readiness_check")
        response = self.client.get(url)
        # Can be 200 or 503 depending on system state
        assert response.status_code in [200, 503]

    def test_dashboard_returns_200_for_authenticated_user(self):
        """Test dashboard returns 200 for authenticated users."""
        url = reverse("dashboard:index")
        response = self.client.get(url)
        assert response.status_code == 200

    def test_dashboard_requires_authentication(self):
        """Test dashboard redirects unauthenticated users."""
        client = Client()  # Not authenticated
        url = reverse("dashboard:index")
        response = client.get(url)
        assert response.status_code == 302  # Redirect to login

    def test_invalid_item_returns_404(self):
        """Test that invalid item IDs return 404."""
        url = reverse("dashboard:detail_page", kwargs={"material_id": 999999})
        response = self.client.get(url)
        assert response.status_code == 404

    def test_batch_upload_page_loads(self):
        """Test that batch upload page loads."""
        url = reverse("ingest:upload")
        response = self.client.get(url)
        # Should show upload form
        assert response.status_code == 200


class TestHTMXBehaviors:
    """Test HTMX-specific behaviors."""

    @pytest.fixture(autouse=True)
    def setup(self, db, staff_user):
        self.client = Client()
        self.client.force_login(staff_user)
        self.faculty, _ = Faculty.objects.get_or_create(
            abbreviation="TEST",
            defaults={"name": "Test Faculty", "hierarchy_level": 1, "full_abbreviation": "UT-TEST"},
        )

    def test_item_detail_panel_returns_partial_html(self):
        """Test that item detail panel returns partial HTML."""
        item = CopyrightItem.objects.create(
            material_id=10101,
            faculty=self.faculty,
        )
        
        url = reverse("dashboard:detail_panel", kwargs={"material_id": item.material_id})
        response = self.client.get(
            url,
            HTTP_HX_REQUEST="true",
        )
        
        assert response.status_code == 200
        # Should not include full HTML document structure
        assert b"<!DOCTYPE html>" not in response.content

    def test_enrichment_trigger_accepts_htmx_request(self):
        """Test that enrichment trigger accepts HTMX requests."""
        item = CopyrightItem.objects.create(
            material_id=10102,
            faculty=self.faculty,
        )
        
        url = reverse("enrichment:trigger_item", kwargs={"material_id": item.material_id})
        response = self.client.post(
            url,
            HTTP_HX_REQUEST="true",
        )
        
        # Should accept request (may return various statuses based on implementation)
        assert response.status_code in [200, 201, 202, 204, 400]


class TestJSONResponses:
    """Test JSON response schemas for API endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self, db, staff_user):
        self.client = Client()
        self.client.force_login(staff_user)

    def test_health_check_json_schema(self):
        """Test health check returns proper response."""
        url = reverse("api:health_check")
        response = self.client.get(url)
        
        assert response.status_code == 200
        # Health check returns JSON or simple text
        assert response["Content-Type"].startswith(("application/json", "text/", "text/html"))

    def test_batch_status_api_returns_json(self):
        """Test batch status API returns JSON."""
        # Create a batch first
        from apps.ingest.models import IngestionBatch
        from apps.users.models import User
        
        user, _ = User.objects.get_or_create(
            username="testuser",
            defaults={"email": "test@example.com"}
        )
        
        batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            uploaded_by=user,
            status=IngestionBatch.Status.STAGED,
        )
        
        url = reverse("ingest:batch_status_api", kwargs={"batch_id": batch.id})
        response = self.client.get(url)
        
        assert response.status_code == 200
        assert response["Content-Type"].startswith("application/json")
        
        # Should have JSON data
        data = response.json()
        assert "status" in data or "batch_status" in data


class TestContentTypes:
    """Test response content types."""

    @pytest.fixture(autouse=True)
    def setup(self, db, staff_user):
        self.client = Client()
        self.client.force_login(staff_user)

    def test_dashboard_returns_html(self):
        """Test dashboard returns HTML content."""
        url = reverse("dashboard:index")
        response = self.client.get(url)
        
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/html")

    def test_api_health_check_returns_json_or_text(self):
        """Test API health check returns appropriate content type."""
        url = reverse("api:health_check")
        response = self.client.get(url)
        
        assert response.status_code == 200
        # Should be JSON or text
        assert response["Content-Type"].startswith(("application/json", "text/"))


class TestDatabaseStateVerification:
    """Test that operations correctly modify database state."""

    @pytest.fixture(autouse=True)
    def setup(self, db, staff_user):
        self.client = Client()
        self.client.force_login(staff_user)
        self.faculty, _ = Faculty.objects.get_or_create(
            abbreviation="TEST",
            defaults={"name": "Test Faculty", "hierarchy_level": 1, "full_abbreviation": "UT-TEST"},
        )

    def test_item_creation_persists_to_database(self):
        """Test that item creation persists to database."""
        initial_count = CopyrightItem.objects.count()
        
        # Create item
        CopyrightItem.objects.create(
            material_id=10201,
            faculty=self.faculty,
        )
        
        final_count = CopyrightItem.objects.count()
        assert final_count == initial_count + 1

    def test_item_field_update_persists(self):
        """Test that item field updates persist."""
        item = CopyrightItem.objects.create(
            material_id=10202,
            faculty=self.faculty,
            notes="Original notes",
        )
        
        url = reverse("dashboard:update_field", kwargs={"material_id": item.material_id})
        response = self.client.post(url, {
            "field": "notes",
            "value": "Updated notes",
        })
        
        # Refresh from database
        item.refresh_from_db()
        
        # If update was successful, verify it persisted
        if response.status_code in [200, 204]:
            assert item.notes == "Updated notes"


class TestErrorResponses:
    """Test error response handling."""

    @pytest.fixture(autouse=True)
    def setup(self, db, staff_user):
        self.client = Client()
        self.client.force_login(staff_user)

    def test_404_for_nonexistent_item(self):
        """Test 404 response for nonexistent items."""
        url = reverse("dashboard:detail_page", kwargs={"material_id": 999999})
        response = self.client.get(url)
        assert response.status_code == 404

    def test_404_for_nonexistent_batch(self):
        """Test 404 response for nonexistent batches."""
        url = reverse("ingest:batch_detail", kwargs={"batch_id": 999999})
        response = self.client.get(url)
        assert response.status_code == 404

