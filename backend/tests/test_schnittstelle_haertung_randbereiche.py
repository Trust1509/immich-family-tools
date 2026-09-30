"""Nacharbeit 1 zu #85 — Testluecken aus Blind-, Gegen- und Fremdpruefer.

Vier Befunde und eine Reihe von Testluecken (Bau-Brief
`welle4/S6_na1.md`), alle ueber die ECHTE Tuer (Prueffrage 7):

  1. `errors.validation_failed` deduplizierte mit einer LISTE statt einer
     MENGE — quadratisch in der Anzahl der Fehler. Siehe
     `test_viele_zusatzfelder_bleiben_schnell_und_die_antwort_bleibt_klein`
     und `test_api_health_bleibt_schnell_waehrend_grossem_request` (echter
     uvicorn — eine reine `TestClient`-Probe teilt sich zwar denselben
     Event-Loop, beweist aber nichts ueber einen echten Server unter
     echter Netzwerk-E/A).
  2. `GET /api/sync/autosync-config` antwortete mit 500, sobald die
     gespeicherten Daten ein Zusatzfeld trugen (`AutoSyncConfig` ist
     zugleich `response_model` UND `extra="forbid"`).
  3. Ein Request OHNE `Content-Length`-Header (chunked) umging die
     1-MiB-Pruefung der Middleware vollstaendig.
  4. Der Grund eigener Validatoren (Zugangsdaten in der URL, nicht
     erlaubte Netzadresse) ging im generischen Validierungspfad verloren;
     kaputtes JSON zeigte eine Byte-Position als "Feldname".

Dazu die benannten Testluecken: `extra="forbid"` an JEDEM betroffenen
Modell/Endpunkt (vorher nur `SyncNamesMultiRequest` abgedeckt), ein
verschachtelter Pfad (`persons.0.x`) statt nur des letzten Glieds.

Alle Konten, Personen, Alben und Adressen sind ERFUNDEN; das Repo ist
oeffentlich (`http://*.invalid`, Platzhalter-Schluessel).
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main

TESTMARKE = "nur-fuer-den-test-kein-geheimnis"
KOPF = {"Authorization": f"Bearer {TESTMARKE}"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Leeres Datenverzeichnis — die Tests hier brauchen keine bestehenden
    Konten oder Alben: Jeder `extra="forbid"`-Fehler entsteht schon bei der
    Koerper-Validierung, BEVOR ein Router auf gespeicherte Daten zugreift.
    """
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({"accounts": {}, "managed_albums": []}), encoding="utf-8")
    monkeypatch.setattr(main.settings, "secret", TESTMARKE, raising=False)
    monkeypatch.setattr(main.settings, "config_path", pfad, raising=False)
    with TestClient(main.app, raise_server_exceptions=False) as c:
        yield c


# ── Testluecke: `extra="forbid"` an JEDEM betroffenen Modell ───────────────
#
# Vorher hatte nur `SyncNamesMultiRequest` eine eigene Probe
# (`test_gruppenwahl_schnittstelle.py`). Ein Wechsel, der `extra="forbid"`
# an einem der GESCHWISTER-Modelle verliert (Pruefframge 3), waere an keiner
# Stelle aufgefallen — die sieben Mutationen M13–M20 im Blind-Bericht zielen
# genau darauf.

_FORBID_FAELLE = [
    ("UndoRequest", "post", "/api/sync/undo", {"log_entry_id": "x"}),
    ("AutoSyncConfig", "put", "/api/sync/autosync-config", {"enabled": True, "time": "02:00"}),
    ("SyncNamesRequest", "post", "/api/sync/names", {"match_id": "m1", "name": "X"}),
    ("ExtendMatchRequest", "post", "/api/sync/extend",
     {"managed_album_id": "a1", "account_id": "konto-2", "person_id": "p9"}),
    ("SyncAlbumRequest", "post", "/api/sync/album",
     {"match_id": "m1", "owner_account_id": "konto-1"}),
    ("RenameManagedAlbumRequest", "patch", "/api/sync/albums/a1", {"album_name": "Neu"}),
]


