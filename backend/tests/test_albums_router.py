import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from models.account import Account
from models.match import ConditionalAlbumRequest, ExtendMatchRequest, LinkedPerson, ManagedAlbum
from routers import albums


def account(account_id: str) -> Account:
    return Account(
        id=account_id,
        name=account_id,
        immich_url=f"http://192.168.1.{len(account_id) + 10}",
        api_key="key",
        color="#000",
        user_id=f"user-{account_id}",
    )


@pytest.mark.asyncio
async def test_conditional_album_endpoint_validates_people_and_deduplicates_payload(monkeypatch):
    owner = account("owner")
    captured: dict = {}

    class Store:
        def get_account(self, account_id):
            return owner if account_id == owner.id else None

        def get_managed_albums(self):
            return []

        def treffer_schloss(self, _match_id):
            return asyncio.Lock()

        def gruppen_schloss(self, _album_name):
            return asyncio.Lock()

        def list_accounts(self):
            return [owner]

        def append_log(self, logs):
            captured["logs"] = logs

    class Client:
        async def get_person(self, person_id):
            return {"id": person_id, "name": person_id.upper()}

    class Pool:
        def get_for_account(self, _account):
            return Client()

    async def create_album(**kwargs):
        captured.update(kwargs)
        return None, []

    monkeypatch.setattr(albums.sync_service, "create_shared_album", create_album)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=Store(), client_pool=Pool())))
    body = ConditionalAlbumRequest(
        album_name="  Family  ",
        owner_account_id=owner.id,
        persons=[
            {"account_id": owner.id, "person_id": "p1"},
            {"account_id": owner.id, "person_id": "p2"},
            {"account_id": owner.id, "person_id": "p3"},
            {"account_id": owner.id, "person_id": "p1"},
        ],
        minimum_person_count=2,
    )

    await albums.create_conditional_album(body, request)

    assert captured["album_name"] == "Family"
    assert captured["minimum_person_count"] == 2
    assert [ref["person_id"] for ref in captured["person_refs"]] == ["p1", "p2", "p3"]
    assert captured["logs"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_album_id", [None, "album-existing"])
async def test_concurrent_conditional_requests_create_only_one_album(
    monkeypatch, existing_album_id,
):
    owner = account("owner")
    started = asyncio.Event()
    release = asyncio.Event()
    created: list[dict] = []
    saved: list[ManagedAlbum] = []
    appended: list = []

    class Store:
        def __init__(self):
            self.match_locks = {}
            self.group_locks = {}

        def get_account(self, account_id):
            return owner if account_id == owner.id else None

        def list_accounts(self):
            return [owner]

        def get_managed_albums(self):
            return saved[:]

        def treffer_schloss(self, match_id):
            return self.match_locks.setdefault(match_id, asyncio.Lock())

        def gruppen_schloss(self, album_name):
            return self.group_locks.setdefault(album_name, asyncio.Lock())

        def resolve_group_id(self, _album_name):
            return saved[0].group_id if saved else "group-family"

        def append_log(self, logs):
            appended.extend(logs)

    class Client:
        async def get_person(self, person_id):
            return {"id": person_id, "name": person_id}

        async def get_album_info(self, album_id):
            assert album_id == existing_album_id
            return {"albumName": "Family"}

    class Pool:
        def get_for_account(self, _account):
            return Client()

    async def create(**kwargs):
        created.append(kwargs)
        started.set()
        await release.wait()
        managed = ManagedAlbum(
            id=f"managed-{len(saved)}", match_id=kwargs["match_id"], album_id="album",
            album_name=kwargs["album_name"], group_id=kwargs["group_id"],
            owner_account_id=owner.id, person_refs=kwargs["person_refs"],
            minimum_person_count=kwargs["minimum_person_count"],
            created_at="2026-09-10T00:00:00+00:00",
        )
        saved.append(managed)
        return managed, []

    monkeypatch.setattr(albums.sync_service, "create_shared_album", create)
    monkeypatch.setattr(albums.sync_service, "link_existing_album", create)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(store=Store(), client_pool=Pool()))
    )
    entries = [
        {"account_id": owner.id, "person_id": "p1"},
        {"account_id": owner.id, "person_id": "p2"},
    ]
    body = ConditionalAlbumRequest(
        album_name=None if existing_album_id else "Family",
        existing_album_id=existing_album_id, owner_account_id=owner.id,
        persons=entries, minimum_person_count=2,
    )
    reversed_body = body.model_copy(update={"persons": list(reversed(body.persons))})

    first = asyncio.create_task(albums.create_conditional_album(body, request))
    await asyncio.wait_for(started.wait(), 1)
    second = asyncio.create_task(albums.create_conditional_album(reversed_body, request))
    # A distinct condition may create another album with the same name; its
    # group must still be resolved after the first album has been persisted.
    third = (
        asyncio.create_task(albums.create_conditional_album(
            body.model_copy(update={"minimum_person_count": 1}), request,
        )) if existing_album_id is None else None
    )
    await asyncio.sleep(0)
    assert not second.done()
    if third:
        assert not third.done()
    release.set()
    first_logs, second_logs = await asyncio.wait_for(asyncio.gather(first, second), 1)
    if third:
        await asyncio.wait_for(third, 1)

    assert first_logs == []
    assert len(created) == len(saved) == (2 if third else 1)
    assert created[0]["match_id"].startswith("conditional_")
    assert {album.group_id for album in saved} == {"group-family"}
    assert [entry.message_key for entry in second_logs] == ["log_album_already_exists"]
    assert appended == second_logs


