"""Umbenennen lehnt nie mehr wegen eines Namens ab (Owner-Entscheid 28.09.2026, #98).

Zwei verschiedene Albumgruppen duerfen seither denselben Namen tragen. Die
Kollisionspruefung, die das bis hierher verhindert hat
(`ConfigStore.namen_mit_anderer_antwort`, Meldung `errors.album_name_in_use`,
Namensschloss `store.gruppen_schloss` in der Umbenenn-Route), ist entfernt —
samt ihren eigenen Proben (Testdatei geloescht, siehe CHANGELOG 1.9.0) und den
Faellen in `test_umbenennen_gruppe.py` und `test_umbenennen_schloss.py`, die
eine Ablehnung erwarteten. Diese Datei haelt das neue, gewollte Verhalten fest:
ein Umbenennen auf den Namen einer FREMDEN Gruppe gelingt.

DURCH DIE ECHTE HTTP-TUER, mit dem ECHTEN `sync_service` und dem ECHTEN
`ConfigStore` — nur `ImmichClient` ist eine Attrappe (kein echter HTTP-Aufruf
gegen eine Immich-Instanz). Das ist eine Nacharbeit an der ersten Fassung
dieser Datei: Sie hatte `sync_service.rename_managed_album` KOMPLETT durch
eine schreibende Attrappe ersetzt. Blind- und Fremdpruefer haben unabhaengig
voneinander dieselbe Luecke gefunden: Eine Ablehnung, die NICHT im Router
steht, sondern eine Ebene tiefer im echten Dienst (etwa in
`_rename_managed_album_unlocked`), waere durch diese Attrappe nie gelaufen —
die Datei waere gruen geblieben, und mit ihr die ganze Suite (242 von 242,
nachgemessen). Jetzt laeuft der echte Weg bis zum Netzwerk-Rand: Router ->
`sync_service.rename_managed_album` -> `_rename_managed_album_unlocked`.
NUR `ImmichClient.update_album` ist Attrappe, danach schreibt der echte
`ConfigStore.update_managed_album` in die Wegwerf-`accounts.json` — ein
`raise` im ECHTEN `ImmichClient.update_album` selbst wuerde diese Datei NICHT
erreichen, das ist der bewusste Rand der Attrappe, kein Versehen. Eine
Ablehnung an jeder Stelle VOR diesem Rand (Router, `rename_managed_album`,
`_rename_managed_album_unlocked`) wird jetzt rot, nicht nur eine im Router —
gemessen mit zwei Rot-Beweisen in Nacharbeit 1.
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


class _ImmichAttrappe:
    """Ersetzt nur den Netzwerk-Rand: kein HTTP, sonst nichts Eigenes.

    Fuer `_rename_managed_album_unlocked` reicht `update_album` — die Funktion
    ruft weder `get_album_assets` noch `add_assets_to_album` noch teilt sie
    ein Album. Ein Attribut mehr, als der Aufrufer braucht, waere hier schon
    eine unbelegte Behauptung ueber den Dienst.
    """

    def __init__(self, *_a, **_k):
        pass

    async def update_album(self, album_id, payload):
        return {"id": album_id, **payload}


@pytest.fixture
def mit_bestand(tmp_path, monkeypatch):
    """Baut eine Anwendung mit dem übergebenen Bestand, echtem Sync-Dienst und
    echtem ConfigStore — nur `ImmichClient` ist eine Attrappe.
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
        monkeypatch.setattr(sync_service, "ImmichClient", _ImmichAttrappe)

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
    nicht mehr unterscheidbar (#78) — `resolve_group_id`/`group_id_for_name`
    (die Wege, die WIRKLICH etwas anlegen) sehen fuer diesen Namen weiterhin
    keinen eindeutigen Treffer.

    NACHTRAG #113 (29.09.2026): Die VORSCHAU selbst "verstummt" seit #113
    nicht mehr — sie kollabiert Mehrdeutigkeit nicht laenger auf `null`
    (ununterscheidbar von "kein Treffer"), sondern zeigt `status: "many"`
    mit BEIDEN Kandidaten, genau damit ein Nutzer hier explizit waehlen
    kann statt im Dunkeln zu stehen. Der Testname und die erste Haelfte des
    Docstrings sind bewusst NICHT umgeschrieben (`docs/agents/lehren.md`,
    "Ein Widerspruch über zwei Dateien" — dokumentierende Aussage, datierter
    Nachtrag statt Korrektur); die Pruefung unten folgt der neuen Form.
    """
    c = mit_bestand([_album("a1", "Sommerfest", "gruppe-1"),
                     _album("a2", "Herbstfest", "gruppe-2")])

    # Vorher ist "Herbstfest" eindeutig gruppe-2.
    vorher = c.get("/api/sync/album-group", params={"album_name": "Herbstfest"}).json()
    assert vorher and vorher["group_id"] == "gruppe-2", vorher

    antwort = c.patch("/api/sync/albums/a1", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 200, antwort.text

    nachher = c.get("/api/sync/album-group", params={"album_name": "Herbstfest"}).json()
    assert nachher["status"] == "many", nachher
    assert {k["group_id"] for k in nachher["candidates"]} == {"gruppe-1", "gruppe-2"}, nachher
