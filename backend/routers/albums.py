"""Sync actions: name sync, album creation, refresh, undo, log."""
from fastapi import APIRouter, Request

import errors
from pydantic import BaseModel

from models.match import SyncNamesRequest, SyncAlbumRequest, SyncLogEntry, ManagedAlbum, SyncNamesMultiRequest, ExtendMatchRequest
from services import sync_service

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.get("/album-group")
async def album_group_preview(album_name: str, request: Request):
    """Welcher Gruppe wuerde ein Album mit diesem Namen beitreten? (#81)

    `null`, wenn keine — oder wenn der Name nichts aussagt (leer, mehrdeutig).
    Die Regel liegt in ConfigStore; hier steht nur der Aufruf, damit es bei
    EINEM Eigentuemer bleibt.
    """
    store = request.app.state.store
    group_id = store.existing_group_for_name(album_name)
    if not group_id:
        return None
    details = store.group_details(group_id)
    details["person_refs"] = _mit_lebenden_kontodaten(store, details["person_refs"])
    return details


def _resolve_match(match_id: str, matches: list):
    return next((m for m in matches if m.id == match_id), None)


async def _name_des_bestehenden_albums(owner, album_id: str, angegeben: str | None) -> str:
    """Der Anzeigename eines bereits in Immich vorhandenen Albums.

    Ohne diese Aufloesung stand bis zur Nacharbeit zu #78 an beiden
    Verknuepfungsstellen `album_name = body.album_name or
    body.existing_album_id` — die Album-UUID landete im NAMENSFELD. Ueber
    `ManualMatch.tsx` ist das der Normalweg, wenn das Namensfeld leer bleibt;
    es ist ja fuer den Anlegen-Modus gedacht.

    Der Fremdpruefer hat gezeigt, dass das mehr verdirbt als die Anzeige:
    `link_existing_album` reicht diesen Wert an `group_id_for_name` weiter,
    also bestimmt die UUID die DAUERHAFTE Gruppenkennung. Ein spaeter
    korrigierter Anzeigename holt die falsche Zuordnung nicht zurueck.

    Wir holen deshalb den echten Namen aus Immich. Geht das nicht, wird
    abgelehnt statt geraten — eine UUID ist kein Name.
    """
    if angegeben and angegeben.strip():
        return angegeben
    from services.immich_client import ImmichClient

    try:
        info = await ImmichClient(owner.immich_url, owner.api_key).get_album_info(album_id)
        name = (info.get("albumName") or "").strip()
    except Exception:
        name = ""
    if not name:
        raise errors.album_name_required()
    return name



@router.post("/names", response_model=list[SyncLogEntry])
async def sync_names(body: SyncNamesRequest, request: Request):
    store = request.app.state.store
    from routers.faces import get_matches
    matches = await get_matches(request)
    match = _resolve_match(body.match_id, matches)
    if not match:
        raise errors.match_not_found()

    acc_a = store.get_account(match.person_a.account_id)
    acc_b = store.get_account(match.person_b.account_id)
    if not acc_a or not acc_b:
        raise errors.account_not_found()

    entries = await sync_service.sync_names(
        account_a=acc_a, person_id_a=match.person_a.person_id,
        account_b=acc_b, person_id_b=match.person_b.person_id,
        canonical_name=body.name,
    )
    store.append_log(entries)
    if all(e.status == "success" for e in entries):
        store.mark_names_synced(body.match_id)
    request.app.state.match_cache.invalidate()
    return entries


def _personenmenge(refs) -> set:
    """Wer in diesem Album steckt — als Menge, unabhaengig von der Reihenfolge.

    Zwei Aufrufe mit derselben manuellen Kennung sind nur dann DERSELBE
    Vorgang, wenn sie dieselben Personen meinen. Die Kennung allein sagt das
    nicht: Sie traegt nur Name und Eigentuemer.
    """
    aus = set()
    for r in refs or []:
        if isinstance(r, dict):
            aus.add((r.get("account_id"), r.get("person_id")))
        else:
            aus.add((getattr(r, "account_id", None), getattr(r, "person_id", None)))
    return aus


