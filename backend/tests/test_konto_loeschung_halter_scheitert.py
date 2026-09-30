"""Nacharbeit 2 (#117/#121/#103, LETZTE Runde): Halter scheitert -> tote
Referenz blieb bisher stehen; Status/Caches der Kontoloeschung haengen jetzt
an DER Kennung, nicht an irgendeinem Rest; `locked()` allein ist nicht
verbindlich; Immich-Aufrufbloecke nach dem 204 pruefen frisch.

Blind- und Gegenpruefer haben `11c0524` unabhaengig widerlegt: „Gesperrte
Alben bereinigt der Halter beim eigenen Schreiben" hatte eine Luecke —
Halter, die SCHEITERN und deshalb NICHT schreiben (Immich-Fehler, Album weg,
Besitzer fehlt, Umbenennen 404, Abbruch), liessen die tote Referenz liegen;
beim verwaisten Album dauerhaft, auch nach einem Neustart.

DIE NEUE REGEL: Jeder der drei Schloss-Wrapper (`sync_service.
refresh_managed_album`, `.rename_managed_album`, `.extend_match`) raeumt tote
Kontoreferenzen SEINES Albums jetzt in einem `finally`, das den ganzen Rumpf
unter dem Schloss umschliesst — bei JEDEM Ausgang, nicht nur beim Erfolg
(`sync_service._raeume_tote_referenzen_synchron`). `ConfigStore._migrate`
raeumt zusaetzlich einmal beim Start, damit ein Absturz vor dem naechsten
erfolgreichen Schreibvorgang keine Reste ueber einen Neustart hinweg
konserviert.

DIESE DATEI BAUT DIE ABLAEUFE DER PRUEFSTIMMEN-PROBEN NACH (Bau-Brief Block 2
und 5; Herkunft je Test im Docstring: Sonde-Kennungen aus
`scratchpad/welle4/blind/S3na1/kopie/backend/sonde/test_sonde_na1.py`,
`test_sonde_vergleich.py`, `test_sonde_m17.py`, Gegenpruefer-Proben aus
`scratchpad/welle4/gegen/S3na1/proben/test_zz_gegen_na1.py`).

Alle Daten erfunden (erfundene Konten, Personen, Alben, Schluessel
`platzhalter`, Adressen `http://<name>.invalid`); das Repo ist oeffentlich.
"""
import asyncio
import json
import time

import httpx
import pytest

from services.immich_client import AlbumNotFoundError


def _konto(n: int) -> dict:
    return {"id": f"konto-{n}", "name": f"Konto {n}",
            "immich_url": f"http://konto{n}.invalid", "api_key": "platzhalter",
            "color": "#11111" + str(n), "user_id": f"u{n}"}


KONTEN = {n: _konto(n) for n in (1, 2, 3)}


def _ref(n: int, person_id: str | None = None) -> dict:
    return {"account_id": f"konto-{n}", "person_id": person_id or f"p{n}",
            "person_name": f"PersonName{n}", "account_name": f"Konto {n}",
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
    def __init__(self):
        self.aufrufe: list[tuple[float, str, str, str]] = []
        self.halt_bei = None
        self.angekommen = asyncio.Event()
        self.tor = asyncio.Event()
        self.fehler_nach_tor = None
        self.marke = 0

    def nach_marke(self):
        return self.aufrufe[self.marke:]


def _immich_attrappe(monkeypatch, welt: _Welt, teilen_stubben: bool = True):
    from services import sync_service

    class Client:
        def __init__(self, url, key, *_a, **_k):
            self.url = url

        async def _h(self, m, a):
            self_time = time.monotonic()
            welt.aufrufe.append((self_time, self.url, m, a))
            if welt.halt_bei == (m, a) and not welt.angekommen.is_set():
                welt.angekommen.set()
                await welt.tor.wait()
                if welt.fehler_nach_tor is not None:
                    raise welt.fehler_nach_tor

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

        async def get_album_user_ids(self, aid):
            await self._h("get_album_user_ids", aid)
            return set()

        async def share_album_with_users(self, aid, entries):
            await self._h("share_album_with_users", ",".join(e["userId"] for e in entries))
            return {}

        async def create_album(self, name, ids):
            await self._h("create_album", name)
            return {"id": "immich-neu"}

    monkeypatch.setattr(sync_service, "ImmichClient", Client)
    if teilen_stubben:
        async def ohne(*_a, **_k):
            return []
        monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne)


class _App:
    def __init__(self, tmp_path, monkeypatch, alben, konten=None):
        import main
        self.main = main
        self.pfad = _bestand(tmp_path, alben, konten)
        monkeypatch.setattr(main.settings, "secret", "welle4-s3-na2", raising=False)
        monkeypatch.setattr(main.settings, "config_path", str(self.pfad), raising=False)

    async def __aenter__(self):
        # Dasselbe Leeren wie in `test_konto_loeschung_ohne_konvoi.py`: ein
        # `asyncio.Lock` aus dem (bereits geschlossenen) Ring eines frueheren
        # Tests darf hier nicht wiederverwendet werden.
        from services import sync_service
        sync_service._album_locks.clear()
        self._lc = self.main.app.router.lifespan_context(self.main.app)
        await self._lc.__aenter__()
        self.store = self.main.app.state.store
        self.c = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.main.app),
                                    base_url="http://test")
        await self.c.__aenter__()
        r = await self.c.post("/api/auth/login", json={"token": "welle4-s3-na2"})
        assert r.status_code == 200
        return self

    async def __aexit__(self, *a):
        await self.c.__aexit__(*a)
        await self._lc.__aexit__(*a)


