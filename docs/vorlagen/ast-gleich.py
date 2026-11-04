#!/usr/bin/env python3
"""Belegt, dass sich an einer .py NUR der Kopftext geaendert hat.

    python -I -S docs/vorlagen/ast-gleich.py <alt.py> <neu.py>
    python -I -S docs/vorlagen/ast-gleich.py --selbstprobe

Exit 0 = die Syntaxbaeume ohne Docstrings sind gleich; 1 = sie sind es nicht;
2 = Aufruf- oder Lesefehler (falsche Argumentzahl, Datei fehlt, kein gueltiges
Python, nicht als UTF-8 lesbar, eine erklaerte Kodierung ausser UTF-8, der
Interpreter liest die Datei anders als dieses Skript, Lauf ohne -I -S). Den alten Stand holt man ohne Auscheckung:

    git show <tag>:docs/vorlagen/<datei>.py > /tmp/alt.py

WOFUER: Die Risiko-Tabelle in CLAUDE.md stuft eine kritische Datei als R3 ein,
unabhaengig von der Diffgroesse. Ausnahme seit dem Owner-Entscheid vom
2026-09-21: Aendern sich nur Kommentare oder Docstrings UND ist der Syntaxbaum
ohne Docstrings nachweislich gleich, laeuft der Schnitt als R2 (Blindpruefer +
Fremdpruefer, kein Gegenpruefer). Dieses Skript ist der Nachweis; sein Ergebnis
gehoert in den Panel-Kommentar. Bedingungen und Verfahren stehen in
docs/agents/panel.md, "Kritische Dateien". Die Tuer-Probe bleibt in beiden
Faellen.

WAS ES BEWEIST
--------------
Es vergleicht `ast.dump` beider Dateien, nachdem der Docstring von Modul,
Funktionen und Klassen entfernt wurde. GLEICH heisst: keine Anweisung, kein
Name und kein Konstanten-WERT hat sich geaendert.

WAS ES NICHT BEWEIST — hier steht die Grenze, nicht im Urteil des Lesers
------------------------------------------------------------------------
- **Der Kopftext kann falsch sein.** Ein Docstring darf beschreiben, was die
  Datei nicht tut; dagegen hilft nur das Lesen im Panel.
- **`#`-Kommentare sieht der Syntaxbaum nicht.** Dazu gehoeren zwei Zeilen, die
  KEIN Kopftext sind, obwohl sie wie Kommentare aussehen: die **Shebang-Zeile**
  und eine **Kodierungs-Deklaration** (`# -*- coding: ... -*-`). Beide aendern
  das Verhalten. Wer die Ausnahme in Anspruch nimmt, prueft sie eigens — dieses
  Skript meldet sie unten, verlaesst sich aber nicht darauf, dass jemand den
  Diff daraufhin ansieht. Es liest als UTF-8, und unter utf-7 ist ein Kommentar
  wie "# +AAo-import json" fuer den Interpreter eine Anweisung — beide Dateien
  mit derselben utf-7-Zeile waren sonst GLEICH, obwohl die neue einen Import
  mehr hatte (v1.18.11, dieselbe Klasse wie bei der Schalter-Wache in v1.18.7).
  Deshalb zwei Abbrueche mit Exit 2, in dieser Reihenfolge:
  1. **Die Sicht des Interpreters:** compile() auf die ROHBYTES erkennt die
     Kodierung selbst, wie der Import. Ergibt das einen anderen Baum als der
     UTF-8-Text, oder ist die Datei so kein gueltiges Python, bricht das Skript
     ab. Das ist der Beleg — nicht die eigene Erkennung der Kodierungszeile:
     Die trennte Zeilen nur an LF und sah "\r# coding: utf-7\r" nicht
     (Fremd-, Blind- und Gegenpruefer v1.18.11, gemessen: GLEICH, Exit 0).
  2. **Der Name:** Eine erklaerte Kodierung ausser UTF-8 (auch `utf-8-unix`
     und andere `utf-8-...` gelten als UTF-8, wie im Interpreter) bricht ab,
     auch wenn der Interpreter die Datei heute gleich liest.
- **Zeilenenden und BOM** aendern den Baum nicht. Eine Datei, die nur von LF auf
  CRLF kippt, ist AST-gleich und trotzdem NICHT byte-gleich — und `cmp`, die
  Gate-Probe und der Blob-Vergleich der Setup-Checkliste lehnen sie ab. Das
  Skript sagt bei jedem Paar, das nicht byte-gleich ist, GENAU DAS als ersten
  Hinweis; die einzelnen Hinweise darunter sind Zugaben, keine vollstaendige
  Liste (die Anzahl CRLF kann gleich und die Verteilung anders sein).
- **Doctests.** Ein `>>>`-Beispiel im Docstring ist ausfuehrbarer Text: Zwei
  Dateien, die sich nur im ERWARTETEN ERGEBNIS eines Beispiels unterscheiden,
  sind AST-gleich, und `python -m doctest` ist bei der einen gruen, bei der
  anderen rot. Das Skript meldet es, wenn sich Docstrings mit `>>>` geaendert
  haben; ob das Projekt Doctests fahrt, weiss es nicht.
- **Weitere Kommentare, die Werkzeuge steuern:** `# noqa`, `# type: ignore`,
  `# pragma: no cover` und Verwandte aendern das Urteil von Linter, Typpruefer
  oder Abdeckungs-Gate — also genau der Werkzeuge, um die es bei einer
  kritischen Datei geht. Der Syntaxbaum sieht sie nicht; dieses Skript meldet
  sie nicht. Wer sie im Diff sieht, hat keine reine Kopftext-Aenderung.
- **Ein Docstring, der zur Laufzeit ausgegeben wird** (etwa
  `ArgumentParser(description=__doc__)` oder eine eigene --help-Ausgabe),
  aendert das Verhalten des Programms, obwohl er hier weggeschnitten wird.
  Wer `__doc__` benutzt, hat keine reine Kopftext-Aenderung.
- **Die Schreibweise einer Konstante** ist kein Unterschied: `10` und `0x0A`
  ergeben denselben Wert und damit GLEICH. Die Aussage gilt fuer Werte, nicht
  fuer Zeichen. Dasselbe fuer den NAMEN einer Kodierung: `utf-8`, `UTF8` und
  `utf-8-unix` sind derselbe Codec, also kein Hinweis. Hinter einem BOM lehnt
  der Interpreter einige Schreibweisen ab (gemessen: `utf8`, `u8`, `cp65001`);
  die Sicht des Interpreters (unten in main) bricht dann mit Exit 2 ab.
- **Ein Rumpf, der nur aus einem Docstring besteht**, wird beim Abschneiden zu
  `pass` — gegen eine Funktion, die schon `pass` sagt, ergibt das GLEICH,
  obwohl `__doc__` von einem Text auf `None` wechselt (Gegenpruefer).
- **Dass die Datei laeuft.** Das ist die Tuer-Probe, und die entfaellt nie.

Ein Unterschied in der Zeilenzahl ist kein Unterschied im Baum (Positionen
werden nicht verglichen): Ein laengerer Docstring verschiebt alles darunter —
genau der Fall, den die Ausnahme meint. Code, der seine eigene Zeilennummer
liest (`f_lineno`, `inspect`, Text eines Tracebacks), verhaelt sich danach
anders; den sieht dieses Skript nicht (Blindpruefer v1.18.11, gemessen an einem
konstruierten Beispiel).
"""

