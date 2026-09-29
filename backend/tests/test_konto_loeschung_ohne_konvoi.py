"""Nacharbeit 1 (#117/#121/#103): Konto-Loeschung wartet auf kein
Albumschloss mehr, ein waehrend des Wartens eines anderen Schreibers
geloeschtes Konto bleibt draussen, und Reste heilen sich beim naechsten
Schreibvorgang.

Alle drei Pruefstimmen haben `f796140` widerlegt: Ein Erweitern konnte ein
geloeschtes Konto nach dem 204 zurueckbringen (BLOCKER), ein Abbruch
zwischen zwei Alben liess einen Teilzustand ohne Heilweg zurueck, und
`DELETE /api/accounts/{id}` wartete nacheinander auf jedes Albumschloss
("Konvoi").

DIE NEUE REGEL — EINE fuer ALLE Schreiber (Abgleich, Umbenennen, Erweitern,
Auto-Sync, Anlegen/Verknuepfen): Unter dem Albumschloss werden Besitzer,
Teilnehmer und ein hinzuzufuegendes Konto frisch aus dem Store gelesen;
Referenzen auf Konten, die es nicht mehr gibt, werden beim Zurueckschreiben
verworfen und NIE neu angehaengt (`ConfigStore._ohne_tote_konten`, aufgerufen
aus `add_managed_album`/`update_managed_album` — also aus JEDEM Schreibpfad).
`ConfigStore.delete_account` wartet dafuer auf KEIN Albumschloss mehr: Ist ein
betroffenes Album gerade durch einen anderen Schreiber gesperrt, ueberspringt
die Loeschung es einfach — der Halter bereinigt die tote Referenz selbst,
wenn er seinen Datensatz zurueckschreibt.

DIESE DATEI BAUT DIE ABLAEUFE DER PRUEFSTIMMEN-PROBEN NACH (Bau-Brief Block 2
und 5; Herkunft je Test im Docstring: Sonde-Kennung aus
`scratchpad/welle4/blind/S3/sonde/...` bzw.
`scratchpad/welle4/gegen/S3/proben/test_gegen_s3.py`), ANGEPASST an die neue
Regel: Wo eine Probe fruehte pruefte, dass die Loeschung selbst als
Warteschlangen-Eintrag an einem Schloss haengt, pruefen die entsprechenden
Tests hier stattdessen, dass die Loeschung SOFORT zurueckkehrt (kein Warten)
und der Halter des Schlosses die tote Referenz beim eigenen Zurueckschreiben
entfernt. Bewusst NICHT nachgebaut: Blind-Sonde S4 und S6b sowie
Gegenpruefer-Probe C (reine Zeitmessungen/Clientverhalten ohne pruefbare
Zusicherung unter der neuen Regel) — Begruendung am jeweiligen Test bzw. im
Bau-Bericht.

Alle Daten erfunden (erfundene Konten, Personen, Alben, Schluessel
`platzhalter`, Adressen `http://<name>.invalid`); das Repo ist oeffentlich.
"""
import asyncio
import json
import time

import httpx
import pytest


def _konto(n: int) -> dict:
    return {"id": f"konto-{n}", "name": f"Konto {n}",
            "immich_url": f"http://konto{n}.invalid", "api_key": "platzhalter",
            "color": "#11111" + str(n), "user_id": f"u{n}"}


KONTEN = {n: _konto(n) for n in (1, 2, 3)}


def _ref(n: int, person_id: str | None = None) -> dict:
    return {"account_id": f"konto-{n}", "person_id": person_id or f"p{n}",
            "person_name": f"P{n}", "account_name": f"Konto {n}",
            "account_color": "#11111" + str(n)}


def _album(album_id: str, owner: int, teilnehmer: list[int]) -> dict:
    return {"id": album_id, "match_id": f"m-{album_id}", "album_id": f"immich-{album_id}",
            "album_name": album_id, "group_id": f"g-{album_id}",
            "owner_account_id": f"konto-{owner}",
            "person_refs": [_ref(n) for n in teilnehmer], "linked_match_ids": [],
            "created_at": "2026-01-01T00:00:00+00:00", "total_assets": 0}


