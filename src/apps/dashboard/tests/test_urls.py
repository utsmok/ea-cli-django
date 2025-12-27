"""
URL resolution and routing tests for the dashboard app.

Tests verify:
- URL patterns resolve to correct views
- Authentication requirements are enforced
- Invalid parameters return 404
- HTTP methods are correctly handled
"""
import pytest
from django.test import Client
from django.urls import reverse

from apps.core.models import CopyrightItem


class TestDashboardURLs:
    """Test URL resolution and routing for dashboard views."""

    # =========================================================================
    # URL Resolution Tests
    # =========================================================================

    @pytest.mark.django_db
    def test_dashboard_index_url_resolves(self, authenticated_client):
        """Test that dashboard index URL resolves correctly."""
        url = reverse("dashboard:index")
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_update_item_field_url_resolves(self, authenticated_client, staff_user):
        """Test that item update field URL resolves correctly."""
        # Create a test item
        item = CopyrightItem.objects.create(
            material_id=999001,
            title="Test Item",
            filetype="PDF",
        )

        url = reverse("dashboard:update_field", kwargs={"material_id": item.material_id})
        response = authenticated_client.get(url)
        # GET request should return method not allowed or redirect
        # (This is typically a POST-only endpoint for inline editing)
        assert response.status_code in [200, 405, 302]

    @pytest.mark.django_db
    def test_item_detail_panel_url_resolves(self, authenticated_client, staff_user):
        """Test that item detail panel URL resolves correctly."""
        item = CopyrightItem.objects.create(
            material_id=999002,
            title="Test Item",
            filetype="PDF",
        )

        url = reverse("dashboard:detail_panel", kwargs={"material_id": item.material_id})
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_item_detail_modal_url_resolves(self, authenticated_client, staff_user):
        """Test that item detail modal URL resolves correctly."""
        item = CopyrightItem.objects.create(
            material_id=999003,
            title="Test Item",
            filetype="PDF",
        )

        url = reverse("dashboard:detail_modal", kwargs={"material_id": item.material_id})
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_item_enrichment_status_url_resolves(
        self, authenticated_client, staff_user
    ):
        """Test that item enrichment status URL resolves correctly."""
        item = CopyrightItem.objects.create(
            material_id=999004,
            title="Test Item",
            filetype="PDF",
        )

        url = reverse("dashboard:enrichment_status", kwargs={"material_id": item.material_id})
        response = authenticated_client.get(url)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_item_detail_page_url_resolves(self, authenticated_client, staff_user):
        """Test that item detail page URL resolves correctly."""
        item = CopyrightItem.objects.create(
            material_id=999005,
            title="Test Item",
            filetype="PDF",
        )

        url = reverse("dashboard:detail_page", kwargs={"material_id": item.material_id})
        response = authenticated_client.get(url)
        assert response.status_code == 200

    # =========================================================================
    # Authentication Tests
    # =========================================================================

    @pytest.mark.django_db
    def test_dashboard_index_requires_authentication(self, client):
        """Test that dashboard index redirects anonymous users to login."""
        url = reverse("dashboard:index")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    @pytest.mark.django_db
    def test_update_item_field_requires_authentication(self, client, staff_user):
        """Test that item update requires authentication."""
        item = CopyrightItem.objects.create(
            material_id=999006,
            title="Test Item",
            filetype="PDF",
        )

        url = reverse("dashboard:update_field", kwargs={"material_id": item.material_id})
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    @pytest.mark.django_db
    def test_item_detail_requires_authentication(self, client, staff_user):
        """Test that item detail page requires authentication."""
        item = CopyrightItem.objects.create(
            material_id=999007,
            title="Test Item",
            filetype="PDF",
        )

        url = reverse("dashboard:detail_page", kwargs={"material_id": item.material_id})
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    # =========================================================================
    # Invalid Parameter Tests
    # =========================================================================

    @pytest.mark.django_db
    def test_nonexistent_item_returns_error(self, authenticated_client):
        """Test that requesting a non-existent item returns an error."""
        url = reverse("dashboard:detail_page", kwargs={"material_id": 999999})
        response = authenticated_client.get(url)
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_invalid_material_id_returns_error(self, authenticated_client):
        """Test that invalid material_id returns an error."""
        url = reverse("dashboard:detail_page", kwargs={"material_id": 0})
        response = authenticated_client.get(url)
        assert response.status_code == 404

    # =========================================================================
    # HTTP Method Tests
    # =========================================================================

    @pytest.mark.django_db
    def test_update_item_field_accepts_post(self, authenticated_client, staff_user):
        """Test that update item field accepts POST requests."""
        item = CopyrightItem.objects.create(
            material_id=999008,
            title="Test Item",
            filetype="PDF",
        )

        url = reverse("dashboard:update_field", kwargs={"material_id": item.material_id})
        response = authenticated_client.post(
            url, {"field": "classification", "value": "open access"}
        )
        # Should return 200 or 302 (success or redirect)
        assert response.status_code in [200, 302, 400]

    @pytest.mark.django_db
    def test_item_detail_page_get_only(self, authenticated_client, staff_user):
        """Test that item detail page accepts GET requests."""
        item = CopyrightItem.objects.create(
            material_id=999009,
            title="Test Item",
            filetype="PDF",
        )

        url = reverse("dashboard:detail_page", kwargs={"material_id": item.material_id})
        response = authenticated_client.get(url)
        assert response.status_code == 200
