"""Umbenennen muss sich gegen Refresh und gegen sich selbst ausschliessen (#79).

Beides sind Funde des Fremdpruefers am zugelieferten Zweig, und beide waren
beim Rebase textlich unsichtbar:

1. **Die Schlossform.** Der Zweig nahm `_album_locks.setdefault(managed.id,
   ...)`, der Refresh daneben `(id(loop), managed.id)`. Zwei verschieden
   geformte Schluessel in derselben Ablage schliessen sich nicht aus. Der
   Docstring des Umbenennens sagte woertlich das Gegenteil — er war die
   einzige Zusicherung, und er war falsch.
2. **Das Fenster in der Kollisionspruefung.** Die Pruefung „gehoert der Name
   schon einer anderen Gruppe?“ stand VOR dem Schreibvorgang, aber unter
   keinem Schloss. Zwei gleichzeitige Umbenennungen auf denselben Namen kamen
   beide durch und erzeugten genau die zwei gleichnamigen Gruppen, die die
   Pruefung verhindern soll.

Gemessen wird hier die Ausschliessung selbst, nicht das Innenleben von
Refresh oder Umbenennen: Die beiden inneren Funktionen sind Attrappen, die
ihren Eintritt protokollieren. Damit sagt ein rotes Ergebnis, dass die
Schloesser nicht greifen — und nichts anderes.
"""
import asyncio
import json
from types import SimpleNamespace

import pytest

KONTO = {"id": "konto-1", "name": "Konto Eins",
         "immich_url": "http://beispiel.invalid", "api_key": "platzhalter",
         "color": "#111111", "user_id": "u1"}


def _album(album_id, name, gruppe):
    return {"id": album_id, "match_id": "m-" + album_id,
            "album_id": "immich-" + album_id, "album_name": name,
            "group_id": gruppe, "owner_account_id": "konto-1",
            "person_refs": [], "linked_match_ids": [],
            "created_at": "2026-01-01T00:00:00+00:00"}


def _store(tmp_path, alben):
    from services.config_store import ConfigStore
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({"accounts": {"konto-1": KONTO},
                                "schema_version": 3, "managed_albums": alben}),
                    encoding="utf-8")
    return ConfigStore(str(pfad))


def _anfrage(store):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)))


# ------------------------------------------------ 1) Umbenennen gegen Refresh

@pytest.mark.asyncio
async def test_ein_refresh_wartet_auf_ein_laufendes_umbenennen(tmp_path, monkeypatch):
    """Der Kern von BLOCKER 1: dasselbe Album, dasselbe Schloss.

    Ohne die gemeinsame Schlossform betritt der Refresh seinen Rumpf, waehrend
    das Umbenennen noch im seinen steht — und ein Refresh mit altem Abbild
    schreibt den alten Namen zurueck.
    """
    from services import sync_service

    store = _store(tmp_path, [_album("a1", "Straßenfest", "g1")])
    verwaltet = store.get_managed_albums()[0]
    konto = store.get_account("konto-1")

    sync_service._album_locks.clear()
    protokoll: list[str] = []
    tor = asyncio.Event()

    async def umbenennen_innen(*_a, **_k):
        protokoll.append("umbenennen an")
        await tor.wait()
        protokoll.append("umbenennen aus")
        return []

    async def refresh_innen(*_a, **_k):
        protokoll.append("refresh an")
        return []

    monkeypatch.setattr(sync_service, "_rename_managed_album_unlocked", umbenennen_innen)
    monkeypatch.setattr(sync_service, "_refresh_managed_album_unlocked", refresh_innen)

    u = asyncio.create_task(
        sync_service.rename_managed_album(verwaltet, konto, "Herbstfest", store))
    await asyncio.sleep(0)
    assert protokoll == ["umbenennen an"], protokoll

    r = asyncio.create_task(
        sync_service.refresh_managed_album(verwaltet, [konto], store))
    for _ in range(5):
        await asyncio.sleep(0)

    # DER KERN: Der Refresh steht noch draussen.
    assert protokoll == ["umbenennen an"], protokoll

    tor.set()
    await asyncio.gather(u, r)
    assert protokoll == ["umbenennen an", "umbenennen aus", "refresh an"], protokoll