def _bestand(tmp_path, alben, konten=None):
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {k["id"]: k for k in (konten or KONTEN.values())},
        "schema_version": 3, "managed_albums": alben,
    }), encoding="utf-8")
    return pfad


class _Welt:
    """Zeichnet Immich-Aufrufe auf und kann beim ERSTEN Treffer auf ein
    `asyncio.Event` (`tor`) warten — dieselbe Form wie in
    `test_erweitern_schloss.py`/`test_loeschen_im_schloss.py`, hier fuer
    mehrere gleichzeitige Proben gebuendelt."""

    def __init__(self):
        self.aufrufe: list[tuple[float, str, str, str]] = []
        self.halt_bei = None
        self.angekommen = asyncio.Event()
        self.tor = asyncio.Event()
        self.marke = 0

    def nach_marke(self) -> list[tuple[float, str, str, str]]:
        return self.aufrufe[self.marke:]


def _immich_attrappe(monkeypatch, welt: _Welt):
    from services import sync_service

    class Client:
        def __init__(self, url, key, *_a, **_k):
            self.url = url

        async def _h(self, m, a):
            welt.aufrufe.append((time.monotonic(), self.url, m, a))
            if welt.halt_bei == (m, a) and not welt.angekommen.is_set():
                welt.angekommen.set()
                await welt.tor.wait()

        async def get_person(self, pid):
            await self._h("get_person", pid)
            return {"id": pid, "name": "X"}

        async def get_album_assets(self, aid):
            await self._h("get_album_assets", aid)
            return []

        async def get_album_assets_with_name(self, aid):
            await self._h("get_album_assets_with_name", aid)
            return aid.removeprefix("immich-"), []

        async def get_person_assets(self, pid):
            await self._h("get_person_assets", pid)
            return [{"id": f"asset-{pid}"}]

        async def add_assets_to_album(self, aid, ids):
            await self._h("add_assets_to_album", aid)
            return [{"id": i, "success": True} for i in ids]

        async def update_album(self, aid, payload):
            await self._h("update_album", aid)
            return {"id": aid, **payload}

        async def update_person(self, pid, payload):
            await self._h("update_person", pid)
            return {"id": pid, **payload}

    async def ohne_teilen(*_a, **_k):
        return []

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)


class _App:
    """Echte HTTP-Tuer ueber ASGI mit Lifespan — dieselbe Form wie die
    Blind-Sonde S3 (`scratchpad/welle4/blind/S3/sonde/...`)."""

    def __init__(self, tmp_path, monkeypatch, alben, konten=None):
        import main
        self.main = main
        pfad = _bestand(tmp_path, alben, konten)
        monkeypatch.setattr(main.settings, "secret", "welle4-s3-na1", raising=False)
        monkeypatch.setattr(main.settings, "config_path", str(pfad), raising=False)

    async def __aenter__(self):
        # Dieselbe Vorsicht wie in `test_erweitern_schloss.py`: Ein
        # `asyncio.Lock` bindet sich an die EREIGNISSCHLEIFE, in der er zuerst
        # benutzt wird (`config_store._gruppen_schloesser`, Modul-Docstring).
        # Alle Tests dieser Datei benutzen dieselben Album-Kennungen ("a1",
        # "a2", ...); ohne dieses Leeren kann ein Schloss aus dem (bereits
        # geschlossenen) Ring eines FRUEHEREN Tests hier wiederverwendet
        # werden, sobald Python die `id()` dieses Rings fuer den NEUEN Ring
        # wiederverwendet — ein `await` darauf haengt dann fuer immer, weil
        # niemand es je wieder freigibt (gemessen: erst beim Lauf der ganzen
        # Datei zusammen, nie bei einem einzelnen Test fuer sich).
        from services import sync_service
        sync_service._album_locks.clear()
        self._lc = self.main.app.router.lifespan_context(self.main.app)
        await self._lc.__aenter__()
        self.store = self.main.app.state.store
        self.c = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.main.app),
                                    base_url="http://test")
        await self.c.__aenter__()
        r = await self.c.post("/api/auth/login", json={"token": "welle4-s3-na1"})
        assert r.status_code == 200
        return self

    async def __aexit__(self, *a):
        await self.c.__aexit__(*a)
        await self._lc.__aexit__(*a)


