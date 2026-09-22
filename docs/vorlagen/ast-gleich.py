#!/usr/bin/env python3
"""Belegt, dass sich an einer .py NUR der Kopftext geaendert hat.

    python docs/vorlagen/ast-gleich.py <alt.py> <neu.py>

Exit 0 = die Syntaxbaeume ohne Docstrings sind gleich; 1 = sie sind es nicht;
2 = Aufruf- oder Lesefehler (falsche Argumentzahl, Datei fehlt, kein gueltiges
Python, nicht als UTF-8 lesbar). Den alten Stand holt man ohne Auscheckung:

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
  Diff daraufhin ansieht.
- **Zeilenenden und BOM** aendern den Baum nicht. Eine Datei, die nur von LF auf
  CRLF kippt, ist AST-gleich und trotzdem NICHT byte-gleich — und `cmp`, die
  Gate-Probe und der Blob-Vergleich der Setup-Checkliste lehnen sie ab. Das
  Skript meldet den Unterschied, damit niemand eine umgeflippte Datei als
  "nur Kopftext" ausgibt.
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
  fuer Zeichen.
- **Dass die Datei laeuft.** Das ist die Tuer-Probe, und die entfaellt nie.

Ein Unterschied in der Zeilenzahl ist kein Unterschied im Baum (Positionen
werden nicht verglichen): Ein laengerer Docstring verschiebt alles darunter,
ohne dass sich etwas aendert — genau der Fall, den die Ausnahme meint.
"""

import ast
import io
import re
import sys


def ohne_docstrings(quelle: str) -> str:
    baum = ast.parse(quelle)
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            if (knoten.body and isinstance(knoten.body[0], ast.Expr)
                    and isinstance(knoten.body[0].value, ast.Constant)
                    and isinstance(knoten.body[0].value.value, str)):
                knoten.body = knoten.body[1:] or [ast.Pass()]
    return ast.dump(baum, include_attributes=False)


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
    zeilen = roh.split(b"\n")[:2]
    shebang = zeilen[0] if zeilen and zeilen[0].startswith(b"#!") else b""
    # Pythons eigenes Muster (PEP 263), nicht "irgendwo steht coding": ein
    # gewoehnlicher Kommentar mit dem Wort waere sonst eine Deklaration.
    muster = re.compile(rb"^[ \t\f]*#.*?coding[:=][ \t]*([-_.a-zA-Z0-9]+)")
    kodierung = b""
    for z in zeilen:
        treffer = muster.match(z)
        if treffer:
            kodierung = treffer.group(1)
    return shebang.strip(), kodierung


def main() -> int:
    # Ohne das scheitert auf einem Windows-Host die Ausgabe an einem
    # Gedankenstrich — NACHDEM "GLEICH" schon gedruckt ist, mit Exit 1, was
    # laut Kopf "verschieden" heisst. Dieselbe Zeile steht in panel-stimme3.py.
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if len(sys.argv) != 3:
        sys.stderr.write("Aufruffehler: genau zwei Dateien erwartet.\n"
                         "    python ast-gleich.py <alt.py> <neu.py>\n"
                         "Gegeben: %d Argument(e).\n" % (len(sys.argv) - 1))
        return 2

    a_text, a_roh = lies(sys.argv[1])
    b_text, b_roh = lies(sys.argv[2])

    try:
        a_baum = ohne_docstrings(a_text)
        b_baum = ohne_docstrings(b_text)
    except SyntaxError as e:
        sys.stderr.write("Aufruffehler: kein gueltiges Python (%s).\n" % e)
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
        if a_roh.count(b"\r\n") != b_roh.count(b"\r\n"):
            hinweise.append("ACHTUNG: Die Zeilenenden unterscheiden sich (CRLF/LF). "
                            "Die Datei ist NICHT byte-gleich; cmp, Gate-Probe und "
                            "Blob-Vergleich lehnen sie ab.")
        if a_roh.startswith(b"\xef\xbb\xbf") != b_roh.startswith(b"\xef\xbb\xbf"):
            hinweise.append("ACHTUNG: Eine der Dateien hat ein BOM, die andere nicht.")
        a_sb, a_kod = kopfzeilen(a_roh)
        b_sb, b_kod = kopfzeilen(b_roh)
        if a_sb != b_sb:
            hinweise.append("ACHTUNG: Die Shebang-Zeile hat sich geaendert (%r -> %r) "
                            "— das ist kein Kopftext, das ist Verhalten."
                            % (a_sb.decode("utf-8", "replace"),
                               b_sb.decode("utf-8", "replace")))
        if a_kod != b_kod:
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
