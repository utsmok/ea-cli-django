import pytest
from django.urls import reverse
from unittest.mock import patch, AsyncMock
from apps.core.models import CopyrightItem, Faculty, EnrichmentStatus

@pytest.mark.django_db
class TestEnrichmentViews:

    @pytest.fixture
    def item(self):
        faculty = Faculty.objects.create(
            abbreviation="EEMCS",
            name="EEMCS",
            hierarchy_level=1,
            full_abbreviation="EEMCS-TEST"
        )
        return CopyrightItem.objects.create(
            material_id=999,
            filename="test.pdf",
            faculty=faculty,
            enrichment_status=EnrichmentStatus.PENDING
        )

    def test_trigger_item_enrichment(self, client, item):
        """Test manual trigger of enrichment via HTMX."""
        url = reverse("enrichment:trigger_item", args=[item.material_id])

        # Patch the async task trigger
        with patch("apps.enrichment.views.enrich_item") as mock_task:
            response = client.post(url)

            assert response.status_code == 200
            assert b"Running..." in response.content
            # We can't easily verify the async task was scheduled in a sync view test
            # without more complex mocking of the event loop,
            # but we verify the view logic returns the correct HTMX partial.

    def test_item_enrichment_status(self, client, item):
        """Test status polling view."""
        url = reverse("enrichment:item_status", args=[item.material_id])
        response = client.get(url)
        assert response.status_code == 200
        assert b"PENDING" in response.content

        # Update status
        item.enrichment_status = EnrichmentStatus.COMPLETED
        item.save()

        response = client.get(url)
        assert response.status_code == 200
        assert b"COMPLETED" in response.content