@pytest.mark.asyncio
async def test_conditional_album_endpoint_rejects_threshold_above_person_count():
    body = ConditionalAlbumRequest(
        album_name="Family",
        owner_account_id="owner",
        persons=[
            {"account_id": "owner", "person_id": "p1"},
            {"account_id": "owner", "person_id": "p2"},
        ],
        minimum_person_count=3,
    )

    with pytest.raises(HTTPException) as exc_info:
        await albums.create_conditional_album(body, SimpleNamespace())

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_conditional_album_endpoint_rejects_people_from_another_account():
    owner = account("owner")

    class Store:
        def get_account(self, account_id):
            return owner if account_id == owner.id else None

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=Store())))
    body = ConditionalAlbumRequest(
        album_name="Family",
        owner_account_id=owner.id,
        persons=[
            {"account_id": owner.id, "person_id": "p1"},
            {"account_id": "other", "person_id": "p2"},
        ],
        minimum_person_count=2,
    )

    with pytest.raises(HTTPException) as exc_info:
        await albums.create_conditional_album(body, request)

    assert exc_info.value.status_code == 422
    assert getattr(exc_info.value, "key", None) == "err_conditional_people_owner_only"


@pytest.mark.asyncio
async def test_linked_people_expand_across_accounts_but_count_as_logical_identities():
    accounts = {key: account(key) for key in ("owner", "other")}
    links = {
        f"link-{index}": LinkedPerson(
            id=f"link-{index}",
            display_name=f"Person {index}",
            person_refs=[
                {
                    "account_id": account_id,
                    "person_id": f"p{index}-{account_id}",
                    "person_name": f"Person {index}",
                    "account_name": value.name,
                    "account_color": value.color,
                }
                for account_id, value in accounts.items()
            ],
            created_at="2026-09-10T00:00:00+00:00",
        )
        for index in (1, 2, 3)
    }

    class Store:
        def get_linked_person(self, link_id):
            return links.get(link_id)

        def get_account(self, account_id):
            return accounts.get(account_id)

    class Client:
        async def get_person(self, person_id):
            return {"id": person_id, "name": person_id}

    class Pool:
        def get_for_account(self, _account):
            return Client()

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(store=Store(), client_pool=Pool()))
    )
    body = ConditionalAlbumRequest(
        album_name="Family",
        owner_account_id="owner",
        linked_person_ids=list(links),
        minimum_person_count=2,
    )

    linked_ids, logical_count, refs = await albums._resolve_conditional_people(body, request)

    assert linked_ids == ["link-1", "link-2", "link-3"]
    assert logical_count == 3
    assert len(refs) == 6
    assert {ref["account_id"] for ref in refs} == {"owner", "other"}