import sys

# Erst die Schalter, dann jeder andere Import. Ohne -I liegt das Verzeichnis
# dieser Datei vorn im Modulpfad: Eine Datei mit dem Namen eines Moduls der
# Standardbibliothek daneben (ast.py, codecs.py) wird statt seiner geladen und
# kann den Lauf mit Exit 0 beenden, bevor etwas geprueft ist — gemessen in
# einem Kind-Repo an lehren-verweise-pruefen.py: Gate gruen, nichts geprueft
# (v1.18.0). -S laesst site aus (sitecustomize, .pth). sys ist eingebaut und
# laesst sich so nicht ersetzen. Das Werkzeug braucht nur die Standardbibliothek.
# GRENZE: Ohne Schalter laeuft site VOR dieser Zeile — eine sitecustomize.py
# oder usercustomize.py aus PYTHONPATH, dem Benutzerverzeichnis oder dem
# site-packages des Interpreters kommt also vor die Wache (Blind- und
# Gegenpruefer v1.18.0, gemessen: os._exit(0) dort, Exit 0); mit nur -I bleibt
# die aus dem site-packages des Interpreters. Dagegen hilft nur der Schalter
# selbst, nicht diese Zeile. Und ueber die Shebang-Zeile gestartet laeuft die
# Datei ohne Schalter: Exit 2.
if not (sys.flags.isolated and sys.flags.no_site):
    sys.stderr.write("Aufbau: ast-gleich.py laeuft nur mit -I -S: "
                     "<interpreter> -I -S ast-gleich.py ...\n")
    sys.exit(2)