async def _bis_wartend(album_id: str, n: int = 1, timeout: float = 2.0) -> bool:
    """Wartet aktiv, bis `n` Aufrufer am Albumschloss haengen
    (`docs/agents/lehren.md` §44) — fuer Schreiber, die NACH dieser
    Nacharbeit weiterhin normal warten (Refresh/Umbenennen/Erweitern).
    `ConfigStore.delete_account` gehoert seit dieser Nacharbeit NICHT mehr
    dazu (siehe Modul-Docstring) und wird hier nie darauf geprueft."""
    from services import sync_service
    schloss = sync_service._album_schloss(album_id)
    schritte = int(timeout / 0.005)
    for _ in range(schritte):
        if schloss._waiters and len(schloss._waiters) >= n:
            return True
        await asyncio.sleep(0.005)
    return False


def _konten_in(store, album_id: str) -> set[str]:
    album = store.get_managed_album(album_id)
    return set() if album is None else {r["account_id"] for r in album.person_refs}


# ---------------------------------------------------------------------------
# BLOCKER: Erweitern bringt ein geloeschtes Konto nach dem 204 zurueck
# (Blind-Sonde S1/S1b; Gegenpruefer-Probe A/B)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_erweitern_wartet_neues_konto_wird_waehrenddessen_geloescht(tmp_path, monkeypatch):
    """Blind-Sonde S1: Erweitern wartet (Schloss von a1 durch einen Refresh
    belegt), waehrenddessen wird GENAU das neu hinzuzufuegende Konto
    geloescht — rot unter `f796140`: Der Router liest `new_account` VOR dem
    Schloss; `_extend_match_unlocked` haengte es trotzdem an `person_refs`
    an und rief Immich mit seinem Schluessel auf.
    """
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_album_assets_with_name", "immich-a1")
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2])]) as w:
        t_ref = asyncio.create_task(w.c.post("/api/sync/album/a1/refresh"))
        await asyncio.wait_for(welt.angekommen.wait(), 5)
        t_ext = asyncio.create_task(w.c.post("/api/sync/extend", json={
            "managed_album_id": "a1", "account_id": "konto-3",
            "person_id": "p3", "person_name": "Drei"}))
        assert await _bis_wartend("a1", 1), "Erweitern wartet nicht am Schloss"
        welt.marke = len(welt.aufrufe)

        r_del = await asyncio.wait_for(w.c.delete("/api/accounts/konto-3"), 5)
        assert r_del.status_code == 204

        welt.tor.set()
        r_ref, r_ext = await t_ref, await t_ext

        assert r_ref.status_code == 200 and r_ext.status_code == 200
        konten = _konten_in(w.store, "a1")
        assert "konto-3" not in konten, konten
        immich_mit_drei_danach = [x for x in welt.nach_marke() if "konto3" in x[1]]
        assert not immich_mit_drei_danach, immich_mit_drei_danach


