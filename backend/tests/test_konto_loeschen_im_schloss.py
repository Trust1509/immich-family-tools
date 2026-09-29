"""`DELETE /api/accounts/{id}` muss dasselbe Albumschloss nehmen wie die drei
Schreiber — sonst nimmt es eine Loeschung selbst wieder zurueck (#117).

`ConfigStore.delete_account` schrieb bisher OHNE jedes Albumschloss direkt in
`managed_albums`. Die drei Schreiber eines Albums (Refresh/Umbenennen/
Erweitern) lesen ihren Datensatz dagegen UNTER `sync_service._album_schloss`
frisch (`_frisch`), warten auf Immich und schreiben am Ende den GANZEN
Datensatz zurueck. Lief `delete_account` in diesem Wartefenster, gewann der
spaeter fertige Schreiber mit seiner ALTEN Kopie — die Loeschung war zwar kurz
sichtbar, wurde aber vom naechsten Schreibvorgang wieder rueckgaengig gemacht
(gemessen, Panel zu #101: `konto-3` stand nach `delete_account("konto-3")`
parallel zu einer Erweiterung wieder in `person_refs`).

Seit dieser Nacharbeit nimmt `ConfigStore.delete_account` je betroffenem Album
dasselbe `sync_service._album_schloss` wie die drei Schreiber, auf einem dort
frisch gelesenen Datensatz. Die Loeschung wartet dann, bis die laufende
Operation ihr Schloss verlaesst (inklusive ihres eigenen abschliessenden
Schreibens), und arbeitet danach auf DEREN Ergebnis weiter.

Das Fenster wird erzwungen (`docs/agents/lehren.md` §44), exakt wie in
`test_loeschen_im_schloss.py`: Die Konto-Loeschung wird als eigene Task
gestartet und die Probe wartet aktiv, bis sie wirklich als Warteschlangen-
Eintrag am Albumschloss haengt (`asyncio.Lock._waiters`), bevor sie den
Immich-Haken zurueckkehren laesst.

WARUM DER BESITZER (nicht ein beliebiger Teilnehmer) geloescht wird: Der
Besitzer steht in jedem hier gebauten Album selbst auch als `person_refs`-
Eintrag — die Probe deckt damit in EINEM Zug sowohl die Referenz-Entfernung
(#117, Hauptteil) als auch den ueblichen Fall ab, in dem ein geloeschtes
Konto zugleich Besitzer war. Der Besitzer-FRISCH-Check selbst (#117 Nachtrag:
Umbenennen/Abgleichen lesen den Besitzer jetzt unter dem Schloss aus dem
Store, nicht mehr aus einer vor dem Schloss gebauten Kontenliste) hat eigene,
naeherliegende Proben in `test_sync_service.py` — dort laesst er sich als
reiner Unit-Test fassen, weil das Zeitfenster, das er schliesst (zwischen
`_frisch` und der Besitzerpruefung), KEIN `await` enthaelt und sich darum
nicht ueber echte Nebenlaeufigkeit erzwingen laesst.

DIE OPERATION, DIE HIER WARTET, HATTE DEN BESITZER-CHECK LAENGST BESTANDEN,
BEVOR SIE AM IMMICH-HAKEN HAENGEN BLEIBT — sie arbeitet legitim mit dem zu
diesem Zeitpunkt noch gueltigen Konto weiter (das ist keine Regression: eine
laufende Operation, die mit gueltigen Daten begonnen hat, wird nicht
rueckwirkend storniert). Was diese Probe zeigt, ist die Kehrseite: Die
Loeschung selbst darf NICHT durch die noch laufende Operation wieder
rueckgaengig gemacht werden — und genau das tat sie vor dieser Nacharbeit.

Alle Daten erfunden; das Repo ist oeffentlich.
"""
import asyncio
import json

import httpx
import pytest

KONTO1 = {"id": "konto-1", "name": "Konto Eins", "immich_url": "http://eins.invalid",
          "api_key": "platzhalter", "color": "#111111", "user_id": "u1"}
