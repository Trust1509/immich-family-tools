"""Umbenennen über eine ganze Gruppe — die Wege, die die Oberfläche geht (#79).

Alle drei Fälle hier sind Funde des Blindprüfers an der ersten Nacharbeit, und
alle drei haben eine gemeinsame Wurzel: **Die Kollisionsprüfung urteilte über
ein Album, der Vorgang betrifft aber eine Gruppe.**

1. Die Oberfläche benennt eine Gruppe um, indem sie jedes ihrer Alben EINZELN
   umbenennt. Für diesen Weg — den normalen — gab es keine Backend-Probe; die
   Ausnahme „die eigene Gruppe zählt nicht als Kollision" liess sich entkernen,
   ohne dass eine der 236 Proben rot wurde.
2. Nach einem Teilausfall trägt die Gruppe den neuen Namen schon über ihr
   erstes Album, das zurückgebliebene noch den alten. Fragte die Ausnahme nur
   dieses Album, lehnte das Backend die Wiederholung **dauerhaft** mit 409 ab —
   obwohl das Frontend sie seit derselben Nacharbeit anbietet und obwohl der
   Vorgang die Mehrdeutigkeit nachweislich nicht verändert.
3. Die Ausnahme und der Abzug der eigenen Gruppe sind NICHT dasselbe: Der Abzug
   ist weiter (die eigene Gruppe ist immer ausgenommen), die Ausnahme enger
   (sie fragt beide Faltungen). Der dritte Test unten ist der Fall, in dem sich
   die beiden unterscheiden — ohne ihn wäre der Abzug unbewacht.

Die Attrappe hier **schreibt wirklich**. Eine zählende Attrappe wie in
`test_umbenennen_kollision.py` kann diese Fälle nicht messen: Die zweite Anfrage
sieht dann nie, was die erste angerichtet hat.
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
    """Baut eine Anwendung mit dem übergebenen Bestand und schreibendem Immich."""
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


def _namen(client):
    return {a["id"]: a["album_name"] for a in client.get("/api/sync/albums").json()}


def test_beide_alben_einer_gruppe_lassen_sich_umbenennen(mit_bestand):
    """Der normale Weg der Oberfläche — und er hatte keine Backend-Probe.

    Das zweite Album sieht den neuen Namen des ersten schon im Bestand. Ohne die
    Ausnahme für die eigene Gruppe bekäme es 409, und eine Gruppe mit zwei Alben
    liesse sich überhaupt nicht umbenennen.
    """
    c = mit_bestand([_album("a1", "Sommerfest", "gruppe-1"),
                     _album("a2", "Sommerfest", "gruppe-1")])
    assert c.patch("/api/sync/albums/a1",
                   json={"album_name": "Herbstfest"}).status_code == 200
    zweite = c.patch("/api/sync/albums/a2", json={"album_name": "Herbstfest"})
    assert zweite.status_code == 200, zweite.text
    assert _namen(c) == {"a1": "Herbstfest", "a2": "Herbstfest"}


def test_die_wiederholung_nach_einem_teilausfall_kommt_durch(mit_bestand):
    """Der Stand nach einem Teilausfall, mit einer fremden Schreibweise daneben.

    `gruppe-1` trägt „Herbstfest" schon über a1; a2 blieb zurück. `gruppe-2`
    hält „HERBSTFEST" — dieselbe Stufe-1-Faltung, andere Stufe 2. Damit steht
    `gruppe-2` in `fremd`, und die Ausnahme entscheidet.

    Sie muss die GRUPPE fragen: a2 selbst trägt den Namen noch nicht, seine
    Gruppe schon. Die Mehrdeutigkeit ist vorher und nachher dieselbe — eine
    Ablehnung würde nichts verhindern und a2 für immer zurücklassen.
    """
    c = mit_bestand([_album("a1", "Herbstfest", "gruppe-1"),
                     _album("a2", "Sommerfest", "gruppe-1"),
                     _album("a3", "HERBSTFEST", "gruppe-2")])
    antwort = c.patch("/api/sync/albums/a2", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 200, antwort.text
    assert _namen(c)["a2"] == "Herbstfest"


def test_die_eigene_gruppe_darf_eine_zweite_schreibweise_bekommen(mit_bestand):
    """Der Fall, in dem Abzug und Ausnahme AUSEINANDERGEHEN.

    `gruppe-1` hält „Strassenfest" und „Sommerfest". Wer „Sommerfest" in
    „Straßenfest" umbenennt, kollidiert in Stufe 1 mit dem eigenen
    „Strassenfest" — und mit KEINER anderen Gruppe. Es entsteht also keine
    gruppenübergreifende Mehrdeutigkeit, und der Vorgang gehört erlaubt.

    Die Ausnahme allein trägt das nicht: `derselbe_name` verneint für beide
    eigenen Namen (Stufe 2 unterscheidet sie). Es ist der Abzug der eigenen
    Gruppe, der hier entscheidet — und ohne diesen Test wäre er unbewacht.
    """
    c = mit_bestand([_album("a1", "Strassenfest", "gruppe-1"),
                     _album("a2", "Sommerfest", "gruppe-1")])
    antwort = c.patch("/api/sync/albums/a2", json={"album_name": "Straßenfest"})
    assert antwort.status_code == 200, antwort.text
    assert _namen(c) == {"a1": "Strassenfest", "a2": "Straßenfest"}


def test_eine_fremde_gruppe_bleibt_auch_hier_gesperrt(mit_bestand):
    """Die Gegenprobe zu allen drei Fällen darüber."""
    c = mit_bestand([_album("a1", "Sommerfest", "gruppe-1"),
                     _album("a2", "Herbstfest", "gruppe-2")])
    antwort = c.patch("/api/sync/albums/a1", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 409, antwort.text
    assert antwort.json().get("error_key") == "err_album_name_in_use"
    assert _namen(c)["a1"] == "Sommerfest"
