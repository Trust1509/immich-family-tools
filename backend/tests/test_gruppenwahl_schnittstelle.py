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
        ("   ", "leer sagt nichts ueber Zugehoerigkeit"),
        ("", "ganz leer"),
    ],
)
def test_endpunkt_behauptet_nichts_ohne_treffer(client, name, warum):
    antwort = client.get("/api/sync/album-group", headers=KOPF, params={"album_name": name})

    assert antwort.status_code == 200, warum
    assert antwort.json() is None, warum


def test_endpunkt_unterscheidet_mehrdeutig_von_gar_keinem_treffer(client):
    """#113: "kein Treffer" und "mehrdeutig" sahen bis hierher GLEICH aus.

    `existing_group_for_name` (und damit die alte Fassung dieses Endpunkts)
    lieferte fuer beide `None` — die Oberflaeche konnte "neuer Name" nicht
    von "mehrere Gruppen tragen diesen Namen, aber KEINE davon ist gemeint,
    ohne dass ich es weiss" unterscheiden. Jetzt: `status: "many"` mit ALLEN
    Kandidaten, in derselben Form wie ein eindeutiger Treffer.
    """
    antwort = client.get("/api/sync/album-group", headers=KOPF, params={"album_name": "Doppelt"})

    assert antwort.status_code == 200
    koerper = antwort.json()
    assert koerper["status"] == "many"
    kandidaten = {k["group_id"]: k for k in koerper["candidates"]}
    assert set(kandidaten) == {"gruppe-2", "gruppe-3"}
    # Dieselbe Form wie der eindeutige Treffer — Kennung, Personen, Konten.
    assert [r["person_id"] for r in kandidaten["gruppe-2"]["person_refs"]] == ["p4"]
    assert [r["person_id"] for r in kandidaten["gruppe-3"]["person_refs"]] == ["p5"]
    assert kandidaten["gruppe-2"]["album_names"] == ["Doppelt"]


def test_endpunkt_traegt_die_markierungen_je_kandidat(client, tmp_path):
    """#124 B9: `owner_account_missing`/`too_few_people` fehlten in der Vorschau.

    Wer einer Gruppe beitritt, soll VORHER sehen, dass sie ein verwaistes
    Mitglied hat — nicht erst danach am einzelnen Album.
    """
    # a4 (gruppe-3) bekommt einen ANDEREN Besitzer als a3 (gruppe-2) — die
    # Fixture-Hilfsfunktion `_album` setzt sonst bei ALLEN Alben denselben
    # Besitzer ("konto-1"), und die beiden Kandidaten waeren nicht zu
    # unterscheiden.
    alben = main.app.state.store._data["managed_albums"]
    next(a for a in alben if a["id"] == "a4")["owner_account_id"] = "konto-2"

    # gruppe-2 (Album a3, Besitzer konto-1) wird verwaist: konto-1 verschwindet
    # aus dem LEBENDEN Bestand, ohne das Album selbst zu aendern — genau der
    # Fall, den `owner_account_missing` auf Gruppenebene beschreibt.
    main.app.state.store._data["accounts"].pop("konto-1")

    antwort = client.get("/api/sync/album-group", headers=KOPF, params={"album_name": "Doppelt"})

    assert antwort.status_code == 200
    kandidaten = {k["group_id"]: k for k in antwort.json()["candidates"]}
    assert kandidaten["gruppe-2"]["owner_account_missing"] is True
    assert kandidaten["gruppe-2"]["too_few_people"] is True  # genau eine Person
    assert kandidaten["gruppe-3"]["owner_account_missing"] is False


