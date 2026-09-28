"""`extend_match` muss dasselbe Albumschloss nehmen wie Refresh und Umbenennen (#101).

Befund aus dem Issue: `extend_match` schrieb bisher OHNE `_album_schloss` und
OHNE `_frisch` auf `managed`. Gemessen am echten Weg: Ein Umbenennen auf
"Neu" geht durch, danach kommt `extend_match` mit einem Abbild von VORHER
an — und schreibt den alten Namen zurueck, waehrend Immich "Neu" traegt und
beide Protokolleintraege Erfolg melden.

NACHARBEIT 1 (Blind-/Fremdpruefer) hat zwei Einschaetzungen der ersten
Fassung korrigiert, siehe die betroffenen Tests unten fuer die gemessenen
Einzelheiten statt einer Regel in Prosa hier (lehren.md §47):

- Die erste Fassung bewies nur "Erweitern gegen Erweitern" und "Umbenennen
  DANACH Erweitern" (sequenziell) — nie "Erweitern GLEICHZEITIG mit
  Umbenennen/Refresh". Damit blieben 302 Tests gruen, obwohl `extend_match`
  mit einem eigenen, ANDEREN Schloss geschlossen haette (z. B. nach
  `managed.album_id` statt `managed.id`, oder einer eigenen Ablage
  `_extend_locks`) — die Kernzusage des Slices war ungeprueft. Neu:
  `test_erweitern_wartet_auf_ein_laufendes_umbenennen`,
  `test_erweitern_wartet_auf_einen_laufenden_refresh`.
- "Zwei gleichzeitige Erweiterungen fuer dieselbe Person haengen sie zweimal
  an" ist FALSCH fuer den Bestand: `update_managed_album` ersetzt den
  Datensatz GANZ, die letzte Schreibung gewinnt vollstaendig — im Bestand
  steht die Person hinterher immer genau einmal, mit oder ohne Schloss. Der
  echte Schaden liegt auf der IMMICH-Seite (zwei echte
  `add_assets_to_album`-Aufrufe, zwei erfolgreiche Protokolleintraege). Neu
  gemessen in
  `test_zwei_gleichzeitige_erweiterungen_derselben_person_haengen_sie_nur_einmal_an`.

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


# ----------------------------------------------------------------------
# Die Kernzusage selbst: DASSELBE Schloss wie Refresh und Umbenennen
#
# Nacharbeit 1 (Blind-/Fremdpruefer): Die urspruengliche Probendatei bewies
# nur Erweitern-gegen-Erweitern und ein SEQUENZIELLES Umbenennen-dann-
# Erweitern. Beides haette 302 gruene Tests auch dann gezeigt, wenn
# `extend_match` mit einem eigenen, von Refresh/Umbenennen VERSCHIEDENEN
# Schloss geschlossen haette (etwa `_album_schloss(managed.album_id)` statt
# `managed.id`, oder eine eigene Ablage `_extend_locks`) — gemessen: beide
# Mutationen liessen die volle Suite gruen. Die beiden Proben hier zwingen
# Umbenennen/Refresh und Erweitern in dasselbe Zeitfenster (`asyncio.Event`
# als Tor) und pruefen, dass die Erweiterung WARTET, statt am fremden
# Schloss vorbeizulaufen.
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_erweitern_wartet_auf_ein_laufendes_umbenennen(tmp_path, monkeypatch):
    """Der Kern der Nacharbeit: `extend_match` und `rename_managed_album`
    teilen sich EIN Schloss je Album — nicht zwei verschieden geformte.

    Gemessen (Nacharbeit 1): Schliesst `extend_match` stattdessen nach
    `managed.album_id` ("immich-a1") statt `managed.id` ("a1") — zwei
    verschiedene Zeichenketten in derselben Ablage `_album_locks` — oder in
    einer eigenen Ablage `_extend_locks`, laeuft die Erweiterung SOFORT
    durch, waehrend das Umbenennen noch am Tor haengt: Das Protokoll unten
    lautet dann `["umbenennen an", "erweitern an"]`, nicht
    `["umbenennen an", "umbenennen aus", "erweitern an"]`.
    """
    from services import sync_service

    store = _store(tmp_path, person_refs=[
        {"account_id": "konto-1", "person_id": "p1", "person_name": "Eins",
         "account_name": "Konto Eins", "account_color": "#111111"},
    ])
    owner = store.get_account("konto-1")
    neues_konto = store.get_account("konto-2")

    sync_service._album_locks.clear()
    protokoll: list[str] = []
    tor = asyncio.Event()

    async def umbenennen_innen(*_a, **_k):
        protokoll.append("umbenennen an")
        await tor.wait()
        protokoll.append("umbenennen aus")
        return []

    async def erweitern_innen(*_a, **_k):
        protokoll.append("erweitern an")
        return []

    monkeypatch.setattr(sync_service, "_rename_managed_album_unlocked", umbenennen_innen)
    monkeypatch.setattr(sync_service, "_extend_match_unlocked", erweitern_innen)

    managed = store.get_managed_albums()[0]
    u = asyncio.create_task(
        sync_service.rename_managed_album(managed, owner, "Neu", store))
    await asyncio.sleep(0)
    assert protokoll == ["umbenennen an"], protokoll

    e = asyncio.create_task(sync_service.extend_match(
        managed, neues_konto, "p2", "Zwei", None, [owner, neues_konto], store))
    for _ in range(5):
        await asyncio.sleep(0)
    # DER KERN: Die Erweiterung steht noch draussen.
    assert protokoll == ["umbenennen an"], protokoll

    tor.set()
    await asyncio.gather(u, e)
    assert protokoll == ["umbenennen an", "umbenennen aus", "erweitern an"], protokoll


@pytest.mark.asyncio
async def test_erweitern_wartet_auf_einen_laufenden_refresh(tmp_path, monkeypatch):
    """Dieselbe Probe, gegen `refresh_managed_album` statt `rename_managed_album`."""
    from services import sync_service

    store = _store(tmp_path, person_refs=[
        {"account_id": "konto-1", "person_id": "p1", "person_name": "Eins",
         "account_name": "Konto Eins", "account_color": "#111111"},
    ])
    owner = store.get_account("konto-1")
    neues_konto = store.get_account("konto-2")

    sync_service._album_locks.clear()
    protokoll: list[str] = []
    tor = asyncio.Event()

    async def refresh_innen(*_a, **_k):
        protokoll.append("refresh an")
        await tor.wait()
        protokoll.append("refresh aus")
        return []

    async def erweitern_innen(*_a, **_k):
        protokoll.append("erweitern an")
        return []

    monkeypatch.setattr(sync_service, "_refresh_managed_album_unlocked", refresh_innen)
    monkeypatch.setattr(sync_service, "_extend_match_unlocked", erweitern_innen)

    managed = store.get_managed_albums()[0]
    r = asyncio.create_task(
        sync_service.refresh_managed_album(managed, [owner], store))
    await asyncio.sleep(0)
    assert protokoll == ["refresh an"], protokoll

    e = asyncio.create_task(sync_service.extend_match(
        managed, neues_konto, "p2", "Zwei", None, [owner, neues_konto], store))
    for _ in range(5):
        await asyncio.sleep(0)
    assert protokoll == ["refresh an"], protokoll

    tor.set()
    await asyncio.gather(r, e)
    assert protokoll == ["refresh an", "refresh aus", "erweitern an"], protokoll


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
    """Rot-Beweis 2 (#101, RICHTIGGESTELLT in Nacharbeit 1): doppelte Person.

    Die erste Fassung dieses Tests pruefte nur, dass `person_refs` die Person
    hinterher genau einmal enthaelt — und das gilt IMMER, mit oder ohne
    Schloss: `update_managed_album` ersetzt den Datensatz GANZ, die letzte
    Schreibung gewinnt vollstaendig, also steht im Bestand nie eine
    Dopplung (gemessen: dieselbe Behauptung blieb gruen, wenn das Schloss
    durch `managed.album_id` statt `managed.id` oder eine eigene Ablage
    `_extend_locks` ersetzt wurde — kein Test hier haette das gefangen).

    Der echte Schaden liegt auf der IMMICH-SEITE, nicht im Bestand: Ohne
    Schloss (oder ohne `_frisch`) sehen beide gleichzeitigen Aufrufe die
    "schon enthalten"-Pruefung mit `false` (keiner kennt den anderen), und
    BEIDE rufen `add_assets_to_album` bei Immich auf — ein echter,
    doppelter Schreibvorgang gegen eine fremde API — und BEIDE erzeugen
    einen erfolgreichen `log_assets_linked`-Eintrag; keiner meldet
    `log_person_already_in_album`. Genau das prueft dieser Test jetzt:
    GENAU EIN Immich-Aufruf, GENAU EIN `log_person_already_in_album`.

    Das Fenster wird durch `await asyncio.sleep(0)` in der Attrappe
    erzwungen (lehren.md §44) — ohne diese Zeile bindet sich `asyncio.Lock`
    nie an die laufende Schleife und die Probe bliebe gruen, auch ohne
    Schloss.
    """
    from services import sync_service

    store = _store(tmp_path, person_refs=[
        {"account_id": "konto-1", "person_id": "p1", "person_name": "Eins",
         "account_name": "Konto Eins", "account_color": "#111111"},
    ])
    owner = store.get_account("konto-1")
    neues_konto = store.get_account("konto-2")
    draussen = {"wert": "Alt"}
    Client = _immich_attrappe(monkeypatch, draussen, personen_assets={"p2": ["x1"]})
    add_aufrufe: list[list[str]] = []
    orig_add = Client.add_assets_to_album

    async def add_mitzaehlen(self, album_id, ids):
        add_aufrufe.append(list(ids))
        return await orig_add(self, album_id, ids)

    monkeypatch.setattr(Client, "add_assets_to_album", add_mitzaehlen)

    sync_service._album_locks.clear()

    def frisches_album():
        return store.get_managed_albums()[0]

    logs_a, logs_b = await asyncio.gather(
        sync_service.extend_match(
            frisches_album(), neues_konto, "p2", "Zwei", None,
            [owner, neues_konto], store),
        sync_service.extend_match(
            frisches_album(), neues_konto, "p2", "Zwei", None,
            [owner, neues_konto], store),
    )

    alle_logs = logs_a + logs_b
    schon_enthalten = [e for e in alle_logs if e.message_key == "log_person_already_in_album"]
    erfolgreich_verknuepft = [e for e in alle_logs if e.message_key == "log_assets_linked"]

    assert len(add_aufrufe) == 1, (
        f"Immich haette genau EINMAL angesprochen werden sollen, war "
        f"{len(add_aufrufe)}-mal: {add_aufrufe}")
    assert len(schon_enthalten) == 1, (
        f"genau einer der beiden Aufrufe haette 'schon enthalten' melden "
        f"sollen, gemeldet haben es {len(schon_enthalten)}: "
        f"{[e.message_key for e in alle_logs]}")
    assert len(erfolgreich_verknuepft) == 1, (
        f"genau einer der beiden Aufrufe haette erfolgreich verknuepfen "
        f"sollen, erfolgreich waren {len(erfolgreich_verknuepft)}")

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
