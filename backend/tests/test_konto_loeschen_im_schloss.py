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

Seit dieser Nacharbeit nahm `ConfigStore.delete_account` dafuer je
betroffenem Album dasselbe `sync_service._album_schloss` wie die drei
Schreiber — und WARTETE, bis eine laufende Operation es freigab. Das erzeugte
einen neuen Fehler, den NACHARBEIT 1 (#117/#121/#103) behebt: Wartete die
Loeschung so auf MEHRERE gehaltene Alben nacheinander (etwa hinter einem
Sammelabgleich ueber vier Alben), summierten sich deren Wartezeiten zu einem
"Konvoi" (gemessen 1,29 s bei vier mal 0,3 s Einzelwartezeit), waehrend das
Konto nach aussen laengst verschwunden war (`GET /api/accounts` ohne das
Konto) — die Anfrage selbst stand aber noch offen. Siehe
`test_konto_loeschung_ohne_konvoi.py` fuer den Konvoi-Beweis und die
Blind-/Gegenpruefer-Proben (S1/S1b/S2/S3/S5/S6/S7/S8, A/B/D/F/F2/G/H), die
seither AUSSCHLIESSLICH dort stehen.

NACHARBEIT 1: `ConfigStore.delete_account` WARTET AUF KEIN ALBUMSCHLOSS MEHR
(`docs/agents/lehren.md`-Klasse "grün ohne bewiesen" haette hier sonst wieder
zugeschlagen — ein Wartemechanismus, der schneller wird, indem man ihn
entfernt, verdient eine eigene Begruendung, keine stille Annahme): Ist ein
betroffenes Album gerade gesperrt, ueberspringt die Loeschung es; der Halter
des Schlosses entfernt die tote Referenz SELBST, wenn er seinen Datensatz
zurueckschreibt (`ConfigStore._ohne_tote_konten`, aus `update_managed_album`
fuer JEDEN Schreiber). Die Tests HIER pruefen deshalb nicht mehr, dass die
Loeschung selbst wartet — sondern dass sie SOFORT zurueckkehrt, WAEHREND eine
andere Operation noch mit dem (zum Zeitpunkt ihres eigenen Starts gueltigen)
Konto arbeitet, und dass die Referenz danach trotzdem verschwindet, sobald
diese Operation ihren Datensatz zurueckschreibt.

WARUM DER BESITZER (nicht ein beliebiger Teilnehmer) geloescht wird: Der
Besitzer steht in jedem hier gebauten Album selbst auch als `person_refs`-
Eintrag — die Probe deckt damit in EINEM Zug sowohl die Referenz-Entfernung
(#117, Hauptteil) als auch den ueblichen Fall ab, in dem ein geloeschtes
Konto zugleich Besitzer war.

RICHTIGSTELLUNG (Nacharbeit 1, WICHTIG 4): Hier stand bis zu dieser Fassung,
das Zeitfenster zwischen dem Lesen des Besitzers VOR dem Schloss und der
eigentlichen Besitzerpruefung sei nicht ueber echte Nebenlaeufigkeit
erzwingbar, weil dazwischen kein `await` liege. Das war FALSCH — und zwar aus
einem Grund, den diese Datei selbst nicht zeigen konnte: Das Fenster liegt
nicht zwischen `_frisch` und der Besitzerpruefung (dort stimmt die
Beobachtung, dort liegt tatsaechlich kein `await`), sondern zwischen einem
Lesen VOR dem Schloss (wie es ein Aufrufer VOR #117 Nachtrag tat) und dem
WARTEN an einem belegten Schloss — und genau dort liegt ein `await`
(`async with _album_schloss(...)`, wenn das Schloss belegt ist). Eine
Mutation, die `owner_account = store.get_account(...)` vor
`async with _album_schloss(...)` verschiebt (Blind M6, Gegen M5), blieb an
DIESER Datei gruen, weil die hier gebauten Operationen ihren eigenen
Besitzer-Check laengst bestanden hatten, BEVOR sie am Immich-Haken
haengenblieben (siehe unten) — das erzwingt das FALSCHE Fenster. Die
RICHTIGE Probe steht jetzt in
`test_konto_loeschung_ohne_konvoi.py::test_umbenennen_liest_den_besitzer_nach_dem_warten_nicht_davor`:
Sie laesst ein Umbenennen HINTER einem belegten Schloss WARTEN (ein echter
Warteschlangen-Eintrag) und loescht den Besitzer WAEHREND dieses Wartens.

DIE OPERATION, DIE HIER WARTET, HATTE DEN BESITZER-CHECK LAENGST BESTANDEN,
BEVOR SIE AM IMMICH-HAKEN HAENGEN BLEIBT — sie arbeitet legitim mit dem zu
diesem Zeitpunkt noch gueltigen Konto weiter (das ist keine Regression: eine
laufende Operation, die mit gueltigen Daten begonnen hat, wird nicht
rueckwirkend storniert). Was diese Probe zeigt, ist die Kehrseite: Die
Loeschung selbst darf NICHT durch die noch laufende Operation wieder
rueckgaengig gemacht werden — und genau das tat sie vor #117.

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
# zurueckkehren.
#
# `extend` FUEGT KONTO-3 SEIT NACHARBEIT 2 NICHT MEHR HINZU (#117/#121/#103,
# WICHTIG 3) — GEAENDERT GEGENUEBER NACHARBEIT 1: Der Immich-Haken dieser
# Datei loest beim JEWEILS ERSTEN Aufruf aus; bei `extend` ist das die
# Personen-Validierung (`new_client.get_person`, mit `konto-3`s Schluessel,
# nicht dem des geloeschten Besitzers). Die Kontoloeschung (`konto-1`, der
# BESITZER) laeuft darin vollstaendig durch, BEVOR `_extend_match_unlocked`
# zum naechsten Aufrufblock kommt — und seit Nacharbeit 2 prueft die Funktion
# vor JEDEM weiteren Immich-Aufrufblock frisch, ob der Besitzer noch lebt
# (Befund Blind W3/W4, Gegen N5/N6: ein Aufrufblock NACH dem 204 rief zuvor
# noch mit dem Schluessel eines bereits geloeschten Kontos). Der Besitzer
# fehlt hier schon vor Block 2 („Album-Assets abrufen", braucht
# `owner_client`) — ohne diesen Aufruf kennt die Funktion `existing_ids`
# nicht und kann Block 3 (Assets von `konto-3` hinzufuegen) nicht sicher
# gegen Duplikate ausfuehren, bricht also ehrlich mit
# `log_owner_account_missing` ab, BEVOR `konto-3` je an `person_refs` haengt.
# `konto-1` verschwindet trotzdem — nicht ueber `_extend_match_unlocked`s
# eigenes `store.update_managed_album` (das wird hier nie erreicht), sondern
# ueber das `finally` des Schloss-Wrappers
# (`sync_service._raeume_tote_referenzen_synchron`, BLOCKER dieser
# Nacharbeit), das bei JEDEM Ausgang aufraeumt.
ERWARTETE_KONTEN_NACHHER = {
    "rename": {"konto-2"},
    "refresh": {"konto-2"},
    "extend": {"konto-2"},
}


@pytest.mark.asyncio
@pytest.mark.parametrize("art", ["rename", "refresh", "extend"])
async def test_konto_loeschung_waehrend_ein_schreiber_wartet_wird_nicht_zurueckgenommen(
    tmp_path, monkeypatch, art
):
    """NACHARBEIT 1 (#117/#121/#103): angepasst an die neue Regel — die
    Kontoloeschung WARTET nicht mehr am Albumschloss (siehe Modul-Docstring).
    Sie kehrt SOFORT zurueck, waehrend `art` noch mit `konto-1` im Immich-Haken
    haengt; das Album traegt `konto-1` deshalb zu diesem Zeitpunkt noch — und
    verliert es erst, wenn `art` seinen Datensatz zurueckschreibt
    (`ConfigStore._ohne_tote_konten`, ueber `update_managed_album`)."""
    import main
    from services import sync_service

    pfad = _datei(tmp_path)
    monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test-117", raising=False)
    monkeypatch.setattr(main.settings, "config_path", str(pfad), raising=False)

    client_ref: dict = {}
    op_task_ref: dict = {}
    store_ref: dict = {}
    # AUSSERHALB des Immich-Hakens gefuellt und AUSSERHALB des `async with`
    # geprueft — ein `assert` IM Haken liefe innerhalb des `except
    # Exception`, mit dem die Wrapper einen Immich-Fehler abfangen, und
    # wuerde dort verschluckt (dieselbe Lehre wie #121 Punkt 2, siehe
    # `test_loeschen_im_schloss.py`).
    konto_beim_loeschen_noch_da: list[bool] = []
    loeschung_ergebnis: dict = {}

    async def haken(_m, _a):
        if "ausgeloest" in loeschung_ergebnis:
            return  # nur beim ERSTEN Immich-Aufruf ausloesen
        loeschung_ergebnis["ausgeloest"] = True
        # `art` haelt a1s Schloss bereits (der Immich-Haken laeuft darunter) —
        # die Loeschung darf hier NICHT warten, sie kehrt sofort zurueck.
        album_vorher = store_ref["store"].get_managed_album("a1")
        konto_beim_loeschen_noch_da.append(
            album_vorher is not None
            and any(r["account_id"] == "konto-1" for r in album_vorher.person_refs)
        )
        loeschung_ergebnis["antwort"] = await asyncio.wait_for(
            client_ref["c"].delete("/api/accounts/konto-1"), 2)

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
            op_task_ref["task"] = asyncio.create_task(c.request(methode, url, json=body))
            r_op = await op_task_ref["task"]

        assert "antwort" in loeschung_ergebnis, "Immich-Haken nie erreicht"
        r_del = loeschung_ergebnis["antwort"]

        assert r_op.status_code == 200, r_op.text
        assert r_del.status_code == 204, r_del.text
        assert konto_beim_loeschen_noch_da and konto_beim_loeschen_noch_da[0], (
            "konto-1 war schon vor der Loeschung aus person_refs verschwunden — "
            "die Fixture baut das Fenster nicht wie beabsichtigt auf")

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
