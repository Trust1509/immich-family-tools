"""Prueft die Fehlerform und den Abgleich mit dem Frontend.

Der teuerste Fehler dieses Pfades ist NICHT eine falsche Uebersetzung, sondern
eine LEERE Meldung: Der Nutzer sieht "Error:" und nichts dahinter. Deshalb
pruefen die Tests hier vor allem, dass der deutsche Klartext die Antwort nie
verlaesst — und dass die Schluesselmengen von Backend und Frontend
uebereinstimmen, weil ein Schluessel ohne Gegenstueck genau dorthin fuehrt.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import errors
import main

WURZEL = Path(__file__).resolve().parents[2]
I18N = WURZEL / "frontend" / "src" / "i18n.tsx"

SCHLUESSEL_MUSTER = re.compile(r'"(err_[a-z0-9_]+)"')


def backend_schluessel() -> set[str]:
    return set(SCHLUESSEL_MUSTER.findall((WURZEL / "backend" / "errors.py").read_text("utf-8")))


def frontend_schluessel() -> set[str]:
    """Nur die Schluessel, die als EINTRAG in der Tabelle stehen.

    Ein blosses Vorkommen von "err_..." irgendwo in der Datei reicht nicht —
    ein Schluessel in einem Kommentar oder in ERROR_PARAM_ORDER waere sonst
    ein Treffer, und der Abgleich waere gruen, ohne dass eine Uebersetzung
    existiert. Gesucht wird die Form `  err_xyz: {` am Zeilenanfang.
    """
    text = I18N.read_text("utf-8")
    return set(re.findall(r"^  (err_[a-z0-9_]+): \{", text, re.M))


def test_jede_meldung_hat_einen_schluessel_und_klartext():
    """Kein AppError darf ohne Schluessel oder ohne Text existieren."""
    ohne = []
    for name in dir(errors):
        if name.startswith("_") or name in ("AppError", "antwort"):
            continue
        f = getattr(errors, name)
        if not callable(f) or not hasattr(f, "__module__") or f.__module__ != "errors":
            continue
        # Meldungen mit Parametern bekommen Platzhalterwerte.
        anzahl = f.__code__.co_argcount
        fehler = f(*["x"] * anzahl)
        if not isinstance(fehler, errors.AppError):
            continue
        if not fehler.key or not fehler.detail:
            ohne.append(name)
    assert ohne == [], f"AppError ohne Schluessel oder Text: {ohne}"


def test_antwortform_traegt_klartext_schluessel_und_werte():
    fehler = errors.account_id_not_found("a1")
    assert errors.antwort(fehler) == {
        "detail": "Account a1 nicht gefunden",
        "error_key": "err_account_id_not_found",
        "error_params": {"id": "a1"},
    }


def test_detail_bleibt_eine_zeichenkette():
    """Die Rueckwaertsvertraeglichkeit der Schnittstelle.

    Wer `detail` zu einem Objekt macht, bricht jeden Fremdkonsumenten UND
    nimmt dem Frontend den Rueckfall. Beides auf einmal, still.
    """
    for name in ("account_not_found", "immich_unreachable", "match_album_exists"):
        f = getattr(errors, name)
        fehler = f(*["x"] * f.__code__.co_argcount)
        assert isinstance(errors.antwort(fehler)["detail"], str)


def test_schluesselmengen_von_backend_und_frontend_sind_gleich():
    """Zwei Stellen, die auseinanderlaufen koennen — also verglichen.

    Ein Schluessel ohne Uebersetzung faellt zwar auf den deutschen Klartext
    zurueck (das ist gewollt), aber dann ist die Meldung fuer spanische und
    portugiesische Nutzer still deutsch. Genau der Zustand, den dieser Slice
    beseitigt hat; er darf nicht durch die Hintertuer zurueckkommen.
    """
    nur_backend = sorted(backend_schluessel() - frontend_schluessel())
    nur_frontend = sorted(frontend_schluessel() - backend_schluessel())
    assert nur_backend == [], f"ohne Uebersetzung im Frontend: {nur_backend}"
    assert nur_frontend == [], f"im Frontend, aber nirgends geworfen: {nur_frontend}"


# Nicht "raise HTTPException" als Zeichenkette, sondern jede Erzeugung einer
# HTTPException — egal ob geworfen, zwischengespeichert oder qualifiziert
# geschrieben. Die erste Fassung suchte woertlich "raise HTTPException" und war
# in EINER Zeile zu umgehen:
#
#     exc = HTTPException(status_code=404, detail="…")
#     raise exc          ->  57 Tests gruen, error_key still verloren
#
# Ebenso unentdeckt: zwei Leerzeichen nach "raise", "fastapi.HTTPException",
# und alles ausserhalb von routers/ — der Scan sah genau ein Verzeichnis an.
# Von der blinden Panel-Stimme vorgefuehrt.
# OHNE REGULAEREN AUSDRUCK, und das ist der zweite Anlauf. Die erste Fassung
# begann mit einer Wortgrenze — und beim Schreiben durch die Werkzeugkette
# wurde daraus ein BACKSPACE-ZEICHEN (0x08). Das Muster traf danach gar
# nichts mehr, sah aber im Editor und in `grep` voellig richtig aus, weil das
# Zeichen unsichtbar ist. Zwei Mutationen liefen daran vorbei und wurden nur
# zufaellig vom Nachbartest gefangen, der auf den deutschen Text ansprang.
#
# Ein Waechter, dessen Muster man nicht LESEN kann, ist keiner.
def _erzeugt_httpexception(zeile: str) -> bool:
    """Findet jede Erzeugung, egal wie geschrieben.

    Leerzeichen fallen vorher weg, damit `HTTPException (` und
    `fastapi.HTTPException(` genauso auffallen wie die uebliche Form.
    """
    return "HTTPException(" in zeile.replace(" ", "")

# Diese Dateien duerfen HTTPException nennen: errors.py definiert AppError
# darauf, und dieser Test sucht danach.
ERLAUBT = {"errors.py", "test_errors.py"}


def test_niemand_erzeugt_mehr_eine_nackte_httpexception():
    """Eine neue HTTPException ohne Schluessel faellt still auf Deutsch zurueck.

    Das ist kein Absturz und keine leere Meldung — deshalb faellt es niemandem
    auf. Ein Test ist der einzige Ort, an dem es auffallen kann.
    """
    treffer = []
    for datei in sorted((WURZEL / "backend").rglob("*.py")):
        if datei.name in ERLAUBT:
            continue
        for nr, zeile in enumerate(datei.read_text("utf-8").splitlines(), 1):
            if _erzeugt_httpexception(zeile):
                treffer.append(f"{datei.relative_to(WURZEL)}:{nr}")
    assert treffer == [], f"nackte HTTPException: {treffer}"


def test_kein_deutscher_klartext_ohne_schluessel_im_backend():
    """Deutsche Meldungen gibt es auch AUSSERHALB der Fehlerpfade.

    `account_status` antwortet mit 200 und legte den deutschen Text in ein
    Feld — an jedem Fehler-Waechter vorbei. Gefunden von der blinden
    Panel-Stimme, nachdem die Fehlerpfade schon umgestellt waren. Der Test
    sucht deshalb nicht nach Ausnahmen, sondern nach deutschem Text in
    Zuweisungen.
    """
    deutsch = re.compile(
        r'(?:error|detail|message)\s*=\s*"[^"]*'
        r"(?:nicht|kein|fehlgeschlagen|ungültig|bereits|erforderlich)",
        re.I,
    )
    treffer = []
    for datei in sorted((WURZEL / "backend").rglob("*.py")):
        if datei.name in ERLAUBT or "test" in datei.name:
            continue
        for nr, zeile in enumerate(datei.read_text("utf-8").splitlines(), 1):
            if deutsch.search(zeile):
                treffer.append(f"{datei.relative_to(WURZEL)}:{nr}  {zeile.strip()[:60]}")
    assert treffer == [], "deutscher Klartext ohne Schluessel: " + "; ".join(treffer)


# Der Statuscode je Meldung, festgenagelt.
#
# WARUM ALS TABELLE UND NICHT ALS KOMMENTAR: Beim Bau dieses Slices habe ich
# vier Codes "aufgeraeumt" (422 -> 400 bzw. 409), weil sie mir passender
# schienen — im selben Commit, der behauptete, an der Schnittstelle aendere
# sich nichts. Gefunden hat es die blinde Panel-Stimme, indem sie die
# laufende App gegen den Elternstand gemessen hat; KEIN Test hat es bemerkt.
#
# Ein Statuscode ist der haertere Teil des Vertrags als der Text:
# Fremdkonsumenten verzweigen darauf. Diese Tabelle macht jede Aenderung zu
# einer bewussten.
STATUSCODES = {
    "err_account_gone": 404,
    "err_account_id_not_found": 404,
    "err_account_not_found": 404,
    "err_album_already_managed": 409,
    "err_album_name_required": 422,
    "err_immich_request_failed": 502,
    "err_immich_unreachable": 422,
    "err_invalid_content_length": 400,
    "err_invalid_time_format": 422,
    "err_invalid_token": 401,
    "err_log_entry_not_found": 404,
    "err_managed_album_not_found": 404,
    "err_match_album_exists": 409,
    "err_match_not_found": 404,
    "err_min_two_people": 422,
    "err_no_thumbnail": 404,
    "err_not_undoable": 422,
    "err_owner_account_id_not_found": 404,
    "err_owner_account_not_found": 404,
    "err_person_validation_failed": 422,
    "err_request_too_large": 413,
    "err_too_many_login_attempts": 429,
    "err_unauthorized": 401,
    "err_unsupported_immich_version": 422,
}


def test_die_statuscodes_sind_festgenagelt():
    ist = {}
    for name in dir(errors):
        if name.startswith("_") or name in ("AppError", "antwort"):
            continue
        f = getattr(errors, name)
        if not callable(f) or getattr(f, "__module__", None) != "errors":
            continue
        fehler = f(*["x"] * f.__code__.co_argcount)
        if isinstance(fehler, errors.AppError):
            ist[fehler.key] = fehler.status_code
    assert ist == STATUSCODES


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Ein Client MIT Startup-Ereignissen, auf einem Wegwerf-Datenverzeichnis.

    `TestClient(app)` allein fuehrt den Startup NICHT aus — die Route holt
    dann `app.state.settings` und bekommt einen AttributeError. Nur die
    Kontextmanager-Form startet die Anwendung wirklich. Beim ersten Anlauf
    ist genau daran ein Test gescheitert, und der Middleware-Test daneben
    blieb gruen, weil er die Route gar nicht erreicht: Ein halb gestarteter
    Client sieht aus wie ein ganzer, solange man nur flach genug prueft.

    Das Datenverzeichnis zeigt auf tmp_path, damit kein Lauf die echte
    accounts.json anfasst. Kein Geheimnis wird gesetzt: Der 401-Pfad und der
    Login-mit-falschem-Token brauchen keins.
    """
    # main.py bindet `settings` beim IMPORT (Modulebene). Umgebungsvariablen
    # nach dem Import wirken deshalb nicht mehr — der erste Anlauf hat das
    # versucht und ist am Startup-Wachhund gescheitert. Also das Objekt
    # selbst umstellen, das main tatsaechlich benutzt.
    monkeypatch.setattr(main.settings, "allow_insecure_no_auth", True, raising=False)
    monkeypatch.setattr(main.settings, "config_path", tmp_path / "accounts.json", raising=False)
    with TestClient(main.app) as c:
        yield c


