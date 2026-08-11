"""Cross-account synchronisation actions."""
import logging
import uuid
import asyncio
from datetime import datetime, timezone

from services.immich_client import ImmichClient, AlbumNotFoundError
from services.config_store import ConfigStore
from typing import Optional
from models.account import Account
from models.match import ManagedAlbum, SyncLogEntry

logger = logging.getLogger(__name__)
_album_locks: dict[str, asyncio.Lock] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_add_results(result: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split add_assets_to_album's per-item results into (added, failed).

    "duplicate" errors are semantically harmless — the asset was already in
    the album — so they land in neither list and are silently ignored.
    """
    added = [r for r in result if r.get("success")]
    failed = [
        r for r in result
        if not r.get("success") and r.get("error") != "duplicate"
    ]
    return added, failed


def _partial_failure_log(action: str, account_name: str, failed: list[dict]) -> SyncLogEntry:
    return SyncLogEntry(
        id=str(uuid.uuid4()), timestamp=_now(), action=action,
        details=(
            f"{len(failed)} Assets von '{account_name}' konnten nicht hinzugefügt werden "
            "(z. B. fehlende Berechtigung)"
        ),
        status="error", error_message="IMMICH_API_ERROR",
        message_key="log_assets_partial_failure",
        message_params={"count": len(failed), "account": account_name},
    )


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
            details="Album-Mitglieder konnten nicht abgerufen werden",
            status="error", error_message="IMMICH_API_ERROR",
            message_key="log_album_members_fetch_failed", message_params={},
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
            message_key="log_album_shared",
            message_params={"album": album_name, "names": ", ".join(a.name for a in to_add)},
        ))
    except Exception as exc:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="share_album",
            details=f"Sharing mit {', '.join(a.name for a in to_add)} fehlgeschlagen",
            status="error", error_message="IMMICH_API_ERROR",
            message_key="log_share_failed",
            message_params={"names": ", ".join(a.name for a in to_add)},
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
            previous = await client.get_person(person_id)
            previous_name = previous.get("name", "")
            if previous_name != canonical_name:
                await client.update_person(person_id, {"name": canonical_name})
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
                        "previous_name": previous_name,
                    },
                    message_key="log_name_synced",
                    message_params={"account": account.name, "person": person_id, "name": canonical_name},
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
                    error_message="IMMICH_API_ERROR",
                    message_key="log_name_sync_failed",
                    message_params={"account": account.name, "person": person_id},
                )
            )
    return results


async def sync_names_multi(
    accounts_persons: list[tuple[Account, str]],
    canonical_name: str,
) -> list[SyncLogEntry]:
    """Set the same name on N persons across N accounts."""
    results: list[SyncLogEntry] = []
    for account, person_id in accounts_persons:
        entry_id = str(uuid.uuid4())
        try:
            client = ImmichClient(account.immich_url, account.api_key)
            previous = await client.get_person(person_id)
            previous_name = previous.get("name", "")
            if previous_name != canonical_name:
                await client.update_person(person_id, {"name": canonical_name})
            results.append(SyncLogEntry(
                id=entry_id, timestamp=_now(), action="sync_names",
                details=f"Account '{account.name}' – person {person_id} → '{canonical_name}'",
                status="success",
                undo_data={
                    "account_id": account.id,
                    "person_id": person_id,
                    "previous_name": previous_name,
                },
                message_key="log_name_synced",
                message_params={"account": account.name, "person": person_id, "name": canonical_name},
            ))
        except Exception as exc:
            logger.error("sync_names_multi failed for account %s: %s", account.name, exc)
            results.append(SyncLogEntry(
                id=entry_id, timestamp=_now(), action="sync_names",
                details=f"Account '{account.name}' – person {person_id}",
                status="error", error_message="IMMICH_API_ERROR",
                message_key="log_name_sync_failed",
                message_params={"account": account.name, "person": person_id},
            ))
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
            message_key="log_album_created",
            message_params={"album": album_name, "account": owner_account.name, "count": len(initial_asset_ids)},
        ))
    except Exception as exc:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="create_album",
            details=f"Album '{album_name}' konnte nicht erstellt werden",
            status="error", error_message="IMMICH_API_ERROR",
            message_key="log_album_create_failed",
            message_params={"album": album_name},
        ))
        return None, logs

    total_assets = len(initial_asset_ids)

    # ── 2. Share album with all other accounts ─────────────────────────
    participant_ids = {r["account_id"] for r in person_refs}
    other_accounts = [
        a for a in all_accounts
        if a.id != owner_account.id and a.id in participant_ids
    ]
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
                result = await client.add_assets_to_album(album_id, asset_ids)
                added, failed = _split_add_results(result)
                total_assets += len(added)
                if added:
                    logs.append(SyncLogEntry(
                        id=str(uuid.uuid4()), timestamp=_now(), action="album_add_assets",
                        details=f"{len(added)} Assets von '{account.name}' hinzugefügt",
                        status="success",
                        message_key="log_assets_added",
                        message_params={"count": len(added), "account": account.name},
                    ))
                if failed:
                    logs.append(_partial_failure_log("album_add_assets", account.name, failed))
        except Exception as exc:
            logs.append(SyncLogEntry(
                id=str(uuid.uuid4()), timestamp=_now(), action="album_add_assets",
                details=f"Assets von '{account.name}' konnten nicht hinzugefügt werden",
                status="error", error_message="IMMICH_API_ERROR",
                message_key="log_assets_add_failed",
                message_params={"account": account.name},
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
        status="partial" if any(entry.status == "error" for entry in logs) else "active",
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
    participant_ids = {r["account_id"] for r in person_refs}
    other_accounts = [
        a for a in all_accounts
        if a.id != owner_account.id and a.id in participant_ids
    ]
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
            message_key="log_album_not_found",
            message_params={"album": album_name},
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
                result = await client.add_assets_to_album(album_id, new_ids)
                added, failed = _split_add_results(result)
                added_ids = {r["id"] for r in added}
                existing_ids.update(added_ids)
                total_assets += len(added)
                if added:
                    logs.append(SyncLogEntry(
                        id=str(uuid.uuid4()), timestamp=_now(), action="album_add_assets",
                        details=f"{len(added)} Assets von '{account.name}' zu '{album_name}' hinzugefügt",
                        status="success",
                        message_key="log_assets_linked",
                        message_params={"count": len(added), "account": account.name, "album": album_name},
                    ))
                if failed:
                    logs.append(_partial_failure_log("album_add_assets", account.name, failed))
        except Exception as exc:
            logs.append(SyncLogEntry(
                id=str(uuid.uuid4()), timestamp=_now(), action="album_add_assets",
                details=f"Assets von '{account.name}' fehlgeschlagen",
                status="error", error_message="IMMICH_API_ERROR",
                message_key="log_assets_link_failed",
                message_params={"account": account.name},
            ))

    managed = ManagedAlbum(
        id=str(uuid.uuid4()), match_id=match_id, album_id=album_id,
        album_name=album_name, owner_account_id=owner_account.id,
        person_refs=person_refs, created_at=_now(), last_synced_at=_now(),
        total_assets=total_assets,
        status="partial" if any(entry.status == "error" for entry in logs) else "active",
    )
    store.add_managed_album(managed)
    return managed, logs


async def _refresh_managed_album_unlocked(
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
            message_key="log_owner_account_missing", message_params={},
        )]

    owner_client = ImmichClient(owner.immich_url, owner.api_key)
    participant_ids = {ref["account_id"] for ref in managed.person_refs}
    share_accounts = [
        account for account in all_accounts
        if account.id != owner.id and account.id in participant_ids
    ]
    logs.extend(
        await _share_album_if_needed(
            owner_client, managed.album_id, managed.album_name, share_accounts
        )
    )
    try:
        existing_ids = set(await owner_client.get_album_assets(managed.album_id))
    except AlbumNotFoundError:
        return [SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
            details=f"Album '{managed.album_name}' wurde in Immich gelöscht. Eintrag kann über die Alben-Übersicht entfernt werden.",
            status="error", error_message="ALBUM_DELETED",
            message_key="log_album_deleted",
            message_params={"album": managed.album_name},
        )]
    except Exception as exc:
        return [SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
            details="Album nicht abrufbar",
            status="error",
            message_key="log_album_unreachable", message_params={},
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
                result = await client.add_assets_to_album(managed.album_id, new_ids)
                added, failed = _split_add_results(result)
                added_ids = {r["id"] for r in added}
                existing_ids.update(added_ids)
                new_total += len(added)
                if added:
                    logs.append(SyncLogEntry(
                        id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
                        details=f"{len(added)} neue Assets von '{account.name}' zum Album '{managed.album_name}' hinzugefügt",
                        status="success",
                        message_key="log_assets_added_to_album",
                        message_params={"count": len(added), "account": account.name, "album": managed.album_name},
                    ))
                if failed:
                    logs.append(_partial_failure_log("refresh_album", account.name, failed))
        except Exception as exc:
            logs.append(SyncLogEntry(
                id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
                details=f"Sync von '{account.name}' fehlgeschlagen",
                status="error", error_message="IMMICH_API_ERROR",
                message_key="log_sync_failed",
                message_params={"account": account.name},
            ))

    # Update last_synced_at and total_assets
    managed.last_synced_at = _now()
    managed.total_assets = len(existing_ids)
    managed.status = "partial" if any(entry.status == "error" for entry in logs) else "active"
    store.update_managed_album(managed)

    if not logs:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
            details=f"Album '{managed.album_name}': Keine neuen Assets gefunden",
            status="success",
            message_key="log_no_new_assets",
            message_params={"album": managed.album_name},
        ))
    return logs


async def refresh_managed_album(
    managed: ManagedAlbum,
    all_accounts: list[Account],
    store: ConfigStore,
) -> list[SyncLogEntry]:
    """Serialize refreshes per album across manual and automatic sync."""
    lock = _album_locks.setdefault(managed.id, asyncio.Lock())
    async with lock:
        return await _refresh_managed_album_unlocked(managed, all_accounts, store)


async def extend_match(
    managed: ManagedAlbum,
    new_account: Account,
    person_id: str,
    person_name: Optional[str],
    canonical_name: Optional[str],
    all_accounts: list[Account],
    store: ConfigStore,
) -> list[SyncLogEntry]:
    """Add a new account/person to an existing managed album."""
    logs: list[SyncLogEntry] = []
    account_map = {a.id: a for a in all_accounts}

    # Guard: person already in this album
    already = any(
        r["account_id"] == new_account.id and r["person_id"] == person_id
        for r in managed.person_refs
    )
    if already:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="extend_match",
            details=f"Person {person_id} aus '{new_account.name}' ist bereits in Album '{managed.album_name}' enthalten.",
            status="error",
            message_key="log_person_already_in_album",
            message_params={"person": person_id, "account": new_account.name, "album": managed.album_name},
        ))
        return logs

    owner = account_map.get(managed.owner_account_id)
    if not owner:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="extend_match",
            details="Owner-Account nicht mehr vorhanden.",
            status="error",
            message_key="log_owner_account_missing", message_params={},
        ))
        return logs

    owner_client = ImmichClient(owner.immich_url, owner.api_key)

    # Validate the selected person before sharing or mutating the album.
    new_client = ImmichClient(new_account.immich_url, new_account.api_key)
    try:
        await new_client.get_person(person_id)
    except Exception:
        return [SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="extend_match",
            details=f"Person in '{new_account.name}' konnte nicht validiert werden",
            status="error", error_message="IMMICH_API_ERROR",
            message_key="log_person_validation_failed",
            message_params={"account": new_account.name},
        )]

    # 1. Share album with new account
    share_logs = await _share_album_if_needed(owner_client, managed.album_id, managed.album_name, [new_account])
    logs.extend(share_logs)

    # 2. Fetch existing asset IDs to avoid duplicates
    try:
        existing_ids = set(await owner_client.get_album_assets(managed.album_id))
    except Exception as exc:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="extend_match",
            details="Album-Assets konnten nicht abgerufen werden",
            status="error", error_message="IMMICH_API_ERROR",
            message_key="log_album_assets_fetch_failed", message_params={},
        ))
        return logs

    # 3. Add new person's assets
    try:
        assets = await new_client.get_person_assets(person_id)
        new_ids = [a["id"] for a in assets if a["id"] not in existing_ids]
        added: list[dict] = []
        if new_ids:
            result = await new_client.add_assets_to_album(managed.album_id, new_ids)
            added, failed = _split_add_results(result)
            if added:
                logs.append(SyncLogEntry(
                    id=str(uuid.uuid4()), timestamp=_now(), action="extend_match",
                    details=f"{len(added)} Assets von '{new_account.name}' zu '{managed.album_name}' hinzugefügt",
                    status="success",
                    message_key="log_assets_linked",
                    message_params={"count": len(added), "account": new_account.name, "album": managed.album_name},
                ))
            if failed:
                logs.append(_partial_failure_log("extend_match", new_account.name, failed))
        else:
            logs.append(SyncLogEntry(
                id=str(uuid.uuid4()), timestamp=_now(), action="extend_match",
                details=f"Keine neuen Assets von '{new_account.name}' (alle bereits im Album)",
                status="success",
                message_key="log_no_new_assets_from_account",
                message_params={"account": new_account.name},
            ))
        total = len(existing_ids) + len(added)
    except Exception as exc:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="extend_match",
            details=f"Assets von '{new_account.name}' konnten nicht hinzugefügt werden",
            status="error", error_message="IMMICH_API_ERROR",
            message_key="log_assets_add_failed",
            message_params={"account": new_account.name},
        ))
        total = len(existing_ids)

    # 4. Optionally rename person
    if canonical_name:
        try:
            previous = await new_client.get_person(person_id)
            previous_name = previous.get("name", "")
            if previous_name != canonical_name:
                await new_client.update_person(person_id, {"name": canonical_name})
            logs.append(SyncLogEntry(
                id=str(uuid.uuid4()), timestamp=_now(), action="sync_names",
                details=f"Account '{new_account.name}' – person {person_id} → '{canonical_name}'",
                status="success",
                undo_data={
                    "account_id": new_account.id,
                    "person_id": person_id,
                    "previous_name": previous_name,
                },
                message_key="log_name_synced",
                message_params={"account": new_account.name, "person": person_id, "name": canonical_name},
            ))
        except Exception as exc:
            logs.append(SyncLogEntry(
                id=str(uuid.uuid4()), timestamp=_now(), action="sync_names",
                details=f"Umbenennung in '{new_account.name}' fehlgeschlagen",
                status="error", error_message="IMMICH_API_ERROR",
                message_key="log_rename_failed",
                message_params={"account": new_account.name},
            ))

    # 5. Update managed album record
    # Use canonical_name if renaming, else fall back to person_name (display name), else None
    stored_name = canonical_name if canonical_name else person_name
    managed.person_refs.append({
        "account_id": new_account.id,
        "person_id": person_id,
        "person_name": stored_name,
        "account_name": new_account.name,
        "account_color": new_account.color,
    })
    managed.last_synced_at = _now()
    managed.total_assets = total
    store.update_managed_album(managed)

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
            message_key="log_undo_name_reverted",
            message_params={"person": person_id, "account": account.name, "name": previous_name},
        )
    except Exception as exc:
        return SyncLogEntry(
            id=entry_id, timestamp=_now(), action="undo_sync_names",
            details=f"Undo failed for person {person_id}",
            status="error", error_message="IMMICH_API_ERROR",
            message_key="log_undo_failed",
            message_params={"person": person_id},
        )
