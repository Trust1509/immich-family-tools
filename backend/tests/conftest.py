"""Laufzeitpruefung des Sync-Log-Vertrags -- Ergaenzung zur statischen
Pruefung in `test_log_messages.py` (#115, Nacharbeit 2).

WARUM ES DIESE DATEI JETZT GIBT
--------------------------------------------------------------------------
Die statische Pruefung (`backend/tests/test_log_messages.py`) liest den
Syntaxbaum und erkennt eine wachsende, aber prinzipiell unabschliessbare
Liste von Konstruktionsformen. Der Blindpruefer der Nacharbeit 1 hat 14
weitere, unerkannte Formen gemessen, darunter `cls(**roh)` in einer
Fabrikmethode, `e.__init__(**roh)`, ein Closure-Alias auf `SyncLogEntry`,
ein Klassenattribut-Alias, ein Re-Export in eine andere Datei und der
`response_model`-Weg von FastAPI. Jede dieser Formen ist syntaktisch
beliebig variierbar (ein neues Muster deckt immer nur genau diese eine
Variante ab) -- mehr AST-Muster schliessen diese Klasse strukturell nicht.

Diese Datei ergaenzt deshalb eine LAUFZEITPRUEFUNG: eine `autouse`-Fixture
haengt sich fuer die Dauer JEDES einzelnen Tests in `SyncLogEntry.
model_post_init` ein (siehe `backend/models/match.py`,
`_SYNC_LOG_LAUFZEIT_HAKEN`) und prueft JEDEN dabei entstehenden
`SyncLogEntry` gegen `frontend/src/logMessages.contract.json` -- unabhaengig
davon, UEBER WELCHEN WEG er konstruiert wurde. Ein Test, der waehrend seiner
Laufzeit eine vertragswidrige Konstruktion auslost, schlaegt fehl.

WAS SIE SIEHT UND WAS NICHT
--------------------------------------------------------------------------
Sie sieht JEDE Konstruktion, die WAEHREND EINES TESTS tatsaechlich
AUSGEFUEHRT wird -- unabhaengig vom syntaktischen Weg (`__init__`,
`model_validate`, `model_construct`, der `response_model`-Validierungspfad
von FastAPI, eine Unterklasse, die `model_post_init` nicht selbst
ueberschreibt). Sie sieht NICHT:

  - Code, der in KEINEM Test ausgefuehrt wird (die statische Pruefung deckt
    genau diesen Fall zusaetzlich ab -- die beiden Pruefungen sind
    komplementaer, keine ersetzt die andere).
  - Eine Unterklasse, die `model_post_init` selbst ueberschreibt, ohne
    `super().model_post_init(...)` aufzurufen (kein heutiger Produktionscode
    tut das; ein kategorisches Verbot dieser Form ist Aufgabe der
    statischen Pruefung, nicht dieser Datei).

WARUM `model_post_init` UND NICHT NUR `__init__` MONKEYPATCHEN
--------------------------------------------------------------------------
Ein Monkeypatch von `SyncLogEntry.__init__` saehe `cls(**roh)`,
`e.__init__(**roh)` und einen Closure-/Klassenattribut-Alias -- alle rufen
letztlich `__init__` auf. Er saehe aber NICHT `model_validate(...)`,
`model_construct(...)` oder den `response_model`-Weg von FastAPI: Pydantic
v2 validiert dort ueber den generierten Validator, der `__init__` NICHT
aufruft. `model_post_init` ist der einzige Erweiterungspunkt, den Pydantic
v2 nach JEDER erfolgreichen Konstruktion aufruft, unabhaengig vom Weg --
deshalb liegt der Haken dort (eine Zeile Produktionscode in
`backend/models/match.py`, siehe dort fuer die ausfuehrliche Begruendung,
warum das den Vertrag aus `docs/agents/bau-brief.md` nicht verletzt: die
Zeile aendert das Verhalten ausserhalb von Tests nicht).

WAS SIE NICHT TUT
--------------------------------------------------------------------------
Sie bricht NIEMALS einen Abgleich ab und schreibt kein Log -- ausserhalb
eines Tests ist `_SYNC_LOG_LAUFZEIT_HAKEN` immer `None`. Sie sammelt
Verstoesse waehrend eines Tests und laesst ihn erst bei dessen eigener
TEARDOWN fehlschlagen (nicht synchron an der Konstruktionsstelle) -- ein
Test, der eine Konstruktion absichtlich zu Testzwecken sabotiert (siehe die
`monkeypatch`-Tests in `test_log_messages.py`, die den Haken dafuer
VORUEBERGEHEND auf `None` setzen), stoert die eigentliche Pruefung damit
nicht.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Optional

import pytest

import models.match as _match_modul
from models.match import SyncLogEntry

WURZEL = Path(__file__).resolve().parents[2]
VERTRAG_PFAD = WURZEL / "frontend" / "src" / "logMessages.contract.json"


def lade_vertrag() -> dict[str, list[str]]:
    return json.loads(VERTRAG_PFAD.read_text("utf-8"))


def pruefe_laufzeit_eintrag(eintrag: SyncLogEntry, vertrag: dict[str, list[str]]) -> Optional[str]:
    """Die eigentliche Pruefung EINES Eintrags -- von der Fixture unten fuer
    jeden waehrend eines Tests konstruierten Eintrag aufgerufen, UND direkt
    von den Rot-Beweisen in `test_log_messages.py` fuer die Restformen, die
    kein AST-Muster kennt (`cls(**roh)`, `e.__init__(**roh)`, Closure-Alias,
    `response_model`-Weg). Gibt `None` zurueck, wenn der Eintrag in Ordnung
    ist, sonst eine lesbare Verstossmeldung (Schluessel + Parameter).

    Ein Eintrag OHNE `message_key` bleibt erlaubt -- wie heute (Alt-Format-
    Vertraeglichkeit, `details` als Fallback, siehe CLAUDE.md,
    "Projektspezifisches", Abschnitt "Sync-Log").
    """
    schluessel = eintrag.message_key
    if schluessel is None:
        return None
    erwartete = vertrag.get(schluessel)
    if erwartete is None:
        return (
            f"SyncLogEntry mit message_key={schluessel!r}, der in "
            "logMessages.contract.json nicht steht"
        )
    tatsaechlich = sorted((eintrag.message_params or {}).keys())
    erwartete_sortiert = sorted(erwartete)
    if tatsaechlich != erwartete_sortiert:
        return (
            f"SyncLogEntry '{schluessel}' wurde mit Parametern {tatsaechlich} konstruiert, "
            f"der Vertrag verlangt {erwartete_sortiert}"
        )
    return None


@pytest.fixture(autouse=True)
def _sync_log_vertragswaechter(request: pytest.FixtureRequest) -> Iterator[None]:
    """Haengt `pruefe_laufzeit_eintrag` fuer die Dauer EINES Tests in
    `SyncLogEntry.model_post_init` ein (siehe Moduldocstring). Sammelt
    Verstoesse waehrend des Tests und laesst ihn an der eigenen TEARDOWN
    fehlschlagen, mit Testname, Schluessel und Parametern in der Meldung."""
    vertrag = lade_vertrag()
    verstoesse: list[str] = []

    def _haken(eintrag: SyncLogEntry) -> None:
        meldung = pruefe_laufzeit_eintrag(eintrag, vertrag)
        if meldung is not None:
            verstoesse.append(meldung)

    _match_modul._SYNC_LOG_LAUFZEIT_HAKEN = _haken
    try:
        yield
    finally:
        _match_modul._SYNC_LOG_LAUFZEIT_HAKEN = None
    if verstoesse:
        pytest.fail(
            f"Sync-Log-Vertragswaechter (Laufzeit, {request.node.nodeid}): " + "; ".join(verstoesse),
            pytrace=False,
        )
