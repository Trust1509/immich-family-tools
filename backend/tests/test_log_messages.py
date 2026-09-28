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

WAS DIESER WAECHTER ERFASST (gemessen, Stand dieser Runde):
  - jede Konstruktion von `SyncLogEntry` oder einer (transitiven)
    Unterklasse, ob als nackter Name, ueber einen Modulnamen oder ueber
    einen lokalen Importalias;
  - fehlendes, nicht-woertliches oder falsch geformtes `message_key`/
    `message_params` an einer solchen Konstruktion;
  - jeden Attribut-Zugriff auf `.message_key`/`.message_params` ausserhalb
    einer Konstruktion (Lesen, Schreiben, `+=`, `.pop()`, `.update()`,
    Subskript);
  - jedes literale Vorkommen der Zeichenketten `"message_key"`/
    `"message_params"` irgendwo im Baum, ausserhalb der einen benannten
    Ausnahme;
  - `functools.partial(SyncLogEntry, ...)` und
    `SyncLogEntry.model_validate(...)`/`.model_validate_json(...)`
    (kategorisch, unabhaengig vom Inhalt).

WAS ER NICHT ERFASST (bekannte Restformen, keine Vollstaendigkeit behauptet):
  - `getattr(x, "message_" + "key")` oder eine andere zur Laufzeit erst
    zusammengesetzte Zeichenkette (kein woertlicher `ast.Constant` mehr);
  - Reflection ueber `__dict__`/`vars(x)` ohne den Namen als Zeichenkette;
  - ein zweites, semantisch anderes Attribut, das zufaellig auch
    `message_key` heisst, an einer voellig anderen Klasse (der Scan ist
    NAMENSBASIERT auf dem ganzen Baum, nicht typgebunden).
