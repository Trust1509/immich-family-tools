"""Zwei Anfragen fuer EINEN Treffer duerfen kein zweites Album anlegen (#86).

Der Anlass ist ein Doppelklick auf „Album erstellen": zwei gleichzeitige
Anfragen mit derselben `match_id`. Beide liefen durch die Dublettensperre,
bevor eine von ihnen gespeichert hatte — Ergebnis waren zwei verwaltete
Albumeintraege fuer einen Treffer und zwei Alben in Immich.

Der Owner hat die Richtung entschieden (Kommentar in #86): **idempotent
anlegen**. Der zweite Klick bekommt KEINEN Fehler, sondern Erfolg mit dem
bereits bestehenden Album plus einen Protokolleintrag „gab es schon". Das
haelt nebenbei die Reihenfolge-Regel ein, um die sich diese Datei dreimal
gestritten hat: Wer nicht ablehnt, kann auch nicht hinter einem
Schreibvorgang ablehnen.

Die Sperre schluesselt auf die `match_id`, nicht auf den Albumnamen — zwei
Anfragen mit derselben Kennung und VERSCHIEDENEN Namen naehmen sonst
verschiedene Schloesser und kaemen beide durch. Genau das prueft
`test_gleiche_kennung_verschiedene_namen`.
"""
import asyncio
import json as _json
from types import SimpleNamespace

import pytest

KONTEN = {
    "konto-1": {"id": "konto-1", "name": "Konto Eins",
                "immich_url": "http://beispiel.invalid", "api_key": "platzhalter-1",
                "color": "#111111", "user_id": "u1"},
    "konto-2": {"id": "konto-2", "name": "Konto Zwei",
                "immich_url": "http://beispiel.invalid", "api_key": "platzhalter-2",
                "color": "#222222", "user_id": "u2"},
}


def _treffer(nr):
    return SimpleNamespace(
        id=f"match-{nr}",
        person_a=SimpleNamespace(account_id="konto-1", person_id=f"p{nr}a",
                                 person_name=f"A{nr}", account_name="Konto Eins",
                                 account_color="#111111"),
        person_b=SimpleNamespace(account_id="konto-2", person_id=f"p{nr}b",
                                 person_name=f"B{nr}", account_name="Konto Zwei",
                                 account_color="#222222"),
    )


def _store(tmp_path):
    from services.config_store import ConfigStore
    pfad = tmp_path / "accounts.json"
    pfad.write_text(_json.dumps({"accounts": KONTEN, "managed_albums": []}),
                    encoding="utf-8")
    return ConfigStore(str(pfad))


def _immich_attrappe(monkeypatch, angelegte: list):
    """Ein Immich, das jede Anlage mitzaehlt.

    Die Zahl der verwalteten Eintraege allein wuerde den Fall nicht ganz
    treffen: Sie sagt, was WIR gespeichert haben, nicht, was DRAUSSEN
    entstanden ist. Beim Doppelklick sind beide Zahlen der Schaden.
    """
    from services import sync_service

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def create_album(self, name, _ids):
            await asyncio.sleep(0)   # das Fenster, in dem der zweite Klick ankommt
            angelegte.append(name)
            return {"id": f"immich-{len(angelegte)}"}

        async def get_person_assets(self, _pid):
            await asyncio.sleep(0)
            return []

        async def get_album(self, album_id):
            await asyncio.sleep(0)
            return {"id": album_id, "albumName": "Bestehendes Album"}

        async def add_assets_to_album(self, _album_id, _ids):
            await asyncio.sleep(0)
            return []

    async def ohne_teilen(*_a, **_k):
        return []

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)
    return Client


# --------------------------------------------------------------- Vorschlagsweg