async def _bis_wartend(album_id: str, n: int = 1, timeout: float = 2.0) -> bool:
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


# =============================================================================
# BLOCKER: Ein Halter, der SCHEITERT, hinterlaesst nach seinem Ende keine tote
# Referenz mehr — Blind-Sonden test_A/test_V3.
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("fehler", ["album_weg", "immich_500"])
@pytest.mark.parametrize("wer", [1, 2])
async def test_A_halter_scheitert_tote_referenz_bleibt_nicht(tmp_path, monkeypatch, fehler, wer):
    """Blind-Sonde test_A: Ein Refresh haelt a1s Schloss (haengt an
    `get_album_assets_with_name`); waehrenddessen wird `konto-{wer}`
    geloescht (Besitzer bei wer=1, Teilnehmer bei wer=2); danach scheitert
    der bereits laufende Immich-Aufruf (Album weg ODER 500) — er darf zu Ende
    laufen (`fehler_nach_tor`).

    ROT unter `11c0524`: Der Refresh schrieb nie (er scheitert), also blieb
    die tote Referenz auf `konto-{wer}` in `a1` stehen — dauerhaft, auch nach
    einem zweiten Refresh, einem Umbenennen und einem Auto-Sync, weil keiner
    von ihnen je wieder erfolgreich durch DIESES Album schreibt (das Album
    bleibt ja verwaist bzw. kann nichts mehr aendern, das den Rest raeumt).
    GRUEN seit dem `finally` in `refresh_managed_album`.
    """
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_album_assets_with_name", "immich-a1")
    welt.fehler_nach_tor = (AlbumNotFoundError("immich-a1") if fehler == "album_weg"
                             else RuntimeError("Immich antwortet mit 500"))
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2])]) as w:
        t = asyncio.create_task(w.c.post("/api/sync/album/a1/refresh"))
        # `welt.tor.set()` steht in einem `finally`: Ein scheiterndes `assert`
        # unten darf den Refresh nicht als haengenden Wartenden zuruecklassen
        # — ein Task, dessen Haken nie geoeffnet wird, bleibt sonst fuer den
        # Rest des Testlaufs an `a1`s Schloss haengen (Keine Verklemmung,
        # Nachweis-Pflicht dieser Nacharbeit).
        try:
            await asyncio.wait_for(welt.angekommen.wait(), 5)
            r_del = await asyncio.wait_for(w.c.delete(f"/api/accounts/konto-{wer}"), 5)
            assert r_del.status_code == 204
        finally:
            welt.tor.set()
        r_ref = await asyncio.wait_for(t, 5)
        assert r_ref.status_code == 200
        # Der Refresh selbst meldet einen Fehlereintrag (Album weg/Immich-
        # Fehler) — das ist erwartet, kein Erfolg wird behauptet.
        entries = r_ref.json()
        assert any(e["status"] == "error" for e in entries), entries

        konten_direkt_danach = _konten_in(w.store, "a1")
        assert f"konto-{wer}" not in konten_direkt_danach, konten_direkt_danach

        # Auch auf der Platte ist die Referenz weg — nicht nur im Speicher.
        platte = w.pfad.read_text(encoding="utf-8")
        assert f"PersonName{wer}" not in platte, "Personenname blieb auf der Platte"

        # DELETE einer erfundenen Kennung bleibt ein echter Nichttreffer.
        r_erfunden = await asyncio.wait_for(
            w.c.delete("/api/accounts/gibt-es-nicht-und-gab-es-nie"), 5)
        assert r_erfunden.status_code == 404