@pytest.mark.parametrize("name,methode,pfad,koerper", _FORBID_FAELLE)
def test_unbekanntes_feld_wird_an_jedem_modell_abgelehnt(client, name, methode, pfad, koerper):
    anfrage = dict(koerper)
    anfrage["foo"] = 1
    antwort = getattr(client, methode)(pfad, headers=KOPF, json=anfrage)
    assert antwort.status_code == 422, f"{name}: {antwort.status_code} {antwort.text}"
    koerper_antwort = antwort.json()
    assert koerper_antwort.get("error_key") == "err_validation_failed", (name, koerper_antwort)
    assert "foo" in koerper_antwort["error_params"]["fields"], (name, koerper_antwort)
    # Nicht nur `error_params` — auch `detail` (der Rueckfall-Klartext fuer
    # ein Frontend, das den Schluessel nicht kennt) muss den Feldnamen
    # nennen. Mutation M21 (Blind-Bericht): `detail` ohne Feldliste blieb
    # unter 6157ff1 unbemerkt gruen, weil kein Test `detail` selbst pruefte.
    assert "foo" in koerper_antwort["detail"], (name, koerper_antwort)


def test_verschachteltes_zusatzfeld_nennt_den_vollen_pfad(client):
    """`MultiSyncPersonEntry` ist verschachtelt (`persons[i]`) — die
    bestehende Probe fuer `SyncNamesMultiRequest`
    (`test_gruppenwahl_schnittstelle.py`) haengt das Zusatzfeld nur auf die
    OBERSTE Ebene. `main._feldnamen_aus_validierungsfehlern` verbindet
    `loc[1:]` mit '.' — dieser Test bindet das an den tatsaechlichen
    verschachtelten Pfad, nicht nur das letzte Glied (Mutation M11 im
    Blind-Bericht: "nur letztes Glied" bliebe sonst unbemerkt gruen, weil
    "foo" ohnehin im letzten Glied steckt).
    """
    antwort = client.post("/api/sync/names-multi", headers=KOPF, json={
        "persons": [
            {"account_id": "konto-1", "person_id": "p1"},
            {"account_id": "konto-2", "person_id": "p2", "foo": 1},
        ],
        "canonical_name": "N",
    })
    assert antwort.status_code == 422
    felder = antwort.json()["error_params"]["fields"]
    assert felder == "persons.1.foo", felder


# ── Befund 2: AutoSyncConfig 500 bei gespeichertem Zusatzfeld ──────────────


def test_autosync_config_mit_gespeichertem_zusatzfeld_liefert_200(tmp_path, monkeypatch):
    """Rot unter 6157ff1 (500 Internal Server Error), gruen danach.

    `AutoSyncConfig` war zugleich `response_model` UND trug
    `extra="forbid"` — Pydantic validiert das Antwortobjekt GEGEN dasselbe
    Modell, und ein gespeichertes Zusatzfeld (Handbearbeitung, Downgrade
    nach einem kuenftigen Feld) loeste eine `ResponseValidationError` aus,
    die FastAPI als 500 beantwortet, BEVOR unser eigener Handler ueberhaupt
    zum Zug kommt (das ist ein interner Fehler der Anwendung, kein
    Client-Fehler).
    """
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {}, "managed_albums": [],
        "auto_sync": {"enabled": True, "time": "02:00", "ein_kuenftiges_feld": "x"},
    }), encoding="utf-8")
    main_settings_patch(monkeypatch, pfad)
    with TestClient(main.app, raise_server_exceptions=False) as c:
        antwort = c.get("/api/sync/autosync-config", headers=KOPF)
        assert antwort.status_code == 200, antwort.text
        assert antwort.json() == {"enabled": True, "time": "02:00"}


