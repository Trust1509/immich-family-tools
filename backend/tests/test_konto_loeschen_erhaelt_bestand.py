"""Rot-Beweise gegen den ECHTEN `ConfigStore` fuer #99/#112 (Owner-Entscheid
28.09.2026): Beim Loeschen eines Kontos verschwindet ausschliesslich das
Konto selbst und seine `person_refs` in jedem Album — sonst nichts.

Vorher raeumte `delete_account` weit mehr auf: Ein Album mit weniger als
zwei verbleibenden Personen fiel still weg, `dismissed_match_ids` und
`synced_name_match_ids` wurden GANZ geleert, und ein Protokolleintrag
verschwand schon, wenn der Kontoname als Teilwort in seinem `details`-Text
vorkam. Jede dieser vier Zusicherungen bekommt hier ihren eigenen Rot-Beweis
gegen den echten Store — keine Attrappe, kein HTTP.

Alle Daten erfunden; das Repo ist oeffentlich.
"""
from datetime import datetime, timezone

from models.account import AccountCreate
from models.match import ManagedAlbum, SyncLogEntry
from services.config_store import ConfigStore


def _konto(store: ConfigStore, name: str):
    return store.add_account(
        AccountCreate(name=name, immich_url="http://192.168.1.2", api_key="platzhalter")
    )


def _ref(account) -> dict:
    return {
        "account_id": account.id,
        "person_id": f"person-{account.id}",
        "person_name": f"Person von {account.name}",
        "account_name": account.name,
        "account_color": account.color,
    }


