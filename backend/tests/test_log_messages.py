"""Fail-closed-Waechter fuer den Vertrag der Protokollmeldungen.

NACHARBEIT 1 ZU #94 — WARUM DIE ERSTE FASSUNG NICHT REICHTE
-------------------------------------------------------------
Die erste Fassung verglich zwei UNABHAENGIGE Erfassungen (Backend per
Syntaxbaum, Frontend per Regex auf den Quelltext) direkt gegeneinander. Der
Hauptagent hat das reproduziert: Eine deutsche Vorlage von
`log_album_created`, umgeschrieben zu `(q) => ... ${q.acount} ...`, blieb bei
allen sieben damaligen Tests gruen — die volle Suite lief mit 268 gruenen
Tests durch, das Protokoll zeigte "undefined". Ursache: Eine Regex auf
Quelltext sieht nur, dass IRGENDEIN `p.<name>` vorkommt, nicht ob es der
RICHTIGE Name ist, wenn der Parameter selbst anders heisst (`q` statt `p`),
und sie sieht Vorlagen mit Destrukturierung, `function`-Schreibweise oder
Kommentaren (ein auskommentierter Eintrag zaehlte als vorhanden) gar nicht
oder falsch.

ZWEI AENDERUNGEN BEHEBEN DAS STRUKTURELL, NICHT DURCH MEHR MUSTER:

1. Ein VERTRAG als eigene Datei (`frontend/src/logMessages.contract.json`,
   Schluessel -> sortierte Parameterliste). Beide Seiten pruefen gegen
   DIESELBE Datei, es gibt keine zweite Erfassung mehr, die unabhaengig
   auseinanderlaufen kann.

2. Backend: FAIL-CLOSED statt Symboltabelle. Jede `SyncLogEntry(...)`-
   Konstruktion und jeder Aufruf mit einem `message_key`-Schluesselwort MUSS
   `message_key` als woertliche `"log_..."`-Zeichenkette und `message_params`
   als woertliches dict mit woertlichen Schluesseln tragen — eine ueber eine
   Konstante, eine Nachschlagetabelle, ein Funktionsargument oder einen
   f-String gebauter Schluessel ist ein VERSTOSS, keine aufgeloeste
   Fundstelle mehr (siehe `test_rotbeweis_*` unten). Die Frontend-Haelfte
   dieses Vertrags steht in `frontend/src/logMessages.contract.test.ts` und
   misst zur LAUFZEIT (Proxy), welche Eigenschaften eine Vorlage tatsaechlich
   liest — Syntaxform und Kommentare sind dort per Konstruktion irrelevant,
   weil ein auskommentierter Eintrag zur Laufzeit schlicht nicht existiert.

GEMESSEN (dieser Slice, Nacharbeit 1): Alle 37 heutigen `SyncLogEntry(...)`-
Konstruktionen in `backend/services/sync_service.py` sind woertlich. Die
einzige nicht-woertliche Konstruktion im ganzen `backend/`-Baum ist
`backend/services/config_store.py::_build_log_entries`
(`SyncLogEntry(**entry)`) — sie liest bereits gespeicherte Protokolleintraege
aus `accounts.json` wieder ein und waehlt keinen neuen Schluessel. Sie ist
eine BENANNTE Ausnahme (Datei+Funktion, nicht ein `**`-Muster generell): ein
`**`-Aufruf an jeder ANDEREN Stelle bleibt ein Verstoss (siehe
`test_rotbeweis_doppelstern_ausserhalb_der_ausnahme_ist_fail_closed`).
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

# Die EINE benannte Ausnahme vom Fail-Closed-Vertrag (Datei relativ zur
# Repo-Wurzel, Funktionsname) -> Begruendung. Bewusst nicht ueber ein Muster
# (z. B. "jedes `**`"), damit ein `**`-Aufruf an einer ANDEREN Stelle ein
# Verstoss bleibt. Wird die Ausnahme in einem Lauf NICHT getroffen, ist das
# selbst ein Verstoss (siehe `backend_sendestellen`) — eine Ausnahme, die
# niemand mehr braucht, verschwindet dadurch nicht unbemerkt aus dem Bild.
_BENANNTE_AUSNAHMEN: dict[tuple[str, str], str] = {
    ("backend/services/config_store.py", "_build_log_entries"): (
        "SyncLogEntry(**entry) baut ein Modell aus einem bereits in "
        "accounts.json gespeicherten Protokolleintrag wieder auf "
        "(Alt-Format-Vertraeglichkeit) - keine Stelle, die einen NEUEN "
        "message_key waehlt."
    ),
}


def lade_vertrag() -> dict[str, list[str]]:
    return json.loads(VERTRAG_PFAD.read_text("utf-8"))


class _SyncLogPruefer(ast.NodeVisitor):
    """Fail-closed-Pruefung EINER Datei.

    Zwei Fundorte fuer `message_key`:
      (a) als Schluesselwort eines Aufrufs (`SyncLogEntry(message_key=...)`
          oder jeder andere Aufruf mit diesem Schluesselwort),
      (b) als Eintrag in einem dict-Literal irgendwo in der Datei (deckt
          `irgendwas.model_copy(update={"message_key": ...})` ab, wo
          `message_key` kein direktes Schluesselwort des Aufrufs waere und
          Fundort (a) allein daran vorbeisaehe).
    Dazu eine dritte Pruefung: eine nachtraegliche Zuweisung
    `x.message_key = ...` ausserhalb einer Konstruktion ist immer ein
    Verstoss, unabhaengig vom zugewiesenen Wert.
    """

    def __init__(self, relativer_pfad: str):
        self.relativer_pfad = relativer_pfad
        self._funktionsstapel: list[str] = ["<Modul>"]
        self.gefunden: dict[str, set[frozenset[str]]] = {}
        self.verstoesse: list[str] = []
        self.getroffene_ausnahmen: set[tuple[str, str]] = set()

    def _aktuelle_funktion(self) -> str:
        return self._funktionsstapel[-1]

    def visit_FunctionDef(self, knoten: ast.FunctionDef) -> None:  # noqa: N802
        self._funktionsstapel.append(knoten.name)
        self.generic_visit(knoten)
        self._funktionsstapel.pop()

    def visit_AsyncFunctionDef(self, knoten: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._funktionsstapel.append(knoten.name)
        self.generic_visit(knoten)
        self._funktionsstapel.pop()

    def visit_Assign(self, knoten: ast.Assign) -> None:  # noqa: N802
        for ziel in knoten.targets:
            if isinstance(ziel, ast.Attribute) and ziel.attr in ("message_key", "message_params"):
                self.verstoesse.append(
                    f"{self.relativer_pfad}:{knoten.lineno} nachtraegliche Zuweisung an "
                    f".{ziel.attr} ausserhalb der Konstruktion ist fail-closed verboten"
                )
        self.generic_visit(knoten)

    def visit_Dict(self, knoten: ast.Dict) -> None:  # noqa: N802
        eintraege = {
            k.value: v
            for k, v in zip(knoten.keys, knoten.values)
            if isinstance(k, ast.Constant) and isinstance(k.value, str)
        }
        if "message_key" in eintraege:
            self._pruefe_und_sammle(
                message_key_knoten=eintraege.get("message_key"),
                message_params_knoten=eintraege.get("message_params"),
                hat_message_params_schluessel="message_params" in eintraege,
                zeile=knoten.lineno,
            )
        self.generic_visit(knoten)

    def visit_Call(self, knoten: ast.Call) -> None:  # noqa: N802
        ist_konstruktion = isinstance(knoten.func, ast.Name) and knoten.func.id == "SyncLogEntry"
        msg_key_kw = next((kw for kw in knoten.keywords if kw.arg == "message_key"), None)
        msg_params_kw = next((kw for kw in knoten.keywords if kw.arg == "message_params"), None)
        hat_doppelstern = any(kw.arg is None for kw in knoten.keywords)

        if ist_konstruktion or msg_key_kw is not None:
            ausnahme_schluessel = (self.relativer_pfad, self._aktuelle_funktion())
            if hat_doppelstern and msg_key_kw is None and ausnahme_schluessel in _BENANNTE_AUSNAHMEN:
                self.getroffene_ausnahmen.add(ausnahme_schluessel)
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
        ort = f"{self.relativer_pfad}:{zeile}"
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

    Jeder Verstoss (fehlendes `message_key`, ein nicht-woertlicher Wert, eine
    nachtraegliche Zuweisung, eine nicht getroffene benannte Ausnahme) landet
    in der Verstossliste, statt eine Fundstelle stillschweigend
    auszulassen. Der Aufrufer entscheidet, ob eine nicht-leere Verstossliste
    ein Testfehlschlag ist (Produktivpruefung) oder das erwartete Ergebnis
    (Rot-Beweis).
    """
    dateien = [
        datei
        for datei in sorted(wurzel.rglob("*.py"))
        if not _AUSGESCHLOSSENE_VERZEICHNISNAMEN & set(datei.relative_to(wurzel).parts[:-1])
    ]
    gefunden: dict[str, set[frozenset[str]]] = {}
    verstoesse: list[str] = []
    getroffene_ausnahmen: set[tuple[str, str]] = set()

    # Relativer Pfad IMMER gegen die echte Repo-Wurzel, auch wenn `wurzel`
    # (Rot-Beweise) eine Kopie unter tmp_path ist — sonst wuerde die benannte
    # Ausnahme dort nie zutreffen, weil ihr Schluessel `backend/services/...`
    # lautet, nicht `services/...`.
    ist_kopie = wurzel != BACKEND_DIR

    for datei in dateien:
        if ist_kopie:
            relativer_pfad = "backend/" + str(datei.relative_to(wurzel)).replace("\\", "/")
        else:
            relativer_pfad = str(datei.relative_to(WURZEL)).replace("\\", "/")
        pruefer = _SyncLogPruefer(relativer_pfad)
        pruefer.visit(ast.parse(datei.read_text("utf-8"), filename=str(datei)))
        verstoesse.extend(pruefer.verstoesse)
        getroffene_ausnahmen |= pruefer.getroffene_ausnahmen
        for schluessel, mengen in pruefer.gefunden.items():
            gefunden.setdefault(schluessel, set()).update(mengen)

    for (pfad, funktion), begruendung in _BENANNTE_AUSNAHMEN.items():
        if (pfad, funktion) not in getroffene_ausnahmen:
            verstoesse.append(f"veraltete Ausnahme: {pfad}::{funktion} wurde nicht getroffen ({begruendung})")

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
    Vergleichslogik. Eine Aushoehlung dieser Funktion (z. B. `==` zu `<=`
    geschwaecht) traefe dadurch automatisch auch jeden Rot-Beweis, der hier
    auf ein `pytest.raises` angewiesen ist.
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
    """Rot-Beweis: ein per Konstante gebauter Schluessel ist jetzt ein Verstoss.

    In der ERSTEN Fassung dieses Waechters (vor Nacharbeit 1) wurde genau
    dieser Fall ueber eine Symboltabelle AUFGELOEST und blieb gruen. Die neue
    Fail-Closed-Regel verlangt eine woertliche Zeichenkette an der
    Aufrufstelle selbst — die Symboltabelle ist ersatzlos entfernt.
    """
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
    """Rot-Beweis: die benannte Ausnahme gilt nur an IHRER Stelle, nicht ueberall.

    Waere die Ausnahme ein Muster ("jedes `**`ist erlaubt") statt eine
    benannte Datei+Funktion, wuerde dieser `**`-Aufruf durchrutschen. So
    fehlt ihm schlicht das `message_key`-Schluesselwort (das Unpacking
    liefert keins), und das ist ein Verstoss wie jeder andere.
    """
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
    with pytest.raises(AssertionError, match="nachtraegliche Zuweisung"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_message_key_versteckt_in_model_copy_update_wird_erfasst(tmp_path):
    """Rot-Beweis: `model_copy(update={"message_key": ...})` bleibt nicht unsichtbar.

    Fundort (a) (Aufruf-Schluesselwort) saehe hier nichts: `message_key`
    steht nicht als Schluesselwort von `.model_copy(...)`, sondern als
    Eintrag IN dem dict, das `update=` uebergeben wird. Fundort (b)
    (`visit_Dict`) deckt genau das ab.
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
    with pytest.raises(AssertionError, match="log_voellig_neu_via_model_copy"):
        pruefe_vertrag(backend_kopie)


def test_rotbeweis_veraltete_ausnahme_wird_erkannt(tmp_path):
    """Rot-Beweis: verschwindet die einzige Fundstelle der Ausnahme, faellt das auf.

    Ohne diese Pruefung koennte die Ausnahme nach einem Refactoring, das
    `_build_log_entries` entfernt oder umbenennt, stillschweigend zu einer
    UNBEGRUENDETEN Freikarte fuer die betroffene Datei werden.
    """

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
