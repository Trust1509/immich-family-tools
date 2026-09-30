"""Prueft die Fehlerform und den Abgleich mit dem Frontend.

Der teuerste Fehler dieses Pfades ist NICHT eine falsche Uebersetzung, sondern
eine LEERE Meldung: Der Nutzer sieht "Error:" und nichts dahinter. Deshalb
pruefen die Tests hier vor allem, dass der deutsche Klartext die Antwort nie
verlaesst — und dass die Schluesselmengen von Backend und Frontend
uebereinstimmen, weil ein Schluessel ohne Gegenstueck genau dorthin fuehrt.
"""

import ast
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import errors
import main

WURZEL = Path(__file__).resolve().parents[2]
I18N = WURZEL / "frontend" / "src" / "i18n.tsx"
_MODELS_DIR = WURZEL / "backend" / "models"

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
    for name in ("account_not_found", "immich_unreachable", "person_validation_failed"):
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
    "err_album_name_required": 422,
    "err_credentials_in_url": 422,
    "err_disallowed_network_address": 422,
    "err_duplicate_query_param": 422,
    "err_invalid_json_body": 422,
    "err_invalid_url_scheme": 422,
    "err_group_choice_conflict": 422,
    "err_group_choice_required": 409,
    "err_group_not_found": 404,
    "err_group_situation_changed": 409,
    "err_immich_request_failed": 502,
    "err_immich_unreachable": 422,
    "err_invalid_content_length": 400,
    "err_invalid_time_format": 422,
    "err_invalid_token": 401,
    "err_length_required": 411,
    "err_log_entry_not_found": 404,
    "err_managed_album_not_found": 404,
    "err_manual_match_id_collision": 409,
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
    "err_validation_failed": 422,
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


def test_gekuerzt_kappt_exakt_bei_200_zeichen_plus_ellipse():
    """#85 Nacharbeit 1, KLEIN: Die Kappung liefert bei Ueberlaenge 201
    Zeichen (200 gehaltene plus die Ellipse) — nicht genau 200. Bisherige
    Tests pruefen nur `< len(original)`, das waere auch bei einer falschen
    Grenze (z. B. 50 oder 500) gruen. Dieser Test naegelt den EXAKTEN Wert
    fest, wie im Bau-Brief gefordert.
    """
    lang = "x" * 300
    assert errors._gekuerzt(lang) == "x" * 200 + "…"
    assert len(errors._gekuerzt(lang)) == 201


def test_gekuerzt_laesst_kurze_werte_unveraendert():
    kurz = "x" * 200
    assert errors._gekuerzt(kurz) == kurz


@pytest.mark.parametrize(
    "fabrik",
    [
        errors.account_id_not_found,
        errors.owner_account_id_not_found,
        errors.person_validation_failed,
        errors.manual_match_id_collision,
        errors.group_choice_required,
        errors.group_situation_changed,
    ],
)
def test_jede_meldung_mit_zurueckgespiegeltem_wert_kappt_ihn(fabrik):
    """#85 Nacharbeit 1, Testluecke: `group_not_found` und `validation_failed`
    hatten schon eine Kappungsprobe (`test_gruppenwahl_schnittstelle.py`) —
    die uebrigen fuenf Funktionen mit `_gekuerzt()` hatten keine EIGENE. Ein
    Tippfehler, der `_gekuerzt()` an einer dieser Stellen durch `str()`
    ersetzt, waere hier unbemerkt geblieben.
    """
    lang = "y" * 5000
    fehler = fabrik(lang)
    erwartet = "y" * 200 + "…"
    assert lang not in fehler.detail
    assert erwartet in fehler.detail
    for wert in fehler.params.values():
        assert wert == erwartet, (fabrik.__name__, fehler.params)


def test_validation_failed_dedupliziert_und_erhaelt_reihenfolge():
    """Die eigentliche Fehlfunktion war quadratisch (Liste statt Menge) —
    dieser Test prueft die KORREKTHEIT (Reihenfolge, keine Duplikate); die
    LAUFZEIT prueft `test_schnittstelle_haertung_randbereiche.py` durch die
    echte Tuer.
    """
    fehler = errors.validation_failed(["b", "a", "b", "c", "a"])
    assert fehler.params["fields"] == "b, a, c"
    assert fehler.params["more"] == "0"


