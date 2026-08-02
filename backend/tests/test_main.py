import asyncio
from datetime import datetime as RealDateTime
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


@pytest.mark.asyncio
async def test_auto_sync_runs_again_when_rescheduled_for_later_the_same_day(monkeypatch):
    configured_times = iter(("12:01", "12:03"))
    current_times = iter((
        RealDateTime(2026, 8, 2, 12, 1),
        RealDateTime(2026, 8, 2, 12, 3),
    ))
    runs: list[str] = []
    sleep_calls = 0

    class Store:
        def get_auto_sync_config(self):
            return {"enabled": True, "time": next(configured_times)}

    class FakeDateTime:
        @classmethod
        def now(cls):
            return next(current_times)

    async def fake_sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 2:
            raise asyncio.CancelledError

    async def run_auto_sync(_state):
        runs.append("run")

    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(main, "datetime", FakeDateTime)
    monkeypatch.setattr(main, "_run_auto_sync", run_auto_sync)

    with pytest.raises(asyncio.CancelledError):
        await main._auto_sync_loop(SimpleNamespace(store=Store()))

    assert runs == ["run", "run"]


@pytest.mark.asyncio
async def test_auto_sync_runs_only_once_for_the_same_time_slot(monkeypatch):
    runs: list[str] = []
    sleep_calls = 0

    class Store:
        def get_auto_sync_config(self):
            return {"enabled": True, "time": "12:01"}

    class FakeDateTime:
        @classmethod
        def now(cls):
            return RealDateTime(2026, 8, 2, 12, 1)

    async def fake_sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 2:
            raise asyncio.CancelledError

    async def run_auto_sync(_state):
        runs.append("run")

    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(main, "datetime", FakeDateTime)
    monkeypatch.setattr(main, "_run_auto_sync", run_auto_sync)

    with pytest.raises(asyncio.CancelledError):
        await main._auto_sync_loop(SimpleNamespace(store=Store()))

    assert runs == ["run"]
