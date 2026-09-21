"""Schnittstellenprobe fuer die Gruppenwahl (#81) — durch die ECHTE Tuer.

Warum es diese Datei gibt: Der Slice war zunaechst als R2 eingestuft, mit der
Begruendung, die REST-Schnittstelle habe genau einen Konsumenten. Die
Zweitstimme hat das widerlegt — der Endpunkt steht im OpenAPI-Schema und ist
mit Token von jedem Client erreichbar — und die Risikotabelle in CLAUDE.md
kennt fuer "Aussenwirkung ueber eine Schnittstelle" keine Ausnahme fuer
"nur ein bekannter Konsument".

Entscheidend war aber ein Befund, kein Argument: ZWEI der drei schweren
Funde der ersten Panel-Runde waren ueber die Oberflaeche gar nicht
erreichbar, nur ueber die API. Genau dort sass das Risiko, und genau dort
hatte niemand hingesehen.

Alle Daten erfunden; das Repo ist oeffentlich.
"""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main

# ERFUNDEN und als solches erkennbar. Hier wird nichts echtes hinterlegt: Der
# Wert lebt in einem Testprozess und steht im oeffentlichen Repo.
TESTMARKE = "nur-fuer-den-test-kein-geheimnis"
KOPF = {"Authorization": f"Bearer {TESTMARKE}"}


def _konfiguration(pfad, alben):
    pfad.write_text(json.dumps({"accounts": {}, "managed_albums": alben}), encoding="utf-8")


def _album(aid, name, gid, personen):
    return {
        "id": aid, "match_id": f"m-{aid}", "album_id": f"ia-{aid}",
        "album_name": name, "group_id": gid, "owner_account_id": "konto-1",
        "person_refs": [{"account_id": "konto-1", "person_id": p, "person_name": p,
                         "account_name": "Konto Eins", "account_color": "#111111"}
                        for p in personen],
        "created_at": "2026-01-01T00:00:00+00:00", "last_synced_at": None,
        "total_assets": 0, "status": "active",
    }


KONTEN = {
    "konto-1": {"id": "konto-1", "name": "Konto Eins",
                "immich_url": "http://beispiel.invalid", "api_key": "platzhalter-1",
                "color": "#111111", "user_id": "u1"},
    "konto-2": {"id": "konto-2", "name": "Konto Zwei",
                "immich_url": "http://beispiel.invalid", "api_key": "platzhalter-2",
                "color": "#222222", "user_id": "u2"},
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({"accounts": KONTEN, "managed_albums": [
        _album("a1", "Testalbum", "gruppe-1", ["p1", "p2"]),
        _album("a2", "Anders benannt", "gruppe-1", ["p2", "p3"]),
        _album("a3", "Doppelt", "gruppe-2", ["p4"]),
        _album("a4", "Doppelt", "gruppe-3", ["p5"]),
    ]}), encoding="utf-8")
    monkeypatch.setattr(main.settings, "secret", TESTMARKE, raising=False)
    monkeypatch.setattr(main.settings, "config_path", pfad, raising=False)
    with TestClient(main.app) as c:
        # Die Personenpruefung soll durchlaufen — geprueft wird hier die
        # GRUPPENwahl, nicht Immich. Kein Netz, keine echte Instanz.
        class Konto:
            async def get_person(self, _pid):
                return {"id": _pid}

        class Pool:
            def get_for_account(self, _acc):
                return Konto()

            def get(self, *_a, **_k):
                return Konto()

        main.app.state.client_pool = Pool()
        yield c


def _anlegen(client, **zusatz):
    """Ein Album ueber den MANUELLEN Weg anlegen — echter HTTP-Aufruf.

    Nicht ueber /sync/album: Dort braucht es ein bestehendes Match aus dem
    Gesichtsabgleich, und die Ablehnung griffe schon davor. Der manuelle Weg
    erreicht die Gruppenpruefung wirklich.
    """
    koerper = {
        "persons": [{"account_id": "konto-1", "person_id": "p1"},
                    {"account_id": "konto-2", "person_id": "p2"}],
        "canonical_name": "Testname",
        "album_name": "Testalbum",
        "owner_account_id": "konto-1",
    }
    koerper.update(zusatz)
    return client.post("/api/sync/names-multi", headers=KOPF, json=koerper)