@pytest.mark.asyncio
async def test_zwei_gleichzeitige_anlagen_fuer_denselben_treffer(tmp_path, monkeypatch):
    """Der Doppelklick selbst: zweimal dieselbe `match_id`, gleichzeitig."""
    from models.match import SyncAlbumRequest
    from routers import albums as albums_router
    import routers.faces as faces

    store = _store(tmp_path)
    angelegte: list = []
    _immich_attrappe(monkeypatch, angelegte)

    async def hole_matches(_request):
        return [_treffer(1)]

    monkeypatch.setattr(faces, "get_matches", hole_matches)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)))

    def anfrage():
        return SyncAlbumRequest(match_id="match-1", owner_account_id="konto-1",
                                album_name="Familie Ohnesorg")

    await asyncio.gather(
        albums_router.create_album(anfrage(), request),
        albums_router.create_album(anfrage(), request),
    )

    alben = store.get_managed_albums()
    assert len(alben) == 1, f"{len(alben)} verwaltete Alben fuer EINEN Treffer"
    assert len(angelegte) == 1, f"{len(angelegte)} Alben in Immich angelegt"


@pytest.mark.asyncio
async def test_gleiche_kennung_verschiedene_namen(tmp_path, monkeypatch):
    """Die Sperre haengt an der Kennung, nicht am Namen.

    Ein Namensschloss allein reicht hier nicht: Zwei Anfragen mit derselben
    `match_id`, aber verschiedenen Albumnamen naehmen verschiedene Schloesser
    und kaemen beide durch. Der Fall ist nicht kuenstlich — die Oberflaeche
    schlaegt den Personennamen vor, und der laesst sich vor dem zweiten Klick
    aendern.
    """
    from models.match import SyncAlbumRequest
    from routers import albums as albums_router
    import routers.faces as faces

    store = _store(tmp_path)
    angelegte: list = []
    _immich_attrappe(monkeypatch, angelegte)

    async def hole_matches(_request):
        return [_treffer(1)]

    monkeypatch.setattr(faces, "get_matches", hole_matches)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)))

    await asyncio.gather(
        albums_router.create_album(
            SyncAlbumRequest(match_id="match-1", owner_account_id="konto-1",
                             album_name="Erster Name"), request),
        albums_router.create_album(
            SyncAlbumRequest(match_id="match-1", owner_account_id="konto-1",
                             album_name="Zweiter Name"), request),
    )

    assert len(store.get_managed_albums()) == 1
    assert len(angelegte) == 1


@pytest.mark.asyncio
async def test_der_zweite_klick_meldet_erfolg_mit_dem_bestehenden_album(
        tmp_path, monkeypatch):
    """Nacheinander: kein Fehler, sondern ein Eintrag „gab es schon".

    Der Owner-Entscheid nennt beides: Erfolg — damit ein hektischer zweiter
    Klick nicht bestraft wird — UND einen sichtbaren Eintrag, damit der
    Nutzer merkt, dass sein zweiter Klick etwas anderes getan hat als sein
    erster.
    """
    from models.match import SyncAlbumRequest
    from routers import albums as albums_router
    import routers.faces as faces

    store = _store(tmp_path)
    angelegte: list = []
    _immich_attrappe(monkeypatch, angelegte)

    async def hole_matches(_request):
        return [_treffer(1)]

    monkeypatch.setattr(faces, "get_matches", hole_matches)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)))

    def anfrage():
        return SyncAlbumRequest(match_id="match-1", owner_account_id="konto-1",
                                album_name="Familie Ohnesorg")

    await albums_router.create_album(anfrage(), request)
    zweite = await albums_router.create_album(anfrage(), request)

    assert len(store.get_managed_albums()) == 1
    assert len(angelegte) == 1

    assert zweite, "der zweite Aufruf gibt kein Protokoll zurueck"
    eintrag = zweite[-1]
    assert eintrag.status == "success", (
        "der zweite Klick meldet einen Fehler — der Entscheid war Erfolg")
    assert eintrag.message_key == "log_album_already_exists", eintrag.message_key
    assert eintrag.message_params.get("album") == "Familie Ohnesorg"

    # Und er steht im Protokoll, nicht nur in der Antwort: Wer den zweiten
    # Klick spaeter erklaeren muss, liest das Protokoll.
    im_protokoll = [e for e in store.get_log()
                    if e.message_key == "log_album_already_exists"]
    assert len(im_protokoll) == 1, im_protokoll


