import pytest

from models.account import Account
from models.match import ManagedAlbum
from services import sync_service
from services.immich_client import AlbumNotFoundError


def account(account_id: str) -> Account:
    return Account(
        id=account_id,
        name=account_id,
        immich_url=f"http://192.168.1.{len(account_id) + 10}",
        api_key="key",
        color="#000",
        user_id=f"user-{account_id}",
    )


class StoreDoppel:
    """Test-Doppel des Stores, das Alben WIRKLICH haelt.

    `sync_service` liest den Datensatz innerhalb seines Schlosses neu
    (`_frisch`), weil ein Schnappschuss von vor dem Schloss jede Aenderung
    zurueckdreht, die dazwischen lag. Ein Doppel, das nur
    `update_managed_album` kennt, laesst diesen Weg nicht laufen — und haette
    ihn beim Einbau als „bricht die Tests" erscheinen lassen, obwohl die Tests
    nur unvollstaendig doppelten.

    Wer ein Album nicht mitgibt, doppelt damit den Fall „steht nicht im
    Bestand": Dann greift der Rueckfall auf die uebergebene Kopie.
    """

    def __init__(self, *alben):
        self.alben = {a.id: a for a in alben}
        self.geschrieben = []

    def get_managed_album(self, album_id):
        # Eine KOPIE, wie der echte Store: `get_managed_albums` baut bei jedem
        # Aufruf neue Objekte. Ein Doppel, das dieselbe Instanz zurueckgibt,
        # laesst Code durchgehen, der auf das Mitwandern einer Aenderung im
        # Objekt des Aufrufers baut.
        album = self.alben.get(album_id)
        return album.model_copy(deep=True) if album else None

    def update_managed_album(self, album):
        self.alben[album.id] = album
        self.geschrieben.append(album)

    def add_managed_album(self, album):
        self.alben[album.id] = album

    def group_id_for_name(self, _name):
        return "gruppe-testdoppel"


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


    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", fake_share)
    refs = [
        {"account_id": "owner", "person_id": "p1"},
        {"account_id": "participant", "person_id": "p2"},
    ]
    await sync_service.create_shared_album(
        "match", owner, [owner, participant, unrelated], refs, "Album", StoreDoppel(),
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

        async def get_album_assets_with_name(self, _album_id):
            # Namensuebernahme (#97) ist hier nicht Gegenstand des Tests —
            # derselbe Name wie der Bestand haelt sie ausdruecklich aus.
            return "Family", ["asset-1"]

        async def get_person_assets(self, _person_id):
            return [{"id": "asset-1"}]

        async def add_assets_to_album(self, _album_id, asset_ids):
            add_calls.append(asset_ids)

    async def skip_sharing(*_args):
        return []

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

    store = StoreDoppel(managed)
    entries = await sync_service.refresh_managed_album(managed, [owner], store)

    assert add_calls == []
    # Gemessen am BESTAND: Der Dienst arbeitet seit der zweiten Nacharbeit an
    # #79 auf einem im Schloss frisch gelesenen Datensatz, die Kopie des
    # Aufrufers wandert also nicht mehr mit — und das ist der Sinn der Sache.
    assert store.get_managed_album("managed-1").total_assets == 1
    assert entries[0].status == "success"


@pytest.mark.asyncio
async def test_refresh_adds_only_new_assets_and_updates_the_total(monkeypatch):
    add_calls: list[list[str]] = []

    class Client:
        def __init__(self, *_):
            pass

        async def get_album_assets(self, _album_id):
            return ["asset-1"]

        async def get_album_assets_with_name(self, _album_id):
            # Namensuebernahme (#97) ist hier nicht Gegenstand des Tests —
            # derselbe Name wie der Bestand haelt sie ausdruecklich aus.
            return "Family", ["asset-1"]

        async def get_person_assets(self, _person_id):
            return [{"id": "asset-1"}, {"id": "asset-2"}]

        async def add_assets_to_album(self, _album_id, asset_ids):
            add_calls.append(asset_ids)
            return [{"id": asset_id, "success": True} for asset_id in asset_ids]

    async def skip_sharing(*_args):
        return []

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

    store = StoreDoppel(managed)
    entries = await sync_service.refresh_managed_album(managed, [owner], store)

    assert add_calls == [["asset-2"]]
    # Gemessen am BESTAND: Der Dienst arbeitet seit der zweiten Nacharbeit an
    # #79 auf einem im Schloss frisch gelesenen Datensatz, die Kopie des
    # Aufrufers wandert also nicht mehr mit — und das ist der Sinn der Sache.
    assert store.get_managed_album("managed-1").total_assets == 2
    assert entries[0].message_key == "log_assets_added_to_album"
    assert entries[0].message_params == {"count": 1, "account": owner.name, "album": managed.album_name}


@pytest.mark.asyncio
async def test_refresh_reports_partial_failures_and_ignores_duplicates(monkeypatch):
    class Client:
        def __init__(self, *_):
            pass

        async def get_album_assets(self, _album_id):
            return ["asset-1"]

        async def get_album_assets_with_name(self, _album_id):
            # Namensuebernahme (#97) ist hier nicht Gegenstand des Tests —
            # derselbe Name wie der Bestand haelt sie ausdruecklich aus.
            return "Family", ["asset-1"]

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

    store = StoreDoppel(managed)
    entries = await sync_service.refresh_managed_album(managed, [owner], store)

    # Only the real success counts toward the total.
    # Gemessen am BESTAND: Der Dienst arbeitet seit der zweiten Nacharbeit an
    # #79 auf einem im Schloss frisch gelesenen Datensatz, die Kopie des
    # Aufrufers wandert also nicht mehr mit — und das ist der Sinn der Sache.
    assert store.get_managed_album("managed-1").total_assets == 2

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


# --------------------------- #97: Der Albumname aus Immich gewinnt beim Abgleich

def _konto_eins() -> Account:
    """Das Konto aus dem Bau-Brief zu #97 — offensichtlich erfundene Werte."""
    return Account(
        id="konto-1", name="Konto Eins", immich_url="http://beispiel.invalid",
        api_key="platzhalter", color="#111111", user_id="u1",
    )


def _album_fuer_namensuebernahme(**overrides) -> ManagedAlbum:
    basis = dict(
        id="managed-1", match_id="match-1", album_id="album-1",
        album_name="Alter Name", group_id="gruppe-1",
        owner_account_id="konto-1",
        person_refs=[{"account_id": "konto-1", "person_id": "person-1"}],
        created_at="2026-08-02T00:00:00+00:00",
    )
    basis.update(overrides)
    return ManagedAlbum(**basis)


def _immich_client_mit_namen(monkeypatch, name, bestand=("asset-1",), person_assets=None):
    """ImmichClient-Attrappe, die den Immich-Albumnamen mitliefert und die
    echten `GET /api/albums/{id}`-Aufrufe zählt (#97).

    `get_album_assets_with_name` ruft ihren EIGENEN `get_album_info` auf —
    genau wie die echte Klasse —, damit der Zähler den tatsächlichen
    Netzwerkaufruf misst, nicht nur den Aufruf der Hülle.

    `person_assets` ist standardmäßig deckungsgleich mit `bestand` (dann
    entstehen nie neue Assets — der bisherige Normalfall dieser Attrappe).
    Ein abweichender Wert lässt echte neue Assets entstehen, für Tests, die
    Namensübernahme UND Asset-Zuwachs gleichzeitig brauchen (Nacharbeit 2).
    """
    calls = {"get_album_info": 0}
    person_ids = bestand if person_assets is None else person_assets

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def get_album_info(self, _album_id):
            calls["get_album_info"] += 1
            return {"id": _album_id, "albumName": name}

        async def get_album_assets_with_name(self, album_id):
            info = await self.get_album_info(album_id)
            return info.get("albumName"), list(bestand)

        async def get_person_assets(self, _person_id):
            return [{"id": asset_id} for asset_id in person_ids]

        async def add_assets_to_album(self, _album_id, asset_ids):
            return [{"id": a, "success": True} for a in asset_ids]

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    return calls


@pytest.mark.asyncio
async def test_refresh_uebernimmt_den_aktuellen_namen_aus_immich(monkeypatch):
    """Nachweis 1 (#97): Ein abweichender Name aus Immich gewinnt — der BESTAND
    (`StoreDoppel`, das echte `update_managed_album`/`get_managed_album`-Verhalten
    nachbildet, keine Attrappe des Rueckgabewerts) trägt danach den neuen
    Namen. Das Protokoll trägt ZWEI Einträge: den Namenswechsel UND „keine
    neuen Assets" — Letzteres ist eine ZUSAETZLICHE Meldung, kein Ersatz dafür
    (Nacharbeit 1, technisch entschieden)."""
    owner = _konto_eins()
    managed = _album_fuer_namensuebernahme(album_name="Alter Name")
    calls = _immich_client_mit_namen(monkeypatch, "Neu in Immich")

    store = StoreDoppel(managed)
    entries = await sync_service.refresh_managed_album(managed, [owner], store)

    assert calls["get_album_info"] == 1, "GET /api/albums/{id} darf nur einmal laufen"
    assert store.get_managed_album("managed-1").album_name == "Neu in Immich"
    assert len(entries) == 2, entries
    assert entries[0].message_key == "log_album_name_adopted"
    assert entries[0].message_params == {"old_name": "Alter Name", "new_name": "Neu in Immich"}
    assert entries[1].message_key == "log_no_new_assets"


@pytest.mark.asyncio
async def test_refresh_zeigt_namensuebernahme_und_neue_assets_nebeneinander(monkeypatch):
    """Nacharbeit 2 (#97, Blindpruefer): „Zusaetzlich, kein Ersatz" war nur in
    EINER Richtung bewacht — ein Umbau zu `if not logs or name_entry is not
    None:` blieb bei den bisherigen 266 Faellen unentdeckt gruen, meldete dann
    aber bei Namensuebernahme UND neuen Assets faelschlich zusaetzlich „keine
    neuen Assets". Dieser Test deckt genau die fehlende Kombination ab."""
    owner = _konto_eins()
    managed = _album_fuer_namensuebernahme(album_name="Alter Name")
    _immich_client_mit_namen(
        monkeypatch, "Neu in Immich",
        bestand=("asset-1",), person_assets=("asset-1", "asset-2"),
    )

    store = StoreDoppel(managed)
    entries = await sync_service.refresh_managed_album(managed, [owner], store)

    assert [e.message_key for e in entries] == [
        "log_album_name_adopted", "log_assets_added_to_album",
    ], entries
    assert not any(e.message_key == "log_no_new_assets" for e in entries), entries


@pytest.mark.asyncio
async def test_refresh_ohne_namensaenderung_schreibt_keinen_namenseintrag(monkeypatch):
    """Nachweis 2 (#97): Gleicher Name -> kein Namens-Eintrag, Name unverändert."""
    owner = _konto_eins()
    managed = _album_fuer_namensuebernahme(album_name="Alter Name")
    _immich_client_mit_namen(monkeypatch, "Alter Name")

    store = StoreDoppel(managed)
    entries = await sync_service.refresh_managed_album(managed, [owner], store)

    assert not any(e.message_key == "log_album_name_adopted" for e in entries), entries
    assert store.get_managed_album("managed-1").album_name == "Alter Name"


@pytest.mark.asyncio
async def test_refresh_uebernimmt_den_namen_roh_auch_bei_sichtbar_gleichem_namen(monkeypatch):
    """Nacharbeit 2 (#97): 'Immich gewinnt' gilt WOERTLICH, nicht bereinigt.

    Ein Name, der sich nur durch Leerraum am Rand unterscheidet („Foo" gegen
    „Foo "), ist als Python-String ungleich — er wird uebernommen und roh
    gespeichert, auch wenn beide fuer einen Menschen gleich aussehen. Das ist
    keine Regression des Leerraum-Schutzes (der faengt nur einen Namen aus
    AUSSCHLIESSLICH Leerraum ab), sondern die bewusste Kehrseite von
    'woertlich, nicht bereinigt'."""
    owner = _konto_eins()
    managed = _album_fuer_namensuebernahme(album_name="Foo")
    _immich_client_mit_namen(monkeypatch, "Foo ")

    store = StoreDoppel(managed)
    entries = await sync_service.refresh_managed_album(managed, [owner], store)

    name_entries = [e for e in entries if e.message_key == "log_album_name_adopted"]
    assert len(name_entries) == 1, entries
    assert name_entries[0].message_params == {"old_name": "Foo", "new_name": "Foo "}
    assert store.get_managed_album("managed-1").album_name == "Foo "


def _leerraum_zeichen() -> list[str]:
    """Alle Codepunkte, die Python `str.strip()` als Leerraum faltet.

    Selbst gemessen (Owner-Vorgabe: keine Zahl abschreiben), nicht die vom
    Panel genannte Zahl uebernommen — 29 Zeichen zum Zeitpunkt dieses Baus.
    Kein Import einer fremden Liste: Aendert Python diese Menge je, aendert
    sich auch diese Liste automatisch mit.
    """
    return [chr(i) for i in range(0x110000) if chr(i).strip() == ""]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "immich_name",
    [None, ""] + _leerraum_zeichen() + ["".join(_leerraum_zeichen())],
)
async def test_refresh_behaelt_den_namen_wenn_immich_keinen_liefert(monkeypatch, immich_name):
    """Nachweis 3 (#97, erweitert in Nacharbeit 1 und 2): Kein, ein leerer
    oder ein NUR aus Leerraum bestehender Name aus Immich leert den Bestand
    nicht — parametrisiert ueber JEDEN Codepunkt, den Python als Leerraum
    faltet (siehe `_leerraum_zeichen`), plus alle 29 zusammen in einem
    String.

    Gemessen ohne den `.strip()`-Schutz (Fund von Blind- und Fremdpruefer):
    Ein Name aus reinem Leerraum ist in Python truthy und ungleich dem
    Bestandsnamen — er wurde uebernommen und hat den sichtbaren Namen
    geleert, obwohl `not immich_name` allein das nicht faengt. Dieselbe
    Faltung wie im Umbenennen-Router (`body.album_name.strip()`)."""
    owner = _konto_eins()
    managed = _album_fuer_namensuebernahme(album_name="Alter Name")
    _immich_client_mit_namen(monkeypatch, immich_name)

    store = StoreDoppel(managed)
    entries = await sync_service.refresh_managed_album(managed, [owner], store)

    assert not any(e.message_key == "log_album_name_adopted" for e in entries), entries
    assert store.get_managed_album("managed-1").album_name == "Alter Name"