import ast
import codecs
import io
import os
import re
import shutil
import subprocess
import tempfile


def ohne_docstrings(quelle: str) -> tuple:
    """(Baum-Abdruck ohne Docstrings, Liste der abgeschnittenen Docstrings)."""
    baum = ast.parse(quelle)
    docstrings = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            if (knoten.body and isinstance(knoten.body[0], ast.Expr)
                    and isinstance(knoten.body[0].value, ast.Constant)
                    and isinstance(knoten.body[0].value.value, str)):
                docstrings.append(knoten.body[0].value.value)
                knoten.body = knoten.body[1:] or [ast.Pass()]
    return ast.dump(baum, include_attributes=False), docstrings


def interpreter_sicht(text: str, roh: bytes) -> bool:
    """Liest der Interpreter die Rohbytes wie dieses Skript den Text?

    ast.parse auf BYTES nimmt den Weg des Imports (importlib uebergibt die
    Rohbytes an compile): Kodierungszeile, BOM und Zeilenenden erkennt dort
    Python selbst, nicht ein Muster in diesem Skript. Wirft SyntaxError, wenn
    die Bytes unter ihrer eigenen Kodierung kein gueltiges Python sind.
    """
    return (ast.dump(ast.parse(roh), include_attributes=False)
            == ast.dump(ast.parse(text), include_attributes=False))


def lies(pfad: str) -> tuple:
    """(Text, Rohbytes) — oder Abbruch mit Exit 2 samt Grund."""
    try:
        with io.open(pfad, "rb") as f:
            roh = f.read()
    except OSError as e:
        sys.stderr.write("Aufruffehler: %s nicht lesbar (%s).\n" % (pfad, e))
        raise SystemExit(2)
    try:
        # utf-8-sig: ein BOM ist gueltiges Python, wuerde den Parser aber mit
        # "invalid non-printable character" abbrechen — dann waere der
        # BOM-Hinweis unten unerreichbar (Blindpruefer v1.16.0).
        return roh.decode("utf-8-sig"), roh
    except UnicodeDecodeError as e:
        sys.stderr.write("Aufruffehler: %s ist nicht als UTF-8 lesbar (%s). "
                         "Dieses Skript vergleicht nur UTF-8-Quellen.\n" % (pfad, e))
        raise SystemExit(2)


def kopfzeilen(roh: bytes) -> tuple:
    """Shebang und Kodierungs-Deklaration — Kommentare, die Verhalten aendern."""
    # Ohne das blendet ein BOM die ganze Erkennung aus: Zeile 1 beginnt dann nicht
    # mit "#!" und nicht mit "#", also meldete das Skript weder einen geaenderten
    # Shebang noch eine geaenderte Kodierungs-Zeile (Blindpruefer, gemessen an
    # zwei Paaren mit BOM). Der BOM-Unterschied selbst wird getrennt gemeldet.
    if roh.startswith(b"\xef\xbb\xbf"):
        roh = roh[3:]
    # Zeilenenden wie der Interpreter: auch ein einzelnes CR beendet eine Zeile.
    # Mit split an LF allein sah das Skript "\r# coding: utf-7" nicht und hielt
    # "# a\r# b\r# coding: latin-1" fuer eine Erklaerung in Zeile 1, die der
    # Interpreter als Zeile 3 uebergeht (Blind- und Gegenpruefer v1.18.11).
    zeilen = re.split(rb"\r\n|\r|\n", roh)[:2]
    shebang = zeilen[0] if zeilen and zeilen[0].startswith(b"#!") else b""
    # Pythons eigenes Muster (PEP 263), nicht "irgendwo steht coding": ein
    # gewoehnlicher Kommentar mit dem Wort waere sonst eine Deklaration.
    muster = re.compile(rb"^[ \t\f]*#.*?coding[:=][ \t]*([-_.a-zA-Z0-9]+)")
    kodierung = b""
    # Pythons Regel (tokenize.detect_encoding), nicht "der letzte Treffer der
    # ersten zwei Zeilen": Es gilt der ERSTE Treffer, und Zeile 2 wird nur
    # angesehen, wenn Zeile 1 leer oder ein Kommentar ist. Vorher meldete das
    # Skript "# coding: utf-8 / # coding: latin-1" gegen zweimal
    # "# coding: latin-1" als GLEICH ohne Hinweis, obwohl Python verschiedene
    # Kodierungen liest (Blindpruefer, Nacharbeit 2 von v1.16.0, gemessen).
    for nr, z in enumerate(zeilen):
        z = z.rstrip(b"\r")
        treffer = muster.match(z)
        if treffer:
            kodierung = treffer.group(1)
            break
        if nr == 0:
            rest = z.strip()
            if rest and not rest.startswith(b"#"):
                break
    return shebang.strip(), kodierung


