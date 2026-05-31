"""Sync actions: name sync, album creation, refresh, undo, log."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from models.match import SyncNamesRequest, SyncAlbumRequest, SyncLogEntry, ManagedAlbum
from services import sync_service
from services.immich_client import ImmichClient

router = APIRouter(prefix="/api/sync", tags=["sync"])


def _resolve_match(match_id: str, matches: list):
    return next((m for m in matches if m.id == match_id), None)


@router.post("/names", response_model=list[SyncLogEntry])
async def sync_names(body: SyncNamesRequest, request: Request):
    store = request.app.state.store
    from routers.faces import get_matches
    matches = await get_matches(request)
    match = _resolve_match(body.match_id, matches)
    if not match:
        raise HTTPException(status_code=404, detail="Match nicht gefunden")

    acc_a = store.get_account(match.person_a.account_id)
    acc_b = store.get_account(match.person_b.account_id)
    if not acc_a or not acc_b:
        raise HTTPException(status_code=404, detail="Account nicht gefunden")

    entries = await sync_service.sync_names(
        account_a=acc_a, person_id_a=match.person_a.person_id,
        account_b=acc_b, person_id_b=match.person_b.person_id,
        canonical_name=body.name,
    )
    store.append_log(entries)
    if all(e.status == "success" for e in entries):
        store.mark_names_synced(body.match_id)
    from routers.faces import _cache
    _cache["matches"] = None
    return entries


@router.post("/album", response_model=list[SyncLogEntry])
async def create_album(body: SyncAlbumRequest, request: Request):
    store = request.app.state.store
    from routers.faces import get_matches
    matches = await get_matches(request)
    match = _resolve_match(body.match_id, matches)
    if not match:
        raise HTTPException(status_code=404, detail="Match nicht gefunden")

    owner = store.get_account(body.owner_account_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner-Account nicht gefunden")

    all_accounts = store.list_accounts()
    person_refs = [
        {
            "account_id": match.person_a.account_id,
            "person_id": match.person_a.person_id,
            "person_name": match.person_a.person_name,
            "account_name": match.person_a.account_name,
        },
        {
            "account_id": match.person_b.account_id,
            "person_id": match.person_b.person_id,
            "person_name": match.person_b.person_name,
            "account_name": match.person_b.account_name,
        },
    ]

    if body.existing_album_id:
        # Link existing album
        album_name = body.album_name or body.existing_album_id
        _, logs = await sync_service.link_existing_album(
            match_id=body.match_id,
            owner_account=owner,
            album_id=body.existing_album_id,
            album_name=album_name,
            all_accounts=all_accounts,
            person_refs=person_refs,
            store=store,
        )
    else:
        # Create new album
        if not body.album_name:
            raise HTTPException(status_code=422, detail="album_name erforderlich für neues Album")
        # Duplicate check
        existing = [a for a in store.get_managed_albums() if a.match_id == body.match_id]
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Für diesen Match existiert bereits ein verwaltetes Album: '{existing[0].album_name}'. Bitte verwende 'Vorhandenes Album verknüpfen'."
            )
        _, logs = await sync_service.create_shared_album(
            match_id=body.match_id,
            owner_account=owner,
            all_accounts=all_accounts,
            person_refs=person_refs,
            album_name=body.album_name,
            store=store,
        )

    store.append_log(logs)
    return logs


@router.post("/album/{managed_album_id}/refresh", response_model=list[SyncLogEntry])
async def refresh_album(managed_album_id: str, request: Request):
    store = request.app.state.store
    albums = store.get_managed_albums()
    managed = next((a for a in albums if a.id == managed_album_id), None)
    if not managed:
        raise HTTPException(status_code=404, detail="Managed Album nicht gefunden")
    logs = await sync_service.refresh_managed_album(
        managed=managed, all_accounts=store.list_accounts(), store=store,
    )
    store.append_log(logs)
    return logs


@router.get("/albums", response_model=list[ManagedAlbum])
async def list_managed_albums(request: Request):
    return request.app.state.store.get_managed_albums()


@router.delete("/albums/{managed_album_id}", status_code=204)
async def delete_managed_album(managed_album_id: str, request: Request):
    """Remove a managed album record (does NOT delete the album in Immich)."""
    ok = request.app.state.store.delete_managed_album(managed_album_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Managed Album nicht gefunden")


class UndoRequest(BaseModel):
    log_entry_id: str


@router.post("/undo", response_model=SyncLogEntry)
async def undo_action(body: UndoRequest, request: Request):
    store = request.app.state.store
    log = store.get_log()
    entry = next((e for e in log if e.id == body.log_entry_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Log-Eintrag nicht gefunden")
    if entry.action != "sync_names" or not entry.undo_data:
        raise HTTPException(status_code=422, detail="Aktion kann nicht rückgängig gemacht werden")
    undo = entry.undo_data
    account = store.get_account(undo["account_id"])
    if not account:
        raise HTTPException(status_code=404, detail="Account nicht mehr vorhanden")
    result = await sync_service.undo_sync_name(
        account=account, person_id=undo["person_id"],
        previous_name=undo.get("previous_name", ""),
    )
    store.append_log([result])
    return result


@router.get("/log", response_model=list[SyncLogEntry])
async def get_sync_log(request: Request):
    return request.app.state.store.get_log()
