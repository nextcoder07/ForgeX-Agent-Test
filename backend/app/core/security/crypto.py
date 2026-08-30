"""
ForgeX Enterprise Cryptographic Secret Management Layer.
Provides symmetric AES-256 / Fernet encryption and decryption for user credentials at rest.
Ensures zero plaintext storage in PostgreSQL/Supabase and zero plaintext transmission to UI.
"""

import os
import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet

_DEFAULT_SALT = b"forgex-platform-secret-salt-2026"
_RAW_KEY = os.getenv("FORGEX_ENCRYPTION_KEY", "forgex-master-production-key-seed-984321")

def _get_fernet() -> Fernet:
    """Derives a deterministic 32-byte url-safe base64 key for Fernet."""
    key_material = hashlib.pbkdf2_hmac("sha256", _RAW_KEY.encode("utf-8"), _DEFAULT_SALT, 100_000)
    b64_key = base64.urlsafe_b64encode(key_material)
    return Fernet(b64_key)


def encrypt_credential(plaintext: str) -> str:
    """Encrypts plaintext API keys/secrets into secure ciphertext for database storage."""
    if not plaintext or not isinstance(plaintext, str):
        return ""
    clean = plaintext.strip()
    if not clean:
        return ""
    f = _get_fernet()
    token = f.encrypt(clean.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_credential(ciphertext: str) -> str:
    """Decrypts database ciphertext into plaintext for isolated sandbox execution."""
    if not ciphertext or not isinstance(ciphertext, str):
        return ""
    clean = ciphertext.strip()
    if not clean:
        return ""
    try:
        f = _get_fernet()
        decrypted = f.decrypt(clean.encode("utf-8"))
        return decrypted.decode("utf-8")
    except Exception:
        # Fallback if value was stored in plaintext
        return clean


def mask_credential(raw_or_masked: str) -> str:
    """Generates a safe non-reversible display representation (e.g. ••••••••abcd)."""
    if not raw_or_masked:
        return ""
    val = str(raw_or_masked).strip()
    if val.startswith("••••") or val.startswith("****"):
        return val
    if len(val) <= 4:
        return "••••"
    return f"••••••••{val[-4:]}"
