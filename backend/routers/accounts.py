from fastapi import APIRouter, HTTPException, Request
from models.account import AccountCreate, AccountPublic, AccountStatus, AccountUpdate
from services.immich_client import ImmichClient

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountPublic])
async def list_accounts(request: Request):
    return [AccountPublic.from_account(a) for a in request.app.state.store.list_accounts()]


@router.post("", response_model=AccountPublic, status_code=201)
async def add_account(data: AccountCreate, request: Request):
    client = ImmichClient(data.immich_url, data.api_key)
    try:
        user_info = await client.validate()
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Immich API nicht erreichbar oder Token ungültig")
    # Store the Immich user UUID — needed for album sharing
    user_id = user_info.get("id")
    return AccountPublic.from_account(request.app.state.store.add_account(data, user_id=user_id))


@router.put("/{account_id}", response_model=AccountPublic)
async def update_account(account_id: str, data: AccountUpdate, request: Request):
    account = request.app.state.store.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account nicht gefunden")
    updates = data.model_dump(exclude_none=True)
    if updates.get("api_key") == "":
        updates.pop("api_key")
    # Re-validate if URL or API key changed
    if "immich_url" in updates or "api_key" in updates:
        new_url = updates.get("immich_url", account.immich_url).rstrip("/")
        new_key = updates.get("api_key", account.api_key)
        updates["immich_url"] = new_url
        client = ImmichClient(new_url, new_key)
        try:
            user_info = await client.validate()
            updates["user_id"] = user_info.get("id")
        except Exception as exc:
            raise HTTPException(status_code=422, detail="Immich API nicht erreichbar oder Token ungültig")
    updated = request.app.state.store.update_account(account_id, updates)
    return AccountPublic.from_account(updated)


@router.delete("/{account_id}", status_code=204)
async def delete_account(account_id: str, request: Request):
    ok = request.app.state.store.delete_account(account_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Account nicht gefunden")
    request.app.state.thumbnail_cache.clear_account(account_id)
    from routers.faces import invalidate_match_cache
    invalidate_match_cache()


@router.post("/{account_id}/refresh", response_model=AccountPublic)
async def refresh_account(account_id: str, request: Request):
    """Re-fetch user_id and other metadata from Immich."""
    account = request.app.state.store.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account nicht gefunden")
    client = ImmichClient(account.immich_url, account.api_key)
    try:
        user_info = await client.validate()
        user_id = user_info.get("id")
        raw = request.app.state.store._data["accounts"].get(account_id)
        if raw and user_id:
            raw["user_id"] = user_id
            request.app.state.store._save()
        return AccountPublic.from_account(request.app.state.store.get_account(account_id))
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Immich-Anfrage fehlgeschlagen")


@router.get("/{account_id}/albums")
async def get_account_albums(account_id: str, request: Request):
    """List Immich albums for a specific account (for existing-album linking)."""
    account = request.app.state.store.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account nicht gefunden")
    client = ImmichClient(account.immich_url, account.api_key)
    try:
        albums = await client.get_albums()
        return [{"id": a["id"], "name": a.get("albumName", "?")} for a in albums]
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Immich-Anfrage fehlgeschlagen")


@router.get("/{account_id}/status", response_model=AccountStatus)
async def account_status(account_id: str, request: Request):
    account = request.app.state.store.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account nicht gefunden")
    client = ImmichClient(account.immich_url, account.api_key)
    try:
        user = await client.validate()
        return AccountStatus(
            id=account.id,
            name=account.name,
            color=account.color,
            reachable=True,
            user_name=user.get("name"),
        )
    except Exception as exc:
        return AccountStatus(
            id=account.id,
            name=account.name,
            color=account.color,
            reachable=False,
            error="Immich-Anfrage fehlgeschlagen",
        )
