"""Cross-account synchronisation actions."""
import logging
import uuid
import asyncio
from collections import Counter
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


def _person_ids_by_account(person_refs: list[dict]) -> dict[str, list[str]]:
    """Group distinct selected people by account while preserving input order."""
    grouped: dict[str, list[str]] = {}
    for ref in person_refs:
        person_ids = grouped.setdefault(ref["account_id"], [])
        if ref["person_id"] not in person_ids:
            person_ids.append(ref["person_id"])
    return grouped


async def _get_qualifying_asset_ids(
    client: ImmichClient,
    person_ids: list[str],
    minimum_person_count: int,
) -> list[str]:
    """Return assets that occur for at least N distinct selected people."""
    if len(set(person_ids)) < minimum_person_count:
        return []
    structured_resolver = getattr(client, "get_assets_matching_people", None)
    if callable(structured_resolver):
        assets = await structured_resolver(person_ids, minimum_person_count)
        return list(dict.fromkeys(asset["id"] for asset in assets))

    # Compatibility path for lightweight clients used by integrations and
    # tests that only implement the long-standing per-person method.
    counts: Counter[str] = Counter()
    ordered_ids: list[str] = []
    for person_id in person_ids:
        assets = await client.get_person_assets(person_id)
        seen_for_person: set[str] = set()
        for asset in assets:
            asset_id = asset["id"]
            if asset_id in seen_for_person:
                continue
            seen_for_person.add(asset_id)
            if asset_id not in counts:
                ordered_ids.append(asset_id)
            counts[asset_id] += 1
    return [asset_id for asset_id in ordered_ids if counts[asset_id] >= minimum_person_count]


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


