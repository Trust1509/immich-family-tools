"""Cross-account synchronisation actions."""
import logging
import uuid
from datetime import datetime, timezone

from services.immich_client import ImmichClient, AlbumNotFoundError
from services.config_store import ConfigStore
from models.account import Account
from models.match import ManagedAlbum, SyncLogEntry

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _share_album_if_needed(
    owner_client: ImmichClient,
    album_id: str,
    album_name: str,
    accounts_to_share: list[Account],
) -> list[SyncLogEntry]:
    """
    Share album with accounts that aren't already members.
    Returns log entries only for accounts that were actually added or failed.
    Silently skips accounts that are already editors.
    """
    logs: list[SyncLogEntry] = []
    if not accounts_to_share:
        return logs

    # Fetch current album members
    try:
        existing_ids = await owner_client.get_album_user_ids(album_id)
    except Exception as exc:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="share_album",
            details=f"Album-Mitglieder konnten nicht abgerufen werden: {exc}",
            status="error", error_message=str(exc),
        ))
        return logs

    # Only add accounts not already in the album
    to_add = [a for a in accounts_to_share if a.user_id and a.user_id not in existing_ids]
    already_there = [a for a in accounts_to_share if a.user_id and a.user_id in existing_ids]

    if already_there:
        logger.info("Already in album '%s': %s", album_name, [a.name for a in already_there])

    if not to_add:
        return logs  # All accounts already have access — no log entry needed

    user_entries = [{"userId": a.user_id, "role": "editor"} for a in to_add]
    try:
        await owner_client.share_album_with_users(album_id, user_entries)
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="share_album",
            details=f"Album '{album_name}' geteilt mit: {', '.join(a.name for a in to_add)}",
            status="success",
        ))
    except Exception as exc:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="share_album",
            details=f"Sharing mit {', '.join(a.name for a in to_add)} fehlgeschlagen",
            status="error", error_message=str(exc),
        ))
    return logs


async def sync_names(
    account_a: Account,
    person_id_a: str,
    account_b: Account,
    person_id_b: str,
    canonical_name: str,
) -> list[SyncLogEntry]:
    """Set the same name on both persons."""
    results: list[SyncLogEntry] = []
    for account, person_id in [(account_a, person_id_a), (account_b, person_id_b)]:
        entry_id = str(uuid.uuid4())
        try:
            client = ImmichClient(account.immich_url, account.api_key)
            updated = await client.update_person(person_id, {"name": canonical_name})
            results.append(
                SyncLogEntry(
                    id=entry_id,
                    timestamp=_now(),
                    action="sync_names",
                    details=f"Account '{account.name}' – person {person_id} → '{canonical_name}'",
                    status="success",
                    undo_data={
                        "account_id": account.id,
                        "person_id": person_id,
                        "previous_name": updated.get("name", ""),
                    },
                )
            )
        except Exception as exc:
            logger.error("sync_names failed for account %s: %s", account.name, exc)
            results.append(
                SyncLogEntry(
                    id=entry_id,
                    timestamp=_now(),
                    action="sync_names",
                    details=f"Account '{account.name}' – person {person_id}",
                    status="error",
                    error_message=str(exc),
                )
            )
    return results


