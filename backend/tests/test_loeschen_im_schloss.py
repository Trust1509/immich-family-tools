"""`DELETE /api/sync/albums/{id}` muss dasselbe Albumschloss nehmen (#101, Nacharbeit 2).

Restfenster, gemessen vom Fremdprüfer über die echte HTTP-Tür: Das Löschen
nahm bisher KEIN Schloss. Lief einer der drei Wrapper (Refresh/Umbenennen/
Erweitern) gerade im Schloss und wartete auf Immich, kam das Löschen dazwischen
durch — 200/204, Immich wurde trotzdem noch verändert, ein Erfolgseintrag
entstand, und `ConfigStore.update_managed_album` speicherte am Ende mangels
passender Zeile still NICHTS. Genau die Projekt-Prämisse „nichts verschwindet
still" war betroffen, diesmal in der Gegenrichtung: nicht das Album verschwand
still, sondern die Wirkung der noch laufenden Operation.

Seit dieser Nacharbeit nimmt der Router dasselbe `sync_service._album_schloss`
wie die drei Wrapper. Das Löschen wartet dann, bis die laufende Operation ihr
Schloss verlässt, und entfernt danach den (dann aktuellen) Datensatz.

Das Fenster wird erzwungen (`docs/agents/lehren.md` §44): Das Löschen wird als
eigene Task gestartet, DAMIT es sich anlegen kann, ohne den Aufrufer (der noch
im Schloss steckt) zu blockieren — ein `await` direkt im Immich-Haken würde
sich selbst verklemmen, da dieselbe Ausführung dann auf ein Schloss wartet,
das sie selbst hält. Die Probe wartet aktiv, bis das Löschen wirklich als
Warteschlangen-Eintrag am Schloss hängt (`asyncio.Lock._waiters`), bevor sie
den Immich-Haken zurückkehren lässt — ohne dieses Warten wäre nicht bewiesen,
dass ein Fenster überhaupt entstanden ist.
"""
import asyncio
import json

import httpx
import pytest

KONTO1 = {"id": "konto-1", "name": "Konto Eins", "immich_url": "http://eins.invalid",
          "api_key": "platzhalter", "color": "#111111", "user_id": "u1"}
KONTO2 = {"id": "konto-2", "name": "Konto Zwei", "immich_url": "http://zwei.invalid",
          "api_key": "platzhalter", "color": "#222222", "user_id": "u2"}
REF1 = {"account_id": "konto-1", "person_id": "p1", "person_name": "Eins",
        "account_name": "Konto Eins", "account_color": "#111111"}


def _album():
    return {"id": "a1", "match_id": "m-a1", "album_id": "immich-a1",
            "album_name": "Eins", "group_id": "g1", "owner_account_id": "konto-1",
            "person_refs": [REF1], "linked_match_ids": [],
            "created_at": "2026-01-01T00:00:00+00:00", "total_assets": 0}


def _datei(tmp_path):
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {"konto-1": KONTO1, "konto-2": KONTO2},
        "schema_version": 3, "managed_albums": [_album()],
    }), encoding="utf-8")
    return pfad


def _attrappe(monkeypatch, haken):
    """Immich-Attrappe; `haken(methode, album_id)` läuft vor jeder Antwort."""
    from services import sync_service

    class Client:
        def __init__(self, *_a, **_k):
            pass

        async def _h(self, m, a):
            await haken(m, a)

        async def get_person(self, pid):
            await self._h("get_person", pid)
            return {"id": pid, "name": "X"}

        async def get_album_assets(self, aid):
            await self._h("get_album_assets", aid)
            return []

        async def get_album_assets_with_name(self, aid):
            await self._h("get_album_assets_with_name", aid)
            return "Eins", []

        async def get_person_assets(self, pid):
            await self._h("get_person_assets", pid)
            return [{"id": "asset-1"}]

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


FALL = {
    "rename": ("PATCH", "/api/sync/albums/a1", {"album_name": "Neu"}),
    "refresh": ("POST", "/api/sync/album/a1/refresh", None),
    "extend": ("POST", "/api/sync/extend", {"managed_album_id": "a1", "account_id": "konto-2",
                                             "person_id": "p2", "person_name": "Zwei"}),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("art", ["rename", "refresh", "extend"])
async def test_loeschen_wartet_auf_eine_laufende_operation_im_schloss(tmp_path, monkeypatch, art):
    import main
    from services import sync_service

    pfad = _datei(tmp_path)
    monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test-101-na2", raising=False)
    monkeypatch.setattr(main.settings, "config_path", str(pfad), raising=False)

    client_ref: dict = {}
    delete_task_ref: dict = {}
    ausgeloest = []

    async def haken(_m, _a):
        if "task" in delete_task_ref:
            return  # nur beim ERSTEN Immich-Aufruf ausloesen
        ausgeloest.append(True)
        # Als eigene Task, NICHT direkt awaiten: Ein direktes `await` hier
        # wuerde sich selbst verklemmen (dieselbe Ausfuehrung wartet auf ein
        # Schloss, das sie selbst haelt, solange sie hier steht).
        delete_task_ref["task"] = asyncio.create_task(
            client_ref["c"].delete("/api/sync/albums/a1"))
        schloss = sync_service._album_schloss("a1")
        for _ in range(200):
            await asyncio.sleep(0.005)
            if schloss._waiters:
                break
        assert schloss._waiters, "Loeschen wartet nicht am Schloss - kein Fenster erzwungen"

    _attrappe(monkeypatch, haken)

    async with main.app.router.lifespan_context(main.app):
        store = main.app.state.store
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://test") as c:
            client_ref["c"] = c
            r_login = await c.post("/api/auth/login", json={"token": main.settings.secret})
            assert r_login.status_code == 200, r_login.text

            methode, url, body = FALL[art]
            r_op = await c.request(methode, url, json=body)
            assert "task" in delete_task_ref, "Immich-Haken nie erreicht"
            r_del = await delete_task_ref["task"]

        assert r_op.status_code == 200, r_op.text
        assert r_del.status_code == 204, r_del.text

        # Die laufende Operation ist normal zu Ende gelaufen (Erfolg im
        # Protokoll), UND das Album ist danach weg.
        log_status = [e.status for e in store.get_log()]
        assert "success" in log_status, log_status
        assert store.get_managed_album("a1") is None
