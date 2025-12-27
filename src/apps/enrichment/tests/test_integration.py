from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile

from apps.ingest.models import IngestionBatch
from apps.ingest.tasks import process_batch
from apps.users.models import User


@pytest.mark.django_db
def test_enrichment_triggered_on_ingest(db):
    """Verify that enrichment is triggered after batch processing."""
    user = User.objects.create_user(username="testuser", email="test@example.com")

    # Create a mock batch
    batch = IngestionBatch.objects.create(
        source_type=IngestionBatch.SourceType.QLIK,
        uploaded_by=user,
        source_file=ContentFile(b"dummy content", name="test.xlsx"),
        status=IngestionBatch.Status.STAGED,
    )

    # Mock the processor and enrichment trigger
    with (
        patch("apps.ingest.tasks.BatchProcessor") as MockProcessor,
        patch("apps.enrichment.tasks.trigger_batch_enrichment") as mock_trigger,
    ):
        # Mock the processor instance and its process method
        processor_instance = MockProcessor.return_value
        processor_instance.process.return_value = None

        # Execute - access underlying function via .func attribute
        process_batch.func(batch.id)

        assert mock_trigger.called
        mock_trigger.assert_called_with(batch.id)
