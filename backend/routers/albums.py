"""Sync actions: name sync, album creation, refresh, undo, log."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from models.match import SyncNamesRequest, SyncAlbumRequest, SyncLogEntry, ManagedAlbum, SyncNamesMultiRequest, ExtendMatchRequest
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


@router.post("/names-multi", response_model=list[SyncLogEntry])
async def sync_names_multi(body: SyncNamesMultiRequest, request: Request):
    """Sync a canonical name + optionally create an album for N persons at once."""
    if len(body.persons) < 2:
        raise HTTPException(status_code=422, detail="Mindestens 2 Personen erforderlich")

    store = request.app.state.store
    accounts_persons: list[tuple] = []
    person_refs: list[dict] = []

    for entry in body.persons:
        acc = store.get_account(entry.account_id)
        if not acc:
            raise HTTPException(status_code=404, detail=f"Account {entry.account_id} nicht gefunden")
        accounts_persons.append((acc, entry.person_id))
        person_refs.append({
            "account_id": entry.account_id,
            "person_id": entry.person_id,
            "person_name": body.canonical_name,
            "account_name": acc.name,
            "account_color": acc.color,
        })

    # Preflight every selected person before any write is attempted.
    for acc, person_id in accounts_persons:
        try:
            await ImmichClient(acc.immich_url, acc.api_key).get_person(person_id)
        except Exception:
            raise HTTPException(
                status_code=422,
                detail=f"Person in Account '{acc.name}' konnte nicht validiert werden",
            )

    requested_album = bool(body.album_name or body.existing_album_id)
    owner_id = body.owner_account_id or body.persons[0].account_id
    manual_match_id = f"manual_{body.canonical_name.lower().replace(' ', '_')}_{owner_id[:8]}"
    if requested_album and any(a.match_id == manual_match_id for a in store.get_managed_albums()):
        raise HTTPException(
            status_code=409,
            detail="Für diese manuelle Zuordnung existiert bereits ein verwaltetes Album",
        )

    logs = await sync_service.sync_names_multi(accounts_persons, body.canonical_name)
    store.append_log(logs)

    # Mark all pairwise combinations as names-synced
    if all(e.status == "success" for e in logs):
        store.mark_all_pairs_synced([e.person_id for e in body.persons])

    wants_album = (body.album_name or body.existing_album_id) and all(e.status == "success" for e in logs)
    if wants_album:
        owner = store.get_account(owner_id)
        if not owner:
            raise HTTPException(status_code=404, detail=f"Owner-Account {owner_id} nicht gefunden")
        match_id = manual_match_id
        all_accounts = store.list_accounts()
        if body.existing_album_id:
            album_name = body.album_name or body.existing_album_id
            _, album_logs = await sync_service.link_existing_album(
                match_id=match_id,
                owner_account=owner,
                album_id=body.existing_album_id,
                album_name=album_name,
                all_accounts=all_accounts,
                person_refs=person_refs,
                store=store,
            )
        else:
            _, album_logs = await sync_service.create_shared_album(
                match_id=match_id,
                owner_account=owner,
                all_accounts=all_accounts,
                person_refs=person_refs,
                album_name=body.album_name,
                store=store,
            )
        store.append_log(album_logs)
        logs.extend(album_logs)

    return logs


@router.post("/extend", response_model=list[SyncLogEntry])
async def extend_match(body: ExtendMatchRequest, request: Request):
    """Add a new account/person to an existing managed album."""
    store = request.app.state.store
    albums = store.get_managed_albums()
    managed = next((a for a in albums if a.id == body.managed_album_id), None)
    if not managed:
        raise HTTPException(status_code=404, detail="Managed Album nicht gefunden")
    account = store.get_account(body.account_id)
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {body.account_id} nicht gefunden")
    all_accounts = store.list_accounts()
    logs = await sync_service.extend_match(
        managed=managed,
        new_account=account,
        person_id=body.person_id,
        person_name=body.person_name,
        canonical_name=body.canonical_name,
        all_accounts=all_accounts,
        store=store,
    )
    store.append_log(logs)
    # If name was synced, mark all new pairwise combinations as names-synced
    if body.canonical_name and any(e.action == "sync_names" and e.status == "success" for e in logs):
        # Re-fetch the updated album to get all person_ids
        updated = next((a for a in store.get_managed_albums() if a.id == managed.id), None)
        if updated:
            store.mark_all_pairs_synced([r["person_id"] for r in updated.person_refs])
    return logs


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
            "account_color": match.person_a.account_color,
        },
        {
            "account_id": match.person_b.account_id,
            "person_id": match.person_b.person_id,
            "person_name": match.person_b.person_name,
            "account_name": match.person_b.account_name,
            "account_color": match.person_b.account_color,
        },
    ]

    existing = [a for a in store.get_managed_albums() if a.match_id == body.match_id]
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Für diesen Match existiert bereits ein verwaltetes Album: '{existing[0].album_name}'.",
        )

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
    store = request.app.state.store
    albums = store.get_managed_albums()
    # Always inject live account_color and account_name so frontend never shows stale data
    account_map = {a.id: a for a in store.list_accounts()}
    for album in albums:
        for ref in album.person_refs:
            acc = account_map.get(ref.get("account_id", ""))
            if acc:
                ref["account_color"] = acc.color
                if not ref.get("account_name"):
                    ref["account_name"] = acc.name
    return albums


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
    if entry.action != "sync_names" or not entry.undo_data or entry.undone_at:
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
    if result.status == "success":
        from datetime import datetime, timezone
        store.mark_log_undone(entry.id, datetime.now(timezone.utc).isoformat())
    return result


@router.get("/log", response_model=list[SyncLogEntry])
async def get_sync_log(request: Request):
    return request.app.state.store.get_log()


@router.delete("/log", status_code=204)
async def clear_sync_log(request: Request):
    request.app.state.store.clear_log()


# ── Auto-sync config ───────────────────────────────────────────────────────

class AutoSyncConfig(BaseModel):
    enabled: bool
    time: str  # "HH:MM" in server local time


@router.get("/autosync-config", response_model=AutoSyncConfig)
async def get_autosync_config(request: Request):
    return request.app.state.store.get_auto_sync_config()


@router.put("/autosync-config", response_model=AutoSyncConfig)
async def set_autosync_config(body: AutoSyncConfig, request: Request):
    # Validate time format
    try:
        h, m = map(int, body.time.split(":"))
        assert 0 <= h <= 23 and 0 <= m <= 59
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid time format. Use HH:MM (e.g. 01:00)")
    request.app.state.store.set_auto_sync_config(body.enabled, body.time)
    return request.app.state.store.get_auto_sync_config()