@pytest.mark.asyncio
async def test_refresh_eines_geloeschten_albums_uebernimmt_keinen_namen(monkeypatch):
    """Nachweis 4 (#97): Der bisherige Weg bei gelöschtem Album bleibt
    unverändert — kein Speichern, kein Namens-Eintrag."""
    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def get_album_assets_with_name(self, album_id):
            raise AlbumNotFoundError(album_id)

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    owner = _konto_eins()
    managed = _album_fuer_namensuebernahme(album_name="Alter Name")

    store = StoreDoppel(managed)
    entries = await sync_service.refresh_managed_album(managed, [owner], store)

    assert [e.message_key for e in entries] == ["log_album_deleted"]
    assert store.geschrieben == [], "bei gelöschtem Album wird nicht gespeichert"
    assert store.get_managed_album("managed-1").album_name == "Alter Name"


@pytest.mark.asyncio
async def test_ein_abgleich_ruft_get_album_info_nur_einmal_auf(monkeypatch):
    """Nachweis 5 (#97): `GET /api/albums/{id}` läuft für den Namens-/
    Asset-Abruf pro Abgleich genau einmal, nicht zweimal — der Kern der
    'kein Doppelaufruf'-Zusage im Befund.

    Die Zusicherung gilt hier für ein Album mit EINEM Konto (`person_refs`
    enthält nur den Owner): `_share_album_if_needed` wird trotzdem aufgerufen,
    kehrt aber sofort zurück (`if not accounts_to_share: return logs`), noch
    bevor sie `get_album_user_ids` erreicht — deshalb bleibt es bei einem
    Aufruf. Mit einem weiteren Teilnehmer holt `get_album_user_ids` denselben
    Endpunkt ein ZWEITES Mal, UNABHÄNGIG davon, ob dieser Teilnehmer schon
    Mitglied ist — die Mitgliedschaftsprüfung braucht den Aufruf so oder so
    (gemessen per Wegwerf-Skript, Nacharbeit 2: 1 Aufruf ohne weiteren
    Teilnehmer, 2 Aufrufe mit einem neuen Teilnehmer, 2 Aufrufe mit einem
    bereits vorhandenen Teilnehmer). Das ist keine Regression dieses Slices,
    sondern der bereits vorher bestehende Weg des Teilens."""
    owner = _konto_eins()
    managed = _album_fuer_namensuebernahme(album_name="Alter Name")
    calls = _immich_client_mit_namen(
        monkeypatch, "Neu in Immich", bestand=("asset-1", "asset-2")
    )

    store = StoreDoppel(managed)
    await sync_service.refresh_managed_album(managed, [owner], store)

    assert calls["get_album_info"] == 1


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

    store = StoreDoppel(managed)
    await sync_service.extend_match(
        managed,
        participant,
        "person-2",
        "Family",
        None,
        [owner, participant],
        store,
    )

    assert add_calls == [["asset-2"]]
    # Gemessen am BESTAND: Der Dienst arbeitet seit #101 auf einem im Schloss
    # frisch gelesenen Datensatz, die Kopie des Aufrufers wandert also nicht
    # mehr mit — und das ist der Sinn der Sache. (Anders als bei Refresh und
    # Umbenennen: Dort kam der Umbau schon mit #79, hier erst mit #101.)
    assert store.get_managed_album("managed-1").total_assets == 2


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