def test_das_albumschloss_ueberlebt_einen_schleifenwechsel(tmp_path, monkeypatch):
    """Dieselbe Klasse, die `sync_service` im Kopf als behoben notiert.

    Ein `asyncio.Lock` haengt an der Schleife, in der er zum ersten Mal
    gewartet hat. Ein Schloss aus einem beendeten Ring wirft beim zweiten
    Gebrauch — deshalb steht die Loop-Kennung im Schluessel. Fuer den Refresh
    hielt das `test_album_schloss_ueberlebt_einen_schleifenwechsel` fest, fuer
    das Umbenennen gab es kein Gegenstueck; genau dort hat der zugelieferte
    Zweig die Klasse zurueckgeholt (gemessen vom Blindpruefer).

    Bewusst OHNE `pytest.mark.asyncio`: Dieser Test fuehrt die beiden
    Ereignis-Ringe selbst, und er raeumt `_album_locks` zwischen ihnen NICHT
    auf — das Aufraeumen waere genau die Sichtblende.
    """
    from services import sync_service

    store = _store(tmp_path, [_album("a1", "Straßenfest", "g1")])
    konto = store.get_account("konto-1")

    async def umbenennen_innen(*_a, **_k):
        # DAS `sleep(0)` IST DER BEWEIS, nicht Kosmetik: Ein `asyncio.Lock`
        # bindet sich erst an eine Schleife, wenn jemand WARTEN muss — der
        # freie Griff laeuft an `_get_loop()` vorbei. Ohne diese Zeile lief
        # das erste Umbenennen durch, bevor das zweite begann, es gab keine
        # Kollision, und der Test blieb gruen, auch mit dem alten Schluessel
        # (gemessen: „B1a UEBERLEBT").
        await asyncio.sleep(0)
        return []

    monkeypatch.setattr(sync_service, "_rename_managed_album_unlocked", umbenennen_innen)
    sync_service._album_locks.clear()

    def frisches_album():
        return store.get_managed_albums()[0]

    async def umkaempft():
        await asyncio.gather(
            sync_service.rename_managed_album(frisches_album(), konto, "X", store),
            sync_service.rename_managed_album(frisches_album(), konto, "X", store),
        )
        return True

    assert asyncio.run(umkaempft())
    assert asyncio.run(umkaempft()), "zweite Schleife scheiterte"


@pytest.mark.asyncio
async def test_zwei_alben_blockieren_sich_nicht_gegenseitig(tmp_path, monkeypatch):
    """Die Gegenprobe: Das Schloss haengt am Album, nicht am Modul.

    Ohne sie waere ein globales Schloss die billigste Antwort auf den Fund —
    und die haette die gleichzeitige Arbeit an verschiedenen Alben abgeschafft.
    """
    from services import sync_service

    store = _store(tmp_path, [_album("a1", "Eins", "g1"), _album("a2", "Zwei", "g2")])
    eins, zwei = store.get_managed_albums()
    konto = store.get_account("konto-1")

    sync_service._album_locks.clear()
    protokoll: list[str] = []
    tor = asyncio.Event()

    async def umbenennen_innen(managed, *_a, **_k):
        protokoll.append("an " + managed.id)
        await tor.wait()
        return []

    monkeypatch.setattr(sync_service, "_rename_managed_album_unlocked", umbenennen_innen)

    a = asyncio.create_task(sync_service.rename_managed_album(eins, konto, "X", store))
    b = asyncio.create_task(sync_service.rename_managed_album(zwei, konto, "Y", store))
    for _ in range(5):
        await asyncio.sleep(0)

    assert sorted(protokoll) == ["an a1", "an a2"], protokoll
    tor.set()
    await asyncio.gather(a, b)


# ------------------------- 1b) Das Schloss allein reicht nicht

def _immich_attrappe(monkeypatch, name_draussen, bestand=("x1", "x2")):
    """Ein Immich, das den Namen mitschreibt und ein paar Assets kennt.

    Die Assets sind nötig, weil der Refresh `total_assets` daraus setzt — und
    genau daran zeigt sich die Gegenrichtung des Fehlers.
    """
    from services import sync_service

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def update_album(self, album_id, payload):
            name_draussen["wert"] = payload["albumName"]
            return {"id": album_id, **payload}

        async def get_album_assets(self, _album_id):
            await asyncio.sleep(0)
            return list(bestand)

        async def get_person_assets(self, _person_id):
            await asyncio.sleep(0)
            return []

        async def add_assets_to_album(self, _album_id, _ids):
            return []

    async def ohne_teilen(*_a, **_k):
        return []

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)
    return Client