def test_too_few_people_ist_ODER_je_album_nicht_die_entdoppelte_summe(client):
    """Nacharbeit 1 zu #113/#119/#124 (Gegen F3), Owner-Entscheid #112/#123.

    "Zu wenige Personen" markiert eine GRUPPE, wenn EIN Album zu wenige
    Personen hat — ODER je Album, nicht die entdoppelte Personenzahl der
    ganzen Gruppe. Zwei Bestaende:

    * (2+1): ein Album mit zwei Personen, eins mit einer, ohne Ueberschneidung
      — die ENTDOPPELTE Summe ist hier 3 (>= 2, "genug"), obwohl das zweite
      Album fuer sich allein zu wenige hat.
    * (1+1): zwei Alben mit je EINER (verschiedenen) Person — die entdoppelte
      Summe ist hier genau 2 ("genug"), obwohl KEIN einzelnes Album fuer sich
      zwei Personen hat.

    Nach der alten Rechnung (entdoppelte Summe der Gruppe < 2) waeren BEIDE
    Bestaende "genug" gewesen; nach der neuen (ODER je Album) sind es beide
    nicht.

    Beide muessen `too_few_people: True` liefern — wie die Albumliste
    (`GET /api/sync/albums`, `ManagedAlbumOut.too_few_people`) es fuer jedes
    der beteiligten Alben schon tut.
    """
    pfad_alben = main.app.state.store._data["managed_albums"]
    pfad_alben.clear()
    pfad_alben.append(_album("zwei_eins_a", "ZweiEins", "gruppe-21", ["p1", "p2"]))
    pfad_alben.append(_album("zwei_eins_b", "ZweiEins", "gruppe-21", ["p3"]))
    pfad_alben.append(_album("eins_eins_a", "EinsEins", "gruppe-11", ["p4"]))
    pfad_alben.append(_album("eins_eins_b", "EinsEins", "gruppe-11", ["p5"]))

    v21 = client.get("/api/sync/album-group", headers=KOPF, params={"album_name": "ZweiEins"}).json()
    v11 = client.get("/api/sync/album-group", headers=KOPF, params={"album_name": "EinsEins"}).json()

    assert v21["too_few_people"] is True, v21
    assert v11["too_few_people"] is True, v11

    # Gegenprobe: EIN Album mit >= 2 Personen und sonst nichts ist NICHT
    # markiert.
    pfad_alben.append(_album("genug_a", "Genug", "gruppe-genug", ["p6", "p7"]))
    vgenug = client.get("/api/sync/album-group", headers=KOPF, params={"album_name": "Genug"}).json()
    assert vgenug["too_few_people"] is False, vgenug


def test_eindeutiger_treffer_traegt_die_markierungen_auch(client):
    """Dieselben zwei Felder auch am unveraenderten Ein-Treffer-Pfad."""
    antwort = client.get("/api/sync/album-group", headers=KOPF,
                         params={"album_name": "Testalbum"})

    koerper = antwort.json()
    assert koerper["owner_account_missing"] is False
    assert koerper["too_few_people"] is False  # gruppe-1 hat drei Personen


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


def test_vorschau_zeigt_lebende_kontodaten_auch_im_many_zweig(client, tmp_path):
    """Testluecke, Nacharbeit 1 (Blind B8): Die Kontodaten-Anreicherung
    (`_mit_lebenden_kontodaten`) galt bisher nur getestet fuer den EINDEUTIGEN
    Treffer — der MEHRDEUTIGE Zweig (`status: "many"`) ruft dieselbe Routine
    im Code schon auf (`routers/albums.py`, Schleife ueber `kandidaten`), war
    aber ungeprueft. "Doppelt" traegt zwei Gruppen (gruppe-2/gruppe-3, beide
    Besitzer "konto-1").
    """
    vorher = client.get("/api/sync/album-group", headers=KOPF,
                        params={"album_name": "Doppelt"}).json()
    assert vorher["status"] == "many"
    kandidaten_vorher = {k["group_id"]: k for k in vorher["candidates"]}
    assert kandidaten_vorher["gruppe-2"]["person_refs"][0]["account_color"] == "#111111"

    main.app.state.store._data["accounts"]["konto-1"]["color"] = "#aaaaaa"

    nachher = client.get("/api/sync/album-group", headers=KOPF,
                         params={"album_name": "Doppelt"}).json()
    kandidaten_nachher = {k["group_id"]: k for k in nachher["candidates"]}
    assert kandidaten_nachher["gruppe-2"]["person_refs"][0]["account_color"] == "#aaaaaa"
    assert kandidaten_nachher["gruppe-3"]["person_refs"][0]["account_color"] == "#aaaaaa"


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


def test_post_album_expected_no_group_wird_geprueft(client, ohne_immich, monkeypatch):
    """Testluecke, Nacharbeit 1 (Blind B5, Gegen F2): `expected_no_group` galt
    bisher nur ueber geprueft am MANUELLEN Weg (`/sync/names-multi`,
    `_anlegen`) — der HAUPTWEG (Vorschlagsliste, `/sync/album`, Anlegen) war
    ungedeckt. "Testalbum" traegt schon `gruppe-1`; wer das nicht weiss (der
    Client zeigt "keine Gruppe") und trotzdem mit `expected_no_group`
    anlegt, muss abgelehnt werden statt still beizutreten.
    """
    _vorschlags_match(monkeypatch)

    antwort = client.post("/api/sync/album", headers=KOPF, json={
        "match_id": "match-vorschlag",
        "owner_account_id": "konto-1",
        "album_name": "Testalbum",
        "expected_no_group": True,
    })

    assert antwort.status_code == 409, antwort.text
    assert antwort.json().get("error_key") == "err_group_situation_changed"