@pytest.mark.asyncio
async def test_V3_halter_scheitert_besitzer_persistiert_nicht(tmp_path, monkeypatch):
    """Blind-Sonde test_V3 (Vergleichssonde): derselbe Fall wie test_A,
    speziell fuer den BESITZER (owner=1, wer=1) und mit dem DELETE als eigene
    Hintergrund-Aufgabe (dieselbe Form wie die Sonde: die Loeschung laeuft
    tatsaechlich VOLLSTAENDIG durch, waehrend der Refresh noch am Immich-
    Aufruf haengt)."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_album_assets_with_name", "immich-a1")
    welt.fehler_nach_tor = AlbumNotFoundError("immich-a1")
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2])]) as w:
        t = asyncio.create_task(w.c.post("/api/sync/album/a1/refresh"))
        await asyncio.wait_for(welt.angekommen.wait(), 5)

        t_del = asyncio.create_task(w.c.delete("/api/accounts/konto-1"))
        # `welt.tor.set()` steht in einem `finally`: Ein scheiterndes `assert`
        # unten darf weder den Refresh noch das DELETE als haengenden
        # Wartenden zuruecklassen (Keine Verklemmung, Nachweis-Pflicht).
        try:
            await asyncio.sleep(0.2)
            assert t_del.done(), "DELETE lief nicht vollstaendig durch, waehrend der Refresh haengt"
        finally:
            welt.tor.set()
        await asyncio.wait_for(t, 5)
        r_del = await asyncio.wait_for(t_del, 5)

        assert r_del.status_code == 204
        assert "konto-1" not in _konten_in(w.store, "a1")
        assert "PersonName1" not in w.pfad.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_umbenennen_404_halter_scheitert_tote_referenz_bleibt_nicht(tmp_path, monkeypatch):
    """Dieselbe Klasse wie test_A, fuer den Umbenennen-Wrapper: `update_album`
    scheitert mit 404 (Album in Immich weg), nachdem ein Teilnehmer
    waehrenddessen geloescht wurde. Umbenennen selbst meldet einen
    Fehlereintrag (`log_album_not_found`) und schreibt NIE — ohne das
    `finally` in `rename_managed_album` bliebe die tote Referenz stehen."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("update_album", "immich-a1")
    welt.fehler_nach_tor = AlbumNotFoundError("immich-a1")
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2])]) as w:
        t = asyncio.create_task(w.c.patch("/api/sync/albums/a1", json={"album_name": "Neu"}))
        # `welt.tor.set()` steht in einem `finally`: siehe test_A.
        try:
            await asyncio.wait_for(welt.angekommen.wait(), 5)
            r_del = await asyncio.wait_for(w.c.delete("/api/accounts/konto-2"), 5)
            assert r_del.status_code == 204
        finally:
            welt.tor.set()
        r = await asyncio.wait_for(t, 5)
        assert r.status_code == 200
        entries = r.json()
        assert entries and entries[0]["status"] == "error", entries

        assert "konto-2" not in _konten_in(w.store, "a1")