def test_validation_failed_deckelt_die_angezeigte_feldzahl():
    """#85 Nacharbeit 1 Punkt 1/3: Ohne Deckel waechst `detail` mit jedem
    vom Client gewaehlten Feldnamen — bei vielen tausend Feldern eine
    unbegrenzte Antwort (Punkt 3). Diese Probe bindet nur die KORREKTHEIT der
    Deckelung (Anzahl, Resttext); die Laenge/Zeit unter echtem HTTP-Umfang
    prueft `test_schnittstelle_haertung_randbereiche.py`.

    Nacharbeit 2 zu #85: `fields` traegt seit dieser Runde NUR noch die
    Feldnamen — kein "... und N weitere" mehr als deutscher Klartext darin
    (das war das Testluecken-Symptom: `"weitere" in liste` war bisher gruen,
    weil die Uebersetzung diesen Teilsatz nie sah). Der Rest steht jetzt im
    eigenen Parameter `more`.
    """
    namen = [f"f{i:04d}" for i in range(50)]
    fehler = errors.validation_failed(namen)
    liste = fehler.params["fields"]
    assert liste.count(",") < 20, "mehr als die gedeckelten Felder erscheinen einzeln"
    assert "weitere" not in liste, "der Rest-Hinweis gehoert nicht mehr in 'fields'"
    assert fehler.params["more"] == "30"
    assert "weitere" in fehler.detail  # der deutsche Klartext-Rueckfall bleibt vollstaendig
    for name in namen[:5]:
        assert name in liste
    assert namen[-1] not in liste


@pytest.mark.parametrize(
    "anzahl_felder",
    [19, 20, 21, 22],
)
def test_validation_failed_deckel_exakt_bei_19_20_21_22(anzahl_felder):
    """Nacharbeit 2 zu #85, Punkt 2: Der Deckel selbst war nie an den GENAUEN
    Grenzen (19/20/21/22 verschiedene Felder) festgenagelt — ein `>=` statt
    `>` (zeigt bei genau 20 faelschlich
    "und 0 weitere"), ein Deckel von 24 statt 20, oder eine Kuerzung auf der
    ROHEN statt der entduplizierten Liste waeren hier alle unbemerkt
    geblieben.
    """
    namen = [f"f{i:03d}" for i in range(anzahl_felder)]
    fehler = errors.validation_failed(namen)
    liste = fehler.params["fields"]
    rest = fehler.params["more"]
    if anzahl_felder <= 20:
        assert liste == ", ".join(namen)
        assert rest == "0"
        assert "weitere" not in fehler.detail
    else:
        assert liste == ", ".join(namen[:20])
        assert rest == str(anzahl_felder - 20)
        assert namen[20] not in liste
        assert "weitere" in fehler.detail


def test_deutscher_singular_bei_genau_einem_rest_exakter_wortlaut():
    """Nacharbeit 3 zu #85, KLEIN: Die Probe oben (Fall `anzahl_felder=21`,
    `rest == "1"`) prueft nur `"weitere" in fehler.detail` — das waere auch
    bei "und 1 weitere" gruen, obwohl die eigene Singularform (`errors.py`,
    `" und eine weitere" if rest == 1 else ...`) dann entfernt waere. Dieser
    Test naegelt den EXAKTEN Wortlaut fest.
    """
    namen = [f"f{i:03d}" for i in range(21)]
    fehler = errors.validation_failed(namen)
    assert "und eine weitere" in fehler.detail, fehler.detail
    assert "und 1 weitere" not in fehler.detail, fehler.detail


def test_validation_failed_entdoppelt_vor_dem_kuerzen_nicht_danach():
    """Nacharbeit 2 zu #85: Kuerzung VOR der Entdopplung wuerde 40
    verschiedene, aber langegleich beginnende Feldnamen faelschlich auf
    weniger als 40 zusammenfassen (alle 40 teilen die ersten 200 Zeichen,
    `_gekuerzt()` liefert fuer alle denselben String). Entdoppelt wird daher
    auf dem ROHEN Namen; erst danach wird gekuerzt.
    """
    namen = [("L" * 200) + f"{i:05d}" for i in range(40)]  # gleicher 200er-Anfang, 40 verschiedene
    fehler = errors.validation_failed(namen)
    assert fehler.params["more"] == "20", fehler.params


