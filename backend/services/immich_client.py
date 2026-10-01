"""Async Immich REST API client."""
from collections import Counter
from itertools import combinations
from math import comb

import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(30.0, connect=10.0)
STRUCTURED_SEARCH_MIN_VERSION = (3, 2)
MAX_STRUCTURED_OR_BRANCHES = 64


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
        self._structured_search_supported: Optional[bool] = None

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
        else:
            logger.warning("search/metadata pagination stopped at the 500-page safety cap")
        return all_items

    async def _supports_structured_search(self) -> bool:
        """Return whether this server supports Immich's Search API v2 shape."""
        if self._structured_search_supported is not None:
            return self._structured_search_supported
        try:
            version = await self.get_server_version()
            current = (int(version["major"]), int(version["minor"]))
            self._structured_search_supported = current >= STRUCTURED_SEARCH_MIN_VERSION
        except Exception as exc:
            logger.warning(
                "Could not determine Immich search API version; using legacy search: %s",
                exc,
            )
            # Treat this as a transient decision for the current request. A
            # cached client should retry version detection after connectivity
            # recovers instead of remaining on the legacy path forever.
            return False
        return self._structured_search_supported

    async def _search_structured_all_pages(self, search_filter: dict) -> list[dict]:
        """Run a Search API v2 filter and follow its opaque cursor."""
        all_items: list[dict] = []
        cursor: Optional[str] = None
        seen_cursors: set[str] = set()
        for _ in range(500):
            payload = {"filter": search_filter, "size": 1000}
            if cursor:
                payload["cursor"] = cursor
            async with self._client() as c:
                r = await c.post("/api/search/metadata", json=payload)
                r.raise_for_status()
                data = r.json()
            assets = data.get("assets", {})
            all_items.extend(assets.get("items", []))
            next_cursor = assets.get("nextCursor")
            if not next_cursor:
                break
            if not isinstance(next_cursor, str):
                logger.warning(
                    "search/metadata returned a non-string nextCursor (%r); stopping pagination",
                    next_cursor,
                )
                break
            if next_cursor in seen_cursors:
                logger.warning(
                    "search/metadata repeated nextCursor (%r); stopping pagination",
                    next_cursor,
                )
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        else:
            logger.warning("structured search pagination stopped at the 500-page safety cap")
        return all_items

    @staticmethod
    def _people_filter(person_ids: list[str], minimum_person_count: int) -> dict:
        """Build a compact structured filter for a small N-of-M rule."""
        base: dict = {"trashedAt": {"eq": None}}
        if minimum_person_count == 1:
            base["personIds"] = {"any": person_ids}
        elif minimum_person_count == len(person_ids):
            base["personIds"] = {"all": person_ids}
        else:
            base["or"] = [
                {"personIds": {"all": list(group)}}
                for group in combinations(person_ids, minimum_person_count)
            ]
        return base

    async def _count_people_locally(
        self,
        person_ids: list[str],
        minimum_person_count: int,
        structured: bool,
    ) -> list[dict]:
        """Evaluate N-of-M with one bounded search per person."""
        counts: Counter[str] = Counter()
        first_asset: dict[str, dict] = {}
        ordered_ids: list[str] = []
        for person_id in person_ids:
            if structured:
                assets = await self._search_structured_all_pages(
                    self._people_filter([person_id], 1)
                )
            else:
                assets = await self._search_metadata_all_pages({"personIds": [person_id]})
            seen_for_person: set[str] = set()
            for asset in assets:
                asset_id = asset["id"]
                if asset_id in seen_for_person:
                    continue
                seen_for_person.add(asset_id)
                if asset_id not in first_asset:
                    first_asset[asset_id] = asset
                    ordered_ids.append(asset_id)
                counts[asset_id] += 1
        return [
            first_asset[asset_id]
            for asset_id in ordered_ids
            if counts[asset_id] >= minimum_person_count
        ]

    async def get_assets_matching_people(
        self,
        person_ids: list[str],
        minimum_person_count: int,
    ) -> list[dict]:
        """Return assets matching an N-of-M people rule.

        Immich 3.2+ evaluates compact any/all rules and small intermediate
        thresholds server-side. Large combinatorial rules keep predictable
        request sizes by counting one search per person locally. Immich 3.1
        uses the same local algorithm with its legacy flat search fields.
        """
        distinct_ids = list(dict.fromkeys(person_ids))
        if not distinct_ids or not 1 <= minimum_person_count <= len(distinct_ids):
            raise ValueError("minimum_person_count must be between 1 and the person count")

        structured = await self._supports_structured_search()
        branch_count = (
            1
            if minimum_person_count in (1, len(distinct_ids))
            else comb(len(distinct_ids), minimum_person_count)
        )
        if structured and branch_count <= MAX_STRUCTURED_OR_BRANCHES:
            return await self._search_structured_all_pages(
                self._people_filter(distinct_ids, minimum_person_count)
            )
        return await self._count_people_locally(
            distinct_ids, minimum_person_count, structured=structured
        )

    async def get_person_assets(self, person_id: str) -> list[dict]:
        """Fetch assets belonging to one person with the best supported search shape."""
        return await self.get_assets_matching_people([person_id], 1)

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

    async def update_album(self, album_id: str, payload: dict) -> dict:
        """Update album metadata such as its name."""
        async with self._client() as c:
            r = await c.patch(f"/api/albums/{album_id}", json=payload)
            if r.status_code == 404:
                raise AlbumNotFoundError(album_id)
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
                # Unknown response shape (older Immich?). Preserve the
                # pre-per-item behavior: treat all sent IDs as added.
                logger.warning(
                    "add_assets_to_album returned a dict instead of per-item results; "
                    "treating all %d sent assets as added",
                    len(asset_ids),
                )
                return [{"id": i, "success": True} for i in asset_ids]
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

    async def get_album_assets_with_name(self, album_id: str) -> tuple[Optional[str], list[str]]:
        """Wie `get_album_assets`, liefert zusätzlich den aktuellen Albumnamen (#97).

        Ein zweiter Aufruf von `GET /api/albums/{id}` wäre hier der Fehler: Der
        Name steht schon in der Antwort, die `get_album_info` für die
        Existenzprüfung ohnehin holt — nur verwarf `get_album_assets` sie
        bisher. Raises AlbumNotFoundError if deleted.
        """
        info = await self.get_album_info(album_id)
        if await self._supports_structured_search():
            items = await self._search_structured_all_pages({
                "trashedAt": {"eq": None},
                "albumIds": {"any": [album_id]},
            })
        else:
            items = await self._search_metadata_all_pages({"albumIds": [album_id]})
        asset_ids: list[str] = []
        seen_ids: set[str] = set()
        for asset in items:
            asset_id = asset["id"]
            if asset_id not in seen_ids:
                seen_ids.add(asset_id)
                asset_ids.append(asset_id)
        return info.get("albumName"), asset_ids

    async def get_album_assets(self, album_id: str) -> list[str]:
        """Return asset IDs already in an album. Raises AlbumNotFoundError if deleted."""
        _, asset_ids = await self.get_album_assets_with_name(album_id)
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
