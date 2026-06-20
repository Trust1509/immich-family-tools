import pytest

from models.account import Account
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
