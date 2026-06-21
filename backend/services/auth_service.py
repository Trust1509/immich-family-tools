"""Stateless, signed session cookies for the single shared application secret."""
import base64
import hashlib
import hmac
import secrets
import time


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_session(secret: str, ttl_seconds: int) -> str:
    payload = f"{int(time.time()) + ttl_seconds}:{secrets.token_urlsafe(24)}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return f"{_b64encode(payload.encode())}.{_b64encode(signature)}"


def verify_session(token: str | None, secret: str) -> bool:
    if not token or "." not in token:
        return False
    try:
        payload_b64, signature_b64 = token.split(".", 1)
        payload = _b64decode(payload_b64)
        signature = _b64decode(signature_b64)
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            return False
        expires_at = int(payload.decode().split(":", 1)[0])
        return expires_at >= int(time.time())
    except (ValueError, UnicodeDecodeError):
        return False