def test_autosync_config_put_bleibt_bei_forbid(tmp_path, monkeypatch):
    """Gegenprobe: Die Trennung Anfrage-/Antwortmodell darf `extra="forbid"`
    fuer die ANFRAGE nicht verlieren — sonst waere ein Tippfehler im PUT
    wieder still ignoriert worden (derselbe Fehler, den #85 Punkt 2 fuer
    die anderen Modelle behoben hat).
    """
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({"accounts": {}, "managed_albums": []}), encoding="utf-8")
    main_settings_patch(monkeypatch, pfad)
    with TestClient(main.app, raise_server_exceptions=False) as c:
        antwort = c.put("/api/sync/autosync-config", headers=KOPF,
                         json={"enabled": True, "time": "02:00", "foo": 1})
        assert antwort.status_code == 422
        assert antwort.json().get("error_key") == "err_validation_failed"


def main_settings_patch(monkeypatch, pfad):
    monkeypatch.setattr(main.settings, "secret", TESTMARKE, raising=False)
    monkeypatch.setattr(main.settings, "config_path", pfad, raising=False)


# ── Befund 3: Chunked ohne Content-Length umgeht die 1-MiB-Grenze ──────────


def test_chunked_ohne_content_length_wird_trotzdem_begrenzt(client):
    """Rot unter 6157ff1 (200/422 statt 413), gruen danach.

    Gemessen VOR diesem Fix, mit genau diesem Muster (20 * 64 KiB = 1,25 MB
    ohne Content-Length-Header): Die 1-MiB-Pruefung der Middleware griff
    nicht, FastAPI las den kompletten Koerper trotzdem ein.
    """
    def strom():
        for _ in range(20):
            yield b"x" * 65536  # 20 * 64 KiB > 1 MiB, ohne Content-Length

    antwort = client.post(
        "/api/sync/undo",
        headers={**KOPF, "Content-Type": "application/json"},
        content=strom(),
    )
    assert antwort.status_code == 413
    assert antwort.json().get("error_key") == "err_request_too_large"


def test_chunked_body_unter_dem_limit_kommt_beim_router_an(client):
    """Gegenprobe zum Grenzentest oben (Pruefframge 4): Der Fix darf einen
    GUELTIGEN, bloss ohne Content-Length gesendeten Koerper nicht kaputt
    machen — sonst waere die Sperre staerker als noetig, und ein echter
    Client, der zufaellig chunked sendet (z. B. hinter einem Proxy), faende
    sich blockiert, ohne zu gross zu sein. Das prueft zugleich, dass das
    Setzen von `request._body` in der Middleware (Pruefframge 1: schreibt
    dieser Fix an einer Stelle, die vorher nur las?) den Koerper korrekt an
    den Router WEITERGIBT, statt ihn zu verschlucken.
    """
    body = json.dumps({"log_entry_id": "gibt-es-nicht"}).encode()

    def strom():
        yield body

    antwort = client.post(
        "/api/sync/undo",
        headers={**KOPF, "Content-Type": "application/json"},
        content=strom(),
    )
    # 404 (log_entry_not_found), NICHT 413/422 — der Koerper kam vollstaendig
    # und korrekt geparst beim Router an.
    assert antwort.status_code == 404
    assert antwort.json().get("error_key") == "err_log_entry_not_found"


# ── Befund 4: Eigener Validierungsgrund geht verloren ──────────────────────


def test_zugangsdaten_in_der_url_bleiben_als_eigener_fehler_erkennbar(client):
    antwort = client.post("/api/accounts", headers=KOPF, json={
        "name": "Testkonto", "immich_url": "http://nutzer:geheim@beispiel.invalid",
        "api_key": "platzhalter",
    })
    assert antwort.status_code == 422
    koerper = antwort.json()
    assert koerper.get("error_key") == "err_credentials_in_url", koerper
    assert koerper["error_key"] != "err_validation_failed"


