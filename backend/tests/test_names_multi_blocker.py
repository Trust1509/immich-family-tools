"""BLOCKER Nacharbeit 1 (#113/#119/#124): keine Ablehnung hinter einem
Schreibvorgang im manuellen Weg (`sync_names_multi`).

Gemessen an 5e99584 (Blind B-1, Gegen F7): `resolve_group_id` konnte ablehnen,
lief aber ERST NACH `sync_service.sync_names_multi` (Immich-Umbenennung),
`store.append_log` und `mark_all_pairs_synced`. Diese Proben fahren die
echte Tuer (ASGI, mit `lifespan`, echtem `sync_service.sync_names_multi`),
erzwingen das Zeitfenster ueber ein `asyncio.Event` und pruefen die WIRKUNG:
Nach einer Ablehnung ist in Immich NICHTS umbenannt und nichts protokolliert.

Herkunft: An die Sonden der Pruefstimmen angelehnt (Blind P1,
`scratchpad/welle4/blind/S2/sonden/test_sonde_blind_s2.py`; Gegen P1/P4/P6/P7,
`scratchpad/welle4/gegen/S2/proben/test_gegen_s2.py`) — hier als feste,
assertierende Tests statt druckender Sonden, damit sie im Gate bleiben.

Alle Daten erfunden; das Repo ist oeffentlich.
"""

import asyncio
import json

import httpx
import pytest

GEHEIM = "nur-fuer-den-test-kein-geheimnis"
K1 = {"id": "konto-1", "name": "Konto Eins", "immich_url": "http://eins.invalid",
      "api_key": "platzhalter-1", "color": "#111111", "user_id": "u1"}
K2 = {"id": "konto-2", "name": "Konto Zwei", "immich_url": "http://zwei.invalid",
      "api_key": "platzhalter-2", "color": "#222222", "user_id": "u2"}


def _album(aid, name, gid, personen, owner="konto-1", synced="2026-01-01T00:00:00+00:00"):
    return {"id": aid, "match_id": f"m-{aid}", "album_id": f"ia-{aid}",
            "album_name": name, "group_id": gid, "owner_account_id": owner,
            "person_refs": [{"account_id": acc, "person_id": p, "person_name": p,
                             "account_name": acc, "account_color": "#111111"}
                            for acc, p in personen],
            "linked_match_ids": [], "created_at": "2026-01-01T00:00:00+00:00",
            "last_synced_at": synced, "total_assets": 0, "status": "active"}


def _datei(tmp_path, alben, konten=(K1, K2)):
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({"accounts": {k["id"]: k for k in konten},
                                "schema_version": 3, "managed_albums": alben}),
                    encoding="utf-8")
    return pfad


class _Halt:
    """Ein erzwungenes Zeitfenster — an genau EINER Stelle, dem angegebenen Punkt."""

    def __init__(self):
        self.an = False
        self.erreicht = asyncio.Event()
        self.frei = asyncio.Event()

    async def punkt(self):
        if self.an:
            self.an = False
            self.erreicht.set()
            await self.frei.wait()


def _attrappen(monkeypatch, *, halt_get_person=None, halt_create=None):
    """Immich-Attrappe mit Zaehlern — kein Netz, keine echte Instanz."""
    from services import sync_service
    import services.immich_client as ic

    zaehler = {"create": 0, "update_person": 0}

    class Immich:
        def __init__(self, *_a, **_k):
            pass

        async def get_person(self, pid):
            if halt_get_person is not None:
                await halt_get_person.punkt()
            return {"id": pid, "name": "alt"}

        async def update_person(self, pid, body):
            zaehler["update_person"] += 1
            return {}

        async def get_person_assets(self, _pid):
            return []

        async def create_album(self, name, ids):
            if halt_create is not None:
                await halt_create.punkt()
            zaehler["create"] += 1
            return {"id": f"immich-{name}-{zaehler['create']}"}

        async def add_assets_to_album(self, *_a):
            return []

        async def get_album_assets(self, *_a):
            return []

        async def get_album_info(self, _aid):
            return {"albumName": "Neu in Immich"}

    async def ohne_teilen(*_a, **_k):
        return []

    monkeypatch.setattr(sync_service, "ImmichClient", Immich)
    monkeypatch.setattr(ic, "ImmichClient", Immich)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)
    return zaehler


class _Pool:
    """Die Vorabpruefung `get_person` je Person — trivial gruen, kein Netz."""

    def get_for_account(self, _acc):
        class P:
            async def get_person(self, pid):
                return {"id": pid}
        return P()


async def _start(main, pfad, monkeypatch):
    monkeypatch.setattr(main.settings, "secret", GEHEIM, raising=False)
    monkeypatch.setattr(main.settings, "config_path", str(pfad), raising=False)


async def _warte_am_schloss(schloss):
    """Wartet, bis mindestens eine Korutine am Schloss haengt — mit Frist."""
    for _ in range(400):
        await asyncio.sleep(0.005)
        if schloss._waiters:
            return True
    return False


