from django.db.utils import IntegrityError
from django.test import TestCase

from apps.core.models import Classification, QlikItem, Status


class QlikItemModelTests(TestCase):
    def test_create_qlik_item_minimal(self):
        """Test creating QlikItem with minimal fields (handling nulls)."""
        item = QlikItem.objects.create(material_id=1)
        self.assertEqual(item.material_id, 1)
        self.assertIsNone(item.filename)
        # Verify defaults
        self.assertEqual(item.status, Status.PUBLISHED)
        self.assertEqual(item.classification, Classification.NIET_GEANALYSEERD)

    def test_create_qlik_item_full(self):
        """Test creating QlikItem with all fields."""
        item = QlikItem.objects.create(
            material_id=2,
            title="Test Title",
            filename="test.pdf",
            status=Status.UNPUBLISHED,
            classification=Classification.OPEN_ACCESS
        )
        self.assertEqual(item.title, "Test Title")
        self.assertEqual(item.status, Status.UNPUBLISHED)

    def test_nullable_fields(self):
        """Verify that fields can be explicitly set to None."""
        item = QlikItem.objects.create(
            material_id=3,
            status=None,
            classification=None,
            filetype=None
        )
        self.assertIsNone(item.status)
        self.assertIsNone(item.classification)
        self.assertIsNone(item.filetype)

    def test_material_id_unique(self):
        """Verify duplicate material_id raises IntegrityError."""
        QlikItem.objects.create(material_id=4)
        with self.assertRaises(IntegrityError):
            QlikItem.objects.create(material_id=4)
