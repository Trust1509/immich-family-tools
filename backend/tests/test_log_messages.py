"""Fail-closed-Waechter fuer den Vertrag der Protokollmeldungen.

NACHARBEIT 1 — WARUM DIE ERSTE FASSUNG NICHT REICHTE
-------------------------------------------------------------
Die erste Fassung verglich zwei UNABHAENGIGE Erfassungen (Backend per
Syntaxbaum, Frontend per Regex auf den Quelltext) direkt gegeneinander. Der
Hauptagent hat reproduziert, dass eine deutsche Vorlage von
`log_album_created`, umgeschrieben zu `(q) => ... ${q.acount} ...`, bei allen
damaligen Tests gruen blieb, das Protokoll zeigte "undefined". Ursache: Eine
Regex auf Quelltext sieht nur, dass IRGENDEIN `p.<name>` vorkommt, nicht ob es
der RICHTIGE Name ist, wenn der Parameter selbst anders heisst (`q` statt
`p`), und sie sieht Vorlagen mit Destrukturierung, `function`-Schreibweise
oder Kommentaren (ein auskommentierter Eintrag zaehlte als vorhanden) gar
nicht oder falsch.

Zwei Aenderungen beheben das strukturell statt durch mehr Muster: (1) ein
VERTRAG als eigene Datei (`frontend/src/logMessages.contract.json`,
Schluessel -> sortierte Parameterliste), gegen den beide Seiten pruefen; (2)
diese Datei liest fail-closed per Syntaxbaum statt per Symboltabelle. Die
Frontend-Haelfte (`frontend/src/logMessages.contract.test.ts`) ruft jede
Vorlage zur LAUFZEIT ueber einen `Proxy` mit mehreren Sondenwerten auf.

NACHARBEIT 2 — DREI LUECKEN, DIE DER BLINDPRUEFER AN NACHARBEIT 1 GEMESSEN HAT
-------------------------------------------------------------------------------
1. Die benannte Ausnahme war ueber (Datei, Funktionsname) allein zu weit
   gefasst: `entry.setdefault("message_key", ...)` VOR dem `**entry`-Aufruf,
   eine zweite Klasse mit gleichnamiger Methode oder ein zweiter `**`-Aufruf
   in derselben Funktion blieben unentdeckt. Der Schluessel ist jetzt
   (Datei, Klasse-oder-keine, Funktion), verlangt GENAU EINEN Treffer — einen
   Aufruf mit AUSSCHLIESSLICH der `**`-Erweiterung, keinen weiteren
   Schluesselwoertern — und jedes literale Vorkommen von `"message_key"`
   oder `"message_params"` in derselben Funktion bleibt trotzdem ein
   Verstoss (siehe Punkt 3).
2. Konstruktionen ueber einen Modulnamen (`mm.SyncLogEntry(...)`) oder eine
   Unterklasse (`class X(SyncLogEntry): ...`) wurden nicht erkannt, weil nur
   der nackte Name `SyncLogEntry` geprueft wurde. Erkannt wird jetzt der
   RECHTE Bezeichner eines Aufrufziels (bei `mm.SyncLogEntry` also
   `SyncLogEntry`, unabhaengig vom Modulnamen `mm`), zusammengenommen mit
   einer Menge aller (transitiven) Unterklassennamen von `SyncLogEntry` im
   ganzen `backend/`-Baum sowie lokalen Importe-Aliasen (`from models.match
   import SyncLogEntry as X`).
3. Zugriffe NACH der Konstruktion (`setattr`, `+=`, `.pop(...)`,
   `.update(...)`, Subskript-Zuweisung) wurden nur als Sonderfall einer
   direkten Zuweisung erkannt. Jetzt gilt EINHEITLICH: JEDER
   `ast.Attribute`-Zugriff mit dem Namen `message_key` oder `message_params`
   ist ein Verstoss (deckt Lesen, Schreiben, `+=`, `.pop()`, `.update()` und
   Subskript-Ziele — die Attribut-Basis ist in jedem Fall dasselbe
   Attribut-Token), UND JEDES literale String-Vorkommen von `"message_key"`
   oder `"message_params"` irgendwo im Baum (deckt `setattr`, `getattr`,
   `hasattr`, `entry.setdefault(...)`, ein dict-Literal wie
   `model_copy(update={"message_key": ...})`) ist ein Verstoss. `partial(...)`
   und `X.model_validate(...)`/`X.model_validate_json(...)` auf
   SyncLogEntry/einer Unterklasse sind kategorisch verboten (spaetere Bindung
   bzw. beliebige Rohdaten sind statisch nicht pruefbar). KEINE
   Pydantic-Aenderung am Produktionsmodell in dieser Runde — eine
   Laufzeitpruefung am Modell waere denkbar, aendert aber
   `backend/models/match.py` selbst und war damit fuer diese Runde
   ausgeschlossen.

NACHARBEIT 3 (#115, Erstrunde) — RICHTUNG STATT BLANKO-VERBOT, VERWORFEN
-------------------------------------------------------------------------------
Der Blindpruefer der Nachlese zu #94 hatte gemessen: Nacharbeit 2 verbot JEDEN
Attribut-Zugriff und JEDES Literal, auch berechtigtes LESEN. Die Erstrunde zu
#115 waehlte daraufhin die ERSTE der beiden im Issue genannten Richtungen:
JEDER lesende (`ctx=Load`) Attributzugriff wurde pauschal erlaubt, und vier
Funktions-/Methodennamen (`getattr`, `hasattr`, `field_validator`,
`model_dump`/`model_dump_json`) machten ein literales Vorkommen pauschal zu
einer erlaubten Lese-Form.

Das Panel (Blind- und Gegenpruefer, unabhaengig) hat daran ZWEI BLOCKER
gemessen, die diese Fassung wieder verworfen haben:

BLOCKER 1 — Schreiben ueber eine GELESENE Referenz war unentdeckt. Weil JEDER
lesende Attributzugriff pauschal erlaubt war, entzog sich alles, was zuerst
liest und danach mutiert, der Pruefung: `getattr(e, "message_params").pop(...)`
(die Basis ist ein Aufrufergebnis, kein `ast.Attribute`-Knoten, den die
Mutationsmethoden-Pruefung kennt), `p = e.message_params; p.pop(...)` (die
Zwischenvariable traegt keine Spur der Herkunft), `(p := e.message_params)[...]
= ...` (Walrus), `dict.update(e.message_params, ...)` /
`operator.setitem(e.message_params, ...)` (die gelesene Referenz wandert als
Argument in eine fremde Funktion), `e.message_params.__ior__(...)` /
`.__init__(...)` (Dunder-Aufrufe ausserhalb der bekannten Methodenliste),
`(e.message_params or {}).update(...)` (die Basis steckt in einem `BoolOp`),
`u = e.message_params.update; u(...)` (die gebundene Methode selbst wird
weitergereicht). Laufzeit gemessen: der Log-Eintrag erreichte das Frontend mit
falschen Parametern ("... von 'undefined' ...").

BLOCKER 2 — Die vier pauschal erlaubten Lese-Formen waren selbst keine reinen
Lese-Pfade bzw. liessen sich umgehen: `@field_validator("message_key")`
SCHREIBT (der Rueckgabewert der validierenden Funktion wird der neue
Feldwert) — gemessen: `message_key` wurde zu einem unuebersetzten Schluessel.
`model_dump(exclude={"message_params"})` erzeugt einen Log-Eintrag OHNE
Parameter, der so ans Frontend geht ("... von 'undefined' ..."). Und weil die
Erkennung rein NAMENSBASIERT war (der bare Name `getattr`/`field_validator`
im Aufruf, ohne zu pruefen, ob dieser Name im aktuellen Sichtbereich
ueberhaupt noch auf das Original zeigt), schaltet eine lokal umdefinierte
Funktion gleichen Namens (`def _p(e, getattr=setattr): ...`) ein Literal frei,
das in Wahrheit ueber `setattr` SCHREIBT.

NACHARBEIT 4 (#115, Nacharbeit 1) — DIE ZWEITE RICHTUNG: BENANNTE LESE-AUSNAHME
-------------------------------------------------------------------------------
Diese Fassung verwirft die pauschale Lese-Erlaubnis vollstaendig und stellt
die Strenge von Nacharbeit 2 (Commit `c8e2458`) wieder her: JEDER
`ast.Attribute`-Zugriff auf `.message_key`/`.message_params` — ob lesend oder
schreibend — und JEDES literale Vorkommen der Zeichenketten `"message_key"`/
`"message_params"` im Nicht-Test-Backend sind wieder kategorisch verboten. Es
gibt dafuer GENAU EINEN Ausweg (die zweite im Issue #115 genannte Richtung),
und er gilt NUR fuer lesende Attributzugriffe, nie fuer Literale:

  `_BENANNTE_LESE_AUSNAHMEN: dict[(Datei, Klasse-oder-None, Funktion), Begruendung]`

Ein lesender Zugriff (`ctx=Load`) auf `.message_key`/`.message_params` ist NUR
dann erlaubt, wenn BEIDES zutrifft: (a) der Knoten selbst traegt eine
STRUKTURELL BEWEISBARE Lese-Form — heute genau eine erkannt: Operand eines
`ast.Compare` (z. B. `e.message_key == schluessel`, das Beispiel aus #115,
Punkt 1) —, UND (b) die Stelle (Datei, Klasse, Funktion) steht in der Liste.
Dieselbe Form an einer NICHT gelisteten Stelle bleibt verboten; eine gelistete
Stelle, an der die Form nicht (mehr) vorkommt, ist eine VERALTETE Ausnahme und
damit selbst ein Verstoss (Meldung "veraltete Lese-Ausnahme"). Anders als bei
der bestehenden Schreib-Ausnahme (`_BENANNTE_AUSNAHMEN`, unveraendert) wird
hier keine Obergrenze von genau einem Treffer verlangt — mehrere beweisbare
Lesestellen in derselben benannten Funktion sind gleich sicher, weil jede fuer
sich strukturell geprueft wird; nur NULL Treffer (die Ausnahme ist veraltet)
ist ein Fehler. **Heute ist diese Liste leer (0 berechtigte Nutzungen,
gemessen: kein Produktionscode liest `.message_key`/`.message_params` per
Attributzugriff).**

Diese EINE Aenderung schliesst BEIDE Blocker der Erstrunde, ohne fuer jede in
BLOCKER 1 aufgezaehlte Form ein eigenes Muster zu brauchen: Jede dort
genannte Form referenziert `.message_params` zwingend entweder ueber einen
`ast.Attribute`-Knoten (Load) — der jetzt wieder faellt, unabhaengig davon, in
welchem Ausdruck er steckt (Walrus, `BoolOp`, Funktionsargument, gebundene
Methode) — oder ueber die literale Zeichenkette (`getattr`, `dict.update`
braucht sie nicht als String, faellt aber ueber die Attribut-Basis).
`field_validator`/`model_dump(exclude=...)` verlieren ihren Sonderstatus
ersatzlos (BLOCKER 2, Punkt 1+2); die Namens-Shadowing-Luecke (BLOCKER 2,
Punkt 3) verschwindet, weil es keine namensbasierte Sonderbehandlung mehr
gibt, die sich shadowen liesse.

Restformen (Nacharbeit 1, #115 — gefangen ohne Fehlalarm gegen den heutigen
Baum, siehe Docstring-Abschnitt "WAS DIESER WAECHTER ERFASST"):
  - `type(vorlage)(**roh)` / `vorlage.__class__(**roh)` — beide rufen das
    Ergebnis einer dynamischen Typ-Ermittlung als Konstruktor auf. Im
    heutigen Backend gibt es GENAU EINEN `type(...)`-Aufruf
    (`type(exc).__name__` in `face_matcher.py`, kein Aufruf des Ergebnisses)
    und KEINEN `.__class__(...)`-Aufruf (beides gemessen) — das Fangen ist
    also ohne Fehlalarm moeglich. Eine kuenftige, unbeteiligte Nutzung dieses
    Musters wuerde neu bewertet werden muessen; dasselbe Risiko tragen die
    bereits bestehenden kategorischen Sperren (`model_validate`, `partial`).
  - `SyncLogEntry.construct(**roh)` (Pydantic-v1-Altform von
    `model_construct`), `.parse_obj(roh)` (Pydantic-v1-Altform von
    `model_validate`), `.model_validate_strings(roh)` — dieselbe
    kategorische Sperre wie die bestehenden drei, um dieselbe Begruendung
    erweitert.
  - `dict(message_params=..., ...)` — ein `dict(...)`-Aufruf mit dem
    Schluesselwort `message_params`/`message_key` ist verboten, unabhaengig
    vom Kontext. Deckt `model_copy(update=dict(message_params=...))` ab, das
    der reinen Literal-Suche entginge (der Schluesselwortname eines
    `ast.keyword` ist ein Python-String auf dem Knoten, kein `ast.Constant`).
  - `TypeAdapter(list[SyncLogEntry]).validate_python(...)` (Huelle ueber
    `Subscript`), `TypeAdapter(SyncLogEntry).validate_strings(...)`,
    `ta = TypeAdapter(SyncLogEntry); ta.validate_python(...)` (Variablen-
    Alias), `from pydantic import TypeAdapter as TA` (Import-Alias) — je eine
    gezielte Erweiterung der bestehenden, eng gefassten TypeAdapter-Pruefung.
  - Klassen-Aliase ueber einen modulqualifizierten Wert (`_E = mm.SyncLogEntry`),
    eine Annotation (`_E: type = SyncLogEntry`), eine Tupel-Zuweisung
    (`_E, _x = SyncLogEntry, 1`) und eine Kettenzuweisung
    (`_A = _B = SyncLogEntry`) — `_sammle_aliase` (Ersatz fuer die alte
    `_sammle_lokale_aliase`) deckt jetzt alle vier Formen ab, UND trennt dabei
    nach Geltungsbereich (siehe naechster Punkt).
  - `_pp = partial` (Namens-Alias auf den bereits importierten `partial`,
    nicht nur einen Importalias) — `_sammle_partial_aliase` erweitert.

KLEIN, behoben (Nacharbeit 1, #115) — Aliase OHNE Geltungsbereich: Die alte
`_sammle_lokale_aliase` sammelte Zuweisungs-Aliase DATEIWEIT, ohne Funktions-
grenzen zu achten. Gemessen (Gegenpruefer-Sonde "Fehlalarm Scope"): `k =
SyncLogEntry` in einer Funktion `_f1` (dort nie aufgerufen) haette `k(**roh)`
in einer VOELLIG ANDEREN Funktion `_f2` — wo `k` lokal `dict` bedeutet und
`dict(**roh)` mit `SyncLogEntry` nichts zu tun hat — faelschlich als
Konstruktion ohne `message_key` gemeldet. `_sammle_aliase` trennt jetzt nach
Geltungsbereich: eine Zuweisung auf Modulebene ist (wie ein echter Python-Name)
ueberall im Baum sichtbar, eine Zuweisung INNERHALB einer Funktion nur dort.

Restform, die weiterhin BEWUSST NICHT gefangen wird (im Docstring benannt
statt stillschweigend uebersehen — siehe "WAS ER NICHT ERFASST" unten):
  - `model_copy(update=roh)` ohne woertliches Dict — ob `roh` `message_key`/
    `message_params` beruehrt, haengt vom LAUFZEITWERT von `roh` ab; ein
    kategorisches Verbot jedes `.model_copy(update=<Variable>)` im ganzen
    Backend traefe garantiert auch harmlose Aktualisierungen voellig anderer
    Felder auf voellig anderen Pydantic-Modellen (Fehlalarm-Garantie).
  - ein "Huellmodell" mit einem `list[SyncLogEntry]`-Feld, aus Rohdaten
    gebaut (`Huelle.model_validate({"eintraege": roh})`) — die eigentliche
    SyncLogEntry-Konstruktion passiert dann tief in Pydantics eigener
    Validierung, nie als eigener, textuell sichtbarer `SyncLogEntry(...)`-
    oder `TypeAdapter(...)`-Aufruf. Das zu erfassen braucht Typfluss ueber
    Feld-Deklarationen hinweg, nicht nur einen Datei-fuer-Datei-Syntaxbaum-Scan.
  - `type(vorlage)(**roh)`, dessen `vorlage`-Variable erst zur LAUFZEIT einer
    fremden, unbeteiligten Klasse entstammt — die Erkennung oben ist rein
    SYNTAKTISCH (jeder `type(x)(...)`-Aufruf gilt als Konstruktion), nicht
    typgebunden.

WAS DIESER WAECHTER ERFASST (gemessen, Stand dieser Runde):
  - jede Konstruktion von `SyncLogEntry` oder einer (transitiven)
    Unterklasse, ob als nackter Name, ueber einen Modulnamen, einen lokalen
    Importalias, eine Zuweisungs-Alias (Name, Attribut, Tupel, Kette,
    Annotation — je nach Geltungsbereich), `type(vorlage)(...)` oder
    `vorlage.__class__(...)`;
  - fehlendes, nicht-woertliches oder falsch geformtes `message_key`/
    `message_params` an einer solchen Konstruktion;
  - JEDEN Attribut-Zugriff (`ctx` `Store`, `Del` ODER `Load`) auf
    `.message_key`/`.message_params`, AUSSER einem `Load`-Zugriff, der (a)
    Operand eines Vergleichs ist UND (b) an einer Stelle aus
    `_BENANNTE_LESE_AUSNAHMEN` steht; eine Subskript-Zuweisung/-Loeschung auf
    `.message_params[...]` sowie jede Mutationsmethode
    (`.pop()`/`.update()`/`.clear()`/`.popitem()`/`.setdefault()`/
    `.__setitem__()`/`.__delitem__()`/`.__ior__()`/`.__init__()`) auf
    `.message_params`, wenn die Basis ein direkter Attributzugriff ist (die
    generische Load-Sperre oben faengt jede indirekte Form zusaetzlich);
  - JEDES literale Vorkommen der Zeichenketten `"message_key"`/
    `"message_params"` — ausnahmslos, ausser innerhalb der einen benannten
    `**`-Schreib-Ausnahme;
  - `functools.partial(SyncLogEntry, ...)` (auch unter Import- oder
    Namens-Alias), `SyncLogEntry.model_validate(...)`/`.model_validate_json(...)`/
    `.model_construct(...)`/`.construct(...)`/`.parse_obj(...)`/
    `.model_validate_strings(...)` (kategorisch, unabhaengig vom Inhalt);
  - `TypeAdapter(SyncLogEntry)`/`TypeAdapter(list[SyncLogEntry])` (auch unter
    Import- oder Variablen-Alias) `.validate_python(...)`/`.validate_json(...)`/
    `.validate_strings(...)`;
  - `dict(message_params=..., ...)`/`dict(message_key=..., ...)`.

WAS ER NICHT ERFASST (bekannte Restformen, keine Vollstaendigkeit behauptet):
  - `getattr(x, "message_" + "key")` oder eine andere zur Laufzeit erst
    zusammengesetzte Zeichenkette (kein woertlicher `ast.Constant` mehr);
  - Reflection ueber `__dict__`/`vars(x)` ohne den Namen als Zeichenkette;
  - ein zweites, semantisch anderes Attribut, das zufaellig auch
    `message_key` heisst, an einer voellig anderen Klasse (der Scan ist
    NAMENSBASIERT auf dem ganzen Baum, nicht typgebunden);
  - `model_copy(update=roh)` ohne woertliches Dict und ein Huellmodell mit
    `list[SyncLogEntry]`-Feld — Begruendung siehe "NACHARBEIT 4" oben;
  - eine benannte Lese-Ausnahme deckt AUSSCHLIESSLICH die eine erkannte
    beweisbare Form (Vergleichsoperand) an der genannten Stelle ab — ein
    zweiter, andersartiger lesender Zugriff (z. B. ein blosses `print(...)`)
    an DERSELBEN Stelle bleibt verboten, das ist kein Freibrief fuer die
    ganze Funktion.
"""

