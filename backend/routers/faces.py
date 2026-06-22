"""
Match suggestions router.

GET  /api/matches              – Return cached match list (recompute if stale)
POST /api/matches/refresh      – Invalidate cache and recompute
POST /api/matches/{id}/dismiss – Mark a match as dismissed
"""
import time
import logging
import asyncio
from fastapi import APIRouter, Request

from models.match import Match
from services.face_matcher import compute_matches, enrich_matches

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/matches", tags=["matches"])


def invalidate_match_cache() -> None:
    """Legacy shim — kept for callers that import this by name.

    Prefer request.app.state.match_cache.invalidate() in new code.
    The module-level function cannot reach app.state, so callers that still
    use this path (e.g. albums.py line 39) must migrate to the state-based call.
    This shim is intentionally a no-op stub to avoid import errors; the real
    invalidation is done in-line via request.app.state.match_cache.invalidate().
    """
    # NOTE: actual invalidation is performed via request.app.state.match_cache
    pass


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
                client = request.app.state.client_pool.get_for_account(account)
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
    """Delegate to enrich_matches() with store data (always fresh, never cached)."""
    return enrich_matches(
        matches,
        managed_albums=request.app.state.store.get_managed_albums(),
        synced_name_ids=request.app.state.store.get_synced_name_ids(),
    )


@router.get("", response_model=list[Match])
async def get_matches(request: Request):
    cache = request.app.state.match_cache
    now = time.monotonic()
    if cache.matches is not None and (now - cache.ts) < _ttl(request):
        return _enrich(list(cache.matches), request)
    async with cache.lock:
        now = time.monotonic()
        if cache.matches is not None and (now - cache.ts) < _ttl(request):
            return _enrich(list(cache.matches), request)
        matches = await _build_matches(request)
        cache.set(matches, time.monotonic())
    return _enrich(list(matches), request)


@router.post("/refresh", response_model=list[Match])
async def refresh_matches(request: Request):
    cache = request.app.state.match_cache
    async with cache.lock:
        cache.invalidate()
        matches = await _build_matches(request)
        cache.set(matches, time.monotonic())
    return _enrich(list(matches), request)


@router.post("/{match_id}/dismiss", status_code=204)
async def dismiss_match(match_id: str, request: Request):
    request.app.state.store.dismiss_match(match_id)
    request.app.state.match_cache.invalidate()
