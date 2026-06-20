"""
Match suggestions router.

GET  /api/matches              – Return cached match list (recompute if stale)
POST /api/matches/refresh      – Invalidate cache and recompute
POST /api/matches/{id}/dismiss – Mark a match as dismissed
"""
import hashlib
import time
import logging
import asyncio
from collections import defaultdict
from itertools import combinations
from fastapi import APIRouter, Request

from models.match import Match
from services.immich_client import ImmichClient
from services.face_matcher import compute_matches

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/matches", tags=["matches"])

_cache: dict = {"matches": None, "ts": 0.0}
_refresh_lock = asyncio.Lock()


def invalidate_match_cache() -> None:
    _cache["matches"] = None
    _cache["ts"] = 0.0


def _ttl(request: Request) -> int:
    return request.app.state.settings.match_cache_ttl


async def _load_people(request: Request):
    from routers.people import get_all_people
    return await get_all_people(request)


async def _build_matches(request: Request) -> list[Match]:
    people = await _load_people(request)
    dismissed = request.app.state.store.get_dismissed_ids()

    embeddings: dict[str, list[float]] = {}
    accounts = request.app.state.store.list_accounts()
    account_map = {a.id: a for a in accounts}
    named_people = [person for person in people if person.name]
    semaphore = asyncio.Semaphore(5)

    async def fetch_embedding(person):
        account = account_map.get(person.account_id)
        if not account:
            return
        async with semaphore:
            try:
                client = ImmichClient(account.immich_url, account.api_key)
                assets = await client.get_person_assets(person.id)
                if not assets:
                    return
                faces = await client.get_faces(assets[0]["id"])
                for face in faces:
                    if face.get("personId") == person.id and face.get("embedding"):
                        embeddings[person.id] = face["embedding"]
                        return
            except Exception as exc:
                logger.warning(
                    "Embedding unavailable for account %s person %s: %s",
                    person.account_id,
                    person.id,
                    type(exc).__name__,
                )

    await asyncio.gather(*(fetch_embedding(person) for person in named_people))
    return compute_matches(
        named_people,
        embeddings=embeddings or None,
        dismissed_ids=dismissed,
    )


def _enrich(matches: list[Match], request: Request) -> list[Match]:
    """Add has_album and names_synced flags (always fresh, never cached)."""
    managed_albums = request.app.state.store.get_managed_albums()
    synced_name_ids = request.app.state.store.get_synced_name_ids()

    # Group albums by normalised name and collect all unique person_ids per group.
    # This handles the case where the same person is covered by multiple 2-person
    # albums (e.g. Manu↔Majo + Majo↔Jojo both named "Manuel") — the transitive
    # pair Manu↔Jojo is then also considered to have an album.
    by_name: dict[str, set[str]] = defaultdict(set)
    for ma in managed_albums:
        key = ma.album_name.strip().lower()
        for ref in ma.person_refs:
            by_name[key].add(ref["person_id"])

    all_linked_ids: set[str] = set()
    for person_ids in by_name.values():
        for a, b in combinations(sorted(person_ids), 2):
            k = "_".join(sorted([a, b]))
            all_linked_ids.add(hashlib.md5(k.encode()).hexdigest())

    for m in matches:
        m.has_album = m.id in all_linked_ids
        same_name = bool(m.person_a.person_name) and m.person_a.person_name == m.person_b.person_name
        m.names_synced = m.id in synced_name_ids or same_name
    return matches


@router.get("", response_model=list[Match])
async def get_matches(request: Request):
    now = time.monotonic()
    if _cache["matches"] is not None and (now - _cache["ts"]) < _ttl(request):
        return _enrich(list(_cache["matches"]), request)
    async with _refresh_lock:
        now = time.monotonic()
        if _cache["matches"] is not None and (now - _cache["ts"]) < _ttl(request):
            return _enrich(list(_cache["matches"]), request)
        matches = await _build_matches(request)
        _cache["matches"] = matches
        _cache["ts"] = time.monotonic()
    return _enrich(list(matches), request)


@router.post("/refresh", response_model=list[Match])
async def refresh_matches(request: Request):
    async with _refresh_lock:
        invalidate_match_cache()
        matches = await _build_matches(request)
        _cache["matches"] = matches
        _cache["ts"] = time.monotonic()
    return _enrich(list(matches), request)


@router.post("/{match_id}/dismiss", status_code=204)
async def dismiss_match(match_id: str, request: Request):
    request.app.state.store.dismiss_match(match_id)
    invalidate_match_cache()
