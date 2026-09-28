"""Album zwischen dem Lesen des Aufrufers und dem Schloss geloescht (#101, Nacharbeit 1).

Befund des Blindpruefers, aelter als der Fix aus #101, aber dieselbe Zusage
dieses Slices: `_frisch` fiel bis hierher auf die uebergebene, veraltete Kopie
zurueck, wenn der Datensatz weg war (`store.get_managed_album(managed.id) or
managed`). Der Docstring versprach dafuer einen "gibt es nicht mehr"-Weg — den
es nicht gab. Alle drei Aufrufer (`refresh_managed_album`,
`rename_managed_album`, `extend_match`) arbeiteten anschliessend klaglos mit
der alten Kopie weiter: Sie aenderten Immich, schrieben einen
Erfolgs-Protokolleintrag, und `ConfigStore.update_managed_album` speicherte
mangels passender Zeile am Ende still NICHTS (siehe dort: die Schleife findet
keinen Treffer und kehrt kommentarlos zurueck). Genau die Projekt-Praemisse
"nichts verschwindet still" war betroffen.

Seit dieser Nacharbeit liefert `_frisch` `None`, wenn der Datensatz weg ist,
und alle drei Aufrufer werfen dann `errors.managed_album_not_found()` — VOR
jedem Immich-Aufruf. Diese Datei prueft das je Wrapper direkt (nicht ueber
die echte HTTP-Tuer): Die Uebersetzung derselben Ausnahme in eine 404-Antwort
ist fuer denselben Schluessel (`err_managed_album_not_found`) an derselben
Route (`POST /api/sync/extend`) bereits ueber die echte Tuer bewiesen —
`test_reihenfolge_waechter.py`, Teil B, deckt den Fall "Album beim ERSTEN
Lesen schon unbekannt" ab. Neu und hier zu pruefen ist ausschliesslich: dass
dieselbe Ausnahme auch fuer den SPAETEREN Zeitpunkt (Album verschwindet
NACH dem Lesen des Aufrufers) kommt, und zwar bevor irgendetwas an Immich
geschickt wurde.
"""
import json

import pytest

import errors

KONTO_EINS = {"id": "konto-1", "name": "Konto Eins",
              "immich_url": "http://beispiel.invalid", "api_key": "platzhalter",
              "color": "#111111", "user_id": "u1"}
KONTO_ZWEI = {"id": "konto-2", "name": "Konto Zwei",
              "immich_url": "http://beispiel-zwei.invalid", "api_key": "platzhalter",
              "color": "#222222", "user_id": "u2"}

REF1 = {"account_id": "konto-1", "person_id": "p1", "person_name": "Eins",
        "account_name": "Konto Eins", "account_color": "#111111"}


def _store(tmp_path):
    from services.config_store import ConfigStore
    album = {"id": "a1", "match_id": "m-a1", "album_id": "immich-a1",
              "album_name": "Alt", "group_id": "g1", "owner_account_id": "konto-1",
              "person_refs": [REF1], "linked_match_ids": [],
              "created_at": "2026-01-01T00:00:00+00:00", "total_assets": 1}
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {"konto-1": KONTO_EINS, "konto-2": KONTO_ZWEI},
        "schema_version": 3, "managed_albums": [album],
    }), encoding="utf-8")
    return ConfigStore(str(pfad))


