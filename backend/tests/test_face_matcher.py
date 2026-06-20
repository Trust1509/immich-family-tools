from models.person import Person
from services.face_matcher import compute_matches


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