@pytest.mark.asyncio
async def test_abbruch_waehrend_immich_wartet_raeumt_trotzdem(tmp_path, monkeypatch):
    """BLOCKER, Abbruch/`CancelledError`: Ein Refresh haengt am Immich-Aufruf,
    waehrenddessen wird ein Teilnehmer geloescht; DANACH wird der Refresh
    selbst abgebrochen (`Task.cancel()`), statt normal zu Ende zu laufen. Das
    `finally` in `refresh_managed_album` muss auch hier greifen — Python
    fuehrt `finally` aus, bevor `CancelledError` weiter nach oben laeuft."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_album_assets_with_name", "immich-a1")
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2])]) as w:
        from services import sync_service

        managed = w.store.get_managed_album("a1")
        t = asyncio.create_task(
            sync_service.refresh_managed_album(managed, w.store.list_accounts(), w.store)
        )
        await asyncio.wait_for(welt.angekommen.wait(), 5)

        r_del = await asyncio.wait_for(w.c.delete("/api/accounts/konto-2"), 5)
        assert r_del.status_code == 204

        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t

        assert "konto-2" not in _konten_in(w.store, "a1")


# =============================================================================
# Start-Heilung: `ConfigStore._migrate` raeumt tote Referenzen einmal beim
# Laden — Blind-Sonde test_sonde_m17 (M17/Heilweg).
# =============================================================================

@pytest.mark.asyncio
async def test_neustart_heilt_tote_referenz_ohne_jeden_weiteren_schreibvorgang(tmp_path):
    """Kein Refresh/Umbenennen/Erweitern, keine Kontoloeschung ueber diesen
    Prozess — die tote Referenz steht bereits so in der Datei (etwa Ergebnis
    eines fruehreren Absturzes). Ein blosses `ConfigStore(pfad)` (wie beim
    Start der Anwendung) muss sie beim Laden raeumen.

    ROT unter `11c0524`: `_migrate()` fuellte nur fehlende Felder auf, filterte
    aber nie nach Kontoexistenz — ein Neustart allein heilte nichts."""
    from services.config_store import ConfigStore

    pfad = _bestand(tmp_path, [_album("a1", 1, [1, 2])], konten=[KONTEN[1]])
    store = ConfigStore(str(pfad))

    assert _konten_in(store, "a1") == {"konto-1"}
    # Auch auf der Platte, nicht nur im Speicher — `_migrate` speichert bei
    # Aenderung.
    roh = json.loads(pfad.read_text(encoding="utf-8"))
    refs = roh["managed_albums"][0]["person_refs"]
    assert [r["account_id"] for r in refs] == ["konto-1"]


@pytest.mark.asyncio
async def test_neustart_ohne_tote_referenzen_schreibt_nicht_erneut(tmp_path, monkeypatch):
    """Gegenprobe zur Heilung: Ein Bestand OHNE tote Referenzen loest beim
    Start keinen zusaetzlichen Schreibvorgang aus — sonst waere jeder Start
    ein `_save()`, unabhaengig davon, ob es etwas zu heilen gibt.

    ERSTER Start heilt hier noch andere, von dieser Aenderung UNABHAENGIGE
    Kleinigkeiten (`linked_match_ids` aus einer leeren Fixture-Vorgabe,
    fehlende `group_id`) — deshalb wird EINMAL geladen (dieser Start darf
    speichern) und danach ein ZWEITER, frischer Store auf demselben Pfad
    beobachtet: Der darf nichts mehr zu tun finden."""
    from services.config_store import ConfigStore

    pfad = _bestand(tmp_path, [_album("a1", 1, [1, 2])])
    ConfigStore(str(pfad))  # erster Start: migriert ggf. Nebensaechliches

    aufrufe = {"n": 0}
    orig_save = ConfigStore._save

    def gezaehlt(self):
        aufrufe["n"] += 1
        orig_save(self)

    monkeypatch.setattr(ConfigStore, "_save", gezaehlt)
    ConfigStore(str(pfad))
    assert aufrufe["n"] == 0, "zweiter Start hat gespeichert, obwohl nichts zu heilen war"


@pytest.mark.asyncio
async def test_heilweg_raeumt_auch_ein_ganz_anderes_totes_konto(tmp_path):
    """Blind-Sonde test_sonde_m17::test_heilweg_raeumt_anderes_totes_konto:
    `delete_account("konto-2")` muss nicht nur `konto-2` aus `a1` entfernen,
    sondern auch eine Referenz auf `konto-alt` — ein VOELLIG ANDERES Konto.
    Diese Regel stammt aus Nacharbeit 1 ('HEILWEG'), hatte dort aber keinen
    Test in der Suite, der sie von der AKTUELL geloeschten Kennung
    unterscheidet: M4 (Heilweg nur `== account_id` statt `not in
    lebende_konten`) ueberlebte deshalb bis Nacharbeit 2 unbemerkt die volle
    Suite (Blind W6).

    Der Rest wird absichtlich DIREKT in `store._data` eingespeist, nicht ueber
    die JSON-Datei: Ein frischer Start heilt seit Nacharbeit 2 selbst schon
    (siehe die Start-Heilungs-Proben oben) und wuerde den Rest laengst
    entfernt haben, bevor `delete_account` ueberhaupt liefe — dieser Test
    prueft gezielt `delete_account`s EIGENEN Heilweg, unabhaengig von der
    Start-Heilung."""
    from services.config_store import ConfigStore

    pfad = _bestand(tmp_path, [_album("a1", 1, [1]), _album("a2", 1, [1, 2])])
    store = ConfigStore(str(pfad))
    a1 = store.get_managed_album("a1")
    a1.person_refs.append(_ref("alt", "p-alt"))
    store._data["managed_albums"][0]["person_refs"] = a1.person_refs

    ok = await store.delete_account("konto-2")

    assert ok is True
    refs_a1 = [r["account_id"] for r in store.get_managed_album("a1").person_refs]
    assert refs_a1 == ["konto-1"], (
        f"konto-alt (ein VOELLIG ANDERES, schon vorher totes Konto) blieb stehen: {refs_a1}")
    assert "konto-2" not in _konten_in(store, "a2")


@pytest.mark.asyncio
async def test_kontenzeile_ist_sofort_auf_der_platte_auch_ohne_alben(tmp_path):
    """Blind-Sonde test_sonde_m17::test_kontoloeschung_ohne_alben_ist_auf_platte
    (M17): Ein Konto OHNE jedes verwaltete Album — die Heilschleife hat dann
    NICHTS zu tun und loest deshalb KEINEN weiteren `_save()` aus. Die
    Kontenzeile muss trotzdem SOFORT persistiert sein, nicht erst beim
    naechsten Schreibvorgang irgendeines Albums (den es hier gar nicht gibt).

    ROT unter `11c0524` (Mutation M17, `_save()` direkt nach dem Loeschen der
    Kontenzeile entfernt): Ohne Alben, die noch einen weiteren Schreibvorgang
    ausloesen, waere ein Absturz direkt nach `delete_account` mit dieser
    Mutation folgenlos fuer die Antwort (204), aber die Kontenzeile bliebe
    auf der Platte — ein Neustart brächte das geloeschte Konto zurueck."""
    from services.config_store import ConfigStore

    pfad = _bestand(tmp_path, [], konten=[KONTEN[1]])
    store = ConfigStore(str(pfad))

    assert await store.delete_account("konto-1") is True

    # Neustart: frischer Store von der PLATTE, ohne dass hier irgendein
    # weiterer Schreibvorgang stattgefunden haette.
    neu = ConfigStore(str(pfad))
    assert neu.get_account("konto-1") is None


# =============================================================================
# WICHTIG 1: Status und Caches haengen an DER Kennung, nicht an irgendeinem
# Rest — Blind W1, Gegen N4; K1: zweites DELETE waehrend gesperrtem Album.
# =============================================================================

@pytest.mark.asyncio
async def test_N4_erfundene_kennung_mit_fremden_resten_bleibt_404(tmp_path, monkeypatch):
    """Gegen-Probe N4, verkettet mit dem BLOCKER (test_A): Erst scheitert ein
    Halter (Immich meldet 500, nachdem `konto-3` waehrenddessen geloescht
    wurde) — GENAU DAS ist die einzige Art, wie ein UNGESPERRTES Album zur
    Laufzeit (nicht nur beim Start) noch eine tote Referenz tragen kann.
    Unter `11c0524` blieb sie dort STEHEN (kein `finally`), und ein
    UNABHAENGIGES, DELETE auf eine erfundene Kennung heilte sie in DERSELBEN
    Anfrage — und antwortete faelschlich 204 fuer eine Kennung, die nie
    existiert hat. Seit dem BLOCKER-Fix ist a1 zu diesem Zeitpunkt schon
    laengst bereinigt (das `finally` lief, noch unter dem Schloss) — die
    erfundene Kennung findet also gar nichts mehr vor, das ihr zugerechnet
    werden koennte, und bleibt aus EIGENEM Recht 404."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_album_assets_with_name", "immich-a1")
    welt.fehler_nach_tor = RuntimeError("Immich antwortet mit 500")
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2, 3])]) as w:
        t = asyncio.create_task(w.c.post("/api/sync/album/a1/refresh"))
        # `welt.tor.set()` steht in einem `finally`: siehe test_A.
        try:
            await asyncio.wait_for(welt.angekommen.wait(), 5)
            r_del3 = await asyncio.wait_for(w.c.delete("/api/accounts/konto-3"), 5)
            assert r_del3.status_code == 204
        finally:
            welt.tor.set()
        r_ref = await asyncio.wait_for(t, 5)
        assert r_ref.status_code == 200
        assert any(e["status"] == "error" for e in r_ref.json())

        # Der Halter ist fertig (Fehler, keine Ausnahme mehr offen); a1 ist
        # unter der neuen Regel bereits bereinigt — siehe test_A.
        assert "konto-3" not in _konten_in(w.store, "a1")

        r = await asyncio.wait_for(w.c.delete("/api/accounts/gibt-es-nicht-und-gab-es-nie"), 5)
        assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_caches_nur_fuer_eine_kennung_die_wirklich_existierte(tmp_path, monkeypatch):
    """Blind W1: `DELETE` mit einem eigenen Rest eines FREMDEN, bereits
    geloeschten Kontos darf dessen Cache-Eintraege nicht ein zweites Mal
    "leeren" — `thumbnail_cache`/`client_pool` sind pro ECHTEM Konto
    gefuehrt, und dieses Konto ist zu diesem Zeitpunkt schon weg. Derselbe
    Aufbau wie test_N4 (Rest waehrend eines gesperrten Albums), diesmal wird
    DIESELBE (jetzt tote) Kennung ein zweites Mal angefragt."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_album_assets_with_name", "immich-a1")
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2, 3])]) as w:
        t = asyncio.create_task(w.c.post("/api/sync/album/a1/refresh"))
        await asyncio.wait_for(welt.angekommen.wait(), 5)

        aufgerufen = {"thumbnail": None, "pool": None}
        orig_thumb = w.main.app.state.thumbnail_cache.clear_account
        orig_pool = w.main.app.state.client_pool.invalidate

        def thumb(account_id):
            aufgerufen["thumbnail"] = account_id
            return orig_thumb(account_id)

        def pool(account_id):
            aufgerufen["pool"] = account_id
            return orig_pool(account_id)

        w.main.app.state.thumbnail_cache.clear_account = thumb
        w.main.app.state.client_pool.invalidate = pool

        # `welt.tor.set()` steht in einem `finally`: siehe test_A.
        try:
            r1 = await asyncio.wait_for(w.c.delete("/api/accounts/konto-3"), 5)
            assert r1.status_code == 204
            assert aufgerufen == {"thumbnail": "konto-3", "pool": "konto-3"}, (
                "das ERSTE, ECHTE DELETE muss seine eigenen Caches leeren")

            aufgerufen["thumbnail"] = aufgerufen["pool"] = None
            assert w.store.get_account("konto-3") is None

            # a1 haelt das Schloss noch — konto-3 steht noch als Rest darin,
            # das ZWEITE DELETE auf dieselbe (jetzt tote) Kennung bleibt 204
            # (der Rest ist real), leert aber KEINE Caches mehr — es gibt
            # kein echtes Konto mehr, dessen Caches das waeren.
            r2 = await asyncio.wait_for(w.c.delete("/api/accounts/konto-3"), 5)
            assert r2.status_code == 204
            assert aufgerufen == {"thumbnail": None, "pool": None}, (
                "Caches wurden fuer eine Kennung geleert, die kein echtes Konto mehr war")
        finally:
            welt.tor.set()
        await asyncio.wait_for(t, 5)


@pytest.mark.asyncio
async def test_K1_zweites_delete_mit_eigenem_rest_in_gesperrtem_album_bleibt_204(
    tmp_path, monkeypatch
):
    """K1 (Bau-Brief WICHTIG 1): Ein zweites `DELETE` auf eine Kennung mit
    einer EIGENEN Referenz, waehrend GENAU dieses Album gesperrt ist, bleibt
    204 — nicht 404. Die Referenz ist real (nur gerade nicht raeumbar), also
    ist die Antwort weiterhin ein Treffer."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_album_assets_with_name", "immich-a1")
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2])]) as w:
        t = asyncio.create_task(w.c.post("/api/sync/album/a1/refresh"))
        await asyncio.wait_for(welt.angekommen.wait(), 5)

        # `welt.tor.set()` steht in einem `finally`: siehe test_A.
        try:
            r1 = await asyncio.wait_for(w.c.delete("/api/accounts/konto-2"), 5)
            assert r1.status_code == 204
            # a1 haelt das Schloss noch (Refresh haengt) — die Referenz ist
            # noch nicht geraeumt.
            assert "konto-2" in _konten_in(w.store, "a1")

            r2 = await asyncio.wait_for(w.c.delete("/api/accounts/konto-2"), 5)
            assert r2.status_code == 204, (
                "zweites DELETE mit eigenem Rest in gesperrtem Album wurde 404")
        finally:
            welt.tor.set()
        await asyncio.wait_for(t, 5)
        assert "konto-2" not in _konten_in(w.store, "a1")


