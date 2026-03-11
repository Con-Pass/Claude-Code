from typing import Optional

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.logging_config import get_logger
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
import jwt

logger = get_logger(__name__)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces presence of a ConPass auth token on incoming requests.

    Once verified end-to-end, consider renaming to reflect the new pass-through auth
    behaviour or migrating to dependency injection instead of middleware.
    """

    DEFAULT_VERIFY_URL = f"{settings.CONPASS_API_BASE_URL}/user"
    DEFAULT_TIMEOUT_SECONDS = 10.0

    def __init__(self, app):
        super().__init__(app)
        self.verify_url = self.DEFAULT_VERIFY_URL
        self.verify_timeout = self.DEFAULT_TIMEOUT_SECONDS

    @staticmethod
    def _extract_token_from_request(
        request: Request,
    ) -> Optional[str]:
        """Attempt to extract ConPass auth token from the `auth-token` cookie."""
        token = request.cookies.get("auth-token")
        if token:
            return token
        return None

    async def _verify_token_with_conpass(
        self, token: str
    ) -> tuple[Optional[dict], Optional[JSONResponse]]:
        """
        Validate the provided token against the ConPass user endpoint.
        """
        try:
            logger.info(f"Verifying token with ConPass: {self.verify_url}")
            async with httpx.AsyncClient(timeout=self.verify_timeout) as client:
                response = await client.get(
                    self.verify_url,
                    headers={"Accept": "application/json"},
                    cookies={"auth-token": token},
                )
                response.raise_for_status()
                return response.json(), None
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.warning(
                "ConPass token verification failed with status %s", status_code
            )
            if status_code in (401, 403):
                return (
                    None,
                    JSONResponse(
                        status_code=401,
                        content={"message": "Invalid ConPass authentication token"},
                    ),
                )
            return (
                None,
                JSONResponse(
                    status_code=502,
                    content={"message": "Unable to verify authentication token"},
                ),
            )
        except httpx.RequestError as exc:
            logger.error("Error contacting ConPass user endpoint: %s", exc)
            return (
                None,
                JSONResponse(
                    status_code=503,
                    content={
                        "message": "Unable to reach ConPass authentication service"
                    },
                ),
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Unexpected error verifying ConPass token: %s", exc)
            return (
                None,
                JSONResponse(
                    status_code=500,
                    content={"message": "Internal authentication error"},
                ),
            )

    def _decode_token_payload(self, token: str) -> Optional[dict]:
        """
        Decode JWT payload without verifying signature.
        ConPass handles validity; here we only inspect claims.
        """
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception as exc:
            logger.error(f"Failed to decode JWT: {exc}")
            return None

    async def dispatch(self, request: Request, call_next):
        skip_paths = {"/docs", "/redoc", "/openapi.json", "/health", "/api/internal"}
        if (
            request.method == "OPTIONS"
            or request.url.path.endswith("/health")
            or any(request.url.path.startswith(p) for p in skip_paths)
        ):
            return await call_next(request)

        try:
            token = self._extract_token_from_request(request)

            if not token:
                logger.warning("Missing ConPass authentication token.")
                return JSONResponse(
                    status_code=401, content={"message": "Authentication token missing"}
                )

            _, error_response = await self._verify_token_with_conpass(token)
            if error_response is not None:
                return error_response

            # Decode token payload to extract scope
            payload = self._decode_token_payload(token)
            if payload:
                request.state.scope = payload.get("scope")
            else:
                request.state.scope = None

            request.state.conpass_token = token

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(f"Unexpected auth error: {exc}")
            return JSONResponse(
                status_code=500,
                content={"message": "Internal authentication error"},
            )

        return await call_next(request)
