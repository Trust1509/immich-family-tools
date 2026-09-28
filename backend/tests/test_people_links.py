from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from models.account import Account
from models.match import LinkedPersonCreate, ManagedAlbum
from routers import people_links
from services.config_store import ConfigStore


def account(account_id: str) -> Account:
    return Account(
        id=account_id, name=account_id.upper(), immich_url="http://192.168.1.2",
        api_key="key", color="#123456", user_id=f"user-{account_id}",
    )


@pytest.mark.asyncio
async def test_create_link_validates_without_renaming_and_returns_enriched_refs(tmp_path):
    accounts = {key: account(key) for key in ("a", "b")}
    store = ConfigStore(str(tmp_path / "accounts.json"))
    store._data["accounts"] = {key: value.model_dump() for key, value in accounts.items()}
    updated = []

    class Client:
        async def get_person(self, person_id):
            return {"id": person_id, "name": f"Name {person_id}"}

        async def update_person(self, *_args):
            updated.append(True)

    class Pool:
        def get_for_account(self, _account):
            return Client()

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store, client_pool=Pool())))
    linked = await people_links.create_person_link(LinkedPersonCreate(persons=[
        {"account_id": "a", "person_id": "pa"},
        {"account_id": "b", "person_id": "pb"},
    ]), request)

    assert linked.display_name == "Name pa"
    assert [(ref.account_id, ref.person_name, ref.account_name) for ref in linked.person_refs] == [
        ("a", "Name pa", "A"), ("b", "Name pb", "B")
    ]
    assert updated == []
    assert ConfigStore(str(tmp_path / "accounts.json")).get_linked_person(linked.id) == linked


def test_store_reuses_compatible_link_and_rejects_account_collision(tmp_path):
    store = ConfigStore(str(tmp_path / "accounts.json"))
    for key in ("a", "b", "c"):
        store._data["accounts"][key] = account(key).model_dump()
    first = store.ensure_linked_person("Alex", [
        {"account_id": "a", "person_id": "pa"},
        {"account_id": "b", "person_id": "pb"},
    ])
    reused = store.ensure_linked_person("Ignored", [
        {"account_id": "a", "person_id": "pa"},
        {"account_id": "c", "person_id": "pc"},
    ])
    assert reused.id == first.id
    assert reused.display_name == "Ignored"
    assert {ref.account_id for ref in reused.person_refs} == {"a", "b", "c"}
    with pytest.raises(ValueError):
        store.ensure_linked_person("Conflict", [
            {"account_id": "a", "person_id": "different"},
            {"account_id": "b", "person_id": "pb"},
        ])


def test_deleting_account_removes_links_that_no_longer_span_two_accounts(tmp_path):
    store = ConfigStore(str(tmp_path / "accounts.json"))
    for key in ("a", "b"):
        store._data["accounts"][key] = account(key).model_dump()
    linked = store.ensure_linked_person("Alex", [
        {"account_id": "a", "person_id": "pa"},
        {"account_id": "b", "person_id": "pb"},
    ])

    assert store.delete_account("a") is True
    assert store.get_linked_person(linked.id) is None


def test_conditional_album_only_links_profiles_within_each_logical_person(tmp_path):
    store = ConfigStore(str(tmp_path / "accounts.json"))
    for key in ("a", "b"):
        store._data["accounts"][key] = account(key).model_dump()
    alex = store.ensure_linked_person("Alex", [
        {"account_id": "a", "person_id": "alex-a"},
        {"account_id": "b", "person_id": "alex-b"},
    ])
    sam = store.ensure_linked_person("Sam", [
        {"account_id": "a", "person_id": "sam-a"},
        {"account_id": "b", "person_id": "sam-b"},
    ])
    album = ManagedAlbum(
        id="managed", match_id="conditional_rule", album_id="album",
        album_name="Family", group_id="gruppe-family", owner_account_id="a",
        person_refs=[ref.model_dump() for link in (alex, sam) for ref in link.person_refs],
        linked_person_ids=[alex.id, sam.id], condition_person_count=2,
        minimum_person_count=2, created_at="2026-09-10T00:00:00+00:00",
    )

    store.add_managed_album(album)

    assert set(album.linked_match_ids) == {
        ConfigStore.pair_match_id("alex-a", "alex-b"),
        ConfigStore.pair_match_id("sam-a", "sam-b"),
    }
    assert ConfigStore.pair_match_id("alex-a", "sam-a") not in album.linked_match_ids


@pytest.mark.asyncio
async def test_create_link_rejects_two_profiles_from_same_account():
    request = SimpleNamespace()
    with pytest.raises(HTTPException) as exc_info:
        await people_links.create_person_link(LinkedPersonCreate(persons=[
            {"account_id": "a", "person_id": "p1"},
            {"account_id": "a", "person_id": "p2"},
        ]), request)
    assert exc_info.value.status_code == 422
