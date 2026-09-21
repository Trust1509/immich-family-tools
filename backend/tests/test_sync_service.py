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

        def group_id_for_name(self, _name):
            return "gruppe-testdoppel"

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", fake_share)
    refs = [
        {"account_id": "owner", "person_id": "p1"},
        {"account_id": "participant", "person_id": "p2"},
    ]
    await sync_service.create_shared_album(
        "match", owner, [owner, participant, unrelated], refs, "Album", Store(),
        group_id="gruppe-testdoppel",
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
        group_id="gruppe-family",
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
            return [{"id": asset_id, "success": True} for asset_id in asset_ids]

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
        group_id="gruppe-family",
        owner_account_id=owner.id,
        person_refs=[{"account_id": owner.id, "person_id": "person-1"}],
        created_at="2026-08-02T00:00:00+00:00",
    )
    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", skip_sharing)

    entries = await sync_service.refresh_managed_album(managed, [owner], Store())

    assert add_calls == [["asset-2"]]
    assert managed.total_assets == 2
    assert entries[0].message_key == "log_assets_added_to_album"
    assert entries[0].message_params == {"count": 1, "account": owner.name, "album": managed.album_name}


@pytest.mark.asyncio
async def test_refresh_reports_partial_failures_and_ignores_duplicates(monkeypatch):
    class Client:
        def __init__(self, *_):
            pass

        async def get_album_assets(self, _album_id):
            return ["asset-1"]

        async def get_person_assets(self, _person_id):
            return [{"id": "asset-1"}, {"id": "asset-2"}, {"id": "asset-3"}, {"id": "asset-4"}]

        async def add_assets_to_album(self, _album_id, asset_ids):
            return [
                {"id": "asset-2", "success": True},
                {"id": "asset-3", "success": False, "error": "duplicate"},
                {"id": "asset-4", "success": False, "error": "permission"},
            ]

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
        group_id="gruppe-family",
        owner_account_id=owner.id,
        person_refs=[{"account_id": owner.id, "person_id": "person-1"}],
        created_at="2026-08-02T00:00:00+00:00",
    )
    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", skip_sharing)

    entries = await sync_service.refresh_managed_album(managed, [owner], Store())

    # Only the real success counts toward the total.
    assert managed.total_assets == 2

    success_entries = [e for e in entries if e.status == "success"]
    failure_entries = [e for e in entries if e.status == "error"]

    assert len(success_entries) == 1
    assert success_entries[0].message_key == "log_assets_added_to_album"
    assert success_entries[0].message_params["count"] == 1

    # Exactly one failure entry — the duplicate is silently ignored.
    assert len(failure_entries) == 1
    assert failure_entries[0].message_key == "log_assets_partial_failure"
    assert failure_entries[0].message_params == {"count": 1, "account": owner.name}
    assert "1 Assets von 'owner' konnten nicht hinzugefügt werden" in failure_entries[0].details


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
            return [{"id": asset_id, "success": True} for asset_id in asset_ids]

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
        group_id="gruppe-family",
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


# ----------------------------------------------------------------------
# Verdrahtung der Gruppenkennung (#78)
#
# Die Regel selbst deckt test_config_store ab. Hier geht es um die
# VERDRAHTUNG an der Erzeugungsstelle — die Luecke, die das Panel gemessen
# hat: Beide Zuweisungen durch eine feste Kennung ersetzt, und die volle
# Suite blieb gruen, weil das Store-Doppel oben eine Konstante liefert und
# damit genau das verdeckt, was zu pruefen waere.
#
# Deshalb hier ein ECHTER ConfigStore, kein Doppel.
# ----------------------------------------------------------------------


def _store_mit_album(tmp_path, album_name: str, group_id: str):
    import json

    from services.config_store import ConfigStore

    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {},
        "managed_albums": [{
            "id": "vorhanden", "match_id": "m-alt", "album_id": "ia-alt",
            "album_name": album_name, "group_id": group_id,
            "owner_account_id": "owner", "person_refs": [],
            "created_at": "2026-01-01T00:00:00+00:00", "last_synced_at": None,
            "total_assets": 0, "status": "active",
        }],
    }), encoding="utf-8")
    return ConfigStore(str(pfad))


async def _lege_album_an(monkeypatch, store, album_name: str):
    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def create_album(self, _name, _ids):
            return {"id": "neues-immich-album"}

        async def get_person_assets(self, _pid):
            return []

    async def fake_share(*_a, **_k):
        return []

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", fake_share)
    owner = account("owner")
    # Wie ein echter Aufrufer: erst aufloesen, dann uebergeben. Die Kennung
    # ist Pflicht — es gibt keinen stillen Rueckfall mehr.
    return await sync_service.create_shared_album(
        "match-neu", owner, [owner],
        [{"account_id": "owner", "person_id": "p1"}],
        album_name, store,
        group_id=store.resolve_group_id(album_name),
    )


