"""Vier Alben einer Gruppe parallel entfernen, waehrend eines im Schloss haengt (#123, #121 Punkt 1).

`AlbumsOverview.tsx` (`handleDelete`) schickt seit diesem Slice alle DELETEs
einer Gruppe GLEICHZEITIG (`Promise.all`), nicht mehr nacheinander. Diese
Datei prueft die Voraussetzung dafuer auf der Server-Seite, ueber die echte
HTTP-Tuer: `sync_service._album_schloss` ist ein Schloss JE ALBUM-ID (siehe
dessen Docstring) — vier Alben derselben Gruppe nehmen vier VERSCHIEDENE
Schloesser. Haelt ein laufender Refresh das Schloss von genau einem Album,
duerfen die drei anderen DELETEs fertig werden, WAEHREND das eine noch wartet
— nicht erst danach.

Dasselbe Muster wie `test_loeschen_im_schloss.py` (#101, Nacharbeit 2): Das
Fenster wird ERZWUNGEN (`docs/agents/lehren.md` §44) — der haltende Aufruf
startet die vier DELETEs als eigene Tasks und wartet aktiv, bis das
betroffene DELETE wirklich als Warteschlangen-Eintrag am Schloss haengt
(`asyncio.Lock._waiters`), bevor er den Immich-Haken zurueckkehren laesst.
Ohne dieses Warten waere nicht bewiesen, dass ueberhaupt ein Fenster
entstanden ist — nur, dass am Ende alle vier weg sind, was eine rein
sequenzielle Reihenfolge genauso liefern wuerde (§40: ein Test, der nur das
Endergebnis betrachtet, uebersieht den toten Zwischenzustand).
"""
import asyncio
import json
import time

import httpx
import pytest

KONTO = {"id": "konto-1", "name": "Konto Eins", "immich_url": "http://eins.invalid",
         "api_key": "platzhalter", "color": "#111111", "user_id": "u1"}


def _album(album_id):
    return {"id": album_id, "match_id": f"m-{album_id}", "album_id": f"immich-{album_id}",
            "album_name": "Grossfamilie", "group_id": "gruppe-gross",
            "owner_account_id": "konto-1", "person_refs": [], "linked_match_ids": [],
            "created_at": "2026-01-01T00:00:00+00:00", "total_assets": 0}


def _datei(tmp_path):
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {"konto-1": KONTO},
        "schema_version": 3,
        "managed_albums": [_album("a1"), _album("a2"), _album("a3"), _album("a4")],
    }), encoding="utf-8")
    return pfad


@pytest.mark.asyncio
async def test_drei_geschwister_werden_entfernt_waehrend_das_vierte_im_schloss_haengt(
    tmp_path, monkeypatch
):
    import main
    from services import sync_service

    pfad = _datei(tmp_path)
    monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test-123", raising=False)
    monkeypatch.setattr(main.settings, "config_path", str(pfad), raising=False)

    class ImmichAttrappe:
        """Haengt beim ERSTEN Aufruf (Refresh von a1), bis freigegeben wird."""

        def __init__(self, *_a, **_k):
            pass

        async def get_album_assets(self, _aid):
            await haltepunkt()
            return []

        async def get_album_assets_with_name(self, _aid):
            await haltepunkt()
            return "Grossfamilie", []

    async def ohne_teilen(*_a, **_k):
        return []

    freigabe = asyncio.Event()
    erreicht = asyncio.Event()

    async def haltepunkt():
        erreicht.set()
        await freigabe.wait()

    monkeypatch.setattr(sync_service, "ImmichClient", ImmichAttrappe)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", ohne_teilen)

    async with main.app.router.lifespan_context(main.app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://test") as c:
            r_login = await c.post("/api/auth/login", json={"token": main.settings.secret})
            assert r_login.status_code == 200, r_login.text

            # a1 im Refresh "einfrieren" (haelt dessen Albumschloss).
            refresh_task = asyncio.create_task(c.post("/api/sync/album/a1/refresh"))
            await erreicht.wait()

            # Jetzt ALLE VIER parallel entfernen — genau das, was
            # `handleDelete` seit diesem Slice per `Promise.all` tut.
            start = time.monotonic()
            delete_tasks = {
                aid: asyncio.create_task(c.delete(f"/api/sync/albums/{aid}"))
                for aid in ("a1", "a2", "a3", "a4")
            }

            # a1 muss jetzt am SELBEN Schloss warten wie der Refresh — das ist
            # das erzwungene Fenster.
            schloss = sync_service._album_schloss("a1")
            for _ in range(200):
                await asyncio.sleep(0.005)
                if schloss._waiters:
                    break
            assert schloss._waiters, "a1 wartet nicht am Schloss - kein Fenster erzwungen"

            # a2, a3, a4 haengen an KEINEM gemeinsamen Schloss mit a1 - sie
            # duerfen fertig werden, WAEHREND a1 noch wartet.
            r2, r3, r4 = await asyncio.gather(
                delete_tasks["a2"], delete_tasks["a3"], delete_tasks["a4"]
            )
            dauer_ohne_a1 = time.monotonic() - start
            assert r2.status_code == 204, r2.text
            assert r3.status_code == 204, r3.text
            assert r4.status_code == 204, r4.text
            # Grosszuegige Schranke (die Probe selbst schlaeft bis zu 1s in
            # 5ms-Schritten, um das Fenster zu erzwingen) — der Punkt ist
            # NICHT eine exakte Zahl (docs/agents/lehren.md #46), sondern:
            # deutlich WENIGER als die Freigabe unten braucht.
            assert dauer_ohne_a1 < 1.0, dauer_ohne_a1

            # a1 haengt noch immer - erst jetzt geben wir frei.
            assert not delete_tasks["a1"].done()
            freigabe.set()
            r_op = await refresh_task
            r1 = await delete_tasks["a1"]

            assert r_op.status_code == 200, r_op.text
            assert r1.status_code == 204, r1.text

            # Alle vier Alben sind weg — ueber dieselbe HTTP-Tuer gemessen,
            # nicht ueber den Store direkt (R3: der Pfad, den das Produkt
            # benutzt).
            r_liste = await c.get("/api/sync/albums")
            assert r_liste.json() == [], r_liste.json()