def test_endpunkt_nennt_die_gruppe_und_ihre_personen(client):
    antwort = client.get("/api/sync/album-group", headers=KOPF, params={"album_name": "  TESTALBUM "})

    assert antwort.status_code == 200
    koerper = antwort.json()
    assert koerper["group_id"] == "gruppe-1"
    # Die GANZE Gruppe ueber Albumgrenzen hinweg, entdoppelt und in der
    # Reihenfolge des ersten Auftretens.
    assert [r["person_id"] for r in koerper["person_refs"]] == ["p1", "p2", "p3"]
    assert sorted(koerper["album_names"]) == ["Anders benannt", "Testalbum"]


@pytest.mark.parametrize(
    "name, warum",
    [
        ("Kennt keiner", "kein Treffer"),
        ("Doppelt", "mehrdeutig — zwei Gruppen tragen den Namen"),
        ("   ", "leer sagt nichts ueber Zugehoerigkeit"),
        ("", "ganz leer"),
    ],
)
def test_endpunkt_behauptet_nichts_ohne_eindeutigen_treffer(client, name, warum):
    antwort = client.get("/api/sync/album-group", headers=KOPF, params={"album_name": name})

    assert antwort.status_code == 200, warum
    assert antwort.json() is None, warum


def test_endpunkt_verlangt_den_parameter(client):
    """Ein fremder Client, der den Parameter vergisst, bekommt 422 statt 500."""
    antwort = client.get("/api/sync/album-group", headers=KOPF)

    assert antwort.status_code == 422


def test_endpunkt_steht_im_schema(client):
    """Er ist von aussen sichtbar — mit ein Grund fuer die Hochstufung auf R3.

    Ehrlich dazugesagt: Das Schema liegt HINTER der Anmeldung, ein beliebiger
    Fremder sieht es also nicht. Der Auslöser der Risikotabelle fragt aber
    nicht nach der Zahl der Konsumenten, sondern danach, ob die Aenderung nach
    aussen wirkt — und wer das Token hat, sieht und benutzt den Endpunkt.
    """
    schema = client.get("/api/openapi.json", headers=KOPF).json()

    assert "/api/sync/album-group" in schema["paths"]


def test_unbekannte_kennung_wird_abgelehnt_und_nichts_angelegt(client):
    """Eine geratene Kennung darf keine Geistergruppe erzeugen — ueber HTTP.

    Ueber die Oberflaeche ist dieser Aufruf nicht formulierbar; ueber die
    Schnittstelle sofort. Genau diese Luecke hat die Hochstufung ausgeloest.
    """
    antwort = _anlegen(client, group_id="gibt-es-nicht")

    assert antwort.status_code == 404
    assert antwort.json().get("error_key") == "err_group_not_found"

    # Und kein Album ist dabei entstanden.
    alben = client.get("/api/sync/albums", headers=KOPF).json()
    assert [a["id"] for a in alben] == ["a1", "a2", "a3", "a4"]


def test_widersprechende_angaben_werden_abgelehnt(client):
    antwort = _anlegen(client, group_id="gruppe-1", force_new_group=True)

    assert antwort.status_code == 422
    assert antwort.json().get("error_key") == "err_group_choice_conflict"


def test_leere_kennung_ist_eine_angabe_und_kein_versehen(client):
    """`group_id: ""` galt mit dem Wahrheitswert als "nicht gesetzt"."""
    antwort = _anlegen(client, group_id="", force_new_group=True)

    assert antwort.status_code == 422
    assert antwort.json().get("error_key") == "err_group_choice_conflict"


def test_names_multi_lehnt_ab_BEVOR_umbenannt_wird(client, monkeypatch):
    """Alles, was ablehnen kann, gehoert vor den ersten Schreibvorgang.

    Beide Panel-Stimmen haben unabhaengig gemessen, dass die
    Gruppenaufloesung hier NACH dem Umbenennen stand — und zwar einen Commit,
    nachdem dieselbe Klasse in derselben Datei behoben worden war.
    """
    from services import sync_service

    geschrieben: list[str] = []

    async def merkt_sich(*_a, **_k):
        geschrieben.append("sync_names_multi")
        return []

    monkeypatch.setattr(sync_service, "sync_names_multi", merkt_sich)

    antwort = client.post("/api/sync/names-multi", headers=KOPF, json={
        "persons": [{"account_id": "konto-1", "person_id": "p1"},
                    {"account_id": "konto-1", "person_id": "p2"}],
        "canonical_name": "Testname",
        "album_name": "Testalbum",
        "group_id": "gibt-es-nicht",
    })

    assert antwort.status_code in (404, 400)
    assert geschrieben == [], "es darf nichts umbenannt worden sein"


