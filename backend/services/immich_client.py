"""Async Immich REST API client."""
import httpx
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class ImmichClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self._headers = {"x-api-key": api_key, "Accept": "application/json"}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=TIMEOUT,
            follow_redirects=False,
        )

    # ------------------------------------------------------------------
    # Auth / health
    # ------------------------------------------------------------------

    async def validate(self) -> dict:
        """Validate API key and return user info."""
        async with self._client() as c:
            r = await c.get("/api/users/me")
            r.raise_for_status()
            return r.json()

    # ------------------------------------------------------------------
    # People
    # ------------------------------------------------------------------

    async def get_people(self, page: int = 1, page_size: int = 100) -> dict:
        """Fetch a page of people. Returns the raw Immich response."""
        async with self._client() as c:
            r = await c.get(
                "/api/people",
                params={"page": page, "pageSize": page_size, "withHidden": False},
            )
            r.raise_for_status()
            return r.json()

    async def get_all_people(self) -> list[dict]:
        """Fetch ALL people, handling pagination transparently."""
        all_people: list[dict] = []
        page = 1
        while True:
            data = await self.get_people(page=page, page_size=100)
            # Immich returns {"people": [...], "total": N, "visible": N, "hasNextPage": bool}
            people = data.get("people", [])
            all_people.extend(people)
            if not data.get("hasNextPage", False):
                break
            page += 1
        return all_people

    async def get_person(self, person_id: str) -> dict:
        async with self._client() as c:
            r = await c.get(f"/api/people/{person_id}")
            r.raise_for_status()
            return r.json()

    async def get_person_asset_count(self, person_id: str) -> int:
        """Fetch asset count for a person via statistics endpoint."""
        async with self._client() as c:
            r = await c.get(f"/api/people/{person_id}/statistics")
            if r.status_code in (403, 404):
                return 0
            r.raise_for_status()
            return r.json().get("assets", 0)

    async def get_person_thumbnail(self, person_id: str) -> Optional[bytes]:
        """Fetch the thumbnail bytes for a person."""
        async with self._client() as c:
            r = await c.get(
                f"/api/people/{person_id}/thumbnail",
                headers={**self._headers, "Accept": "image/*"},
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content

    async def update_person(self, person_id: str, payload: dict) -> dict:
        """Update a person (e.g. rename)."""
        async with self._client() as c:
            r = await c.put(f"/api/people/{person_id}", json=payload)
            r.raise_for_status()
            return r.json()

    async def get_person_assets(self, person_id: str) -> list[dict]:
        """Fetch assets belonging to a person via search/metadata (works in all recent Immich versions)."""
        all_assets: list[dict] = []
        page = 1
        while True:
            async with self._client() as c:
                r = await c.post(
                    "/api/search/metadata",
                    json={"personIds": [person_id], "size": 1000, "page": page},
                )
                r.raise_for_status()
                data = r.json()
            items = data.get("assets", {}).get("items", [])
            all_assets.extend(items)
            next_page = data.get("assets", {}).get("nextPage")
            if not next_page:
                break
            page += 1
        return all_assets

    # ------------------------------------------------------------------
    # Face embeddings
    # ------------------------------------------------------------------

    async def get_faces(self, asset_id: str) -> list[dict]:
        """Return face records for an asset, including embedding if available."""
        async with self._client() as c:
            r = await c.get("/api/faces", params={"id": asset_id})
            if r.status_code in (404, 422):
                return []
            r.raise_for_status()
            return r.json()

    # ------------------------------------------------------------------
    # Albums
    # ------------------------------------------------------------------

    async def create_album(self, album_name: str, asset_ids: list[str]) -> dict:
        async with self._client() as c:
            r = await c.post(
                "/api/albums",
                json={"albumName": album_name, "assetIds": asset_ids},
            )
            r.raise_for_status()
            return r.json()

    async def add_assets_to_album(self, album_id: str, asset_ids: list[str]) -> dict:
        async with self._client() as c:
            r = await c.put(
                f"/api/albums/{album_id}/assets",
                json={"ids": asset_ids},
            )
            r.raise_for_status()
            return r.json()

    async def share_album_with_users(self, album_id: str, user_entries: list[dict]) -> dict:
        """Share album with other users. user_entries = [{"userId": "...", "role": "editor"}]"""
        async with self._client() as c:
            r = await c.put(
                f"/api/albums/{album_id}/users",
                json={"albumUsers": user_entries},
            )
            r.raise_for_status()
            return r.json()

    async def get_album_info(self, album_id: str) -> dict:
        """Fetch full album info (assets + users). Raises AlbumNotFoundError if deleted."""
        async with self._client() as c:
            r = await c.get(f"/api/albums/{album_id}")
            if r.status_code == 404:
                raise AlbumNotFoundError(album_id)
            r.raise_for_status()
            return r.json()

    async def get_album_assets(self, album_id: str) -> list[str]:
        """Return asset IDs already in an album. Raises AlbumNotFoundError if deleted."""
        data = await self.get_album_info(album_id)
        return [a["id"] for a in data.get("assets", [])]

    async def get_album_user_ids(self, album_id: str) -> set[str]:
        """Return set of user IDs already in the album (any role)."""
        data = await self.get_album_info(album_id)
        # albumUsers: [{user: {id: ...}, role: "editor"|"viewer"}, ...]
        return {u["user"]["id"] for u in data.get("albumUsers", []) if "user" in u}

    async def get_albums(self) -> list[dict]:
        async with self._client() as c:
            r = await c.get("/api/albums")
            r.raise_for_status()
            return r.json()


class AlbumNotFoundError(Exception):
    def __init__(self, album_id: str):
        self.album_id = album_id
        super().__init__(f"Album {album_id} not found in Immich (deleted?)")


class ClientPool:
    """Lazy per-account ImmichClient cache.

    Clients are created on first access and cached by account_id.
    Call invalidate(account_id) when an account's credentials change or the
    account is deleted so the next request gets a fresh client.
    """

    def __init__(self):
        self._pool: dict[str, ImmichClient] = {}

    def get(self, account_id: str, url: str, api_key: str) -> ImmichClient:
        """Return a cached client, creating it if necessary."""
        if account_id not in self._pool:
            self._pool[account_id] = ImmichClient(url, api_key)
        return self._pool[account_id]

    def get_for_account(self, account) -> ImmichClient:
        """Convenience wrapper — pass an Account model directly."""
        return self.get(account.id, account.immich_url, account.api_key)

    def invalidate(self, account_id: str) -> None:
        """Remove the cached client for account_id (if present)."""
        self._pool.pop(account_id, None)
