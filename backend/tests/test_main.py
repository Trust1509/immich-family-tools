from types import SimpleNamespace

import pytest

import main
from models.match import ManagedAlbum
from services import sync_service


@pytest.mark.asyncio
async def test_scheduled_sync_refreshes_each_managed_album(monkeypatch):
    albums = [
        ManagedAlbum(
            id="managed-1",
            match_id="match-1",
            album_id="album-1",
            album_name="Family",
            owner_account_id="owner",
            person_refs=[],
            created_at="2026-08-02T00:00:00+00:00",
        )
    ]
    refreshed: list[str] = []

    async def refresh(album, _accounts, _store):
        refreshed.append(album.id)
        return []

    class Store:
        def get_managed_albums(self):
            return albums

        def list_accounts(self):
            return []

        def append_log(self, _logs):
            pass

    monkeypatch.setattr(sync_service, "refresh_managed_album", refresh)

    await main._run_auto_sync(SimpleNamespace(store=Store()))

    assert refreshed == ["managed-1"]
