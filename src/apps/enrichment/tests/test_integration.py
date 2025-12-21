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
        status=IngestionBatch.Status.STAGED,  # Mock it as staked so we skip stage logic if possible or just rely on process
    )

    # We mock the actual processing logic to avoid needing real Qlik data
    # We just want to see if the hook at the end is called.
    # However, process_batch calls services.processing.process_qlik_batch, etc.
    # So we need to ensure process_batch reaches the end.

    with (
        patch("apps.ingest.tasks.BatchProcessor") as MockProcessor,
        patch("apps.enrichment.tasks.trigger_batch_enrichment") as mock_trigger,
    ):
        # Mock the processor instance and its process method
        processor_instance = MockProcessor.return_value
        processor_instance.process.return_value = None  # process() returns None usually

        # We need to simulate the batch being in a state that process_batch accepts
        # process_batch checks consistency then calls process_staged_data

        # Actually, let's just patch the internal function call in `apps.ingest.tasks` if possible,
        # but importing it there changes the namespace.
        # The hook is: `from apps.enrichment.tasks import trigger_batch_enrichment` inside the function.
        # This makes it hard to patch via `apps.ingest.tasks.trigger_batch_enrichment` because it's a local import?
        # No, typically we patch where it is used. But since it's imported INSIDE the function,
        # we might need to patch `apps.enrichment.tasks.trigger_batch_enrichment` globally?
        # Yes, patching the module where it's defined should work if using `apps.enrichment.tasks.trigger_batch_enrichment`.

        process_batch(batch.id)

        assert mock_trigger.called
        mock_trigger.assert_called_with(batch.id)
