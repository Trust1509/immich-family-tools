"""Umbenennen darf keine zweite Gruppe mit demselben Namen erzeugen (#79).

Auflage aus dem Review des zugelieferten Zweigs. Ohne diese Pruefung
verschmilzt ein Umbenennen zwei Gruppen **dem Auge nach**, ohne sie zu
verschmelzen: Beide tragen danach denselben Namen, und
`existing_group_for_name` antwortet fuer BEIDE mit „keine Gruppe" (#78). Der
Nutzer sieht zwei Karten mit gleichem Namen und bekommt beim naechsten
Anlegen keine Gruppenvorschau mehr.

DIE PRUEFUNG BENUTZT DIE ZUORDNUNG SELBST — sie vergleicht `Name -> Gruppe`
vor und nach dem Vorgang (`ConfigStore.namen_mit_anderer_antwort`). Seit #83
ist das keine Formalie: Mit einem `==` auf dem Namen haette sie
„Strassenfest" gegen „Straßenfest" durchgelassen, obwohl das heute derselbe
Name ist. Genau dieser Fall steht unten.

Was die Pruefung NICHT tut, seit der dritten Nacharbeit: eine Mehrdeutigkeit
ablehnen, die schon da war und kleiner wird. Diese Faelle stehen in
`test_umbenennen_gruppe.py`.

Die Ablehnung steht VOR dem ersten Schreibvorgang — sonst waere sie die
Klasse, die diese Datei dreimal getroffen hat: ein Fehler, der sich als
Eingabefehler ausgibt, nachdem in Immich schon umbenannt wurde.
"""
import json

import pytest
from fastapi.testclient import TestClient

import errors


def _bestand(tmp_path, alben):
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {
            "konto-1": {"id": "konto-1", "name": "Konto Eins",
                        "immich_url": "http://beispiel.invalid",
                        "api_key": "platzhalter", "color": "#111111",
                        "user_id": "u1"},
        },
        "schema_version": 3,
        "managed_albums": alben,
    }), encoding="utf-8")
    return pfad