def kodierungsname(roh: bytes) -> str:
    """Der normalisierte Codec-Name — 'utf-8', 'UTF8' und 'utf-8-unix' sind derselbe.

    Ohne das meldete das Skript einen Verhaltensunterschied, wo keiner ist, und
    hob eine R2-Einstufung ohne Grund auf R3 (Gegenpruefer, gemessen an
    latin-1/iso-8859-1 und utf-8/UTF8; latin-1 bricht seit v1.18.11 schon vorher
    mit Exit 2 ab).
    """
    if not roh:
        return ""
    # Pythons eigene Vorstufe (get_normal_name im Tokenizer): "utf-8-unix",
    # "utf-8-dos" und jedes "utf-8-..." sind UTF-8, codecs.lookup kennt sie
    # aber nicht. Ohne das brach das Skript bei einer Emacs-Kodierungszeile auf
    # einer UTF-8-Datei mit Exit 2 ab (Blindpruefer v1.18.11, gemessen).
    name = roh.decode("ascii", "replace").lower().replace("_", "-")
    if name == "utf-8" or name.startswith("utf-8-"):
        return "utf-8"
    try:
        return codecs.lookup(roh.decode("ascii", "replace")).name
    except (LookupError, ValueError):
        return roh.decode("utf-8", "replace")