@pytest.mark.asyncio
async def test_erweitern_laeuft_neues_konto_wird_waehrenddessen_geloescht(tmp_path, monkeypatch):
    """Blind-Sonde S1b/Gegenpruefer-Probe B: Erweitern haelt das Schloss
    schon und haengt am ERSTEN Immich-Aufruf (Personen-Validierung), als das
    neue Konto geloescht wird. Die Regel greift hier NICHT ueber die
    Vorab-Pruefung (die hat schon bestanden), sondern ueber das
    Zurueckschreiben (`ConfigStore._ohne_tote_konten`)."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_person", "p3")
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2])]) as w:
        t_ext = asyncio.create_task(w.c.post("/api/sync/extend", json={
            "managed_album_id": "a1", "account_id": "konto-3",
            "person_id": "p3", "person_name": "Drei"}))
        await asyncio.wait_for(welt.angekommen.wait(), 5)

        r_del = await asyncio.wait_for(w.c.delete("/api/accounts/konto-3"), 5)
        assert r_del.status_code == 204

        welt.tor.set()
        r_ext = await t_ext
        assert r_ext.status_code == 200
        konten = _konten_in(w.store, "a1")
        assert "konto-3" not in konten, konten


@pytest.mark.asyncio
async def test_erweitern_ganz_ohne_wartenden_schreiber_konto_faellt_trotzdem_raus(
    tmp_path, monkeypatch
):
    """Gegenpruefer-Probe A: `a1` haelt zunaechst KEIN Schloss — `delete_account`
    nimmt es also gar nicht (das Konto steht dort noch nicht in
    `person_refs`). Das Fenster liegt allein im Erweitern selbst: Die
    Loeschung laeuft VOLLSTAENDIG durch, waehrend das Erweitern am
    Immich-Aufruf haengt."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_person", "p3")
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2])]) as w:
        t_ext = asyncio.create_task(w.c.post("/api/sync/extend", json={
            "managed_album_id": "a1", "account_id": "konto-3",
            "person_id": "p3", "person_name": "Drei"}))
        await asyncio.wait_for(welt.angekommen.wait(), 5)

        r_del = await w.c.delete("/api/accounts/konto-3")
        assert r_del.status_code == 204
        assert w.store.get_account("konto-3") is None

        welt.tor.set()
        r_ext = await t_ext
        assert r_ext.status_code == 200
        assert "konto-3" not in _konten_in(w.store, "a1")


