import pytest

from core.auth import require_api_key
from core.config import settings
from core.exceptions import InvalidApiKeyError


class TestRequireApiKey:
    """core/auth.py directly — every other test only exercises this as a
    FastAPI dependency through a real route (test_batch.py), never the
    function's own edge cases."""

    async def test_happy_path_the_real_key_is_accepted(self):
        await require_api_key(authorization=f"Bearer {settings.api_key}")  # no exception

    async def test_edge_case_no_header_at_all_is_rejected(self):
        with pytest.raises(InvalidApiKeyError):
            await require_api_key(authorization="")

    async def test_edge_case_the_wrong_key_is_rejected(self):
        with pytest.raises(InvalidApiKeyError):
            await require_api_key(authorization="Bearer not-the-real-key")

    async def test_edge_case_a_header_without_the_bearer_prefix_is_rejected(self):
        """Scope: the real key with no `Bearer ` prefix must not be
        accidentally accepted — removeprefix() only strips a prefix
        that's actually present, so this must still fail the comparison,
        not silently succeed."""
        with pytest.raises(InvalidApiKeyError):
            await require_api_key(authorization=settings.api_key)
