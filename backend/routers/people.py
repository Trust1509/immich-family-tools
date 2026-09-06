import asyncio
from fastapi import APIRouter, Request, Response

import errors
from models.person import Person

router = APIRouter(prefix="/api/people", tags=["people"])


def _make_person(raw: dict, account) -> Person:
    return Person(
        id=raw["id"],
        name=raw.get("name") or None,
        thumbnail_path=raw.get("thumbnailPath"),
        asset_count=raw.get("assetCount", 0),
        is_hidden=raw.get("isHidden", False),
        account_id=account.id,
        account_name=account.name,
        account_color=account.color,
    )


@router.get("", response_model=list[Person])
async def get_all_people(request: Request):
    """Return all persons from all configured accounts (aggregated)."""
    accounts = request.app.state.store.list_accounts()
    if not accounts:
        return []

    async def fetch(account):
        client = request.app.state.client_pool.get_for_account(account)
        try:
            raw_list = await client.get_all_people()
            return [_make_person(p, account) for p in raw_list]
        except Exception as exc:
            return []  # Silently skip unreachable accounts

    results = await asyncio.gather(*[fetch(a) for a in accounts])
    people: list[Person] = []
    for lst in results:
        people.extend(lst)
    return people


@router.get("/{account_id}", response_model=list[Person])
async def get_people_for_account(account_id: str, request: Request):
    account = request.app.state.store.get_account(account_id)
    if not account:
        raise errors.account_not_found()
    client = request.app.state.client_pool.get_for_account(account)
    try:
        raw_list = await client.get_all_people()
        return [_make_person(p, account) for p in raw_list]
    except Exception as exc:
        raise errors.immich_request_failed()


@router.get("/{account_id}/{person_id}/count")
async def get_person_count(account_id: str, person_id: str, request: Request):
    """Return asset count for a single person (lazy load)."""
    account = request.app.state.store.get_account(account_id)
    if not account:
        raise errors.account_not_found()
    client = request.app.state.client_pool.get_for_account(account)
    count = await client.get_person_asset_count(person_id)
    return {"count": count}


@router.get("/{account_id}/{person_id}/thumbnail")
async def get_thumbnail(account_id: str, person_id: str, request: Request):
    """Proxy thumbnail through backend (handles auth + caching)."""
    # Try cache first
    cached = request.app.state.thumbnail_cache.get(account_id, person_id)
    if cached:
        return Response(content=cached, media_type="image/jpeg")

    account = request.app.state.store.get_account(account_id)
    if not account:
        raise errors.account_not_found()

    client = request.app.state.client_pool.get_for_account(account)
    data = await client.get_person_thumbnail(person_id)
    if data is None:
        raise errors.no_thumbnail()

    request.app.state.thumbnail_cache.set(account_id, person_id, data)
    return Response(content=data, media_type="image/jpeg")