# ----------------------------------------------------------------------
# Die VIER Verdrahtungsstellen
#
# `group_id=gruppe` steht an vier Aufrufstellen: anlegen und verknuepfen, je
# einmal in /names-multi und in /album. Der erste Mutationslauf traf davon
# genau EINE — die anderen drei liessen sich ersatzlos streichen, ohne dass
# ein Test rot wurde (Blindpruefer 21.09.2026, gemessen). Die Behauptung
# "30 Mutationen, alle gefangen" war deshalb falsch: gemessen wurde, was
# ausgewaehlt war, nicht was da ist.
#
# Diese Proben gehen durch die echte Tuer und pruefen, was GESPEICHERT wird.
# ----------------------------------------------------------------------


@pytest.fixture
def ohne_immich(monkeypatch):
    """Immich-Aufrufe stillgelegt — geprueft wird die Gruppenvergabe."""
    from services import sync_service

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def create_album(self, _name, _ids):
            return {"id": "neues-immich-album"}

        async def get_album_info(self, _album_id):
            return {"albumName": "Testalbum"}

        async def get_album_assets(self, _album_id):
            return []

        async def get_person_assets(self, _pid):
            return []

        async def add_assets_to_album(self, _album_id, _ids):
            return []

    async def ohne_teilen(*_a, **_k):
        return []

    async def ohne_namen(*_a, **_k):
        return []

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)
    monkeypatch.setattr(sync_service, "sync_names_multi", ohne_namen)
    monkeypatch.setattr("services.immich_client.ImmichClient", Client)


def _gruppe_von(client, match_id: str) -> str:
    alben = client.get("/api/sync/albums", headers=KOPF).json()
    treffer = [a for a in alben if a["match_id"] == match_id]
    assert len(treffer) == 1, f"kein Album zu {match_id}"
    return treffer[0]["group_id"]


def test_names_multi_anlegen_folgt_der_wahl(client, ohne_immich):
    antwort = _anlegen(client, force_new_group=True)

    assert antwort.status_code == 200
    gruppe = _gruppe_von(client, "manual_testname_konto-1")
    assert gruppe != "gruppe-1", "der Name haette gruppe-1 getroffen"


def test_names_multi_verknuepfen_folgt_der_wahl(client, ohne_immich):
    antwort = _anlegen(client, album_name=None, existing_album_id="immich-x",
                       force_new_group=True)

    assert antwort.status_code == 200
    gruppe = _gruppe_von(client, "manual_testname_konto-1")
    assert gruppe != "gruppe-1", "der echte Name 'Testalbum' haette gruppe-1 getroffen"


def test_names_multi_anlegen_tritt_ohne_wahl_der_gruppe_bei(client, ohne_immich):
    """Der Rueckfall muss ebenso verdrahtet sein wie die Wahl."""
    antwort = _anlegen(client)

    assert antwort.status_code == 200
    assert _gruppe_von(client, "manual_testname_konto-1") == "gruppe-1"


def test_names_multi_tritt_der_ausdruecklich_gewaehlten_gruppe_bei(client, ohne_immich):
    """Nicht nur 'eigene Gruppe' — auch der ausdrueckliche Beitritt.

    Genau dieser Weg war end-to-end ungedeckt: Die Oberflaeche schickt seit
    der Nacharbeit `group_id` mit, und nichts pruefte, ob der Router sie
    benutzt.
    """
    antwort = _anlegen(client, album_name="Kennt keiner", group_id="gruppe-2")

    assert antwort.status_code == 200
    assert _gruppe_von(client, "manual_testname_konto-1") == "gruppe-2"


def test_gruppenangabe_wird_auch_ohne_album_geprueft(client):
    """Derselbe Koerper darf nicht mal 422 und mal 200 sein."""
    antwort = client.post("/api/sync/names-multi", headers=KOPF, json={
        "persons": [{"account_id": "konto-1", "person_id": "p1"},
                    {"account_id": "konto-2", "person_id": "p2"}],
        "canonical_name": "Testname",
        "group_id": "gibt-es-nicht",
        "force_new_group": True,
    })

    assert antwort.status_code == 422
    assert antwort.json().get("error_key") == "err_group_choice_conflict"


