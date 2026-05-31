"""
Match suggestions router.

GET  /api/matches              – Return cached match list (recompute if stale)
POST /api/matches/refresh      – Invalidate cache and recompute
POST /api/matches/{id}/dismiss – Mark a match as dismissed
"""
import time
import logging
from fastapi import APIRouter, Request

from models.match import Match
from services.immich_client import ImmichClient
from services.face_matcher import compute_matches

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/matches", tags=["matches"])

_cache: dict = {"matches": None, "ts": 0.0}


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
    for account in accounts:
        client = ImmichClient(account.immich_url, account.api_key)
        account_people = [p for p in people if p.account_id == account.id]
        for person in account_people[:20]:
            try:
                assets = await client.get_person_assets(person.id)
                if assets:
                    faces = await client.get_faces(assets[0]["id"])
                    for face in faces:
                        if face.get("personId") == person.id and face.get("embedding"):
                            embeddings[person.id] = face["embedding"]
                            break
            except Exception:
                pass

    return compute_matches(people, embeddings=embeddings or None, dismissed_ids=dismissed)


def _enrich(matches: list[Match], request: Request) -> list[Match]:
    """Add has_album and names_synced flags (always fresh, never cached)."""
    managed_albums = request.app.state.store.get_managed_albums()
    album_match_ids = {ma.match_id for ma in managed_albums}
    synced_name_ids = request.app.state.store.get_synced_name_ids()
    for m in matches:
        m.has_album = m.id in album_match_ids
        m.names_synced = m.id in synced_name_ids  # only explicit tool syncs
    return matches


@router.get("", response_model=list[Match])
async def get_matches(request: Request):
    now = time.monotonic()
    if _cache["matches"] is not None and (now - _cache["ts"]) < _ttl(request):
        return _enrich(list(_cache["matches"]), request)
    matches = await _build_matches(request)
    _cache["matches"] = matches
    _cache["ts"] = now
    return _enrich(list(matches), request)


@router.post("/refresh", response_model=list[Match])
async def refresh_matches(request: Request):
    _cache["matches"] = None
    _cache["ts"] = 0.0
    matches = await _build_matches(request)
    _cache["matches"] = matches
    _cache["ts"] = time.monotonic()
    return _enrich(list(matches), request)


@router.post("/{match_id}/dismiss", status_code=204)
async def dismiss_match(match_id: str, request: Request):
    request.app.state.store.dismiss_match(match_id)
    _cache["matches"] = None
