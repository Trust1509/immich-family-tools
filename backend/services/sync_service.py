"""Cross-account synchronisation actions."""
import logging
import uuid
import asyncio
from datetime import datetime, timezone

import errors
from services.immich_client import ImmichClient, AlbumNotFoundError
from services.config_store import ConfigStore
from typing import Optional
from models.account import Account
from models.match import ManagedAlbum, SyncLogEntry

logger = logging.getLogger(__name__)
# Der Schluessel traegt die EREIGNISSCHLEIFE mit — siehe die ausfuehrliche
# Begruendung bei `config_store._gruppen_schloesser`. Dieselbe Schwaeche lag
# hier seit jeher; behoben wird die Klasse, nicht die Instanz.
_album_locks: dict[tuple[int, str], asyncio.Lock] = {}


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


def album_gab_es_schon(album_name: str) -> SyncLogEntry:
    """Der Eintrag fuer den zweiten Klick (#86).

    Er ist **Erfolg**, nicht Fehler: Ein hektischer zweiter Klick auf
    „Album erstellen" hat nichts falsch gemacht, und der gewuenschte Zustand
    ist erreicht. Sichtbar ist er trotzdem, weil der zweite Klick etwas
    anderes getan hat als der erste — das war die Owner-Entscheidung zu #86,
    ausdruecklich gegen den stillen Erfolg.

    `album_name` ist der Name des BESTEHENDEN Albums, nicht der angefragte.
    Beim Doppelklick sind beide gleich; kommt die zweite Anfrage mit einem
    anderen Namen, ist der bestehende die Auskunft, die dem Nutzer hilft.
    """
    return SyncLogEntry(
        id=str(uuid.uuid4()), timestamp=_now(), action="create_album",
        details=f"Album '{album_name}' bestand für diesen Treffer bereits — nichts angelegt",
        status="success",
        message_key="log_album_already_exists",
        message_params={"album": album_name},
    )


def manuelle_kennung_kollidiert(album_name: str) -> SyncLogEntry:
    """Dieselbe Kollision, aber im RENNEN — da ist Ablehnen zu spaet.

    Die Vorabpruefung im Router faengt den Normalfall: Sie sieht das fremde
    Album und lehnt ab, bevor irgendetwas geschrieben ist. Kommen beide
    Aufrufe gleichzeitig, sieht sie noch nichts — das Album entsteht erst
    danach. Unter dem Schloss ist dann bereits umbenannt, und eine Ablehnung
    waere genau die Klasse, die dieses Projekt dreimal getroffen hat: ein
    Fehler, der sich als Eingabefehler ausgibt, nachdem geschrieben wurde.

    Also ein FEHLEREINTRAG statt einer Ablehnung. Er ist nicht „gab es schon"
    — das waere die Luege, die der Fremdpruefer und der Blindpruefer
    unabhaengig voneinander gefunden haben.
    """
    return SyncLogEntry(
        id=str(uuid.uuid4()), timestamp=_now(), action="create_album",
        details=(f"Album '{album_name}' gehört unter diesem Namen zu ANDEREN "
                 f"Personen — es wurde keines angelegt"),
        status="error", error_message="MANUAL_MATCH_ID_COLLISION",
        message_key="log_manual_match_collision",
        message_params={"album": album_name},
    )


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
    group_id: str,
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
        # Die Kennung loest der AUFRUFER auf (ConfigStore.resolve_group_id),
        # weil dort die ausdrueckliche Wahl des Nutzers ankommt (#81).
        #
        # PFLICHT, kein Rueckfall auf die Namensregel: Ein `or`-Rueckfall
        # haette genau das getan, wovor der Kommentar am Modell warnt — wer
        # die Wahl des Nutzers vergisst, bekaeme stilles Raten statt eines
        # lauten Fehlers. Gemessen: Mit Rueckfall ueberlebte die Mutation
        # "Router verwirft die aufgeloeste Kennung" die volle Suite
        # (Gegenpruefer 21.09.2026).
        group_id=group_id,
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
    group_id: str,
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
        album_name=album_name, group_id=group_id,
        owner_account_id=owner_account.id,
        person_refs=person_refs, created_at=_now(), last_synced_at=_now(),
        total_assets=total_assets,
        status="partial" if any(entry.status == "error" for entry in logs) else "active",
    )
    store.add_managed_album(managed)
    return managed, logs