def test_album_schloss_ueberlebt_einen_schleifenwechsel(monkeypatch):
    """Die Behauptung "Klasse behoben, nicht Instanz" — durch die ECHTE Funktion.

    Ein `asyncio.Lock` gehoert der Schleife, in der es zuerst UMKAEMPFT
    wurde. Ein Register, das nur nach `managed.id` schluesselt, liefert beim
    naechsten Lauf in einer ANDEREN Schleife dasselbe Objekt aus, und der
    Zugriff endet mit "is bound to a different event loop".

    ZWEI Fallen, beide gemessen und beide hier vermieden:
    * Ohne WETTSTREIT bindet sich das Schloss gar nicht — ein unbestrittenes
      `async with` beruehrt die Schleife nie. Die erste Fassung war deshalb
      in beide Richtungen gruen.
    * Baut der Test das Muster NACH, statt `refresh_managed_album` zu rufen,
      prueft er die Regel und nicht die Verdrahtung. Die Mutation an der
      Produktionszeile ueberlebte ihn (lehren.md §39, zum wiederholten Mal).
    """
    import asyncio

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def get_album_assets(self, _album_id):
            await asyncio.sleep(0.01)      # erzeugt den Wettstreit
            return []

        async def get_person_assets(self, _pid):
            return []

        async def add_assets_to_album(self, _album_id, _ids):
            return []

    async def skip_sharing(*_args, **_k):
        return []

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", skip_sharing)
    owner = account("owner")

    def frisches_album():
        return ManagedAlbum(
            id="managed-schloss",                     # DIESELBE Kennung
            match_id="m-schloss",
            album_id="ia-schloss",
            album_name="Testalbum",
            group_id="gruppe-1",
            owner_account_id=owner.id,
            person_refs=[{"account_id": owner.id, "person_id": "p1"}],
            created_at="2026-01-01T00:00:00+00:00",
        )

    async def umkaempft():
        await asyncio.gather(
            sync_service.refresh_managed_album(
                frisches_album(), [owner], StoreDoppel(frisches_album())),
            sync_service.refresh_managed_album(
                frisches_album(), [owner], StoreDoppel(frisches_album())),
        )
        return True

    # Zwei getrennte Schleifen, dasselbe Album.
    assert asyncio.run(umkaempft())
    assert asyncio.run(umkaempft()), "zweite Schleife scheiterte"


