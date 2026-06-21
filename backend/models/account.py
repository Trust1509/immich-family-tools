from pydantic import BaseModel, field_validator
from typing import Optional
import uuid
import ipaddress
from urllib.parse import urlparse


def validate_immich_url(value: str) -> str:
    if value is None:
        return value
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Immich URL must use http:// or https://")
    if parsed.username or parsed.password:
        raise ValueError("Credentials are not allowed inside the Immich URL")
    try:
        address = ipaddress.ip_address(parsed.hostname)
        if (
            address.is_link_local
            or address.is_loopback
            or address.is_multicast
            or address.is_unspecified
            or address.is_reserved
        ):
            raise ValueError("This network address is not allowed")
    except ValueError as exc:
        if "not allowed" in str(exc):
            raise
        # Hostnames and private LAN addresses are intentionally supported.
    return value


class AccountCreate(BaseModel):
    name: str
    immich_url: str
    api_key: str

    _validate_url = field_validator("immich_url")(validate_immich_url)


class Account(BaseModel):
    id: str
    name: str
    immich_url: str
    api_key: str
    color: str  # Hex color for UI badge
    user_id: Optional[str] = None  # Immich internal user UUID (fetched on add)

    @classmethod
    def from_create(cls, data: AccountCreate) -> "Account":
        colors = [
            "#6366f1",  # indigo
            "#10b981",  # emerald
            "#f59e0b",  # amber
            "#ef4444",  # red
            "#8b5cf6",  # violet
            "#06b6d4",  # cyan
        ]
        account_id = str(uuid.uuid4())
        color_idx = hash(account_id) % len(colors)
        return cls(
            id=account_id,
            name=data.name,
            immich_url=data.immich_url.rstrip("/"),
            api_key=data.api_key,
            color=colors[color_idx],
        )


class AccountPublic(BaseModel):
    id: str
    name: str
    immich_url: str
    color: str
    user_id: Optional[str] = None
    api_key_configured: bool = True

    @classmethod
    def from_account(cls, account: Account) -> "AccountPublic":
        return cls(
            id=account.id,
            name=account.name,
            immich_url=account.immich_url,
            color=account.color,
            user_id=account.user_id,
            api_key_configured=bool(account.api_key),
        )


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    immich_url: Optional[str] = None
    api_key: Optional[str] = None
    color: Optional[str] = None

    _validate_url = field_validator("immich_url")(validate_immich_url)


class AccountStatus(BaseModel):
    id: str
    name: str
    color: str
    reachable: bool
    error: Optional[str] = None
    user_name: Optional[str] = None