from __future__ import annotations

import ast
import json
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional

import pytest

WURZEL = Path(__file__).resolve().parents[2]
BACKEND_DIR = WURZEL / "backend"
VERTRAG_PFAD = WURZEL / "frontend" / "src" / "logMessages.contract.json"

# Modul-Objekt dieser Datei selbst -- fuer `monkeypatch.setattr(...)` auf die
# beiden modulweiten Ausnahme-Dicts unten, unabhaengig davon, unter welchem
# Namen pytest dieses Modul importiert (rootdir-abhaengig).
_DIESES_MODUL = sys.modules[__name__]

# Verzeichnisse, deren Python-Dateien nicht durchsucht werden: Tests selbst
# (eigene, ausgedachte Schluessel wie die Sonden dieser Datei) und
# Cache-Verzeichnisse.
_AUSGESCHLOSSENE_VERZEICHNISNAMEN = {"tests", "__pycache__"}

# Die EINE benannte Ausnahme vom Fail-Closed-Vertrag fuer SCHREIBEN: (Datei
# relativ zur Repo-Wurzel, Klassenname oder None fuer Modulebene,
# Funktionsname) -> Begruendung. Der Schluessel traegt seit Nacharbeit 2 auch
# die Klasse, damit eine ZWEITE Klasse mit gleichnamiger Methode NICHT
# versehentlich mitgemeint ist. Verlangt wird zudem GENAU EIN Treffer mit
# AUSSCHLIESSLICH der `**`-Erweiterung (siehe `_SyncLogPruefer.visit_Call`) —
# ein zweiter `**`-Aufruf in derselben Funktion oder gar keiner sind beide ein
# Verstoss (siehe `backend_sendestellen`).
_BENANNTE_AUSNAHMEN: dict[tuple[str, Optional[str], str], str] = {
    ("backend/services/config_store.py", "ConfigStore", "_build_log_entries"): (
        "SyncLogEntry(**entry) baut ein Modell aus einem bereits in "
        "accounts.json gespeicherten Protokolleintrag wieder auf "
        "(Alt-Format-Vertraeglichkeit) - keine Stelle, die einen NEUEN "
        "message_key waehlt."
    ),
}

# Die benannte Ausnahme fuer LESEN (Nacharbeit 1, #115) — siehe Docstring,
# "NACHARBEIT 4". Anders als oben wird KEINE Obergrenze verlangt (mehrere
# beweisbare Lesestellen in derselben Funktion sind gleich sicher); nur NULL
# Treffer machen einen Eintrag zu einer veralteten Ausnahme. Heute leer.
_BENANNTE_LESE_AUSNAHMEN: dict[tuple[str, Optional[str], str], str] = {}

_LITERALE_NAMEN = ("message_key", "message_params")

# Methoden, die ein Dict-Attribut IN-PLACE veraendern, obwohl der Zugriff auf
# das Attribut selbst (um die Methode zu finden) syntaktisch ein Lesen ist
# (`ctx=Load`). `visit_Call` prueft diese separat von `visit_Attribute`, wenn
# die Basis ein DIREKTER Attributzugriff ist (fuer eine bessere, spezifische
# Meldung); jede INDIREKTE Form (ueber `getattr`, eine Zwischenvariable, ...)
# faengt die generische Load-Sperre in `visit_Attribute` zusaetzlich.
_MUTIERENDE_DICT_METHODEN = frozenset(
    {"pop", "update", "clear", "popitem", "setdefault", "__setitem__", "__delitem__", "__ior__", "__init__"}
)

# Kategorisch verbotene Deserialisierungs-/Konstruktions-Methoden auf
# SyncLogEntry/einer Unterklasse — beliebige Rohdaten sind statisch nicht
# pruefbar (siehe Docstring, "NACHARBEIT 2" und "NACHARBEIT 4").
_KATEGORISCH_VERBOTENE_METHODEN = frozenset(
    {
        "model_validate",
        "model_validate_json",
        "model_construct",
        "construct",
        "parse_obj",
        "model_validate_strings",
    }
)

# TypeAdapter-Methoden, die aus beliebigen Rohdaten (ohne pruefbare
# Schluesselwort-Form) ein Modell bauen.
_TYPE_ADAPTER_METHODEN = frozenset({"validate_python", "validate_json", "validate_strings"})


def lade_vertrag() -> dict[str, list[str]]:
    return json.loads(VERTRAG_PFAD.read_text("utf-8"))