# `manuelle_kennung_kollidiert` (Kollision im RENNEN, als Protokolleintrag
# statt Ablehnung) ist mit Nacharbeit 2 zu #113/#119/#124 ENTFERNT: Blind-
# und Gegenpruefer haben gemessen, dass ihre Begruendung „Ablehnen geht nicht
# mehr, es ist bereits umbenannt" seit Nacharbeit 1 nicht mehr stimmt — die
# Aufloesung unter dem Schloss (`routers.albums.
# _gruppe_fuer_manuellen_weg_unter_dem_schloss`) laeuft dort schon VOR
# `sync_names_multi`, nur nutzte der Aufrufer das Ergebnis bis hierher nicht,
# um den Schreibvorgang zu verhindern. Die Kollision WIRFT jetzt
# `errors.manual_match_id_collision` (409) an genau der Stelle, an der diese
# Funktion vorher einen Log-Eintrag baute — vor jedem Schreibvorgang, nicht
# danach. Der Protokollschluessel `log_manual_match_collision` hat damit
# keinen Sender mehr und ist aus `logMessages.contract.json` und
# `frontend/src/i18n.tsx` mitentfernt (Vertrag #94).


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
    owner_id: Optional[str] = None,
    store: Optional[ConfigStore] = None,
) -> list[SyncLogEntry]:
    """
    Share album with accounts that aren't already members.
    Returns log entries only for accounts that were actually added or failed.
    Silently skips accounts that are already editors.

    `owner_id`/`store` sind OPTIONAL und POSITIONAL, nicht Schluesselwoerter
    (Nacharbeit 2, #117/#121/#103 WICHTIG 3): `create_shared_album` und
    `link_existing_album` — beide „nicht anfassen", gehoeren zum Anlageweg
    eines parallelen Slices — rufen diese Funktion weiterhin mit nur vier
    Argumenten auf, unveraendert. Nur `_refresh_managed_album_unlocked` und
    `_extend_match_unlocked` geben beide mit, um NACH dem `await` unten frisch
    pruefen zu koennen, ob Besitzer und Teilnehmer noch leben — ohne
    `owner_id`/`store` bleibt diese Funktion beim alten Verhalten (keine
    Frischpruefung), auch wenn ein bestehender Test sie durch eine Attrappe
    mit fester Positionsliste ersetzt (`*_args`-Fassungen in
    `test_sync_service.py`), die keine Schluesselwoerter kennt.
    """
    logs: list[SyncLogEntry] = []
    if not accounts_to_share:
        return logs

    # A payload may contain several people from the same account. Share once.
    unique_accounts: list[Account] = []
    seen_account_ids: set[str] = set()
    seen_user_ids: set[str] = set()
    for account in accounts_to_share:
        if account.id in seen_account_ids or (account.user_id and account.user_id in seen_user_ids):
            continue
        unique_accounts.append(account)
        seen_account_ids.add(account.id)
        if account.user_id:
            seen_user_ids.add(account.user_id)

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

    # FRISCH NACH DEM AWAIT (Nacharbeit 2, Gegen N6/N6b): Der obige Aufruf ist
    # der ERSTE Immich-Aufruf dieser Funktion und kann lange genug dauern,
    # dass Besitzer oder Teilnehmer waehrenddessen geloescht werden. Ein
    # geloeschter Besitzer machte den NAECHSTEN Aufrufblock hier
    # (`share_album_with_users`, mit `owner_client`) sonst zu einem Aufruf mit
    # dem Schluessel eines zu diesem Zeitpunkt schon toten Kontos — der
    # bereits laufende Aufruf oben darf zu Ende laufen (er ist es ja schon),
    # nur der naechste Block wird ausgelassen. Ein geloeschter Teilnehmer wird
    # nicht mehr geteilt (Nacharbeit-2-Auftrag: „das Teilen mit Nutzern
    # geloeschter Konten auslassen").
    if store is not None:
        if owner_id is not None and store.get_account(owner_id) is None:
            return logs
        unique_accounts = [a for a in unique_accounts if store.get_account(a.id) is not None]
        if not unique_accounts:
            return logs

    # Only add accounts not already in the album
    to_add = [a for a in unique_accounts if a.user_id and a.user_id not in existing_ids]
    already_there = [a for a in unique_accounts if a.user_id and a.user_id in existing_ids]

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
    minimum_person_count: int = 1,
    linked_person_ids: Optional[list[str]] = None,
    condition_person_count: Optional[int] = None,
) -> tuple[ManagedAlbum | None, list[SyncLogEntry]]:
    """
    Create a shared album in the owner account, share it with all other
    accounts as editors, then add each account's assets using their own API key.
    """
    logs: list[SyncLogEntry] = []
    account_map = {a.id: a for a in all_accounts}
    grouped_person_ids = _person_ids_by_account(person_refs)

    # ── 1. Create album in owner account ──────────────────────────────
    owner_client = ImmichClient(owner_account.immich_url, owner_account.api_key)
    initial_asset_ids: list[str] = []
    owner_person_ids = grouped_person_ids.get(owner_account.id, [])
    if owner_person_ids:
        try:
            initial_asset_ids = await _get_qualifying_asset_ids(
                owner_client, owner_person_ids, minimum_person_count
            )
        except Exception as exc:
            logger.warning("Could not load owner assets: %s", exc)
            if minimum_person_count > 1:
                return None, [SyncLogEntry(
                    id=str(uuid.uuid4()), timestamp=_now(), action="create_album",
                    details=f"Assets für Album '{album_name}' konnten nicht geladen werden",
                    status="error", error_message="IMMICH_API_ERROR",
                    message_key="log_album_create_failed",
                    message_params={"album": album_name},
                )]

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
    for account_id, person_ids in grouped_person_ids.items():
        if account_id == owner_account.id:
            continue  # already added in step 1
        account = account_map.get(account_id)
        if not account:
            continue
        client = ImmichClient(account.immich_url, account.api_key)
        try:
            asset_ids = await _get_qualifying_asset_ids(
                client, person_ids, minimum_person_count
            )
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
        minimum_person_count=minimum_person_count,
        linked_person_ids=linked_person_ids or [],
        condition_person_count=(
            condition_person_count
            if condition_person_count is not None
            else len({(ref["account_id"], ref["person_id"]) for ref in person_refs})
        ),
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
    minimum_person_count: int = 1,
    linked_person_ids: Optional[list[str]] = None,
    condition_person_count: Optional[int] = None,
) -> tuple[ManagedAlbum | None, list[SyncLogEntry]]:
    """Link an existing Immich album to a match, share it, and fill with assets."""
    logs: list[SyncLogEntry] = []
    account_map = {a.id: a for a in all_accounts}
    owner_client = ImmichClient(owner_account.immich_url, owner_account.api_key)
    grouped_person_ids = _person_ids_by_account(person_refs)

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
    for account_id, person_ids in grouped_person_ids.items():
        account = account_map.get(account_id)
        if not account:
            continue
        client = ImmichClient(account.immich_url, account.api_key)
        try:
            qualifying_ids = await _get_qualifying_asset_ids(
                client, person_ids, minimum_person_count
            )
            new_ids = [asset_id for asset_id in qualifying_ids if asset_id not in existing_ids]
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
        person_refs=person_refs, minimum_person_count=minimum_person_count,
        linked_person_ids=linked_person_ids or [],
        condition_person_count=(
            condition_person_count
            if condition_person_count is not None
            else len({(ref["account_id"], ref["person_id"]) for ref in person_refs})
        ),
        created_at=_now(), last_synced_at=_now(),
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
    new_total = 0

    # Get current asset IDs in album (using owner's key)
    #
    # FRISCH AUS DEM STORE, NICHT AUS EINEM SCHNAPPSCHUSS (#117 Nachtrag):
    # `all_accounts` ist ein Schnappschuss, den der Aufrufer VOR dem
    # Albumschloss gebaut hat (`routers/albums.py`, `main._run_auto_sync`).
    # Wird der Besitzer GENAU WAEHREND dieser Funktion auf ihr Schloss
    # wartet geloescht, traegt ein aus `all_accounts` gebauter `dict` ihn
    # trotzdem noch — mit seinem jetzt ungueltigen API-Schluessel. Gemessen
    # (erzwungenes Fenster): Immich bekam einen Aufruf mit dem Schluessel
    # eines Kontos, das zu diesem Zeitpunkt schon geloescht war.
    # `store.get_account` liest dagegen den AKTUELLEN Bestand. Seit
    # Nacharbeit 1 gilt dasselbe auch fuer jeden TEILNEHMER weiter unten,
    # nicht mehr nur fuer den Besitzer — ein eigener `account_map`-Schnapp-
    # schuss wuerde diese Zusage wieder unterlaufen, darum gibt es hier
    # keinen mehr.
    owner = store.get_account(managed.owner_account_id)
    if not owner:
        return [SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
            details="Owner-Account nicht mehr vorhanden",
            status="error",
            message_key="log_owner_account_missing", message_params={},
        )]

    owner_client = ImmichClient(owner.immich_url, owner.api_key)
    participant_ids = {ref["account_id"] for ref in managed.person_refs}
    # KEINE EIGENE FRISCHPRUEFUNG MEHR HIER (Nacharbeit 2, M10 —
    # RICHTIGGESTELLT gegenueber Nacharbeit 1): Diese Zeile trug bis hierher
    # ihr eigenes `store.get_account(account.id) is not None`, mit derselben
    # Begruendung wie unten am `account_map` — ein Teilnehmer, der zwischen
    # dem Bau des `all_accounts`-Schnappschusses und hier geloescht wurde,
    # sollte nicht mehr geteilt werden. Seit Nacharbeit 2 filtert
    # `_share_album_if_needed` SELBST noch einmal frisch, NACH ihrem eigenen
    # `get_album_user_ids`-Aufruf (siehe dort, WICHTIG 3) — strikt SPAETER als
    # diese Stelle hier, deckt also jeden Fall, den die Pruefung hier deckte,
    # UND das Fenster WAEHREND des Aufrufs selbst. Die Pruefung hier war damit
    # UNBEWEISBAR geworden: Eine Mutation, die sie entfernt, ueberlebt die
    # volle Suite unbemerkt, weil die zweite Pruefung jeden Fall ohnehin
    # abfaengt (`docs/agents/lehren.md` §1, „gruen ohne bewiesen" — gemessen,
    # Mutation M10). `share_accounts` geht deshalb ungeprueft in
    # `_share_album_if_needed`; `owner_id`/`store` unten geben ihr die
    # Moeglichkeit dazu.
    share_accounts = [
        account for account in all_accounts
        if account.id != owner.id and account.id in participant_ids
    ]
    logs.extend(
        await _share_album_if_needed(
            owner_client, managed.album_id, managed.album_name, share_accounts,
            owner.id, store,
        )
    )

    # FRISCH VOR DEM NAECHSTEN IMMICH-AUFRUFBLOCK (Nacharbeit 2, WICHTIG 3,
    # Gegen N6): Das Teilen oben war der erste Aufrufblock mit dem
    # Besitzerschluessel und kann lange genug gedauert haben, dass der
    # Besitzer waehrenddessen geloescht wurde — `owner_client` truege dann
    # noch dessen (jetzt ungueltigen) Schluessel in den naechsten Block
    # hinein. Bereits laufende Aufrufe (das Teilen selbst) laufen zu Ende;
    # nur DIESER naechste Block wird bei totem Besitzer ausgelassen. Die
    # bisher gesammelten Protokolleintraege (etwa ein erfolgreiches Teilen)
    # gehen dabei NICHT verloren — „nichts verschwindet still".
    owner = store.get_account(owner.id)
    if not owner:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="refresh_album",
            details="Owner-Account nicht mehr vorhanden",
            status="error",
            message_key="log_owner_account_missing", message_params={},
        ))
        return logs
    owner_client = ImmichClient(owner.immich_url, owner.api_key)

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

    grouped_person_ids = _person_ids_by_account(managed.person_refs)
    for account_id, person_ids in grouped_person_ids.items():
        # FRISCH AUS DEM STORE, NICHT AUS `account_map` (Nacharbeit 1 zu
        # #117/#121/#103 — gemessen, Blocker-Klasse „Teilnehmerschluessel"):
        # `account_map` ist derselbe Schnappschuss aus `all_accounts`, den der
        # Aufrufer VOR dem Albumschloss gebaut hat (`routers/albums.py`,
        # `main._run_auto_sync`) — dieselbe Schwaeche, die der Docstring bei
        # `_refresh_managed_album_unlocked`s Besitzer-Lesung oben schon fuer
        # den BESITZER beschreibt, traf bisher jeden TEILNEHMER ungeprueft:
        # Wird ein Teilnehmer WAEHREND dieser Schleife (an einem `await` einer
        # frueheren Runde) geloescht, trug `account_map` ihn trotzdem noch
        # weiter, mit seinem jetzt ungueltigen API-Schluessel — gemessen
        # (erzwungenes Fenster, Sonde S2): Immich bekam einen Aufruf mit dem
        # Schluessel eines zu diesem Zeitpunkt schon geloeschten Kontos.
        # `store.get_account` liest den AKTUELLEN Bestand, direkt VOR dem
        # Aufrufblock fuer genau dieses Konto — ein bereits laufender Aufruf
        # (fuer ein FRUEHERES Konto derselben Schleife) wird dadurch nicht
        # abgebrochen, nur der NAECHSTE Block startet mit einer frischen
        # Pruefung.
        account = store.get_account(account_id)
        if not account:
            continue
        client = ImmichClient(account.immich_url, account.api_key)
        try:
            qualifying_ids = await _get_qualifying_asset_ids(
                client, person_ids, managed.minimum_person_count
            )
            new_ids = [asset_id for asset_id in qualifying_ids if asset_id not in existing_ids]
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