def test_vorschau_zeigt_lebende_kontodaten(client, tmp_path):
    """Veraltete Farben ausgerechnet dort, wo zugestimmt werden soll."""
    vorher = client.get("/api/sync/album-group", headers=KOPF,
                        params={"album_name": "Testalbum"}).json()
    assert vorher["person_refs"][0]["account_color"] == "#111111"

    # Die Farbe direkt im Bestand aendern: Geprueft wird, ob die VORSCHAU
    # lebende Kontodaten liest — nicht, wie man Konten bearbeitet.
    main.app.state.store._data["accounts"]["konto-1"]["color"] = "#aaaaaa"

    nachher = client.get("/api/sync/album-group", headers=KOPF,
                         params={"album_name": "Testalbum"}).json()
    assert nachher["person_refs"][0]["account_color"] == "#aaaaaa"


def test_post_album_benutzt_die_gewaehlte_gruppe(client, ohne_immich, monkeypatch):
    """Der HAUPTWEG — die Vorschlagsliste. Ueber ihn lief keine Probe.

    Gemessen vom Gegenpruefer: `chosen=body.group_id` -> `chosen=None` in
    diesem Endpunkt ueberlebte die volle Suite. Der Name ist hier absichtlich
    MEHRDEUTIG ("Doppelt" traegt gruppe-2 und gruppe-3), damit die Namensregel
    und die Wahl verschiedene Ergebnisse liefern — sonst prueft der Test
    nichts.
    """
    import routers.faces as faces

    treffer = SimpleNamespace(
        id="match-vorschlag",
        person_a=SimpleNamespace(account_id="konto-1", person_id="p7",
                                 person_name="Person G", account_name="Konto Eins",
                                 account_color="#111111"),
        person_b=SimpleNamespace(account_id="konto-2", person_id="p8",
                                 person_name="Person H", account_name="Konto Zwei",
                                 account_color="#222222"),
    )

    async def hole_matches(_request):
        return [treffer]

    monkeypatch.setattr(faces, "get_matches", hole_matches)

    antwort = client.post("/api/sync/album", headers=KOPF, json={
        "match_id": "match-vorschlag",
        "owner_account_id": "konto-1",
        "album_name": "Doppelt",
        "group_id": "gruppe-2",
    })

    assert antwort.status_code == 200, antwort.text
    assert _gruppe_von(client, "match-vorschlag") == "gruppe-2"


def test_post_album_oeffnet_auf_wunsch_eine_eigene_gruppe(client, ohne_immich, monkeypatch):
    import routers.faces as faces

    treffer = SimpleNamespace(
        id="match-vorschlag",
        person_a=SimpleNamespace(account_id="konto-1", person_id="p7",
                                 person_name="Person G", account_name="Konto Eins",
                                 account_color="#111111"),
        person_b=SimpleNamespace(account_id="konto-2", person_id="p8",
                                 person_name="Person H", account_name="Konto Zwei",
                                 account_color="#222222"),
    )

    async def hole_matches(_request):
        return [treffer]

    monkeypatch.setattr(faces, "get_matches", hole_matches)

    antwort = client.post("/api/sync/album", headers=KOPF, json={
        "match_id": "match-vorschlag",
        "owner_account_id": "konto-1",
        "album_name": "Testalbum",
        "force_new_group": True,
    })

    assert antwort.status_code == 200, antwort.text
    assert _gruppe_von(client, "match-vorschlag") != "gruppe-1"


def _vorschlags_match(monkeypatch):
    import routers.faces as faces

    treffer = SimpleNamespace(
        id="match-vorschlag",
        person_a=SimpleNamespace(account_id="konto-1", person_id="p7",
                                 person_name="Person G", account_name="Konto Eins",
                                 account_color="#111111"),
        person_b=SimpleNamespace(account_id="konto-2", person_id="p8",
                                 person_name="Person H", account_name="Konto Zwei",
                                 account_color="#222222"),
    )

    async def hole_matches(_request):
        return [treffer]

    monkeypatch.setattr(faces, "get_matches", hole_matches)


def test_post_album_verknuepfen_folgt_der_wahl(client, ohne_immich, monkeypatch):
    """Der VIERTE Aufrufort — Verknuepfen ueber die Vorschlagsliste.

    Von vier Stellen, an denen `group_id=gruppe` steht, hatte der erste
    Mutationslauf genau eine getroffen. Diese hier war die letzte ungedeckte.
    """
    _vorschlags_match(monkeypatch)

    antwort = client.post("/api/sync/album", headers=KOPF, json={
        "match_id": "match-vorschlag",
        "owner_account_id": "konto-1",
        "existing_album_id": "immich-x",   # get_album_info liefert "Testalbum"
        "force_new_group": True,
    })

    assert antwort.status_code == 200, antwort.text
    assert _gruppe_von(client, "match-vorschlag") != "gruppe-1"