async def _manuelles_album_unter_dem_schloss(
    *, body, store, match_id, owner, all_accounts, person_refs,
    name_fuer_gruppe, gruppe_vorab, festgelegt, album_name_vorab,
) -> list[SyncLogEntry]:
    """Der Album-Teil des manuellen Wegs, mit gehaltenem Trefferschloss.

    Eigene Funktion der Lesbarkeit wegen; die Begruendung steht bei
    `_album_anlegen_unter_dem_schloss`, samt der beiden falschen Saetze, die
    dort eine Fassung lang standen.
    """
    bestehend = [a for a in store.get_managed_albums() if a.match_id == match_id]
    if bestehend:
        # Im Rennen sieht die Vorabpruefung oben noch nichts — das Album
        # entsteht erst danach. Ablehnen ginge hier nicht mehr, ohne hinter
        # einen Schreibvorgang zu geraten; also ein Fehlereintrag.
        if not _personenmenge(body.persons) <= _personenmenge(bestehend[0].person_refs):
            return [sync_service.manuelle_kennung_kollidiert(bestehend[0].album_name)]
        return [sync_service.album_gab_es_schon(bestehend[0].album_name)]

    async with store.gruppen_schloss(name_fuer_gruppe):
        gruppe = gruppe_vorab if festgelegt else store.group_id_for_name(name_fuer_gruppe)
        if body.existing_album_id:
            _, album_logs = await sync_service.link_existing_album(
                match_id=match_id,
                owner_account=owner,
                album_id=body.existing_album_id,
                album_name=album_name_vorab,
                all_accounts=all_accounts,
                person_refs=person_refs,
                store=store,
                group_id=gruppe,
            )
        else:
            _, album_logs = await sync_service.create_shared_album(
                match_id=match_id,
                owner_account=owner,
                all_accounts=all_accounts,
                person_refs=person_refs,
                album_name=body.album_name,
                store=store,
                group_id=gruppe,
            )
    return album_logs


