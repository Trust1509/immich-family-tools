import pytest

from models.account import Account
from models.match import ManagedAlbum
from services import sync_service


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
async def test_name_sync_records_previous_name(monkeypatch):
    class Client:
        def __init__(self, *_):
            pass

        async def get_person(self, _person_id):
            return {"name": "Before"}

        async def update_person(self, _person_id, payload):
            assert payload == {"name": "After"}
            return {"name": "After"}

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    entries = await sync_service.sync_names(account("a"), "p1", account("b"), "p2", "After")
    assert all(entry.undo_data["previous_name"] == "Before" for entry in entries)


@pytest.mark.asyncio
async def test_album_is_shared_only_with_participants(monkeypatch):
    owner, participant, unrelated = account("owner"), account("participant"), account("unrelated")
    captured = []

    class Client:
        def __init__(self, *_):
            pass

        async def get_person_assets(self, _person_id):
            return []

        async def create_album(self, _name, _assets):
            return {"id": "album"}

    async def fake_share(_client, _album_id, _album_name, accounts):
        captured.extend(a.id for a in accounts)
        return []

    class Store:
        def add_managed_album(self, _album):
            pass

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", fake_share)
    refs = [
        {"account_id": "owner", "person_id": "p1"},
        {"account_id": "participant", "person_id": "p2"},
    ]
    await sync_service.create_shared_album(
        "match", owner, [owner, participant, unrelated], refs, "Album", Store()
    )
    assert captured == ["participant"]


@pytest.mark.asyncio
async def test_refresh_does_not_readd_assets_already_in_the_album(monkeypatch):
    add_calls: list[list[str]] = []

    class Client:
        def __init__(self, *_):
            pass

        async def get_album_assets(self, _album_id):
            return ["asset-1"]

        async def get_person_assets(self, _person_id):
            return [{"id": "asset-1"}]

        async def add_assets_to_album(self, _album_id, asset_ids):
            add_calls.append(asset_ids)

    async def skip_sharing(*_args):
        return []

    class Store:
        def update_managed_album(self, _album):
            pass

    owner = account("owner")
    managed = ManagedAlbum(
        id="managed-1",
        match_id="match-1",
        album_id="album-1",
        album_name="Family",
        owner_account_id=owner.id,
        person_refs=[{"account_id": owner.id, "person_id": "person-1"}],
        created_at="2026-08-02T00:00:00+00:00",
    )
    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", skip_sharing)

    entries = await sync_service.refresh_managed_album(managed, [owner], Store())

    assert add_calls == []
    assert managed.total_assets == 1
    assert entries[0].status == "success"


@pytest.mark.asyncio
async def test_refresh_adds_only_new_assets_and_updates_the_total(monkeypatch):
    add_calls: list[list[str]] = []

    class Client:
        def __init__(self, *_):
            pass

        async def get_album_assets(self, _album_id):
            return ["asset-1"]

        async def get_person_assets(self, _person_id):
            return [{"id": "asset-1"}, {"id": "asset-2"}]

        async def add_assets_to_album(self, _album_id, asset_ids):
            add_calls.append(asset_ids)

    async def skip_sharing(*_args):
        return []

    class Store:
        def update_managed_album(self, _album):
            pass

    owner = account("owner")
    managed = ManagedAlbum(
        id="managed-1",
        match_id="match-1",
        album_id="album-1",
        album_name="Family",
        owner_account_id=owner.id,
        person_refs=[{"account_id": owner.id, "person_id": "person-1"}],
        created_at="2026-08-02T00:00:00+00:00",
    )
    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", skip_sharing)

    await sync_service.refresh_managed_album(managed, [owner], Store())

    assert add_calls == [["asset-2"]]
    assert managed.total_assets == 2


@pytest.mark.asyncio
async def test_extend_match_adds_only_assets_missing_from_the_album(monkeypatch):
    add_calls: list[list[str]] = []

    class Client:
        def __init__(self, *_):
            pass

        async def get_person(self, _person_id):
            return {"id": "person-2", "name": "Family"}

        async def get_album_assets(self, _album_id):
            return ["asset-1"]

        async def get_person_assets(self, _person_id):
            return [{"id": "asset-1"}, {"id": "asset-2"}]

        async def add_assets_to_album(self, _album_id, asset_ids):
            add_calls.append(asset_ids)

    async def skip_sharing(*_args):
        return []

    class Store:
        def update_managed_album(self, _album):
            pass

    owner = account("owner")
    participant = account("participant")
    managed = ManagedAlbum(
        id="managed-1",
        match_id="match-1",
        album_id="album-1",
        album_name="Family",
        owner_account_id=owner.id,
        person_refs=[{"account_id": owner.id, "person_id": "person-1"}],
        created_at="2026-08-02T00:00:00+00:00",
        total_assets=1,
    )
    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", skip_sharing)

    await sync_service.extend_match(
        managed,
        participant,
        "person-2",
        "Family",
        None,
        [owner, participant],
        Store(),
    )

    assert add_calls == [["asset-2"]]
    assert managed.total_assets == 2