KONTO2 = {"id": "konto-2", "name": "Konto Zwei", "immich_url": "http://zwei.invalid",
          "api_key": "platzhalter", "color": "#222222", "user_id": "u2"}
KONTO3 = {"id": "konto-3", "name": "Konto Drei", "immich_url": "http://drei.invalid",
          "api_key": "platzhalter", "color": "#333333", "user_id": "u3"}
REF1 = {"account_id": "konto-1", "person_id": "p1", "person_name": "Eins",
        "account_name": "Konto Eins", "account_color": "#111111"}
REF2 = {"account_id": "konto-2", "person_id": "p2", "person_name": "Zwei",
        "account_name": "Konto Zwei", "account_color": "#222222"}


def _album():
    return {"id": "a1", "match_id": "m-a1", "album_id": "immich-a1",
            "album_name": "Eins", "group_id": "g1", "owner_account_id": "konto-1",
            "person_refs": [REF1, REF2], "linked_match_ids": [],
            "created_at": "2026-01-01T00:00:00+00:00", "total_assets": 0}


def _datei(tmp_path):
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {"konto-1": KONTO1, "konto-2": KONTO2, "konto-3": KONTO3},
        "schema_version": 3, "managed_albums": [_album()],
    }), encoding="utf-8")
    return pfad


def _attrappe(monkeypatch, haken):
    """Immich-Attrappe; `haken(methode, album_id)` läuft vor jeder Antwort.

    Dieselbe Form wie in `test_loeschen_im_schloss.py` — bewusst nicht
    geteilt, damit diese Datei ohne Blick in die andere lesbar bleibt
    (Konvention dieses Projekts, siehe `test_umbenennen_gruppe.py`).
    """
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
    "extend": ("POST", "/api/sync/extend", {"managed_album_id": "a1", "account_id": "konto-3",
                                             "person_id": "p3", "person_name": "Drei"}),
}

# Nach jedem Fall duerfen im Album nur noch diese Konten stehen — konto-1
# (der Besitzer) wurde waehrend des Wartens geloescht und darf NICHT
# zurueckkehren; `extend` fuegt zusaetzlich konto-3 hinzu.
ERWARTETE_KONTEN_NACHHER = {
    "rename": {"konto-2"},
    "refresh": {"konto-2"},
    "extend": {"konto-2", "konto-3"},
}


