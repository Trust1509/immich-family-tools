"""Nacharbeit 1 + 2 + 3 zu #85 — Testluecken aus Blind-, Gegen- und Fremdpruefer.

Vier Befunde und eine Reihe von Testluecken, alle ueber die ECHTE Tuer
(Prueffrage 7):

  1. `errors.validation_failed` deduplizierte mit einer LISTE statt einer
     MENGE — quadratisch in der Anzahl der Fehler. Siehe
     `test_viele_zusatzfelder_bleiben_schnell_und_die_antwort_bleibt_klein`
     und `test_api_health_bleibt_schnell_waehrend_grossem_request` (echter
     uvicorn — eine reine `TestClient`-Probe teilt sich zwar denselben
     Event-Loop, beweist aber nichts ueber einen echten Server unter
     echter Netzwerk-E/A). NACHARBEIT 2: Ein Request OHNE
     `Content-Length`-Header (chunked) wurde bis dahin bytesweise
     eingelesen und bei Ueberschreiten des Limits abgebrochen — das las den
     Koerper aber VOR der Anmeldeprüfung und ohne Zeitgrenze und oeffnete
     damit selbst eine neue Tuer (unbegrenzt Speicher/Verbindungen durch
     einen absichtlich nie endenden, anonymen Koerper). Ersetzt durch eine
     sofortige 411-Ablehnung ohne jedes Lesen — siehe die Tests unter
     "Befund 3" unten. NACHARBEIT 3: Die 411-Pruefung selbst liess sich mit
     einer doppelten, zuerst LEEREN `Transfer-Encoding`-Kopfzeile umgehen —
     siehe "Befund 3, Nacharbeit 3" weiter unten.
  2. `GET /api/sync/autosync-config` antwortete mit 500, sobald die
     gespeicherten Daten ein Zusatzfeld trugen (`AutoSyncConfig` ist
     zugleich `response_model` UND `extra="forbid"`).
  3. (Nacharbeit 1) Ein Request OHNE `Content-Length`-Header (chunked)
     umging die 1-MiB-Pruefung der Middleware vollstaendig — siehe Punkt 1.
  4. Der Grund eigener Validatoren (Zugangsdaten in der URL, nicht
     erlaubte Netzadresse, ungueltiges URL-Schema) ging im generischen
     Validierungspfad verloren; kaputtes JSON zeigte eine Byte-Position als
     "Feldname".

Dazu die benannten Testluecken: `extra="forbid"` an JEDEM betroffenen
Modell/Endpunkt (vorher nur `SyncNamesMultiRequest` abgedeckt), ein
verschachtelter Pfad (`persons.0.x`) statt nur des letzten Glieds.

Alle Konten, Personen, Alben und Adressen sind ERFUNDEN; das Repo ist
oeffentlich (`http://*.invalid`, Platzhalter-Schluessel).
"""

import json
import os
import re
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
# an einem der GESCHWISTER-Modelle verliert (Prueffrage 3), waere an keiner
# Stelle aufgefallen — mehrere gezielte Mutationen zielen genau darauf.

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
    # nennen: `detail` ohne Feldliste blieb unter 6157ff1 unbemerkt gruen,
    # weil kein Test `detail` selbst pruefte.
    assert "foo" in koerper_antwort["detail"], (name, koerper_antwort)