def _album(store: ConfigStore, *, album_id: str, owner_id: str, person_refs: list[dict]):
    album = ManagedAlbum(
        id=album_id,
        match_id=f"m-{album_id}",
        album_id=f"immich-{album_id}",
        album_name="Testalbum",
        group_id=f"gruppe-{album_id}",
        owner_account_id=owner_id,
        person_refs=person_refs,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    store.add_managed_album(album)
    return album


def _album_im_bestand(store: ConfigStore, album_id: str) -> ManagedAlbum | None:
    return next((a for a in store.get_managed_albums() if a.id == album_id), None)


# --------------------------------------------------------------------------
# Alben bleiben, unabhaengig von der Zahl verbleibender Personen
# --------------------------------------------------------------------------


def test_album_mit_einer_verbleibenden_person_bleibt(tmp_path):
    """Besitzer geloescht, EINE fremde Person bleibt: Album bleibt in Verwaltung."""
    store = ConfigStore(str(tmp_path / "accounts.json"))
    besitzer = _konto(store, "Besitzer")
    teilnehmer = _konto(store, "Teilnehmer")
    _album(store, album_id="a1", owner_id=besitzer.id,
           person_refs=[_ref(besitzer), _ref(teilnehmer)])

    assert store.delete_account(besitzer.id)

    album = _album_im_bestand(store, "a1")
    assert album is not None, "Album mit einer verbleibenden Person ist verschwunden"
    assert [r["account_id"] for r in album.person_refs] == [teilnehmer.id]


def test_album_mit_null_verbleibenden_personen_bleibt(tmp_path):
    """Besitzer geloescht, NIEMAND bleibt: Album bleibt trotzdem in Verwaltung."""
    store = ConfigStore(str(tmp_path / "accounts.json"))
    besitzer = _konto(store, "Besitzer")
    _album(store, album_id="a1", owner_id=besitzer.id, person_refs=[_ref(besitzer)])

    assert store.delete_account(besitzer.id)

    album = _album_im_bestand(store, "a1")
    assert album is not None, "Album mit null verbleibenden Personen ist verschwunden"
    assert album.person_refs == []
    # owner_account_id bleibt UNVERAENDERT — das erzeugt den verwaisten
    # Zustand, den die Albumliste beim Lesen markiert (Owner: markieren,
    # nicht umschreiben).
    assert album.owner_account_id == besitzer.id


def test_album_mit_zwei_verbleibenden_personen_bei_teilnehmer_loeschung_bleibt(tmp_path):
    """Ein TEILNEHMER (nicht der Besitzer) wird geloescht: >= 2 bleiben ohnehin."""
    store = ConfigStore(str(tmp_path / "accounts.json"))
    besitzer = _konto(store, "Besitzer")
    a = _konto(store, "TeilnehmerA")
    b = _konto(store, "TeilnehmerB")
    _album(store, album_id="a1", owner_id=besitzer.id,
           person_refs=[_ref(besitzer), _ref(a), _ref(b)])

    assert store.delete_account(a.id)

    album = _album_im_bestand(store, "a1")
    assert album is not None
    assert {r["account_id"] for r in album.person_refs} == {besitzer.id, b.id}
    assert album.owner_account_id == besitzer.id


def test_album_mit_einer_verbleibenden_person_bei_teilnehmer_loeschung_bleibt(tmp_path):
    """Ein Teilnehmer wird geloescht, nur der Besitzer bleibt: bleibt trotzdem."""
    store = ConfigStore(str(tmp_path / "accounts.json"))
    besitzer = _konto(store, "Besitzer")
    teilnehmer = _konto(store, "Teilnehmer")
    _album(store, album_id="a1", owner_id=besitzer.id,
           person_refs=[_ref(besitzer), _ref(teilnehmer)])

    assert store.delete_account(teilnehmer.id)

    album = _album_im_bestand(store, "a1")
    assert album is not None
    assert [r["account_id"] for r in album.person_refs] == [besitzer.id]
    assert album.owner_account_id == besitzer.id


def test_konto_ohne_alben_wird_trotzdem_sauber_geloescht(tmp_path):
    """Konto ohne jedes Album: loescht sich normal, ohne Nebenwirkung."""
    store = ConfigStore(str(tmp_path / "accounts.json"))
    konto = _konto(store, "Einsam")

    assert store.delete_account(konto.id)
    assert store.list_accounts() == []


# --------------------------------------------------------------------------
# Ablehnungen und Namensmerker bleiben VOLLSTAENDIG
# --------------------------------------------------------------------------


def test_ablehnungen_und_namensmerker_bleiben_unveraendert(tmp_path):
    store = ConfigStore(str(tmp_path / "accounts.json"))
    besitzer = _konto(store, "Besitzer")
    store.dismiss_match("md5-irgendein-paar")
    store.mark_names_synced("md5-anderes-paar")

    assert store.delete_account(besitzer.id)

    assert store.get_dismissed_ids() == {"md5-irgendein-paar"}
    assert store.get_synced_name_ids() == {"md5-anderes-paar"}


# --------------------------------------------------------------------------
# Das Protokoll bleibt VOLLSTAENDIG stehen
# --------------------------------------------------------------------------


def test_protokoll_bleibt_vollstaendig_auch_mit_kontoname_als_teilwort(tmp_path):
    """Frueher: ein Teilwort-Treffer im `details`-Text loeschte den Eintrag mit.

    Gemessen am echten Store (#112): "Name 'Carlas Mama' abgeglichen"
    verschwand beim Loeschen von "Carla".
    """
    store = ConfigStore(str(tmp_path / "accounts.json"))
    besitzer = _konto(store, "Carla")
    store.append_log([SyncLogEntry(
        id="log-teilwort", timestamp=datetime.now(timezone.utc).isoformat(),
        action="sync_names", details="Name 'Carlas Mama' abgeglichen",
        status="success",
    )])

    assert store.delete_account(besitzer.id)

    verlauf = [e.id for e in store.get_log()]
    assert "log-teilwort" in verlauf, "Eintrag mit Kontoname als Teilwort ist verschwunden"


def test_protokoll_bleibt_vollstaendig_auch_bei_undo_data_auf_das_konto(tmp_path):
    """Frueher: ein Eintrag, dessen `undo_data.account_id` passte, fiel weg."""
    store = ConfigStore(str(tmp_path / "accounts.json"))
    besitzer = _konto(store, "Besitzer")
    store.append_log([SyncLogEntry(
        id="log-undo", timestamp=datetime.now(timezone.utc).isoformat(),
        action="sync_names", details="Name synchronisiert",
        status="success",
        undo_data={"account_id": besitzer.id, "person_id": "p1", "previous_name": "Alt"},
    )])

    assert store.delete_account(besitzer.id)

    verlauf = [e.id for e in store.get_log()]
    assert "log-undo" in verlauf, "Eintrag mit undo_data auf das geloeschte Konto ist verschwunden"
