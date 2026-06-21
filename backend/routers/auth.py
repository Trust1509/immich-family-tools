"""Single-secret login endpoints. This is intentionally not user management."""
import hmac
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from services.auth_service import create_session

router = APIRouter(prefix="/api/auth", tags=["auth"])
_failed_logins: dict[str, deque[float]] = defaultdict(deque)


class LoginRequest(BaseModel):
    token: str


def _check_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    attempts = _failed_logins[client_ip]
    while attempts and attempts[0] < now - 60:
        attempts.popleft()
    if len(attempts) >= 5:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again in one minute.")


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    settings = request.app.state.settings
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)
    if not hmac.compare_digest(body.token, settings.secret):
        _failed_logins[client_ip].append(time.monotonic())
        raise HTTPException(status_code=401, detail="Invalid token")
    _failed_logins.pop(client_ip, None)
    max_age = settings.session_ttl_hours * 3600
    response.set_cookie(
        key="ift_session",
        value=create_session(settings.secret, max_age),
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return {"authenticated": True}


@router.get("/status")
async def status():
    return {"authenticated": True}


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie("ift_session", path="/")
