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
import asyncio
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
    aufrufe = _immich_attrappe_mit_zaehler(monkeypatch)

    abbild = store.get_managed_albums()[0]
    assert store.delete_managed_album("a1")

    with pytest.raises(errors.AppError) as exc_info:
        # Der Besitzer wird seit #117 Nachtrag NICHT mehr uebergeben, sondern
        # innerhalb des Schlosses aus dem Store gelesen (siehe dort) —
        # deshalb hier nur noch drei Argumente.
        await sync_service.rename_managed_album(abbild, "Neu", store)

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

    Beantwortet die Frage aus der Nacharbeit-1-Nachricht: Was landet im Log?
    Urspruenglich `logger.error(...)` mit dem VERALTETEN Namen aus der Kopie
    von vor der Schleife. Seit Nacharbeit 2 (Blind-/Fremdpruefer, Punkt 5)
    ist ein zwischendurch entferntes Album KEIN Fehler des Auto-Syncs mehr —
    ein Nutzer hat genau das gewollt, und doppelte Namen sind seit #98
    erlaubt (die Kennung ist die einzige verlaessliche Auskunft). Der Fall
    wird jetzt gezielt am Statuscode (404) abgefangen und als INFO mit der
    Kennung geloggt; jede ANDERE Ausnahme bleibt ERROR.
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
    info = []
    orig_error = main.logger.error
    orig_info = main.logger.info

    def _error_mitschreiben(*a, **k):
        fehler.append(a)
        return orig_error(*a, **k)

    def _info_mitschreiben(*a, **k):
        info.append(a)
        return orig_info(*a, **k)

    monkeypatch.setattr(main.logger, "error", _error_mitschreiben)
    monkeypatch.setattr(main.logger, "info", _info_mitschreiben)

    await main._run_auto_sync(types.SimpleNamespace(store=store))

    # "Bleibt" (a2) wurde normal verarbeitet ...
    nach_a2 = store.get_managed_album("a2")
    assert nach_a2 is not None
    assert nach_a2.last_synced_at
    # ... "Alt" (a1) ist und bleibt weg, nichts wurde fuer sie an Immich
    # geschickt, und das entfernte Album ist KEIN Fehler (#101, Nacharbeit 2,
    # Punkt 5): kein `logger.error`-Aufruf nennt es, stattdessen genau eine
    # INFO-Zeile mit der KENNUNG (nicht dem veralteten Namen "Alt").
    assert store.get_managed_album("a1") is None
    aufrufe_fuer_a1 = [a for a in aufrufe if "immich-a1" in a]
    assert aufrufe_fuer_a1 == [], (
        f"Immich wurde fuer das geloeschte Album a1 angesprochen: {aufrufe_fuer_a1}")
    assert fehler == [], f"das entfernte Album haette keinen ERROR ausloesen sollen: {fehler}"
    a1_info = [a for a in info if "a1" in a]
    assert len(a1_info) == 1, f"erwartet genau eine INFO-Zeile zu a1, war: {a1_info}"
    assert "Alt" not in str(a1_info[0]), (
        "der veraltete Name, nicht die Kennung, wurde geloggt")


@pytest.mark.asyncio
async def test_auto_sync_faengt_eine_unerwartete_ausnahme_ab_und_macht_bei_den_anderen_weiter(
    tmp_path, monkeypatch
):
    """Traegt die GENERISCHE `except Exception`-Zeile in `_run_auto_sync`.

    Seit Punkt 5 (Nacharbeit 2) fängt eine eigene `except errors.AppError`-
    Zeile den 404-Fall gezielt ab — die obige Probe zum entfernten Album
    prueft NUR NOCH diesen Zweig, nicht mehr die generische Zeile darunter.
    Ohne diesen Test waere die generische `except Exception`-Zeile
    unbelegt: Eine ECHTE, unerwartete Ausnahme (hier: `RuntimeError` aus
    Immich fuer Album "a1") muss weiterhin als ERROR geloggt werden UND darf
    die Verarbeitung des anderen Albums ("a2") nicht verhindern.
    """
    import types
    from services.config_store import ConfigStore
    import main

    album_bleibt = {"id": "a2", "match_id": "m-a2", "album_id": "immich-a2",
                     "album_name": "Bleibt", "group_id": "g2",
                     "owner_account_id": "konto-1", "person_refs": [REF1],
                     "linked_match_ids": [], "created_at": "2026-01-01T00:00:00+00:00",
                     "total_assets": 0}
    album_kaputt = {"id": "a1", "match_id": "m-a1", "album_id": "immich-a1",
                    "album_name": "Kaputt", "group_id": "g1",
                    "owner_account_id": "konto-1", "person_refs": [REF1],
                    "linked_match_ids": [], "created_at": "2026-01-01T00:00:00+00:00",
                    "total_assets": 0}
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {"konto-1": KONTO_EINS},
        "schema_version": 3, "managed_albums": [album_kaputt, album_bleibt],
    }), encoding="utf-8")
    store = ConfigStore(str(pfad))

    from services import sync_service

    _immich_attrappe_mit_zaehler(monkeypatch)

    # `_refresh_managed_album_unlocked` faengt Immich-Fehler LAENGST selbst
    # ab und macht daraus einen Protokolleintrag (`log_album_unreachable`) —
    # ein kaputter Immich-Client erreicht `_run_auto_sync` also NIE als
    # Ausnahme. Um die generische `except Exception`-Zeile dort wirklich zu
    # treffen, muss der Fehler EINE Ebene hoeher entstehen: direkt in
    # `refresh_managed_album` selbst, wie es z. B. ein defekter Datensatz
    # oder ein Schreibfehler des Stores koennte.
    orig_refresh = sync_service.refresh_managed_album

    async def refresh_mit_fehler_fuer_a1(managed, all_accounts, store):
        if managed.id == "a1":
            raise RuntimeError("Immich antwortet nicht")
        return await orig_refresh(managed, all_accounts, store)

    monkeypatch.setattr(sync_service, "refresh_managed_album", refresh_mit_fehler_fuer_a1)

    fehler = []
    orig_error = main.logger.error

    def _error_mitschreiben(*a, **k):
        fehler.append(a)
        return orig_error(*a, **k)

    monkeypatch.setattr(main.logger, "error", _error_mitschreiben)

    await main._run_auto_sync(types.SimpleNamespace(store=store))

    nach_a2 = store.get_managed_album("a2")
    assert nach_a2 is not None and nach_a2.last_synced_at, (
        "a2 haette trotz des Fehlers bei a1 normal laufen sollen")
    assert len(fehler) == 1, f"erwartet genau einen ERROR-Aufruf, war: {fehler}"
    # Die KENNUNG, nicht der (womoeglich veraltete) Name aus der Kopie von
    # vor der Schleife (#121 Punkt 3, #103 Punkt 4) — die Erfolgszeile logt
    # seit #79 schon die Kennung, die Fehlerzeile tat es bis hierher nicht.
    assert fehler[0][1] == "a1", "falsche Kennung im Fehlerlog genannt"
    assert "Immich antwortet nicht" in str(fehler[0][2])