def test_post_album_verknuepfen_expected_no_group_wird_geprueft(client, ohne_immich, monkeypatch):
    """Dieselbe Testluecke fuer den VIERTEN Aufrufort — Verknuepfen ueber die
    Vorschlagsliste (Blind B6, Gegen F2). `existing_album_id="immich-x"`
    loest ueber die Attrappe auf "Testalbum" auf, das schon `gruppe-1`
    traegt.
    """
    _vorschlags_match(monkeypatch)

    antwort = client.post("/api/sync/album", headers=KOPF, json={
        "match_id": "match-vorschlag",
        "owner_account_id": "konto-1",
        "existing_album_id": "immich-x",
        "expected_no_group": True,
    })

    assert antwort.status_code == 409, antwort.text
    assert antwort.json().get("error_key") == "err_group_situation_changed"


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
    hat (lehren.md §39).
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


# ----------------------------------------------------------------------
# #113: mehrdeutiger Name OHNE ausdrueckliche Wahl wird abgelehnt
# ----------------------------------------------------------------------


def test_mehrdeutiger_name_ohne_wahl_wird_beim_anlegen_abgelehnt(client):
    """`resolve_group_id` oeffnete hier bis #113 still eine DRITTE Gruppe."""
    vorher = client.get("/api/sync/albums", headers=KOPF).json()

    antwort = _anlegen(client, album_name="Doppelt")

    assert antwort.status_code == 409, antwort.text
    assert antwort.json().get("error_key") == "err_group_choice_required"
    nachher = client.get("/api/sync/albums", headers=KOPF).json()
    assert nachher == vorher, "nichts wurde angelegt"


def test_mehrdeutiger_name_ohne_wahl_wird_beim_verknuepfen_ueber_die_vorschlagsliste_abgelehnt(
    client, monkeypatch
):
    """Derselbe Fall am HAUPTWEG (`/sync/album`), nicht nur im manuellen Weg."""
    _vorschlags_match(monkeypatch)
    vorher = client.get("/api/sync/albums", headers=KOPF).json()

    antwort = client.post("/api/sync/album", headers=KOPF, json={
        "match_id": "match-vorschlag",
        "owner_account_id": "konto-1",
        "album_name": "Doppelt",
    })

    assert antwort.status_code == 409, antwort.text
    assert antwort.json().get("error_key") == "err_group_choice_required"
    nachher = client.get("/api/sync/albums", headers=KOPF).json()
    assert nachher == vorher, "nichts wurde angelegt"


def test_mehrdeutiger_name_mit_ausdruecklicher_wahl_geht_weiter_wie_bisher(client, ohne_immich):
    """Die Ablehnung trifft NUR den Fall ohne Angabe — #113 aendert daran nichts."""
    antwort = _anlegen(client, album_name="Doppelt", group_id="gruppe-2")

    assert antwort.status_code == 200, antwort.text
    assert _gruppe_von(client, "manual_testname_konto-1") == "gruppe-2"


# ----------------------------------------------------------------------
# #119: der Client schickt mit, was er ANGEZEIGT hat ("keine Gruppe") — der
# Server prueft das unter dem Schloss und lehnt ab, wenn es nicht mehr
# stimmt. #86 (zwei GLEICHZEITIGE Anlagen ohne jede Angabe -> eine Gruppe)
# bleibt ausdruecklich unberuehrt: Das Verhalten hier gilt nur, wenn der
# Client `expected_no_group` MITSCHICKT — die Proben zu #86 weiter oben tun
# das nicht und bleiben deshalb gruen (Rot-Beweis siehe Bericht).
# ----------------------------------------------------------------------


def test_119_erwartete_leere_lage_wird_beim_absenden_geprueft(client, ohne_immich):
    """Karte 1 legt vollstaendig an; Karte 2 zeigte "keine Gruppe" fuer
    denselben Namen und bestaetigt das mit `expected_no_group` — die Lage hat
    sich seither geaendert, also wird abgelehnt statt still beizutreten.

    Sequenziell durch die ECHTE HTTP-Tuer (das erzwungene Fenster fuer
    dieselbe Klasse steht unten, am Router direkt).
    """
    erste = _anlegen(client, canonical_name="Karte Eins", album_name="Kartenpaar",
                      expected_no_group=True)
    assert erste.status_code == 200, erste.text
    vorher = client.get("/api/sync/albums", headers=KOPF).json()

    zweite = _anlegen(client, canonical_name="Karte Zwei", album_name="Kartenpaar",
                       expected_no_group=True)

    assert zweite.status_code == 409, zweite.text
    assert zweite.json().get("error_key") == "err_group_situation_changed"
    nachher = client.get("/api/sync/albums", headers=KOPF).json()
    assert nachher == vorher, "die zweite Anlage darf nichts veraendert haben"


