from django.test import TestCase

# Import models from the ingest app
from apps.ingest.models import (
    IngestionBatch,
)


class IngestModelsTest(TestCase):
    def test_ingestion_batch_creation(self):
        """Test the creation of an IngestionBatch object."""
        # Assuming a User model exists for ForeignKey
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user, created = User.objects.get_or_create(username="testuser")

        batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            source_file="test_file.xlsx",
            uploaded_by=user,
            total_rows=10,
        )
        self.assertIsInstance(batch, IngestionBatch)
        self.assertEqual(batch.source_type, IngestionBatch.SourceType.QLIK)
        self.assertEqual(batch.total_rows, 10)
