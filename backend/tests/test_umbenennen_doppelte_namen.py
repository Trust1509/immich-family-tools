"""Umbenennen lehnt nie mehr wegen eines Namens ab (Owner-Entscheid 28.09.2026, #98).

Zwei verschiedene Albumgruppen duerfen seither denselben Namen tragen. Die
Kollisionspruefung, die das bis hierher verhindert hat
(`ConfigStore.namen_mit_anderer_antwort`, Meldung `errors.album_name_in_use`,
Namensschloss `store.gruppen_schloss` in der Umbenenn-Route), ist entfernt —
samt ihren Proben in `test_umbenennen_kollision.py` (Datei geloescht) und den
Faellen in `test_umbenennen_gruppe.py` und `test_umbenennen_schloss.py`, die
eine Ablehnung erwarteten. Diese Datei haelt das neue, gewollte Verhalten fest:
ein Umbenennen auf den Namen einer FREMDEN Gruppe gelingt.

DURCH DIE ECHTE HTTP-TUER, mit einer schreibenden Attrappe fuer den
Sync-Dienst — wie in `test_umbenennen_gruppe.py`, aus demselben Grund: Eine
zaehlende Attrappe sieht nicht, was der erste Aufruf im Bestand angerichtet
hat, und genau das ist hier der Punkt.
"""
import json

import pytest
from fastapi.testclient import TestClient

KONTO = {"id": "konto-1", "name": "Konto Eins",
         "immich_url": "http://beispiel.invalid", "api_key": "platzhalter",
         "color": "#111111", "user_id": "u1"}


def _album(album_id, name, gruppe):
    return {"id": album_id, "match_id": "m-" + album_id,
            "album_id": "immich-" + album_id, "album_name": name,
            "group_id": gruppe, "owner_account_id": "konto-1",
            "person_refs": [], "linked_match_ids": [],
            "created_at": "2026-01-01T00:00:00+00:00"}


@pytest.fixture
def mit_bestand(tmp_path, monkeypatch):
    """Baut eine Anwendung mit dem übergebenen Bestand und schreibendem Immich.

    Dieselbe Form wie in `test_umbenennen_gruppe.py` — bewusst nicht geteilt,
    damit diese Datei ohne Blick in die andere lesbar bleibt.
    """
    def bauen(alben):
        import main
        from services import sync_service

        pfad = tmp_path / "accounts.json"
        pfad.write_text(json.dumps({"accounts": {"konto-1": KONTO},
                                    "schema_version": 3, "managed_albums": alben}),
                        encoding="utf-8")
        monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test", raising=False)
        monkeypatch.setattr(main.settings, "config_path", pfad, raising=False)

        async def umbenennen(managed, _owner, neuer_name, store):
            managed.album_name = neuer_name
            store.update_managed_album(managed)
            return []

        monkeypatch.setattr(sync_service, "rename_managed_album", umbenennen)
        c = TestClient(main.app)
        c.__enter__()
        c.post("/api/auth/login", json={"token": "nur-fuer-den-test"})
        return c

    yield bauen


def _gruppen(client):
    return {a["id"]: a["group_id"] for a in client.get("/api/sync/albums").json()}


def test_ein_umbenennen_auf_den_namen_einer_fremden_gruppe_gelingt(mit_bestand):
    """Der Fall, den die entfernte Pruefung bis #98 mit 409 abgelehnt hat.

    `gruppe-1` traegt „Sommerfest", `gruppe-2` „Herbstfest". Ihr Album aus
    `gruppe-1` auf „Herbstfest" umzubenennen erzeugt zwei Gruppen mit demselben
    Namen — genau das erlaubt #98 jetzt ausdruecklich.
    """
    c = mit_bestand([_album("a1", "Sommerfest", "gruppe-1"),
                     _album("a2", "Herbstfest", "gruppe-2")])

    antwort = c.patch("/api/sync/albums/a1", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 200, antwort.text

    # Beide Gruppen tragen danach den Namen ...
    alben = c.get("/api/sync/albums").json()
    namen = {a["id"]: a["album_name"] for a in alben}
    assert namen == {"a1": "Herbstfest", "a2": "Herbstfest"}, namen

    # ... und keine Gruppenkennung hat sich veraendert: Das Umbenennen aendert
    # den Namen, nicht die Zugehoerigkeit.
    assert _gruppen(c) == {"a1": "gruppe-1", "a2": "gruppe-2"}, _gruppen(c)


def test_die_gruppenvorschau_verstummt_fuer_den_jetzt_doppelten_namen(mit_bestand):
    """Die Kehrseite, ausdruecklich hingenommen (Befund im Bau-Brief zu #98).

    Zwei Gruppen mit demselben Namen sind fuer `existing_group_for_name`
    nicht mehr unterscheidbar (#78) — die Vorschau antwortet fuer diesen
    Namen mit `null`, genau wie bei jedem anderen mehrdeutigen Namen.
    """
    c = mit_bestand([_album("a1", "Sommerfest", "gruppe-1"),
                     _album("a2", "Herbstfest", "gruppe-2")])

    # Vorher ist "Herbstfest" eindeutig gruppe-2.
    vorher = c.get("/api/sync/album-group", params={"album_name": "Herbstfest"}).json()
    assert vorher and vorher["group_id"] == "gruppe-2", vorher

    antwort = c.patch("/api/sync/albums/a1", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 200, antwort.text

    nachher = c.get("/api/sync/album-group", params={"album_name": "Herbstfest"}).json()
    assert nachher is None, nachher
