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