def _rechter_bezeichner(knoten: Optional[ast.expr]) -> Optional[str]:
    """Der 'zustaendige' Name eines Aufrufziels: bei `SyncLogEntry(...)` das
    ist `SyncLogEntry`, bei `mm.SyncLogEntry(...)` ebenfalls `SyncLogEntry`
    (das Modul `mm` links davon ist fuer die Frage 'was wird gebaut'
    unerheblich)."""
    if isinstance(knoten, ast.Name):
        return knoten.id
    if isinstance(knoten, ast.Attribute):
        return knoten.attr
    return None


def _rechter_bezeichner_tief(knoten: Optional[ast.expr]) -> Optional[str]:
    """Wie `_rechter_bezeichner`, zusaetzlich durch einen `Subscript`
    hindurch: deckt `list[SyncLogEntry]`/`List[SyncLogEntry]` als
    TypeAdapter-Huelle ab (#115, Nacharbeit 1) — die Klasse steht dann im
    `slice`, nicht am Aufrufziel selbst."""
    if isinstance(knoten, ast.Subscript):
        return _rechter_bezeichner_tief(knoten.slice)
    return _rechter_bezeichner(knoten)


def _sammle_sync_log_entry_namen(baeume: dict[Path, ast.Module]) -> set[str]:
    """Alle (transitiven) Unterklassennamen von `SyncLogEntry`, ueber ALLE
    Dateien hinweg (eine Unterklasse kann in einer anderen Datei stehen als
    ihre Basis). Fixpunkt-Iteration, weil eine Unterklasse ihrerseits
    Basis einer weiteren sein kann."""
    namen = {"SyncLogEntry"}
    geaendert = True
    while geaendert:
        geaendert = False
        for baum in baeume.values():
            for knoten in ast.walk(baum):
                if isinstance(knoten, ast.ClassDef) and knoten.name not in namen:
                    for basis in knoten.bases:
                        if _rechter_bezeichner(basis) in namen:
                            namen.add(knoten.name)
                            geaendert = True
                            break
    return namen


class _AliasSammler(ast.NodeVisitor):
    """Sammelt rohe Namens-Alias-Zuweisungen (`Y = X`, `Y: T = X`, Tupel- und
    Kettenzuweisungen), GETRENNT NACH GELTUNGSBEREICH (#115, Nacharbeit 1,
    KLEIN-Fund "Aliase dateiweit ohne Geltungsbereich"): eine Zuweisung auf
    Modulebene ist im ganzen Baum sichtbar, eine Zuweisung INNERHALB einer
    Funktion nur dort — genau wie ein echter Python-Name. Ohne diese Trennung
    wuerde `k = SyncLogEntry` in einer Funktion `k(**roh)` in einer VOELLIG
    ANDEREN Funktion faelschlich als Konstruktion markieren (gemessen,
    Gegenpruefer-Sonde "Fehlalarm Scope")."""

    def __init__(self) -> None:
        self._funktionsstapel: list[str] = ["<Modul>"]
        self._klassenstapel: list[Optional[str]] = [None]
        # (Klasse-oder-None, Funktion) -> Liste roher (Zielname, Quellausdruck)
        self.roh: dict[tuple[Optional[str], str], list[tuple[str, ast.expr]]] = {}

    def _schluessel(self) -> tuple[Optional[str], str]:
        return (self._klassenstapel[-1], self._funktionsstapel[-1])

    def visit_ClassDef(self, knoten: ast.ClassDef) -> None:  # noqa: N802
        self._klassenstapel.append(knoten.name)
        self.generic_visit(knoten)
        self._klassenstapel.pop()

    def visit_FunctionDef(self, knoten: ast.FunctionDef) -> None:  # noqa: N802
        self._funktionsstapel.append(knoten.name)
        self.generic_visit(knoten)
        self._funktionsstapel.pop()

    def visit_AsyncFunctionDef(self, knoten: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._funktionsstapel.append(knoten.name)
        self.generic_visit(knoten)
        self._funktionsstapel.pop()

    def _merke(self, ziel: str, wert: ast.expr) -> None:
        self.roh.setdefault(self._schluessel(), []).append((ziel, wert))

    def visit_Assign(self, knoten: ast.Assign) -> None:  # noqa: N802
        # Kettenzuweisung (`_A = _B = SyncLogEntry`): ALLE Ziele bekommen
        # denselben Wert. Tupel-/Listenzuweisung (`_E, _x = SyncLogEntry, 1`):
        # positionsweise, nur wenn beide Seiten dieselbe Laenge haben.
        for ziel in knoten.targets:
            if isinstance(ziel, ast.Name):
                self._merke(ziel.id, knoten.value)
            elif (
                isinstance(ziel, (ast.Tuple, ast.List))
                and isinstance(knoten.value, (ast.Tuple, ast.List))
                and len(ziel.elts) == len(knoten.value.elts)
            ):
                for teil_ziel, teil_wert in zip(ziel.elts, knoten.value.elts):
                    if isinstance(teil_ziel, ast.Name):
                        self._merke(teil_ziel.id, teil_wert)
        self.generic_visit(knoten)

    def visit_AnnAssign(self, knoten: ast.AnnAssign) -> None:  # noqa: N802
        if isinstance(knoten.target, ast.Name) and knoten.value is not None:
            self._merke(knoten.target.id, knoten.value)
        self.generic_visit(knoten)


def _fixpunkt_aufloesen(roh: list[tuple[str, ast.expr]], bekannte_namen: set[str]) -> set[str]:
    """Loest eine Liste roher (Zielname, Quellausdruck)-Paare zum Fixpunkt
    auf: eine Quelle zaehlt, wenn sie ein `Name` ODER ein modulqualifiziertes
    `Attribute` ist (`_rechter_bezeichner` deckt beides ab) und selbst schon
    bekannt ist. Fixpunkt, weil ein Alias seinerseits Ziel eines weiteren
    Alias sein kann (`_B = _A; _A = SyncLogEntry`, in welcher Reihenfolge auch
    immer im Baum — M11, Nacharbeit 1)."""
    aliase: set[str] = set()
    geaendert = True
    while geaendert:
        geaendert = False
        gueltig = bekannte_namen | aliase
        for ziel, wert in roh:
            if _rechter_bezeichner(wert) in gueltig and ziel not in aliase:
                aliase.add(ziel)
                geaendert = True
    return aliase


def _sammle_aliase(
    baum: ast.Module, bekannte_namen: set[str]
) -> tuple[set[str], dict[tuple[Optional[str], str], set[str]]]:
    """Ersatz fuer die fruehere `_sammle_lokale_aliase`: (modulweite Aliase,
    {(Klasse, Funktion): NUR-DORT-gueltige Aliase}). Modulweite Aliase
    fliessen als zusaetzliche 'bekannte Namen' in JEDEN Funktions-Fixpunkt ein
    (eine Funktion darf einen modulweiten Alias immer sehen), nie umgekehrt."""
    aliase_import: set[str] = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.ImportFrom):
            for alias in knoten.names:
                if alias.name in bekannte_namen:
                    aliase_import.add(alias.asname or alias.name)

    sammler = _AliasSammler()
    sammler.visit(baum)
    modul_roh = sammler.roh.get((None, "<Modul>"), [])
    modul_aliase = aliase_import | _fixpunkt_aufloesen(modul_roh, bekannte_namen | aliase_import)
    global_sichtbar = bekannte_namen | modul_aliase

    funktions_aliase: dict[tuple[Optional[str], str], set[str]] = {}
    for schluessel, roh in sammler.roh.items():
        if schluessel == (None, "<Modul>"):
            continue
        aufgeloest = _fixpunkt_aufloesen(roh, global_sichtbar)
        if aufgeloest:
            funktions_aliase[schluessel] = aufgeloest
    return modul_aliase, funktions_aliase


def _sammle_partial_aliase(baum: ast.Module) -> set[str]:
    """Lokale Namen, die auf `functools.partial` zeigen: ein Importalias
    (`from functools import partial as X`) UND eine schlichte
    Namens-Alias-Zuweisung auf den (ggf. bereits aliasierten) Namen selbst
    (`_pp = partial`, #115 Nacharbeit 1). Der unveraenderte Name `partial` und
    der modul-qualifizierte Aufruf `functools.partial(...)` werden bereits
    ueber `_rechter_bezeichner` (den nackten bzw. den Attributnamen) erkannt
    und brauchen keinen Eintrag hier.

    Bewusst MODULWEIT ohne Funktions-Geltungsbereich (anders als
    `_sammle_aliase` fuer SyncLogEntry-Namen): Eine lokale Variable ausgerechnet
    `partial` zu nennen ist ein seltenes Muster, das Restrisiko einer
    file-weiten statt funktionslokalen Ueberdeckung wird hier in Kauf
    genommen."""
    aliase: set[str] = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.ImportFrom) and knoten.module == "functools":
            for alias in knoten.names:
                if alias.name == "partial" and alias.asname:
                    aliase.add(alias.asname)

    gueltig = {"partial"} | aliase
    geaendert = True
    while geaendert:
        geaendert = False
        for knoten in ast.walk(baum):
            if (
                isinstance(knoten, ast.Assign)
                and len(knoten.targets) == 1
                and isinstance(knoten.targets[0], ast.Name)
                and isinstance(knoten.value, ast.Name)
                and knoten.value.id in gueltig
                and knoten.targets[0].id not in gueltig
            ):
                aliase.add(knoten.targets[0].id)
                gueltig.add(knoten.targets[0].id)
                geaendert = True
    return aliase


def _sammle_typeadapter_aliase(baum: ast.Module, gueltige_namen: set[str]) -> tuple[set[str], set[str]]:
    """(Importalias-Namen fuer `TypeAdapter` selbst, Variablennamen, die an
    `TypeAdapter(SyncLogEntry)`/`TypeAdapter(list[SyncLogEntry])` gebunden
    wurden — #115, Nacharbeit 1). Bewusst MODULWEIT, dieselbe Abwaegung wie
    bei `_sammle_partial_aliase`."""
    import_aliase: set[str] = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.ImportFrom) and knoten.module == "pydantic":
            for alias in knoten.names:
                if alias.name == "TypeAdapter" and alias.asname:
                    import_aliase.add(alias.asname)

    ziel_namen = {"TypeAdapter"} | import_aliase
    var_aliase: set[str] = set()
    for knoten in ast.walk(baum):
        if (
            isinstance(knoten, ast.Assign)
            and len(knoten.targets) == 1
            and isinstance(knoten.targets[0], ast.Name)
            and isinstance(knoten.value, ast.Call)
            and _rechter_bezeichner(knoten.value.func) in ziel_namen
            and any(_rechter_bezeichner_tief(arg) in gueltige_namen for arg in knoten.value.args)
        ):
            var_aliase.add(knoten.targets[0].id)
    return import_aliase, var_aliase