def selbstprobe() -> int:
    """Faelle mit bekanntem Ergebnis; ohne sie ist dieses Skript Disziplin."""
    geprueft = [0]
    fehler = []

    def erwarte(name, ist, soll):
        geprueft[0] += 1
        if ist != soll:
            fehler.append("%s: %r, erwartet %r" % (name, ist, soll))

    def stumm(argv):
        alt_out, alt_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = fang = io.StringIO()
        try:
            return main(argv), fang.getvalue()
        except SystemExit as ende:
            return (ende.code if isinstance(ende.code, int) else 1), fang.getvalue()
        finally:
            sys.stdout, sys.stderr = alt_out, alt_err

    d = tempfile.mkdtemp(prefix="ast-gleich-selbstprobe-")
    try:
        def paar(a, b):
            pa, pb = os.path.join(d, "a.py"), os.path.join(d, "b.py")
            with io.open(pa, "wb") as f:
                f.write(a)
            with io.open(pb, "wb") as f:
                f.write(b)
            return stumm(["prog", pa, pb])

        k = (b'"""Kopf."""\nX = 10\n\n\ndef f():\n    """Doc."""\n    return X\n')
        rc, aus = paar(k, k.replace(b"Kopf.", b"Kopf, neu."))
        erwarte("Docstring geaendert -> GLEICH, nicht byte-gleich",
                (rc, "GLEICH" in aus, "NICHT byte-gleich" in aus), (0, True, True))
        rc, aus = paar(k, k.replace(b"X = 10", b"X = 11"))
        erwarte("Wert geaendert -> VERSCHIEDEN", (rc, "VERSCHIEDEN" in aus), (1, True))
        rc, aus = paar(k, k.replace(b"return X", b"return -X"))
        erwarte("Anweisung geaendert -> VERSCHIEDEN", rc, 1)
        rc, aus = paar(k, k)
        erwarte("byte-gleich -> GLEICH mit Hinweis",
                (rc, "sind byte-gleich" in aus, "NICHT byte-gleich" in aus), (0, True, False))
        rc, aus = paar(k, k.replace(b"X = 10", b"X = 0x0A"))
        erwarte("Schreibweise einer Konstante -> GLEICH (benannte Grenze)", rc, 0)
        doc = k.replace(b'"""Doc."""', b'"""Doc.\n\n    >>> f()\n    10\n    """')
        rc, aus = paar(doc, doc.replace(b"    10\n", b"    11\n"))
        erwarte("Doctest geaendert -> Hinweis", (rc, "Doctests" in aus), (0, True))
        zwei = (b'def f():\n    """>>> 1"""\n    return 1\n\n\ndef g():\n    """>>> 2"""\n'
                b'    return 2\n')
        rc, aus = paar(zwei, zwei.replace(b">>> 1", b"@@@").replace(b">>> 2", b">>> 1")
                       .replace(b"@@@", b">>> 2"))
        erwarte("Doctests zwischen Funktionen getauscht -> Hinweis", (rc, "Doctests" in aus),
                (0, True))
        rc, aus = paar(k, k.replace(b"\n", b"\r\n"))
        erwarte("CRLF -> Hinweis Zeilenenden", (rc, "Zeilenenden" in aus), (0, True))
        rc, aus = paar(k, b"\xef\xbb\xbf" + k)
        erwarte("BOM -> Hinweis BOM", (rc, "BOM" in aus), (0, True))
        rc, aus = paar(b"#!/usr/bin/env python3\n" + k, b"#!/usr/bin/python\n" + k)
        erwarte("Shebang -> Hinweis", (rc, "Shebang" in aus), (0, True))
        rc, aus = paar(b"\xef\xbb\xbf#!/usr/bin/env python3\n" + k,
                       b"\xef\xbb\xbf#!/usr/bin/python\n" + k)
        erwarte("Shebang hinter BOM -> Hinweis", (rc, "Shebang" in aus), (0, True))
        rc, aus = paar(b"# -*- coding: utf-8 -*-\n" + k, b"# coding: UTF8\n" + k)
        erwarte("utf-8 und UTF8 sind derselbe Codec -> kein Hinweis",
                (rc, "Kodierungs-Deklaration" in aus), (0, False))
        rc, aus = paar(k, b"# coding: utf-8\n" + k)
        erwarte("Kodierungs-Zeile hinzugefuegt -> Hinweis",
                (rc, "Kodierungs-Deklaration" in aus), (0, True))
        utf7 = b"# -*- coding: utf-7 -*-\n" + k
        rc, aus = paar(utf7, utf7.replace(b"X = 10\n", b"X = 10  # +AAo-import json\n"))
        erwarte("utf-7: Kommentar, der fuer den Interpreter Code ist -> Exit 2",
                (rc, "liest der Interpreter" in aus), (2, True))
        rc, aus = paar(utf7, utf7)
        erwarte("utf-7 ohne verstecktes Zeichen -> Exit 2 nach dem Namen",
                (rc, "nur UTF-8" in aus), (2, True))
        # Die Kodierungszeile hinter einem einzelnen CR: Die Zeilen-Erkennung hier
        # sieht sie nicht, der Interpreter schon (Fremdpruefer v1.18.11).
        cr = b"\r# coding: utf-7\rX = 10\r"
        rc, aus = paar(cr, cr.replace(b"X = 10\r", b"X = 10  # +AAo-import json\r"))
        erwarte("utf-7 hinter einzelnem CR -> Exit 2 (Sicht des Interpreters)",
                (rc, "liest der Interpreter" in aus), (2, True))
        rc, aus = paar(k.replace(b"\n", b"\r"), k.replace(b"\n", b"\r").replace(b"Kopf.", b"Neu."))
        erwarte("UTF-8 mit CR-Zeilenenden, Docstring geaendert -> GLEICH", rc, 0)
        emacs = b"# -*- mode: python; coding: utf-8-unix -*-\n" + k
        rc, aus = paar(emacs, emacs.replace(b"Kopf.", b"Neu."))
        erwarte("utf-8-unix (Emacs) ist UTF-8 -> GLEICH", rc, 0)
        rc, aus = paar(b"# coding: latin-1\n" + k, k)
        erwarte("nur die ALTE Datei erklaert latin-1 -> Exit 2", rc, 2)
        rc, aus = paar(k, b"# coding: cp1252\n" + k)
        erwarte("nur die NEUE Datei erklaert cp1252 -> Exit 2", rc, 2)
        drei = b"# a\r# b\r# coding: latin-1\r" + k.replace(b"\n", b"\r")
        rc, aus = paar(drei, drei.replace(b"Kopf.", b"Neu."))
        erwarte("Kodierung erst in Zeile 3 (CR) -> GLEICH, der Interpreter liest UTF-8", rc, 0)
        bom = b"\xef\xbb\xbf# -*- coding: utf-8 -*-\n" + k
        rc, aus = paar(bom, bom.replace(b"coding: utf-8", b"coding: utf8"))
        erwarte("BOM mit 'utf8' -> Exit 2 (der Interpreter bricht ab)", rc, 2)
        rc, aus = paar(bom.replace(b"coding: utf-8", b"coding: utf8"), bom)
        erwarte("BOM mit 'utf8' nur in der ALTEN Datei -> Exit 2", rc, 2)
        crlf = b"#!/usr/bin/env python3\r\n# coding: latin-1\r\n" + k.replace(b"\n", b"\r\n")
        rc, aus = paar(crlf, crlf)
        erwarte("CRLF, latin-1 in Zeile 2 hinter der Shebang -> Exit 2", rc, 2)
        rc, aus = paar(b"# coding: latin-1\n" + k, b"# coding: latin-1\n" + k)
        erwarte("latin-1 erklaert -> Exit 2", rc, 2)
        rc, aus = paar(b"#!/usr/bin/env python3\n# coding: utf-7\n" + k,
                       b"#!/usr/bin/env python3\n# coding: utf-7\n" + k)
        erwarte("utf-7 in Zeile 2 hinter der Shebang -> Exit 2", rc, 2)
        rumpf = b'def f():\n    """Nur Doc."""\n'
        rc, aus = paar(rumpf, b"def f():\n    pass\n")
        erwarte("Rumpf nur Docstring gegen pass -> GLEICH (benannte Grenze)", rc, 0)
        erwarte("Aufruf: eine Datei -> Exit 2", stumm(["prog", "a.py"])[0], 2)
        erwarte("Aufruf: Datei fehlt -> Exit 2",
                stumm(["prog", os.path.join(d, "fehlt.py"), os.path.join(d, "fehlt2.py")])[0], 2)
        rc, aus = paar(k, b"def (:\n")
        erwarte("kein gueltiges Python -> Exit 2, ohne von Kodierung zu reden",
                (rc, "kein gueltiges Python (" in aus, "Kodierung" in aus), (2, True, False))
        rc, aus = paar(b"def (:\n", k)
        erwarte("Syntaxfehler in der ALTEN Datei -> die Meldung nennt sie",
                (rc, os.path.join(d, "a.py") in aus), (2, True))
        rc, aus = paar(k, b"def (:\n")
        erwarte("Syntaxfehler in der NEUEN Datei -> die Meldung nennt sie",
                (rc, os.path.join(d, "b.py") in aus, os.path.join(d, "a.py") in aus),
                (2, True, False))
        rc, aus = paar(k, b"# coding: utf-7\nX = +ADE-\n")
        erwarte("nur unter utf-7 gueltig -> Exit 2, die Meldung nennt die Kodierung",
                (rc, "Kodierung" in aus), (2, True))
        rc, aus = paar(k, "X = '\u00e4'\n".encode("latin-1"))
        erwarte("nicht als UTF-8 lesbar -> Exit 2", rc, 2)

        # Die Schalter-Wache WIRKT: eine Kopie neben einer ast.py, die den Lauf mit
        # Exit 0 beendet. Ohne Wache gewaenne der Schatten (dieselbe Probe wie in
        # den anderen Werkzeugen; die STELLE der Wache prueft die
        # Waechter-Selbstprobe am Syntaxbaum nur fuer ihre eigenen Dateien).
        kopie = os.path.join(d, "ast-gleich.py")
        shutil.copy(os.path.abspath(__file__), kopie)
        with io.open(os.path.join(d, "ast.py"), "w", encoding="utf-8") as f:
            f.write("raise SystemExit(0)\n")
        for name, schalter in (("keiner", []), ("nur -I", ["-I"]), ("nur -S", ["-S"])):
            try:
                kind = subprocess.run([sys.executable] + schalter + [kopie, "a", "b"],
                                      capture_output=True, timeout=60)
                ergebnis = (kind.returncode, b"laeuft nur mit -I -S" in kind.stderr)
            except subprocess.TimeoutExpired:
                ergebnis = ("Zeitgrenze", False)
            erwarte("Wache: Schalter %s, ast.py daneben -> Exit 2 mit der Meldung der Wache"
                    % name, ergebnis, (2, True))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    erwarte("mindestens 37 Erwartungen", geprueft[0] >= 37, True)
    if fehler:
        sys.stderr.write("ast-gleich Selbstprobe ROT: %d Abweichung(en)\n  " % len(fehler)
                         + "\n  ".join(fehler) + "\n")
        return 1
    print("ast-gleich Selbstprobe gruen: %d Erwartungen (GLEICH/VERSCHIEDEN, Hinweise zu "
          "Doctest, Zeilenenden, BOM, Shebang und Kodierung, Exit 2 bei anderer Kodierung, "
          "Fehlerwege, Wache). Nicht geprueft: ob ein Kopftext WAHR ist." % geprueft[0])
    return 0


