"""Tuer-Probe (R3) fuer #99/#112 — vom Hauptagenten gefahren.

Ein echter Ablauf ueber die HTTP-Endpunkte (TestClient), genau die Kette aus
dem Bau-Brief: Konto loeschen -> Liste -> Umbenennen -> Refresh -> Rueckgaengig.

Diese Datei ist die Vorbereitung fuer die Tuer-Probe, nicht ihr Ersatz — sie
laeuft in der normalen Suite mit und haelt den Ablauf fest, den der
Hauptagent als R3-Probe nachvollzieht.

Alle Daten erfunden; das Repo ist oeffentlich.
"""
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

BESITZER = {"id": "besitzer", "name": "Besitzer",
            "immich_url": "http://besitzer.invalid", "api_key": "platzhalter",
            "color": "#111111", "user_id": "u-besitzer"}
TEILNEHMER = {"id": "teilnehmer", "name": "Teilnehmer",
              "immich_url": "http://teilnehmer.invalid", "api_key": "platzhalter",
              "color": "#222222", "user_id": "u-teilnehmer"}

ALBUM = {
    "id": "album-1", "match_id": "m-album-1", "album_id": "immich-album-1",
    "album_name": "Familienalbum", "group_id": "gruppe-1",
    "owner_account_id": "besitzer",
    "person_refs": [
        {"account_id": "besitzer", "person_id": "p-besitzer",
         "person_name": "Person Besitzer", "account_name": "Besitzer",
         "account_color": "#111111"},
        {"account_id": "teilnehmer", "person_id": "p-teilnehmer",
         "person_name": "Person Teilnehmer", "account_name": "Teilnehmer",
         "account_color": "#222222"},
    ],
    "linked_match_ids": [],
    "created_at": "2026-01-01T00:00:00+00:00",
}

# Ein rueckgaengig-faehiger Protokolleintrag, dessen undo_data auf den
# BESITZER zeigt — genau die Stelle, die nach dem Loeschen gesperrt sein muss.
#
# Zeitstempel bewusst "jetzt", nicht fest in der Vergangenheit: Die
# Aufbewahrung (`ConfigStore._apply_log_retention`, 90 Tage) wuerde einen
# festen alten Zeitstempel beim naechsten `append_log` (Schritt 4, Refresh)
# aus dem Verlauf entfernen — das waere Aufbewahrung, keine Aussage ueber
# das Loeschen eines Kontos.
LOG_EINTRAG = {
    "id": "log-undo-1", "timestamp": datetime.now(timezone.utc).isoformat(),
    "action": "sync_names", "details": "Name synchronisiert",
    "status": "success",
    "undo_data": {"account_id": "besitzer", "person_id": "p-besitzer",
                  "previous_name": "Alt"},
}


def _bestand(tmp_path):
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {"besitzer": BESITZER, "teilnehmer": TEILNEHMER},
        "schema_version": 3,
        "managed_albums": [ALBUM],
        "sync_log": [LOG_EINTRAG],
    }), encoding="utf-8")
    return pfad


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Echte HTTP-Tuer, echter Store — nur Immich ist eine Attrappe."""
    import main
    from services import sync_service

    pfad = _bestand(tmp_path)
    monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test", raising=False)
    monkeypatch.setattr(main.settings, "config_path", pfad, raising=False)

    class ImmichAttrappe:
        def __init__(self, *_a, **_k):
            pass

        async def update_album(self, album_id, payload):
            return {"id": album_id, **payload}

        async def update_person(self, person_id, payload):
            return {"id": person_id, **payload}

    monkeypatch.setattr(sync_service, "ImmichClient", ImmichAttrappe)

    with TestClient(main.app) as c:
        c.post("/api/auth/login", json={"token": "nur-fuer-den-test"})
        yield c


def test_konto_loeschen_liste_umbenennen_refresh_rueckgaengig(client):
    """Die volle Kette aus dem Bau-Brief, ueber die echten Endpunkte."""

    # 1) Konto loeschen
    antwort = client.delete("/api/accounts/besitzer")
    assert antwort.status_code == 204, antwort.text

    # 2) Liste — das Album traegt die Markierung, mit lebendem Konto nicht
    alben = client.get("/api/sync/albums").json()
    album = next(a for a in alben if a["id"] == "album-1")
    assert album["owner_account_missing"] is True, album
    # Der Besitzer war einer von zwei `person_refs` — nach dem Loeschen
    # bleibt nur der Teilnehmer, also "zu wenige Personen" zusaetzlich.
    assert album["too_few_people"] is True, album

    # 3) Umbenennen — abgelehnt mit Grund, nichts geschrieben
    antwort = client.patch("/api/sync/albums/album-1", json={"album_name": "Neuer Name"})
    assert antwort.status_code == 404, antwort.text
    assert antwort.json().get("error_key") == "err_owner_account_not_found"
    unveraendert = next(a for a in client.get("/api/sync/albums").json() if a["id"] == "album-1")
    assert unveraendert["album_name"] == "Familienalbum"

    # 4) Refresh (manueller Abgleich) — meldet den Grund, wirft keinen Fehler
    antwort = client.post("/api/sync/album/album-1/refresh")
    assert antwort.status_code == 200, antwort.text
    eintraege = antwort.json()
    assert [e["status"] for e in eintraege] == ["error"], eintraege
    assert eintraege[0]["message_key"] == "log_owner_account_missing"

    # 5) Rueckgaengig — der Server lehnt ab, das Konto ist weg; der Eintrag
    #    selbst ist NICHT verschwunden (siehe Schritt vorher: er blieb im
    #    Protokoll stehen, obwohl `undo_data.account_id` auf das geloeschte
    #    Konto zeigt).
    verlauf = client.get("/api/sync/log").json()
    assert any(e["id"] == "log-undo-1" for e in verlauf), verlauf
    antwort = client.post("/api/sync/undo", json={"log_entry_id": "log-undo-1"})
    assert antwort.status_code == 404, antwort.text
    assert antwort.json().get("error_key") == "err_account_gone"