@pytest.mark.asyncio
async def test_ein_refresh_mit_altem_abbild_holt_den_alten_namen_nicht_zurueck(
    tmp_path, monkeypatch
):
    """Der Kern des Funds an der ERSTEN Nacharbeit.

    Das Schloss serialisiert die Rümpfe — aber beide Seiten haben ihre Kopie
    schon vorher in der Hand. Der Auto-Sync liest ALLE Alben einmal und
    arbeitet sie danach der Reihe nach ab (`main._run_auto_sync`), und
    `update_managed_album` ersetzt den Datensatz GANZ.

    Gemessen ohne die Nachbesserung: Immich trägt „Neu", der Bestand fällt auf
    „Alt" zurück, und BEIDE Protokolleinträge melden Erfolg. Es gibt keinen
    Fehler, den ein Nutzer sehen könnte — deshalb ist das ein Blocker und
    keine Unschönheit.
    """
    from services import sync_service

    store = _store(tmp_path, [_album("a1", "Alt", "g1")])
    konto = store.get_account("konto-1")
    draussen = {"wert": "Alt"}
    _immich_attrappe(monkeypatch, draussen)

    # So liest der Auto-Sync: EINMAL, vor der Schleife.
    abbild_des_autosync = store.get_managed_albums()[0]

    await sync_service.rename_managed_album(
        store.get_managed_albums()[0], konto, "Neu", store)
    assert draussen["wert"] == "Neu"

    # Und jetzt kommt er an diesem Album an.
    logs = await sync_service.refresh_managed_album(
        abbild_des_autosync, [konto], store)

    assert [e.status for e in logs] == ["success"], logs
    assert store.get_managed_album("a1").album_name == "Neu", "alter Name zurückgeholt"


@pytest.mark.asyncio
async def test_ein_umbenennen_mit_altem_abbild_wirft_den_refresh_nicht_weg(
    tmp_path, monkeypatch
):
    """Die Gegenrichtung desselben Fehlers.

    Hier verliert nicht der Name, sondern das Ergebnis des Abgleichs:
    `total_assets` und `last_synced_at` stehen im selben Datensatz. Ein
    Umbenennen mit altem Abbild schrieb sie zurück auf den Stand von vorher.
    """
    from services import sync_service

    store = _store(tmp_path, [_album("a1", "Alt", "g1")])
    konto = store.get_account("konto-1")
    draussen = {"wert": "Alt"}
    _immich_attrappe(monkeypatch, draussen)

    # Das Abbild, das der Umbenenner gleich benutzt — gelesen VOR dem Refresh.
    altes_abbild = store.get_managed_albums()[0]
    assert altes_abbild.total_assets == 0

    await sync_service.refresh_managed_album(
        store.get_managed_albums()[0], [konto], store)
    nach_refresh = store.get_managed_album("a1")
    assert nach_refresh.total_assets == 2, "Attrappe liefert zwei Assets"
    assert nach_refresh.last_synced_at

    await sync_service.rename_managed_album(altes_abbild, konto, "Neu", store)

    danach = store.get_managed_album("a1")
    assert danach.album_name == "Neu"
    assert danach.total_assets == 2, "Ergebnis des Abgleichs weggeworfen"
    assert danach.last_synced_at == nach_refresh.last_synced_at


# --------------------------------------- 2) Umbenennen gegen Umbenennen