def main(argv=None) -> int:
    argv = sys.argv if argv is None else argv
    # Ohne das scheitert auf einem Windows-Host die Ausgabe an einem
    # Gedankenstrich — NACHDEM "GLEICH" schon gedruckt ist, mit Exit 1, was
    # laut Kopf "verschieden" heisst. Dieselbe Zeile steht in panel-stimme3.py.
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if argv[1:] == ["--selbstprobe"]:
        return selbstprobe()

    if len(argv) != 3:
        sys.stderr.write("Aufruffehler: genau zwei Dateien erwartet.\n"
                         "    python -I -S ast-gleich.py <alt.py> <neu.py>\n"
                         "    python -I -S ast-gleich.py --selbstprobe\n"
                         "Gegeben: %d Argument(e).\n" % (len(argv) - 1))
        return 2

    a_text, a_roh = lies(argv[1])
    b_text, b_roh = lies(argv[2])
    # Zuerst gewoehnliches Python: Ein Syntaxfehler im UTF-8-Text bekommt seine
    # eigene Meldung. Lief er erst in die Sicht des Interpreters, hiess es dort
    # irrefuehrend "unter der Kodierung, die der Interpreter erkennt"
    # (Blindpruefer, Nacharbeit 1 zu v1.18.11). Die Meldung nennt die Datei, und
    # ist die Datei nur unter ihrer eigenen Kodierung gueltig (etwa utf-7 mit
    # "+ADE-"), sagt sie das (Blindpruefer, Nacharbeit 2 zu v1.18.11).
    baeume = []
    for pfad, text, roh in ((argv[1], a_text, a_roh), (argv[2], b_text, b_roh)):
        try:
            baeume.append(ohne_docstrings(text))
        except SyntaxError as e:
            try:
                ast.parse(roh)
                grund = ("als UTF-8 kein gueltiges Python, unter der Kodierung, die "
                         "der Interpreter erkennt, schon: Er liest die Datei anders "
                         "als dieses Skript")
            except (SyntaxError, ValueError):
                grund = "kein gueltiges Python"
            sys.stderr.write("Aufruffehler: %s ist %s (%s).\n" % (pfad, grund, e))
            return 2
    (a_baum, a_docs), (b_baum, b_docs) = baeume
    # Dann die Sicht des Interpreters: Liest er eine Datei anders als dieses
    # Skript den UTF-8-Text, ist jeder Vergleich unten wertlos. Die Erkennung
    # der Kodierungszeile allein trennte an LF und uebersah "\r# coding: utf-7\r"
    # (Fremd-, Blind- und Gegenpruefer v1.18.11, gemessen: GLEICH, Exit 0,
    # Schatten geladen). Diese Pruefung steht VOR der nach dem Namen, damit die
    # Selbstprobe jede der beiden fuer sich erreicht.
    for pfad, text, roh in ((argv[1], a_text, a_roh), (argv[2], b_text, b_roh)):
        try:
            gleich_gelesen = interpreter_sicht(text, roh)
        except (SyntaxError, ValueError) as e:
            sys.stderr.write("Aufruffehler: %s ist unter der Kodierung, die der "
                             "Interpreter erkennt, kein gueltiges Python (%s).\n" % (pfad, e))
            return 2
        if not gleich_gelesen:
            sys.stderr.write("Aufruffehler: %s liest der Interpreter anders als dieses "
                             "Skript (Kodierung, die hier nicht erkannt wird). Der "
                             "Vergleich saehe nicht, was laeuft.\n" % pfad)
            return 2

    # Dann nur UTF-8 nach dem Namen: auch eine Datei, die der Interpreter heute
    # gleich liest, wird abgelehnt, wenn sie eine andere Kodierung erklaert —
    # die naechste Aenderung an ihr laege sonst ausserhalb dessen, was dieses
    # Skript liest. Unter utf-7 war "# +AAo-import json" hier ein Kommentar und
    # fuer den Interpreter ein Import (v1.18.11).
    for pfad, roh in ((argv[1], a_roh), (argv[2], b_roh)):
        name = kodierungsname(kopfzeilen(roh)[1])
        if name not in ("", "utf-8", "utf-8-sig"):
            sys.stderr.write("Aufruffehler: %s erklaert die Kodierung %r. Dieses Skript "
                             "vergleicht nur UTF-8-Quellen: Unter einer anderen Kodierung "
                             "kann ein Kommentar fuer den Interpreter Code sein, und der "
                             "Vergleich hier saehe ihn nicht.\n" % (pfad, name))
            return 2

    gleich = a_baum == b_baum
    print("AST ohne Docstrings: %s (%d Zeichen)"
          % ("GLEICH" if gleich else "VERSCHIEDEN", len(a_baum)))
    if not gleich:
        return 1

    # Nur wenn der Baum gleich ist, sind die Grenzen unten entscheidungsrelevant:
    # Sie sagen, ob "GLEICH" wirklich "nur Kopftext" heisst.
    hinweise = []
    if a_roh == b_roh:
        hinweise.append("Die Dateien sind byte-gleich — es hat sich nichts geaendert.")
    else:
        # Dieser Satz steht vor allen einzelnen Hinweisen und schliesst die
        # Loecher, die kein eigener Hinweis kennt (etwa dieselbe ANZAHL CRLF an
        # anderen Zeilen): Was nicht byte-gleich ist, faellt spaetestens am
        # Blob-Vergleich auf, auch wenn hier nichts Weiteres steht
        # (Blindpruefer, Nacharbeit 2 von v1.16.0).
        hinweise.append("Die Dateien sind NICHT byte-gleich; cmp, Gate-Probe und "
                        "Blob-Vergleich lehnen sie ab. Was unten nicht eigens "
                        "genannt ist, ist damit nicht ausgeschlossen.")
        # Reihenfolge NICHT sortieren: Die Baeume sind an dieser Stelle schon
        # gleich, also ist die Knotenfolge dieselbe — und ein Tausch zweier
        # Docstrings zwischen zwei Funktionen faellt nur auf, wenn man die Folge
        # vergleicht (Fremdstimme).
        if a_docs != b_docs and any(">>>" in t for t in a_docs + b_docs):
            # Ein Docstring mit >>>-Beispiel ist ausfuehrbarer Text: Wer
            # --doctest-modules oder python -m doctest fahrt, hat hier
            # Verhalten geaendert, obwohl der Baum gleich bleibt.
            hinweise.append("ACHTUNG: Ein Docstring mit einem '>>>'-Beispiel hat sich "
                            "geaendert — Doctests sind ausfuehrbarer Text. Wer "
                            "'python -m doctest' oder '--doctest-modules' fahrt, "
                            "hat damit Verhalten geaendert, nicht nur Kopftext.")
        if a_roh.count(b"\r\n") != b_roh.count(b"\r\n"):
            hinweise.append("ACHTUNG: Die Zeilenenden unterscheiden sich in der Anzahl "
                            "(CRLF/LF).")
        if a_roh.startswith(b"\xef\xbb\xbf") != b_roh.startswith(b"\xef\xbb\xbf"):
            hinweise.append("ACHTUNG: Eine der Dateien hat ein BOM, die andere nicht.")
        a_sb, a_kod = kopfzeilen(a_roh)
        b_sb, b_kod = kopfzeilen(b_roh)
        if a_sb != b_sb:
            hinweise.append("ACHTUNG: Die Shebang-Zeile hat sich geaendert (%r -> %r) "
                            "— das ist kein Kopftext, das ist Verhalten."
                            % (a_sb.decode("utf-8", "replace"),
                               b_sb.decode("utf-8", "replace")))
        if kodierungsname(a_kod) != kodierungsname(b_kod):
            hinweise.append("ACHTUNG: Die Kodierungs-Deklaration hat sich geaendert "
                            "(%r -> %r) — das ist kein Kopftext, das ist Verhalten."
                            % (a_kod.decode("utf-8", "replace"),
                               b_kod.decode("utf-8", "replace")))
    for h in hinweise:
        print(h)
    print("Nicht geprueft: ob der Kopftext WAHR ist, und ob die Datei laeuft "
          "(Tuer-Probe).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