def test_validation_failed_rest_zaehlt_verschiedene_rohnamen_nicht_duplikate():
    """Nacharbeit 2 zu #85, Punkt 2: Der Rest muss die
    Anzahl der NICHT einzeln genannten, aber VERSCHIEDENEN Rohnamen zaehlen —
    nicht die Gesamtzahl der (moeglicherweise mehrfach vorkommenden)
    Rohnamen. 25 verschiedene Namen, jeder davon zweimal in der Eingabe:
    20 werden gezeigt, der Rest ist 5 (verschiedene), nicht 30 (= 50 - 20
    Rohnamen insgesamt).
    """
    einzigartige = [f"f{i:03d}" for i in range(25)]
    namen = einzigartige + einzigartige  # jeder Name kommt zweimal vor
    fehler = errors.validation_failed(namen)
    assert fehler.params["more"] == "5"
    assert fehler.params["fields"] == ", ".join(einzigartige[:20])


def test_eigene_validatoren_haben_einen_uebersetzbaren_schluessel():
    """#85 Nacharbeit 1, KLEIN + Nacharbeit 2 (der DRITTE eigene
    Validator-Text, `models/account.py`, "Immich URL must use http:// or
    https://") muessen alle ERKENNBAR bleiben — nicht mehr im generischen
    "Ungueltige oder unbekannte Angabe fuer: immich_url" untergehen.
    """
    a = errors.credentials_in_url()
    b = errors.disallowed_network_address()
    c = errors.invalid_url_scheme()
    for fehler in (a, b, c):
        assert fehler.key != "err_validation_failed"
        assert fehler.detail
    assert len({a.key, b.key, c.key}) == 3


def _raise_valueerror_texte(quelltext: str) -> list[str]:
    """Jeder `raise ValueError("...")`-Text in einer Python-Quelldatei, per
    AST gelesen (Nacharbeit 2 zu #85, KLEIN) — nicht per Textsuche, damit ein
    mehrzeiliger oder anders eingerueckter `raise` genauso gefunden wird.

    Sieht NUR literale Strings (`ast.Constant`) — ein f-String oder eine per
    Name uebergebene Konstante liefert hier nichts zurueck. Das ist bewusst
    (der naechste Test prueft genau diesen Rest), nicht ein Versehen: Siehe
    `_raise_valueerror_nichtliterale` fuer die Gegenprobe.
    """
    baum = ast.parse(quelltext)
    texte = []
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Raise) or not isinstance(knoten.exc, ast.Call):
            continue
        func = knoten.exc.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name != "ValueError" or not knoten.exc.args:
            continue
        arg = knoten.exc.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            texte.append(arg.value)
    return texte


def _raise_valueerror_nichtliterale(quelltext: str) -> list[str]:
    """Jeder `raise ValueError(...)`-Aufruf, dessen ERSTES Argument KEIN
    literaler String ist (Nacharbeit 3 zu #85, WICHTIG).

    `_raise_valueerror_texte` sieht nur `ast.Constant`-Strings — ein
    f-String (`ast.JoinedStr`) oder eine per Namen uebergebene Konstante
    (`ast.Name`) rutscht daran vorbei UND kann *nie* einen Eintrag in
    `EIGENE_VALIDATOR_GRUENDE` haben: Ein f-String aendert sich mit jedem
    Aufruf (der Text ist nicht wiederholbar, also nicht als Schluessel
    tauglich), eine per Namen uebergebene Konstante ist im AST nur ein
    Bezeichner, nicht ihr Wert. Der Grund faellt in BEIDEN Faellen IMMER auf
    den generischen Pfad zurueck — `_raise_valueerror_texte` allein wuerde
    das nie sehen, weil es dafuer gar keinen Text gibt, den es vermissen
    koennte. Jedes solche Argument ist deshalb selbst ein Fund.
    """
    baum = ast.parse(quelltext)
    fundstellen = []
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Raise) or not isinstance(knoten.exc, ast.Call):
            continue
        func = knoten.exc.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name != "ValueError" or not knoten.exc.args:
            continue
        arg = knoten.exc.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            continue
        fundstellen.append(f"Zeile {knoten.lineno}")
    return fundstellen