@pytest.mark.asyncio
async def test_rename_managed_album_updates_immich_and_persisted_name(monkeypatch):
    updates: list[tuple[str, dict]] = []

    class Client:
        def __init__(self, *_):
            pass

        async def update_album(self, album_id, payload):
            updates.append((album_id, payload))
            return {"id": album_id, **payload}

    owner = account("owner")
    managed = ManagedAlbum(
        id="managed-1",
        match_id="match-1",
        album_id="album-1",
        album_name="Old family name",
        # `group_id` ist seit #78 Pflicht (min_length=1). Der zugelieferte
        # Zweig entstand davor; genau das haben wir ihm am 21.09. als den
        # einen Punkt genannt, der beim Rebase Hand braucht.
        group_id="gruppe-1",
        owner_account_id=owner.id,
        person_refs=[],
        created_at="2026-09-10T00:00:00+00:00",
    )
    monkeypatch.setattr(sync_service, "ImmichClient", Client)

    store = StoreDoppel(managed)
    logs = await sync_service.rename_managed_album(
        managed, owner, "New family name", store
    )

    assert updates == [("album-1", {"albumName": "New family name"})]
    # Gemessen am BESTAND, nicht an der Kopie des Aufrufers: Seit der zweiten
    # Nacharbeit an #79 arbeitet der Dienst auf einem im Schloss frisch
    # gelesenen Datensatz, und das ist der Sinn der Sache — die Kopie des
    # Aufrufers ist womoeglich alt. Was zaehlt, ist, was gespeichert wurde.
    assert store.get_managed_album("managed-1").album_name == "New family name"
    assert [a.album_name for a in store.geschrieben] == ["New family name"]
    assert logs[0].status == "success"
    assert logs[0].message_key == "log_album_renamed"