class _SyncLogPruefer(ast.NodeVisitor):
    """Fail-closed-Pruefung EINER Datei. Siehe Moduldocstring fuer die
    vollstaendige Liste der erfassten und der bekannten NICHT erfassten
    Formen."""

    def __init__(
        self,
        relativer_pfad: str,
        gueltige_namen: set[str],
        funktions_aliase: dict[tuple[Optional[str], str], set[str]],
        partial_aliase: set[str],
        typeadapter_aliase: set[str],
        typeadapter_var_aliase: set[str],
    ):
        self.relativer_pfad = relativer_pfad
        self.gueltige_namen = gueltige_namen
        self.funktions_aliase = funktions_aliase
        self.partial_aliase = partial_aliase
        self.typeadapter_aliase = typeadapter_aliase
        self.typeadapter_var_aliase = typeadapter_var_aliase
        self._funktionsstapel: list[str] = ["<Modul>"]
        self._klassenstapel: list[Optional[str]] = [None]
        self.gefunden: dict[str, set[frozenset[str]]] = {}
        self.verstoesse: list[str] = []
        self.ausnahme_treffer: dict[tuple[str, Optional[str], str], int] = {}
        self.lese_ausnahme_treffer: dict[tuple[str, Optional[str], str], int] = {}
        # Attribut-Knoten (Load), die `visit_Compare` VOR seinem
        # `generic_visit` als strukturell beweisbare Lese-Form markiert hat
        # (Identitaet, nicht Wert — zwei Attributzugriffe an verschiedenen
        # Stellen sind zwei verschiedene Knoten).
        self._beweisbare_lese_knoten: set[ast.Attribute] = set()

    def _ort(self, zeile: int) -> str:
        return f"{self.relativer_pfad}:{zeile}"

    def _aktueller_schluessel(self) -> tuple[str, Optional[str], str]:
        return (self.relativer_pfad, self._klassenstapel[-1], self._funktionsstapel[-1])

    def _gueltige_namen_hier(self) -> set[str]:
        """`gueltige_namen` (modulweit + globale Unterklassen), erweitert um
        Zuweisungs-Aliase, die NUR in der aktuellen Funktion gelten (#115,
        Nacharbeit 1 — Geltungsbereich statt dateiweiter Ueberdeckung)."""
        ort = (self._klassenstapel[-1], self._funktionsstapel[-1])
        return self.gueltige_namen | self.funktions_aliase.get(ort, set())

    def visit_ClassDef(self, knoten: ast.ClassDef) -> None:  # noqa: N802
        self._klassenstapel.append(knoten.name)
        self.generic_visit(knoten)
        self._klassenstapel.pop()

    def visit_FunctionDef(self, knoten: ast.FunctionDef) -> None:  # noqa: N802
        self._funktionsstapel.append(knoten.name)
        self.generic_visit(knoten)
        self._funktionsstapel.pop()

    def visit_AsyncFunctionDef(self, knoten: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._funktionsstapel.append(knoten.name)
        self.generic_visit(knoten)
        self._funktionsstapel.pop()

    def visit_Compare(self, knoten: ast.Compare) -> None:  # noqa: N802
        """Markiert Attributzugriffe auf `.message_key`/`.message_params`,
        die als Operand EINES Vergleichs auftreten (z. B.
        `e.message_key == schluessel`), als strukturell BEWEISBARE Lese-Form
        (#115, Nacharbeit 1, Punkt 1, Beispiel 1 aus dem Issue). Nur an einem
        so bewiesenen Knoten UND nur an einer in `_BENANNTE_LESE_AUSNAHMEN`
        gelisteten Stelle erlaubt `visit_Attribute` unten den Zugriff.
        Reihenfolge: Markierung VOR `generic_visit`, das `visit_Attribute`
        erst ausloest (derselbe Kniff wie eine Markierung vor dem Besuch)."""
        for operand in (knoten.left, *knoten.comparators):
            if (
                isinstance(operand, ast.Attribute)
                and operand.attr in _LITERALE_NAMEN
                and isinstance(operand.ctx, ast.Load)
            ):
                self._beweisbare_lese_knoten.add(operand)
        self.generic_visit(knoten)

    def visit_Attribute(self, knoten: ast.Attribute) -> None:  # noqa: N802
        """Restaurierte Strenge von Nacharbeit 2 (`c8e2458`): JEDER
        Attributzugriff auf `.message_key`/`.message_params` ist ein
        Verstoss — `Store`/`Del` (Zuweisung, `+=`, `del`) IMMER, ein `Load`
        NUR DANN NICHT, wenn er (a) Operand eines Vergleichs ist (siehe
        `visit_Compare`) UND (b) an einer Stelle aus
        `_BENANNTE_LESE_AUSNAHMEN` steht (#115, Nacharbeit 1 — die zweite im
        Issue genannte Richtung: eine benannte Lese-Ausnahme statt einer
        allgemeinen Lese-Erlaubnis).

        Zwei Schreib-Formen tragen an DIESEM Knoten trotzdem `Load`, weil das
        Schreiben eine Ebene hoeher passiert — die werden bewusst NICHT hier,
        sondern in `visit_Subscript` (Subskript-Zuweisung) bzw. `visit_Call`
        (Mutationsmethode auf einer direkten Attribut-Basis) zusaetzlich mit
        einer spezifischeren Meldung gefangen; diese generische Pruefung hier
        greift trotzdem (der Attributzugriff selbst ist ja ebenfalls ein
        Knoten) und deckt zusaetzlich jede INDIREKTE Form (ueber `getattr`,
        eine Zwischenvariable, einen Walrus, einen `BoolOp`, eine gebundene
        Methode — siehe Docstring, "BLOCKER 1")."""
        if knoten.attr not in _LITERALE_NAMEN:
            self.generic_visit(knoten)
            return
        if isinstance(knoten.ctx, (ast.Store, ast.Del)):
            self.verstoesse.append(
                f"{self._ort(knoten.lineno)} schreibender Zugriff auf .{knoten.attr} ist fail-closed "
                "verboten (deckt Zuweisung, `+=` und `del` ab; Schreiben ausschliesslich ueber eine "
                "woertliche SyncLogEntry-Konstruktion mit message_key=... / message_params=...)"
            )
        else:
            schluessel = self._aktueller_schluessel()
            if knoten in self._beweisbare_lese_knoten and schluessel in _BENANNTE_LESE_AUSNAHMEN:
                self.lese_ausnahme_treffer[schluessel] = self.lese_ausnahme_treffer.get(schluessel, 0) + 1
            else:
                self.verstoesse.append(
                    f"{self._ort(knoten.lineno)} lesender Zugriff auf .{knoten.attr} ist fail-closed "
                    "verboten (kein an diesem Knoten beweisbares Lesen mit einer benannten "
                    "Lese-Ausnahme an dieser Stelle; erlaubter Weg: ein Eintrag in "
                    "_BENANNTE_LESE_AUSNAHMEN fuer eine strukturell beweisbare Form wie einen "
                    "Vergleichsoperanden, z. B. eintrag.message_key == schluessel)"
                )
        self.generic_visit(knoten)

    def visit_Subscript(self, knoten: ast.Subscript) -> None:  # noqa: N802
        """Subskript-Zuweisung/-Loeschung auf die Basis
        `.message_params[...] = ...` bzw. `del .message_params[...]`. Der
        `Attribute`-Knoten der Basis traegt hier `Load` (er wird gelesen, um
        das Dict zu bekommen) — `visit_Attribute` faengt ihn seit Nacharbeit 1
        ZUSAETZLICH generisch, diese spezifischere Meldung bleibt fuer den
        haeufigen, direkten Fall erhalten."""
        basis = knoten.value
        if (
            isinstance(basis, ast.Attribute)
            and basis.attr in _LITERALE_NAMEN
            and isinstance(knoten.ctx, (ast.Store, ast.Del))
        ):
            self.verstoesse.append(
                f"{self._ort(knoten.lineno)} Subskript-Zuweisung auf .{basis.attr}[...] ist fail-closed "
                "verboten (erlaubt ist nur Lesen ueber eine benannte Lese-Ausnahme; Schreiben "
                "ausschliesslich ueber eine woertliche SyncLogEntry-Konstruktion mit "
                "message_key=... / message_params=...)"
            )
        self.generic_visit(knoten)

    def visit_Constant(self, knoten: ast.Constant) -> None:  # noqa: N802
        """Restaurierte Strenge von Nacharbeit 2: JEDES literale Vorkommen
        von genau `"message_key"` oder `"message_params"` als STRING-WERT ist
        ein Verstoss, AUSNAHMSLOS (#115, Nacharbeit 1 hat die vier
        pauschalen Lese-Formen der Erstrunde — `getattr`/`hasattr`/
        `field_validator`/`model_dump` — ersatzlos gestrichen, siehe
        Docstring "BLOCKER 2"). Deckt `setattr(...)`,
        `entry.setdefault("message_key", ...)`, `model_copy(update=
        {"message_key": ...})`, `@field_validator("message_key")` und
        `model_dump(exclude={"message_params"})` gleichermassen ab."""
        if isinstance(knoten.value, str) and knoten.value in _LITERALE_NAMEN:
            self.verstoesse.append(
                f"{self._ort(knoten.lineno)} literale Zeichenkette '{knoten.value}' ist fail-closed "
                "verboten (kein Lese-Pfad mehr ueber Literale; Lesen ausschliesslich ueber einen an "
                "einem Vergleichsoperanden beweisbaren Attributzugriff mit benannter Lese-Ausnahme; "
                "Schreiben ausschliesslich ueber eine woertliche SyncLogEntry-Konstruktion)"
            )

    def visit_Call(self, knoten: ast.Call) -> None:  # noqa: N802
        rechter_name = _rechter_bezeichner(knoten.func)
        gueltige_namen_hier = self._gueltige_namen_hier()

        # dict(message_params=..., ...) / dict(message_key=..., ...): der
        # Schluesselwortname eines `ast.keyword` ist ein Python-String auf dem
        # Knoten, kein `ast.Constant` — entgeht deshalb `visit_Constant`.
        # Deckt `model_copy(update=dict(message_params=...))` ab (#115,
        # Nacharbeit 1).
        if rechter_name == "dict":
            for schluesselwort in knoten.keywords:
                if schluesselwort.arg in _LITERALE_NAMEN:
                    self.verstoesse.append(
                        f"{self._ort(knoten.lineno)} dict(...)-Aufruf mit Schluesselwort "
                        f"'{schluesselwort.arg}' ist fail-closed verboten (deckt z. B. "
                        "model_copy(update=dict(message_params=...)) ab; Schreiben ausschliesslich "
                        "ueber eine woertliche SyncLogEntry-Konstruktion)"
                    )

        # Kategorische Verbote, unabhaengig von etwaigen Schluesselwoertern:
        # Die spaetere Bindung eines `partial` und beliebige Rohdaten an
        # `model_validate*`/`model_construct`/`construct`/`parse_obj`/
        # `model_validate_strings` sind statisch nicht pruefbar. `partial` UND
        # sein per-Datei gesammelter Alias treffen hier gleichermassen.
        if (rechter_name == "partial" or rechter_name in self.partial_aliase) and knoten.args:
            if _rechter_bezeichner(knoten.args[0]) in gueltige_namen_hier:
                self.verstoesse.append(
                    f"{self._ort(knoten.lineno)} functools.partial auf SyncLogEntry/Unterklasse ist "
                    "fail-closed verboten (die spaetere Bindung ist statisch nicht pruefbar)"
                )
                self.generic_visit(knoten)
                return
        if isinstance(knoten.func, ast.Attribute) and knoten.func.attr in _KATEGORISCH_VERBOTENE_METHODEN:
            if _rechter_bezeichner(knoten.func.value) in gueltige_namen_hier:
                self.verstoesse.append(
                    f"{self._ort(knoten.lineno)} {knoten.func.attr}(...) auf SyncLogEntry/Unterklasse ist "
                    "fail-closed verboten (keine pruefbare Schluesselwort-Form)"
                )
                self.generic_visit(knoten)
                return

        # TypeAdapter(SyncLogEntry|list[SyncLogEntry]).validate_python(roh)/
        # .validate_json(roh)/.validate_strings(roh), auch ueber einen
        # Import- oder Variablen-Alias: eine eng gefasste, gezielte
        # Erkennung dieser konkreten Form(en). `knoten.func.value` ist hier
        # entweder der INNERE Call `TypeAdapter(...)` oder ein Name, der auf
        # eine vorher zugewiesene TypeAdapter-Variable zeigt.
        if isinstance(knoten.func, ast.Attribute) and knoten.func.attr in _TYPE_ADAPTER_METHODEN:
            innerer_aufruf = knoten.func.value
            ist_typeadapter_aufruf = (
                isinstance(innerer_aufruf, ast.Call)
                and _rechter_bezeichner(innerer_aufruf.func) in ({"TypeAdapter"} | self.typeadapter_aliase)
                and any(_rechter_bezeichner_tief(arg) in gueltige_namen_hier for arg in innerer_aufruf.args)
            )
            ist_typeadapter_variable = (
                isinstance(innerer_aufruf, ast.Name) and innerer_aufruf.id in self.typeadapter_var_aliase
            )
            if ist_typeadapter_aufruf or ist_typeadapter_variable:
                self.verstoesse.append(
                    f"{self._ort(knoten.lineno)} TypeAdapter(...).{knoten.func.attr}(...) auf "
                    "SyncLogEntry/Unterklasse ist fail-closed verboten (keine pruefbare "
                    "Schluesselwort-Form, beliebige Rohdaten)"
                )
                self.generic_visit(knoten)
                return

        # Mutationsmethode auf `.message_params` (`.pop()`, `.update()`, ...):
        # Der Attribut-Zugriff, der das Dict holt, traegt `Load` und wird von
        # `visit_Attribute` seit Nacharbeit 1 ZUSAETZLICH generisch gefangen —
        # diese spezifischere Meldung bleibt fuer den direkten Fall erhalten.
        if (
            isinstance(knoten.func, ast.Attribute)
            and knoten.func.attr in _MUTIERENDE_DICT_METHODEN
            and isinstance(knoten.func.value, ast.Attribute)
            and knoten.func.value.attr in _LITERALE_NAMEN
        ):
            self.verstoesse.append(
                f"{self._ort(knoten.lineno)} Mutationsmethode .{knoten.func.attr}() auf "
                f".{knoten.func.value.attr} ist fail-closed verboten (erlaubt ist nur Lesen ueber eine "
                "benannte Lese-Ausnahme; Schreiben ausschliesslich ueber eine woertliche "
                "SyncLogEntry-Konstruktion)"
            )
            self.generic_visit(knoten)
            return

        ist_konstruktion = rechter_name in gueltige_namen_hier
        # Gegenpruefer-Sonde bestaetigt (Skizze in `gegen/S5/k1fix`, Ergebnis
        # selbst gemessen: genau ein `type(...)`-Aufruf im heutigen Backend,
        # `type(exc).__name__`, kein `type(x)(...)`-Aufruf, kein
        # `.__class__(...)`-Aufruf) — Fangen ist ohne Fehlalarm moeglich.
        ist_dynamischer_typ_aufruf = (
            isinstance(knoten.func, ast.Call)
            and isinstance(knoten.func.func, ast.Name)
            and knoten.func.func.id == "type"
        ) or (isinstance(knoten.func, ast.Attribute) and knoten.func.attr == "__class__")
        if ist_dynamischer_typ_aufruf:
            ist_konstruktion = True

        msg_key_kw = next((kw for kw in knoten.keywords if kw.arg == "message_key"), None)
        msg_params_kw = next((kw for kw in knoten.keywords if kw.arg == "message_params"), None)
        ist_reiner_doppelstern = len(knoten.keywords) == 1 and knoten.keywords[0].arg is None

        if ist_konstruktion or msg_key_kw is not None:
            ausnahme_schluessel = self._aktueller_schluessel()
            if ist_konstruktion and ist_reiner_doppelstern and ausnahme_schluessel in _BENANNTE_AUSNAHMEN:
                self.ausnahme_treffer[ausnahme_schluessel] = self.ausnahme_treffer.get(ausnahme_schluessel, 0) + 1
            else:
                self._pruefe_und_sammle(
                    message_key_knoten=msg_key_kw.value if msg_key_kw else None,
                    message_params_knoten=msg_params_kw.value if msg_params_kw else None,
                    hat_message_params_schluessel=msg_params_kw is not None,
                    zeile=knoten.lineno,
                    ist_dynamischer_typ_aufruf=ist_dynamischer_typ_aufruf,
                )
        self.generic_visit(knoten)

    def _pruefe_und_sammle(
        self,
        *,
        message_key_knoten: Optional[ast.expr],
        message_params_knoten: Optional[ast.expr],
        hat_message_params_schluessel: bool,
        zeile: int,
        ist_dynamischer_typ_aufruf: bool = False,
    ) -> None:
        ort = self._ort(zeile)
        praefix = "type(...)/.__class__(...)-Konstruktion" if ist_dynamischer_typ_aufruf else "SyncLogEntry-Konstruktion"
        if message_key_knoten is None:
            self.verstoesse.append(f"{ort} {praefix} ohne message_key")
            return
        if not (isinstance(message_key_knoten, ast.Constant) and isinstance(message_key_knoten.value, str)):
            self.verstoesse.append(
                f"{ort} message_key ist keine woertliche Zeichenkette (fail-closed: Variablen, "
                "f-Strings, Funktionsargumente, Tabellen-Zugriffe und aehnliches sind verboten)"
            )
            return
        schluessel = message_key_knoten.value
        if not schluessel.startswith("log_"):
            self.verstoesse.append(f"{ort} message_key '{schluessel}' beginnt nicht mit 'log_'")
            return
        if not hat_message_params_schluessel:
            self.verstoesse.append(f"{ort} '{schluessel}' ohne message_params")
            return
        if not isinstance(message_params_knoten, ast.Dict):
            self.verstoesse.append(f"{ort} '{schluessel}': message_params ist kein woertliches dict")
            return
        namen: set[str] = set()
        for k in message_params_knoten.keys:
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                self.verstoesse.append(
                    f"{ort} '{schluessel}': message_params hat einen nicht-woertlichen Schluessel"
                )
                return
            namen.add(k.value)
        self.gefunden.setdefault(schluessel, set()).add(frozenset(namen))


def backend_sendestellen(wurzel: Path = BACKEND_DIR) -> tuple[dict[str, frozenset[str]], list[str]]:
    """Fail-closed: (gesendete Schluessel -> Parametermenge, Verstossliste).

    Jeder Verstoss landet in der Verstossliste, statt eine Fundstelle
    stillschweigend auszulassen. Der Aufrufer entscheidet, ob eine
    nicht-leere Verstossliste ein Testfehlschlag ist (Produktivpruefung)
    oder das erwartete Ergebnis (Rot-Beweis).
    """
    dateipfade = [
        datei
        for datei in sorted(wurzel.rglob("*.py"))
        if not _AUSGESCHLOSSENE_VERZEICHNISNAMEN & set(datei.relative_to(wurzel).parts[:-1])
    ]
    baeume = {datei: ast.parse(datei.read_text("utf-8"), filename=str(datei)) for datei in dateipfade}
    gueltige_namen_global = _sammle_sync_log_entry_namen(baeume)

    # Relativer Pfad IMMER gegen die echte Repo-Wurzel, auch wenn `wurzel`
    # (Rot-Beweise) eine Kopie unter tmp_path ist — sonst wuerde eine benannte
    # Ausnahme dort nie zutreffen, weil ihr Schluessel `backend/services/...`
    # lautet, nicht `services/...`.
    ist_kopie = wurzel != BACKEND_DIR

    gefunden: dict[str, set[frozenset[str]]] = {}
    verstoesse: list[str] = []
    ausnahme_treffer: dict[tuple[str, Optional[str], str], int] = {}
    lese_ausnahme_treffer: dict[tuple[str, Optional[str], str], int] = {}

    for datei, baum in baeume.items():
        if ist_kopie:
            relativer_pfad = "backend/" + str(datei.relative_to(wurzel)).replace("\\", "/")
        else:
            relativer_pfad = str(datei.relative_to(WURZEL)).replace("\\", "/")
        modul_aliase, funktions_aliase = _sammle_aliase(baum, gueltige_namen_global)
        gueltige_namen = gueltige_namen_global | modul_aliase
        partial_aliase = _sammle_partial_aliase(baum)
        typeadapter_aliase, typeadapter_var_aliase = _sammle_typeadapter_aliase(baum, gueltige_namen)
        pruefer = _SyncLogPruefer(
            relativer_pfad,
            gueltige_namen,
            funktions_aliase,
            partial_aliase,
            typeadapter_aliase,
            typeadapter_var_aliase,
        )
        pruefer.visit(baum)
        verstoesse.extend(pruefer.verstoesse)
        for schluessel, anzahl in pruefer.ausnahme_treffer.items():
            ausnahme_treffer[schluessel] = ausnahme_treffer.get(schluessel, 0) + anzahl
        for schluessel, anzahl in pruefer.lese_ausnahme_treffer.items():
            lese_ausnahme_treffer[schluessel] = lese_ausnahme_treffer.get(schluessel, 0) + anzahl
        for schluessel, mengen in pruefer.gefunden.items():
            gefunden.setdefault(schluessel, set()).update(mengen)

    for schluessel, begruendung in _BENANNTE_AUSNAHMEN.items():
        anzahl = ausnahme_treffer.get(schluessel, 0)
        if anzahl == 0:
            verstoesse.append(f"veraltete Ausnahme: {schluessel} wurde nicht getroffen ({begruendung})")
        elif anzahl > 1:
            verstoesse.append(f"Ausnahme {schluessel} mehrfach getroffen ({anzahl}x) statt genau einmal")

    for schluessel, begruendung in _BENANNTE_LESE_AUSNAHMEN.items():
        if lese_ausnahme_treffer.get(schluessel, 0) == 0:
            verstoesse.append(f"veraltete Lese-Ausnahme: {schluessel} wurde nicht getroffen ({begruendung})")

    ergebnis: dict[str, frozenset[str]] = {}
    for schluessel, mengen in gefunden.items():
        if len(mengen) > 1:
            verstoesse.append(
                f"'{schluessel}' wird an verschiedenen Stellen mit unterschiedlichen Parametern "
                f"verschickt: {sorted((sorted(m) for m in mengen), key=str)}"
            )
            continue
        ergebnis[schluessel] = next(iter(mengen))
    return ergebnis, verstoesse


def pruefe_vertrag(wurzel: Path = BACKEND_DIR) -> None:
    """Die eigentliche Vertragspruefung.

    Wird sowohl vom Produktivtest als auch von JEDEM Rot-Beweis unten
    aufgerufen — nicht eine fuer die Rot-Beweise nachgebaute Kopie der
    Vergleichslogik. Eine Aushoehlung dieser Funktion traefe dadurch
    automatisch auch jeden Rot-Beweis, der hier auf ein `pytest.raises`
    angewiesen ist.
    """
    gefunden, verstoesse = backend_sendestellen(wurzel)
    assert verstoesse == [], "Fail-closed-Verstoesse: " + "; ".join(verstoesse)

    vertrag = lade_vertrag()
    hinten = set(gefunden)
    vorne = set(vertrag)
    nur_hinten = sorted(hinten - vorne)
    nur_vorne = sorted(vorne - hinten)
    assert nur_hinten == [], f"gesendet, aber kein Vertragseintrag: {nur_hinten}"
    assert nur_vorne == [], f"Vertragseintrag, den niemand sendet: {nur_vorne}"

    abweichungen = {
        schluessel: {"gesendet": sorted(gefunden[schluessel]), "vertrag": sorted(vertrag[schluessel])}
        for schluessel in sorted(hinten & vorne)
        if gefunden[schluessel] != frozenset(vertrag[schluessel])
    }
    assert abweichungen == {}, f"Parameter weichen vom Vertrag ab: {abweichungen}"


def test_vertragsdatei_ist_nicht_leer():
    """Ersetzt die fruehere Mindestzahl-Zusicherung.

    Eine leere Backend-Erfassung waere gegen einen leeren Vertrag
    mengengleich und `pruefe_vertrag` bliebe gruen — aber nur, wenn die
    eingecheckte Vertragsdatei SELBST leer waere. Das ist ein sichtbarer,
    eigener Akt (jemand setzt die Datei auf "{}") und kein stiller
    Seiteneffekt eines kaputten Scanners; diese Zusicherung deckt genau das
    ab, keine willkuerliche Mindestzahl mehr.
    """
    assert lade_vertrag() != {}


def test_backend_stimmt_mit_dem_vertrag_ueberein():
    pruefe_vertrag()


def test_produktivpruefung_sieht_den_echten_baum_unabhaengig_vom_test_oben():
    """Absicherung gegen Aushoehlung (Fremdpruefer-Fund, #115 Nacharbeit 1):
    `test_backend_stimmt_mit_dem_vertrag_ueberein` liesse sich durch `pass`
    ersetzen oder loeschen, ohne dass ein anderer Test das bemerkt — alle
    Rot-Beweise unten arbeiten auf einer MUTIERTEN KOPIE, keiner prueft den
    echten Baum.

    Dieser Test ruft `backend_sendestellen()` UNABHAENGIG ein zweites Mal auf
    dem echten Baum auf und verlangt, dass der Scanner dort selbst etwas
    gesehen hat — keine hartkodierte Zahl, sondern ein Vergleich gegen die
    Vertragsdatei (die ihrerseits `test_vertragsdatei_ist_nicht_leer` gegen
    Leere absichert). Wird `test_backend_stimmt_mit_dem_vertrag_ueberein`
    unbemerkt neutralisiert, bleibt DIESER Test trotzdem rot.
    """
    gefunden, verstoesse = backend_sendestellen()
    assert verstoesse == [], "Fail-closed-Verstoesse: " + "; ".join(verstoesse)
    assert len(gefunden) > 0, "pruefe_vertrag hat auf dem echten Baum NICHTS gefunden - Scanner kaputt?"
    assert set(gefunden) == set(lade_vertrag())


def _kopiere_backend_mit_mutation(tmp_path: Path, mutation: Callable[[Path], None]) -> Path:
    """Kopiert `backend/` nach `tmp_path/backend` und wendet `mutation` an.

    Der echte Arbeitsbaum wird nie veraendert. `tests/` und `__pycache__/`
    werden nicht mitkopiert (fuer die Pruefung ohnehin ausgeschlossen).
    """
    ziel = tmp_path / "backend"
    shutil.copytree(BACKEND_DIR, ziel, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    mutation(ziel)
    return ziel


def _sonde_anhaengen(backend_kopie: Path, python_quelltext: str) -> None:
    datei = backend_kopie / "services" / "sync_service.py"
    datei.write_text(datei.read_text("utf-8") + "\n\n" + python_quelltext, "utf-8")


def test_rotbeweis_neuer_schluessel_im_backend_ohne_vertrag(tmp_path):
    """Rot-Beweis: ein gesendeter Schluessel ohne Vertragseintrag faellt auf."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_neuer_schluessel():\n"
            "    return SyncLogEntry(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde',\n"
            "        status='error',\n"
            "        message_key='log_voellig_neu_und_unuebersetzt',\n"
            "        message_params={'wert': 1},\n"
            "    )\n",
        ),
    )
    with pytest.raises(AssertionError, match="log_voellig_neu_und_unuebersetzt"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_parameter_im_backend_entfernt(tmp_path):
    """Rot-Beweis: ein im Backend entfernter Parameter weicht vom Vertrag ab.

    `log_album_shared` kommt im heutigen Stand genau EINMAL vor (Zeile 141f.
    in `sync_service.py`) — dadurch ist die Mutation eindeutig, ohne mit den
    Mehrfachvorkommen anderer Schluessel (z. B. `log_name_synced`, dreimal)
    zu kollidieren.
    """

    def mutieren(backend_kopie: Path) -> None:
        datei = backend_kopie / "services" / "sync_service.py"
        text = datei.read_text("utf-8")
        ziel = 'message_params={"album": album_name, "names": ", ".join(a.name for a in to_add)},'
        ersatz = 'message_params={"album": album_name},'
        assert text.count(ziel) == 1, "erwartete Fundstelle fuer log_album_shared nicht (mehr) vorhanden"
        datei.write_text(text.replace(ziel, ersatz), "utf-8")

    backend_kopie = _kopiere_backend_mit_mutation(tmp_path, mutieren)
    with pytest.raises(AssertionError, match="Parameter weichen vom Vertrag ab"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_schluessel_ueber_variable_gebaut_ist_fail_closed(tmp_path):
    """Rot-Beweis: ein per Konstante gebauter Schluessel ist ein Verstoss."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "_SONDE_SCHLUESSEL = 'log_ast_sonde_variable'\n"
            "\n"
            "\n"
            "def _rotbeweis_variable():\n"
            "    return SyncLogEntry(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde',\n"
            "        status='error',\n"
            "        message_key=_SONDE_SCHLUESSEL,\n"
            "        message_params={'wert': 1},\n"
            "    )\n",
        ),
    )
    with pytest.raises(AssertionError, match="message_key ist keine woertliche Zeichenkette"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_schluessel_als_f_string_ist_fail_closed(tmp_path):
    """Rot-Beweis: ein f-String ist ebenso wenig woertlich wie eine Variable."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_f_string(suffix):\n"
            "    return SyncLogEntry(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde',\n"
            "        status='error',\n"
            "        message_key=f'log_ast_sonde_{suffix}',\n"
            "        message_params={},\n"
            "    )\n",
        ),
    )
    with pytest.raises(AssertionError, match="message_key ist keine woertliche Zeichenkette"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_doppelstern_ausserhalb_der_ausnahme_ist_fail_closed(tmp_path):
    """Rot-Beweis: die benannte Ausnahme gilt nur an IHRER Stelle, nicht ueberall."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_doppelstern_anderswo(rohdaten):\n"
            "    return SyncLogEntry(**rohdaten)\n",
        ),
    )
    with pytest.raises(AssertionError, match="ohne message_key"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_nachtraegliche_zuweisung_ist_fail_closed(tmp_path):
    """Rot-Beweis: `.message_key = ...` NACH der Konstruktion bleibt nicht unbemerkt."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_nachtraeglich():\n"
            "    eintrag = SyncLogEntry(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde',\n"
            "        status='error',\n"
            "        message_key='log_album_shared',\n"
            "        message_params={'album': 'x', 'names': 'y'},\n"
            "    )\n"
            "    eintrag.message_key = 'log_anders_nachtraeglich'\n"
            "    return eintrag\n",
        ),
    )
    with pytest.raises(AssertionError, match=r"Zugriff auf \.message_key"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_message_key_versteckt_in_model_copy_update_wird_erfasst(tmp_path):
    """Rot-Beweis: `model_copy(update={"message_key": ...})` bleibt nicht unsichtbar.

    Der allgemeine Literal-Scan (`visit_Constant`) kennt seit Nacharbeit 1
    KEINE Lese-Form mehr, die ein Literal freischaltet — die literale
    Zeichenkette `"message_key"` in `update={...}` bleibt deshalb IMMER ein
    Verstoss, unabhaengig davon, in welchem Container sie steht.
    """
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_model_copy():\n"
            "    eintrag = SyncLogEntry(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde',\n"
            "        status='error',\n"
            "        message_key='log_album_shared',\n"
            "        message_params={'album': 'x', 'names': 'y'},\n"
            "    )\n"
            "    return eintrag.model_copy(update={\n"
            "        'message_key': 'log_voellig_neu_via_model_copy',\n"
            "        'message_params': {'anders': 1},\n"
            "    })\n",
        ),
    )
    with pytest.raises(AssertionError, match="literale Zeichenkette 'message_key'"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_veraltete_ausnahme_wird_erkannt(tmp_path):
    """Rot-Beweis: verschwindet die einzige Fundstelle der Ausnahme, faellt das auf."""

    def mutieren(backend_kopie: Path) -> None:
        datei = backend_kopie / "services" / "config_store.py"
        text = datei.read_text("utf-8")
        ziel = "SyncLogEntry(**entry)"
        ersatz = (
            "SyncLogEntry(id='x', timestamp='x', action='x', details='x', status='success', "
            "message_key='log_album_shared', message_params={'album': 'x', 'names': 'y'})"
        )
        assert text.count(ziel) == 1, "erwartete Fundstelle fuer die benannte Ausnahme nicht (mehr) vorhanden"
        datei.write_text(text.replace(ziel, ersatz), "utf-8")

    backend_kopie = _kopiere_backend_mit_mutation(tmp_path, mutieren)
    with pytest.raises(AssertionError, match="veraltete Ausnahme"):
        pruefe_vertrag(backend_kopie)


# ── Nacharbeit 2: die drei WICHTIG-Funde ────────────────────────────────────


def test_rotbeweis_h1_pop_auf_message_params_ist_fail_closed(tmp_path):
    """H1: `.pop("names")` auf `.message_params` nach der Konstruktion."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_h1_pop():\n"
            "    eintrag = SyncLogEntry(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde',\n"
            "        status='error',\n"
            "        message_key='log_album_shared',\n"
            "        message_params={'album': 'x', 'names': 'y'},\n"
            "    )\n"
            "    eintrag.message_params.pop('names')\n"
            "    return eintrag\n",
        ),
    )
    with pytest.raises(AssertionError, match=r"Mutationsmethode \.pop\(\) auf \.message_params"):
        pruefe_vertrag(backend_kopie)