def _immich_attrappe_mit_zaehler(monkeypatch):
    """Immich-Attrappe, die JEDEN Aufruf zaehlt.

    Kein einziger Aufruf darf ankommen, wenn `_frisch` `None` liefert — das
    ist genau die Zusage dieses Slices ("VOR jedem Immich-Aufruf").
    """
    from services import sync_service

    aufrufe = []

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def get_person(self, person_id):
            aufrufe.append(("get_person", person_id))
            return {"id": person_id, "name": "Family"}

        async def get_album_assets(self, album_id):
            aufrufe.append(("get_album_assets", album_id))
            return []

        async def get_album_assets_with_name(self, album_id):
            aufrufe.append(("get_album_assets_with_name", album_id))
            return "Alt", []

        async def get_person_assets(self, person_id):
            aufrufe.append(("get_person_assets", person_id))
            return []

        async def add_assets_to_album(self, album_id, ids):
            aufrufe.append(("add_assets_to_album", album_id, list(ids)))
            return [{"id": i, "success": True} for i in ids]

        async def update_album(self, album_id, payload):
            aufrufe.append(("update_album", album_id, payload))
            return {"id": album_id, **payload}

        async def update_person(self, person_id, payload):
            aufrufe.append(("update_person", person_id, payload))
            return {"id": person_id, **payload}

    async def ohne_teilen(*_a, **_k):
        aufrufe.append(("share_album_if_needed",))
        return []

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)
    return aufrufe


@pytest.mark.asyncio
async def test_refresh_bricht_ab_wenn_album_vor_dem_schloss_geloescht_wurde(
    tmp_path, monkeypatch
):
    from services import sync_service

    store = _store(tmp_path)
    owner = store.get_account("konto-1")
    aufrufe = _immich_attrappe_mit_zaehler(monkeypatch)

    abbild = store.get_managed_albums()[0]   # so liest der Router / der Auto-Sync
    assert store.delete_managed_album("a1")  # dazwischen geloescht

    with pytest.raises(errors.AppError) as exc_info:
        await sync_service.refresh_managed_album(abbild, [owner], store)

    assert exc_info.value.status_code == 404
    assert exc_info.value.key == "err_managed_album_not_found"
    assert aufrufe == [], f"Immich wurde fuer ein geloeschtes Album angesprochen: {aufrufe}"
    assert store.get_managed_albums() == []


@pytest.mark.asyncio
async def test_rename_bricht_ab_wenn_album_vor_dem_schloss_geloescht_wurde(
    tmp_path, monkeypatch
):
    from services import sync_service

    store = _store(tmp_path)
    owner = store.get_account("konto-1")
    aufrufe = _immich_attrappe_mit_zaehler(monkeypatch)

    abbild = store.get_managed_albums()[0]
    assert store.delete_managed_album("a1")

    with pytest.raises(errors.AppError) as exc_info:
        await sync_service.rename_managed_album(abbild, owner, "Neu", store)

    assert exc_info.value.status_code == 404
    assert exc_info.value.key == "err_managed_album_not_found"
    assert aufrufe == [], f"Immich wurde fuer ein geloeschtes Album angesprochen: {aufrufe}"
    assert store.get_managed_albums() == []


@pytest.mark.asyncio
async def test_extend_bricht_ab_wenn_album_vor_dem_schloss_geloescht_wurde(
    tmp_path, monkeypatch
):
    from services import sync_service

    store = _store(tmp_path)
    owner = store.get_account("konto-1")
    neues_konto = store.get_account("konto-2")
    aufrufe = _immich_attrappe_mit_zaehler(monkeypatch)

    abbild = store.get_managed_albums()[0]
    assert store.delete_managed_album("a1")

    with pytest.raises(errors.AppError) as exc_info:
        await sync_service.extend_match(
            abbild, neues_konto, "p2", "Zwei", None, [owner, neues_konto], store)

    assert exc_info.value.status_code == 404
    assert exc_info.value.key == "err_managed_album_not_found"
    assert aufrufe == [], f"Immich wurde fuer ein geloeschtes Album angesprochen: {aufrufe}"
    assert store.get_managed_albums() == []


