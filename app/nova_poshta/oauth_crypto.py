"""Encrypt OAuth tokens at rest using Fernet (key derived from app secret)."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

from app.config.settings import BASE_DIR


def _secret_material() -> bytes:
    explicit = os.getenv("OAUTH_TOKEN_SECRET", "").strip()
    if explicit:
        return explicit.encode("utf-8")
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if bot_token:
        return bot_token.encode("utf-8")
    # Last-resort local-only key file so tooling works without .env in some scripts.
    key_path = BASE_DIR / "data" / ".oauth_token_key"
    if key_path.is_file():
        return key_path.read_bytes()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    raw = os.urandom(32)
    key_path.write_bytes(raw)
    return raw


def _fernet() -> Fernet:
    digest = hashlib.sha256(_secret_material()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret string for database storage."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a secret previously stored with encrypt_secret."""
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        msg = "Failed to decrypt OAuth token (wrong OAUTH_TOKEN_SECRET/BOT_TOKEN?)"
        raise ValueError(msg) from exc
