"""Bearer token authentication for the camera API."""

import hmac
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# auto_error=False so a missing header falls through to our dependency logic
# (which raises 401) instead of FastAPI's default 401 response.
bearer_scheme = HTTPBearer(auto_error=False)

AuthedCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]

TokenDependency = Callable[[HTTPAuthorizationCredentials | None], Awaitable[None]]


def make_token_dependency(expected_token: str) -> TokenDependency:
    """Create a FastAPI dependency that enforces a bearer token.

    Args:
        expected_token: The token required for authorized access.

    Returns:
        A dependency function that returns None when the request carries the
        correct ``Authorization: Bearer <token>`` header, raising HTTP 401
        otherwise (missing header, wrong scheme, or mismatched token).

    Raises:
        ValueError: If expected_token is empty — configure a real token
            (see create_app's fail-closed check).
    """
    if not expected_token:
        raise ValueError("expected_token must be non-empty")

    expected = expected_token.encode("utf-8")

    async def require_token(credentials: AuthedCredentials) -> None:
        if (
            credentials is not None
            and credentials.scheme.lower() == "bearer"
            and hmac.compare_digest(
                credentials.credentials.encode("utf-8"),
                expected,
            )
        ):
            return
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return require_token