def test_post_album_verknuepfen_tritt_der_gewaehlten_gruppe_bei(client, ohne_immich, monkeypatch):
    _vorschlags_match(monkeypatch)

    antwort = client.post("/api/sync/album", headers=KOPF, json={
        "match_id": "match-vorschlag",
        "owner_account_id": "konto-1",
        "existing_album_id": "immich-x",
        "group_id": "gruppe-2",
    })

    assert antwort.status_code == 200, antwort.text
    assert _gruppe_von(client, "match-vorschlag") == "gruppe-2"


def test_leerraum_name_reisst_die_gruppe_nicht_ab(client, ohne_immich, monkeypatch):
    """Ein Name aus reinem Leerraum ist truthy — und war genau deshalb gefaehrlich.

    `_name_des_bestehenden_albums` ignoriert ihn und holt den echten Namen;
    die Gruppenaufloesung nahm in einer frueheren Fassung trotzdem den
    Leerraum. Ergebnis: Das Album wurde unter dem echten Namen gespeichert,
    aber in einer eigenen Gruppe.
    """
    _vorschlags_match(monkeypatch)

    antwort = client.post("/api/sync/album", headers=KOPF, json={
        "match_id": "match-vorschlag",
        "owner_account_id": "konto-1",
        "existing_album_id": "immich-x",
        "album_name": "   ",
    })

    assert antwort.status_code == 200, antwort.text
    # Der echte Name ist "Testalbum" -> gruppe-1.
    assert _gruppe_von(client, "match-vorschlag") == "gruppe-1"


def test_names_multi_leerraum_name_reisst_die_gruppe_nicht_ab(client, ohne_immich):
    """Derselbe Fall im manuellen Weg — eigene Zeile, eigene Probe.

    Eine erste Fassung dieses Tests lief gegen /sync/album und liess die
    vertauschte Reihenfolge in /sync/names-multi ungeprueft durch: zwei
    Endpunkte, zwei Zeilen, und eine Probe deckt nicht beide.
    """
    antwort = _anlegen(client, album_name="   ", existing_album_id="immich-x")

    assert antwort.status_code == 200, antwort.text
    # Der echte Name aus Immich ist "Testalbum" -> gruppe-1.
    assert _gruppe_von(client, "manual_testname_konto-1") == "gruppe-1"


# ----------------------------------------------------------------------
# Gleichzeitige Anlagen (#84)
#
# Gemessen vom Gegenpruefer zu #81: Zwei parallele Anlagen mit DEMSELBEN
# neuen Namen oeffnen zwei Gruppen. Danach ist der Name dauerhaft
# mehrdeutig, die Vorschau schweigt fuer immer, und die Oberflaeche bietet
# keinen Weg zurueck — sie kann nur beitreten, was angezeigt wird.
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zwei_gleichzeitige_anlagen_oeffnen_eine_gruppe(tmp_path, monkeypatch):
    """Derselbe neue Name, zwei Anfragen zugleich — EINE Gruppe.

    Das Fenster liegt zwischen der Aufloesung und dem Speichern: Dazwischen
    laufen die Immich-Aufrufe, und an jedem `await` kann die andere Anfrage
    drankommen. Beide sehen dann "diesen Namen gibt es noch nicht".
    """
    import asyncio
    import json as _json

    import main
    from models.match import MultiSyncPersonEntry, SyncNamesMultiRequest
    from routers import albums as albums_router
    from services import sync_service
    from services.config_store import ConfigStore

    pfad = tmp_path / "accounts.json"
    pfad.write_text(_json.dumps({"accounts": KONTEN, "managed_albums": []}), encoding="utf-8")
    store = ConfigStore(str(pfad))

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def create_album(self, _name, _ids):
            # Der Immich-Aufruf ist das Fenster: hier gibt die Anfrage ab.
            await asyncio.sleep(0)
            return {"id": "immich-neu"}

        async def get_person_assets(self, _pid):
            await asyncio.sleep(0)
            return []

    async def ohne_teilen(*_a, **_k):
        return []

    async def ohne_namen(*_a, **_k):
        return []

    class Konto:
        async def get_person(self, _pid):
            return {"id": _pid}

    class Pool:
        def get_for_account(self, _acc):
            return Konto()

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)
    monkeypatch.setattr(sync_service, "sync_names_multi", ohne_namen)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        store=store, client_pool=Pool())))

    def anfrage(nr):
        return SyncNamesMultiRequest(
            persons=[MultiSyncPersonEntry(account_id="konto-1", person_id=f"p{nr}a"),
                     MultiSyncPersonEntry(account_id="konto-2", person_id=f"p{nr}b")],
            canonical_name=f"Name {nr}",
            album_name="Gleicher Name",
            owner_account_id="konto-1",
        )

    await asyncio.gather(
        albums_router.sync_names_multi(anfrage(1), request),
        albums_router.sync_names_multi(anfrage(2), request),
    )

    gruppen = {a.group_id for a in store.get_managed_albums()}
    assert len(store.get_managed_albums()) == 2, "beide Alben wurden angelegt"
    assert len(gruppen) == 1, f"zwei Gruppen fuer denselben Namen: {gruppen}"
    # Und die Vorschau schweigt danach NICHT.
    assert store.existing_group_for_name("Gleicher Name") is not None