def _album(album_id, name, gruppe):
    return {"id": album_id, "match_id": "m-" + album_id,
            "album_id": "immich-" + album_id, "album_name": name,
            "group_id": gruppe, "owner_account_id": "konto-1",
            "person_refs": [], "linked_match_ids": [],
            "created_at": "2026-01-01T00:00:00+00:00"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from services import sync_service

    pfad = _bestand(tmp_path, [
        _album("a1", "Straßenfest", "gruppe-1"),
        _album("a2", "Sommerfest", "gruppe-2"),
    ])
    import main

    monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test", raising=False)
    monkeypatch.setattr(main.settings, "config_path", pfad, raising=False)

    # Ein Umbenennen, das MITZAEHLT statt zu schreiben: So faellt auf, wenn
    # eine Ablehnung erst NACH dem Schreibvorgang kommt.
    geschrieben = []

    async def zaehlendes_umbenennen(managed, owner, neuer_name, store):
        geschrieben.append((managed.id, neuer_name))
        return []

    monkeypatch.setattr(sync_service, "rename_managed_album", zaehlendes_umbenennen)

    # `with`, nicht der nackte Konstruktor: Ohne den Kontext laeuft das
    # Startereignis nicht, und `app.state.settings` fehlt.
    with TestClient(main.app) as c:
        c.post("/api/auth/login", json={"token": "nur-fuer-den-test"})
        c.geschrieben = geschrieben
        yield c


def test_umbenennen_auf_einen_fremden_namen_wird_abgelehnt(client):
    antwort = client.patch("/api/sync/albums/a1",
                           json={"album_name": "Sommerfest"})
    assert antwort.status_code == 409, antwort.text
    assert antwort.json().get("error_key") == "err_album_name_in_use", antwort.text
    # UND es wurde nichts geschrieben.
    assert client.geschrieben == [], client.geschrieben


def test_die_pruefung_benutzt_die_faltung_nicht_einen_zeichenvergleich(client):
    """Der Fall, den ein `==` durchgelassen haette.

    „Strassenfest" und „Straßenfest" sind seit #83 derselbe Name. Wer die
    Gruppe „Sommerfest" so umbenennt, erzeugt die Mehrdeutigkeit, die die
    Pruefung verhindern soll.
    """
    antwort = client.patch("/api/sync/albums/a2",
                           json={"album_name": "Strassenfest"})
    assert antwort.status_code == 409, antwort.text
    assert antwort.json().get("error_key") == "err_album_name_in_use"
    assert client.geschrieben == []


def test_umbenennen_innerhalb_der_eigenen_gruppe_bleibt_erlaubt(client):
    """Die Oberflaeche benennt alle Alben einer Gruppe EINZELN um.

    Das zweite Album sieht dabei den neuen Namen des ersten. Wuerde die
    eigene Gruppe nicht ausgenommen, koennte eine Gruppe mit zwei Alben nie
    umbenannt werden — die Pruefung haette die Funktion abgeschafft, die sie
    schuetzen soll.
    """
    antwort = client.patch("/api/sync/albums/a1",
                           json={"album_name": "Straßenfest"})
    assert antwort.status_code == 200, antwort.text
    assert client.geschrieben == [("a1", "Straßenfest")]


def test_ein_freier_name_wird_umbenannt(client):
    antwort = client.patch("/api/sync/albums/a1",
                           json={"album_name": "Herbstfest"})
    assert antwort.status_code == 200, antwort.text
    assert client.geschrieben == [("a1", "Herbstfest")]


def test_die_ablehnung_traegt_den_namen_als_parameter(client):
    antwort = client.patch("/api/sync/albums/a1",
                           json={"album_name": "Sommerfest"})
    assert antwort.json().get("error_params") == {"album": "Sommerfest"}, antwort.text
    # Und der deutsche Rueckfall steht daneben, wie bei jeder Meldung.
    assert "Sommerfest" in antwort.json().get("detail", "")


# ---------------------------------------------------------------------------
# Der Bestand, fuer den die ZWEITE Faltungsstufe aus #83 ueberhaupt existiert:
# zwei Schreibweisen desselben Namens in ZWEI Gruppen. Die heutige Faltung zieht
# sie zusammen (`casefold` macht aus „ß" ein „ss"), die alte hielt sie
# auseinander — deshalb antwortet die Gruppenvorschau hier noch.
#
# Gefunden vom Blindpruefer an #79: In diesem Bestand konnte eine Gruppe die
# Grossschreibung ihres EIGENEN Namens nicht mehr aendern.
# ---------------------------------------------------------------------------


@pytest.fixture
def client_zwei_schreibweisen(tmp_path, monkeypatch):
    from services import sync_service

    pfad = _bestand(tmp_path, [
        _album("a1", "Straßenfest", "gruppe-1"),
        _album("a2", "Strassenfest", "gruppe-2"),
    ])
    import main

    monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test", raising=False)
    monkeypatch.setattr(main.settings, "config_path", pfad, raising=False)

    geschrieben = []

    async def zaehlendes_umbenennen(managed, owner, neuer_name, store):
        geschrieben.append((managed.id, neuer_name))
        return []

    monkeypatch.setattr(sync_service, "rename_managed_album", zaehlendes_umbenennen)

    with TestClient(main.app) as c:
        c.post("/api/auth/login", json={"token": "nur-fuer-den-test"})
        c.geschrieben = geschrieben
        yield c


def test_die_eigene_schreibweise_darf_sich_aendern(client_zwei_schreibweisen):
    """Grossschreibung des eigenen Namens: Die Mehrdeutigkeit bleibt, wie sie war.

    Beide Faltungen sehen „Strassenfest" und „STRASSENFEST" als denselben
    Namen. Es entsteht keine neue Kollision — also darf die Ablehnung nicht
    kommen, und ihre Meldung („gehört bereits zu einer anderen Gruppe") waere
    hier schlicht falsch.
    """
    c = client_zwei_schreibweisen
    antwort = c.patch("/api/sync/albums/a2", json={"album_name": "STRASSENFEST"})
    assert antwort.status_code == 200, antwort.text
    assert c.geschrieben == [("a2", "STRASSENFEST")]


def test_die_schreibweise_der_anderen_gruppe_bleibt_verboten(client_zwei_schreibweisen):
    """Die Gegenprobe — und der Grund, warum BEIDE Faltungen gefragt werden.

    „Strassenfest" in „Straßenfest" zu aendern laesst die heutige Faltung
    unberuehrt: Sie zog die beiden ohnehin zusammen. Aber die zweite Stufe, die
    sie bisher auseinanderhielt, kollidiert danach — die Gruppenvorschau
    verstummt fuer BEIDE Gruppen. Das ist eine neue Mehrdeutigkeit.
    """
    c = client_zwei_schreibweisen
    antwort = c.patch("/api/sync/albums/a2", json={"album_name": "Straßenfest"})
    assert antwort.status_code == 409, antwort.text
    assert antwort.json().get("error_key") == "err_album_name_in_use"
    assert c.geschrieben == []


def test_die_ablehnung_gilt_auch_in_der_anderen_richtung(client_zwei_schreibweisen):
    """Dieselbe Sperre von der Gegenseite — die Ausnahme schafft nichts ab.

    Ohne diesen Fall waere „immer erlauben, sobald ueberhaupt eine Kollision
    besteht" die billigste Antwort auf den Fund des Blindpruefers: Sie haette
    beide Tests darueber gruen gelassen und die Pruefung in diesem Bestand
    vollstaendig ausgeschaltet.
    """
    c = client_zwei_schreibweisen
    antwort = c.patch("/api/sync/albums/a1", json={"album_name": "Strassenfest"})
    assert antwort.status_code == 409, antwort.text
    assert c.geschrieben == []


def test_die_fabrik_gibt_409_und_den_schluessel():
    fehler = errors.album_name_in_use("X")
    assert fehler.status_code == 409
    assert fehler.key == "err_album_name_in_use"
