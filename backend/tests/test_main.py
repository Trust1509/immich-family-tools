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


@pytest.mark.asyncio
async def test_fehler_nach_dem_schreiben_gibt_sich_nicht_als_immich_fehler_aus(
        monkeypatch, tmp_path):
    """#87: Der `except` in refresh_account umfasste auch den Schreibvorgang.

    Schlug irgendetwas NACH `update_account` fehl, bekam der Aufrufer 502
    "Immich-Anfrage fehlgeschlagen" — obwohl geschrieben worden war und
    Immich in Ordnung war. Er erfaehrt damit eine falsche Ursache zu einem
    Zustand, der sich bereits geaendert hat.

    Gefunden vom Reihenfolge-Waechter am sauberen Baum, von der Zweitstimme
    bis zur Antwort durchgemessen.
    """
    import json

    from routers import accounts as accounts_router
    from services.config_store import ConfigStore

    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {
            "konto-1": {"id": "konto-1", "name": "Konto Eins",
                        "immich_url": "http://beispiel.invalid",
                        "api_key": "platzhalter", "color": "#111111"},
        },
        "managed_albums": [],
    }), encoding="utf-8")
    store = ConfigStore(str(pfad))

    class Client:
        async def validate(self):
            return {"id": "u1-neu"}          # Immich antwortet einwandfrei

    class Pool:
        def get_for_account(self, _acc):
            return Client()

    # Der Fehler kommt NACH dem Schreibvorgang und hat mit Immich nichts zu tun.
    echt = store.get_account

    def bricht_nach_dem_schreiben(kennung):
        konto = echt(kennung)
        if konto is not None and konto.user_id == "u1-neu":
            raise RuntimeError("irgendetwas nach dem Schreibvorgang")
        return konto

    monkeypatch.setattr(store, "get_account", bricht_nach_dem_schreiben)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        store=store, client_pool=Pool())))

    # Vorher war das ein AppError mit 502 "Immich-Anfrage fehlgeschlagen".
    # Jetzt kommt der echte Fehler durch — ein Serverfehler bleibt ein
    # Serverfehler und gibt sich nicht als Ursache aus, die er nicht ist.
    with pytest.raises(RuntimeError):
        await accounts_router.refresh_account("konto-1", request)

    # Der Schreibvorgang IST passiert — genau deshalb darf die Antwort ihn
    # nicht als Immich-Fehler ausgeben.
    assert store._data["accounts"]["konto-1"]["user_id"] == "u1-neu"


@pytest.mark.asyncio
async def test_immich_antwortet_2xx_ohne_objekt_bleibt_ein_502(monkeypatch, tmp_path):
    """Die Grenze des verengten `try` — gemessen statt behauptet.

    Das Verengen des `try` in refresh_account (#87) hat `.get("id")` aus dem
    Fang herausgenommen. Antwortet Immich mit 2xx, aber KEINEM Objekt, waere
    daraus ein AttributeError und damit 500 geworden — und refresh_account
    waere als einziger der drei Konten-Endpunkte aus der Reihe gefallen;
    `add_account` und `update_account` antworten in derselben Lage 502.

    Gemessen vom Blindpruefer an der Nacharbeit, bevor die Pruefung hier
    stand: `AttributeError: 'list' object has no attribute 'get'`.
    """
    import json

    from errors import AppError
    from routers import accounts as accounts_router
    from services.config_store import ConfigStore

    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {
            "konto-1": {"id": "konto-1", "name": "Konto Eins",
                        "immich_url": "http://beispiel.invalid",
                        "api_key": "platzhalter", "color": "#111111"},
        },
        "managed_albums": [],
    }), encoding="utf-8")
    store = ConfigStore(str(pfad))

    class Client:
        async def validate(self):
            return ["kein", "objekt"]        # 2xx, aber kein Objekt

    class Pool:
        def get_for_account(self, _acc):
            return Client()

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        store=store, client_pool=Pool())))

    with pytest.raises(AppError) as fehler:
        await accounts_router.refresh_account("konto-1", request)

    assert fehler.value.status_code == 502
    assert fehler.value.key == "err_immich_request_failed"


# ----------------------------------------------------------------------
# Vorschau und ausdrueckliche Gruppenwahl (#81)
# ----------------------------------------------------------------------