@pytest.mark.asyncio
async def test_auto_sync_faengt_das_geloeschte_album_ab_und_macht_bei_den_anderen_weiter(
    tmp_path, monkeypatch
):
    """`main._run_auto_sync` verarbeitet Alben EINZELN — eines weg, Rest normal.

    Beantwortet die Frage aus der Nacharbeit-Nachricht: Was landet im Log?
    `logger.error("Auto-sync: album '%s' failed: %s", album.album_name, exc)`
    — der Name ist die Kopie von VOR der Schleife (kann veraltet sein, siehe
    Kommentar an der Stelle), die Ausnahme selbst ist die `AppError`; ihr
    `str()` ist "<Statuscode>: <deutscher Klartext>" (Erbe von
    `HTTPException.__str__`), gemessen hier als
    "404: Managed Album nicht gefunden".
    """
    import types
    from services.config_store import ConfigStore
    import main

    album_bleibt = {"id": "a2", "match_id": "m-a2", "album_id": "immich-a2",
                     "album_name": "Bleibt", "group_id": "g2",
                     "owner_account_id": "konto-1", "person_refs": [REF1],
                     "linked_match_ids": [], "created_at": "2026-01-01T00:00:00+00:00",
                     "total_assets": 0}
    album_weg = {"id": "a1", "match_id": "m-a1", "album_id": "immich-a1",
                 "album_name": "Alt", "group_id": "g1",
                 "owner_account_id": "konto-1", "person_refs": [REF1],
                 "linked_match_ids": [], "created_at": "2026-01-01T00:00:00+00:00",
                 "total_assets": 0}
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {"konto-1": KONTO_EINS},
        "schema_version": 3, "managed_albums": [album_weg, album_bleibt],
    }), encoding="utf-8")
    store = ConfigStore(str(pfad))

    aufrufe = _immich_attrappe_mit_zaehler(monkeypatch)

    # "a1" verschwindet GENAU zwischen dem einen Lesen von `_run_auto_sync`
    # (vor der Schleife, siehe Kommentar dort) und der Verarbeitung: Der
    # gestubbte `get_managed_albums` liefert die Liste wie zum Lesezeitpunkt
    # UND loescht "a1" im selben Atemzug — dieselbe Form wie beim Router, nur
    # ohne echte Nebenlaeufigkeit noetig zu haben.
    orig_get_albums = store.get_managed_albums

    def _lesen_dann_loeschen():
        ergebnis = orig_get_albums()
        store.delete_managed_album("a1")
        return ergebnis

    monkeypatch.setattr(store, "get_managed_albums", _lesen_dann_loeschen)

    fehler = []
    orig_error = main.logger.error

    def _error_mitschreiben(*a, **k):
        fehler.append(a)
        return orig_error(*a, **k)

    monkeypatch.setattr(main.logger, "error", _error_mitschreiben)

    await main._run_auto_sync(types.SimpleNamespace(store=store))

    # "Bleibt" (a2) wurde normal verarbeitet ...
    nach_a2 = store.get_managed_album("a2")
    assert nach_a2 is not None
    assert nach_a2.last_synced_at
    # ... "Alt" (a1) ist und bleibt weg, nichts wurde fuer sie an Immich
    # geschickt, und genau EIN Fehler wurde geloggt.
    assert store.get_managed_album("a1") is None
    aufrufe_fuer_a1 = [a for a in aufrufe if "immich-a1" in a]
    assert aufrufe_fuer_a1 == [], (
        f"Immich wurde fuer das geloeschte Album a1 angesprochen: {aufrufe_fuer_a1}")
    assert len(fehler) == 1, f"erwartet genau einen geloggten Fehler, war: {fehler}"
    assert fehler[0][1] == "Alt", "falsches Album im Fehlerlog benannt"
    # `%s`-Formatierung: die dritte Positionsangabe ist das Exception-Objekt
    # selbst; `str()` einer `HTTPException` ist "<status>: <detail>" —
    # gemessen, nicht angenommen (die erste Fassung dieser Zeile erwartete
    # nur den Klartext ohne Statuscode und war rot).
    assert str(fehler[0][2]) == "404: Managed Album nicht gefunden"