def test_ein_echter_fehlerpfad_liefert_die_neue_form(client):
    """Durch die echte Anwendung, nicht gegen die Funktion allein."""
    antwort = client.post("/api/auth/login", json={"token": "falsch"})
    assert antwort.status_code == 401
    koerper = antwort.json()
    assert koerper["error_key"] == "err_invalid_token"
    assert isinstance(koerper["detail"], str) and koerper["detail"]
    assert koerper["error_params"] == {}


def test_der_middleware_pfad_liefert_dieselbe_form(client):
    """Die Middleware laeuft VOR dem Exception-Handler und baut selbst.

    Genau deshalb ist sie die Stelle, an der ein Pfad still beim alten Format
    bleiben koennte.
    """
    antwort = client.get("/api/accounts")
    assert antwort.status_code == 401
    koerper = antwort.json()
    assert koerper["error_key"] == "err_unauthorized"
    assert isinstance(koerper["detail"], str) and koerper["detail"]


def test_fastapis_eigener_validierungsfehler_bleibt_unveraendert(client):
    """Nicht jeder Fehler hat einen Schluessel — und das ist in Ordnung.

    FastAPI liefert bei Validierungsfehlern eine LISTE unter `detail` und gar
    keinen Schluessel. Das Frontend muss damit umgehen; hier wird nur
    festgehalten, dass es diese Form wirklich gibt, damit niemand den
    Rueckfall im Frontend fuer ueberfluessig haelt.
    """
    antwort = client.post("/api/auth/login", json={})
    assert antwort.status_code == 422
    koerper = antwort.json()
    assert isinstance(koerper["detail"], list)
    assert "error_key" not in koerper
