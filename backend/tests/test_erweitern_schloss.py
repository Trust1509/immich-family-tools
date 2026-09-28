"""`extend_match` muss dasselbe Albumschloss nehmen wie Refresh und Umbenennen (#101).

Befund aus dem Issue: `extend_match` schrieb bisher OHNE `_album_schloss` und
OHNE `_frisch` auf `managed`. Gemessen am echten Weg: Ein Umbenennen auf
"Neu" geht durch, danach kommt `extend_match` mit einem Abbild von VORHER
an — und schreibt den alten Namen zurueck, waehrend Immich "Neu" traegt und
beide Protokolleintraege Erfolg melden. Zwei gleichzeitige Erweiterungen fuer
dieselbe Person haengen sie zweimal an (kein Schloss); zwei gleichzeitige
Erweiterungen fuer VERSCHIEDENE Personen ueberschreiben sich gegenseitig
(kein `_frisch`), weil `update_managed_album` den Datensatz GANZ ersetzt.

Dieselbe Klasse, dieselbe Form der Probe wie `test_umbenennen_schloss.py`
(#79): echter `ConfigStore`, Immich-Client gestubbt, Nebenlaeufigkeit mit
einem erzwungenen Fenster (`docs/agents/lehren.md` §44) — ohne `await` in der
Attrappe bindet sich ein `asyncio.Lock` nie an die laufende Schleife, und die
Probe bliebe gruen, auch mit einem defekten Schloss.
"""
import asyncio
import json

import pytest

KONTO_EINS = {"id": "konto-1", "name": "Konto Eins",
              "immich_url": "http://beispiel.invalid", "api_key": "platzhalter",
              "color": "#111111", "user_id": "u1"}
KONTO_ZWEI = {"id": "konto-2", "name": "Konto Zwei",
              "immich_url": "http://beispiel-zwei.invalid", "api_key": "platzhalter",
              "color": "#222222", "user_id": "u2"}


def _album(person_refs):
    return {"id": "a1", "match_id": "m-a1", "album_id": "immich-a1",
            "album_name": "Alt", "group_id": "g1", "owner_account_id": "konto-1",
            "person_refs": person_refs, "linked_match_ids": [],
            "created_at": "2026-01-01T00:00:00+00:00", "total_assets": 1}


def _store(tmp_path, person_refs):
    from services.config_store import ConfigStore
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {"konto-1": KONTO_EINS, "konto-2": KONTO_ZWEI},
        "schema_version": 3, "managed_albums": [_album(person_refs)],
    }), encoding="utf-8")
    return ConfigStore(str(pfad))


def _immich_attrappe(monkeypatch, name_draussen, personen_assets):
    """Ein Immich, das den Albumnamen mitschreibt und je Person Assets kennt.

    `personen_assets`: dict `person_id -> Liste von Asset-IDs`. Fehlt eine
    Person, liefert `get_person_assets` eine leere Liste — genuegt fuer die
    Proben hier, die auf `person_refs` schauen, nicht auf `total_assets`.
    """
    from services import sync_service

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def get_person(self, person_id):
            await asyncio.sleep(0)
            return {"id": person_id, "name": "Family"}

        async def get_album_assets(self, _album_id):
            await asyncio.sleep(0)
            return []

        async def get_album_assets_with_name(self, _album_id):
            await asyncio.sleep(0)
            return name_draussen["wert"], []

        async def get_person_assets(self, person_id):
            await asyncio.sleep(0)
            return [{"id": a} for a in personen_assets.get(person_id, [])]

        async def add_assets_to_album(self, _album_id, ids):
            await asyncio.sleep(0)
            return [{"id": i, "success": True} for i in ids]

        async def update_album(self, album_id, payload):
            name_draussen["wert"] = payload["albumName"]
            return {"id": album_id, **payload}

    async def ohne_teilen(*_a, **_k):
        await asyncio.sleep(0)
        return []

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)
    return Client