def test_119_gegenprobe_unveraenderte_lage_wird_angelegt(client, ohne_immich):
    """Gegenprobe: Bleibt die Lage tatsaechlich "keine Gruppe", wird angelegt."""
    antwort = _anlegen(client, canonical_name="Karte Solo", album_name="Ganz allein",
                        expected_no_group=True)

    assert antwort.status_code == 200, antwort.text
    assert _gruppe_von(client, "manual_karte_solo_konto-1") is not None


def test_119_ohne_das_feld_bleibt_das_alte_verhalten_bestehen(client, ohne_immich):
    """Ohne `expected_no_group` (Vorgabe: aus) bleibt der stille Beitritt
    bestehen — dieselbe Klasse wie #86, hier fuer den EINDEUTIGEN Fall (nicht
    das gleichzeitige `asyncio.gather`, sondern zwei sequenzielle Anfragen
    ohne das neue Feld).
    """
    erste = _anlegen(client, canonical_name="Karte A", album_name="Ohne Angabe")
    assert erste.status_code == 200, erste.text

    zweite = _anlegen(client, canonical_name="Karte B", album_name="Ohne Angabe")

    assert zweite.status_code == 200, zweite.text
    assert _gruppe_von(client, "manual_karte_a_konto-1") == _gruppe_von(
        client, "manual_karte_b_konto-1"
    ), "beide muessen in DERSELBEN Gruppe landen wie vor #119"


@pytest.mark.asyncio
async def test_119_erzwungenes_fenster_lehnt_nach_der_ersten_anlage_ab(tmp_path, monkeypatch):
    """#119 mit ERZWUNGENEM Fenster, nicht mit Glueck (`lehren.md`, Nebenlaeufigkeit).

    Anders als die HTTP-Probe oben (rein sequenziell) haelt dieser Test die
    ERSTE Anfrage bewusst MITTEN im Namensschloss an (`asyncio.Event`),
    startet dann die ZWEITE — die also auf DASSELBE Schloss trifft, waehrend
    die erste es noch haelt — und laesst die erste erst danach fertigwerden.
    Das beweist, dass die Pruefung wirklich FRISCH unter dem Schloss liest,
    nicht aus einem Schnappschuss von VOR dem Warten auf das Schloss.
    """
    import asyncio
    import json as _json

    from errors import AppError
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
            if name == "Kartenpaar":
                # Haelt das Namensschloss fuer "Kartenpaar" fest, waehrend die
                # zweite Anfrage bereits darauf wartet.
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

    def anfrage(canonical_name):
        return SyncNamesMultiRequest(
            persons=[MultiSyncPersonEntry(account_id="konto-1", person_id="p1"),
                     MultiSyncPersonEntry(account_id="konto-2", person_id="p2")],
            canonical_name=canonical_name,
            album_name="Kartenpaar",
            owner_account_id="konto-1",
            expected_no_group=True,
        )

    erste = asyncio.create_task(albums_router.sync_names_multi(anfrage("Karte Eins"), request))
    await drin.wait()   # "Karte Eins" haelt das Schloss, mitten im Immich-Aufruf.

    zweite = asyncio.create_task(albums_router.sync_names_multi(anfrage("Karte Zwei"), request))
    # Zwei Runden statt einer, aus Sicherheitsabstand: "Karte Zwei" soll bis
    # zum Schloss-Erwerb laufen (ihr eigener Preflight hat keine echten
    # Wartepunkte), nicht nur einmal angestossen werden.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert store.gruppen_schloss("Kartenpaar").locked(), (
        "das Schloss muss zu diesem Zeitpunkt noch von Karte Eins gehalten werden"
    )

    weiter.set()   # "Karte Eins" darf fertigwerden und das Schloss freigeben.
    await erste

    with pytest.raises(AppError) as exc_info:
        await zweite
    assert exc_info.value.key == "err_group_situation_changed"

    alben = store.get_managed_albums()
    assert len(alben) == 1, "nur Karte Eins darf angelegt haben"
    assert alben[0].match_id == "manual_karte_eins_konto-1"