def test_verschachteltes_zusatzfeld_nennt_den_vollen_pfad(client):
    """`MultiSyncPersonEntry` ist verschachtelt (`persons[i]`) — die
    bestehende Probe fuer `SyncNamesMultiRequest`
    (`test_gruppenwahl_schnittstelle.py`) haengt das Zusatzfeld nur auf die
    OBERSTE Ebene. `main._feldnamen_aus_validierungsfehlern` verbindet
    `loc[1:]` mit '.' — dieser Test bindet das an den tatsaechlichen
    verschachtelten Pfad, nicht nur das letzte Glied ("nur letztes Glied"
    bliebe sonst unbemerkt gruen, weil "foo" ohnehin im letzten Glied
    steckt).
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


# ── Befund 3: Chunked ohne Content-Length ───────────────────────────────────
#
# NACHARBEIT 2 zu #85: Der fruehere Fix (Nacharbeit 1) las einen chunked
# Koerper bytesweise ein und brach beim Ueberschreiten des Limits ab — das
# geschah aber VOR der Anmeldeprüfung und OHNE Zeitgrenze und oeffnete damit
# selbst eine neue Tuer: Ein anonymer, absichtlich nie endender chunked-
# Koerper band unbegrenzt Speicher und eine Verbindung, ohne dass je eine
# Antwort kam (gemessen, echter uvicorn: 500 solcher Verbindungen ->
# +553 MB, keine einzige Antwort; separat gemessen: 40 gehaltene
# Verbindungen -> 43 Tracebacks "Exception in ASGI application" im Log,
# vorher 0). Ersetzt durch eine sofortige 411-Ablehnung, OHNE ein einziges
# Byte des Koerpers zu lesen (`main.py`, `auth_middleware`) — unabhaengig,
# ob die Anfrage angemeldet ist oder nicht, weil die Reihenfolge nichts
# kostet, wenn nichts gelesen wird.
#
# Kein Konsument dieser Anwendung sendet chunked (`frontend/src/api/
# client.ts` schickt ausschliesslich `JSON.stringify(...)`-Zeichenketten,
# `fetch` setzt dafuer selbst `Content-Length`) — die 411-Antwort trifft
# also nie einen echten Aufruf dieser Oberflaeche.


def test_chunked_ohne_anmeldung_wird_sofort_mit_411_abgelehnt(client):
    """Rot unter 12e45c4 (200/422/413, je nach Groesse, nach vollstaendigem
    Einlesen), gruen danach: 411, ohne Anmeldung.
    """
    def strom():
        yield b"x" * 10  # ein einzelnes, winziges Stueck reicht

    antwort = client.post(
        "/api/sync/undo",
        headers={"Content-Type": "application/json"},  # KEIN Authorization-Header
        content=strom(),
    )
    assert antwort.status_code == 411
    assert antwort.json().get("error_key") == "err_length_required"


def test_chunked_mit_anmeldung_wird_ebenfalls_mit_411_abgelehnt(client):
    """Prueffrage 1/9: Die 411-Antwort kommt UNABHAENGIG von der
    Anmeldeprüfung — ein authentifizierter chunked-Aufruf bekommt dieselbe
    Antwort wie ein unauthentifizierter, weil in beiden Faellen nichts
    gelesen wird (kein Vorrang der Anmeldung noetig).
    """
    def strom():
        yield b"x" * 10

    antwort = client.post(
        "/api/sync/undo",
        headers={**KOPF, "Content-Type": "application/json"},
        content=strom(),
    )
    assert antwort.status_code == 411
    assert antwort.json().get("error_key") == "err_length_required"


def test_411_gilt_auch_fuer_andere_methoden_als_post(client):
    """Mutations-Namensgeber "411 nur fuer POST": Die Pruefung in
    `auth_middleware` haengt NICHT am HTTP-Verb — jede `/api/`-Anfrage mit
    `Transfer-Encoding` ohne `Content-Length` wird abgelehnt, unabhaengig
    von der Methode. Eine Einschraenkung auf POST waere fuer diese
    Anwendung zwar folgenlos (kein Konsument sendet chunked, ueber keine
    Methode), aber NICHT aequivalent zum jetzigen Verhalten — dieser Test
    haelt genau das fest, statt es nur zu behaupten.
    """
    def strom():
        yield b"x" * 10

    antwort = client.put(
        "/api/sync/autosync-config",
        headers={**KOPF, "Content-Type": "application/json"},
        content=strom(),
    )
    assert antwort.status_code == 411
    assert antwort.json().get("error_key") == "err_length_required"


def test_content_length_ueber_dem_limit_liefert_weiterhin_413(client):
    """Gegenprobe/Testluecken-Schluss: Die bisherige 413-Probe hing an der
    ALTEN Chunked-Implementierung (ein Koerper ohne `Content-Length`, der
    beim Einlesen das Limit ueberschritt) — mit deren Entfernung waere die
    413-Antwort ueber `Content-Length` sonst UNGEPRUEFT geblieben, obwohl
    dieser Zweig der Middleware unveraendert ist. Ein echter, expliziter
    `Content-Length`-Header (kein Generator, kein `Transfer-Encoding`) muss
    weiterhin bei Ueberschreiten des Limits 413 liefern.
    """
    antwort = client.post(
        "/api/sync/undo",
        headers={**KOPF, "Content-Type": "application/json"},
        content=b"x" * (1024 * 1024 + 1),  # > max_request_bytes (1 MiB)
    )
    assert antwort.status_code == 413
    assert antwort.json().get("error_key") == "err_request_too_large"


def _freier_port_411() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _hat_anwendungstraceback(logtext: str) -> bool:
    """True nur bei einem Traceback, der aus UNSERER Anwendung oder aus
    Starlette/FastAPI kommt.

    Nacharbeit 3 zu #85, WICHTIG: Die vorherige Fassung dieser Probe pruefte
    pauschal `"Traceback" not in logtext` — das flackert unter Windows.
    ABWEICHUNG vom Bau-Brief: Der Brief vermutet die Health-Poll-Schleife als
    Ursache; in 20 Einzellaeufen dieser Runde (Beleg im Bericht) trat der
    Traceback einmal auf (Lauf 11 von 20) und stammte aus einer der
    ABSICHTLICH mitten im chunked-Koerper abgebrochenen Verbindungen weiter
    unten in DIESEM Test (Teil b), nicht aus der Health-Poll-Schleife: Ein
    `ConnectionResetError` in `asyncio\\proactor_events.py`
    (`_call_connection_lost`), ausgeloest beim endgueltigen Schliessen einer
    Verbindung, die der Client bereits vorher gekappt hat. Fuer die Probe
    macht das keinen Unterschied — beide Quellen sind ein clientseitiger
    Abbruch, den asyncios Proactor-Transport (Windows-spezifisch) erst beim
    naechsten Aufraeumschritt bemerkt, ausserhalb jeder ASGI-Anwendung, nie
    als "Exception in ASGI application" geloggt, aber immer noch ein
    Traceback im Log. Dieser Pfad hat mit dem hier geprueften Verhalten
    nichts zu tun. Ein WIRKLICHER Fund bleibt erkennbar: entweder ueber die
    bereits vorhandene, spezifischere Meldung "Exception in ASGI
    application", oder ueber einen Traceback-Block, der selbst einen Frame
    aus `main.py`, `starlette` oder `fastapi` nennt.
    """
    if "Exception in ASGI application" in logtext:
        return True
    bloecke = re.split(r"(?=Traceback \(most recent call last\):)", logtext)
    for block in bloecke:
        if "Traceback (most recent call last):" not in block:
            continue
        if re.search(r'File "[^"]*[\\/](main\.py|starlette[\\/]|fastapi[\\/])', block):
            return True
    return False


def test_chunked_koerper_wird_nicht_gelesen_kein_traceback_beim_abbruch(tmp_path):
    """Prueffrage 7/9, echter uvicorn (Nacharbeit 2 zu #85): Eine Probe,
    deren Koerper NIE endet, bekommt trotzdem SOFORT die 411-Antwort — das
    ist nur moeglich, wenn die Middleware wirklich nichts liest (eine reine
    `TestClient`-Probe koennte das nicht unterscheiden, ein haengender
    ASGI-`receive` wuerde dort denselben Event-Loop wie der Test selbst
    benutzen). Zusaetzlich: kein ANWENDUNGS-Traceback im Server-Log
    (`_hat_anwendungstraceback`, Nacharbeit 3 zu #85), weder bei dieser Probe
    noch bei einem abgebrochenen chunked-Koerper — anders als unter 12e45c4
    (gemessen: 43 "Exception in ASGI application" bei 40 Abbruechen), weil
    seit dieser Nacharbeit gar nichts mehr vom Koerper gelesen wird, das ein
    `ClientDisconnect` werfen koennte.
    """
    port = _freier_port_411()
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({"accounts": {}, "managed_albums": []}), encoding="utf-8")
    env = dict(
        os.environ,
        IMMICH_FAMILY_TOOLS_SECRET="nur-test-411-probe",
        IMMICH_FAMILY_TOOLS_CONFIG_PATH=str(pfad),
    )
    backend_dir = Path(__file__).resolve().parents[1]
    logpfad = tmp_path / "server.log"
    log = open(logpfad, "w", encoding="utf-8")
    prozess = subprocess.Popen(
        [sys.executable, "-B", "-m", "uvicorn", "main:app", "--port", str(port),
         "--log-level", "info"],
        cwd=backend_dir, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
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

        # a) Koerper, der nie endet: Header senden, dann NUR EIN winziges
        # Chunk, danach absichtlich nichts mehr — die Antwort muss trotzdem
        # sofort kommen, nicht erst nach einem Timeout.
        kopf = (
            "POST /api/sync/undo HTTP/1.1\r\nHost: x\r\n"
            "Content-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
        ).encode()
        s = socket.create_connection(("127.0.0.1", port))
        t0 = time.perf_counter()
        s.sendall(kopf + b"a\r\n" + b"x" * 10 + b"\r\n")  # ein Chunk, KEIN Abschluss
        s.settimeout(5.0)
        antwort = s.recv(4096)
        dauer = time.perf_counter() - t0
        s.close()
        erste_zeile = antwort.split(b"\r\n")[0].decode()
        assert "411" in erste_zeile, erste_zeile
        assert dauer < 3.0, f"Antwort kam erst nach {dauer:.2f}s — Koerper wurde vermutlich gelesen"

        # b) Verbindung mitten im chunked-Koerper abbrechen (unauth und auth)
        for auth_kopf in (b"", b"Authorization: Bearer nur-test-411-probe\r\n"):
            s = socket.create_connection(("127.0.0.1", port))
            s.sendall(
                b"POST /api/sync/undo HTTP/1.1\r\nHost: x\r\n"
                b"Content-Type: application/json\r\nTransfer-Encoding: chunked\r\n"
                + auth_kopf + b"\r\n" + b"5\r\n{\"log\r\n"
            )
            time.sleep(0.3)
            s.close()
        time.sleep(1.0)
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=10)
        except subprocess.TimeoutExpired:
            prozess.kill()
            prozess.wait(timeout=10)
        log.close()
    logtext = logpfad.read_text(encoding="utf-8", errors="replace")
    assert not _hat_anwendungstraceback(logtext), logtext


# ── Befund 3, Nacharbeit 3: Praesenz statt Wahrheitswert ───────────────────
#
# BLOCKER (Nacharbeit 3 zu #85): `elif
# request.headers.get("transfer-encoding"):` prueft einen WAHRHEITSWERT, kein
# Vorhandensein. Starlettes `Headers.__getitem__` durchsucht die rohe
# Kopfzeilenliste und gibt beim ERSTEN Treffer zurueck (siehe
# `starlette.datastructures.Headers`, gemessen in dieser Runde) — bei einer
# doppelten Kopfzeile `Transfer-Encoding: \r\nTransfer-Encoding: chunked\r\n`
# liefert `.get()` also `""`, falsch in einem `if`. httptools (das
# Produktionsformat, `uvicorn[standard]`) rahmt den Koerper trotzdem als
# chunked — die 411 blieb aus, obwohl der Koerper nie gelesen wurde und nie
# endet. Der Fix prueft nur noch die ANWESENHEIT (`in request.headers`) und
# steht jetzt VOR dem Content-Length-Zweig (RFC 9112 §6.3: Transfer-Encoding
# hat Vorrang).


def _lies_bis_eof(sock: socket.socket, timeout: float) -> tuple[bytes, bool]:
    """Liest, bis entweder `timeout` Sekunden ohne neue Daten vergehen oder
    die Gegenseite die Verbindung schliesst (`recv` liefert `b""`).

    Fuer die "Connection: close"-Probe (KLEIN) reicht ein einzelner `recv`
    nicht: Kopfzeilen und Antwortkoerper koennen in getrennten TCP-Paketen
    ankommen (gemessen), ein zu frueher `recv` saehe dann nur die Kopfzeilen
    und wuerde ein offenes Ende faelschlich fuer eine geschlossene Verbindung
    halten oder umgekehrt.
    """
    sock.settimeout(timeout)
    daten = b""
    try:
        while True:
            teil = sock.recv(65536)
            if not teil:
                return daten, True
            daten += teil
    except socket.timeout:
        return daten, False


def test_leere_te_kopfzeile_ohne_anmeldung_wird_ueber_praesenz_erkannt(client):
    """Nacharbeit 3 zu #85, BLOCKER (TestClient-Teil, Prueffrage 7 verlangt
    zusaetzlich echten uvicorn — siehe
    `test_blocker_doppelte_leere_te_kopfzeile_gegen_echten_uvicorn` unten):
    Eine EINZELNE, aber LEERE `Transfer-Encoding`-Kopfzeile ist der einfachste
    Fall, der `.get()`-Wahrheit von echter Anwesenheit unterscheidet — anders
    als bei einer DOPPELTEN Kopfzeile lässt sich dieser Fall auch über
    `TestClient`/httpx nachstellen (siehe Docstring der echten-uvicorn-Probe
    unten, warum die doppelte Form dort NICHT geht). Rot unter f17d104
    (200 statt 411 — gemessen in dieser Runde), gruen seit der
    Praesenzpruefung.
    """
    antwort = client.post(
        "/api/auth/login",
        headers={"Content-Type": "application/json", "Transfer-Encoding": ""},
        content=iter([b'{"token":"x"}']),
    )
    assert antwort.status_code == 411
    assert antwort.json().get("error_key") == "err_length_required"


def test_leere_te_kopfzeile_mit_anmeldung_wird_ebenfalls_erkannt(client):
    """Prueffrage 1/9: dieselbe Praesenzpruefung, jetzt mit gueltiger
    Anmeldung — die 411 kommt unabhaengig davon, ob die Anfrage angemeldet
    ist.
    """
    antwort = client.post(
        "/api/sync/undo",
        headers={**KOPF, "Content-Type": "application/json", "Transfer-Encoding": ""},
        content=iter([b'{"log_entry_id":"x"}']),
    )
    assert antwort.status_code == 411
    assert antwort.json().get("error_key") == "err_length_required"


def test_transfer_encoding_hat_vorrang_vor_gueltiger_content_length(client):
    """Nacharbeit 3 zu #85, Mutation "TE-Pruefung nach dem CL-Zweig": Seit
    diesem Fix steht die TE-Pruefung VOR dem Content-Length-Zweig — eine
    Anfrage mit BEIDEN Kopfzeilen bekommt die 411, selbst wenn die
    Content-Length fuer sich genommen gueltig und unter dem Limit waere.

    Ein echter `uvicorn`/httptools-Prozess weist diese Kombination bereits
    VOR der Middleware mit einem eigenen 400 zurueck (in dieser Runde
    gemessen: `HTTP/1.1 400 Bad Request`, `Invalid HTTP request received.`)
    — die Middleware verlaesst sich darauf aber bewusst nicht, weil das
    Verhalten dann vom HTTP-Server abhinge, nicht von unserem eigenen Code.
    `TestClient` erreicht die Middleware ueber den ASGI-Weg, ohne durch
    diesen Parser zu laufen, und prueft deshalb genau den Fall, den der
    Parser sonst abfaengt: Ein `elif`, das den Content-Length-Zweig VOR der
    TE-Pruefung liesse (wie in f17d104), wuerde hier faelschlich mit 200
    durchgehen — gemessen, mit derselben Anfrage gegen den Elternstand.
    """
    antwort = client.post(
        "/api/auth/login",
        headers={
            "Content-Type": "application/json",
            "Transfer-Encoding": "chunked",
            "Content-Length": "13",
        },
        content=b'{"token":"x"}',
    )
    assert antwort.status_code == 411
    assert antwort.json().get("error_key") == "err_length_required"


@pytest.mark.parametrize("pfad,methode", [("/api/auth/login", "post"), ("/api/health", "get")])
def test_411_gilt_auch_fuer_die_unprotected_pfade(client, pfad, methode):
    """Nacharbeit 3 zu #85, WICHTIG: Die bisherigen 411-Proben deckten nur
    `/api/sync/*` ab — Mutationen, die die 411 auf einzelne Pfade
    einschraenken (etwa "nur ausserhalb von UNPROTECTED" oder "nur unter
    /api/sync"), ueberlebten dort unbemerkt gruen. Gerade die
    UNPROTECTED-Pfade sind aber die eigentliche Tuer des Blocker-Befunds:
    `/api/auth/login` ist der anonyme Login, `/api/health` der zweite Pfad
    ganz ohne Anmeldeprüfung.

    `client.request(...)` statt `client.get(...)`/`client.post(...)`: Starlettes
    `TestClient.get()` nimmt bewusst kein `content` an (anders als `.post()`)
    — die generische `.request()`-Methode schon, fuer beide Methoden gleich.
    """
    antwort = client.request(
        methode.upper(),
        pfad,
        headers={"Content-Type": "application/json", "Transfer-Encoding": "chunked"},
        content=iter([b"x" * 10]),
    )
    assert antwort.status_code == 411
    assert antwort.json().get("error_key") == "err_length_required"


def test_blocker_doppelte_leere_te_kopfzeile_gegen_echten_uvicorn(tmp_path):
    """Nacharbeit 3 zu #85, BLOCKER — Nachweis durch die ECHTE Tuer
    (Prueffrage 7), der eigentliche Umgehungsfall aus dem Befund:
    `Transfer-Encoding: \\r\\nTransfer-Encoding: chunked\\r\\n` (zuerst LEER,
    dann `chunked`). httptools (das Produktionsformat, `uvicorn[standard]`)
    rahmt den Koerper trotzdem als chunked, waehrend
    `request.headers.get("transfer-encoding")` unter f17d104 nur den ersten,
    LEEREN Wert sah und als falsch wertete.

    Dieser Fall ist ueber `TestClient`/httpx NICHT nachstellbar: gemessen (in
    dieser Runde, per Zwischenschritt in der Middleware selbst beobachtet)
    fasst httpx beim Zusammenfuehren der Anfrage-Header (`Client._merge_headers`
    -> `Headers.update` -> `Headers.items()`) mehrere gleichnamige Kopfzeilen
    zu EINEM kommagetrennten Wert zusammen (hier: `", chunked"` — bereits
    WAHR), bevor die Anfrage den ASGI-Scope erreicht; der "leere erste Wert"
    existiert dort also nicht mehr, und `TestClient` kann den Blocker damit
    nicht reproduzieren (weder unter f17d104 noch unter diesem Fix). Nur ein
    echter Socket gegen einen echten `uvicorn`-Prozess zeigt das
    tatsaechliche Verhalten — deshalb diese Probe zusaetzlich zu den
    `TestClient`-Proben oben.

    Rot unter f17d104 (in dieser Runde gemessen: keine Antwort innerhalb von
    3 s, waehrend derselbe nie endende Koerper weiterlaeuft), gruen seit der
    Praesenzpruefung. Deckt in einem Lauf zugleich: Punkt 1 (Login,
    anonym+angemeldet), das KLEIN-Item "Transfer-Encoding: ohne Leerzeichen"
    und das KLEIN-Item "Connection: close".
    """
    port = _freier_port_411()
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({"accounts": {}, "managed_albums": []}), encoding="utf-8")
    env = dict(
        os.environ,
        IMMICH_FAMILY_TOOLS_SECRET="nur-test-411-blocker-probe",
        IMMICH_FAMILY_TOOLS_CONFIG_PATH=str(pfad),
    )
    backend_dir = Path(__file__).resolve().parents[1]
    logpfad = tmp_path / "server.log"
    log = open(logpfad, "w", encoding="utf-8")
    prozess = subprocess.Popen(
        [sys.executable, "-B", "-m", "uvicorn", "main:app", "--host", "127.0.0.1",
         "--port", str(port), "--http", "httptools", "--log-level", "info"],
        cwd=backend_dir, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
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

        # a) Anonymer Login, doppelte TE-Kopfzeile (zuerst leer), Koerper
        # endet nie — die Antwort muss trotzdem SOFORT kommen, und die
        # Verbindung muss danach WIRKLICH schliessen (KLEIN: Connection:
        # close), nicht nur die Kopfzeile tragen.
        kopf = (
            b"POST /api/auth/login HTTP/1.1\r\nHost: x\r\n"
            b"Content-Type: application/json\r\n"
            b"Transfer-Encoding: \r\nTransfer-Encoding: chunked\r\n\r\n"
        )
        s = socket.create_connection(("127.0.0.1", port))
        t0 = time.perf_counter()
        s.sendall(kopf + b"a\r\n" + b"x" * 10 + b"\r\n")  # ein Chunk, KEIN Abschluss
        antwort, eof = _lies_bis_eof(s, 3.0)
        dauer = time.perf_counter() - t0
        s.close()
        erste_zeile = antwort.split(b"\r\n")[0].decode()
        assert "411" in erste_zeile, erste_zeile
        assert dauer < 3.0, f"Antwort kam erst nach {dauer:.2f}s — Koerper wurde vermutlich gelesen"
        assert b"connection: close" in antwort.lower(), antwort
        assert eof, "Verbindung blieb trotz 'Connection: close' offen"

        # b) Dieselbe Kopfzeilenfolge, MIT Anmeldung — Prueffrage 1/9:
        # dieselbe sofortige 411, kein Vorrang der Anmeldeprüfung noetig.
        s = socket.create_connection(("127.0.0.1", port))
        s.sendall(
            b"POST /api/auth/login HTTP/1.1\r\nHost: x\r\n"
            b"Content-Type: application/json\r\n"
            b"Authorization: Bearer nur-test-411-blocker-probe\r\n"
            b"Transfer-Encoding: \r\nTransfer-Encoding: chunked\r\n\r\n"
            + b"a\r\n" + b"x" * 10 + b"\r\n"
        )
        antwort, _ = _lies_bis_eof(s, 3.0)
        assert b"411" in antwort.split(b"\r\n", 1)[0], antwort
        s.close()

        # c) `Transfer-Encoding:chunked` OHNE Leerzeichen nach dem
        # Doppelpunkt — die reine Anwesenheitspruefung haengt nicht an
        # dieser Schreibweise.
        s = socket.create_connection(("127.0.0.1", port))
        s.sendall(
            b"POST /api/auth/login HTTP/1.1\r\nHost: x\r\n"
            b"Content-Type: application/json\r\nTransfer-Encoding:chunked\r\n\r\n"
            + b"a\r\n" + b"x" * 10 + b"\r\n"
        )
        antwort, _ = _lies_bis_eof(s, 3.0)
        assert b"411" in antwort.split(b"\r\n", 1)[0], antwort
        s.close()
        time.sleep(0.5)
    finally:
        prozess.terminate()
        try:
            prozess.wait(timeout=10)
        except subprocess.TimeoutExpired:
            prozess.kill()
            prozess.wait(timeout=10)
        log.close()
    logtext = logpfad.read_text(encoding="utf-8", errors="replace")
    assert not _hat_anwendungstraceback(logtext), logtext


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


def test_ungueltiges_url_schema_bleibt_als_eigener_fehler_erkennbar(client):
    """Nacharbeit 2 zu #85, KLEIN: der DRITTE eigene Validator-Text
    (`models/account.py` ~14, "Immich URL must use http:// or https://")
    war bisher NICHT abgebildet und fiel auf den generischen Pfad zurueck.
    """
    antwort = client.post("/api/accounts", headers=KOPF, json={
        "name": "Testkonto", "immich_url": "ftp://beispiel.invalid", "api_key": "platzhalter",
    })
    assert antwort.status_code == 422
    koerper = antwort.json()
    assert koerper.get("error_key") == "err_invalid_url_scheme", koerper
    assert koerper["error_key"] != "err_validation_failed"


@pytest.mark.parametrize(
    "immich_url",
    [
        "http://nutzer:geheim@beispiel.invalid",  # credentials_in_url
        "http://127.0.0.1",  # disallowed_network_address
    ],
)
def test_zwei_fehler_darunter_ein_bekannter_value_error_bleibt_generisch(client, immich_url):
    """Nacharbeit 2 zu #85, Punkt 2: Der Sonderfall in
    `main._validation_error_handler` erkennt einen eigenen Validator-Grund
    NUR, wenn GENAU EIN Fehler vorliegt (`len(rohe_fehler) == 1`). Ein
    zweiter, unabhaengiger Fehler (hier: das Pflichtfeld `api_key` fehlt)
    schaltet fuer BEIDE eigenen Validator-Faelle auf den generischen Pfad
    zurueck — kein Absturz, nur der genauere Grund geht dann verloren
    (dokumentiertes, bewusstes Verhalten, kein neuer Fehler).

    `api_key` (nicht `name`) fehlt bewusst: `AccountCreate` deklariert die
    Felder in der Reihenfolge `name, immich_url, api_key`, Pydantic meldet
    Fehler in dieser Reihenfolge — mit `api_key` fehlend steht der bekannte
    `value_error` von `immich_url` an ERSTER Stelle in `exc.errors()`. Genau
    das ist die Stelle, an der eine Mutation `len(rohe_fehler) == 1` durch
    `>= 1` ersetzt und trotzdem (faelschlich) den Validator-Grund liefert,
    weil sie nur `rohe_fehler[0]` ansieht — mit `name` fehlend (Feld VOR
    `immich_url`) stuende der bekannte Fehler an zweiter Stelle, und dieselbe
    Mutation bliebe hier unbemerkt gruen.
    """
    antwort = client.post("/api/accounts", headers=KOPF, json={
        "name": "Testkonto", "immich_url": immich_url,
    })
    assert antwort.status_code == 422
    koerper = antwort.json()
    assert koerper.get("error_key") == "err_validation_failed", koerper
    assert "api_key" in koerper["error_params"]["fields"]


def test_gueltige_url_bleibt_unveraendert_erlaubt(client):
    """Gegenprobe: Die Zuordnung ueber den ValueError-Text darf keine
    gueltige URL treffen.
    """
    antwort = client.post("/api/accounts", headers=KOPF, json={
        "name": "Testkonto", "immich_url": "http://beispiel.invalid", "api_key": "platzhalter",
    })
    # Kein 422 mehr wegen der URL selbst (das Konto scheitert hier an der
    # ausbleibenden echten Immich-Instanz, nicht an der URL-Form) — die
    # genaue Fehlerart ist fuer diesen Test irrelevant, nur err_credentials_in_url,
    # err_disallowed_network_address und err_invalid_url_scheme duerfen es
    # NICHT sein. Die Antwort muss trotzdem gueltiges JSON sein — ein
    # Absturz, der stattdessen einen leeren/nicht-JSON-Koerper liefert,
    # waere mit der bisherigen Kulanz (`{}` als Ersatz bei nicht-JSON)
    # unbemerkt geblieben.
    assert antwort.headers.get("content-type", "").startswith("application/json"), antwort.headers
    koerper = antwort.json()
    assert koerper.get("error_key") not in (
        "err_credentials_in_url", "err_disallowed_network_address", "err_invalid_url_scheme",
    )


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
    Gemessen VOR diesem Fix (echter uvicorn, N=74000):
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
