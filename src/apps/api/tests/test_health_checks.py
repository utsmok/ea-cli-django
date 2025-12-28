from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.health_url = reverse("api:health_check")
        self.readiness_url = reverse("api:readiness_check")

    def test_health_check_returns_200(self):
        """Health check should return 200 OK."""
        response = self.client.get(self.health_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "ea-platform")

    def test_readiness_check_returns_200_when_healthy(self):
        """Readiness check should return 200 when DB and cache are healthy."""
        response = self.client.get(self.readiness_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["checks"]["database"], "healthy")
        # Cache check might differ based on setup, but status should be 200

    @patch("django.db.connections")
    def test_readiness_check_returns_503_when_db_down(self, mock_connections):
        """Readiness check should return 503 when DB is down."""
        # Mock cursor to raise exception
        mock_cursor = mock_connections.__getitem__.return_value.cursor.return_value.__enter__.return_value
        mock_cursor.execute.side_effect = Exception("DB Connection Failed")

        response = self.client.get(self.readiness_url)
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["status"], "not_ready")
        self.assertIn("unhealthy", data["checks"]["database"])