@pytest.mark.asyncio
@pytest.mark.parametrize("art", ["rename", "refresh", "extend"])
async def test_konto_loeschung_waehrend_ein_schreiber_wartet_wird_nicht_zurueckgenommen(
    tmp_path, monkeypatch, art
):
    import main
    from services import sync_service

    pfad = _datei(tmp_path)
    monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test-117", raising=False)
    monkeypatch.setattr(main.settings, "config_path", str(pfad), raising=False)

    client_ref: dict = {}
    delete_task_ref: dict = {}
    store_ref: dict = {}
    # AUSSERHALB des Immich-Hakens gefuellt und AUSSERHALB des `async with`
    # geprueft — ein `assert` IM Haken liefe innerhalb des `except
    # Exception`, mit dem die Wrapper einen Immich-Fehler abfangen, und
    # wuerde dort verschluckt (dieselbe Lehre wie #121 Punkt 2, siehe
    # `test_loeschen_im_schloss.py`).
    fenster_erzwungen: list[bool] = []
    konto_beim_warten_noch_da: list[bool] = []

    async def haken(_m, _a):
        if "task" in delete_task_ref:
            return  # nur beim ERSTEN Immich-Aufruf ausloesen
        delete_task_ref["task"] = asyncio.create_task(
            client_ref["c"].delete("/api/accounts/konto-1"))
        schloss = sync_service._album_schloss("a1")
        for _ in range(200):
            await asyncio.sleep(0.005)
            if schloss._waiters:
                break
        fenster_erzwungen.append(bool(schloss._waiters))
        # Waehrend die laufende Operation ihr Schloss noch haelt, darf
        # `delete_account` noch nicht bis zu diesem Album vorgedrungen sein —
        # konto-1 steht also noch in `person_refs`. Erst NACH der Freigabe
        # darf es verschwinden.
        album = store_ref["store"].get_managed_album("a1")
        konto_beim_warten_noch_da.append(
            album is not None
            and any(r["account_id"] == "konto-1" for r in album.person_refs)
        )

    _attrappe(monkeypatch, haken)

    async with main.app.router.lifespan_context(main.app):
        store = main.app.state.store
        store_ref["store"] = store
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
        assert fenster_erzwungen and fenster_erzwungen[0], (
            "Konto-Loeschung wartet nicht am Albumschloss - kein Fenster erzwungen")
        assert konto_beim_warten_noch_da and konto_beim_warten_noch_da[0], (
            "konto-1 war schon aus person_refs verschwunden, waehrend die "
            "laufende Operation ihr Schloss noch hielt - die Loeschung lief "
            "nicht wirklich unter demselben Schloss")

        # Der eigentliche Nachweis (#117): Das geloeschte Konto ist NACH
        # allem weg und bleibt es — kein Schreibvorgang der laufenden
        # Operation hat es zurueckgebracht.
        album = store.get_managed_album("a1")
        assert album is not None
        konten_im_album = {r["account_id"] for r in album.person_refs}
        assert konten_im_album == ERWARTETE_KONTEN_NACHHER[art], (
            f"{art}: erwartet {ERWARTETE_KONTEN_NACHHER[art]}, war {konten_im_album}")
        assert "konto-1" not in [a.id for a in store.list_accounts()]


@pytest.mark.asyncio
async def test_keine_verklemmung_zwischen_konto_loeschen_und_album_entfernen(
    tmp_path, monkeypatch
):
    """Block 5 des Bau-Briefs: gleichzeitiges Konto-Loeschen und Gruppen-
    Entfernen fuer DASSELBE Album darf nicht haengen — beide nehmen je
    Album hoechstens EIN `_album_schloss`, nie zwei gleichzeitig (siehe
    Docstring bei `config_store._treffer_schloesser`). Zeitlimit, damit ein
    Rueckbau rot statt haengend wird.
    """
    import main

    async def keine_immich_aufrufe(*_a, **_k):
        raise AssertionError("Immich haette hier nicht angesprochen werden duerfen")

    from services import sync_service
    monkeypatch.setattr(sync_service, "ImmichClient", keine_immich_aufrufe)

    pfad = _datei(tmp_path)
    monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test-117-vk", raising=False)
    monkeypatch.setattr(main.settings, "config_path", str(pfad), raising=False)

    async with main.app.router.lifespan_context(main.app):
        store = main.app.state.store
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://test") as c:
            r_login = await c.post("/api/auth/login", json={"token": main.settings.secret})
            assert r_login.status_code == 200, r_login.text

            ergebnisse = await asyncio.wait_for(
                asyncio.gather(
                    c.delete("/api/accounts/konto-1"),
                    c.delete("/api/sync/albums/a1"),
                    return_exceptions=True,
                ),
                timeout=5,
            )

        for ergebnis in ergebnisse:
            assert not isinstance(ergebnis, Exception), ergebnisse
            assert ergebnis.status_code in (204,), ergebnis.text

        # Beide Ausgaenge sind zulaessig (Reihenfolge ist nicht festgelegt):
        # Entweder das Album ist schon weg, bevor die Konto-Loeschung ihr
        # Aufraeumen versucht (dann findet sie einfach nichts mehr, siehe
        # `ConfigStore.delete_account`), oder die Konto-Loeschung raeumt
        # zuerst auf und das Album verschwindet danach vollstaendig. In
        # BEIDEN Faellen bleibt am Ende kein Album a1 und kein Konto konto-1.
        assert store.get_managed_album("a1") is None
        assert "konto-1" not in [a.id for a in store.list_accounts()]
