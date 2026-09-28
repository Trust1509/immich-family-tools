"""Die Fehlerwege des Umbenennens — gemessen, nicht angenommen (#79).

Der Gegenpruefer hat an der zugelieferten Fassung 20 Mutationen der neuen
Mechanik mit vollstaendig gruenem Baum ueberlebt. Die schwersten betrafen nicht
den Erfolgsfall, sondern alles daneben:

* `status="error"` im Immich-Fehlerzweig auf `"success"` gedreht → 215 gruen.
  Ein Fehlschlag haette sich als Erfolg protokolliert.
* Den Schnappschuss VOR dem Immich-Aufruf schreiben → 215 gruen. Die App
  haette den neuen Namen gezeigt, Immich den alten.
* `store.append_log(logs)` entfernt → 215 gruen. Das Umbenennen waere nie im
  Protokollverlauf erschienen.
* Die Ablehnung des leeren Namens und das `.strip()` entfernt → 215 gruen. Ein
  Album haette auf „“ umbenannt werden koennen, und `_name_key("   ")` ist
  leer: Die Gruppe verliert damit ihren Namen.
* Die Besitzerpruefung entfernt → aus 404 wird ein AttributeError.
* Im Client `raise_for_status()` bzw. die 404-Abbildung entfernt → die
  Fehlerbehandlung des neuen Aufrufs war ungeprueft.

Diese Datei schliesst jede dieser Luecken mit einer eigenen Zusicherung. Der
Grundsatz dahinter: Ein ueberlebender Mutant heisst meist, dass die MESSUNG zu
eng war — hier war sie auf den Erfolgsfall eingeengt.
"""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from services.immich_client import AlbumNotFoundError, ImmichClient

KONTO = {"id": "konto-1", "name": "Konto Eins",
         "immich_url": "http://beispiel.invalid", "api_key": "platzhalter",
         "color": "#111111", "user_id": "u1"}


def _album(album_id, name, gruppe, besitzer="konto-1"):
    return {"id": album_id, "match_id": "m-" + album_id,
            "album_id": "immich-" + album_id, "album_name": name,
            "group_id": gruppe, "owner_account_id": besitzer,
            "person_refs": [], "linked_match_ids": [],
            "created_at": "2026-01-01T00:00:00+00:00"}


