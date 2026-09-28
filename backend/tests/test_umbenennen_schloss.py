"""Umbenennen muss sich gegen Refresh und gegen sich selbst ausschliessen (#79).

Fund des Fremdpruefers am zugelieferten Zweig, textlich beim Rebase
unsichtbar: **Die Schlossform.** Der Zweig nahm `_album_locks.setdefault(
managed.id, ...)`, der Refresh daneben `(id(loop), managed.id)`. Zwei
verschieden geformte Schluessel in derselben Ablage schliessen sich nicht aus.
Der Docstring des Umbenennens sagte woertlich das Gegenteil — er war die
einzige Zusicherung, und er war falsch.

Gemessen wird hier die Ausschliessung selbst, nicht das Innenleben von
Refresh oder Umbenennen: Die beiden inneren Funktionen sind Attrappen, die
ihren Eintritt protokollieren. Damit sagt ein rotes Ergebnis, dass die
Schloesser nicht greifen — und nichts anderes.

BIS #98 STAND HIER EIN ZWEITER FUND: ein Fenster in der Kollisionspruefung
beim Umbenennen, das zwei gleichzeitige Umbenennungen auf denselben Namen
beide durchliess und genau die zwei gleichnamigen Gruppen erzeugte, die die
Pruefung verhindern sollte. Die Pruefung samt ihrem Namensschloss ist seit
#98 entfernt — zwei Albumgruppen duerfen denselben Namen tragen, es gibt
nichts mehr, das dieses Fenster noch schuetzen muesste. Die drei Proben dazu
(`test_zwei_gleichzeitige_umbenennungen_auf_denselben_namen`,
`test_das_umbenennen_haelt_dasselbe_namensschloss_wie_die_anlage`,
`test_ein_anderer_name_wartet_nicht`) sind mit ihm entfernt.
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

        async def get_album_assets_with_name(self, _album_id):
            # ABSICHTLICH kein Name (#97, Nacharbeit 1 — Fund des
            # Blindpruefers): Wuerde hier `name_draussen["wert"]` stehen,
            # wuerde die Namensuebernahme jede Diskrepanz zwischen einem
            # frischen und einem veralteten `managed`-Abbild selbst reparieren
            # — und genau das ist die Klasse, die
            # `test_ein_refresh_mit_altem_abbild_holt_den_alten_namen_nicht_zurueck`
            # (unten) beweisen soll. Gemessen zum STAND DES ERSTBAUS: Mit dem
            # Namen aus `name_draussen` blieb die Mutation `_frisch(managed,
            # store) -> managed` in `refresh_managed_album` GRUEN ueber den
            # `album_name`-Vergleich. Nachgemessen in Nacharbeit 2: Mit der
            # damaligen Attrappe UND derselben Mutation wird der Test heute
            # zwar rot, aber ueber die PROTOKOLLANZAHL
            # (`[e.status for e in logs] == ["success"]` scheitert an einem
            # zusaetzlichen Eintrag, nicht am Namen) — die Nacharbeit-1-Regel
            # „Name ist eine zusaetzliche Meldung" haette die urspruengliche
            # Luecke also zufaellig mitgedeckt. Diese Attrappe bleibt trotzdem
            # namenlos: Sie soll die Schlossform pruefen, nicht sich auf einen
            # Seiteneffekt einer anderen Regel verlassen. Der Schaden bleibt
            # real (ein veraltetes Abbild schreibt auch `person_refs`/`status`
            # zurueck). Die Namensuebernahme hat ihre eigenen Tests in
            # `test_sync_service.py`.
            await asyncio.sleep(0)
            return None, list(bestand)

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


# ------------------- 1c) `_frisch` muss INNERHALB des Schlosses laufen (M5b/M5c)
#
# #101, Nacharbeit 2 (Blindpruefer): Die beiden Tests oben (1b) sind
# SEQUENZIELL — ein Aufruf laeuft ganz zu Ende, bevor der naechste beginnt.
# Damit pruefen sie, dass `_frisch` VOR dem Schreiben liest, aber nicht, DASS
# es das WAEHREND das Schloss gehalten wird tut. Gemessen: Verschiebt man den
# `_frisch`-Aufruf in `rename_managed_album` bzw. `refresh_managed_album` vor
# den `async with _album_schloss(...)`-Block (die Sperre bleibt bestehen, nur
# der Lesezeitpunkt wandert), bleiben ALLE 308 Tests gruen — auch diese
# beiden 1b-Tests, weil dort niemand gleichzeitig etwas schreibt, waehrend der
# jeweils andere sein Abbild einliest.
#
# Die beiden Proben hier erzwingen genau das fehlende Fenster: EIN Aufruf haelt
# das Schloss und schreibt (hinter einem Tor verzoegert), der ANDERE startet
# waehrenddessen und liest sein Abbild — mit `_frisch` vor dem Schloss noch
# VOR dem Schreiben, mit `_frisch` im Schloss (der korrekte Stand) erst NACH
# dessen Freigabe.

@pytest.mark.asyncio
async def test_umbenennen_gleichzeitig_mit_refresh_behaelt_refresh_ergebnis(
    tmp_path, monkeypatch
):
    """M5b: `_frisch` vor dem Schloss bei `rename_managed_album`.

    Fund des Blindpruefers (eigene Probendatei `test_probe_frisch_im_schloss.py`,
    hier uebernommen). Refresh haelt das Schloss und wartet an einem Tor,
    BEVOR es schreibt; Umbenennen startet waehrenddessen mit demselben alten
    Abbild. Mit `_frisch` im Schloss (Stand nach dieser Nacharbeit) liest
    Umbenennen sein Abbild ERST NACH der Freigabe — also nach Refreshs
    Schreibvorgang — und `total_assets` bleibt erhalten. Mit `_frisch` vor
    dem Schloss (M5b) liest Umbenennen VORHER, wirft das Refresh-Ergebnis beim
    eigenen Schreiben weg: `total_assets` faellt von 2 auf 0 zurueck.
    """
    from services import sync_service

    store = _store(tmp_path, [_album("a1", "Alt", "g1")])
    konto = store.get_account("konto-1")
    _immich_attrappe(monkeypatch, {"wert": "Alt"})
    sync_service._album_locks.clear()

    tor = asyncio.Event()
    orig = sync_service._refresh_managed_album_unlocked

    async def refresh_mit_tor(*a, **k):
        await tor.wait()
        return await orig(*a, **k)

    monkeypatch.setattr(sync_service, "_refresh_managed_album_unlocked", refresh_mit_tor)

    abbild = store.get_managed_albums()[0]
    r = asyncio.create_task(sync_service.refresh_managed_album(abbild, [konto], store))
    await asyncio.sleep(0)
    n = asyncio.create_task(sync_service.rename_managed_album(abbild, konto, "Neu", store))
    for _ in range(5):
        await asyncio.sleep(0)
    tor.set()
    await asyncio.gather(r, n)

    d = store.get_managed_album("a1")
    assert d.album_name == "Neu"
    assert d.total_assets == 2, f"Refresh-Ergebnis weggeworfen: {d.total_assets}"


@pytest.mark.asyncio
async def test_refresh_gleichzeitig_mit_umbenennen_behaelt_den_neuen_namen(
    tmp_path, monkeypatch
):
    """M5c: dieselbe Probe, gespiegelt gegen `refresh_managed_album`.

    Umbenennen haelt das Schloss und wartet an einem Tor, BEVOR es schreibt;
    Refresh startet waehrenddessen mit demselben alten Abbild. Mit `_frisch`
    im Schloss liest Refresh sein Abbild erst nach der Freigabe und behaelt
    den neuen Namen. Mit `_frisch` vor dem Schloss (M5c) liest Refresh vorher
    ("Alt") und schreibt beim eigenen Speichern den alten Namen zurueck.
    """
    from services import sync_service

    store = _store(tmp_path, [_album("a1", "Alt", "g1")])
    konto = store.get_account("konto-1")
    _immich_attrappe(monkeypatch, {"wert": "Alt"})
    sync_service._album_locks.clear()

    tor = asyncio.Event()
    orig = sync_service._rename_managed_album_unlocked

    async def umbenennen_mit_tor(*a, **k):
        await tor.wait()
        return await orig(*a, **k)

    monkeypatch.setattr(sync_service, "_rename_managed_album_unlocked", umbenennen_mit_tor)

    abbild = store.get_managed_albums()[0]
    n = asyncio.create_task(
        sync_service.rename_managed_album(abbild, konto, "Neu", store))
    await asyncio.sleep(0)
    r = asyncio.create_task(sync_service.refresh_managed_album(abbild, [konto], store))
    for _ in range(5):
        await asyncio.sleep(0)
    tor.set()
    await asyncio.gather(n, r)

    d = store.get_managed_album("a1")
    assert d.album_name == "Neu", f"Umbenennen-Ergebnis weggeworfen: {d.album_name}"
    assert d.total_assets == 2
