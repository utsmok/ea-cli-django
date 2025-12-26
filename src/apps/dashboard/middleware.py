"""
Rate limiting middleware for API endpoints.

Implements simple IP-based rate limiting using Redis cache.
For production deployments, consider using django-ratelimit or a dedicated API gateway.
"""

import time
from collections.abc import Callable

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse


class RateLimitMiddleware:
    """
    Simple IP-based rate limiting middleware.

    Limits requests per IP address using a sliding window algorithm.
    Non-blocking - returns 429 (Too Many Requests) when limit exceeded.

    Configuration in settings.py:
        RATE_LIMIT_ENABLED = True
        RATE_LIMIT_REQUESTS = 100  # requests per window
        RATE_LIMIT_WINDOW = 60  # seconds
        RATE_LIMIT_CACHE_PREFIX = "ratelimit"

    To exempt specific paths, add them to RATE_LIMIT_EXEMPT_PATHS.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        from django.conf import settings

        self.enabled = getattr(settings, "RATE_LIMIT_ENABLED", False)
        self.requests = getattr(settings, "RATE_LIMIT_REQUESTS", 100)
        self.window = getattr(settings, "RATE_LIMIT_WINDOW", 60)
        self.prefix = getattr(settings, "RATE_LIMIT_CACHE_PREFIX", "ratelimit")
        self.exempt_paths = getattr(settings, "RATE_LIMIT_EXEMPT_PATHS", [])

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP from request, handling proxies."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # X-Forwarded-For can contain multiple IPs; the first is the client
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "unknown")
        return ip

    def _get_cache_key(self, ip: str) -> str:
        """Generate cache key for rate limiting."""
        return f"{self.prefix}:{ip}"

    def _is_exempt(self, request: HttpRequest) -> bool:
        """Check if request path is exempt from rate limiting."""
        path = request.path
        for exempt in self.exempt_paths:
            if path.startswith(exempt):
                return True
        # Always exempt health checks
        if path in ("/health/", "/api/health/", "/readiness/", "/api/readiness/"):
            return True
        return False

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self.enabled or self._is_exempt(request):
            return self.get_response(request)

        ip = self._get_client_ip(request)
        cache_key = self._get_cache_key(ip)

        # Get current state from cache
        state = cache.get(cache_key, {"count": 0, "window_start": time.time()})

        current_time = time.time()
        window_start = state.get("window_start", current_time)
        count = state.get("count", 0)

        # Reset if window expired
        if current_time - window_start > self.window:
            count = 0
            window_start = current_time

        # Check limit
        if count >= self.requests:
            from django.http import HttpResponse

            response = HttpResponse(
                '{"error": "Rate limit exceeded"}',
                status=429,
                content_type="application/json",
            )
            response["Retry-After"] = str(
                int(self.window - (current_time - window_start))
            )
            response["X-RateLimit-Limit"] = str(self.requests)
            response["X-RateLimit-Remaining"] = "0"
            response["X-RateLimit-Reset"] = str(int(window_start + self.window))
            return response

        # Increment counter
        count += 1
        cache.set(
            cache_key, {"count": count, "window_start": window_start}, self.window
        )

        response = self.get_response(request)

        # Add rate limit headers
        response["X-RateLimit-Limit"] = str(self.requests)
        response["X-RateLimit-Remaining"] = str(self.requests - count)
        response["X-RateLimit-Reset"] = str(int(window_start + self.window))

        return response
