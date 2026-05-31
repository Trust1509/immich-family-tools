from pydantic import BaseModel
from typing import Optional


class Person(BaseModel):
    id: str
    name: Optional[str] = None
    thumbnail_path: Optional[str] = None
    asset_count: int = 0
    is_hidden: bool = False
    # Injected fields (not from Immich API)
    account_id: str
    account_name: str
    account_color: str

    @property
    def display_name(self) -> str:
        return self.name or "Unbekannte Person"
