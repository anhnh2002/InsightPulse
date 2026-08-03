"""Single-account admin auth: pbkdf2 password hash + signed session cookie."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from insightpulse.paths import ADMIN_AUTH

PBKDF2_ITERATIONS = 600_000
SESSION_COOKIE = "ip_admin"
SESSION_MAX_AGE = 7 * 24 * 3600  # seconds


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def save_auth(password: str) -> None:
    ADMIN_AUTH.parent.mkdir(parents=True, exist_ok=True)
    ADMIN_AUTH.write_text(json.dumps({
        "password_hash": hash_password(password),
        "secret_key": secrets.token_hex(32),
    }, indent=2))
    os.chmod(ADMIN_AUTH, 0o600)


def load_auth() -> dict:
    return json.loads(ADMIN_AUTH.read_text())


def _signer() -> TimestampSigner:
    return TimestampSigner(load_auth()["secret_key"])


def make_session_token() -> str:
    return _signer().sign(b"admin").decode()


def valid_session_token(token: str) -> bool:
    try:
        _signer().unsign(token, max_age=SESSION_MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False


def require_session(request: Request) -> None:
    """FastAPI dependency: redirect to the login page unless a valid session exists."""
    token = request.cookies.get(SESSION_COOKIE, "")
    if token and valid_session_token(token):
        return
    raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