@pytest.mark.asyncio
async def test_conditional_album_can_link_existing_album_with_linked_people(monkeypatch):
    owner = account("owner")
    other = account("other")
    accounts = {owner.id: owner, other.id: other}

    def linked(link_id: str, suffix: str) -> LinkedPerson:
        return LinkedPerson(
            id=link_id,
            display_name=link_id,
            person_refs=[
                {
                    "account_id": account_id,
                    "person_id": f"{suffix}-{account_id}",
                    "person_name": link_id,
                    "account_name": value.name,
                    "account_color": value.color,
                }
                for account_id, value in accounts.items()
            ],
            created_at="2026-09-10T00:00:00+00:00",
        )

    links = {"link-1": linked("link-1", "p1"), "link-2": linked("link-2", "p2")}
    captured = {}

    class Store:
        def get_account(self, account_id):
            return accounts.get(account_id)

        def get_linked_person(self, link_id):
            return links.get(link_id)

        def list_accounts(self):
            return list(accounts.values())

        def get_managed_albums(self):
            return []

        def treffer_schloss(self, _match_id):
            return asyncio.Lock()

        def gruppen_schloss(self, _album_name):
            return asyncio.Lock()

        def append_log(self, logs):
            captured["logs"] = logs

    class Client:
        async def get_person(self, person_id):
            return {"id": person_id, "name": person_id}

        async def get_album_info(self, album_id):
            assert album_id == "album-existing"
            return {"id": album_id, "albumName": "Existing family album"}

    class Pool:
        def get_for_account(self, _account):
            return Client()

    async def link_existing(**kwargs):
        captured.update(kwargs)
        return None, []

    monkeypatch.setattr(albums.sync_service, "link_existing_album", link_existing)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(store=Store(), client_pool=Pool()))
    )
    body = ConditionalAlbumRequest(
        existing_album_id="album-existing",
        owner_account_id=owner.id,
        linked_person_ids=list(links),
        minimum_person_count=2,
    )

    await albums.create_conditional_album(body, request)

    assert captured["album_id"] == "album-existing"
    assert captured["album_name"] == "Existing family album"
    assert captured["linked_person_ids"] == ["link-1", "link-2"]
    assert captured["condition_person_count"] == 2
    assert len(captured["person_refs"]) == 4


@pytest.mark.asyncio
async def test_extend_endpoint_rejects_conditional_album():
    managed = ManagedAlbum(
        id="conditional-1",
        match_id="conditional_match",
        album_id="album-1",
        album_name="Family",
        group_id="gruppe-family",
        owner_account_id="owner",
        person_refs=[],
        minimum_person_count=2,
        created_at="2026-09-10T00:00:00+00:00",
    )

    class Store:
        def get_managed_albums(self):
            return [managed]

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=Store())))
    body = ExtendMatchRequest(
        managed_album_id=managed.id,
        account_id="other",
        person_id="p4",
    )

    with pytest.raises(HTTPException) as exc_info:
        await albums.extend_match(body, request)

    assert exc_info.value.status_code == 422


def test_existing_conditional_identity_ignores_mutable_album_name():
    refs = [{"account_id": "owner", "person_id": "person-1"}]

    before = albums._conditional_match_id(
        "owner", "Old name", "immich-album", 1, [], refs,
    )
    after = albums._conditional_match_id(
        "owner", "New name", "immich-album", 1, [], refs,
    )

    assert before == after
