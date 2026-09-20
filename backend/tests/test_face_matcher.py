from models.match import ManagedAlbum
from models.person import Person
from services.face_matcher import compute_matches, enrich_matches


def person(person_id, name, account):
    return Person(
        id=person_id, name=name, account_id=account, account_name=account,
        account_color="#000", thumbnail_path=None,
    )


def test_identical_name_without_embedding_is_not_high_confidence():
    matches = compute_matches([person("1", "Manuel", "a"), person("2", "Manuel", "b")])
    assert len(matches) == 1
    assert matches[0].confidence == 0.75
    assert "embedding_similarity" not in matches[0].reasons


def test_unnamed_people_do_not_produce_suggestions():
    assert compute_matches([person("1", None, "a"), person("2", None, "b")]) == []


# ----------------------------------------------------------------------
# enrich_matches — die Gruppenzugehoerigkeit (#78)
#
# Diese Funktion entscheidet ueber has_album und damit darueber, ob ein
# Vorschlag angezeigt oder UNTERDRUECKT wird. Sie hatte bis v1.7.0 keinen
# einzigen Test, obwohl ein unterdrueckter Vorschlag stiller ausfaellt als
# ein doppelter.
# ----------------------------------------------------------------------


def verwaltetes_album(album_id, name, personen, group_id):
    return ManagedAlbum(
        id=album_id,
        match_id=f"match-{album_id}",
        album_id=f"immich-{album_id}",
        album_name=name,
        group_id=group_id,
        owner_account_id="konto-1",
        person_refs=[
            {"account_id": "konto-1", "person_id": p, "person_name": p,
             "account_name": "konto-1", "account_color": "#000"}
            for p in personen
        ],
        created_at="2026-01-01T00:00:00+00:00",
    )


def paar(person_a, person_b):
    """Das eine Match, dessen has_album uns interessiert."""
    leute = [person(person_a, "Gleichername", "konto-1"),
             person(person_b, "Gleichername", "konto-2")]
    treffer = compute_matches(leute)
    assert len(treffer) == 1
    return treffer


def test_enrich_verbindet_personen_ueber_dieselbe_gruppe():
    """Transitivitaet: p1+p2 und p2+p3 in einer Gruppe -> p1+p3 gilt versorgt."""
    matches = enrich_matches(
        paar("p1", "p3"),
        [verwaltetes_album("a1", "Familie", ["p1", "p2"], "gruppe-1"),
         verwaltetes_album("a2", "Familie", ["p2", "p3"], "gruppe-1")],
        set(),
    )
    assert matches[0].has_album is True


def test_enrich_haelt_die_gruppe_beim_umbenennen_zusammen():
    """Der Kern von #78: verschiedene Namen, gleiche Gruppe -> bleibt eine.

    Vor der stabilen Kennung war das nicht ausdrueckbar — ein Umbenennen
    zerlegte die Gruppe still.
    """
    matches = enrich_matches(
        paar("p1", "p3"),
        [verwaltetes_album("a1", "Familie", ["p1", "p2"], "gruppe-1"),
         verwaltetes_album("a2", "Familie 2024", ["p2", "p3"], "gruppe-1")],
        set(),
    )
    assert matches[0].has_album is True


def test_enrich_verschmilzt_gleichnamige_fremde_gruppen_nicht():
    """Die Gegenrichtung: gleicher Name, verschiedene Gruppen -> getrennt.

    Sonst gilt ein Paar als versorgt, fuer das kein Album existiert, und
    der Vorschlag verschwindet.
    """
    matches = enrich_matches(
        paar("p1", "p3"),
        [verwaltetes_album("a1", "Familie", ["p1", "p2"], "gruppe-1"),
         verwaltetes_album("a2", "Familie", ["p2", "p3"], "gruppe-2")],
        set(),
    )
    assert matches[0].has_album is False