async def create_shared_album(
    match_id: str,
    owner_account: Account,
    all_accounts: list[Account],
    person_refs: list[dict],   # [{"account_id": ..., "person_id": ...}]
    album_name: str,
    store: ConfigStore,
) -> tuple[ManagedAlbum | None, list[SyncLogEntry]]:
    """
    Create a shared album in the owner account, share it with all other
    accounts as editors, then add each account's assets using their own API key.
    """
    logs: list[SyncLogEntry] = []
    account_map = {a.id: a for a in all_accounts}

    # ── 1. Create album in owner account ──────────────────────────────
    owner_client = ImmichClient(owner_account.immich_url, owner_account.api_key)
    owner_ref = next((r for r in person_refs if r["account_id"] == owner_account.id), None)

    initial_asset_ids: list[str] = []
    if owner_ref:
        try:
            assets = await owner_client.get_person_assets(owner_ref["person_id"])
            initial_asset_ids = [a["id"] for a in assets]
        except Exception as exc:
            logger.warning("Could not load owner assets: %s", exc)

    try:
        album = await owner_client.create_album(album_name, initial_asset_ids)
        album_id = album["id"]
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="create_album",
            details=f"Album '{album_name}' in '{owner_account.name}' mit {len(initial_asset_ids)} Assets erstellt",
            status="success",
            undo_data={"account_id": owner_account.id, "album_id": album_id},
        ))
    except Exception as exc:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="create_album",
            details=f"Album '{album_name}' konnte nicht erstellt werden",
            status="error", error_message=str(exc),
        ))
        return None, logs

    total_assets = len(initial_asset_ids)

    # ── 2. Share album with all other accounts ─────────────────────────
    other_accounts = [a for a in all_accounts if a.id != owner_account.id]
    share_logs = await _share_album_if_needed(owner_client, album_id, album_name, other_accounts)
    logs.extend(share_logs)

    # ── 3. Add each account's assets using their own API key ──────────
    for ref in person_refs:
        if ref["account_id"] == owner_account.id:
            continue  # already added in step 1
        account = account_map.get(ref["account_id"])
        if not account:
            continue
        client = ImmichClient(account.immich_url, account.api_key)
        try:
            assets = await client.get_person_assets(ref["person_id"])
            asset_ids = [a["id"] for a in assets]
            if asset_ids:
                await client.add_assets_to_album(album_id, asset_ids)
                total_assets += len(asset_ids)
                logs.append(SyncLogEntry(
                    id=str(uuid.uuid4()), timestamp=_now(), action="album_add_assets",
                    details=f"{len(asset_ids)} Assets von '{account.name}' hinzugefügt",
                    status="success",
                ))
        except Exception as exc:
            logs.append(SyncLogEntry(
                id=str(uuid.uuid4()), timestamp=_now(), action="album_add_assets",
                details=f"Assets von '{account.name}' konnten nicht hinzugefügt werden",
                status="error", error_message=str(exc),
            ))

    # ── 4. Save managed album record ──────────────────────────────────
    managed = ManagedAlbum(
        id=str(uuid.uuid4()),
        match_id=match_id,
        album_id=album_id,
        album_name=album_name,
        owner_account_id=owner_account.id,
        person_refs=person_refs,
        created_at=_now(),
        last_synced_at=_now(),
        total_assets=total_assets,
    )
    store.add_managed_album(managed)
    return managed, logs


async def link_existing_album(
    match_id: str,
    owner_account: Account,
    album_id: str,
    album_name: str,
    all_accounts: list[Account],
    person_refs: list[dict],
    store: ConfigStore,
) -> tuple[ManagedAlbum | None, list[SyncLogEntry]]:
    """Link an existing Immich album to a match, share it, and fill with assets."""
    logs: list[SyncLogEntry] = []
    account_map = {a.id: a for a in all_accounts}
    owner_client = ImmichClient(owner_account.immich_url, owner_account.api_key)

    # Share with accounts not already in the album
    other_accounts = [a for a in all_accounts if a.id != owner_account.id]
    share_logs = await _share_album_if_needed(owner_client, album_id, album_name, other_accounts)
    logs.extend(share_logs)

    # Get existing asset IDs to avoid duplicates
    try:
        existing_ids = set(await owner_client.get_album_assets(album_id))
    except AlbumNotFoundError:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="link_album",
            details=f"Album '{album_name}' existiert nicht in Immich.",
            status="error", error_message="ALBUM_DELETED",
        ))
        return None, logs
    except Exception:
        existing_ids = set()

    total_assets = len(existing_ids)

    # Add assets from all accounts
    for ref in person_refs:
        account = account_map.get(ref["account_id"])
        if not account:
            continue
        client = ImmichClient(account.immich_url, account.api_key)
        try:
            assets = await client.get_person_assets(ref["person_id"])
            new_ids = [a["id"] for a in assets if a["id"] not in existing_ids]
            if new_ids:
                await client.add_assets_to_album(album_id, new_ids)
                existing_ids.update(new_ids)
                total_assets += len(new_ids)
                logs.append(SyncLogEntry(
                    id=str(uuid.uuid4()), timestamp=_now(), action="album_add_assets",
                    details=f"{len(new_ids)} Assets von '{account.name}' zu '{album_name}' hinzugefügt",
                    status="success",
                ))
        except Exception as exc:
            logs.append(SyncLogEntry(
                id=str(uuid.uuid4()), timestamp=_now(), action="album_add_assets",
                details=f"Assets von '{account.name}' fehlgeschlagen",
                status="error", error_message=str(exc),
            ))

    managed = ManagedAlbum(
        id=str(uuid.uuid4()), match_id=match_id, album_id=album_id,
        album_name=album_name, owner_account_id=owner_account.id,
        person_refs=person_refs, created_at=_now(), last_synced_at=_now(),
        total_assets=total_assets,
    )
    store.add_managed_album(managed)
    return managed, logs


