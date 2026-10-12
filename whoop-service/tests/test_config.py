import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from core.config import Settings

_VALID_KWARGS = dict(
    database_url="postgresql+asyncpg://x:x@localhost/x",
    redis_url="redis://localhost:6379",
)


class TestSettings:
    def test_happy_path_accepts_a_valid_fernet_key(self):
        valid_key = Fernet.generate_key().decode()

        settings = Settings(**_VALID_KWARGS, token_encryption_key=valid_key)

        assert settings.token_encryption_key == valid_key

    def test_edge_case_rejects_a_malformed_fernet_key(self):
        """Scope: must fail at construction — startup — not at the first
        encrypt_token() call deep inside a live OAuth callback."""
        with pytest.raises(ValidationError, match="not a valid Fernet key"):
            Settings(**_VALID_KWARGS, token_encryption_key="not-a-real-fernet-key")