def _uebernimm_immich_namen(
    managed: ManagedAlbum, immich_name: Optional[str]
) -> Optional[SyncLogEntry]:
    """Der Name in Immich gewinnt (#97, CONTEXT.md „Album Name Source").

    Ein leerer oder fehlender Name aus Immich LEERT den Bestand nicht — das
    wäre ein Datenverlust, den niemand angefragt hat. Dasselbe gilt fuer einen
    Namen aus reinem Leerraum: `str.strip()` faltet ihn auf leer, genau wie
    die Pruefung im Umbenennen-Router (`new_name = body.album_name.strip()`)
    — ohne diese Faltung haette ein solcher Name den sichtbaren Bestandsnamen
    geleert, gemessen am BESTAND ueber `StoreDoppel` in
    `test_sync_service.py` (Nacharbeit 1, Panel; nicht an der
    Gruppenvorschau — die hat keinen eigenen Test dafuer).

    Der Name wird ROH uebernommen, nicht bereinigt: „Immich gewinnt" gilt
    woertlich, nicht „Immich gewinnt, um Leerraum am Rand bereinigt".
    Gemessen (Nacharbeit 2): Bestandsname „Foo" gegen Immich-Namen „Foo "
    (mit angehaengtem Leerzeichen) sind als Python-Strings UNGLEICH — die
    Funktion uebernimmt „Foo " und meldet eine Namensaenderung zwischen zwei
    fuer einen Menschen sichtbar gleichen Namen. Das ist beabsichtigt, kein
    Fehler dieser Funktion; nur ein Name aus AUSSCHLIESSLICH Leerraum wird
    oben abgefangen.

    Bleibt der Name gleich, gibt es keinen Protokolleintrag: Nur eine
    tatsächliche Änderung ist eine Meldung wert. Mutiert `managed` in-place,
    wie die Nachbarfunktionen dieses Moduls es mit `total_assets`/
    `last_synced_at` auch tun — das Schreiben in den Bestand übernimmt
    weiterhin der Aufrufer.
    """
    if not immich_name or not immich_name.strip() or immich_name == managed.album_name:
        return None
    previous_name = managed.album_name
    managed.album_name = immich_name
    return SyncLogEntry(
        id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
        details=f"Album '{previous_name}' heißt in Immich jetzt '{immich_name}' — Name übernommen",
        status="success",
        message_key="log_album_name_adopted",
        message_params={"old_name": previous_name, "new_name": immich_name},
    )


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
        immich_album_name, existing_asset_ids = await owner_client.get_album_assets_with_name(
            managed.album_id
        )
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

    existing_ids = set(existing_asset_ids)
    name_entry = _uebernimm_immich_namen(managed, immich_album_name)
    if name_entry:
        logs.append(name_entry)

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

    # Der Namens-Eintrag ist eine ZUSAETZLICHE Meldung, kein Ersatz fuer „keine
    # neuen Assets" (Nacharbeit 1 zu #97, technisch entschieden: beide
    # Meldungen zeigen). Ohne diesen Ausschluss haette ein Refresh, der NUR
    # den Namen uebernimmt, die „keine neuen Assets"-Meldung verschluckt, weil
    # `logs` dann nicht mehr leer war.
    if not [entry for entry in logs if entry is not name_entry]:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
            details=f"Album '{managed.album_name}': Keine neuen Assets gefunden",
            status="success",
            message_key="log_no_new_assets",
            message_params={"album": managed.album_name},
        ))
    return logs