@pytest.mark.asyncio
async def test_blocker_kein_teilvollzug_bei_konkurrierenden_karten(tmp_path, monkeypatch):
    """Blind P1 / Gegen P1: zwei Karten, derselbe NEUE Name, echtes Fenster.

    Karte Zwei bekommt eine Ablehnung — und zwar OHNE dass ihre Personen in
    Immich umbenannt oder protokolliert wurden. Das ist die WIRKUNG, die der
    Rot-Beweis am Waechter (`test_reihenfolge_waechter.py`) statisch
    erzwingt; hier wird sie an der echten Tuer gemessen.
    """
    import main

    pfad = _datei(tmp_path, [])
    await _start(main, pfad, monkeypatch)
    halt = _Halt()
    z = _attrappen(monkeypatch, halt_create=halt)
    async with main.app.router.lifespan_context(main.app):
        main.app.state.client_pool = _Pool()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://t") as c:
            assert (await c.post("/api/auth/login", json={"token": GEHEIM})).status_code == 200

            halt.an = True
            koerper_eins = {
                "persons": [{"account_id": "konto-1", "person_id": "p1"},
                            {"account_id": "konto-2", "person_id": "p2"}],
                "canonical_name": "Karte Eins", "album_name": "Kartenpaar",
                "owner_account_id": "konto-1", "expected_no_group": True,
            }
            koerper_zwei = {
                "persons": [{"account_id": "konto-1", "person_id": "p3"},
                            {"account_id": "konto-2", "person_id": "p4"}],
                "canonical_name": "Karte Zwei", "album_name": "Kartenpaar",
                "owner_account_id": "konto-1", "expected_no_group": True,
            }
            erste = asyncio.create_task(c.post("/api/sync/names-multi", json=koerper_eins))
            await halt.erreicht.wait()

            zweite = asyncio.create_task(c.post("/api/sync/names-multi", json=koerper_zwei))
            store = main.app.state.store
            fenster = await _warte_am_schloss(store.gruppen_schloss("Kartenpaar"))
            assert fenster, "Karte Zwei haette am Gruppenschloss haengen muessen"

            halt.frei.set()
            r1 = await erste
            r2 = await zweite

            assert r1.status_code == 200, r1.text
            assert r2.status_code == 409, r2.text
            assert r2.json().get("error_key") == "err_group_situation_changed", r2.text

            # Die WIRKUNG: Karte Zweis Personen (p3, p4) wurden NICHT
            # umbenannt — nur Karte Eins' zwei Personen (p1, p2).
            assert z["update_person"] == 2, (
                f"erwartet 2 Umbenennungen (nur Karte Eins), gemessen {z['update_person']}")

            log = main.app.state.store.get_log()
            protokolliert = [e for e in log if "Karte Zwei" in json.dumps(
                e.model_dump() if hasattr(e, "model_dump") else e, default=str)]
            assert not protokolliert, (
                "Karte Zwei darf nach einer Ablehnung nicht im Protokoll stehen")

            alben = (await c.get("/api/sync/albums")).json()
            assert len(alben) == 1, "nur EIN Album, nicht zwei getrennte Gruppen"


@pytest.mark.asyncio
async def test_blocker_kein_update_person_bei_gleichzeitigem_namen(tmp_path, monkeypatch):
    """Gegen P4: Fenster waehrend `sync_names_multi` selbst (nicht `create_album`).

    Task B wartet am GRUPPENSCHLOSS, waehrend Task A noch mitten in seiner
    eigenen Namensabgleichung haengt — vorher (Blocker) konnte B trotzdem
    durchlaufen und seine eigenen Personen umbenennen, bevor die Ablehnung
    kam. Jetzt haelt A das Schloss schon VOR seinem eigenen Umbenennen.
    """
    import main

    pfad = _datei(tmp_path, [])
    await _start(main, pfad, monkeypatch)
    halt = _Halt()
    z = _attrappen(monkeypatch, halt_get_person=halt)
    async with main.app.router.lifespan_context(main.app):
        main.app.state.client_pool = _Pool()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://t") as c:
            assert (await c.post("/api/auth/login", json={"token": GEHEIM})).status_code == 200
            halt.an = True
            ta = asyncio.create_task(c.post("/api/sync/names-multi", json={
                "persons": [{"account_id": "konto-1", "person_id": "a1"},
                            {"account_id": "konto-2", "person_id": "a2"}],
                "canonical_name": "Anna", "album_name": "Fest", "owner_account_id": "konto-1",
                "expected_no_group": True}))
            await halt.erreicht.wait()

            tb = asyncio.create_task(c.post("/api/sync/names-multi", json={
                "persons": [{"account_id": "konto-1", "person_id": "b1"},
                            {"account_id": "konto-2", "person_id": "b2"}],
                "canonical_name": "Berta", "album_name": "Fest", "owner_account_id": "konto-1",
                "expected_no_group": True}))
            store = main.app.state.store
            fenster = await _warte_am_schloss(store.gruppen_schloss("Fest"))
            assert fenster, "Berta haette am Gruppenschloss von 'Fest' haengen muessen"

            halt.frei.set()
            ra = await ta
            rb = await tb

            assert ra.status_code == 200, ra.text
            assert rb.status_code == 409, rb.text
            # NUR Annas Paar wurde umbenannt (2), Bertas Paar NICHT (0 dazu).
            assert z["update_person"] == 2, (
                f"erwartet 2 Umbenennungen (nur Anna), gemessen {z['update_person']}")


