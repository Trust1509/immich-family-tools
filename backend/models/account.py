from pydantic import BaseModel
from typing import Optional
import uuid


class AccountCreate(BaseModel):
    name: str
    immich_url: str
    api_key: str


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


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    immich_url: Optional[str] = None
    api_key: Optional[str] = None
    color: Optional[str] = None


class AccountStatus(BaseModel):
    id: str
    name: str
    color: str
    reachable: bool
    error: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
