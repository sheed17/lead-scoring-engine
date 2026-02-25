"""
Fake auth middleware for local development.

Injects user_id = 1 into every request's state so downstream
routes can scope data by user without real authentication.
Replace with Supabase JWT verification later.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class FakeAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.user_id = 1
        return await call_next(request)