# ------------------------------------------------------------- manueller Weg

def _manuelle_umgebung(monkeypatch, store):
    from services import sync_service
    from models.match import SyncLogEntry
    import uuid as _uuid

    umbenannt: list = []

    async def ohne_namen(accounts_persons, canonical_name):
        umbenannt.append(canonical_name)
        return [SyncLogEntry(id=str(_uuid.uuid4()), timestamp="t",
                             action="sync_name", details="x", status="success",
                             person_id=pid)
                for _acc, pid in accounts_persons]

    class Konto:
        async def get_person(self, _pid):
            return {"id": _pid}

    class Pool:
        def get_for_account(self, _acc):
            return Konto()

    monkeypatch.setattr(sync_service, "sync_names_multi", ohne_namen)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        store=store, client_pool=Pool())))
    return request, umbenannt


@pytest.mark.asyncio
async def test_zwei_gleichzeitige_manuelle_anlagen_fuer_denselben_treffer(
        tmp_path, monkeypatch):
    """Dieselbe Luecke am manuellen Weg — zwei Tueren, zwei Proben."""
    from models.match import SyncNamesMultiRequest, MultiSyncPersonEntry
    from routers import albums as albums_router

    store = _store(tmp_path)
    angelegte: list = []
    _immich_attrappe(monkeypatch, angelegte)
    request, _ = _manuelle_umgebung(monkeypatch, store)

    def anfrage():
        return SyncNamesMultiRequest(
            persons=[MultiSyncPersonEntry(account_id="konto-1", person_id="p1"),
                     MultiSyncPersonEntry(account_id="konto-2", person_id="p2")],
            canonical_name="Oma Erna",
            album_name="Oma Erna",
            owner_account_id="konto-1",
        )

    await asyncio.gather(
        albums_router.sync_names_multi(anfrage(), request),
        albums_router.sync_names_multi(anfrage(), request),
    )

    assert len(store.get_managed_albums()) == 1
    assert len(angelegte) == 1


@pytest.mark.asyncio
async def test_der_zweite_manuelle_aufruf_benennt_trotzdem_um(tmp_path, monkeypatch):
    """Idempotent heisst NICHT: der zweite Aufruf tut gar nichts.

    Dieser Endpunkt gleicht zuerst NAMEN ab und legt danach optional ein
    Album an. Nur die Anlage ist doppelt; das Umbenennen soll weiterhin
    laufen. Vorher konnte man das gar nicht messen — die Dublettensperre
    lehnte den ganzen Aufruf ab, bevor irgendetwas abgeglichen war.
    """
    from models.match import SyncNamesMultiRequest, MultiSyncPersonEntry
    from routers import albums as albums_router

    store = _store(tmp_path)
    angelegte: list = []
    _immich_attrappe(monkeypatch, angelegte)
    request, umbenannt = _manuelle_umgebung(monkeypatch, store)

    def anfrage():
        return SyncNamesMultiRequest(
            persons=[MultiSyncPersonEntry(account_id="konto-1", person_id="p1"),
                     MultiSyncPersonEntry(account_id="konto-2", person_id="p2")],
            canonical_name="Oma Erna",
            album_name="Oma Erna",
            owner_account_id="konto-1",
        )

    await albums_router.sync_names_multi(anfrage(), request)
    logs = await albums_router.sync_names_multi(anfrage(), request)

    assert umbenannt == ["Oma Erna", "Oma Erna"], (
        "der zweite Aufruf hat die Namen nicht mehr abgeglichen")
    assert len(store.get_managed_albums()) == 1
    assert len(angelegte) == 1
    assert any(e.message_key == "log_album_already_exists" for e in logs), (
        "der zweite Aufruf sagt nicht, dass es das Album schon gab")


# ------------------------------------------- Kollision der manuellen Kennung