@router.post("/names-multi", response_model=list[SyncLogEntry])
async def sync_names_multi(body: SyncNamesMultiRequest, request: Request):
    """Sync a canonical name + optionally create an album for N persons at once."""
    if len(body.persons) < 2:
        raise errors.min_two_people()

    store = request.app.state.store
    accounts_persons: list[tuple] = []
    person_refs: list[dict] = []

    for entry in body.persons:
        acc = store.get_account(entry.account_id)
        if not acc:
            raise errors.account_id_not_found(entry.account_id)
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
            await request.app.state.client_pool.get_for_account(acc).get_person(person_id)
        except Exception:
            raise errors.person_validation_failed(acc.name)

    requested_album = bool(body.album_name or body.existing_album_id)
    owner_id = body.owner_account_id or body.persons[0].account_id
    manual_match_id = f"manual_{body.canonical_name.lower().replace(' ', '_')}_{owner_id[:8]}"
    # Die Dublettensperre lehnt hier nicht mehr pauschal ab (#86) — sie
    # unterscheidet jetzt zwei Faelle, und der Unterschied ist der ganze
    # Punkt:
    #
    #   Auswahl STECKT im Album  -> Doppelklick (oder eine Teilauswahl
    #                               derselben Gruppe). Idempotent, unten
    #                               unter dem Trefferschloss.
    #   Auswahl enthaelt FREMDE   -> KEIN Doppelklick. Die manuelle Kennung
    #                               traegt nur Name und Eigentuemer, nicht
    #                               die Auswahl; zwei verschiedene Gruppen
    #                               teilen sie sich also. Hier wird
    #                               abgelehnt, VOR dem ersten Schreibvorgang.
    #
    # TEILMENGE, nicht Gleichheit — und das ist gemessen, nicht gewaehlt:
    # `extend_match` haengt eine Person an `person_refs` des BESTEHENDEN
    # Albums und laesst die Kennung unberuehrt. Nach jeder Erweiterung ist
    # die gespeicherte Menge eine echte Obermenge, und ein Gleichheitsvergleich
    # haette den unveraenderten Wiederholungsaufruf abgelehnt — mit der
    # falschen Auskunft „andere Personen" und dem schaedlichen Rat, einen
    # anderen Namen zu waehlen. Der Blindpruefer hat das an den echten
    # Endpunkten gemessen (Nacharbeit 1, 22.09.2026).
    #
    # Gefunden haben das Fremd- und Blindpruefer unabhaengig voneinander:
    # Ohne diese Unterscheidung wurden die neuen Personen umbenannt und als
    # abgeglichen markiert, das Album des FREMDEN Paares gefunden und dem
    # Aufrufer „Erfolg, gab es schon" gemeldet. Ein Teilvollzug, als Erfolg
    # ausgegeben — schlimmer als die pauschale Ablehnung davor.
    if requested_album:
        fremd = [a for a in store.get_managed_albums()
                 if a.match_id == manual_match_id
                 and not _personenmenge(body.persons) <= _personenmenge(a.person_refs)]
        if fremd:
            raise errors.manual_match_id_collision(fremd[0].album_name)

    # ALLES, WAS ABLEHNEN KANN, GEHOERT VOR DEN ERSTEN SCHREIBVORGANG.
    #
    # Gemessen vom Blindpruefer an der ersten Nacharbeit: Die Aufloesung des
    # Albumnamens stand NACH sync_names_multi. Schlug sie fehl (Netz, 401,
    # geloeschtes Album), waren die Personen in Immich bereits umbenannt, das
    # Protokoll geschrieben und die Paare als abgeglichen markiert — und der
    # Aufrufer bekam 422 "album_name erforderlich fuer neues Album", was
    # weder stimmte noch half.
    #
    # Dieselbe Klasse traf schon vorher `owner_account_id_not_found`: auch das
    # lehnte erst ab, nachdem umbenannt war. Beides steht jetzt davor.
    # Eine Gruppenangabe wird IMMER geprueft, auch ohne Album — Widerspruch
    # UND unbekannte Kennung. Sonst nimmt derselbe Koerper einmal 422 und
    # einmal 200, je nach einem Feld, das damit nichts zu tun hat; fuer einen
    # fremden Client ist das eine Schnittstelle, die nach Tageslaune prueft
    # (Blind- und Gegenpruefer 21.09.2026, unabhaengig gemessen).
    if body.group_id is not None or body.force_new_group:
        store.resolve_group_id("", chosen=body.group_id, force_new=body.force_new_group)

    owner = None
    album_name_vorab = None
    gruppe_vorab = None
    if requested_album:
        owner = store.get_account(owner_id)
        if not owner:
            raise errors.owner_account_id_not_found(owner_id)
        if body.existing_album_id:
            album_name_vorab = await _name_des_bestehenden_albums(
                owner, body.existing_album_id, body.album_name
            )
        # Auch die Gruppenaufloesung kann ablehnen (unbekannte Kennung,
        # widerspruechliche Angaben) und gehoert deshalb HIERHER. Die erste
        # Fassung dieses Slices hat sie unter `wants_album` gesetzt — also
        # hinter das Umbenennen, genau die Klasse, die der Absatz oben
        # beschreibt und die einen Commit zuvor in derselben Datei behoben
        # wurde (Blindpruefer 21.09.2026).
        #
        # Hier wird ABGELEHNT und die ausdrueckliche Wahl FESTGELEGT — beides
        # vor jedem Schreibvorgang.
        #
        # `album_name_vorab` ZUERST, und zwar genau so weit, wie der Code es
        # haelt: Beim Verknuepfen OHNE mitgeschickten Namen ist es der echte
        # Name aus Immich; MIT mitgeschicktem Namen ist es dieser.
        gruppe_vorab = store.resolve_group_id(
            album_name_vorab or body.album_name or "",
            chosen=body.group_id, force_new=body.force_new_group,
        )

    logs = await sync_service.sync_names_multi(accounts_persons, body.canonical_name)
    store.append_log(logs)

    # Mark all pairwise combinations as names-synced
    if all(e.status == "success" for e in logs):
        store.mark_all_pairs_synced([e.person_id for e in body.persons])

    wants_album = (body.album_name or body.existing_album_id) and all(e.status == "success" for e in logs)
    if wants_album:
        assert owner is not None  # oben aufgeloest, sonst waere hier nichts gewollt
        match_id = manual_match_id
        all_accounts = store.list_accounts()
        name_fuer_gruppe = album_name_vorab or body.album_name or ""
        festgelegt = body.group_id is not None or body.force_new_group
        # Speichern unter dem Schloss (#84) — und NUR die Namensregel wird
        # darunter frisch ausgewertet.
        #
        # Die erste Fassung loeste hier in JEDEM Fall neu auf. Damit konnte
        # `resolve_group_id` nach dem Umbenennen ablehnen (404, wenn die
        # gewaehlte Gruppe inzwischen verschwunden ist) — dieselbe Klasse, die
        # der Absatz oben beschreibt, von mir zum dritten Mal in dieser Datei
        # eingebaut (Blindpruefer 21.09.2026, gemessen).
        #
        # Die ausdrueckliche Wahl steht schon fest und ist vor dem ersten
        # Schreibvorgang geprueft. Frischen Blick braucht allein die
        # Namensregel — und die kann nicht ablehnen.
        # Trefferschloss ZUERST, dann Gruppenschloss — die Reihenfolge ist
        # in `config_store._treffer_schloesser` festgelegt und der Grund,
        # warum die zwei Schloesser sich nicht verklemmen koennen.
        async with store.treffer_schloss(match_id):
            album_logs = await _manuelles_album_unter_dem_schloss(
                body=body, store=store, match_id=match_id, owner=owner,
                all_accounts=all_accounts, person_refs=person_refs,
                name_fuer_gruppe=name_fuer_gruppe,
                gruppe_vorab=gruppe_vorab, festgelegt=festgelegt,
                album_name_vorab=album_name_vorab,
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
        raise errors.managed_album_not_found()
    account = store.get_account(body.account_id)
    if not account:
        raise errors.account_id_not_found(body.account_id)
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
        raise errors.match_not_found()

    owner = store.get_account(body.owner_account_id)
    if not owner:
        raise errors.owner_account_not_found()

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

    # IDEMPOTENT statt ablehnend (#86, Owner-Entscheid).
    #
    # Die Pruefung stand frueher HIER, ausserhalb jedes Schlosses — zwei
    # gleichzeitige Anfragen mit derselben `match_id` (ein Doppelklick ist
    # genau das) liefen beide durch, bevor eine von ihnen gespeichert hatte.
    # Ergebnis: zwei verwaltete Eintraege und zwei Alben in Immich fuer EINEN
    # Treffer.
    #
    # Sie unter das Gruppenschloss zu ziehen waere falsch gewesen: Das
    # schluesselt auf den NAMEN, und zwei Anfragen mit derselben Kennung und
    # verschiedenen Namen naehmen verschiedene Schloesser.
    #
    # Und sie als Ablehnung stehen zu lassen waere im manuellen Weg (unten)
    # eine Ablehnung HINTER dem Umbenennen geworden — die Defektklasse, die
    # diese Datei dreimal getroffen hat. Wer nicht ablehnt, kann das nicht.
    async with store.treffer_schloss(body.match_id):
        return await _album_anlegen_unter_dem_schloss(body, request, owner,
                                                      all_accounts, person_refs)


async def _album_anlegen_unter_dem_schloss(body, request, owner, all_accounts,
                                           person_refs) -> list[SyncLogEntry]:
    """Der Rumpf von `create_album`, mit gehaltenem Trefferschloss.

    Eigene Funktion allein der Lesbarkeit wegen — der Rumpf haette sonst vier
    Einrueckungsstufen.

    Zwei Begruendungen, die hier eine Fassung lang standen, waren FALSCH und
    sind vom Blindpruefer gemessen worden: Die Auslagerung macht die beiden
    Schloesser im Aufrufer nicht sichtbarer, sondern trennt sie (das
    Gruppenschloss liegt jetzt hier drin). Und der Reihenfolge-Waechter
    braucht die Trennung nicht — er folgt dem Aufrufgraphen ueber Funktions-
    und Modulgrenzen; eine Ablehnung hinter dem Schreibvorgang hier drin
    faengt er genauso (nachgemessen mit einer Mutation).
    """
    store = request.app.state.store

    bestehend = [a for a in store.get_managed_albums() if a.match_id == body.match_id]
    if bestehend:
        logs = [sync_service.album_gab_es_schon(bestehend[0].album_name)]
        store.append_log(logs)
        return logs

    if body.existing_album_id:
        # Link existing album
        album_name = await _name_des_bestehenden_albums(
            owner, body.existing_album_id, body.album_name
        )
        # Aufloesen UND Speichern unter demselben Schloss (#84) — zwischen
        # beidem liegen die Immich-Aufrufe.
        async with store.gruppen_schloss(album_name):
            gruppe = store.resolve_group_id(
                album_name, chosen=body.group_id, force_new=body.force_new_group
            )
            _, logs = await sync_service.link_existing_album(
                match_id=body.match_id,
                owner_account=owner,
                album_id=body.existing_album_id,
                album_name=album_name,
                all_accounts=all_accounts,
                person_refs=person_refs,
                store=store,
                group_id=gruppe,
            )
    else:
        # Create new album
        if not body.album_name:
            raise errors.album_name_required()
        async with store.gruppen_schloss(body.album_name):
            gruppe = store.resolve_group_id(
                body.album_name, chosen=body.group_id, force_new=body.force_new_group
            )
            _, logs = await sync_service.create_shared_album(
                match_id=body.match_id,
                owner_account=owner,
                all_accounts=all_accounts,
                person_refs=person_refs,
                album_name=body.album_name,
                store=store,
                group_id=gruppe,
            )

    store.append_log(logs)
    return logs


@router.post("/album/{managed_album_id}/refresh", response_model=list[SyncLogEntry])
async def refresh_album(managed_album_id: str, request: Request):
    store = request.app.state.store
    albums = store.get_managed_albums()
    managed = next((a for a in albums if a.id == managed_album_id), None)
    if not managed:
        raise errors.managed_album_not_found()
    logs = await sync_service.refresh_managed_album(
        managed=managed, all_accounts=store.list_accounts(), store=store,
    )
    store.append_log(logs)
    return logs


def _mit_lebenden_kontodaten(store, person_refs: list[dict]) -> list[dict]:
    """Farbe und Kontoname aus den LEBENDEN Konten nachziehen.

    Die Albumliste tat das seit jeher, die Gruppenvorschau nicht — und
    ausgerechnet dort soll der Nutzer einer Zuordnung zustimmen, die sich
    nicht mehr trennen laesst. Gemessen: Nach einem Farbwechsel zeigte die
    Vorschau die alte Farbe, die Liste daneben die neue (Blindpruefer
    21.09.2026). Jetzt EINE Routine fuer beide Stellen.
    """
    account_map = {a.id: a for a in store.list_accounts()}
    for ref in person_refs:
        acc = account_map.get(ref.get("account_id", ""))
        if acc:
            ref["account_color"] = acc.color
            if not ref.get("account_name"):
                ref["account_name"] = acc.name
    return person_refs


@router.get("/albums", response_model=list[ManagedAlbum])
async def list_managed_albums(request: Request):
    store = request.app.state.store
    albums = store.get_managed_albums()
    for album in albums:
        _mit_lebenden_kontodaten(store, album.person_refs)
    return albums


@router.delete("/albums/{managed_album_id}", status_code=204)
async def delete_managed_album(managed_album_id: str, request: Request):
    """Remove a managed album record (does NOT delete the album in Immich)."""
    ok = request.app.state.store.delete_managed_album(managed_album_id)
    if not ok:
        raise errors.managed_album_not_found()


class UndoRequest(BaseModel):
    log_entry_id: str


@router.post("/undo", response_model=SyncLogEntry)
async def undo_action(body: UndoRequest, request: Request):
    store = request.app.state.store
    log = store.get_log()
    entry = next((e for e in log if e.id == body.log_entry_id), None)
    if not entry:
        raise errors.log_entry_not_found()
    if entry.action != "sync_names" or not entry.undo_data or entry.undone_at:
        raise errors.not_undoable()
    undo = entry.undo_data
    account = store.get_account(undo["account_id"])
    if not account:
        raise errors.account_gone()
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
        raise errors.invalid_time_format()
    request.app.state.store.set_auto_sync_config(body.enabled, body.time)
    return request.app.state.store.get_auto_sync_config()