# Die drei heute bekannten Validator-Texte (`backend/models/account.py`) —
# eine POSITIVE Kontrolle fuer den Scan unten, nicht nur eine Anwesenheitsprobe
# der Datei. Getrennt von `errors.EIGENE_VALIDATOR_GRUENDE` gehalten (nicht
# `set(errors.EIGENE_VALIDATOR_GRUENDE)`), damit ein Waechter, der zufaellig
# dieselbe (falsche) Quelle wie der Code abfragt, nicht sich selbst bestaetigt.
_BEKANNTE_VALIDATOR_TEXTE = {
    "Immich URL must use http:// or https://",
    "Credentials are not allowed inside the Immich URL",
    "This network address is not allowed",
}


def test_ast_waechter_scannt_ueberhaupt_dateien_und_findet_die_bekannten_texte():
    """Nacharbeit 3 zu #85, WICHTIG: `_MODELS_DIR` kann auf einen falschen
    Ordnernamen zeigen (Tippfehler) — `glob("*.py")` liefert dann `[]`, und
    `test_jeder_eigene_validator_text_hat_eine_uebersetzung` bleibt GRUEN,
    OHNE je eine Datei gelesen zu haben ("leer gruen"). Diese Probe verlangt
    mindestens eine gescannte Datei UND dass die drei heute bekannten
    Validator-Texte darin tatsaechlich auftauchen — ein Waechter, der nichts
    sieht, faellt hier durch, bevor er im Nachbartest als "keine Funde"
    durchgeht.
    """
    dateien = sorted(_MODELS_DIR.glob("*.py"))
    assert dateien, f"{_MODELS_DIR} enthaelt keine .py-Datei — Waechter scannt vermutlich den falschen Ordner"
    alle_texte: set[str] = set()
    for datei in dateien:
        alle_texte.update(_raise_valueerror_texte(datei.read_text("utf-8")))
    fehlend = _BEKANNTE_VALIDATOR_TEXTE - alle_texte
    assert fehlend == set(), f"bekannte Validator-Texte nicht gefunden — Scan liest vermutlich die falschen Dateien: {fehlend}"


def test_jeder_eigene_validator_text_hat_eine_uebersetzung():
    """Nacharbeit 2 zu #85, KLEIN: Ein Wächter gegen den naechsten
    unabgebildeten Validator-Text — nicht nur gegen die drei heute bekannten.
    Liest `backend/models/*.py` per AST und verlangt, dass JEDER
    `raise ValueError("…")`-Text einen Eintrag in
    `errors.EIGENE_VALIDATOR_GRUENDE` hat, sonst faellt sein Grund wieder auf
    den generischen Pfad zurueck (kein Absturz, nur der Grund geht verloren).
    """
    fehlend = []
    for datei in sorted(_MODELS_DIR.glob("*.py")):
        for text in _raise_valueerror_texte(datei.read_text("utf-8")):
            if text not in errors.EIGENE_VALIDATOR_GRUENDE:
                fehlend.append(f"{datei.name}: {text!r}")
    assert fehlend == [], f"ValueError-Text ohne Eintrag in EIGENE_VALIDATOR_GRUENDE: {fehlend}"


def test_kein_valueerror_mit_nichtliteralem_argument_in_models():
    """Nacharbeit 3 zu #85, WICHTIG: Ein f-String oder eine per Namen
    uebergebene Konstante als `ValueError`-Argument entkommt
    `_raise_valueerror_texte` unbemerkt (siehe Docstring von
    `_raise_valueerror_nichtliterale`) — jedes Nicht-Literal-Argument von
    `ValueError` in `backend/models/` ist deshalb selbst ein Fund,
    unabhaengig davon, ob ein Eintrag in `EIGENE_VALIDATOR_GRUENDE`
    existiert.
    """
    dateien = sorted(_MODELS_DIR.glob("*.py"))
    assert dateien  # siehe test_ast_waechter_scannt_ueberhaupt_dateien_...
    fundstellen = []
    for datei in dateien:
        for stelle in _raise_valueerror_nichtliterale(datei.read_text("utf-8")):
            fundstellen.append(f"{datei.name} {stelle}")
    assert fundstellen == [], f"ValueError mit nicht-literalem Argument in models/: {fundstellen}"