"""

from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path
from typing import Callable, Optional

import pytest

WURZEL = Path(__file__).resolve().parents[2]
BACKEND_DIR = WURZEL / "backend"
VERTRAG_PFAD = WURZEL / "frontend" / "src" / "logMessages.contract.json"

# Verzeichnisse, deren Python-Dateien nicht durchsucht werden: Tests selbst
# (eigene, ausgedachte Schluessel wie die Sonden dieser Datei) und
# Cache-Verzeichnisse.
_AUSGESCHLOSSENE_VERZEICHNISNAMEN = {"tests", "__pycache__"}

# Die EINE benannte Ausnahme vom Fail-Closed-Vertrag: (Datei relativ zur
# Repo-Wurzel, Klassenname oder None fuer Modulebene, Funktionsname) ->
# Begruendung. Der Schluessel traegt seit Nacharbeit 2 auch die Klasse, damit
# eine ZWEITE Klasse mit gleichnamiger Methode NICHT versehentlich
# mitgemeint ist. Verlangt wird zudem GENAU EIN Treffer mit AUSSCHLIESSLICH
# der `**`-Erweiterung (siehe `_SyncLogPruefer.visit_Call`) — ein zweiter
# `**`-Aufruf in derselben Funktion oder gar keiner sind beide ein Verstoss
# (siehe `_pruefe_ausnahmen_getroffen`).
_BENANNTE_AUSNAHMEN: dict[tuple[str, Optional[str], str], str] = {
    ("backend/services/config_store.py", "ConfigStore", "_build_log_entries"): (
        "SyncLogEntry(**entry) baut ein Modell aus einem bereits in "
        "accounts.json gespeicherten Protokolleintrag wieder auf "
        "(Alt-Format-Vertraeglichkeit) - keine Stelle, die einen NEUEN "
        "message_key waehlt."
    ),
}

_LITERALE_NAMEN = ("message_key", "message_params")


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


def _sammle_lokale_aliase(baum: ast.Module, bekannte_namen: set[str]) -> set[str]:
    """Lokale Namen aus `from ... import X as Y`, wenn `X` ein bekannter
    SyncLogEntry-Name ist. Ein Modul-Alias (`import models.match as mm`)
    braucht das NICHT: `mm.SyncLogEntry(...)` wird bereits ueber
    `_rechter_bezeichner` (den Attributnamen) erkannt."""
    aliase: set[str] = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.ImportFrom):
            for alias in knoten.names:
                if alias.name in bekannte_namen:
                    aliase.add(alias.asname or alias.name)
    return aliase


class _SyncLogPruefer(ast.NodeVisitor):
    """Fail-closed-Pruefung EINER Datei. Siehe Moduldocstring fuer die
    vollstaendige Liste der erfassten und der bekannten NICHT erfassten
    Formen."""

    def __init__(self, relativer_pfad: str, gueltige_namen: set[str]):
        self.relativer_pfad = relativer_pfad
        self.gueltige_namen = gueltige_namen
        self._funktionsstapel: list[str] = ["<Modul>"]
        self._klassenstapel: list[Optional[str]] = [None]
        self.gefunden: dict[str, set[frozenset[str]]] = {}
        self.verstoesse: list[str] = []
        self.ausnahme_treffer: dict[tuple[str, Optional[str], str], int] = {}

    def _ort(self, zeile: int) -> str:
        return f"{self.relativer_pfad}:{zeile}"

    def _aktueller_schluessel(self) -> tuple[str, Optional[str], str]:
        return (self.relativer_pfad, self._klassenstapel[-1], self._funktionsstapel[-1])

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

    def visit_Attribute(self, knoten: ast.Attribute) -> None:  # noqa: N802
        """JEDER Zugriff auf `.message_key`/`.message_params` ist ein
        Verstoss — Lesen, Schreiben, `+=` (dessen Ziel ebenfalls ein
        `Attribute`-Knoten ist), `.pop()`/`.update()` (deren Basis
        `eintrag.message_params` derselbe innere `Attribute`-Knoten ist) und
        eine Subskript-Zuweisung (deren Basis ebenso). Keine Ausnahme: die
        eine erlaubte Konstruktion tauscht `message_key` nie als Attribut
        aus, sondern nur als `**`-entpacktes Schluesselwort."""
        if knoten.attr in _LITERALE_NAMEN:
            self.verstoesse.append(
                f"{self._ort(knoten.lineno)} Zugriff auf .{knoten.attr} ausserhalb einer Konstruktion "
                "ist fail-closed verboten"
            )
        self.generic_visit(knoten)

    def visit_Constant(self, knoten: ast.Constant) -> None:  # noqa: N802
        """Jedes literale Vorkommen von genau `"message_key"` oder
        `"message_params"` als STRING-WERT — nie als Teil eines laengeren
        Satzes (ein Docstring, der das Wort erwaehnt, hat einen anderen,
        laengeren `Constant`-Wert und trifft hier nicht). Deckt `setattr`,
        `getattr`, `hasattr`, `entry.setdefault("message_key", ...)` und ein
        dict-Literal wie `model_copy(update={"message_key": ...})` ab, ohne
        diese Formen einzeln zu benennen."""
        if isinstance(knoten.value, str) and knoten.value in _LITERALE_NAMEN:
            self.verstoesse.append(
                f"{self._ort(knoten.lineno)} literale Zeichenkette '{knoten.value}' ausserhalb der "
                "erlaubten Schluesselwort-Form ist fail-closed verboten"
            )

    def visit_Call(self, knoten: ast.Call) -> None:  # noqa: N802
        rechter_name = _rechter_bezeichner(knoten.func)

        # Kategorische Verbote, unabhaengig von etwaigen Schluesselwoertern:
        # Die spaetere Bindung eines `partial` und beliebige Rohdaten an
        # `model_validate*` sind statisch nicht pruefbar.
        if rechter_name == "partial" and knoten.args:
            if _rechter_bezeichner(knoten.args[0]) in self.gueltige_namen:
                self.verstoesse.append(
                    f"{self._ort(knoten.lineno)} functools.partial auf SyncLogEntry/Unterklasse ist "
                    "fail-closed verboten (die spaetere Bindung ist statisch nicht pruefbar)"
                )
                self.generic_visit(knoten)
                return
        if isinstance(knoten.func, ast.Attribute) and knoten.func.attr in ("model_validate", "model_validate_json"):
            if _rechter_bezeichner(knoten.func.value) in self.gueltige_namen:
                self.verstoesse.append(
                    f"{self._ort(knoten.lineno)} {knoten.func.attr}(...) auf SyncLogEntry/Unterklasse ist "
                    "fail-closed verboten (keine pruefbare Schluesselwort-Form)"
                )
                self.generic_visit(knoten)
                return

        ist_konstruktion = rechter_name in self.gueltige_namen
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
                )
        self.generic_visit(knoten)

    def _pruefe_und_sammle(
        self,
        *,
        message_key_knoten: Optional[ast.expr],
        message_params_knoten: Optional[ast.expr],
        hat_message_params_schluessel: bool,
        zeile: int,
    ) -> None:
        ort = self._ort(zeile)
        if message_key_knoten is None:
            self.verstoesse.append(f"{ort} SyncLogEntry-Konstruktion ohne message_key")
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
    # (Rot-Beweise) eine Kopie unter tmp_path ist — sonst wuerde die benannte
    # Ausnahme dort nie zutreffen, weil ihr Schluessel `backend/services/...`
    # lautet, nicht `services/...`.
    ist_kopie = wurzel != BACKEND_DIR

    gefunden: dict[str, set[frozenset[str]]] = {}
    verstoesse: list[str] = []
    ausnahme_treffer: dict[tuple[str, Optional[str], str], int] = {}

    for datei, baum in baeume.items():
        if ist_kopie:
            relativer_pfad = "backend/" + str(datei.relative_to(wurzel)).replace("\\", "/")
        else:
            relativer_pfad = str(datei.relative_to(WURZEL)).replace("\\", "/")
        gueltige_namen = gueltige_namen_global | _sammle_lokale_aliase(baum, gueltige_namen_global)
        pruefer = _SyncLogPruefer(relativer_pfad, gueltige_namen)
        pruefer.visit(baum)
        verstoesse.extend(pruefer.verstoesse)
        for schluessel, anzahl in pruefer.ausnahme_treffer.items():
            ausnahme_treffer[schluessel] = ausnahme_treffer.get(schluessel, 0) + anzahl
        for schluessel, mengen in pruefer.gefunden.items():
            gefunden.setdefault(schluessel, set()).update(mengen)

    for schluessel, begruendung in _BENANNTE_AUSNAHMEN.items():
        anzahl = ausnahme_treffer.get(schluessel, 0)
        if anzahl == 0:
            verstoesse.append(f"veraltete Ausnahme: {schluessel} wurde nicht getroffen ({begruendung})")
        elif anzahl > 1:
            verstoesse.append(f"Ausnahme {schluessel} mehrfach getroffen ({anzahl}x) statt genau einmal")

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

    Seit Nacharbeit 2 greift hier der allgemeine Literal-Scan
    (`visit_Constant`), nicht mehr eine eigens dafuer gebaute
    dict-Erkennung — die literale Zeichenkette `"message_key"` ist ausserhalb
    der einen erlaubten `**`-Konstruktion IMMER ein Verstoss, unabhaengig
    davon, in welchem Container sie steht.
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
    with pytest.raises(AssertionError, match=r"Zugriff auf \.message_params"):
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
