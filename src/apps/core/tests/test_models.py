from django.test import TestCase

# Import models from the core app
from apps.core.models import (
    Faculty,
    Organization,
)


class CoreModelsTest(TestCase):
    def test_organization_creation(self):
        """Test the creation of an Organization object."""
        org = Organization.objects.create(
            hierarchy_level=0,
            name="University",
            abbreviation="UNI",
            full_abbreviation="UNI",
        )
        self.assertIsInstance(org, Organization)
        self.assertEqual(org.name, "University")

    def test_faculty_creation(self):
        """Test the creation of a Faculty object."""
        faculty = Faculty.objects.create(
            hierarchy_level=1,
            name="Faculty of Engineering",
            abbreviation="ENG",
            full_abbreviation="ENG",
        )
        self.assertIsInstance(faculty, Faculty)
        self.assertEqual(faculty.name, "Faculty of Engineering")