@pytest.mark.asyncio
async def test_neues_album_tritt_der_gruppe_mit_gleichem_namen_bei(monkeypatch, tmp_path):
    """Die Zuordnungsregel muss beim Anlegen WIRKLICH angewandt werden."""
    store = _store_mit_album(tmp_path, "Testalbum", "gruppe-1")

    managed, _ = await _lege_album_an(monkeypatch, store, "  TESTALBUM ")

    assert managed.group_id == "gruppe-1"


@pytest.mark.asyncio
async def test_neues_album_mit_neuem_namen_oeffnet_eine_eigene_gruppe(monkeypatch, tmp_path):
    store = _store_mit_album(tmp_path, "Testalbum", "gruppe-1")

    managed, _ = await _lege_album_an(monkeypatch, store, "Ganz anders")

    assert managed.group_id
    assert managed.group_id != "gruppe-1"


@pytest.mark.asyncio
async def test_neues_album_landet_mit_seiner_kennung_im_speicher(monkeypatch, tmp_path):
    """Die Kennung muss auch GESPEICHERT werden, nicht nur zurueckgegeben."""
    store = _store_mit_album(tmp_path, "Testalbum", "gruppe-1")

    managed, _ = await _lege_album_an(monkeypatch, store, "Testalbum")

    gespeichert = {a.id: a.group_id for a in store.get_managed_albums()}
    assert gespeichert[managed.id] == "gruppe-1"


@pytest.mark.asyncio
async def test_verknuepftes_album_tritt_der_gruppe_mit_gleichem_namen_bei(monkeypatch, tmp_path):
    """Auch der Verknuepfungspfad muss die Zuordnungsregel anwenden.

    `link_existing_album` hatte bis zur Nacharbeit KEINEN einzigen Test
    (Blindpruefer 20.09.2026); die Mutation `group_id="feste-falsche-kennung"`
    an dieser Stelle blieb gruen, waehrend dieselbe Mutation an
    `create_shared_album` gefangen wurde. Eine Defektklasse an der kleineren
    Stelle behoben und an der groesseren stehen gelassen — genau das Muster,
    das dieses Projekt schon mehrfach getroffen hat.
    """
    store = _store_mit_album(tmp_path, "Testalbum", "gruppe-1")

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def get_album_assets(self, _album_id):
            return []

        async def get_person_assets(self, _pid):
            return []

        async def add_assets_to_album(self, _album_id, _ids):
            return []

    async def fake_share(*_a, **_k):
        return []

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", fake_share)
    owner = account("owner")

    managed, _ = await sync_service.link_existing_album(
        match_id="match-verknuepft",
        owner_account=owner,
        album_id="immich-bestehend",
        album_name="  TESTALBUM ",
        all_accounts=[owner],
        person_refs=[{"account_id": "owner", "person_id": "p1"}],
        store=store,
        group_id=store.resolve_group_id("  TESTALBUM "),
    )

    assert managed is not None
    assert managed.group_id == "gruppe-1"


@pytest.mark.asyncio
async def test_verknuepfen_folgt_der_uebergebenen_kennung(monkeypatch, tmp_path):
    """Die uebergebene Gruppe schlaegt den Namen — auch beim Verknuepfen.

    Gemessen vom Blindpruefer: Die Mutation, die `group_id` hier verwirft und
    wieder ueber den Namen aufloest, ueberlebte die volle Suite. Der
    vorhandene Test reichte nicht, weil er die Kennung gar nicht uebergab und
    damit nur den Rueckfall pruefte.
    """
    store = _store_mit_album(tmp_path, "Testalbum", "gruppe-1")

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def get_album_assets(self, _album_id):
            return []

        async def get_person_assets(self, _pid):
            return []

        async def add_assets_to_album(self, _album_id, _ids):
            return []

    async def fake_share(*_a, **_k):
        return []

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", fake_share)
    owner = account("owner")

    managed, _ = await sync_service.link_existing_album(
        match_id="match-verknuepft",
        owner_account=owner,
        album_id="immich-bestehend",
        album_name="Testalbum",          # wuerde gruppe-1 treffen
        all_accounts=[owner],
        person_refs=[{"account_id": "owner", "person_id": "p1"}],
        store=store,
        group_id="eigene-gruppe",        # schlaegt den Namen
    )

    assert managed is not None
    assert managed.group_id == "eigene-gruppe"