@pytest.mark.asyncio
async def test_zwei_gleichzeitige_umbenennungen_auf_denselben_namen(tmp_path, monkeypatch):
    """Der Kern von BLOCKER 2: genau eine der beiden darf durchkommen.

    Die Attrappe schreibt WIRKLICH in den Store und laesst vorher ein Fenster
    (`sleep(0)`) — ohne beides gaebe es nichts zu gewinnen: Ohne Schreiben
    sieht die zweite Anfrage nie, dass der Name vergeben ist, und ohne Fenster
    kaeme sie nie dazwischen.
    """
    from models.match import RenameManagedAlbumRequest
    from routers import albums as albums_router
    from services import sync_service

    store = _store(tmp_path, [_album("a1", "Straßenfest", "g1"),
                              _album("a2", "Sommerfest", "g2")])

    async def umbenennen(managed, _owner, neuer_name, store_):
        await asyncio.sleep(0)
        managed.album_name = neuer_name
        store_.update_managed_album(managed)
        return []

    monkeypatch.setattr(sync_service, "rename_managed_album", umbenennen)
    anfrage = _anfrage(store)

    ergebnisse = await asyncio.gather(
        albums_router.rename_managed_album(
            "a1", RenameManagedAlbumRequest(album_name="Herbstfest"), anfrage),
        albums_router.rename_managed_album(
            "a2", RenameManagedAlbumRequest(album_name="Herbstfest"), anfrage),
        return_exceptions=True,
    )

    fehler = [e for e in ergebnisse if isinstance(e, BaseException)]
    assert len(fehler) == 1, ergebnisse
    assert getattr(fehler[0], "key", None) == "err_album_name_in_use", fehler[0]

    namen = sorted(a.album_name for a in store.get_managed_albums())
    assert namen.count("Herbstfest") == 1, namen


@pytest.mark.asyncio
async def test_das_umbenennen_haelt_dasselbe_namensschloss_wie_die_anlage(
    tmp_path, monkeypatch
):
    """Es muss DAS Schloss des Stores sein, nicht ein eigenes.

    Sonst waere der Fall „Umbenennen gegen Anlegen“ offen: Die Anlage nimmt
    `store.gruppen_schloss(name)`. Gemessen wird deshalb nicht der Endstand,
    sondern ob jemand mit demselben Namen an genau dieses Schloss kommt,
    waehrend das Umbenennen laeuft.
    """
    from models.match import RenameManagedAlbumRequest
    from routers import albums as albums_router
    from services import sync_service

    store = _store(tmp_path, [_album("a1", "Straßenfest", "g1")])
    erreicht: list[str] = []
    tor = asyncio.Event()

    async def umbenennen(*_a, **_k):
        erreicht.append("umbenennen an")
        await tor.wait()
        return []

    monkeypatch.setattr(sync_service, "rename_managed_album", umbenennen)

    async def anlage_versucht_denselben_namen():
        async with store.gruppen_schloss("Herbstfest"):
            erreicht.append("anlage am schloss")

    u = asyncio.create_task(albums_router.rename_managed_album(
        "a1", RenameManagedAlbumRequest(album_name="Herbstfest"), _anfrage(store)))
    await asyncio.sleep(0)
    a = asyncio.create_task(anlage_versucht_denselben_namen())
    for _ in range(5):
        await asyncio.sleep(0)

    assert erreicht == ["umbenennen an"], erreicht

    tor.set()
    await asyncio.gather(u, a)
    assert erreicht == ["umbenennen an", "anlage am schloss"], erreicht


@pytest.mark.asyncio
async def test_ein_anderer_name_wartet_nicht(tmp_path, monkeypatch):
    """Gegenprobe zum Namensschloss: gesperrt wird nur gegen DENSELBEN Namen."""
    from models.match import RenameManagedAlbumRequest
    from routers import albums as albums_router
    from services import sync_service

    store = _store(tmp_path, [_album("a1", "Straßenfest", "g1")])
    erreicht: list[str] = []
    tor = asyncio.Event()

    async def umbenennen(*_a, **_k):
        erreicht.append("umbenennen an")
        await tor.wait()
        return []

    monkeypatch.setattr(sync_service, "rename_managed_album", umbenennen)

    async def anlage_mit_anderem_namen():
        async with store.gruppen_schloss("Ganz anders"):
            erreicht.append("anlage am schloss")

    u = asyncio.create_task(albums_router.rename_managed_album(
        "a1", RenameManagedAlbumRequest(album_name="Herbstfest"), _anfrage(store)))
    await asyncio.sleep(0)
    a = asyncio.create_task(anlage_mit_anderem_namen())
    for _ in range(5):
        await asyncio.sleep(0)

    assert erreicht == ["umbenennen an", "anlage am schloss"], erreicht
    tor.set()
    await asyncio.gather(u, a)