# =============================================================================
# WICHTIG 2: `locked()` ist nicht verbindlich — Blind W2, Gegen N2/N3.
# =============================================================================

@pytest.mark.asyncio
async def test_N2_delete_wartet_nicht_hinter_einem_bereits_geweckten_wartenden(
    tmp_path, monkeypatch
):
    """Gegen-Probe N2: Ein Refresh haelt a1s Schloss; ein Umbenennen WARTET
    bereits in der Schlange (echter Warteschlangen-Eintrag); GENAU IN DIESEM
    Moment gibt der Refresh das Schloss frei — `locked()` meldet ab hier
    `False`, aber der Wartende (`asyncio.Lock` ist FAIR) ist schon geweckt.
    `delete_account` darf sich davon nicht taeuschen lassen und hinter dem
    Wartenden landen.

    ROT ohne die Wartenden-Pruefung: `delete_account` haette dann so lange
    gebraucht wie die GANZE Umbenennen-Operation (hier: `HALTEN` Sekunden)."""
    HALTEN = 1.0
    ev = asyncio.Event()

    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2])]) as w:
        from services import sync_service

        async def haken(url, m, a):
            if m == "get_album_assets_with_name" and "a_drin" not in state:
                state["a_drin"] = True
                await ev.wait()
            if m == "update_album":
                await asyncio.sleep(HALTEN)

        state: dict = {}

        # Eigene Attrappe fuer dieses Timing (Refresh gibt frei, GENAU dann
        # steht das Umbenennen schon in der Schlange).
        class Client:
            def __init__(self, url, key, *_a, **_k):
                self.url = url

            async def get_person(self, pid):
                return {"id": pid, "name": "X"}

            async def get_album_assets(self, aid):
                return []

            async def get_album_assets_with_name(self, aid):
                await haken(self.url, "get_album_assets_with_name", aid)
                return aid.removeprefix("immich-"), []

            async def get_person_assets(self, pid):
                return [{"id": "asset-1"}]

            async def add_assets_to_album(self, aid, ids):
                return [{"id": i, "success": True} for i in ids]

            async def update_album(self, aid, payload):
                await haken(self.url, "update_album", aid)
                return {"id": aid, **payload}

            async def update_person(self, pid, payload):
                return {"id": pid, **payload}

        monkeypatch.setattr(sync_service, "ImmichClient", Client)

        t_a = asyncio.create_task(w.c.post("/api/sync/album/a1/refresh"))
        while "a_drin" not in state:
            await asyncio.sleep(0)
        t_b = asyncio.create_task(w.c.patch("/api/sync/albums/a1", json={"album_name": "Neu"}))
        assert await _bis_wartend("a1", 1), "Umbenennen wartet nicht am Schloss"

        # FENSTER ERZWINGEN: A freigeben und im selben Schritt die Loeschung
        # einreihen — sie laeuft, nachdem A das Schloss freigibt und bevor
        # B (bereits geweckt) es wieder nimmt. `store.delete_account` wird
        # HIER DIREKT gerufen, NICHT ueber die HTTP-Tuer: Der ASGI-Umweg
        # (Middleware, Routing, Pydantic) braucht selbst mehrere
        # Ereignisschleifen-Runden und liess das enge Fenster in einer
        # frueheren Fassung dieser Probe unbeobachtet verstreichen —
        # `schloss.locked()` war beim tatsaechlichen Eintreffen der HTTP-
        # Anfrage bereits wieder `True` (der Wartende hatte laengst
        # zurueckerobert), und die Probe bestand scheinbar, ohne die
        # Fairness-Luecke je zu pruefen. `store.delete_account` direkt zu
        # rufen ist derselbe Aufruf, den der Router letztlich taetigt — nur
        # ohne den Umweg, der das Fenster verdeckt.
        ev.set()
        t0 = time.monotonic()
        schloss = sync_service._album_schloss("a1")
        gesehen = {}

        async def loeschen():
            gesehen["locked_bei_start"] = schloss.locked()
            gesehen["waiters_bei_start"] = len(schloss._waiters or [])
            r = await w.store.delete_account("konto-2")
            gesehen["dauer"] = time.monotonic() - t0
            return r

        t_d = asyncio.create_task(loeschen())
        ra, rb, rd = await asyncio.wait_for(asyncio.gather(t_a, t_b, t_d), 5)

        assert ra.status_code == 200 and rb.status_code == 200
        assert rd is True
        assert gesehen["waiters_bei_start"] >= 1 and not gesehen["locked_bei_start"], (
            "das Fenster (locked()==False, aber ein bereits geweckter Wartender "
            f"in der Schlange) wurde nicht getroffen: {gesehen}")
        assert gesehen["dauer"] < HALTEN / 2, (
            f"delete_account hat {gesehen['dauer']:.2f}s gebraucht — "
            f"hat es doch am Schloss gewartet? (Umbenennen haelt {HALTEN}s)")