@pytest.mark.parametrize(
    "aufruf",
    [
        "eintrag.message_params.update({'album': 'anders'})",
        "eintrag.message_params.clear()",
        "eintrag.message_params.popitem()",
        "eintrag.message_params.setdefault('neu', 1)",
        "eintrag.message_params.__setitem__('album', 'anders')",
        "eintrag.message_params.__delitem__('album')",
    ],
    ids=["update", "clear", "popitem", "setdefault", "dunder_setitem", "dunder_delitem"],
)
def test_rotbeweis_h4_mutationsmethoden_vollstaendige_menge_ist_fail_closed(tmp_path, aufruf):
    """M04 (Blindpruefer-Mutationstest): die Mutationsmethoden-Menge auf EINEN
    Eintrag (`{"pop"}`) zu verkleinern blieb an Nacharbeit 3 GRUEN, weil nur
    `.pop()` (H1) getestet war. Diese parametrisierte Sonde deckt die
    restlichen sechs Methoden der Menge einzeln ab."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_h4_mutationsmethode():\n"
            "    eintrag = SyncLogEntry(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde',\n"
            "        status='error',\n"
            "        message_key='log_album_shared',\n"
            "        message_params={'album': 'x', 'names': 'y'},\n"
            "    )\n"
            f"    eintrag.{aufruf}\n"
            "    return eintrag\n",
        ),
    )
    with pytest.raises(AssertionError, match=r"Mutationsmethode .* auf \.message_params"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_h2_setattr_ist_fail_closed(tmp_path):
    """H2: `setattr(eintrag, "message_key", ...)` umgeht die Attribut-Pruefung."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_h2_setattr():\n"
            "    eintrag = SyncLogEntry(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde',\n"
            "        status='error',\n"
            "        message_key='log_album_shared',\n"
            "        message_params={'album': 'x', 'names': 'y'},\n"
            "    )\n"
            "    setattr(eintrag, 'message_key', 'log_anders_per_setattr')\n"
            "    return eintrag\n",
        ),
    )
    with pytest.raises(AssertionError, match="literale Zeichenkette 'message_key'"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_h3_augmented_assign_ist_fail_closed(tmp_path):
    """H3: `eintrag.message_key += "..."` ist eine Zuweisung wie jede andere."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_h3_augmented():\n"
            "    eintrag = SyncLogEntry(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde',\n"
            "        status='error',\n"
            "        message_key='log_album_shared',\n"
            "        message_params={'album': 'x', 'names': 'y'},\n"
            "    )\n"
            "    eintrag.message_key += '_suffix'\n"
            "    return eintrag\n",
        ),
    )
    with pytest.raises(AssertionError, match=r"Zugriff auf \.message_key"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_h4_unterklasse_ohne_message_key_ist_fail_closed(tmp_path):
    """H4: Eine Unterklasse von SyncLogEntry wird als Konstruktion erkannt."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "class _SondeUnterklasse(SyncLogEntry):\n"
            "    pass\n"
            "\n"
            "\n"
            "def _rotbeweis_h4_unterklasse():\n"
            "    return _SondeUnterklasse(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde', status='error',\n"
            "    )\n",
        ),
    )
    with pytest.raises(AssertionError, match="ohne message_key"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_h5b_setdefault_in_der_ausnahme_ist_fail_closed(tmp_path):
    """H5b: `entry.setdefault("message_key", ...)` VOR dem erlaubten `**entry`.

    Die benannte Ausnahme deckt NUR den einen `SyncLogEntry(**entry)`-Aufruf
    ab — nicht die ganze Funktion. Ein `setdefault` mit der literalen
    Zeichenkette `"message_key"` direkt davor bleibt ein Verstoss, egal ob er
    in derselben Funktion steht wie die Ausnahme.
    """

    def mutieren(backend_kopie: Path) -> None:
        datei = backend_kopie / "services" / "config_store.py"
        text = datei.read_text("utf-8")
        ziel = "            try:\n                result.append(SyncLogEntry(**entry))"
        ersatz = (
            '            try:\n                entry.setdefault("message_key", "log_h5b_sonde")\n'
            "                result.append(SyncLogEntry(**entry))"
        )
        assert text.count(ziel) == 1, "erwartete Fundstelle in _build_log_entries nicht (mehr) vorhanden"
        datei.write_text(text.replace(ziel, ersatz), "utf-8")

    backend_kopie = _kopiere_backend_mit_mutation(tmp_path, mutieren)
    with pytest.raises(AssertionError, match="literale Zeichenkette 'message_key'"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_h7_modulqualifizierter_aufruf_ist_fail_closed(tmp_path):
    """H7: `mm.SyncLogEntry(**roh)` wird trotz Modul-Alias als Konstruktion erkannt."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "import models.match as mm\n"
            "\n"
            "\n"
            "def _rotbeweis_h7_modulqualifiziert(roh):\n"
            "    return mm.SyncLogEntry(**roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="ohne message_key"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_h6_functools_partial_ist_fail_closed(tmp_path):
    """H6 (Ergaenzung): `functools.partial(SyncLogEntry, ...)` ist kategorisch verboten.

    Selbst mit einem woertlichen `message_key` waere hier nicht pruefbar, ob
    und wie der Partial spaeter tatsaechlich aufgerufen wird.
    """
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "import functools\n"
            "\n"
            "\n"
            "_ROTBEWEIS_PARTIAL = functools.partial(\n"
            "    SyncLogEntry, message_key='log_album_shared', message_params={'album': 'x', 'names': 'y'}\n"
            ")\n",
        ),
    )
    with pytest.raises(AssertionError, match="functools.partial auf SyncLogEntry"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_h8_model_validate_ist_fail_closed(tmp_path):
    """H8 (Ergaenzung): `SyncLogEntry.model_validate(...)` ist kategorisch verboten."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_h8_model_validate(roh):\n"
            "    return SyncLogEntry.model_validate(roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="model_validate"):
        pruefe_vertrag(backend_kopie)


# ── Nacharbeit 3 (#115, Erstrunde): die H9-H13-Restformen, unveraendert ─────


def test_rotbeweis_h9_zuweisungs_alias_ist_fail_closed(tmp_path):
    """H9 (#115): `_Eintrag = SyncLogEntry; _Eintrag(**roh)` wird als
    Konstruktion erkannt -- die Restform "Alias der Klasse mit `**roh`" aus
    der Nachlese."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "_Eintrag = SyncLogEntry\n"
            "\n"
            "\n"
            "def _rotbeweis_h9_zuweisungs_alias(roh):\n"
            "    return _Eintrag(**roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="ohne message_key"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_h10_model_construct_ist_fail_closed(tmp_path):
    """H10 (#115): `SyncLogEntry.model_construct(**roh)` umgeht jede
    Validierung -- dieselbe kategorische Sperre wie `model_validate`."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_h10_model_construct(roh):\n"
            "    return SyncLogEntry.model_construct(**roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="model_construct"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_h11_type_adapter_ist_fail_closed(tmp_path):
    """H11 (#115): `TypeAdapter(SyncLogEntry).validate_python(roh)` -- die
    Zwei-Aufruf-Form aus der Nachlese."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "from pydantic import TypeAdapter\n"
            "\n"
            "\n"
            "def _rotbeweis_h11_type_adapter(roh):\n"
            "    return TypeAdapter(SyncLogEntry).validate_python(roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="TypeAdapter"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_h11b_type_adapter_validate_json_ist_fail_closed(tmp_path):
    """M15 (Blindpruefer-Mutationstest): die TypeAdapter-Methodenliste auf
    `("validate_python",)` zu verkuerzen blieb GRUEN, weil H11 nur
    `.validate_python(...)` testete. Eigener Rot-Beweis fuer
    `.validate_json(...)`."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "from pydantic import TypeAdapter\n"
            "\n"
            "\n"
            "def _rotbeweis_h11b_type_adapter_json(roh):\n"
            "    return TypeAdapter(SyncLogEntry).validate_json(roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="TypeAdapter"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_h12_partial_alias_ist_fail_closed(tmp_path):
    """H12 (#115): `functools.partial` unter einem Importalias
    (`from functools import partial as _p`) bleibt erfasst -- H6 deckte nur
    den unveraenderten bzw. modul-qualifizierten Namen ab."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "from functools import partial as _p\n"
            "\n"
            "\n"
            "_ROTBEWEIS_PARTIAL_ALIAS = _p(\n"
            "    SyncLogEntry, message_key='log_album_shared', message_params={'album': 'x', 'names': 'y'}\n"
            ")\n",
        ),
    )
    with pytest.raises(AssertionError, match="functools.partial auf SyncLogEntry"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_h13_subskript_zuweisung_ist_fail_closed(tmp_path):
    """H13 (#115): `eintrag.message_params["album"] = "anders"` nach der
    Konstruktion -- die Attribut-Basis traegt `Load` (sie wird nur gelesen,
    um das Dict zu bekommen), `visit_Subscript` prueft die Basis separat."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_h13_subskript():\n"
            "    eintrag = SyncLogEntry(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde',\n"
            "        status='error',\n"
            "        message_key='log_album_shared',\n"
            "        message_params={'album': 'x', 'names': 'y'},\n"
            "    )\n"
            "    eintrag.message_params['album'] = 'anders'\n"
            "    return eintrag\n",
        ),
    )
    with pytest.raises(AssertionError, match=r"Subskript-Zuweisung auf \.message_params"):
        pruefe_vertrag(backend_kopie)


# ── Nacharbeit 1 (#115): del-Zweige (M02/M03, Blindpruefer-Mutationstest) ───


def test_rotbeweis_del_auf_message_key_direkt_ist_fail_closed(tmp_path):
    """M03: `visit_Attribute` ohne `Del` (nur `Store`) blieb an Nacharbeit 3
    GRUEN, weil kein Test je ein `del eintrag.message_key` (statt einer
    Subskript-Loeschung) ausprobiert hat."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_del_attribut():\n"
            "    eintrag = SyncLogEntry(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde',\n"
            "        status='error',\n"
            "        message_key='log_album_shared',\n"
            "        message_params={'album': 'x', 'names': 'y'},\n"
            "    )\n"
            "    del eintrag.message_key\n"
            "    return eintrag\n",
        ),
    )
    with pytest.raises(AssertionError, match=r"Zugriff auf \.message_key"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_del_auf_message_params_subskript_ist_fail_closed(tmp_path):
    """M02: `visit_Subscript` ohne `Del` (nur `Store`) blieb an Nacharbeit 3
    GRUEN, weil H13 nur eine Subskript-ZUWEISUNG testete, keine
    Subskript-LOESCHUNG."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_del_subskript():\n"
            "    eintrag = SyncLogEntry(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde',\n"
            "        status='error',\n"
            "        message_key='log_album_shared',\n"
            "        message_params={'album': 'x', 'names': 'y'},\n"
            "    )\n"
            "    del eintrag.message_params['names']\n"
            "    return eintrag\n",
        ),
    )
    with pytest.raises(AssertionError, match=r"Subskript-Zuweisung auf \.message_params"):
        pruefe_vertrag(backend_kopie)