def _bestand(tmp_path, alben):
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({"accounts": {"konto-1": KONTO},
                                "schema_version": 3, "managed_albums": alben}),
                    encoding="utf-8")
    return pfad


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Echte HTTP-Tuer, echter Store — nur Immich ist eine Attrappe."""
    import main
    from services import sync_service

    pfad = _bestand(tmp_path, [
        _album("a1", "Straßenfest", "gruppe-1"),
        _album("a2", "Waisenalbum", "gruppe-2", besitzer="konto-verschwunden"),
    ])
    monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test", raising=False)
    monkeypatch.setattr(main.settings, "config_path", pfad, raising=False)

    class ImmichAttrappe:
        """Immich, das tut, was `verhalten` sagt."""

        verhalten = "erfolg"

        def __init__(self, *_a, **_k):
            pass

        async def update_album(self, album_id, payload):
            if ImmichAttrappe.verhalten == "geloescht":
                raise AlbumNotFoundError(album_id)
            if ImmichAttrappe.verhalten == "kaputt":
                raise RuntimeError("Immich antwortet nicht")
            return {"id": album_id, **payload}

    ImmichAttrappe.verhalten = "erfolg"
    monkeypatch.setattr(sync_service, "ImmichClient", ImmichAttrappe)

    with TestClient(main.app) as c:
        c.post("/api/auth/login", json={"token": "nur-fuer-den-test"})
        c.immich = ImmichAttrappe
        yield c


def _name_im_bestand(client, album_id):
    alben = client.get("/api/sync/albums").json()
    return next(a["album_name"] for a in alben if a["id"] == album_id)


# --------------------------------------------------- Immich schlaegt fehl

def test_ein_fehlschlag_wird_als_fehler_protokolliert(client):
    """Nicht als Erfolg. Genau diese Mutation ueberlebte 215 Proben."""
    client.immich.verhalten = "kaputt"
    antwort = client.patch("/api/sync/albums/a1", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 200, antwort.text
    eintraege = antwort.json()
    assert [e["status"] for e in eintraege] == ["error"], eintraege
    assert eintraege[0]["message_key"] == "log_album_rename_failed"
    assert eintraege[0]["error_message"] == "IMMICH_API_ERROR"


def test_nach_einem_fehlschlag_bleibt_der_alte_name_im_bestand(client):
    """Der Schnappschuss darf NICHT vor dem Immich-Aufruf geschrieben werden.

    Sonst zeigt die App den neuen Namen, waehrend Immich den alten traegt —
    und niemand merkt es, weil das Protokoll von einem Fehler spricht, den der
    Bestand nicht widerspiegelt.
    """
    client.immich.verhalten = "kaputt"
    client.patch("/api/sync/albums/a1", json={"album_name": "Herbstfest"})
    assert _name_im_bestand(client, "a1") == "Straßenfest"


def test_ein_in_immich_geloeschtes_album_meldet_sich_als_geloescht(client):
    """Eigener Zweig, eigene Kennung — die Karte zeigt daran ihr Banner."""
    client.immich.verhalten = "geloescht"
    eintraege = client.patch("/api/sync/albums/a1",
                             json={"album_name": "Herbstfest"}).json()
    assert eintraege[0]["error_message"] == "ALBUM_DELETED", eintraege
    assert eintraege[0]["message_key"] == "log_album_not_found"
    assert _name_im_bestand(client, "a1") == "Straßenfest"


# --------------------------------------------------- Erfolg, vollstaendig

def test_der_erfolg_landet_im_protokollverlauf(client):
    """`append_log` entfernt → 215 gruen. Das Umbenennen war unsichtbar.

    Gemessen am VERLAUF, nicht an der Antwort: Die Antwort trug den Eintrag
    auch vorher.
    """
    client.patch("/api/sync/albums/a1", json={"album_name": "Herbstfest"})
    verlauf = client.get("/api/sync/log").json()
    passend = [e for e in verlauf if e.get("action") == "rename_album"]
    assert passend, verlauf[-3:]
    assert passend[-1]["message_params"] == {"old_name": "Straßenfest",
                                             "new_name": "Herbstfest"}


def test_der_erfolg_aendert_den_bestand(client):
    client.patch("/api/sync/albums/a1", json={"album_name": "Herbstfest"})
    assert _name_im_bestand(client, "a1") == "Herbstfest"


# --------------------------------------------------- Eingaben, die ablehnen

@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_ein_leerer_name_wird_abgelehnt(client, name):
    """Ohne `.strip()` verliert die Gruppe ihren Namen.

    `_name_key("   ")` ist leer — ein Album mit Leerraum-Namen ist fuer die
    Zuordnung namenlos und taucht in keiner Gruppenvorschau mehr auf. Deshalb
    zaehlt hier der Nur-Leerraum-Fall, nicht nur der leere String.
    """
    antwort = client.patch("/api/sync/albums/a1", json={"album_name": name})
    assert antwort.status_code == 422, antwort.text
    assert antwort.json().get("error_key") == "err_album_name_required"
    assert _name_im_bestand(client, "a1") == "Straßenfest"


def test_ein_unbekanntes_album_wird_abgelehnt(client):
    antwort = client.patch("/api/sync/albums/gibtsnicht",
                           json={"album_name": "Herbstfest"})
    assert antwort.status_code == 404, antwort.text
    assert antwort.json().get("error_key") == "err_managed_album_not_found"


def test_ein_verschwundenes_besitzerkonto_wird_abgelehnt(client):
    """Kein AttributeError, sondern eine Meldung mit Schluessel.

    Der Zustand ist nicht konstruiert: `delete_account` behaelt seit #99/#112
    JEDES Album, unabhaengig von der Zahl verbliebener Personen, und raeumt
    `owner_account_id` NICHT auf (Owner-Entscheid 28.09.2026: markieren,
    nicht umschreiben). Ein gewoehnliches Loeschen des Besitzerkontos erzeugt
    diesen Zustand also immer.
    """
    antwort = client.patch("/api/sync/albums/a2", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 404, antwort.text
    assert antwort.json().get("error_key") == "err_owner_account_not_found"
    assert _name_im_bestand(client, "a2") == "Waisenalbum"


# --------------------------------------------------- Der Client selbst

@pytest.mark.asyncio
async def test_der_client_macht_aus_404_ein_geloeschtes_album():
    def antworte(_anfrage: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not found"})

    client = ImmichClient("http://immich.test", "api-key",
                          transport=httpx.MockTransport(antworte))
    with pytest.raises(AlbumNotFoundError):
        await client.update_album("album-1", {"albumName": "Neu"})


@pytest.mark.asyncio
async def test_der_client_verschweigt_keinen_serverfehler():
    """Ohne `raise_for_status()` kaeme eine 500 als Erfolg zurueck."""
    def antworte(_anfrage: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "kaputt"})

    client = ImmichClient("http://immich.test", "api-key",
                          transport=httpx.MockTransport(antworte))
    with pytest.raises(httpx.HTTPStatusError):
        await client.update_album("album-1", {"albumName": "Neu"})