# Gefunden vom Fremdpruefer (22.09.2026) und hier reproduziert: Die manuelle
# Kennung ist `manual_<name>_<owner[:8]>` — die ausgewaehlten Personen stehen
# NICHT darin. Zwei verschiedene Personengruppen mit demselben kanonischen
# Namen und demselben Owner bekommen deshalb DIESELBE Kennung.
#
# Vor der Umstellung auf idempotentes Anlegen lehnte der Endpunkt diesen Fall
# mit 409 ab, und zwar VOR dem Umbenennen — es geschah also nichts. Nach der
# Umstellung wurden die Personen umbenannt, das Album des FREMDEN Paares
# gefunden und dem Aufrufer „Erfolg, gab es schon" gemeldet. Das ist die
# schlimmere Form: ein Teilvollzug, als Erfolg gemeldet.
#
# Die Kennung selbst zu aendern waere eine Datenwanderung (bestehende manuelle
# Alben tragen die alte) und gehoert nicht in diesen Slice.

def _paar(a, b):
    from models.match import MultiSyncPersonEntry
    return [MultiSyncPersonEntry(account_id="konto-1", person_id=a),
            MultiSyncPersonEntry(account_id="konto-2", person_id=b)]


@pytest.mark.asyncio
async def test_gleiche_kennung_andere_personen_wird_abgelehnt(tmp_path, monkeypatch):
    """Nacheinander: Der zweite Aufruf darf NICHTS tun und muss ablehnen."""
    from models.match import SyncNamesMultiRequest
    from routers import albums as albums_router
    import errors

    store = _store(tmp_path)
    angelegte: list = []
    _immich_attrappe(monkeypatch, angelegte)
    request, umbenannt = _manuelle_umgebung(monkeypatch, store)

    def anfrage(a, b):
        return SyncNamesMultiRequest(
            persons=_paar(a, b), canonical_name="Alex", album_name="Alex",
            owner_account_id="konto-1")

    await albums_router.sync_names_multi(anfrage("alice-a", "alice-b"), request)
    assert umbenannt == ["Alex"]

    with pytest.raises(errors.AppError) as fehler:
        await albums_router.sync_names_multi(anfrage("alex-c", "alex-d"), request)

    assert fehler.value.status_code == 409, fehler.value.status_code
    # Den SCHLUESSEL festnageln, nicht nur die Zahl: Heute traegt genau eine
    # Meldung im Katalog 409, also haelt der Statuscode zufaellig. Kommt eine
    # zweite dazu, prueft dieser Fall sonst nichts mehr (Blindpruefer,
    # Nacharbeit 1).
    assert fehler.value.key == "err_manual_match_id_collision", fehler.value.key

    # Und der Kern: Es wurde NICHTS getan. Kein zweites Umbenennen, kein
    # zweites Album, kein „Erfolg" fuer einen Vorgang, der nicht stattfand.
    assert umbenannt == ["Alex"], (
        "der abgelehnte Aufruf hat trotzdem umbenannt — eine Ablehnung hinter "
        "einem Schreibvorgang")
    assert len(angelegte) == 1
    assert len(store.get_managed_albums()) == 1