@pytest.mark.asyncio
async def test_gleichzeitige_anlagen_mit_verschiedenen_namen_blockieren_sich_nicht(
    tmp_path, monkeypatch
):
    """Das Schloss sperrt je NAMEN, nicht global.

    Ein Schloss ueber alles waere korrekt und waere eine Warteschlange: Zwei
    Familien, die gleichzeitig Alben anlegen, wuerden sich gegenseitig auf
    die Immich-Aufrufe warten lassen. Hier wird gemessen, dass sie es nicht
    tun — sonst ist die Zusage "nur gegen denselben Namen" unbelegt.
    """
    import asyncio
    import json as _json

    from models.match import MultiSyncPersonEntry, SyncNamesMultiRequest
    from routers import albums as albums_router
    from services import sync_service
    from services.config_store import ConfigStore

    pfad = tmp_path / "accounts.json"
    pfad.write_text(_json.dumps({"accounts": KONTEN, "managed_albums": []}), encoding="utf-8")
    store = ConfigStore(str(pfad))

    drin = asyncio.Event()
    weiter = asyncio.Event()

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def create_album(self, name, _ids):
            if name == "Erster":
                # Haelt das Schloss fuer "Erster" fest.
                drin.set()
                await weiter.wait()
            return {"id": f"immich-{name}"}

        async def get_person_assets(self, _pid):
            return []

    async def ohne_teilen(*_a, **_k):
        return []

    async def ohne_namen(*_a, **_k):
        return []

    class Konto:
        async def get_person(self, _pid):
            return {"id": _pid}

    class Pool:
        def get_for_account(self, _acc):
            return Konto()

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)
    monkeypatch.setattr(sync_service, "sync_names_multi", ohne_namen)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        store=store, client_pool=Pool())))

    def anfrage(nr, name):
        return SyncNamesMultiRequest(
            persons=[MultiSyncPersonEntry(account_id="konto-1", person_id=f"p{nr}a"),
                     MultiSyncPersonEntry(account_id="konto-2", person_id=f"p{nr}b")],
            canonical_name=f"Name {nr}",
            album_name=name,
            owner_account_id="konto-1",
        )

    erster = asyncio.create_task(albums_router.sync_names_multi(anfrage(1, "Erster"), request))
    await drin.wait()

    # Waehrend "Erster" das Schloss haelt, muss "Zweiter" DURCHLAUFEN.
    await asyncio.wait_for(
        albums_router.sync_names_multi(anfrage(2, "Zweiter"), request), timeout=2.0
    )

    weiter.set()
    await erster

    namen = {a.album_name for a in store.get_managed_albums()}
    assert namen == {"Erster", "Zweiter"}