def _frisch(managed: ManagedAlbum, store: ConfigStore) -> Optional[ManagedAlbum]:
    """Denselben Datensatz noch einmal lesen — INNERHALB des Schlosses.

    Das Schloss allein reicht nicht, und genau das hat die erste Nacharbeit an
    #79 uebersehen: Es serialisiert die RUEMPFE, aber beide Seiten haben ihre
    Kopie schon vorher in der Hand. Der Auto-Sync liest alle Alben EINMAL und
    arbeitet sie danach der Reihe nach ab (`main._run_auto_sync`); die Router
    lesen ihren Datensatz vor dem Aufruf. Und `update_managed_album` ersetzt
    den Datensatz GANZ — wer mit einer alten Kopie schreibt, nimmt damit jede
    Aenderung zurueck, die dazwischen lag.

    Gemessen am echten Weg: Umbenennen auf „Neu“ geht durch, danach kommt der
    Auto-Sync mit seinem alten Abbild an, und der Bestand steht wieder auf
    „Alt“ — waehrend Immich „Neu“ traegt und BEIDE Protokolleintraege Erfolg
    melden. Es gibt keinen Fehler an keiner Stelle, den ein Nutzer sehen
    koennte.

    Faellt das Album zwischen dem Lesen des Aufrufers und dem Schloss weg,
    liefert diese Funktion `None` (#101, Nacharbeit 1 — die vorherige Fassung
    fiel hier auf die uebergebene, veraltete Kopie zurueck und BEHAUPTETE einen
    „gibt es nicht mehr"-Weg, den es nicht gab: Alle drei Aufrufer arbeiteten
    anschliessend klaglos mit der alten Kopie weiter, veraenderten Immich und
    schrieben einen Erfolgseintrag, waehrend `store.update_managed_album`
    mangels passender Zeile still nichts speicherte — Fund des Blindpruefers,
    nachgebaut in `backend/tests/test_album_geloescht_vor_dem_schloss.py`).
    Jeder Aufrufer prueft jetzt selbst auf `None` und bricht VOR jedem
    Immich-Aufruf ab.

    Das Restfenster DANACH — das Album verschwindet, WAEHREND ein Aufrufer
    schon im Schloss auf Immich wartet — schliesst `_frisch` allein nicht:
    Es liest nur einmal, zu Beginn. Dafuer nimmt seit Nacharbeit 2 auch
    `DELETE /api/sync/albums/{id}` dasselbe `_album_schloss` wie die drei
    Aufrufer (`routers/albums.py::delete_managed_album`) — das Loeschen
    wartet dann, bis die laufende Operation fertig ist.
    """
    return store.get_managed_album(managed.id)


def _album_schloss(album_id: str) -> asyncio.Lock:
    """Das Schloss fuer dieses Album — EINE Stelle, weil zwei Formen keins sind.

    Gefunden vom Fremdpruefer an #79: Der zugelieferte Zweig nahm
    `_album_locks.setdefault(managed.id, ...)`, der Refresh daneben
    `(id(loop), managed.id)`. Zwei verschieden geformte Schluessel in
    DERSELBEN Ablage schliessen sich nicht aus — Umbenennen und Refresh liefen
    ungebremst nebeneinander, obwohl der Docstring des Umbenennens das
    Gegenteil behauptete. Der Zweig war beim Rebase textlich sauber: Die
    Loop-Kennung kam aus UNSERER spaeteren Arbeit, nicht aus seiner. Deshalb
    steht die Form jetzt an einer Stelle und nicht an zweien.

    Die Loop-Kennung gehoert dazu, weil jeder Test seinen eigenen
    Ereignis-Ring fuehrt: Ein Schloss aus einem beendeten Ring gehoert
    niemandem mehr.
    """
    return _album_locks.setdefault(
        (id(asyncio.get_running_loop()), album_id), asyncio.Lock()
    )


async def refresh_managed_album(
    managed: ManagedAlbum,
    all_accounts: list[Account],
    store: ConfigStore,
) -> list[SyncLogEntry]:
    """Serialize refreshes per album across manual and automatic sync.

    Bricht mit `errors.managed_album_not_found()` ab, wenn das Album zwischen
    dem Lesen des Aufrufers und dem Schloss verschwunden ist (`_frisch`
    liefert dann `None`) — VOR jedem Immich-Aufruf, siehe `_frisch` (#101,
    Nacharbeit 1). Der Auto-Sync faengt das je Album ab
    (`main._run_auto_sync`, `except Exception`); ein Router-Aufruf sieht ein
    404 wie beim schon vorher unbekannten Album.
    """
    async with _album_schloss(managed.id):
        frisches = _frisch(managed, store)
        if frisches is None:
            raise errors.managed_album_not_found()
        return await _refresh_managed_album_unlocked(
            frisches, all_accounts, store
        )