# ---------------------------------------------------------------------------
# Teilnehmerschluessel: Abgleich nimmt Teilnehmer aus dem Store, nicht aus
# einer Momentaufnahme (WICHTIG 1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("wer", [1, 2])
async def test_abgleich_ruft_immich_nicht_mit_dem_schluessel_eines_waehrenddessen_geloeschten_kontos(
    tmp_path, monkeypatch, wer
):
    """Blind-Sonde S2: Ein Umbenennen haelt das Schloss, ein Abgleich wartet
    dahinter, eine Kontoloeschung (Besitzer ODER Teilnehmer) laeuft
    parallel — rot unter `f796140`: `_refresh_managed_album_unlocked` las
    Teilnehmer aus `account_map` (Momentaufnahme VOR dem Schloss)."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("update_album", "immich-a1")
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2])]) as w:
        t_ren = asyncio.create_task(w.c.patch("/api/sync/albums/a1", json={"album_name": "Neu"}))
        await asyncio.wait_for(welt.angekommen.wait(), 5)
        t_ref = asyncio.create_task(w.c.post("/api/sync/album/a1/refresh"))
        assert await _bis_wartend("a1", 1)

        r_del = await asyncio.wait_for(w.c.delete(f"/api/accounts/konto-{wer}"), 5)
        assert r_del.status_code == 204
        welt.marke = len(welt.aufrufe)

        welt.tor.set()
        r_ren, r_ref = await t_ren, await t_ref

        assert r_ren.status_code == 200
        assert r_ref.status_code == 200
        assert f"konto-{wer}" not in _konten_in(w.store, "a1")
        name = KONTEN[wer]["name"].lower().replace(" ", "")
        immich_mit_geloeschtem_danach = [
            x for x in welt.nach_marke() if name in x[1].lower().replace(" ", "")
        ]
        assert not immich_mit_geloeschtem_danach, immich_mit_geloeschtem_danach


# ---------------------------------------------------------------------------
# Ungeschuetzte Zusagen: Besitzerpruefung beim Umbenennen liegt unter dem
# Schloss — das Fenster liegt zwischen dem Lesen VOR dem Schloss und dem
# WARTEN am Schloss (WICHTIG 4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_umbenennen_liest_den_besitzer_nach_dem_warten_nicht_davor(tmp_path, monkeypatch):
    """Blind-Sonde S3, unit-gefasst (kein HTTP noetig): Ein Refresh haelt das
    Schloss, ein Umbenennen WARTET (echter Warteschlangen-Eintrag), und
    WAEHREND dieses Wartens wird der Besitzer geloescht. Erst wenn das
    Umbenennen an der Reihe ist, liest es den Besitzer.

    Dieser Test deckt keine neue Produktionsaenderung, sondern eine bisher
    FEHLENDE Probe (Nacharbeit 1, WICHTIG 4): Der Docstring von
    `test_konto_loeschen_im_schloss.py` behauptete, das Fenster zwischen dem
    Lesen VOR dem Schloss und dem Warten AM Schloss sei nicht erzwingbar —
    das war falsch. `sync_service.rename_managed_album` liest den Besitzer
    schon heute (seit #117 Nachtrag) ERST unter dem Schloss; ohne diesen Test
    blieb eine Mutation, die das rueckgaengig macht (Blind M6, Gegen M5),
    trotzdem gruen, weil kein Test je dieses konkrete Fenster erzwang.
    """
    import errors
    from services import sync_service
    from services.config_store import ConfigStore

    pfad = _bestand(tmp_path, [_album("a1", 1, [1, 2])])
    cs = ConfigStore(str(pfad))

    sync_service._album_locks.clear()
    tor = asyncio.Event()
    protokoll: list[str] = []

    async def refresh_innen(*_a, **_k):
        protokoll.append("refresh an")
        await tor.wait()
        protokoll.append("refresh aus")
        return []

    monkeypatch.setattr(sync_service, "_refresh_managed_album_unlocked", refresh_innen)

    managed = cs.get_managed_albums()[0]
    r = asyncio.create_task(sync_service.refresh_managed_album(managed, [], cs))
    await asyncio.sleep(0)
    assert protokoll == ["refresh an"]

    ren = asyncio.create_task(sync_service.rename_managed_album(managed, "Neu", cs))
    assert await _bis_wartend("a1", 1), "Umbenennen wartet nicht am Schloss"

    # Besitzer (konto-1) WAEHREND des Wartens loeschen.
    geloescht = await cs.delete_account("konto-1")
    assert geloescht is True

    tor.set()
    await r
    with pytest.raises(errors.AppError) as fehler:
        await ren
    assert fehler.value.key == "err_owner_account_not_found", fehler.value.key


# ---------------------------------------------------------------------------
# Teilzustand ohne Heilweg: Abbruch zwischen zwei Alben (WICHTIG 2)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_abbruch_zwischen_zwei_alben_heilt_beim_naechsten_versuch(tmp_path, monkeypatch):
    """Gegenpruefer-Probe D / Blind-Sonde S5: `update_managed_album` schlaegt
    fuer EIN Album fehl (simulierter Plattenfehler), waehrend ein anderes
    Album schon bereinigt wurde. Die Kontenzeile ist in BEIDEN Faellen schon
    weg (sie wird vor der Album-Schleife entfernt) — der zweite Aufruf mit
    DERSELBEN (bereits geloeschten) Kennung heilt den Rest."""
    from services import sync_service
    from services.config_store import ConfigStore

    sync_service._album_locks.clear()  # siehe `_App.__aenter__`
    pfad = _bestand(tmp_path, [_album("a1", 1, [1, 2]), _album("a2", 1, [1, 2])])
    store = ConfigStore(str(pfad))
    orig = type(store).update_managed_album

    def kaputt(self, album):
        if album.id == "a2":
            raise OSError("Platte voll (Probe)")
        return orig(self, album)

    monkeypatch.setattr(type(store), "update_managed_album", kaputt)
    with pytest.raises(OSError):
        await store.delete_account("konto-2")

    # Konto ist trotz des Abbruchs schon weg, a1 schon bereinigt, a2 noch nicht.
    assert store.get_account("konto-2") is None
    assert _konten_in(store, "a1") == {"konto-1"}
    assert _konten_in(store, "a2") == {"konto-1", "konto-2"}

    monkeypatch.setattr(type(store), "update_managed_album", orig)
    geheilt = await store.delete_account("konto-2")

    assert geheilt is True, "Heilweg meldete 'nichts zu tun', obwohl a2 noch die Referenz trug"
    assert _konten_in(store, "a2") == {"konto-1"}


@pytest.mark.asyncio
async def test_zweites_delete_auf_bereits_geloeschtes_konto_ohne_reste_ist_404(tmp_path):
    """Gegenstueck zum Heilweg-Test oben: Eine Kennung, die WEDER im
    Kontenbestand noch als Referenz irgendwo auftaucht, bleibt ein echter
    Nichttreffer (404) — der Heilweg darf nicht jedes zweite DELETE in einen
    Erfolg verwandeln."""
    from services.config_store import ConfigStore

    pfad = _bestand(tmp_path, [_album("a1", 1, [1, 2])])
    store = ConfigStore(str(pfad))

    assert await store.delete_account("konto-nie-vorhanden-gewesen") is False


# ---------------------------------------------------------------------------
# Konvoi: DELETE wartet nicht mehr nacheinander auf jedes Albumschloss
# (WICHTIG 3, Gegenpruefer-Proben F/F2)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_dauer_ist_unabhaengig_von_gehaltenen_schloessern(tmp_path, monkeypatch):
    """Gegenpruefer-Proben F/F2: Vier Alben tragen alle `konto-3`; ein
    Sammelabgleich haelt sie NACHEINANDER, je 0,3 s (`JE`). Rot unter
    `f796140`: Die Kontoloeschung wartete auf jedes gehaltene Schloss
    NACHEINANDER und brauchte in Summe rund 4x JE (gemessen 1,29 s bei
    4x0,3s). Nach dieser Nacharbeit ueberspringt sie jedes gerade gehaltene
    Album sofort — die Dauer bleibt weit unter EINER Wartezeit."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    JE = 0.3
    orig_halten = {"n": 0}

    from services import sync_service

    class LangsamerClient:
        def __init__(self, url, key, *_a, **_k):
            self.url = url

        async def get_album_assets_with_name(self, aid):
            await asyncio.sleep(JE)
            return aid.removeprefix("immich-"), []

        async def get_person_assets(self, pid):
            return []

        async def add_assets_to_album(self, aid, ids):
            return []

        async def update_album(self, aid, payload):
            return {"id": aid, **payload}

        async def update_person(self, pid, payload):
            return {"id": pid, **payload}

        async def get_person(self, pid):
            return {"id": pid, "name": "X"}

    monkeypatch.setattr(sync_service, "ImmichClient", LangsamerClient)

    alben = [_album(f"a{i}", 1, [1, 3]) for i in range(1, 5)]
    async with _App(tmp_path, monkeypatch, alben) as w:
        t_auto = asyncio.create_task(w.main._run_auto_sync(w.main.app.state))
        # Kurz warten, bis der Sammelabgleich sicher am ERSTEN Album haengt.
        await asyncio.sleep(JE / 3)

        t0 = time.monotonic()
        r_del = await asyncio.wait_for(w.c.delete("/api/accounts/konto-3"), 5)
        dauer = time.monotonic() - t0

        assert r_del.status_code == 204
        # Deutlich unter EINER einzelnen Albumwartezeit — die alte Fassung
        # brauchte die SUMME aller vier (~4x JE).
        assert dauer < JE, f"DELETE brauchte {dauer:.2f}s, JE={JE}s (Konvoi?)"

        await asyncio.wait_for(t_auto, 5)
        for i in range(1, 5):
            assert "konto-3" not in _konten_in(w.store, f"a{i}")


# ---------------------------------------------------------------------------
# S6: Ein Schreiber haelt ein Album, die Kontoloeschung muss NICHT (mehr)
# darauf warten — der Schreiber heilt beim eigenen Zurueckschreiben.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_loeschung_wartet_nicht_auf_ein_belegtes_album_schreiber_heilt_es_selbst(
    tmp_path, monkeypatch
):
    """Blind-Sonde S6, angepasst: Vorher pruefte diese Probe, dass die
    Kontoloeschung ALS WARTESCHLANGEN-EINTRAG an einem belegten Schloss
    haengt und dort abgebrochen werden kann. Das ist nach dieser Nacharbeit
    nicht mehr der Fall — GENAU DAS ist der Fix (kein Konvoi mehr, siehe
    WICHTIG 3): Die Loeschung ueberspringt ein belegtes Album, statt darauf
    zu warten. Was bleiben MUSS: a2 traegt am Ende trotzdem nur noch
    `konto-1` — der Refresh, der a2 haelt, entfernt die tote Referenz selbst
    beim Zurueckschreiben (`ConfigStore._ohne_tote_konten`), OHNE dass ein
    zweites DELETE noetig waere."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_album_assets_with_name", "immich-a2")
    async with _App(tmp_path, monkeypatch,
                    [_album("a1", 1, [1, 2]), _album("a2", 1, [1, 2])]) as w:
        t_ref = asyncio.create_task(w.c.post("/api/sync/album/a2/refresh"))
        await asyncio.wait_for(welt.angekommen.wait(), 5)

        t0 = time.monotonic()
        r_del = await asyncio.wait_for(w.c.delete("/api/accounts/konto-2"), 5)
        dauer = time.monotonic() - t0

        assert r_del.status_code == 204
        assert dauer < 0.5, f"Loeschung hat auf das belegte Album gewartet ({dauer:.2f}s)"
        # a1 (Schloss frei) ist sofort bereinigt.
        assert _konten_in(w.store, "a1") == {"konto-1"}

        welt.tor.set()
        await t_ref

        # a2 (war belegt) ist ohne ein zweites DELETE bereinigt.
        assert _konten_in(w.store, "a2") == {"konto-1"}


# ---------------------------------------------------------------------------
# S7: Auto-Sync und Kontoloeschung
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_sync_und_loeschung_kein_aufruf_mit_dem_geloeschten_schluessel_danach(
    tmp_path, monkeypatch
):
    """Blind-Sonde S7: Ein Sammelabgleich haelt a1, waehrenddessen wird ein
    Teilnehmer (`konto-2`) geloescht. Ab der Marke darf kein Immich-Aufruf
    mehr mit `konto-2`s Schluessel/Namen erfolgen."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_album_assets_with_name", "immich-a1")
    alben = [_album("a1", 1, [1, 2]), _album("a2", 1, [1, 2]), _album("a3", 2, [2, 1])]
    async with _App(tmp_path, monkeypatch, alben) as w:
        t_auto = asyncio.create_task(w.main._run_auto_sync(w.main.app.state))
        await asyncio.wait_for(welt.angekommen.wait(), 5)
        welt.marke = len(welt.aufrufe)

        r_del = await asyncio.wait_for(w.c.delete("/api/accounts/konto-2"), 5)
        assert r_del.status_code == 204

        welt.tor.set()
        await asyncio.wait_for(t_auto, 5)

        for aid in ("a1", "a2", "a3"):
            assert "konto-2" not in _konten_in(w.store, aid), aid
        immich_mit_zwei_danach = [x for x in welt.nach_marke() if "konto2" in x[1]]
        assert not immich_mit_zwei_danach, immich_mit_zwei_danach


