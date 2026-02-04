"""Rate limiting middleware."""

import time
from collections import defaultdict
from threading import Lock

from django.conf import settings
from django.http import JsonResponse


class RateLimitMiddleware:
    """Simple in-memory rate limiting middleware."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limit = getattr(settings, "RATE_LIMIT_PER_MINUTE", 60)
        self.window = 60  # 1 minute window
        self.requests: dict[str, list[float]] = defaultdict(list)
        self.lock = Lock()

    def __call__(self, request):
        # Skip rate limiting for admin and metrics
        if request.path.startswith("/admin") or request.path.startswith("/metrics"):
            return self.get_response(request)

        client_ip = self._get_client_ip(request)
        
        if not self._is_allowed(client_ip):
            return JsonResponse(
                {
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {self.rate_limit} requests per minute",
                },
                status=429,
            )

        return self.get_response(request)

    def _get_client_ip(self, request) -> str:
        """Extract client IP from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")

    def _is_allowed(self, client_ip: str) -> bool:
        """Check if request is within rate limit."""
        now = time.time()
        window_start = now - self.window

        with self.lock:
            # Clean old requests
            self.requests[client_ip] = [
                ts for ts in self.requests[client_ip] if ts > window_start
            ]

            # Check limit
            if len(self.requests[client_ip]) >= self.rate_limit:
                return False

            # Record request
            self.requests[client_ip].append(now)
            return True
