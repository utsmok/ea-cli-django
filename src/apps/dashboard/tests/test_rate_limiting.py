from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()

@override_settings(
    RATE_LIMIT_ENABLED=True,
    RATE_LIMIT_REQUESTS=5,
    RATE_LIMIT_WINDOW=60,
    RATE_LIMIT_CACHE_PREFIX="ratelimit_test"
)
class RateLimitingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client.force_login(self.user)
        self.url = reverse("dashboard:index")

        # Clear cache before tests
        cache.clear()

    def test_rate_limit_enforced(self):
        """Test that rate limit is enforced after N requests."""
        # Make 5 allowed requests
        for i in range(5):
            response = self.client.get(self.url)
            self.assertNotEqual(response.status_code, 429, f"Request {i+1} failed")
            self.assertEqual(response["X-RateLimit-Remaining"], str(5 - (i + 1)))

        # Make 6th request - should be blocked
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["X-RateLimit-Remaining"], "0")
        self.assertIn("Retry-After", response)

    @override_settings(RATE_LIMIT_ENABLED=False)
    def test_rate_limit_disabled(self):
        """Test that rate limit is ignored when disabled."""
        for _ in range(10):
            response = self.client.get(self.url)
            self.assertNotEqual(response.status_code, 429)

    def test_exempt_paths(self):
        """Test that exempt paths are not rate limited."""
        # Health check is exempt
        health_url = reverse("api:health_check")

        # Even with limit=5, we can make 10 requests to health check
        for _ in range(10):
            response = self.client.get(health_url)
            self.assertEqual(response.status_code, 200)
