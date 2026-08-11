"""Async Immich REST API client."""
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class ImmichClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._headers = {"x-api-key": api_key, "Accept": "application/json"}
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=TIMEOUT,
            follow_redirects=False,
            transport=self._transport,
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

    async def get_server_version(self) -> dict:
        """Fetch the Immich server version. Unauthenticated endpoint.

        Returns e.g. {"major": 3, "minor": 1, "patch": 0}.
        """
        async with self._client() as c:
            r = await c.get("/api/server/version")
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
                params={"page": page, "size": page_size, "withHidden": False},
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
        """Update a person (e.g. rename).

        Uses PUT: it is the documented primary endpoint in Immich v3.1
        (PATCH exists but is @ApiExcludeEndpoint) and also works on v2.
        """
        async with self._client() as c:
            r = await c.put(f"/api/people/{person_id}", json=payload)
            r.raise_for_status()
            return r.json()

    async def _search_metadata_all_pages(self, filters: dict) -> list[dict]:
        """Paginate POST /api/search/metadata and collect assets.items across all pages.

        Handles the pagination quirks of the endpoint uniformly:
        - missing/empty nextPage ends pagination normally.
        - a non-numeric nextPage is logged and treated as the end (no crash).
        - a nextPage that doesn't advance past the current page is logged and
          treated as the end (guards against an endless loop on a server bug).
        - a hard cap of 500 pages guards against runaway pagination.
        """
        all_items: list[dict] = []
        page = 1
        for _ in range(500):
            async with self._client() as c:
                r = await c.post(
                    "/api/search/metadata",
                    json={**filters, "size": 1000, "page": page},
                )
                r.raise_for_status()
                data = r.json()
            assets = data.get("assets", {})
            all_items.extend(assets.get("items", []))
            next_page = assets.get("nextPage")
            if not next_page:
                break
            try:
                next_page_num = int(next_page)
            except (TypeError, ValueError):
                logger.warning(
                    "search/metadata returned a non-numeric nextPage (%r); stopping pagination",
                    next_page,
                )
                break
            if next_page_num <= page:
                logger.warning(
                    "search/metadata nextPage (%r) did not advance past page %r; stopping pagination",
                    next_page,
                    page,
                )
                break
            page = next_page_num
        return all_items

    async def get_person_assets(self, person_id: str) -> list[dict]:
        """Fetch assets belonging to a person via search/metadata (works in all recent Immich versions)."""
        return await self._search_metadata_all_pages({"personIds": [person_id]})

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

    async def add_assets_to_album(self, album_id: str, asset_ids: list[str]) -> list[dict]:
        """Add assets to an album and return the per-item results.

        Immich responds with a list of
        `{"id": ..., "success": bool, "error": "duplicate" | ...}` — one entry
        per requested asset ID — even though the HTTP status is 200
        regardless of individual outcomes.
        """
        async with self._client() as c:
            r = await c.put(
                f"/api/albums/{album_id}/assets",
                json={"ids": asset_ids},
            )
            r.raise_for_status()
            result = r.json()
            if isinstance(result, dict):
                return [result]
            return result

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
        await self.get_album_info(album_id)
        items = await self._search_metadata_all_pages({"albumIds": [album_id]})
        asset_ids: list[str] = []
        seen_ids: set[str] = set()
        for asset in items:
            asset_id = asset["id"]
            if asset_id not in seen_ids:
                seen_ids.add(asset_id)
                asset_ids.append(asset_id)
        return asset_ids

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