# ---------------------------------------------------------------------------
# S8: Album verschwindet, waehrend Kontoloeschung laeuft
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_album_entfernen_und_konto_loeschen_gleichzeitig(tmp_path, monkeypatch):
    """Blind-Sonde S8: `DELETE /api/sync/albums/a1` wartet hinter einem
    laufenden Refresh (nimmt weiterhin dasselbe Schloss und wartet echt);
    die Kontoloeschung (`konto-2`, Teilnehmer in a1 UND a2) muss darauf NICHT
    warten und trotzdem 204 liefern, und a2 (Schloss frei) muss bereinigt
    sein."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_album_assets_with_name", "immich-a1")
    async with _App(tmp_path, monkeypatch,
                    [_album("a1", 1, [1, 2]), _album("a2", 1, [1, 2])]) as w:
        t_ref = asyncio.create_task(w.c.post("/api/sync/album/a1/refresh"))
        await asyncio.wait_for(welt.angekommen.wait(), 5)
        t_da = asyncio.create_task(w.c.delete("/api/sync/albums/a1"))
        assert await _bis_wartend("a1", 1), "Album-Entfernen wartet nicht am Schloss"

        r_dk = await asyncio.wait_for(w.c.delete("/api/accounts/konto-2"), 5)
        assert r_dk.status_code == 204
        assert _konten_in(w.store, "a2") == {"konto-1"}

        welt.tor.set()
        r_ref, r_da = await asyncio.wait_for(asyncio.gather(t_ref, t_da), 5)
        assert r_ref.status_code == 200
        assert r_da.status_code == 204


# ---------------------------------------------------------------------------
# G: Kontoloeschung || Gruppen-Entfernen (mehrfach) || Refresh — keine
# Verklemmung
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_keine_verklemmung_konto_loeschen_mehrere_alben_entfernen_und_refresh(
    tmp_path, monkeypatch
):
    """Gegenpruefer-Probe G: Kontoloeschung und drei Album-Entfernungen laufen
    gleichzeitig mit einem laufenden Refresh — alles muss innerhalb eines
    Zeitlimits fertig werden (kein Haengenbleiben) und alle vier Aufrufe
    liefern 204."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_album_assets_with_name", "immich-a1")
    alben = [_album(f"a{i}", 1, [1, 3]) for i in range(1, 4)]
    async with _App(tmp_path, monkeypatch, alben) as w:
        t_ref = asyncio.create_task(w.c.post("/api/sync/album/a1/refresh"))
        await asyncio.wait_for(welt.angekommen.wait(), 5)

        aufrufe = [w.c.delete("/api/accounts/konto-3")] + [
            w.c.delete(f"/api/sync/albums/a{i}") for i in (1, 2, 3)
        ]
        # tor erst NACH dem Start aller vier setzen, aber ohne endlos auf
        # Warteschlangen zu pollen (das Wesentliche hier ist die
        # Verklemmungsfreiheit, nicht die exakte Ankunftsreihenfolge).
        antworten_task = asyncio.gather(*aufrufe)
        await asyncio.sleep(0.05)
        welt.tor.set()

        r_ref, antworten = await asyncio.wait_for(
            asyncio.gather(t_ref, antworten_task), 5)

        assert r_ref.status_code == 200
        assert [r.status_code for r in antworten] == [204, 204, 204, 204]