@pytest.mark.asyncio
async def test_erweitern_mit_altem_abbild_holt_das_umbenennen_nicht_zurueck(
    tmp_path, monkeypatch
):
    """Rot-Beweis 1 (#101): verlorene Umbenennung.

    Ohne das Schloss/`_frisch` an `extend_match`: Umbenennen auf "Neu" geht
    durch, danach schreibt `extend_match` mit dem Abbild von VORHER — der
    Bestand faellt auf "Alt" zurueck, Immich traegt "Neu", beide
    Protokolleintraege melden Erfolg. Mit dem Fix bleibt "Neu" stehen UND die
    neue Person landet in `person_refs`.
    """
    from services import sync_service

    store = _store(tmp_path, person_refs=[
        {"account_id": "konto-1", "person_id": "p1", "person_name": "Eins",
         "account_name": "Konto Eins", "account_color": "#111111"},
    ])
    owner = store.get_account("konto-1")
    neues_konto = store.get_account("konto-2")
    draussen = {"wert": "Alt"}
    _immich_attrappe(monkeypatch, draussen, personen_assets={})

    # So liest der Router: EINMAL, vor dem Aufruf.
    abbild_vor_dem_umbenennen = store.get_managed_albums()[0]

    await sync_service.rename_managed_album(
        store.get_managed_albums()[0], owner, "Neu", store)
    assert draussen["wert"] == "Neu"

    logs = await sync_service.extend_match(
        abbild_vor_dem_umbenennen, neues_konto, "p2", "Zwei", None,
        [owner, neues_konto], store,
    )

    assert [e.status for e in logs] != [], "keine Protokolleintraege erzeugt"
    assert all(e.status != "error" for e in logs), logs

    bestand = store.get_managed_album("a1")
    assert bestand.album_name == "Neu", "alter Name zurueckgeholt"
    assert {r["person_id"] for r in bestand.person_refs} == {"p1", "p2"}, (
        "neue Person fehlt im Bestand")


@pytest.mark.asyncio
async def test_zwei_gleichzeitige_erweiterungen_derselben_person_haengen_sie_nur_einmal_an(
    tmp_path, monkeypatch
):
    """Rot-Beweis 2 (#101): doppelte Person.

    Zwei gleichzeitige `extend_match`-Aufrufe fuer DIESELBE Person auf
    dasselbe Album, beide mit demselben alten Abbild. Das Fenster wird durch
    `await asyncio.sleep(0)` in der Attrappe erzwungen (lehren.md §44) — ohne
    diese Zeile bindet sich `asyncio.Lock` nie an die laufende Schleife und
    die Probe bliebe gruen, auch ohne Schloss.
    """
    from services import sync_service

    store = _store(tmp_path, person_refs=[
        {"account_id": "konto-1", "person_id": "p1", "person_name": "Eins",
         "account_name": "Konto Eins", "account_color": "#111111"},
    ])
    owner = store.get_account("konto-1")
    neues_konto = store.get_account("konto-2")
    draussen = {"wert": "Alt"}
    _immich_attrappe(monkeypatch, draussen, personen_assets={})

    sync_service._album_locks.clear()

    def frisches_album():
        return store.get_managed_albums()[0]

    await asyncio.gather(
        sync_service.extend_match(
            frisches_album(), neues_konto, "p2", "Zwei", None,
            [owner, neues_konto], store),
        sync_service.extend_match(
            frisches_album(), neues_konto, "p2", "Zwei", None,
            [owner, neues_konto], store),
    )

    bestand = store.get_managed_album("a1")
    treffer = [r for r in bestand.person_refs if r["person_id"] == "p2"]
    assert len(treffer) == 1, (
        f"Person p2 haette genau einmal stehen sollen, steht {len(treffer)}-mal")


@pytest.mark.asyncio
async def test_zwei_gleichzeitige_erweiterungen_verschiedener_personen_landen_beide(
    tmp_path, monkeypatch
):
    """Rot-Beweis 3 (#101): verschiedene Personen.

    Ohne `_frisch` lesen beide Aufrufe `person_refs` von vorher, haengen ihre
    Person an ihre je EIGENE Kopie an, und `update_managed_album` ersetzt den
    Datensatz GANZ — die zweite Schreibung wirft die erste weg. Mit `_frisch`
    liest der zweite Aufruf (unter demselben Schloss) den bereits erweiterten
    Datensatz und haengt seine Person daran an; beide landen im Album.
    """
    from services import sync_service

    store = _store(tmp_path, person_refs=[
        {"account_id": "konto-1", "person_id": "p1", "person_name": "Eins",
         "account_name": "Konto Eins", "account_color": "#111111"},
    ])
    owner = store.get_account("konto-1")
    neues_konto = store.get_account("konto-2")
    draussen = {"wert": "Alt"}
    _immich_attrappe(monkeypatch, draussen, personen_assets={})

    sync_service._album_locks.clear()

    def frisches_album():
        return store.get_managed_albums()[0]

    await asyncio.gather(
        sync_service.extend_match(
            frisches_album(), neues_konto, "p2", "Zwei", None,
            [owner, neues_konto], store),
        sync_service.extend_match(
            frisches_album(), neues_konto, "p3", "Drei", None,
            [owner, neues_konto], store),
    )

    bestand = store.get_managed_album("a1")
    ids = {r["person_id"] for r in bestand.person_refs}
    assert ids == {"p1", "p2", "p3"}, f"eine Erweiterung wurde ueberschrieben: {ids}"
