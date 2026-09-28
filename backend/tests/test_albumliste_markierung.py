"""`GET /api/sync/albums` markiert verwaiste/knappe Alben, ohne zu schreiben.

#99/#112, Owner-Entscheid 28.09.2026: Die Markierung wird aus dem AKTUELLEN
Kontenbestand berechnet, bei jedem Aufruf neu — nicht gespeichert, keine
Schema-Aenderung von `accounts.json`. Diese Datei prueft beide Haelften
dieser Zusicherung: dass unbeteiligte Alben NICHT markiert werden, und dass
die berechneten Felder nie auf der Platte landen.

Alle Daten erfunden; das Repo ist oeffentlich.
"""
import json

import pytest
from fastapi.testclient import TestClient

BESITZER = {"id": "besitzer", "name": "Besitzer",
            "immich_url": "http://besitzer.invalid", "api_key": "platzhalter",
            "color": "#111111", "user_id": "u-besitzer"}
UNBETEILIGT = {"id": "unbeteiligt", "name": "Unbeteiligt",
               "immich_url": "http://unbeteiligt.invalid", "api_key": "platzhalter",
               "color": "#333333", "user_id": "u-unbeteiligt"}

VERWAIST = {
    "id": "album-verwaist", "match_id": "m-verwaist", "album_id": "immich-verwaist",
    "album_name": "Verwaistes Album", "group_id": "gruppe-verwaist",
    "owner_account_id": "besitzer",
    "person_refs": [
        {"account_id": "besitzer", "person_id": "p1",
         "person_name": "P1", "account_name": "Besitzer",
         "account_color": "#111111"},
        {"account_id": "unbeteiligt", "person_id": "p4",
         "person_name": "P4", "account_name": "Unbeteiligt",
         "account_color": "#333333"},
    ],
    "linked_match_ids": [], "created_at": "2026-01-01T00:00:00+00:00",
}
UNBEEINFLUSST = {
    "id": "album-normal", "match_id": "m-normal", "album_id": "immich-normal",
    "album_name": "Normales Album", "group_id": "gruppe-normal",
    "owner_account_id": "unbeteiligt",
    "person_refs": [
        {"account_id": "unbeteiligt", "person_id": "p2",
         "person_name": "P2", "account_name": "Unbeteiligt",
         "account_color": "#333333"},
        {"account_id": "besitzer", "person_id": "p3",
         "person_name": "P3", "account_name": "Besitzer",
         "account_color": "#111111"},
    ],
    "linked_match_ids": [], "created_at": "2026-01-01T00:00:00+00:00",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    import main
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {"besitzer": BESITZER, "unbeteiligt": UNBETEILIGT},
        "schema_version": 3,
        "managed_albums": [VERWAIST, UNBEEINFLUSST],
    }), encoding="utf-8")
    monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test", raising=False)
    monkeypatch.setattr(main.settings, "config_path", pfad, raising=False)
    with TestClient(main.app) as c:
        c.post("/api/auth/login", json={"token": "nur-fuer-den-test"})
        c.pfad = pfad
        yield c


def test_verwaistes_album_ist_markiert_unbeteiligtes_nicht(client):
    client.delete("/api/accounts/besitzer")
    alben = {a["id"]: a for a in client.get("/api/sync/albums").json()}

    verwaist = alben["album-verwaist"]
    assert verwaist["owner_account_missing"] is True
    assert verwaist["too_few_people"] is True  # eine Person blieb, siehe unten

    # Das unbeteiligte Album verliert seinen Besitzer nicht — nur EINE seiner
    # zwei Personen ("besitzer" war Teilnehmer, nicht Eigentuemer).
    normal = alben["album-normal"]
    assert normal["owner_account_missing"] is False
    assert normal["too_few_people"] is True  # von zwei Personen bleibt eine


def test_ohne_geloeschtes_konto_ist_nichts_markiert(client):
    alben = {a["id"]: a for a in client.get("/api/sync/albums").json()}
    for album in alben.values():
        assert album["owner_account_missing"] is False, album
        assert album["too_few_people"] is False, album


def test_die_markierung_landet_nicht_in_accounts_json(client):
    """Prueffrage 1: Die Berechnung schreibt nicht — kein Feld auf der Platte."""
    client.delete("/api/accounts/besitzer")
    client.get("/api/sync/albums")  # zweimal lesen, falls ein Aufruf schreiben wuerde

    roh = json.loads(client.pfad.read_text(encoding="utf-8"))
    for album in roh["managed_albums"]:
        assert "owner_account_missing" not in album, album
        assert "too_few_people" not in album, album