async def refresh_managed_album(
    managed: ManagedAlbum,
    all_accounts: list[Account],
    store: ConfigStore,
) -> list[SyncLogEntry]:
    """
    Sync new assets into an existing managed album.
    Each account uses its own API key to add its own new assets.
    """
    logs: list[SyncLogEntry] = []
    account_map = {a.id: a for a in all_accounts}
    new_total = 0

    # Get current asset IDs in album (using owner's key)
    owner = account_map.get(managed.owner_account_id)
    if not owner:
        return [SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
            details="Owner-Account nicht mehr vorhanden",
            status="error",
        )]

    owner_client = ImmichClient(owner.immich_url, owner.api_key)
    try:
        existing_ids = set(await owner_client.get_album_assets(managed.album_id))
    except AlbumNotFoundError:
        return [SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
            details=f"Album '{managed.album_name}' wurde in Immich gelöscht. Eintrag kann über die Alben-Übersicht entfernt werden.",
            status="error", error_message="ALBUM_DELETED",
        )]
    except Exception as exc:
        return [SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
            details=f"Album nicht abrufbar: {exc}",
            status="error",
        )]

    for ref in managed.person_refs:
        account = account_map.get(ref["account_id"])
        if not account:
            continue
        client = ImmichClient(account.immich_url, account.api_key)
        try:
            assets = await client.get_person_assets(ref["person_id"])
            new_ids = [a["id"] for a in assets if a["id"] not in existing_ids]
            if new_ids:
                await client.add_assets_to_album(managed.album_id, new_ids)
                existing_ids.update(new_ids)
                new_total += len(new_ids)
                logs.append(SyncLogEntry(
                    id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
                    details=f"{len(new_ids)} neue Assets von '{account.name}' zum Album '{managed.album_name}' hinzugefügt",
                    status="success",
                ))
        except Exception as exc:
            logs.append(SyncLogEntry(
                id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
                details=f"Sync von '{account.name}' fehlgeschlagen",
                status="error", error_message=str(exc),
            ))

    # Update last_synced_at and total_assets
    managed.last_synced_at = _now()
    managed.total_assets = len(existing_ids)
    store.update_managed_album(managed)

    if not logs:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
            details=f"Album '{managed.album_name}': Keine neuen Assets gefunden",
            status="success",
        ))
    return logs


async def undo_sync_name(account: Account, person_id: str, previous_name: str) -> SyncLogEntry:
    entry_id = str(uuid.uuid4())
    try:
        client = ImmichClient(account.immich_url, account.api_key)
        await client.update_person(person_id, {"name": previous_name})
        return SyncLogEntry(
            id=entry_id, timestamp=_now(), action="undo_sync_names",
            details=f"Reverted person {person_id} in '{account.name}' to '{previous_name}'",
            status="success",
        )
    except Exception as exc:
        return SyncLogEntry(
            id=entry_id, timestamp=_now(), action="undo_sync_names",
            details=f"Undo failed for person {person_id}",
            status="error", error_message=str(exc),
        )