# ── Nacharbeit 1 (#115): Alias-Fixpunkt (M11) + Geltungsbereich ─────────────


def test_rotbeweis_alias_fixpunkt_ueber_zwei_schritte_ist_fail_closed(tmp_path):
    """M11: Ohne die Fixpunkt-Iteration (nur EIN Durchlauf) blieb eine
    Alias-KETTE, deren zweites Glied VOR ihrer eigenen Quelle im Quelltext
    steht (`_B = _A` vor `_A = SyncLogEntry`), unentdeckt -- `_B` wurde in
    einem einzigen Durchlauf nie aufgeloest. Reihenfolge exakt wie in der
    Gegenpruefer-Sonde "Fixpunkt umgekehrt"."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_alias_kette(roh):\n"
            "    return _B(**roh)\n"
            "\n"
            "\n"
            "_B = _A\n"
            "_A = SyncLogEntry\n",
        ),
    )
    with pytest.raises(AssertionError, match="ohne message_key"):
        pruefe_vertrag(backend_kopie)


def test_sonde_lokaler_alias_in_anderer_funktion_erzeugt_keinen_fehlalarm(tmp_path):
    """Sonde (GRUEN, darf NICHT werfen): KLEIN-Fund "Aliase dateiweit ohne
    Geltungsbereich". `k = SyncLogEntry` in `_f1` (dort nie aufgerufen) darf
    NICHT dazu fuehren, dass `k(**roh)` in der VOELLIG ANDEREN Funktion `_f2`
    -- wo `k` lokal `dict` bedeutet -- faelschlich als SyncLogEntry-
    Konstruktion ohne message_key gemeldet wird. Exakt die Gegenpruefer-Sonde
    "Fehlalarm Scope"."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _sonde_scope_f1():\n"
            "    k = SyncLogEntry\n"
            "    return k\n"
            "\n"
            "\n"
            "def _sonde_scope_f2(roh):\n"
            "    k = dict\n"
            "    return k(**roh)\n",
        ),
    )
    pruefe_vertrag(backend_kopie)  # darf NICHT werfen