async def _rename_managed_album_unlocked(
    managed: ManagedAlbum,
    owner_account: Account,
    new_name: str,
    store: ConfigStore,
) -> list[SyncLogEntry]:
    """Rename an Immich album and update its managed snapshot after success."""
    previous_name = managed.album_name
    client = ImmichClient(owner_account.immich_url, owner_account.api_key)
    try:
        await client.update_album(managed.album_id, {"albumName": new_name})
    except AlbumNotFoundError:
        return [SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="rename_album",
            details=f"Album '{previous_name}' existiert nicht in Immich.",
            status="error", error_message="ALBUM_DELETED",
            message_key="log_album_not_found",
            message_params={"album": previous_name},
        )]
    except Exception:
        return [SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="rename_album",
            details=f"Album '{previous_name}' konnte nicht umbenannt werden",
            status="error", error_message="IMMICH_API_ERROR",
            message_key="log_album_rename_failed",
            message_params={"album": previous_name},
        )]

    # GRENZE, benannt statt behauptet (Fund des Fremdpruefers an #79): Wenn
    # dieses Speichern scheitert, traegt Immich schon den neuen Namen und wir
    # noch den alten. Ein Fehler-Protokolleintrag hilft dann NICHT — das
    # Protokoll liegt in derselben Datei (`append_log` ruft `_save`), das
    # Schreiben ist also gerade erst gescheitert. Der Aufrufer bekommt 500.
    #
    # Seit #97 (Nacharbeit 2, PRAEZISIERT — die Fassung aus Nacharbeit 1
    # nannte den falschen Mechanismus): `ConfigStore.update_managed_album`
    # aendert `self._data` VOR dem Aufruf von `_save()` (siehe dort) — der
    # Speicher haelt "Neu" also schon, bevor je geschrieben wurde. Im
    # LAUFENDEN Prozess heilt deshalb NICHT `_uebernimm_immich_namen`,
    # sondern das naechste erfolgreiche Speichern eines beliebigen Refreshs:
    # `_frisch` liest "Neu" aus dem Speicher, Immich meldet ebenfalls "Neu",
    # beide sind gleich, und der Refresh schreibt die Platte einfach nach —
    # ohne je durch die Namensuebernahme zu laufen (die Meldung ist dann nur
    # `log_no_new_assets`). Der Weg ueber `_uebernimm_immich_namen`/
    # `log_album_name_adopted` greift erst nach einem NEUSTART des Prozesses,
    # wenn der Speicher wieder von der Platte ("Alt") geladen wurde. Der
    # Auto-Sync ist dafuer kein Heilungspfad mit fester Frist: Er laeuft zu
    # EINEM taeglichen, konfigurierbaren Zeitpunkt (`main._auto_sync_loop`)
    # und ist abschaltbar — beides bleibt hier ungemessen: wie lange dieses
    # Fenster in der Praxis dauert, und was ein Scheitern GENAU darin
    # bewirkt.
    managed.album_name = new_name
    store.update_managed_album(managed)
    return [SyncLogEntry(
        id=str(uuid.uuid4()), timestamp=_now(), action="rename_album",
        details=f"Album '{previous_name}' in '{new_name}' umbenannt",
        status="success",
        message_key="log_album_renamed",
        message_params={"old_name": previous_name, "new_name": new_name},
    )]


async def rename_managed_album(
    managed: ManagedAlbum,
    owner_account: Account,
    new_name: str,
    store: ConfigStore,
) -> list[SyncLogEntry]:
    """Serialize renames with refreshes so stale snapshots cannot restore the old name.

    Dieselbe Schlossform wie der Refresh — siehe `_album_schloss` — und
    derselbe Neu-Einlesevorgang: siehe `_frisch`. Die Zusicherung dieses
    Docstrings war bis zur ZWEITEN Nacharbeit an #79 falsch, und beim ersten
    Anlauf nur zur Haelfte richtig.

    Bricht mit `errors.managed_album_not_found()` ab, wenn `_frisch` `None`
    liefert (Album zwischen Lesen und Schloss geloescht) — VOR dem
    `update_album`-Aufruf gegen Immich (#101, Nacharbeit 1).
    """
    async with _album_schloss(managed.id):
        frisches = _frisch(managed, store)
        if frisches is None:
            raise errors.managed_album_not_found()
        return await _rename_managed_album_unlocked(
            frisches, owner_account, new_name, store
        )