# =============================================================================
# WICHTIG 3: Immich-Aufrufbloecke NACH dem 204 pruefen frisch, ob das Konto
# noch existiert — Gegen N5/N6/N6b.
# =============================================================================

@pytest.mark.asyncio
async def test_N5_erweitern_ruft_immich_nicht_mehr_mit_dem_schluessel_nach_204(
    tmp_path, monkeypatch
):
    """Gegen-Probe N5: Das NEUE Konto (`konto-3`) wird waehrend der
    Personen-Validierung (dem ERSTEN Immich-Aufruf des Erweiterns) geloescht.

    ROT unter `11c0524`: Die Bloecke „Assets hinzufuegen" und „Umbenennen"
    riefen danach trotzdem noch mit `konto-3`s (jetzt ungueltigem)
    Schluessel auf, UND es entstand ein `log_name_synced`-Eintrag mit
    `undo_data` auf das bereits geloeschte Konto."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2])]) as w:
        from services import sync_service

        state: dict = {}

        class Client:
            def __init__(self, url, key, *_a, **_k):
                self.url = url

            async def _spur(self, m, a):
                welt.aufrufe.append((time.monotonic(), self.url, m, a))

            async def get_person(self, pid):
                await self._spur("get_person", pid)
                if "konto3.invalid" in self.url and "del" not in state:
                    state["del"] = await asyncio.wait_for(
                        w.c.delete("/api/accounts/konto-3"), 5)
                    state["t_del"] = time.monotonic()
                return {"id": pid, "name": "X"}

            async def get_album_assets(self, aid):
                await self._spur("get_album_assets", aid)
                return []

            async def get_person_assets(self, pid):
                await self._spur("get_person_assets", pid)
                return [{"id": f"asset-{pid}"}]

            async def add_assets_to_album(self, aid, ids):
                await self._spur("add_assets_to_album", aid)
                return [{"id": i, "success": True} for i in ids]

            async def update_person(self, pid, payload):
                await self._spur("update_person", pid)
                return {"id": pid, **payload}

        monkeypatch.setattr(sync_service, "ImmichClient", Client)

        r = await asyncio.wait_for(w.c.post("/api/sync/extend", json={
            "managed_album_id": "a1", "account_id": "konto-3",
            "person_id": "p3", "person_name": "Drei", "canonical_name": "Kanon",
        }), 5)
        assert r.status_code == 200
        log_entries = r.json()

        assert "del" in state, "Der Immich-Haken wurde nie erreicht"
        assert state["del"].status_code == 204

        nach_204 = [(m, a) for (t, u, m, a) in welt.aufrufe
                    if t > state["t_del"] and "konto3.invalid" in u]
        assert not nach_204, f"Aufrufe mit konto-3s Schluessel NACH dem 204: {nach_204}"

        undo_auf_totes_konto = [
            e for e in log_entries
            if (e.get("undo_data") or {}).get("account_id") == "konto-3"
        ]
        assert not undo_auf_totes_konto, undo_auf_totes_konto

        assert "konto-3" not in _konten_in(w.store, "a1")


@pytest.mark.asyncio
async def test_N6_abgleich_besitzerschluessel_nicht_nach_204(tmp_path, monkeypatch):
    """Gegen-Probe N6: Der BESITZER (`konto-3`) wird waehrend des Teilens
    (`get_album_user_ids`, dem ersten Aufruf von `_share_album_if_needed`)
    geloescht. Danach darf weder `share_album_with_users` noch
    `get_album_assets_with_name` mit seinem Schluessel laufen."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt, teilen_stubben=False)
    async with _App(tmp_path, monkeypatch, [_album("a1", 3, [3, 1])]) as w:
        from services import sync_service

        state: dict = {}

        class Client:
            def __init__(self, url, key, *_a, **_k):
                self.url = url

            async def _spur(self, m, a):
                welt.aufrufe.append((time.monotonic(), self.url, m, a))

            async def get_album_user_ids(self, aid):
                await self._spur("get_album_user_ids", aid)
                if "del" not in state:
                    state["del"] = await asyncio.wait_for(
                        w.c.delete("/api/accounts/konto-3"), 5)
                    state["t_del"] = time.monotonic()
                return set()

            async def share_album_with_users(self, aid, entries):
                await self._spur("share_album_with_users", ",".join(
                    e["userId"] for e in entries))
                return {}

            async def get_album_assets_with_name(self, aid):
                await self._spur("get_album_assets_with_name", aid)
                return aid.removeprefix("immich-"), []

            async def get_person(self, pid):
                return {"id": pid, "name": "X"}

            async def get_person_assets(self, pid):
                return [{"id": f"asset-{pid}"}]

            async def add_assets_to_album(self, aid, ids):
                return [{"id": i, "success": True} for i in ids]

            async def update_person(self, pid, payload):
                return {"id": pid, **payload}

        monkeypatch.setattr(sync_service, "ImmichClient", Client)

        r = await asyncio.wait_for(w.c.post("/api/sync/album/a1/refresh"), 5)
        assert r.status_code == 200

        assert "del" in state and state["del"].status_code == 204
        nach_204 = [(m, a) for (t, u, m, a) in welt.aufrufe
                    if t > state["t_del"] and "konto3.invalid" in u]
        assert not nach_204, f"Aufrufe mit dem Besitzerschluessel NACH dem 204: {nach_204}"
        assert "konto-3" not in _konten_in(w.store, "a1")


