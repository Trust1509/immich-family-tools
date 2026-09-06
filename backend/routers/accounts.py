import logging

from fastapi import APIRouter, Request

import errors
from models.account import AccountCreate, AccountPublic, AccountStatus, AccountUpdate
from services.immich_client import ImmichClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

MIN_SUPPORTED_IMMICH_MAJOR = 3


def _reject_unsupported_version(version: dict) -> None:
    """Raise AppError(422) if the Immich server major version is too old.

    version is the JSON payload from GET /api/server/version, e.g.
    {"major": 3, "minor": 1, "patch": 0}.
    """
    major = version.get("major")
    minor = version.get("minor")
    if major is not None and major < MIN_SUPPORTED_IMMICH_MAJOR:
        raise errors.unsupported_immich_version(major, minor)


async def _check_immich_version(client: ImmichClient) -> None:
    """Fetch and enforce the minimum supported Immich version.

    Fails open: if the version endpoint itself can't be reached (e.g. an
    older Immich instance without it), we only log a warning instead of
    blocking the account — we don't want to lock out exotic setups.
    """
    try:
        version = await client.get_server_version()
    except Exception as exc:
        logger.warning("Could not fetch Immich server version: %s", exc)
        return
    _reject_unsupported_version(version)


@router.get("", response_model=list[AccountPublic])
async def list_accounts(request: Request):
    return [AccountPublic.from_account(a) for a in request.app.state.store.list_accounts()]


@router.post("", response_model=AccountPublic, status_code=201)
async def add_account(data: AccountCreate, request: Request):
    client = ImmichClient(data.immich_url, data.api_key)
    try:
        user_info = await client.validate()
    except Exception as exc:
        raise errors.immich_unreachable()
    await _check_immich_version(client)
    # Store the Immich user UUID — needed for album sharing
    user_id = user_info.get("id")
    return AccountPublic.from_account(request.app.state.store.add_account(data, user_id=user_id))


@router.put("/{account_id}", response_model=AccountPublic)
async def update_account(account_id: str, data: AccountUpdate, request: Request):
    account = request.app.state.store.get_account(account_id)
    if not account:
        raise errors.account_not_found()
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
            raise errors.immich_unreachable()
        await _check_immich_version(client)
        request.app.state.client_pool.invalidate(account_id)
    updated = request.app.state.store.update_account(account_id, updates)
    return AccountPublic.from_account(updated)


@router.delete("/{account_id}", status_code=204)
async def delete_account(account_id: str, request: Request):
    ok = request.app.state.store.delete_account(account_id)
    if not ok:
        raise errors.account_not_found()
    request.app.state.thumbnail_cache.clear_account(account_id)
    request.app.state.client_pool.invalidate(account_id)
    request.app.state.match_cache.invalidate()


@router.post("/{account_id}/refresh", response_model=AccountPublic)
async def refresh_account(account_id: str, request: Request):
    """Re-fetch user_id and other metadata from Immich."""
    account = request.app.state.store.get_account(account_id)
    if not account:
        raise errors.account_not_found()
    client = request.app.state.client_pool.get_for_account(account)
    try:
        user_info = await client.validate()
        user_id = user_info.get("id")
        if user_id:
            request.app.state.store.update_account(account_id, {"user_id": user_id})
        return AccountPublic.from_account(request.app.state.store.get_account(account_id))
    except Exception as exc:
        raise errors.immich_request_failed()


@router.get("/{account_id}/albums")
async def get_account_albums(account_id: str, request: Request):
    """List Immich albums for a specific account (for existing-album linking)."""
    account = request.app.state.store.get_account(account_id)
    if not account:
        raise errors.account_not_found()
    client = request.app.state.client_pool.get_for_account(account)
    try:
        albums = await client.get_albums()
        return [{"id": a["id"], "name": a.get("albumName", "?")} for a in albums]
    except Exception as exc:
        raise errors.immich_request_failed()


@router.get("/{account_id}/status", response_model=AccountStatus)
async def account_status(account_id: str, request: Request):
    account = request.app.state.store.get_account(account_id)
    if not account:
        raise errors.account_not_found()
    client = request.app.state.client_pool.get_for_account(account)
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
            error=errors.immich_request_failed().detail,
            error_key=errors.immich_request_failed().key,
        )