def test_selbstprobe_ast_scan_erkennt_falschen_ordner():
    """Selbstprobe: Ein Ordner ohne `.py`-Dateien liefert eine leere
    Dateiliste — genau die Bedingung, die
    `test_ast_waechter_scannt_ueberhaupt_dateien_und_findet_die_bekannten_texte`
    als Fund werten muss. Ohne echte Datei im Repo zu veraendern.
    """
    leer = sorted((WURZEL / "backend" / "kein-solcher-ordner-xyz").glob("*.py"))
    assert leer == []


def test_selbstprobe_ast_scan_erkennt_nichtliterales_valueerror_argument():
    """Selbstprobe (dieselbe Klasse wie oben): Der Scan muss ein
    NICHT-literales Argument (f-String, per Namen uebergebene Konstante)
    tatsaechlich SEHEN — ohne eine echte Datei im Repo zu veraendern.
    """
    fstring_quelltext = "def f(value):\n    raise ValueError(f'Zu lang: {len(value)}')\n"
    konstante_quelltext = "_TEXT = 'Zu lang'\n\n\ndef f(value):\n    raise ValueError(_TEXT)\n"
    literal_quelltext = "def f(value):\n    raise ValueError('Zu lang')\n"
    assert _raise_valueerror_nichtliterale(fstring_quelltext) != []
    assert _raise_valueerror_nichtliterale(konstante_quelltext) != []
    assert _raise_valueerror_nichtliterale(literal_quelltext) == []


def test_selbstprobe_ast_scan_findet_einen_erfundenen_validator_ohne_eintrag():
    """Selbstprobe: Der Waechter oben ist nur dann einer, wenn der zugrunde
    liegende AST-Scan einen NEUEN, unabgebildeten Validator-Text ueberhaupt
    SEHEN kann. Diese Probe erfindet
    einen und prueft die Scan-Funktion direkt — ohne eine echte Datei im Repo
    zu veraendern (das waere Scope-Erweiterung).
    """
    quelltext = (
        "def f(value):\n"
        "    if not value:\n"
        "        raise ValueError('Ein Validator, den es nirgends gibt')\n"
        "    return value\n"
    )
    gefunden = _raise_valueerror_texte(quelltext)
    assert "Ein Validator, den es nirgends gibt" in gefunden
    assert "Ein Validator, den es nirgends gibt" not in errors.EIGENE_VALIDATOR_GRUENDE


def test_kaputtes_json_hat_einen_eigenen_schluessel():
    fehler = errors.invalid_json_body()
    assert fehler.key != "err_validation_failed"
    assert fehler.detail
    # Keine Ziffernfolge, die wie eine Byte-Position aussieht.
    assert not any(ch.isdigit() for ch in fehler.detail)


def test_fastapis_eigener_validierungsfehler_traegt_jetzt_die_hausform(client):
    """#85 Punkt 1: bewusst UMGESTELLT, nicht mehr "bleibt unveraendert".

    Bis zu diesem Slice lieferte FastAPI bei Validierungsfehlern seine
    eigene Form: `detail` eine LISTE, gar kein `error_key` — obwohl diese
    Datei (Kopf-Docstring) zusagt, `detail` bleibe eine Zeichenkette mit
    Schluessel daneben. Das Frontend zeigte deshalb nur "Unprocessable
    Content" statt einer uebersetzten Meldung (Issue #85, Punkt 3). Der
    Name dieses Tests hat sich mit der Zusicherung geaendert — das ist der
    Punkt, nicht ein Unfall: Ein bestehender Test durfte hier nicht STILL
    weiterlaufen, sondern musste die Umstellung sichtbar machen.
    """
    antwort = client.post("/api/auth/login", json={})
    assert antwort.status_code == 422
    koerper = antwort.json()
    assert isinstance(koerper["detail"], str) and koerper["detail"]
    assert koerper["error_key"] == "err_validation_failed"
    assert "token" in koerper["error_params"]["fields"]
