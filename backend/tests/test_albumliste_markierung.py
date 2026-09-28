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


def test_lebender_besitzer_ohne_eigenen_personenbezug_wird_nicht_markiert(tmp_path, monkeypatch):
    """Nacharbeit 1 (Gegenpruefer, ueber `names-multi` erreichbar): die
    Markierung muss aus dem KONTENBESTAND kommen, nicht aus `person_refs`.

    Ein Album hat immer genau EIN Besitzerkonto (`owner_account_id`), das
    Immich-seitig teilt — es muss aber nicht selbst unter den `person_refs`
    auftauchen (etwa: es teilt ein Album fuer zwei andere Konten, ohne
    selbst eine verknuepfte Person zu haben). Das ist ein gueltiger, gemessen
    ueber `POST /api/sync/names-multi` mit einem abweichenden
    `owner_account_id` erreichbarer Zustand — kein Konstrukt. Eine Markierung,
    die stattdessen prueft, ob der Besitzer UNTER den `person_refs` steht,
    wuerde dieses Album faelschlich als verwaist melden, obwohl das Konto lebt.
    """
    import main

    besitzer = {"id": "besitzer-teilt-nur", "name": "Teilt Nur",
                "immich_url": "http://teilt.invalid", "api_key": "platzhalter",
                "color": "#444444", "user_id": "u-teilt"}
    teilnehmer = {"id": "teilnehmer-x", "name": "Teilnehmer X",
                  "immich_url": "http://x.invalid", "api_key": "platzhalter",
                  "color": "#555555", "user_id": "u-x"}
    album = {
        "id": "album-owner-ohne-ref", "match_id": "m-owner-ohne-ref",
        "album_id": "immich-owner-ohne-ref", "album_name": "Nur Teilnehmer",
        "group_id": "gruppe-owner-ohne-ref", "owner_account_id": "besitzer-teilt-nur",
        "person_refs": [
            {"account_id": "teilnehmer-x", "person_id": "p-x",
             "person_name": "P X", "account_name": "Teilnehmer X",
             "account_color": "#555555"},
            {"account_id": "teilnehmer-y", "person_id": "p-y",
             "person_name": "P Y", "account_name": "Teilnehmer Y",
             "account_color": "#666666"},
        ],
        "linked_match_ids": [], "created_at": "2026-01-01T00:00:00+00:00",
    }
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {"besitzer-teilt-nur": besitzer, "teilnehmer-x": teilnehmer},
        "schema_version": 3,
        "managed_albums": [album],
    }), encoding="utf-8")
    monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test", raising=False)
    monkeypatch.setattr(main.settings, "config_path", pfad, raising=False)

    with TestClient(main.app) as c:
        c.post("/api/auth/login", json={"token": "nur-fuer-den-test"})
        alben = c.get("/api/sync/albums").json()
        antwort = next(a for a in alben if a["id"] == "album-owner-ohne-ref")
        assert antwort["owner_account_missing"] is False, (
            "Ein lebender Besitzer ohne eigenen Personenbezug im Album "
            "wurde faelschlich als verwaist markiert"
        )
        assert antwort["too_few_people"] is False, antwort