@pytest.mark.asyncio
async def test_zwei_gleichzeitige_anlagen_ueber_die_vorschlagsliste(tmp_path, monkeypatch):
    """Derselbe Fall am HAUPTWEG — er war ungedeckt.

    Gemessen: Die Mutation "Anlegen ohne Schloss" in `create_album`
    ueberlebte die volle Suite, weil die Nebenlaeufigkeits-Probe nur den
    manuellen Weg fuhr. Zwei Endpunkte, zwei Schloesser, zwei Proben.
    """
    import asyncio
    import json as _json

    from models.match import SyncAlbumRequest
    from routers import albums as albums_router
    import routers.faces as faces
    from services import sync_service
    from services.config_store import ConfigStore

    pfad = tmp_path / "accounts.json"
    pfad.write_text(_json.dumps({"accounts": KONTEN, "managed_albums": []}), encoding="utf-8")
    store = ConfigStore(str(pfad))

    def treffer(nr):
        return SimpleNamespace(
            id=f"match-{nr}",
            person_a=SimpleNamespace(account_id="konto-1", person_id=f"p{nr}a",
                                     person_name=f"A{nr}", account_name="Konto Eins",
                                     account_color="#111111"),
            person_b=SimpleNamespace(account_id="konto-2", person_id=f"p{nr}b",
                                     person_name=f"B{nr}", account_name="Konto Zwei",
                                     account_color="#222222"),
        )

    async def hole_matches(_request):
        return [treffer(1), treffer(2)]

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def create_album(self, _name, _ids):
            await asyncio.sleep(0)   # das Fenster
            return {"id": "immich-neu"}

        async def get_person_assets(self, _pid):
            await asyncio.sleep(0)
            return []

    async def ohne_teilen(*_a, **_k):
        return []

    monkeypatch.setattr(faces, "get_matches", hole_matches)
    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)))

    def anfrage(nr):
        return SyncAlbumRequest(match_id=f"match-{nr}", owner_account_id="konto-1",
                                album_name="Gleicher Name")

    await asyncio.gather(
        albums_router.create_album(anfrage(1), request),
        albums_router.create_album(anfrage(2), request),
    )

    alben = store.get_managed_albums()
    assert len(alben) == 2
    assert len({a.group_id for a in alben}) == 1, "zwei Gruppen fuer denselben Namen"


@pytest.mark.asyncio
async def test_zwei_gleichzeitige_verknuepfungen_ueber_die_vorschlagsliste(tmp_path, monkeypatch):
    """Die dritte Tuer: gleichzeitig zwei bestehende Alben gleichen Namens.

    Gemessen: Die Mutation "Verknuepfen ohne Schloss" ueberlebte, weil die
    beiden Nebenlaeufigkeits-Proben nur ANLEGEN pruefen. Dieselbe Gefahr,
    anderer Zweig — das Muster, das dieses Projekt schon mehrfach getroffen
    hat (lehren.md §28).
    """
    import asyncio
    import json as _json

    from models.match import SyncAlbumRequest
    from routers import albums as albums_router
    import routers.faces as faces
    from services import sync_service
    from services.config_store import ConfigStore

    pfad = tmp_path / "accounts.json"
    pfad.write_text(_json.dumps({"accounts": KONTEN, "managed_albums": []}), encoding="utf-8")
    store = ConfigStore(str(pfad))

    def treffer(nr):
        return SimpleNamespace(
            id=f"match-{nr}",
            person_a=SimpleNamespace(account_id="konto-1", person_id=f"q{nr}a",
                                     person_name=f"A{nr}", account_name="Konto Eins",
                                     account_color="#111111"),
            person_b=SimpleNamespace(account_id="konto-2", person_id=f"q{nr}b",
                                     person_name=f"B{nr}", account_name="Konto Zwei",
                                     account_color="#222222"),
        )

    async def hole_matches(_request):
        return [treffer(1), treffer(2)]

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def get_album_info(self, _album_id):
            await asyncio.sleep(0)
            return {"albumName": "Gleicher Name"}

        async def get_album_assets(self, _album_id):
            await asyncio.sleep(0)
            return []

        async def get_person_assets(self, _pid):
            await asyncio.sleep(0)
            return []

        async def add_assets_to_album(self, _album_id, _ids):
            return []

    async def ohne_teilen(*_a, **_k):
        return []

    monkeypatch.setattr(faces, "get_matches", hole_matches)
    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr("services.immich_client.ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)))

    def anfrage(nr):
        return SyncAlbumRequest(match_id=f"match-{nr}", owner_account_id="konto-1",
                                existing_album_id=f"immich-{nr}")

    await asyncio.gather(
        albums_router.create_album(anfrage(1), request),
        albums_router.create_album(anfrage(2), request),
    )

    alben = store.get_managed_albums()
    assert len(alben) == 2
    assert len({a.group_id for a in alben}) == 1, "zwei Gruppen fuer denselben Namen"


@pytest.mark.asyncio
async def test_verschwundene_gruppe_lehnt_nach_dem_umbenennen_nicht_mehr_ab(tmp_path, monkeypatch):
    """Die ausdrueckliche Wahl darf nach dem Schreibvorgang nicht mehr kippen.

    Dritte Auflage derselben Klasse in dieser Datei: Loest man die Gruppe
    unter dem Schloss ERNEUT auf, kann sie dort ablehnen (404), obwohl die
    Personen in Immich schon umbenannt sind. Ausgeloest davon, dass die
    gewaehlte Gruppe zwischen Pruefung und Benutzung verschwindet — etwa
    durch ein gleichzeitiges Loeschen (Blindpruefer 21.09.2026, gemessen).

    Die Wahl steht mit der Pruefung fest; nur die Namensregel wird unter dem
    Schloss frisch ausgewertet, und die kann nicht ablehnen.
    """
    import json as _json

    from models.match import MultiSyncPersonEntry, SyncNamesMultiRequest
    from routers import albums as albums_router
    from services import sync_service
    from services.config_store import ConfigStore

    pfad = tmp_path / "accounts.json"
    pfad.write_text(_json.dumps({"accounts": KONTEN, "managed_albums": [
        _album("a1", "Testalbum", "gruppe-1", ["p1"]),
    ]}), encoding="utf-8")
    store = ConfigStore(str(pfad))

    umbenannt: list[str] = []

    async def benennt_um_und_loescht(*_a, **_k):
        umbenannt.append("sync_names_multi")
        # Waehrend des Umbenennens verschwindet die gewaehlte Gruppe.
        store._data["managed_albums"] = []
        return []

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def create_album(self, _name, _ids):
            return {"id": "immich-neu"}

        async def get_person_assets(self, _pid):
            return []

    async def ohne_teilen(*_a, **_k):
        return []

    class Konto:
        async def get_person(self, _pid):
            return {"id": _pid}

    class Pool:
        def get_for_account(self, _acc):
            return Konto()

    monkeypatch.setattr(sync_service, "sync_names_multi", benennt_um_und_loescht)
    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        store=store, client_pool=Pool())))
    anfrage = SyncNamesMultiRequest(
        persons=[MultiSyncPersonEntry(account_id="konto-1", person_id="p1"),
                 MultiSyncPersonEntry(account_id="konto-2", person_id="p2")],
        canonical_name="Testname",
        album_name="Ganz neuer Name",
        owner_account_id="konto-1",
        group_id="gruppe-1",
    )

    await albums_router.sync_names_multi(anfrage, request)   # darf NICHT werfen

    assert umbenannt == ["sync_names_multi"], "es wurde umbenannt"
    gespeichert = {a.match_id: a.group_id for a in store.get_managed_albums()}
    assert gespeichert["manual_testname_konto-1"] == "gruppe-1", (
        "die ausdrueckliche Wahl muss stehen bleiben"
    )


