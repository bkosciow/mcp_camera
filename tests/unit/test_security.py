"""Unit tests for the bearer token dependency."""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from camera_mcp.security import make_token_dependency


def _credentials(scheme: str = "Bearer", token: str = "expected") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme=scheme, credentials=token)


class TestMakeTokenDependency:
    async def test_valid_token_passes(self):
        dependency = make_token_dependency("expected")
        await dependency(_credentials())  # must not raise

    async def test_wrong_token_rejected(self):
        dependency = make_token_dependency("expected")
        with pytest.raises(HTTPException) as excinfo:
            await dependency(_credentials(token="wrong"))
        assert excinfo.value.status_code == 401

    async def test_missing_credentials_rejected(self):
        dependency = make_token_dependency("expected")
        with pytest.raises(HTTPException) as excinfo:
            await dependency(None)
        assert excinfo.value.status_code == 401

    async def test_non_bearer_scheme_rejected(self):
        dependency = make_token_dependency("expected")
        with pytest.raises(HTTPException) as excinfo:
            await dependency(_credentials(scheme="Basic", token="expected"))
        assert excinfo.value.status_code == 401

    @pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
    async def test_bearer_scheme_case_insensitive(self, scheme: str):
        dependency = make_token_dependency("expected")
        await dependency(_credentials(scheme=scheme))  # must not raise

    async def test_non_ascii_token_returns_401_not_type_error(self):
        """A non-ASCII presented token must yield 401, not a TypeError from compare_digest."""
        dependency = make_token_dependency("expected")
        with pytest.raises(HTTPException) as excinfo:
            await dependency(_credentials(token="źłó"))
        assert excinfo.value.status_code == 401

    def test_empty_expected_token_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            make_token_dependency("")