def test_nicht_erlaubte_netzadresse_bleibt_als_eigener_fehler_erkennbar(client):
    antwort = client.post("/api/accounts", headers=KOPF, json={
        "name": "Testkonto", "immich_url": "http://127.0.0.1", "api_key": "platzhalter",
    })
    assert antwort.status_code == 422
    koerper = antwort.json()
    assert koerper.get("error_key") == "err_disallowed_network_address", koerper
    assert koerper["error_key"] != "err_validation_failed"


def test_gueltige_url_bleibt_unveraendert_erlaubt(client):
    """Gegenprobe: Die Zuordnung ueber den ValueError-Text darf keine
    gueltige URL treffen.
    """
    antwort = client.post("/api/accounts", headers=KOPF, json={
        "name": "Testkonto", "immich_url": "http://beispiel.invalid", "api_key": "platzhalter",
    })
    # Kein 422 mehr wegen der URL selbst (das Konto scheitert hier an der
    # ausbleibenden echten Immich-Instanz, nicht an der URL-Form) — die
    # genaue Fehlerart ist fuer diesen Test irrelevant, nur err_credentials_in_url
    # und err_disallowed_network_address duerfen es NICHT sein.
    koerper = antwort.json() if antwort.headers.get("content-type", "").startswith("application/json") else {}
    assert koerper.get("error_key") not in ("err_credentials_in_url", "err_disallowed_network_address")


def test_kaputtes_json_bekommt_einen_eigenen_wortlaut(client):
    """Rot unter 6157ff1 (`error_key=err_validation_failed`,
    `detail="Ungueltiger Wert fuer: 15"` — eine Byte-Position als
    "Feldname"), gruen danach.
    """
    antwort = client.post(
        "/api/sync/names-multi",
        headers={**KOPF, "Content-Type": "application/json"},
        content=b'{"persons": [1,',
    )
    assert antwort.status_code == 422
    koerper = antwort.json()
    assert koerper.get("error_key") == "err_invalid_json_body", koerper
    assert koerper["error_key"] != "err_validation_failed"
    assert not any(ch.isdigit() for ch in koerper["detail"])


# ── Befund 1: quadratische Entdopplung + unbegrenzte Gesamtantwort ─────────