@pytest.mark.asyncio
async def test_gleiche_kennung_andere_personen_gleichzeitig(tmp_path, monkeypatch):
    """Und im Rennen: Die fruehe Schranke sieht das Album noch nicht.

    Beide Aufrufe kommen an der Vorabpruefung vorbei, weil zu dem Zeitpunkt
    noch kein Album existiert. Der zweite darf dann NICHT „gab es schon"
    melden — das waere dieselbe Luege, nur seltener. Ablehnen kann er auch
    nicht mehr, weil da bereits umbenannt wurde; also meldet er einen
    FEHLEREINTRAG im Protokoll.
    """
    from models.match import SyncNamesMultiRequest
    from routers import albums as albums_router

    store = _store(tmp_path)
    angelegte: list = []
    _immich_attrappe(monkeypatch, angelegte)
    request, _ = _manuelle_umgebung(monkeypatch, store)

    def anfrage(a, b):
        return SyncNamesMultiRequest(
            persons=_paar(a, b), canonical_name="Alex", album_name="Alex",
            owner_account_id="konto-1")

    ergebnisse = await asyncio.gather(
        albums_router.sync_names_multi(anfrage("alice-a", "alice-b"), request),
        albums_router.sync_names_multi(anfrage("alex-c", "alex-d"), request),
        return_exceptions=True,
    )

    assert len(store.get_managed_albums()) == 1
    assert len(angelegte) == 1

    eintraege = [e for r in ergebnisse if isinstance(r, list) for e in r
                 if e.action == "create_album"]
    assert not any(e.message_key == "log_album_already_exists" for e in eintraege), (
        "ein fremdes Paar wurde als „gab es schon“ abgetan")
    assert any(e.status == "error" and e.message_key == "log_manual_match_collision"
               for e in eintraege), [(e.status, e.message_key) for e in eintraege]


# ------------------------------------------------------ der Verknuepfungsweg

@pytest.mark.asyncio
async def test_zwei_gleichzeitige_verknuepfungen_fuer_denselben_treffer(
        tmp_path, monkeypatch):
    """Die dritte Tuer: ein BESTEHENDES Album verknuepfen, zweimal.

    Vom Blindpruefer als ungedeckt gemeldet (22.09.2026): Alle uebrigen
    Proben gehen ueber `album_name`, also ueber das ANLEGEN. Der Zweig
    `link_existing_album` liegt unter demselben Trefferschloss und war von
    nichts gedeckt — dieselbe Klasse, die dieses Projekt schon zweimal
    getroffen hat (`lehren.md` §39: zwei Tueren, zwei Proben).
    """
    from models.match import SyncAlbumRequest
    from routers import albums as albums_router
    import routers.faces as faces
    from services import sync_service

    store = _store(tmp_path)
    angelegte: list = []
    _immich_attrappe(monkeypatch, angelegte)

    verknuepft: list = []
    echtes_verknuepfen = sync_service.link_existing_album

    async def zaehlendes_verknuepfen(**kwargs):
        verknuepft.append(kwargs["album_id"])
        return await echtes_verknuepfen(**kwargs)

    monkeypatch.setattr(sync_service, "link_existing_album", zaehlendes_verknuepfen)

    # Der Name des bestehenden Albums wird ueber einen EIGENEN Client geholt,
    # den der Router LOKAL importiert (`albums.py:53`) — die Attrappe muss
    # deshalb am Modul sitzen, nicht am Router. Genau diese Stelle laeuft
    # unter gehaltenem Trefferschloss.
    import services.immich_client as ic

    class RouterClient:
        def __init__(self, *_a, **_k):
            pass

        async def get_album_info(self, album_id):
            await asyncio.sleep(0)
            return {"id": album_id, "albumName": "Bestehendes Album"}

    monkeypatch.setattr(ic, "ImmichClient", RouterClient)

    async def hole_matches(_request):
        return [_treffer(1)]

    monkeypatch.setattr(faces, "get_matches", hole_matches)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)))

    def anfrage():
        return SyncAlbumRequest(match_id="match-1", owner_account_id="konto-1",
                                existing_album_id="ia-7")

    await asyncio.gather(
        albums_router.create_album(anfrage(), request),
        albums_router.create_album(anfrage(), request),
    )

    assert len(store.get_managed_albums()) == 1, "zwei Eintraege fuer EINEN Treffer"
    assert len(verknuepft) == 1, f"{len(verknuepft)}-mal verknuepft"


# ------------------------------------------- Die Haelften des Vergleichs

