from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import get_settings


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Simple API key authentication middleware.

    If API_KEY is set in config, all requests (except health check and docs)
    must include the key via:
      - Header: Authorization: Bearer <key>
      - Query param: ?api_key=<key>

    If API_KEY is empty, authentication is skipped (dev mode).
    """

    SKIP_PATHS = {"/", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        api_key = settings.API_KEY

        # No key configured = dev mode, skip auth
        if not api_key:
            return await call_next(request)

        # Skip auth for health check and docs
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and auth_header[7:] == api_key:
            return await call_next(request)

        # Check query parameter
        if request.query_params.get("api_key") == api_key:
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API key. Set Authorization: Bearer <key> or ?api_key=<key>"},
        )
