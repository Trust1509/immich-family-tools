"""Waechter fuer den Vertrag der Protokollmeldungen (Backend <-> i18n.tsx).

VORBILD IST `test_errors.py`: Dort werden die `err_*`-Schluessel zwischen
`backend/errors.py` und `frontend/src/i18n.tsx` abgeglichen. Fuer die
`log_*`-Schluessel des Sync-Protokolls (`SyncLogEntry.message_key` +
`message_params`, siehe `backend/models/match.py`) gab es diesen Abgleich
bisher NICHT — ein neuer, vergessener Schluessel waere still gruen geblieben,
und ein umbenannter Platzhalter in einer Vorlage waere erst beim Nutzer
aufgefallen ("undefined" im Protokolltext, #100).

ZWEI VERTRAEGE, NICHT EINER:

  1. Jeder `message_key`, den das Backend verschickt, hat eine Vorlage in
     `frontend/src/i18n.tsx` (Existenz).
  2. Jede Vorlage liest genau die Platzhalter, die das Backend fuer diesen
     Schluessel mitschickt — nicht mehr, nicht weniger (Form).

WARUM SYNTAXBAUM UND NICHT REGEX (Backend-Seite): Eine Regex wie
`message_key="log_[a-z0-9_]+"` findet nur woertliche Zeichenketten direkt an
der Aufrufstelle. Sobald ein Schluessel ueber eine Konstante oder eine
Nachschlagetabelle gebaut wird — ein voellig normaler naechster Schritt,
sobald zwei Aufrufstellen denselben Schluessel teilen wollen — sieht eine
Regex nichts mehr, und der neue Schluessel bliebe unbewacht, OHNE dass ein
Test rot wird. `backend_log_schluessel()` loest deshalb einfache
Namens- und Nachschlage-Zuweisungen ueber den Syntaxbaum auf (siehe
`test_variable_und_dict_gebaute_schluessel_werden_erfasst`).

DIE VIER `log_`-PRAEFIX-TEXTE, DIE KEINE PROTOKOLLMELDUNGEN SIND: In
`i18n.tsx` stehen auch UI-Texte mit dem Praefix `log_` (`log_subtitle`,
`log_empty`, `log_clear`, `log_clear_confirm`) — Ueberschriften und
Knopftexte der Protokollansicht, keine `message_key`-Werte. Sie werden HIER
nicht durch eine Ausnahmeliste ausgeschlossen, sondern schlicht nie gesehen:
Diese vier Eintraege liegen im `translations`-Objekt (vor der Zeile
"Sync-Log-Meldungen"), waehrend dieser Test ausschliesslich den Block der
Konstante `logMessages` einliest — strukturell getrennt, nicht per Liste.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Optional

WURZEL = Path(__file__).resolve().parents[2]
I18N = WURZEL / "frontend" / "src" / "i18n.tsx"
SYNC_SERVICE = WURZEL / "backend" / "services" / "sync_service.py"

# Eine Menge, deren Groesse < 30 bleibt (Stand 28.09.2026 gemessen: 30
# Schluessel, 37 Sendestellen in sync_service.py), aber weit genug ueber 0,
# um Rot-Beweis 4 zu tragen: Ein Suchlauf, der aus einem kaputten Baum still
# eine leere Menge liefert, waere sonst durch die Mengengleichheit mit einer
# (dann ebenfalls kaputten) Frontend-Erfassung gedeckt und bliebe unbemerkt.
MINDESTZAHL_BACKEND_SCHLUESSEL = 20


class _Symboltabelle(ast.NodeVisitor):
    """Sammelt einfache `NAME = "literal"` und `NAME = {"k": "literal"}`.

    Nur fuer die Aufloesung von `message_key=KONSTANTE` bzw.
    `message_key=TABELLE["k"]` gedacht — keine vollstaendige
    Datenfluss-Analyse. Mehrfach vergebene Namen ueberschreiben sich in der
    Reihenfolge, in der der Baum sie besucht; fuer die kontrollierten Faelle
    dieser Datei (Modul- und Funktionsebene, je ein Name einmal vergeben)
    reicht das.
    """

    def __init__(self) -> None:
        self.strings: dict[str, str] = {}
        self.tabellen: dict[str, dict[object, str]] = {}

    def visit_Assign(self, knoten: ast.Assign) -> None:  # noqa: N802 (ast-API)
        if len(knoten.targets) == 1 and isinstance(knoten.targets[0], ast.Name):
            name = knoten.targets[0].id
            wert = knoten.value
            if isinstance(wert, ast.Constant) and isinstance(wert.value, str):
                self.strings[name] = wert.value
            elif isinstance(wert, ast.Dict):
                tabelle: dict[object, str] = {}
                vollstaendig = True
                for schluessel_knoten, wert_knoten in zip(wert.keys, wert.values):
                    if (
                        isinstance(schluessel_knoten, ast.Constant)
                        and isinstance(wert_knoten, ast.Constant)
                        and isinstance(wert_knoten.value, str)
                    ):
                        tabelle[schluessel_knoten.value] = wert_knoten.value
                    else:
                        vollstaendig = False
                if vollstaendig:
                    self.tabellen[name] = tabelle
        self.generic_visit(knoten)


def _aufgeloester_string(knoten: ast.expr, symbole: _Symboltabelle) -> Optional[str]:
    """Loest einen Ausdruck zu einer literalen Zeichenkette auf, wenn moeglich."""
    if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
        return knoten.value
    if isinstance(knoten, ast.Name):
        return symbole.strings.get(knoten.id)
    if (
        isinstance(knoten, ast.Subscript)
        and isinstance(knoten.value, ast.Name)
        and isinstance(knoten.slice, ast.Constant)
    ):
        tabelle = symbole.tabellen.get(knoten.value.id, {})
        return tabelle.get(knoten.slice.value)
    return None


def _aufgeloeste_paramnamen(knoten: ast.expr, symbole: _Symboltabelle) -> Optional[frozenset[str]]:
    """Loest `message_params=...` zu der Menge seiner Schluesselnamen auf.

    `None` bedeutet "nicht aufloesbar" (z. B. eine Funktion, die ein dict
    erst zur Laufzeit zusammensetzt) und wird von den Aufrufern als eigener
    Zustand behandelt, statt still als "keine Parameter" durchzugehen.
    """
    if isinstance(knoten, ast.Dict):
        namen: set[str] = set()
        for schluessel_knoten in knoten.keys:
            if isinstance(schluessel_knoten, ast.Constant) and isinstance(schluessel_knoten.value, str):
                namen.add(schluessel_knoten.value)
            else:
                return None
        return frozenset(namen)
    if isinstance(knoten, ast.Name) and knoten.id in symbole.tabellen:
        # Eine benannte Tabelle wird hier nicht als Parametermenge erwartet;
        # dieser Zweig bleibt bewusst ungenutzt, siehe Docstring oben.
        return None
    return None


def _datei_log_schluessel(pfad: Path) -> dict[str, list[frozenset[str]]]:
    """Alle `message_key="log_..."`-Fundstellen EINER Datei, noch ungebuendelt.

    Gibt je Schluessel die LISTE der an den einzelnen Aufrufstellen
    gefundenen Parametermengen zurueck (noch nicht auf Widerspruch geprueft),
    damit der Aufrufer mehrere Dateien zusammenfuehren kann, bevor er auf
    Konsistenz prueft.
    """
    baum = ast.parse(pfad.read_text("utf-8"), filename=str(pfad))
    symbole = _Symboltabelle()
    symbole.visit(baum)

    fundstellen: dict[str, list[frozenset[str]]] = {}

    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call):
            continue
        schluessel_wert: Optional[str] = None
        params_knoten: Optional[ast.expr] = None
        hat_params_kw = False
        for kw in knoten.keywords:
            if kw.arg == "message_key":
                schluessel_wert = _aufgeloester_string(kw.value, symbole)
            if kw.arg == "message_params":
                hat_params_kw = True
                params_knoten = kw.value
        if schluessel_wert is None or not schluessel_wert.startswith("log_"):
            continue
        if hat_params_kw:
            aufgeloest = _aufgeloeste_paramnamen(params_knoten, symbole)
            if aufgeloest is None:
                raise AssertionError(
                    f"message_params fuer '{schluessel_wert}' liess sich nicht als "
                    "literales dict auflösen (Zeile "
                    f"{knoten.lineno} in {pfad})."
                )
        else:
            aufgeloest = frozenset()
        fundstellen.setdefault(schluessel_wert, []).append(aufgeloest)

    return fundstellen


# Verzeichnisse, deren Python-Dateien nicht nach `message_key` durchsucht
# werden: Tests selbst (die haben eigene, ausgedachte Schluessel wie die
# Sonden dieser Datei) und Cache-Verzeichnisse.
_AUSGESCHLOSSENE_VERZEICHNISNAMEN = {"tests", "__pycache__"}


def backend_log_schluessel(pfad: Optional[Path] = None) -> dict[str, frozenset[str]]:
    """Jeder `message_key="log_..."`-Wert samt der Namen seiner Parameter.

    OHNE Argument wird der GESAMTE `backend/`-Baum durchsucht (ausser
    `backend/tests/`) — nicht nur `sync_service.py`. Das ist bewusst weiter
    gefasst als der heutige Befund (alle 30 Schluessel liegen heute dort):
    Ein kuenftiger Slice, der einen neuen Protokollschluessel in eine ANDERE
    Datei legt (einen neuen Dienst, einen Router), bleibt damit ohne
    Anpassung an diesem Test erfasst. Mit einem expliziten Pfad (einer
    einzelnen Datei, fuer die Rot-Beweise unten) wird NUR diese Datei
    gelesen.

    Findet auch Schluessel, die ueber eine Konstante oder eine
    Nachschlagetabelle gebaut werden (Syntaxbaum, nicht Regex — siehe
    Moduldocstring). Taucht ein Schluessel an mehreren Aufrufstellen — auch
    ueber mehrere Dateien hinweg — mit UNTERSCHIEDLICHEN Parametermengen auf,
    ist das selbst ein Befund: Die Funktion wirft dann `AssertionError` mit
    dem Schluessel und den widerspruechlichen Mengen, statt eine der beiden
    still zu verschlucken.
    """
    if pfad is not None:
        dateien = [pfad]
    else:
        backend_wurzel = WURZEL / "backend"
        dateien = [
            datei
            for datei in sorted(backend_wurzel.rglob("*.py"))
            if not _AUSGESCHLOSSENE_VERZEICHNISNAMEN & set(datei.relative_to(backend_wurzel).parts[:-1])
        ]

    fundstellen: dict[str, list[frozenset[str]]] = {}
    for datei in dateien:
        for schluessel, mengen in _datei_log_schluessel(datei).items():
            fundstellen.setdefault(schluessel, []).extend(mengen)

    ergebnis: dict[str, frozenset[str]] = {}
    for schluessel, mengen in fundstellen.items():
        eindeutig = set(mengen)
        if len(eindeutig) > 1:
            raise AssertionError(
                f"'{schluessel}' wird an verschiedenen Stellen mit "
                f"unterschiedlichen Parametern verschickt: {sorted(eindeutig, key=sorted)}"
            )
        ergebnis[schluessel] = mengen[0]
    return ergebnis


# ── Frontend-Seite ───────────────────────────────────────────────────────
#
# Hier genuegt eine Regex (siehe Moduldocstring: Rot-Beweis 3 gilt nur der
# Backend-Seite, die Schluessel per Variable oder Tabelle bauen kann). Die
# Vorlagen in `logMessages` sind literale Objekteintraege ohne diese
# Freiheit; die Regex liest nur, was innerhalb der Konstante steht — nicht
# aus der ganzen Datei, siehe `_logmessages_block`.

_EINTRAG_MUSTER = re.compile(r"\n  (log_[a-z0-9_]+): \{(.*?)\n  \},", re.S)
_SPRACHE_MUSTER = re.compile(
    r'\n {4}(de|en|"pt-BR"|"es-ES"): \((?:\)|p\)) =>\s*(.*?)'
    r'(?=\n {4}(?:de|en|"pt-BR"|"es-ES"):|\n  \},|\Z)',
    re.S,
)
_PLATZHALTER_MUSTER = re.compile(r"\bp\.([a-zA-Z_][a-zA-Z0-9_]*)")


def _logmessages_block(text: str) -> str:
    """Schneidet genau den Koerper der Konstante `logMessages` heraus.

    Balancierte Klammerzaehlung statt eines festen Zeilenbereichs, damit der
    Test nicht an Zeilennummern haengt, wenn ein anderer paralleler Slice
    (#97/#98) Zeilen davor einfuegt oder loescht.
    """
    start = text.index("const logMessages")
    klammer_auf = text.index("{", start)
    tiefe = 0
    for index in range(klammer_auf, len(text)):
        zeichen = text[index]
        if zeichen == "{":
            tiefe += 1
        elif zeichen == "}":
            tiefe -= 1
            if tiefe == 0:
                return text[klammer_auf : index + 1]
    raise AssertionError("logMessages-Block in i18n.tsx nicht geschlossen gefunden")


def frontend_log_vorlagen_je_sprache(pfad: Path = I18N) -> dict[str, dict[str, frozenset[str]]]:
    """Fuer jeden `log_*`-Vorlageneintrag: die gelesenen Platzhalter je Sprache.

    Nur Eintraege der Konstante `logMessages` — die vier `log_`-praefigierten
    UI-Texte (`log_subtitle` & Co.) liegen ausserhalb dieses Blocks und
    werden dadurch nie betrachtet (siehe Moduldocstring).
    """
    block = _logmessages_block(pfad.read_text("utf-8"))
    ergebnis: dict[str, dict[str, frozenset[str]]] = {}
    for schluessel, rumpf in _EINTRAG_MUSTER.findall(block):
        je_sprache: dict[str, frozenset[str]] = {}
        for sprache, sprachrumpf in _SPRACHE_MUSTER.findall(rumpf):
            je_sprache[sprache] = frozenset(_PLATZHALTER_MUSTER.findall(sprachrumpf))
        ergebnis[schluessel] = je_sprache
    return ergebnis


def frontend_log_schluessel(pfad: Path = I18N) -> dict[str, frozenset[str]]:
    """Je Schluessel die Platzhaltermenge — vereinigt ueber alle Sprachen.

    Stimmen die Sprachen (siehe `test_jede_vorlage_ist_in_allen_sprachen_gleich_geformt`)
    ohnehin ueberein, ist die Vereinigung gleich jeder Einzelmenge. Weicht
    eine Sprache ab, wird die Vereinigung GROESSER als jede Einzelmenge —
    und macht damit einen Vergleich gegen das Backend eher zu streng als zu
    lasch, nie umgekehrt still gruen.
    """
    je_schluessel = frontend_log_vorlagen_je_sprache(pfad)
    return {
        schluessel: frozenset().union(*sprachmengen.values()) if sprachmengen else frozenset()
        for schluessel, sprachmengen in je_schluessel.items()
    }


def test_backend_erfassung_findet_nicht_still_eine_leere_menge():
    """Rot-Beweis 4: Ein Suchlauf ohne Treffer darf nicht als 'passt' durchgehen.

    Eine leere Backend-Menge waere gegen eine (aus demselben Grund) leere
    Frontend-Menge mengengleich — und der eigentliche Vertragstest daneben
    bliebe gruen, obwohl er nichts mehr prueft. Diese Zusicherung ist davon
    unabhaengig.
    """
    gefunden = backend_log_schluessel()
    assert len(gefunden) >= MINDESTZAHL_BACKEND_SCHLUESSEL, (
        f"nur {len(gefunden)} log_*-Schluessel gefunden, erwartet mindestens "
        f"{MINDESTZAHL_BACKEND_SCHLUESSEL} — Erfassung vermutlich kaputt"
    )


def test_jede_vorlage_ist_in_allen_sprachen_gleich_geformt():
    """Zweiter Teil des Formvertrags: Sprachen einer Vorlage duerfen nicht auseinanderlaufen.

    Eine einzelne umbenannte Sprachvariante (z. B. nur `de` bekommt
    `p.oldName` statt `p.old_name`) ist noch keine Mengendifferenz zum
    Backend, solange eine ANDERE Sprache den richtigen Namen behaelt — die
    Vereinigung in `frontend_log_schluessel()` wuerde das verdecken. Dieser
    Test prueft deshalb zusaetzlich JEDE Sprache gegen jede andere, nicht nur
    das Ergebnis gegen das Backend.
    """
    je_schluessel = frontend_log_vorlagen_je_sprache()
    abweichungen = {}
    for schluessel, sprachmengen in je_schluessel.items():
        eindeutig = set(sprachmengen.values())
        if len(eindeutig) > 1:
            abweichungen[schluessel] = sprachmengen
    assert abweichungen == {}, f"Sprachen einer Vorlage lesen unterschiedliche Platzhalter: {abweichungen}"


def test_schluesselmengen_von_backend_und_frontend_sind_gleich():
    """Erster Teil des Vertrags: jeder gesendete Schluessel hat eine Vorlage.

    Analog zu `test_errors.py::test_schluesselmengen_von_backend_und_frontend_sind_gleich`,
    nur fuer `message_key` statt `error_key`.
    """
    hinten = set(backend_log_schluessel())
    vorne = set(frontend_log_schluessel())
    nur_backend = sorted(hinten - vorne)
    nur_frontend = sorted(vorne - hinten)
    assert nur_backend == [], f"ohne Vorlage im Frontend: {nur_backend}"
    assert nur_frontend == [], f"Vorlage ohne Sendestelle im Backend: {nur_frontend}"


def test_platzhalter_je_schluessel_stimmen_mit_dem_backend_ueberein():
    """Zweiter Teil des Vertrags: die Vorlage liest genau die geschickten Platzhalter.

    Setzt voraus, dass die Schluesselmengen bereits gleich sind (der Test
    davor) — sonst waere ein KeyError hier nur ein Folgefehler des ersten
    Befunds.
    """
    hinten = backend_log_schluessel()
    vorne = frontend_log_schluessel()
    gemeinsam = set(hinten) & set(vorne)
    abweichungen = {
        schluessel: {"backend": sorted(hinten[schluessel]), "frontend": sorted(vorne[schluessel])}
        for schluessel in sorted(gemeinsam)
        if hinten[schluessel] != vorne[schluessel]
    }
    assert abweichungen == {}, f"Platzhalter weichen ab: {abweichungen}"


def test_variable_und_dict_gebaute_schluessel_werden_erfasst(tmp_path):
    """Rot-Beweis 3: ein per Konstante/Tabelle gebauter Schluessel bleibt sichtbar.

    Baut eine Kopie von `sync_service.py` mit zwei zusaetzlichen, erfundenen
    Aufrufstellen — eine ueber eine Namenskonstante, eine ueber eine
    Nachschlagetabelle — und prueft, dass `backend_log_schluessel()` beide
    samt ihrer Parameter findet. Eine reine Regex auf
    `message_key="log_..."` faende hier NICHTS, weil an der Aufrufstelle gar
    keine woertliche Zeichenkette mehr steht — das ist genau der
    Unterschied, den dieser Test belegt.

    Mutation an einer KOPIE unter `tmp_path`, der Arbeitsbaum bleibt
    unberuehrt.
    """
    original = SYNC_SERVICE.read_text("utf-8")
    sonde = original + (
        "\n\n"
        "# --- ab hier: Testsonde fuer Rot-Beweis 3, keine echte Anwendungslogik ---\n"
        "_SONDE_SCHLUESSEL = \"log_ast_sonde_variable\"\n"
        "_SONDE_TABELLE = {\"fehlgeschlagen\": \"log_ast_sonde_tabelle\"}\n"
        "\n"
        "\n"
        "def _ast_sonde_ueber_variable():\n"
        "    return SyncLogEntry(\n"
        "        id=\"sonde\", timestamp=\"sonde\", action=\"sonde\", details=\"sonde\",\n"
        "        status=\"success\",\n"
        "        message_key=_SONDE_SCHLUESSEL,\n"
        "        message_params={\"eins\": 1, \"zwei\": 2},\n"
        "    )\n"
        "\n"
        "\n"
        "def _ast_sonde_ueber_tabelle():\n"
        "    return SyncLogEntry(\n"
        "        id=\"sonde\", timestamp=\"sonde\", action=\"sonde\", details=\"sonde\",\n"
        "        status=\"error\",\n"
        "        message_key=_SONDE_TABELLE[\"fehlgeschlagen\"],\n"
        "        message_params={},\n"
        "    )\n"
    )
    sonden_datei = tmp_path / "sync_service_sonde.py"
    sonden_datei.write_text(sonde, "utf-8")

    gefunden = backend_log_schluessel(sonden_datei)

    assert gefunden["log_ast_sonde_variable"] == frozenset({"eins", "zwei"})
    assert gefunden["log_ast_sonde_tabelle"] == frozenset()

    # Gegenprobe: Die naive Regex-Form, die dieser Waechter bewusst NICHT
    # verwendet, findet die beiden neuen Schluessel tatsaechlich nicht —
    # genau der Unterschied, den die AST-Aufloesung schliesst.
    naive_regex = re.compile(r'message_key="(log_[a-z0-9_]+)"')
    regex_treffer = set(naive_regex.findall(sonde))
    assert "log_ast_sonde_variable" not in regex_treffer
    assert "log_ast_sonde_tabelle" not in regex_treffer


def test_ein_neuer_schluessel_ohne_vorlage_faellt_auf(tmp_path):
    """Rot-Beweis 1: ein Schluessel ohne Gegenstueck im Frontend wird gefunden.

    Kopie von `sync_service.py` mit einer zusaetzlichen Sendestelle fuer
    einen Schluessel, den es in `i18n.tsx` nicht gibt. Der eigentliche
    Vertragstest (`test_schluesselmengen_von_backend_und_frontend_sind_gleich`)
    wuerde auf dieser Kopie rot laufen; hier wird das ohne Veraenderung am
    echten Arbeitsbaum direkt an der Mengendifferenz gezeigt.
    """
    original = SYNC_SERVICE.read_text("utf-8")
    sonde = original + (
        "\n\n"
        "# --- ab hier: Testsonde fuer Rot-Beweis 1 ---\n"
        "def _rotbeweis_neuer_schluessel_ohne_vorlage():\n"
        "    return SyncLogEntry(\n"
        "        id=\"sonde\", timestamp=\"sonde\", action=\"sonde\", details=\"sonde\",\n"
        "        status=\"error\",\n"
        "        message_key=\"log_voellig_neu_und_unuebersetzt\",\n"
        "        message_params={\"wert\": 1},\n"
        "    )\n"
    )
    sonden_datei = tmp_path / "sync_service_sonde.py"
    sonden_datei.write_text(sonde, "utf-8")

    hinten = set(backend_log_schluessel(sonden_datei))
    vorne = set(frontend_log_schluessel())
    nur_backend = hinten - vorne

    assert "log_voellig_neu_und_unuebersetzt" in nur_backend


def test_ein_umbenannter_platzhalter_faellt_auf(tmp_path):
    """Rot-Beweis 2: ein in EINER Sprache umbenannter Platzhalter wird gefunden.

    Kopie von `i18n.tsx`, in der genau EIN Vorkommen von `p.old_name`
    (innerhalb `log_album_renamed`, deutsche Vorlage) zu `p.oldName`
    umbenannt wird — die drei anderen Sprachen bleiben unveraendert. Eine
    reine Vereinigung ueber alle Sprachen wuerde das verdecken (die
    Vereinigung enthielte weiterhin `old_name`, weil `en`/`pt-BR`/`es-ES` es
    noch lesen); der Sprachvergleich in
    `test_jede_vorlage_ist_in_allen_sprachen_gleich_geformt` deckt es trotzdem
    auf, weil er jede Sprache einzeln vergleicht.
    """
    original = I18N.read_text("utf-8")
    ziel = "de: (p) => `Album '${p.old_name}' in '${p.new_name}' umbenannt`,"
    ersatz = "de: (p) => `Album '${p.oldName}' in '${p.new_name}' umbenannt`,"
    assert original.count(ziel) == 1, "erwartete Fundstelle in i18n.tsx nicht (mehr) vorhanden"
    mutiert = original.replace(ziel, ersatz)

    sonden_datei = tmp_path / "i18n_sonde.tsx"
    sonden_datei.write_text(mutiert, "utf-8")

    je_sprache = frontend_log_vorlagen_je_sprache(sonden_datei)
    sprachmengen = je_sprache["log_album_renamed"]

    assert sprachmengen["de"] == frozenset({"oldName", "new_name"})
    assert sprachmengen["en"] == frozenset({"old_name", "new_name"})
    assert len(set(sprachmengen.values())) > 1, "die Mutation haette die Sprachen auseinanderlaufen lassen muessen"
