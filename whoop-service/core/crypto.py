"""Symmetric (Fernet) encryption for tokens at rest."""

from cryptography.fernet import Fernet


def encrypt_token(raw: str, key: str) -> str:
    """Encrypt a plaintext token for storage."""
    return Fernet(key.encode()).encrypt(raw.encode()).decode()


def decrypt_token(ciphertext: str, key: str) -> str:
    """Decrypt a token previously encrypted by `encrypt_token`."""
    return Fernet(key.encode()).decrypt(ciphertext.encode()).decode()