def test_rotbeweis_alias_ueber_modulqualifizierten_wert_ist_fail_closed(tmp_path):
    """Restform (#115, Nacharbeit 1): `_E = mm.SyncLogEntry` (ein
    modulqualifizierter Wert als Alias-Quelle, nicht nur ein nackter Name)."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "import models.match as mm\n"
            "\n"
            "_E = mm.SyncLogEntry\n"
            "\n"
            "\n"
            "def _rotbeweis_alias_modulqualifiziert(roh):\n"
            "    return _E(**roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="ohne message_key"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_alias_mit_annotation_ist_fail_closed(tmp_path):
    """Restform (#115, Nacharbeit 1): `_E: type = SyncLogEntry` (AnnAssign)."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "_E: type = SyncLogEntry\n"
            "\n"
            "\n"
            "def _rotbeweis_alias_annotiert(roh):\n"
            "    return _E(**roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="ohne message_key"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_alias_aus_tupel_zuweisung_ist_fail_closed(tmp_path):
    """Restform (#115, Nacharbeit 1): `_E, _x = SyncLogEntry, 1`."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "_E, _x = SyncLogEntry, 1\n"
            "\n"
            "\n"
            "def _rotbeweis_alias_tupel(roh):\n"
            "    return _E(**roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="ohne message_key"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_verkettete_zuweisung_ist_fail_closed(tmp_path):
    """Restform (#115, Nacharbeit 1): `_A = _B = SyncLogEntry` (mehrere
    Ziele derselben Zuweisung)."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "_A = _B = SyncLogEntry\n"
            "\n"
            "\n"
            "def _rotbeweis_kette(roh):\n"
            "    return _B(**roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="ohne message_key"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_partial_bare_alias_ist_fail_closed(tmp_path):
    """Restform (#115, Nacharbeit 1): `_pp = partial` (Namens-Alias auf den
    bereits importierten `partial`, nicht nur ein Importalias wie H12)."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "from functools import partial\n"
            "\n"
            "_pp = partial\n"
            "\n"
            "_ROTBEWEIS_PARTIAL_BARE_ALIAS = _pp(\n"
            "    SyncLogEntry, message_key='log_album_shared', message_params={'album': 'x', 'names': 'y'}\n"
            ")\n",
        ),
    )
    with pytest.raises(AssertionError, match="functools.partial auf SyncLogEntry"):
        pruefe_vertrag(backend_kopie)


# ── Nacharbeit 1 (#115): dynamische Konstruktion (Gegenpruefer-Skizze) ──────


def test_rotbeweis_type_vorlage_konstruktion_ist_fail_closed(tmp_path):
    """`type(vorlage)(**roh)`: die Gegenpruefer-Sonde bestaetigt -- genau EIN
    `type(...)`-Aufruf im heutigen Backend, kein `type(x)(...)`-Aufruf --,
    dass diese Restform ohne Fehlalarm gefangen werden kann (Skizze in
    `gegen/S5/k1fix`)."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_type_konstruktion(vorlage, roh):\n"
            "    return type(vorlage)(**roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="ohne message_key"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_dunder_class_konstruktion_ist_fail_closed(tmp_path):
    """`vorlage.__class__(**roh)`: dieselbe Kategorie wie `type(vorlage)(...)`,
    gemessen 0 Vorkommen im heutigen Backend."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_dunder_class(vorlage, roh):\n"
            "    return vorlage.__class__(**roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="ohne message_key"):
        pruefe_vertrag(backend_kopie)


# ── Nacharbeit 1 (#115): weitere kategorische Restformen ───────────────────


def test_rotbeweis_construct_ist_fail_closed(tmp_path):
    """`SyncLogEntry.construct(**roh)`: Pydantic-v1-Altform von
    `model_construct`, dieselbe Begruendung (baut ohne Validierung)."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_construct(roh):\n"
            "    return SyncLogEntry.construct(**roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="construct"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_parse_obj_ist_fail_closed(tmp_path):
    """`SyncLogEntry.parse_obj(roh)`: Pydantic-v1-Altform von `model_validate`."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_parse_obj(roh):\n"
            "    return SyncLogEntry.parse_obj(roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="parse_obj"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_model_validate_strings_ist_fail_closed(tmp_path):
    """`SyncLogEntry.model_validate_strings(roh)`."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_model_validate_strings(roh):\n"
            "    return SyncLogEntry.model_validate_strings(roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="model_validate_strings"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_dict_message_params_keyword_ist_fail_closed(tmp_path):
    """`dict(message_params=...)`: deckt `model_copy(update=dict(
    message_params=...))` ab -- ein Schluesselwortname ist ein Python-String
    auf dem `ast.keyword`-Knoten, kein `ast.Constant`, und entgeht deshalb
    dem reinen Literal-Scan."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_dict_keyword():\n"
            "    eintrag = SyncLogEntry(\n"
            "        id='sonde', timestamp='sonde', action='sonde', details='sonde',\n"
            "        status='error',\n"
            "        message_key='log_album_shared',\n"
            "        message_params={'album': 'x', 'names': 'y'},\n"
            "    )\n"
            "    return eintrag.model_copy(update=dict(message_params={'anders': 1}))\n",
        ),
    )
    with pytest.raises(AssertionError, match="dict\\(...\\)-Aufruf mit Schluesselwort 'message_params'"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_type_adapter_list_huelle_ist_fail_closed(tmp_path):
    """`TypeAdapter(list[SyncLogEntry]).validate_python(roh)`: die Klasse
    steht im `Subscript`-`slice`, nicht direkt am Aufrufziel."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "from pydantic import TypeAdapter\n"
            "\n"
            "\n"
            "def _rotbeweis_type_adapter_liste(roh):\n"
            "    return TypeAdapter(list[SyncLogEntry]).validate_python(roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="TypeAdapter"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_type_adapter_validate_strings_ist_fail_closed(tmp_path):
    """`TypeAdapter(SyncLogEntry).validate_strings(roh)`."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "from pydantic import TypeAdapter\n"
            "\n"
            "\n"
            "def _rotbeweis_type_adapter_strings(roh):\n"
            "    return TypeAdapter(SyncLogEntry).validate_strings(roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="TypeAdapter"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_type_adapter_import_alias_ist_fail_closed(tmp_path):
    """`from pydantic import TypeAdapter as TA` -- ein Importalias fuer
    `TypeAdapter` selbst, nicht nur fuer `SyncLogEntry`."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "from pydantic import TypeAdapter as TA\n"
            "\n"
            "\n"
            "def _rotbeweis_type_adapter_import_alias(roh):\n"
            "    return TA(SyncLogEntry).validate_python(roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="TypeAdapter"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_type_adapter_variablen_alias_ist_fail_closed(tmp_path):
    """`ta = TypeAdapter(SyncLogEntry); ta.validate_python(roh)` -- der
    Adapter wird erst einer Variable zugewiesen, bevor er aufgerufen wird."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "from pydantic import TypeAdapter\n"
            "\n"
            "_ta = TypeAdapter(SyncLogEntry)\n"
            "\n"
            "\n"
            "def _rotbeweis_type_adapter_variable(roh):\n"
            "    return _ta.validate_python(roh)\n",
        ),
    )
    with pytest.raises(AssertionError, match="TypeAdapter"):
        pruefe_vertrag(backend_kopie)


# ── Nacharbeit 1 (#115): die restaurierte Strenge selbst (frueher "Sonden") ─
#
# Die Erstrunde zu #115 hatte an dieser Stelle vier GRUENE Sonden fuer eine
# pauschale Lese-Erlaubnis (lesender Attributzugriff, `@field_validator`,
# `model_dump(exclude=...)`, `getattr`/`hasattr`). Das Panel hat diese
# pauschale Erlaubnis verworfen (siehe Docstring, BLOCKER 1+2) -- dieselben
# vier Formen sind jetzt Rot-Beweise fuer die restaurierte Grundregel: ohne
# eine benannte Lese-Ausnahme ist JEDES Lesen verboten.


def test_rotbeweis_lesender_zugriff_ohne_benannte_ausnahme_ist_fail_closed(tmp_path):
    """Frueher `test_sonde_lesender_attributzugriff_ist_erlaubt` (GRUEN).
    `_BENANNTE_LESE_AUSNAHMEN` ist im ausgelieferten Stand LEER (0 berechtigte
    Nutzungen, siehe Docstring) -- derselbe Vergleichsoperand aus #115,
    Punkt 1, Beispiel 1 bleibt deshalb verboten, bis er dort eingetragen ist."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _rotbeweis_lesender_zugriff(eintraege, schluessel):\n"
            "    return [e for e in eintraege if e.message_key == schluessel]\n",
        ),
    )
    with pytest.raises(AssertionError, match=r"lesender Zugriff auf \.message_key ist fail-closed verboten"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_field_validator_ist_kein_lese_pfad_mehr(tmp_path):
    """Frueher `test_sonde_field_validator_dekorator_ist_erlaubt` (GRUEN).
    `@field_validator("message_key")` SCHREIBT (der Rueckgabewert wird der
    neue Feldwert, siehe Docstring BLOCKER 2) und hat deshalb keinen
    Sonderstatus mehr -- die literale Zeichenkette bleibt ein Verstoss wie
    jede andere."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "from pydantic import field_validator\n"
            "\n"
            "\n"
            "class _SondeValidator:\n"
            "    @field_validator('message_key')\n"
            "    @classmethod\n"
            "    def _pruefe(cls, wert):\n"
            "        return wert\n",
        ),
    )
    with pytest.raises(AssertionError, match="literale Zeichenkette 'message_key'"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_model_dump_exclude_ist_kein_lese_pfad_mehr(tmp_path):
    """Frueher `test_sonde_model_dump_exclude_ist_erlaubt` (GRUEN).
    `model_dump(exclude={"message_params"})` erzeugt einen Log-Eintrag ohne
    Parameter (Docstring BLOCKER 2) und hat deshalb keinen Sonderstatus mehr."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _sonde_model_dump(eintrag):\n"
            "    return eintrag.model_dump(exclude={'message_params'})\n",
        ),
    )
    with pytest.raises(AssertionError, match="literale Zeichenkette 'message_params'"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_getattr_hasattr_literal_ist_kein_lese_pfad_mehr(tmp_path):
    """Frueher `test_sonde_getattr_hasattr_sind_erlaubt` (GRUEN). Die
    Namens-Shadowing-Luecke aus BLOCKER 2 (`def _p(e, getattr=setattr)`)
    entfaellt strukturell, weil `getattr`/`hasattr` keinen namensbasierten
    Sonderstatus mehr haben -- die literalen Zeichenketten bleiben Verstoesse."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _sonde_getattr_hasattr(eintrag):\n"
            "    if hasattr(eintrag, 'message_key'):\n"
            "        return getattr(eintrag, 'message_key')\n"
            "    return None\n",
        ),
    )
    with pytest.raises(AssertionError, match="literale Zeichenkette 'message_key'"):
        pruefe_vertrag(backend_kopie)


# ── Nacharbeit 1 (#115): die benannte LESE-Ausnahme selbst ─────────────────
#
# `_BENANNTE_LESE_AUSNAHMEN` ist im ausgelieferten Stand leer -- die folgenden
# vier Tests spielen den Mechanismus ueber eine EIGENE, ERFUNDENE Sonden-
# Ausnahme durch (`monkeypatch`), analog zum bestehenden Test fuer die
# Schreib-Ausnahme (`test_rotbeweis_veraltete_ausnahme_wird_erkannt`).


def test_sonde_benannte_lese_ausnahme_erlaubt_die_bewiesene_stelle(tmp_path, monkeypatch):
    """Sonde (GRUEN): eine benannte Lese-Ausnahme fuer GENAU die Funktion, in
    der der beweisbare Vergleichsoperand steht, macht diese EINE Stelle
    gruen -- der erlaubte Weg aus #115, Punkt 1."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _sonde_lese_ausnahme_erlaubt(eintraege, schluessel):\n"
            "    return [e for e in eintraege if e.message_key == schluessel]\n",
        ),
    )
    monkeypatch.setattr(
        _DIESES_MODUL,
        "_BENANNTE_LESE_AUSNAHMEN",
        {
            ("backend/services/sync_service.py", None, "_sonde_lese_ausnahme_erlaubt"): (
                "Sonde: filtert eine Liste bereits konstruierter Eintraege nach ihrem "
                "message_key -- ein an einem Vergleichsoperanden beweisbares Lesen."
            )
        },
    )
    pruefe_vertrag(backend_kopie)  # darf NICHT werfen