# ---------------------------------------------------------------------------
# H: Anlegen/Verknuepfen schreibt kein geloeschtes Konto in ein NEUES Album
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verknuepfen_schreibt_kein_waehrenddessen_geloeschtes_konto_in_neues_album(
    tmp_path, monkeypatch
):
    """Gegenpruefer-Probe H: `link_existing_album` (kein Albumschloss, wie
    `add_managed_album` es fuer die Anlage-Pfade nie hatte) haengt
    `konto-3` an, WAEHREND dessen Konto vollstaendig geloescht wird.
    `ConfigStore.add_managed_album` filtert tote Konten jetzt genauso wie
    `update_managed_album` (`_ohne_tote_konten`) — das neue Album darf das
    geloeschte Konto deshalb nie enthalten, unabhaengig vom Zeitpunkt der
    Loeschung. Die Anlage-Schloesser selbst (`gruppen_schloss`/
    `treffer_schloss`, `resolve_group_id`) bleiben unangetastet."""
    from services import sync_service

    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    async with _App(tmp_path, monkeypatch, []) as w:
        owner = w.store.get_account("konto-1")
        accs = w.store.list_accounts()

        # Konto-3 wird geloescht, BEVOR `link_existing_album` ueberhaupt
        # angefragt wird (die Anlage-Pfade nehmen `all_accounts` immer als
        # Schnappschuss VOR jedem Aufruf, wie der Router es tut) — die
        # Regel muss also unabhaengig vom genauen Zeitpunkt greifen.
        r_del = await w.c.delete("/api/accounts/konto-3")
        assert r_del.status_code == 204

        managed, _logs = await sync_service.link_existing_album(
            match_id="m-neu", owner_account=owner, album_id="immich-neu",
            album_name="Neu", all_accounts=accs,
            person_refs=[_ref(1), _ref(3)], store=w.store, group_id="g-neu",
        )

        assert managed is not None
        konten = {r["account_id"] for r in
                  w.store.get_managed_album(managed.id).person_refs}
        assert "konto-3" not in konten, konten