@pytest.mark.asyncio
async def test_auto_sync_loop_ueberlebt_eine_ausnahme_aus_run_auto_sync(monkeypatch):
    """#101, Nacharbeit 2, Punkt 3: `_auto_sync_loop` darf an einer Ausnahme
    aus `_run_auto_sync` nicht sterben — sonst laeuft der taegliche Auto-Sync
    nach dem ERSTEN unerwarteten Fehler nie wieder, bis der Prozess neu
    startet, und niemand merkt es (kein Aufrufer wartet auf diese
    Endlosschleife).

    Gemessen (Blindpruefer): Die ERLAUBT-Begruendung fuer `_auto_sync_loop`
    im Reihenfolge-Waechter stuetzte sich bis hierher auf ein `try`/`except`,
    das KEIN Test hielt — entfernt man es, bleiben alle Tests gruen. Dieser
    Test ist der fehlende Beleg: `asyncio.sleep` und `datetime.now()` werden
    gestubbt, damit die Schleife ohne echte Wartezeit mehrfach durchlaeuft;
    `_run_auto_sync` wirft beim ersten Aufruf. Danach muss die Schleife noch
    mindestens zweimal `asyncio.sleep` erreicht haben — sie ist also nicht
    beendet.
    """
    import types
    from datetime import datetime as _echtes_datetime
    import main

    rufe = {"schlaf": 0}
    tor = asyncio.Event()
    echtes_schlafen = asyncio.sleep  # VOR dem Patchen sichern, sonst ruft die Attrappe sich selbst auf

    async def schnelles_schlafen(_sekunden):
        rufe["schlaf"] += 1
        if rufe["schlaf"] >= 3:
            tor.set()
        await echtes_schlafen(0)

    async def wirft_beim_ersten_aufruf(_app_state):
        raise RuntimeError("simulierter Fehler mitten im Auto-Sync")

    class ZeitDoppel:
        @staticmethod
        def now():
            # Immer derselbe Zeitpunkt: `_auto_sync_loop` loest deshalb nur
            # in RUNDE 1 aus (current_slot == last_run_slot ab Runde 2) —
            # das genuegt: Die Frage ist, ob die Schleife eine Ausnahme aus
            # Runde 1 UEBERLEBT, nicht, ob sie erneut ausloest.
            return _echtes_datetime(2026, 1, 1, 1, 0)

    class StoreDoppel:
        def get_auto_sync_config(self):
            return {"enabled": True, "time": "01:00"}

    fehler = []
    orig_error = main.logger.error

    def _error_mitschreiben(*a, **k):
        fehler.append(a)
        return orig_error(*a, **k)

    monkeypatch.setattr(main.asyncio, "sleep", schnelles_schlafen)
    monkeypatch.setattr(main, "datetime", ZeitDoppel)
    monkeypatch.setattr(main, "_run_auto_sync", wirft_beim_ersten_aufruf)
    monkeypatch.setattr(main.logger, "error", _error_mitschreiben)

    aufgabe = asyncio.create_task(main._auto_sync_loop(types.SimpleNamespace(store=StoreDoppel())))
    try:
        await asyncio.wait_for(tor.wait(), timeout=5)
    finally:
        aufgabe.cancel()
        with pytest.raises(asyncio.CancelledError):
            await aufgabe

    assert rufe["schlaf"] >= 3, (
        f"Schleife lief nur {rufe['schlaf']}x — sie ist an der Ausnahme gestorben")
    assert len(fehler) == 1, f"erwartet genau einen geloggten Fehler, war: {fehler}"