def test_viele_zusatzfelder_bleiben_schnell_und_die_antwort_bleibt_klein(client):
    """Rot unter 6157ff1 (Zeitgrenze), gruen danach.

    `errors.validation_failed` deduplizierte bisher mit einer LISTE
    (`if name not in eindeutig`) — quadratisch in der Anzahl der Fehler.
    Gemessen VOR diesem Fix, isoliert (`errors.validation_failed()` direkt
    aufgerufen, ausserhalb dieser Suite, derselbe Rechner): 10 000 Feldnamen
    0,31 s, 30 000 Feldnamen 2,70 s, 50 000 Feldnamen 8,23 s — deutlich mehr
    als linear. Nach dem Fix (dieselbe isolierte Messung): 50 000 Feldnamen
    0,005 s. Die Grenze hier ist GROSSZUEGIG (mehr als das 500-fache der
    gemessenen Nach-Fix-Zeit inklusive echtem HTTP/Pydantic-Overhead), damit
    der Test auf einer langsamen Maschine nicht flackert — und trotzdem weit
    unter der gemessenen Vorher-Zeit (8,23 s) liegt, also als Rot-Beweis
    taugt.
    """
    n = 50000
    koerper = {f"f{i:06d}": 0 for i in range(n)}
    koerper["log_entry_id"] = "x"
    roh = json.dumps(koerper).encode()
    t0 = time.perf_counter()
    antwort = client.post(
        "/api/sync/undo",
        headers={**KOPF, "Content-Type": "application/json"},
        content=roh,
    )
    dauer = time.perf_counter() - t0
    assert antwort.status_code == 422
    assert dauer < 3.0, (
        f"validation_failed() braucht {dauer:.2f}s fuer {n} Felder — "
        f"Verdacht auf O(n^2) (vor dem Fix gemessen: 8,23s bei 50000)"
    )
    koerper_antwort = antwort.json()
    # Gesamtantwort bleibt begrenzt, unabhaengig von der Anzahl der Felder im
    # Request: Ohne Deckelung waechst `detail`/`error_params` mit dem
    # Client-Input (bei 50000 eindeutigen Feldnamen waere das eine Antwort
    # von rund 400 KB gewesen, statt der paar hundert Bytes hier).
    assert len(antwort.content) < 5000, f"Antwort {len(antwort.content)} Bytes bei {n} Feldern"
    assert "weitere" in koerper_antwort["detail"]


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_api_health_bleibt_schnell_waehrend_grossem_request(tmp_path):
    """Rot unter 6157ff1, gruen danach — mit einem ECHTEN uvicorn-Prozess.

    Pruefframge 7 verlangt hier ausdruecklich "echten uvicorn fuer die
    Blockade-Probe": Eine reine `TestClient`-Probe teilt sich zwar denselben
    Event-Loop wie ein zweiter Thread desselben Prozesses und kann so
    ebenfalls Blockade messen — sie beweist aber nichts ueber einen ECHTEN
    Server unter echter Netzwerk-E/A (Socket, uvicorns eigener Worker-Loop).
    Gemessen VOR diesem Fix (Gegenpruefer #85, echter uvicorn, N=74000):
    `/api/health` wartete 29,7 s auf denselben Event-Loop, waehrend der
    grosse Request lief. Diese Probe nutzt ein kleineres N (siehe die
    isolierten Messungen oben) und eine grosszuegige Grenze.
    """
    port = _freier_port()
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({"accounts": {}, "managed_albums": []}), encoding="utf-8")
    env = dict(
        os.environ,
        IMMICH_FAMILY_TOOLS_SECRET="nur-test-blockade-probe",
        IMMICH_FAMILY_TOOLS_CONFIG_PATH=str(pfad),
    )
    backend_dir = Path(__file__).resolve().parents[1]
    prozess = subprocess.Popen(
        [sys.executable, "-B", "-m", "uvicorn", "main:app", "--port", str(port),
         "--log-level", "warning"],
        cwd=backend_dir, env=env, stdin=subprocess.DEVNULL,
    )
    try:
        hoch = False
        for _ in range(150):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
                hoch = True
                break
            except Exception:
                time.sleep(0.2)
        assert hoch, "uvicorn kam nicht rechtzeitig hoch"

        n = 50000
        koerper = {f"f{i:06d}": 0 for i in range(n)}
        koerper["log_entry_id"] = "x"
        roh = json.dumps(koerper).encode()
        ergebnis: dict[str, float] = {}

        def gross():
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/sync/undo", data=roh, method="POST",
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer nur-test-blockade-probe"},
            )
            try:
                urllib.request.urlopen(req, timeout=60)
            except urllib.error.HTTPError:
                pass  # 422 ist erwartet -- nur die Dauer zaehlt hier
            ergebnis["gross_fertig"] = time.perf_counter()

        th = threading.Thread(target=gross)
        t_start = time.perf_counter()
        th.start()
        time.sleep(1.0)
        t0 = time.perf_counter()
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=30).read()
        health_dauer = time.perf_counter() - t0
        th.join(timeout=60)
        assert "gross_fertig" in ergebnis, "grosser Request nicht rechtzeitig fertig geworden"
        assert health_dauer < 5.0, (
            f"/api/health brauchte {health_dauer:.2f}s waehrend eines grossen Requests "
            f"-- Verdacht auf blockierten Event-Loop (vor dem Fix gemessen: 29,7s bei N=74000)"
        )
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=10)
        except subprocess.TimeoutExpired:
            prozess.kill()
            prozess.wait(timeout=10)