@pytest.mark.asyncio
async def test_N6b_abgleich_teilt_nicht_mehr_mit_geloeschtem_teilnehmer(tmp_path, monkeypatch):
    """Gegen-Probe N6b: Ein TEILNEHMER (`konto-2`, nicht der Besitzer) wird
    waehrend `get_album_user_ids` geloescht — das Album darf danach nicht
    mehr mit seinem Immich-Benutzer geteilt werden."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt, teilen_stubben=False)
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2])]) as w:
        from services import sync_service

        state: dict = {}
        geteilt: list[str] = []

        class Client:
            def __init__(self, url, key, *_a, **_k):
                self.url = url

            async def get_album_user_ids(self, aid):
                if "del" not in state:
                    state["del"] = await asyncio.wait_for(
                        w.c.delete("/api/accounts/konto-2"), 5)
                return set()

            async def share_album_with_users(self, aid, entries):
                geteilt.extend(e["userId"] for e in entries)
                return {}

            async def get_album_assets_with_name(self, aid):
                return aid.removeprefix("immich-"), []

            async def get_person(self, pid):
                return {"id": pid, "name": "X"}

            async def get_person_assets(self, pid):
                return [{"id": f"asset-{pid}"}]

            async def add_assets_to_album(self, aid, ids):
                return [{"id": i, "success": True} for i in ids]

            async def update_person(self, pid, payload):
                return {"id": pid, **payload}

        monkeypatch.setattr(sync_service, "ImmichClient", Client)

        r = await asyncio.wait_for(w.c.post("/api/sync/album/a1/refresh"), 5)
        assert r.status_code == 200
        assert state["del"].status_code == 204
        assert "u2" not in geteilt, geteilt
        assert "konto-2" not in _konten_in(w.store, "a1")


# =============================================================================
# WICHTIG 4: Erweitern meldet ehrlich, wenn das hinzuzufuegende Konto still
# verworfen wurde — deckt sich mit test_N5 oben (kein `log_name_synced` mit
# totem `undo_data`); hier zusaetzlich die Antwort ohne stillen Erfolg.
# =============================================================================

@pytest.mark.asyncio
async def test_erweitern_meldet_ehrlich_wenn_das_neue_konto_verschwindet(tmp_path, monkeypatch):
    """Wird das neue Konto NACH der Personen-Validierung, aber VOR dem
    Assets-Block geloescht, meldet die Antwort das (bestehender Schluessel
    `log_person_validation_failed`, kein neuer `log_*`-Schluessel) — statt
    einen Erfolg zu behaupten, der die Referenz gleich wieder verliert."""
    welt = _Welt()
    _immich_attrappe(monkeypatch, welt)
    welt.halt_bei = ("get_album_assets", "immich-a1")
    async with _App(tmp_path, monkeypatch, [_album("a1", 1, [1, 2])]) as w:
        t = asyncio.create_task(w.c.post("/api/sync/extend", json={
            "managed_album_id": "a1", "account_id": "konto-3",
            "person_id": "p3", "person_name": "Drei"}))
        # `welt.tor.set()` steht in einem `finally`: siehe test_A.
        try:
            await asyncio.wait_for(welt.angekommen.wait(), 5)
            r_del = await asyncio.wait_for(w.c.delete("/api/accounts/konto-3"), 5)
            assert r_del.status_code == 204
        finally:
            welt.tor.set()
        r = await asyncio.wait_for(t, 5)
        assert r.status_code == 200
        entries = r.json()
        assert entries, "keine Protokollzeile — stiller Erfolg?"
        assert all(e["status"] == "error" for e in entries), entries
        assert all(e["message_key"] == "log_person_validation_failed" for e in entries), entries
        assert "konto-3" not in _konten_in(w.store, "a1")