@pytest.mark.asyncio
async def test_schloss_normalisiert_den_namen(tmp_path, monkeypatch):
    """"Gleicher Name" und "gleicher name " sind derselbe Schlossschluessel.

    Gemessen: Das Schloss auf den ROHEN Namen zu setzen ueberlebte die volle
    Suite — Schloss- und Gruppenschluessel muessen gleich normalisieren,
    sonst sperrt das Schloss an der falschen Stelle.
    """
    import asyncio
    import json as _json

    from models.match import MultiSyncPersonEntry, SyncNamesMultiRequest
    from routers import albums as albums_router
    from services import sync_service
    from services.config_store import ConfigStore

    pfad = tmp_path / "accounts.json"
    pfad.write_text(_json.dumps({"accounts": KONTEN, "managed_albums": []}), encoding="utf-8")
    store = ConfigStore(str(pfad))

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def create_album(self, _name, _ids):
            await asyncio.sleep(0)
            return {"id": "immich-neu"}

        async def get_person_assets(self, _pid):
            await asyncio.sleep(0)
            return []

    async def ohne_teilen(*_a, **_k):
        return []

    async def ohne_namen(*_a, **_k):
        return []

    class Konto:
        async def get_person(self, _pid):
            return {"id": _pid}

    class Pool:
        def get_for_account(self, _acc):
            return Konto()

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)
    monkeypatch.setattr(sync_service, "sync_names_multi", ohne_namen)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        store=store, client_pool=Pool())))

    def anfrage(nr, name):
        return SyncNamesMultiRequest(
            persons=[MultiSyncPersonEntry(account_id="konto-1", person_id=f"n{nr}a"),
                     MultiSyncPersonEntry(account_id="konto-2", person_id=f"n{nr}b")],
            canonical_name=f"Name {nr}",
            album_name=name,
            owner_account_id="konto-1",
        )

    await asyncio.gather(
        albums_router.sync_names_multi(anfrage(1, "Gleicher Name"), request),
        albums_router.sync_names_multi(anfrage(2, "  gleicher name "), request),
    )

    gruppen = {a.group_id for a in store.get_managed_albums()}
    assert len(gruppen) == 1, f"verschieden geschrieben, aber dieselbe Gruppe: {gruppen}"