def _raeume_tote_referenzen_synchron(album_id: str, store: ConfigStore) -> None:
    """Bereinigt tote Kontoreferenzen DIESES Albums, NOCH UNTER DEM SCHLOSS.

    Nacharbeit 2 (#117/#121/#103), BLOCKER: Bis hierher bereinigte ein
    Halter tote Referenzen nur, wenn ER SELBST erfolgreich bis zum Ende lief
    und `store.update_managed_album` erreichte (das filtert sie ueber
    `ConfigStore._ohne_tote_konten`). Ein Halter, der STATTDESSEN scheitert
    (Immich antwortet mit einem Fehler, das Album ist weg, der Besitzer fehlt,
    ein `return` vor dem Speichern, ein Abbruch/`CancelledError`), schreibt
    nie — und liess die tote Referenz seither STEHEN, dauerhaft, auch nach
    einem Neustart (Blind- und Gegenpruefer, unabhaengig gemessen an
    `f796140`/`11c0524`: ein Refresh, dessen Immich-Aufruf mit einem Fehler
    endet, nachdem der Besitzer waehrenddessen geloescht wurde, behielt die
    tote Referenz bis zum naechsten ERFOLGREICHEN Schreibvorgang dieses
    Albums — der bei einem dauerhaft verwaisten Album nie kommt).

    Deshalb ruft jeder der drei Schloss-Wrapper (`refresh_managed_album`,
    `rename_managed_album`, `extend_match`) diese Funktion jetzt aus einem
    `finally` auf, das den ganzen Rumpf innerhalb von `_album_schloss`
    umschliesst — bei JEDEM Ausgang: Erfolg, jede Ausnahme (auch
    `errors.managed_album_not_found()`, wenn `_frisch` `None` liefert),
    fruehes `return`, Abbruch/`CancelledError`. `finally` laeuft in allen
    diesen Faellen, auch bei einer Cancellation (Python fuehrt einen
    `finally`-Block aus, bevor `CancelledError` weiter nach oben propagiert).

    SYNCHRON, KEIN `await` — und das ist die tragende Eigenschaft, nicht nur
    ein Stilmittel: `store.get_managed_album`/`store.update_managed_album`
    sind beide synchron (reines Python, kein Netzwerk). Zwischen diesem
    Aufraeumen und der Freigabe des Schlosses (`async with`s eigenes Ende)
    liegt deshalb KEIN `await` — kein Zeitfenster, in dem ein weiterer
    Schreiber dazwischenkommen und mit einer eigenen, jetzt veralteten Kopie
    ueberschreiben koennte, was hier gerade bereinigt wurde.

    Liest den Datensatz selbst noch einmal frisch (er kann sich seit dem
    letzten `_frisch`-Aufruf des Wrappers durch den eigenen erfolgreichen
    Schreibvorgang bereits geaendert haben) und speichert NUR bei
    tatsaechlicher Aenderung — ein Album, das gerade erst durch
    `delete_managed_album` verschwunden ist (`store.get_managed_album`
    liefert dann `None`), wird uebersprungen, kein Fehler.
    """
    frisches = store.get_managed_album(album_id)
    if frisches is None:
        return
    vorher = len(frisches.person_refs)
    # `store.get_account` statt des privaten `ConfigStore._ohne_tote_konten`:
    # `sync_service` kennt seinen Store nur ueber diese oeffentliche
    # Schnittstelle (siehe die Doppel in `test_sync_service.py`, die
    # `ConfigStore` nicht erben und das private Helferlein deshalb nicht
    # tragen) — `update_managed_album` filtert bei der ECHTEN `ConfigStore`
    # ohnehin ueber `_ohne_tote_konten` noch einmal nach, diese Zeile ist die
    # Voraussetzung fuer den VORHER/NACHHER-Vergleich, der entscheidet, ob
    # hier ueberhaupt gespeichert wird.
    gefiltert = [r for r in frisches.person_refs if store.get_account(r.get("account_id")) is not None]
    if len(gefiltert) == vorher:
        return
    frisches.person_refs = gefiltert
    store.update_managed_album(frisches)


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
    (`main._run_auto_sync`, eigene `except errors.AppError`-Zeile, die an der
    FEHLERART haengt — `exc.key == "err_managed_album_not_found"`, nicht am
    Statuscode; #121/#103 Punkt 4/3); ein Router-Aufruf sieht ein 404 wie
    beim schon vorher unbekannten Album.

    RICHTIGGESTELLT (Nacharbeit 1, Fund „KLEIN"): Hier stand bis dahin, vor
    #121/#103 habe an dieser Stelle `except Exception` gestanden, „was nie
    zutraf" — das war ungenau bis falsch: `except Exception` haette
    `AppError` (eine `HTTPException`-Unterklasse) durchaus gefangen, nur
    ohne zwischen „Album planmaessig entfernt" und einem echten Fehler zu
    unterscheiden. Der eigentliche, gemessene Befund war ein anderer: Der
    `except errors.AppError`-Zweig selbst war UNERREICHT, weil
    `refresh_managed_album` im Auto-Sync-Pfad nie eine andere `AppError`-Art
    als `err_managed_album_not_found` wirft — kein Test lief je durch das
    `else`. Drei Mutationen ueberlebten deshalb unbemerkt die volle Suite
    (`exc.status_code == 404` statt `exc.key`, die Fehlerzeile mit
    `album.album_name` statt `album.id`, ein Zweig, der IMMER uebersprungen
    wird) — siehe `test_main.py::
    test_auto_sync_unterscheidet_fehlerart_nicht_statuscode`.

    RAEUMT SEIT NACHARBEIT 2 BEI JEDEM AUSGANG AUF (BLOCKER, #117/#121/#103):
    `finally` ruft `_raeume_tote_referenzen_synchron` — siehe dort fuer die
    Begruendung, insbesondere warum dort KEIN `await` liegt.
    """
    async with _album_schloss(managed.id):
        try:
            frisches = _frisch(managed, store)
            if frisches is None:
                raise errors.managed_album_not_found()
            return await _refresh_managed_album_unlocked(
                frisches, all_accounts, store
            )
        finally:
            _raeume_tote_referenzen_synchron(managed.id, store)


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
    # nannte den falschen Mechanismus; seit #114 NOCHMALS praezisiert, die
    # Nacharbeit-2-Fassung war noch zu eng): `ConfigStore.update_managed_album`
    # aendert `self._data` VOR dem Aufruf von `_save()` (siehe dort) — der
    # Speicher haelt "Neu" also schon, bevor je geschrieben wurde. Im
    # LAUFENDEN Prozess heilt deshalb NICHT `_uebernimm_immich_namen`,
    # sondern JEDES naechste erfolgreiche `_save()` — nicht nur das eines
    # Refreshs (gemessen: auch `set_auto_sync_config`, das die GESAMTEN
    # `self._data` speichert, schreibt "Neu" auf die Platte, ganz ohne dass
    # ein Refresh dazwischen lief). Ein Refresh ist dabei nur der
    # naheliegende, nicht der einzige Fall: `_frisch` liest "Neu" aus dem
    # Speicher, Immich meldet ebenfalls "Neu", beide sind gleich, und der
    # Refresh schreibt die Platte einfach nach — ohne je durch die
    # Namensuebernahme zu laufen. Die Meldung ist in DIESEM Fall (Refresh
    # ohne neue Assets, ohne Teilen-Ereignis UND ohne Fehler) nur
    # `log_no_new_assets` —
    # ein `_save()` aus einer anderen Quelle wie `set_auto_sync_config`
    # erzeugt gar keine Protokollzeile. Der Weg ueber `_uebernimm_immich_namen`/
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

    DER BESITZER WIRD SEIT #117 NACHTRAG NICHT MEHR VOM AUFRUFER UEBERGEBEN,
    SONDERN HIER, UNTER DEM SCHLOSS, AUS DEM AKTUELLEN STORE GELESEN — vorher
    loeste `routers/albums.py::rename_managed_album` den Besitzer VOR diesem
    Schloss auf und reichte ihn als `owner_account` herein. Wartete der
    Aufruf hinter einem laufenden Refresh am Schloss und wurde WAEHREND
    dieses Wartens das Besitzerkonto geloescht, lief er danach mit dem
    veralteten Konto weiter: `PATCH` antwortete 200, Immich bekam
    `update_album` mit dem API-Schluessel eines zu diesem Zeitpunkt bereits
    geloeschten Kontos, und ein inzwischen verwaistes Album trug den neuen
    Namen — obwohl `CONTEXT.md` „Orphaned Managed Album" fuer das Umbenennen
    eines verwaisten Albums das Gegenteil verspricht. Gemessen mit
    erzwungenem Fenster (Refresh haelt das Schloss, PATCH wartet, dann
    Konto-Loeschung, dann Freigabe) — unabhaengig von #123, nicht dadurch
    eingefuehrt.

    Bricht mit `errors.owner_account_not_found()` ab, wenn der Besitzer unter
    dem Schloss fehlt — bevor `update_album` gegen Immich laeuft, aus
    demselben Grund wie der `_frisch`-Abbruch oben.

    RAEUMT SEIT NACHARBEIT 2 BEI JEDEM AUSGANG AUF (BLOCKER, #117/#121/#103):
    siehe `_raeume_tote_referenzen_synchron` — auch wenn `update_album` mit
    404 scheitert (Album in Immich weg) oder ein anderer Fehler den Rumpf
    verlaesst, ohne dass `store.update_managed_album` je erreicht wurde.
    """
    async with _album_schloss(managed.id):
        try:
            frisches = _frisch(managed, store)
            if frisches is None:
                raise errors.managed_album_not_found()
            owner_account = store.get_account(frisches.owner_account_id)
            if not owner_account:
                raise errors.owner_account_not_found()
            return await _rename_managed_album_unlocked(
                frisches, owner_account, new_name, store
            )
        finally:
            _raeume_tote_referenzen_synchron(managed.id, store)


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

    # FRISCH AUS DEM STORE, VOR DEM ERSTEN IMMICH-AUFRUFBLOCK FUER
    # `new_account` (Nacharbeit 1, BLOCKER; Nacharbeit 2, WICHTIG 3: DIES IST
    # NUR NOCH DIE ERSTE VON MEHREREN SOLCHEN PRUEFUNGEN — jeder weitere
    # Aufrufblock mit `new_account`s oder dem Besitzer-Schluessel bekommt
    # seine EIGENE frische Pruefung, direkt davor; siehe unten). Der Aufrufer
    # (`routers/albums.py::extend_match`) liest `new_account` VOR dem
    # Albumschloss — genau wie er es vor #117 Nachtrag auch fuer den
    # Besitzer tat. Wartet diese Erweiterung hinter einem laufenden
    # Schreiber am Schloss und wird WAEHREND dieses Wartens GENAU DIESES
    # Konto geloescht, haette die alte Fassung es trotzdem an `person_refs`
    # angehaengt und mit seinem (jetzt ungueltigen) Schluessel bei Immich
    # angerufen (gemessen, Sonde S1: `get_person`, `get_person_assets`,
    # `add_assets_to_album` NACH dem 204). Diese Pruefung laeuft VOR dem
    # ersten Immich-Aufruf fuer `new_account` (der Personen-Validierung
    # unten) — ein zu DIESEM Zeitpunkt schon laufender Aufruf wird dagegen
    # nicht abgebrochen (siehe die zweite Haelfte des Blockers unten,
    # `_ohne_tote_konten`, das genau diesen Fall als Ruecksicherung
    # schliesst: Ein Aufruf, der HIER die Pruefung noch bestanden hat, aber
    # zwischen Validierung und dem abschliessenden `store.update_managed_album`
    # gelöscht wird, landet trotzdem nicht dauerhaft im Bestand).
    #
    # KEIN NEUER `message_key`: `frontend/` steht in diesem Slice unter
    # „nicht anfassen" (paralleler Slice) — ein frischer Schluessel bliebe
    # ohne Uebersetzung und ohne Eintrag in `logMessages.contract.json`.
    # `log_person_validation_failed` traegt schon die richtige Form (Konto
    # konnte nicht fuer diese Erweiterung herangezogen werden) und denselben
    # `{account}`-Parameter; der Name kommt aus der VOR dem Schloss gelesenen
    # Kopie, die trotz geloeschtem Konto noch existiert.
    neuer_konto_name = new_account.name
    new_account = store.get_account(new_account.id)
    if not new_account:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="extend_match",
            details=f"Konto '{neuer_konto_name}' ist nicht mehr vorhanden.",
            status="error", error_message="ACCOUNT_GONE",
            message_key="log_person_validation_failed",
            message_params={"account": neuer_konto_name},
        ))
        return logs

    # FRISCH AUS DEM STORE (#117 Nachtrag): der Aufrufer baut `all_accounts`
    # VOR dem Albumschloss.
    owner = store.get_account(managed.owner_account_id)
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

    # 1. Share album with new account — `owner_id`/`store` geben
    # `_share_album_if_needed` die Moeglichkeit, NACH ihrem eigenen
    # `get_album_user_ids`-Aufruf frisch zu pruefen, ob Besitzer UND
    # `new_account` noch leben (Nacharbeit 2, WICHTIG 3, siehe dort).
    share_logs = await _share_album_if_needed(
        owner_client, managed.album_id, managed.album_name, [new_account],
        owner.id, store,
    )
    logs.extend(share_logs)

    # FRISCH VOR BLOCK 2 (Nacharbeit 2, WICHTIG 3 — Besitzer vor jedem
    # weiteren Aufrufblock): Das Teilen oben ist der erste Aufrufblock mit
    # dem Besitzerschluessel und kann lange genug gedauert haben, dass der
    # Besitzer waehrenddessen geloescht wurde.
    owner = store.get_account(owner.id)
    if not owner:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="extend_match",
            details="Owner-Account nicht mehr vorhanden.",
            status="error",
            message_key="log_owner_account_missing", message_params={},
        ))
        return logs
    owner_client = ImmichClient(owner.immich_url, owner.api_key)

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

    # FRISCH VOR BLOCK 3 (Nacharbeit 2, WICHTIG 3/4 — das neue Konto vor
    # jedem weiteren Aufrufblock): Wird `new_account` erst HIER geloescht
    # (also nach der Personen-Validierung und dem Teilen oben), meldete die
    # alte Fassung trotzdem Erfolg und rief `new_client` mit dem jetzt
    # ungueltigen Schluessel auf (Blind W5, Gegen N5). Derselbe
    # `log_person_validation_failed`-Schluessel wie beim fruehen
    # Nichtmehr-Vorhanden-Fall oben — kein neuer Schluessel ohne Frontend.
    fresh_new_account = store.get_account(new_account.id)
    if not fresh_new_account:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="extend_match",
            details=f"Konto '{new_account.name}' ist waehrend der Erweiterung entfernt worden.",
            status="error", error_message="ACCOUNT_GONE",
            message_key="log_person_validation_failed",
            message_params={"account": new_account.name},
        ))
        return logs
    new_account = fresh_new_account
    new_client = ImmichClient(new_account.immich_url, new_account.api_key)

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

    # 4. Optionally rename person — FRISCH DAVOR (Nacharbeit 2, WICHTIG 3/4):
    # Block 3 kann lange genug gedauert haben, dass `new_account`
    # waehrenddessen geloescht wird. Ohne diese Pruefung riefe der Rename-Block
    # `new_client` (jetzt ungueltiger Schluessel) auf und erzeugte
    # `log_name_synced` mit `undo_data` auf ein bereits geloeschtes Konto —
    # genau das W5/N5 nicht zulassen sollen. Anders als bei den Bloecken
    # oben BRICHT dieser Fund die Funktion nicht ab: Block 3 hat mit einem
    # zu DIESEM Zeitpunkt noch lebenden Konto bereits erfolgreich
    # geschrieben, das Ergebnis bleibt gueltig — nur die optionale
    # Umbenennung entfaellt, ehrlich protokolliert statt still verworfen.
    if canonical_name and store.get_account(new_account.id) is None:
        logs.append(SyncLogEntry(
            id=str(uuid.uuid4()), timestamp=_now(), action="sync_names",
            details=f"Konto '{new_account.name}' ist waehrend der Erweiterung entfernt worden — Umbenennung entfaellt.",
            status="error", error_message="ACCOUNT_GONE",
            message_key="log_person_validation_failed",
            message_params={"account": new_account.name},
        ))
    elif canonical_name:
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

    RAEUMT SEIT NACHARBEIT 2 BEI JEDEM AUSGANG AUF (BLOCKER, #117/#121/#103):
    siehe `_raeume_tote_referenzen_synchron`.
    """
    async with _album_schloss(managed.id):
        try:
            frisches = _frisch(managed, store)
            if frisches is None:
                raise errors.managed_album_not_found()
            return await _extend_match_unlocked(
                frisches, new_account, person_id, person_name,
                canonical_name, all_accounts, store,
            )
        finally:
            _raeume_tote_referenzen_synchron(managed.id, store)


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