async def _extend_match_unlocked(
    managed: ManagedAlbum,
    new_account: Account,
    person_id: str,
    person_name: Optional[str],
    canonical_name: Optional[str],
    all_accounts: list[Account],
    store: ConfigStore,
) -> list[SyncLogEntry]:
    """Add a new account/person to an existing managed album.

    Die Pruefung „Person schon im Album" laeuft auf `managed` — dem
    Datensatz, den der Aufrufer (`extend_match`) unter dem Schloss frisch
    gelesen hat (`_frisch`). Auf einer aelteren Kopie liefe sie ins Leere:
    Gemessen (Nacharbeit 1 zu #101, Blindpruefer,
    `test_zwei_gleichzeitige_erweiterungen_derselben_person_haengen_sie_nur_einmal_an`):
    Der Bestand selbst zeigt dabei KEINE doppelte Zeile in `person_refs` —
    `ConfigStore.update_managed_album` ersetzt den Datensatz ganz, die letzte
    Schreibung gewinnt vollstaendig. Der Schaden liegt woanders: Zwei
    gleichzeitige Aufrufe, die beide die alte Liste ohne die jeweils andere
    Person sehen, rufen `add_assets_to_album` bei Immich je EINMAL auf (zwei
    echte API-Schreibvorgaenge) und erzeugen je einen erfolgreichen
    `log_assets_linked`-Eintrag — keiner meldet
    `log_person_already_in_album`. Die frische Pruefung verhindert genau das.
    """
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


async def extend_match(
    managed: ManagedAlbum,
    new_account: Account,
    person_id: str,
    person_name: Optional[str],
    canonical_name: Optional[str],
    all_accounts: list[Account],
    store: ConfigStore,
) -> list[SyncLogEntry]:
    """Serialize extensions with refreshes and renames under dasselbe Schloss.

    Dieselbe Schlossform wie Refresh und Umbenennen — siehe `_album_schloss`
    — und derselbe Neu-Einlesevorgang: siehe `_frisch`. Bricht mit
    `errors.managed_album_not_found()` ab, wenn `_frisch` `None` liefert
    (Album zwischen Lesen und Schloss geloescht) — VOR jedem Immich-Aufruf
    (#101, Nacharbeit 1).

    Gemessen (Mutationslauf #101 Nacharbeit 1, ganze Suite, je einzeln
    zurueckgesetzt): Der sequenzielle Fall — Umbenennen auf einen neuen
    Namen, danach eine Erweiterung mit dem Abbild von VORHER — braucht
    dafuer allein `_frisch`; ohne Schloss allein bleibt er gruen (nichts
    laeuft hier gleichzeitig). Zwei GLEICHZEITIGE Erweiterungen brauchen
    dagegen BEIDES, ob mit derselben oder mit verschiedenen Personen: Schloss
    allein entfernt ODER `_frisch` allein entfernt macht beide Faelle je fuer
    sich schon rot (bei verschiedenen Personen wirft die zweite Schreibung
    die erste weg, weil `update_managed_album` den Datensatz GANZ ersetzt;
    bei derselben Person sehen beide Aufrufe die "schon enthalten"-Pruefung
    mit `false` und sprechen Immich zweimal an — Einzelheiten und die
    gemessenen Immich-/Protokoll-Werte stehen an `_extend_match_unlocked`
    und im Test selbst). Dasselbe gilt fuer das eigene Schloss dieser
    Funktion: Ein Schloss, das NICHT `_album_schloss` waere (eigene Ablage
    oder ein anderer Schluessel als `managed.id`), schliesst sich mit
    Refresh und Umbenennen nicht aus — beide Proben dazu stehen in
    `test_erweitern_schloss.py`.
    """
    async with _album_schloss(managed.id):
        frisches = _frisch(managed, store)
        if frisches is None:
            raise errors.managed_album_not_found()
        return await _extend_match_unlocked(
            frisches, new_account, person_id, person_name,
            canonical_name, all_accounts, store,
        )


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
