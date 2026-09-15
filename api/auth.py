"""
api/auth.py — Sistem Autentikasi Sederhana untuk KBMS Shavira
Menggunakan HTTP Basic Auth + JWT Token Bearer
"""
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials

from api.config import get_settings

settings = get_settings()

# ---- Simple in-memory token store ----
# Untuk production, gunakan Redis atau database
_active_tokens: dict[str, datetime] = {}
TOKEN_EXPIRE_HOURS = 8

security_bearer = HTTPBearer(auto_error=False)
security_basic = HTTPBasic(auto_error=False)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_access_token() -> str:
    """Buat token acak yang aman."""
    token = secrets.token_urlsafe(32)
    _active_tokens[token] = datetime.now() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    # Bersihkan token kadaluarsa
    _cleanup_expired_tokens()
    return token


def _cleanup_expired_tokens():
    now = datetime.now()
    expired = [t for t, exp in _active_tokens.items() if exp < now]
    for t in expired:
        del _active_tokens[t]


def verify_token(token: str) -> bool:
    """Verifikasi token masih valid dan belum kadaluarsa."""
    if token not in _active_tokens:
        return False
    if _active_tokens[token] < datetime.now():
        del _active_tokens[token]
        return False
    return True


def verify_credentials(username: str, password: str) -> bool:
    """Verifikasi username dan password dari .env."""
    correct_username = secrets.compare_digest(username, settings.admin_username)
    correct_password = secrets.compare_digest(password, settings.admin_password)
    return correct_username and correct_password


async def get_current_admin(
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    basic: Optional[HTTPBasicCredentials] = Depends(security_basic)
) -> str:
    """
    Dependency untuk proteksi endpoint admin.
    Mendukung dua metode auth:
    1. Bearer Token (setelah login via /api/auth/token)
    2. HTTP Basic Auth (untuk Swagger UI)
    """
    # Coba Bearer Token dulu
    if bearer and bearer.credentials:
        if verify_token(bearer.credentials):
            return "admin"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid atau sudah kadaluarsa. Silakan login ulang.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Coba Basic Auth (untuk Swagger / fallback)
    if basic and basic.username and basic.password:
        if verify_credentials(basic.username, basic.password):
            return basic.username
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah.",
            headers={"WWW-Authenticate": "Basic"},
        )

    # Tidak ada credential sama sekali
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Autentikasi diperlukan. Silakan login di /api/auth/token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
