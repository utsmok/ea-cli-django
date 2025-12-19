from django.test import TestCase

# Import models from the users app
from apps.users.models import User


class UsersModelsTest(TestCase):
    def test_user_creation(self):
        """Test the creation of a custom User object."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password123"
        )
        self.assertIsInstance(user, User)
        self.assertEqual(user.username, "testuser")
        self.assertTrue(user.check_password("password123"))