def test_rotbeweis_lese_ausnahme_gilt_nicht_fuer_andere_funktion(tmp_path, monkeypatch):
    """Rot-Beweis: dieselbe beweisbare Form in einer ANDEREN, nicht gelisteten
    Funktion bleibt verboten -- die Ausnahme wirkt nur an ihrer eigenen Stelle."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _sonde_lese_ausnahme_erlaubt(eintraege, schluessel):\n"
            "    return [e for e in eintraege if e.message_key == schluessel]\n"
            "\n"
            "\n"
            "def _andere_funktion_gleiche_form(eintraege, schluessel):\n"
            "    return [e for e in eintraege if e.message_key == schluessel]\n",
        ),
    )
    monkeypatch.setattr(
        _DIESES_MODUL,
        "_BENANNTE_LESE_AUSNAHMEN",
        {("backend/services/sync_service.py", None, "_sonde_lese_ausnahme_erlaubt"): "Sonde."},
    )
    with pytest.raises(AssertionError, match=r"lesender Zugriff auf \.message_key ist fail-closed verboten"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_lese_ausnahme_ohne_beweisbare_form_bleibt_verboten(tmp_path, monkeypatch):
    """Rot-Beweis: die Ausnahme deckt NUR die eine erkannte Form (Compare-
    Operand) ab -- ein zweiter, andersartiger lesender Zugriff (hier: kein
    Vergleich, sondern eine reine Weitergabe) an DERSELBEN benannten Stelle
    bleibt verboten. Kein Freibrief fuer die ganze Funktion."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _sonde_lese_ausnahme_erlaubt(eintrag):\n"
            "    return eintrag.message_key\n",
        ),
    )
    monkeypatch.setattr(
        _DIESES_MODUL,
        "_BENANNTE_LESE_AUSNAHMEN",
        {("backend/services/sync_service.py", None, "_sonde_lese_ausnahme_erlaubt"): "Sonde."},
    )
    with pytest.raises(AssertionError, match=r"lesender Zugriff auf \.message_key ist fail-closed verboten"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_veraltete_lese_ausnahme_wird_erkannt(tmp_path, monkeypatch):
    """Rot-Beweis: eine gelistete Stelle, an der die beweisbare Form nicht
    (mehr) vorkommt, ist selbst ein Verstoss ("veraltete Lese-Ausnahme")."""
    backend_kopie = _kopiere_backend_mit_mutation(
        tmp_path,
        lambda kopie: _sonde_anhaengen(
            kopie,
            "def _sonde_lese_ausnahme_erlaubt():\n"
            "    return 'nichts mit message_key oder message_params hier'\n",
        ),
    )
    monkeypatch.setattr(
        _DIESES_MODUL,
        "_BENANNTE_LESE_AUSNAHMEN",
        {("backend/services/sync_service.py", None, "_sonde_lese_ausnahme_erlaubt"): "Sonde."},
    )
    with pytest.raises(AssertionError, match="veraltete Lese-Ausnahme"):
        pruefe_vertrag(backend_kopie)
