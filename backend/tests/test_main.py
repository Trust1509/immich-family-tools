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
            group_id="gruppe-family",
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


# ----------------------------------------------------------------------
# Der Name eines bereits vorhandenen Albums (#78, Nacharbeit)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bestehendes_album_holt_seinen_namen_aus_immich(monkeypatch):
    """Ohne Namensangabe wird der echte Name geholt, nicht die UUID gespeichert.

    Bis zur Nacharbeit stand dort `body.album_name or body.existing_album_id`.
    Die UUID landete im Namensfeld UND — ueber group_id_for_name — in der
    dauerhaften Gruppenkennung.
    """
    from routers import albums as albums_router

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def get_album_info(self, _album_id):
            return {"albumName": "Echter Name"}

    monkeypatch.setattr("services.immich_client.ImmichClient", Client)

    class Konto:
        immich_url = "http://beispiel.invalid"
        api_key = "platzhalter"

    name = await albums_router._name_des_bestehenden_albums(Konto(), "immich-uuid", None)
    assert name == "Echter Name"


@pytest.mark.asyncio
async def test_unauffindbares_album_wird_abgelehnt_statt_geraten(monkeypatch):
    from routers import albums as albums_router

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def get_album_info(self, _album_id):
            raise RuntimeError("nicht erreichbar")

    monkeypatch.setattr("services.immich_client.ImmichClient", Client)

    class Konto:
        immich_url = "http://beispiel.invalid"
        api_key = "platzhalter"

    with pytest.raises(Exception) as fehler:
        await albums_router._name_des_bestehenden_albums(Konto(), "immich-uuid", None)
    assert "album_name" in str(fehler.value).lower() or "err_album_name" in str(fehler.value)


@pytest.mark.asyncio
async def test_angegebener_name_hat_vorrang():
    from routers import albums as albums_router

    class Konto:
        immich_url = "http://beispiel.invalid"
        api_key = "platzhalter"

    name = await albums_router._name_des_bestehenden_albums(Konto(), "immich-uuid", "Wunschname")
    assert name == "Wunschname"


@pytest.mark.asyncio
async def test_unauffindbares_album_lehnt_ab_BEVOR_umbenannt_wird(monkeypatch, tmp_path):
    """Alles, was ablehnen kann, gehoert vor den ersten Schreibvorgang.

    Gemessen vom Blindpruefer an der ersten Nacharbeit: Die Namensaufloesung
    stand NACH sync_names_multi. Schlug sie fehl, waren die Personen in Immich
    bereits umbenannt, das Protokoll geschrieben und die Paare als abgeglichen
    markiert — und der Aufrufer bekam 422 "album_name erforderlich fuer neues
    Album", was weder stimmte noch half. Eine Teilausfuehrung, die sich als
    Eingabefehler ausgibt.
    """
    import json

    from models.match import MultiSyncPersonEntry, SyncNamesMultiRequest
    from routers import albums as albums_router
    from services.config_store import ConfigStore

    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {
            "konto-1": {"id": "konto-1", "name": "Konto Eins",
                        "immich_url": "http://beispiel.invalid", "api_key": "platzhalter",
                        "color": "#111111"},
            "konto-2": {"id": "konto-2", "name": "Konto Zwei",
                        "immich_url": "http://beispiel.invalid", "api_key": "platzhalter",
                        "color": "#222222"},
        },
        "managed_albums": [],
    }), encoding="utf-8")
    store = ConfigStore(str(pfad))

    umbenannt: list[str] = []

    async def nie_erreicht(*_a, **_k):
        umbenannt.append("sync_names_multi")
        return []

    class KaputterClient:
        def __init__(self, *_a, **_k):
            pass

        async def get_album_info(self, _album_id):
            raise RuntimeError("Album in Immich geloescht")

    class Pool:
        def get_for_account(self, _acc):
            class C:
                async def get_person(self, _pid):
                    return {}
            return C()

    monkeypatch.setattr(albums_router.sync_service, "sync_names_multi", nie_erreicht)
    monkeypatch.setattr("services.immich_client.ImmichClient", KaputterClient)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        store=store, client_pool=Pool())))
    body = SyncNamesMultiRequest(
        persons=[MultiSyncPersonEntry(account_id="konto-1", person_id="p1"),
                 MultiSyncPersonEntry(account_id="konto-2", person_id="p2")],
        canonical_name="Testname",
        existing_album_id="immich-weg",
    )

    with pytest.raises(Exception):
        await albums_router.sync_names_multi(body, request)

    assert umbenannt == [], "es darf nichts umbenannt worden sein"
    assert store.get_log() == [], "es darf nichts protokolliert worden sein"