@pytest.mark.asyncio
async def test_gleiche_personenkennung_anderes_konto_ist_eine_kollision(
        tmp_path, monkeypatch):
    """Der Vergleich haengt am Paar (Konto, Person), nicht an der Person.

    Gemessen vom Blindpruefer (Nacharbeit 1): Nimmt man das Konto aus dem
    Vergleichsschluessel, bleibt die volle Suite gruen — beide
    Kollisionsproben halten die Konten fest und variieren nur die
    Personen-IDs. Die halbe Zusicherung war von nichts gehalten.

    Der Fall ist nicht kuenstlich: Personen-IDs sind je Immich-Instanz
    vergeben, zwei Konten koennen dieselbe tragen.
    """
    from models.match import SyncNamesMultiRequest, MultiSyncPersonEntry
    from routers import albums as albums_router
    import errors

    store = _store(tmp_path)
    angelegte: list = []
    _immich_attrappe(monkeypatch, angelegte)
    request, umbenannt = _manuelle_umgebung(monkeypatch, store)

    def anfrage(konto_b):
        return SyncNamesMultiRequest(
            persons=[MultiSyncPersonEntry(account_id="konto-1", person_id="p1"),
                     MultiSyncPersonEntry(account_id=konto_b, person_id="p2")],
            canonical_name="Alex", album_name="Alex", owner_account_id="konto-1")

    await albums_router.sync_names_multi(anfrage("konto-2"), request)

    # Dieselben Personen-IDs, aber p2 kommt jetzt aus konto-1.
    with pytest.raises(errors.AppError) as fehler:
        await albums_router.sync_names_multi(anfrage("konto-1"), request)
    assert fehler.value.key == "err_manual_match_id_collision"

    assert umbenannt == ["Alex"], "der abgelehnte Aufruf hat trotzdem umbenannt"
    assert len(angelegte) == 1


@pytest.mark.asyncio
async def test_nach_einer_erweiterung_wird_der_wiederholungsaufruf_nicht_abgelehnt(
        tmp_path, monkeypatch):
    """Eine Erweiterung macht die gespeicherte Menge groesser — das ist keine Kollision.

    `extend_match` haengt eine Person an `person_refs` des bestehenden Albums
    und laesst die `match_id` unberuehrt. Ein Gleichheitsvergleich las danach
    „andere Personen" und lehnte den unveraenderten Wiederholungsaufruf ab —
    mit der falschen Auskunft und, schlimmer, unter Verlust des
    Namensabgleichs. Gemessen vom Blindpruefer an den echten Endpunkten
    (Nacharbeit 1, 22.09.2026); deshalb Teilmenge statt Gleichheit.
    """
    from models.match import SyncNamesMultiRequest, MultiSyncPersonEntry
    from routers import albums as albums_router

    store = _store(tmp_path)
    angelegte: list = []
    _immich_attrappe(monkeypatch, angelegte)
    request, umbenannt = _manuelle_umgebung(monkeypatch, store)

    def anfrage():
        return SyncNamesMultiRequest(
            persons=[MultiSyncPersonEntry(account_id="konto-1", person_id="p1"),
                     MultiSyncPersonEntry(account_id="konto-2", person_id="p2")],
            canonical_name="Oma Erna", album_name="Oma Erna",
            owner_account_id="konto-1")

    await albums_router.sync_names_multi(anfrage(), request)

    # Die Erweiterung so nachbilden, wie `extend_match` sie hinterlaesst:
    # eine Person mehr in `person_refs`, dieselbe Kennung.
    album = store.get_managed_albums()[0]
    album.person_refs = list(album.person_refs) + [{
        "account_id": "konto-1", "person_id": "p3", "person_name": "Dritte",
        "account_name": "Konto Eins", "account_color": "#111111"}]
    store.update_managed_album(album)
    assert len(store.get_managed_albums()[0].person_refs) == 3

    logs = await albums_router.sync_names_multi(anfrage(), request)

    assert umbenannt == ["Oma Erna", "Oma Erna"], (
        "nach einer Erweiterung wurde der Namensabgleich uebersprungen")
    assert len(angelegte) == 1
    assert any(e.message_key == "log_album_already_exists" for e in logs), (
        [(e.status, e.message_key) for e in logs])

