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


def test_kein_router_wirft_noch_eine_nackte_httpexception():
    """Eine neue HTTPException ohne Schluessel faellt still auf Deutsch zurueck.

    Das ist kein Absturz und keine leere Meldung — deshalb faellt es niemandem
    auf. Ein Test ist der einzige Ort, an dem es auffallen kann.
    """
    treffer = []
    for datei in sorted((WURZEL / "backend" / "routers").glob("*.py")):
        for nr, zeile in enumerate(datei.read_text("utf-8").splitlines(), 1):
            if "raise HTTPException" in zeile:
                treffer.append(f"{datei.name}:{nr}")
    assert treffer == [], f"nackte HTTPException: {treffer}"


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