def _store_mit_gruppen(tmp_path):
    import json

    from services.config_store import ConfigStore

    def album(aid, name, gid, personen):
        return {
            "id": aid, "match_id": f"m-{aid}", "album_id": f"ia-{aid}",
            "album_name": name, "group_id": gid, "owner_account_id": "konto-1",
            "person_refs": [{"account_id": "konto-1", "person_id": p,
                             "person_name": p, "account_name": "Konto Eins",
                             "account_color": "#111111"} for p in personen],
            "created_at": "2026-01-01T00:00:00+00:00", "last_synced_at": None,
            "total_assets": 0, "status": "active",
        }

    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({"accounts": {}, "managed_albums": [
        album("a1", "Testalbum", "gruppe-1", ["p1", "p2"]),
        album("a2", "Anders benannt", "gruppe-1", ["p2", "p3"]),
    ]}), encoding="utf-8")
    return ConfigStore(str(pfad))


@pytest.mark.asyncio
async def test_vorschau_nennt_die_gruppe_und_wem_man_beitritt(tmp_path):
    from routers import albums as albums_router

    store = _store_mit_gruppen(tmp_path)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)))

    treffer = await albums_router.album_group_preview("  TESTALBUM ", request)

    assert treffer["group_id"] == "gruppe-1"
    # Die GANZE Gruppe, nicht nur das namensgleiche Album — sonst sieht der
    # Nutzer nicht, wem er wirklich beitritt.
    assert [r["person_id"] for r in treffer["person_refs"]] == ["p1", "p2", "p3"]


@pytest.mark.asyncio
async def test_vorschau_behauptet_nichts_ohne_treffer(tmp_path):
    from routers import albums as albums_router

    store = _store_mit_gruppen(tmp_path)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)))

    assert await albums_router.album_group_preview("Kennt keiner", request) is None
    assert await albums_router.album_group_preview("   ", request) is None


@pytest.mark.asyncio
async def test_anlegen_folgt_der_ausdruecklichen_wahl(tmp_path, monkeypatch):
    """Die VERDRAHTUNG, nicht die Regel.

    lehren.md §39: Bei #78 ueberlebte genau diese Klasse zweimal — die Regel
    war geprueft, der Aufrufer nicht. Hier wird deshalb durch den Router
    angelegt, mit einem echten ConfigStore, und nachgesehen, was GESPEICHERT
    wurde.
    """
    from models.match import SyncAlbumRequest
    from routers import albums as albums_router
    from services import sync_service

    store = _store_mit_gruppen(tmp_path)
    bestehend = "gruppe-1"

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def create_album(self, _name, _ids):
            return {"id": "neues-immich-album"}

        async def get_person_assets(self, _pid):
            return []

    async def fake_share(*_a, **_k):
        return []

    class Konto:
        id = "konto-1"
        name = "Konto Eins"
        color = "#111111"
        immich_url = "http://beispiel.invalid"
        api_key = "platzhalter"

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", fake_share)
    monkeypatch.setattr(store, "get_account", lambda _id: Konto())

    treffer = SimpleNamespace(
        id="match-neu",
        person_a=SimpleNamespace(account_id="konto-1", person_id="p7",
                                 person_name="Person G", account_name="Konto Eins",
                                 account_color="#111111"),
        person_b=SimpleNamespace(account_id="konto-1", person_id="p8",
                                 person_name="Person H", account_name="Konto Eins",
                                 account_color="#111111"),
    )
    monkeypatch.setattr(albums_router, "get_matches", lambda _r: [treffer], raising=False)

    async def hole_matches(_request):
        return [treffer]

    import routers.faces as faces
    monkeypatch.setattr(faces, "get_matches", hole_matches)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)))

    # 1) Ohne Angabe: der Name entscheidet, wie bisher.
    await albums_router.create_album(
        SyncAlbumRequest(match_id="match-neu", owner_account_id="konto-1",
                         album_name="Testalbum"), request)
    ohne = {a.match_id: a.group_id for a in store.get_managed_albums()}["match-neu"]
    assert ohne == bestehend, "gleicher Name tritt der bestehenden Gruppe bei"

    # 2) Mit force_new_group: eine eigene Gruppe, TROTZ passendem Namen.
    store._data["managed_albums"] = [
        a for a in store._data["managed_albums"] if a["match_id"] != "match-neu"
    ]
    await albums_router.create_album(
        SyncAlbumRequest(match_id="match-neu", owner_account_id="konto-1",
                         album_name="Testalbum", force_new_group=True), request)
    eigen = {a.match_id: a.group_id for a in store.get_managed_albums()}["match-neu"]
    assert eigen != bestehend, "force_new_group muss den Namenstreffer schlagen"