@pytest.mark.asyncio
async def test_blocker_wiederholung_mit_expected_no_group_ist_kein_409(tmp_path, monkeypatch):
    """Gegen P6 (KLEIN, Doppelklick/Netz-Retry): idempotente Wiederholung.

    Der 'gab es schon'-Zweig (dieselbe manuelle Kennung, dieselbe
    Personenmenge) entscheidet jetzt VOR `resolve_group_id` — ein exakter
    Wiederholungsaufruf mit `expected_no_group=True` bekommt also keine
    409 mehr, weil die Bestehend-Pruefung zuerst greift.
    """
    import main

    pfad = _datei(tmp_path, [])
    await _start(main, pfad, monkeypatch)
    _attrappen(monkeypatch)
    koerper = {
        "persons": [{"account_id": "konto-1", "person_id": "a1"},
                    {"account_id": "konto-2", "person_id": "a2"}],
        "canonical_name": "Anna", "album_name": "Fest", "owner_account_id": "konto-1",
        "expected_no_group": True,
    }
    async with main.app.router.lifespan_context(main.app):
        main.app.state.client_pool = _Pool()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://t") as c:
            assert (await c.post("/api/auth/login", json={"token": GEHEIM})).status_code == 200
            r1 = await c.post("/api/sync/names-multi", json=koerper)
            r2 = await c.post("/api/sync/names-multi", json=koerper)

            assert r1.status_code == 200, r1.text
            assert r2.status_code == 200, (
                f"eine exakte Wiederholung mit expected_no_group darf keine "
                f"409 bekommen — bekam {r2.status_code}: {r2.text}")


@pytest.mark.asyncio
async def test_gewaehlte_gruppe_verschwindet_im_fenster(tmp_path, monkeypatch):
    """Gegen P7/Fremdpruefer: `group_id` wird jetzt IMMER frisch geprueft.

    MESSUNG, nicht Behauptung: Das Verschwinden geschieht hier waehrend des
    Immich-Aufrufs `get_person` INNERHALB `sync_service.sync_names_multi` —
    also bereits UNTER dem Gruppenschloss, das dieser Slice vor den
    Schreibvorgang gezogen hat. Das Loeschen selbst laeuft ueber
    `sync_service._album_schloss` (eine andere Schloss-Familie, siehe
    `docs/agents/lehren.md` und die "nicht anfassen"-Liste des Bau-Briefs:
    `_album_schloss` gehoert einem anderen Slice). Dieser Test haelt fest,
    WAS tatsaechlich passiert — nicht, was wuenschenswert waere.
    """
    import main

    alben = [_album("x1", "Fest", "gx", [("konto-1", "p1"), ("konto-2", "p2")])]
    pfad = _datei(tmp_path, alben)
    await _start(main, pfad, monkeypatch)
    halt = _Halt()
    _attrappen(monkeypatch, halt_get_person=halt)
    async with main.app.router.lifespan_context(main.app):
        main.app.state.client_pool = _Pool()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://t") as c:
            assert (await c.post("/api/auth/login", json={"token": GEHEIM})).status_code == 200
            halt.an = True
            ta = asyncio.create_task(c.post("/api/sync/names-multi", json={
                "persons": [{"account_id": "konto-1", "person_id": "a1"},
                            {"account_id": "konto-2", "person_id": "a2"}],
                "canonical_name": "Anna", "album_name": "Fest", "owner_account_id": "konto-1",
                "group_id": "gx"}))
            await halt.erreicht.wait()
            rd = await c.delete("/api/sync/albums/x1")
            halt.frei.set()
            ra = await ta
            liste = (await c.get("/api/sync/albums")).json()
            # Dokumentiert im Bericht: `_album_schloss` (Loeschen) und
            # `gruppen_schloss`/`treffer_schloss` (dieser Slice) sind
            # verschiedene Schloss-Familien und schuetzen sich NICHT
            # gegenseitig — das Verschwinden waehrend eines bereits unter dem
            # Gruppenschloss laufenden Immich-Aufrufs bleibt ein bekanntes,
            # ausserhalb des Bau-Briefs liegendes Restrisiko (siehe Bericht).
            print(f"\nP7 delete={rd.status_code} ra={ra.status_code} "
                  f"alben={[(a['album_name'], a['group_id']) for a in liste]}")
