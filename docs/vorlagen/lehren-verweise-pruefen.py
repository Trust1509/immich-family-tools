#!/usr/bin/env python3
"""Prueft, dass jeder Verweis der Form "§N" einen Abschnitt trifft, den es gibt.

    python -I -S docs/vorlagen/lehren-verweise-pruefen.py --lehren <lehren.md> <datei> …
    python -I -S docs/vorlagen/lehren-verweise-pruefen.py --lehren <lehren.md> --ausser "B-KUVG|ASVG" <datei> …
    python -I -S docs/vorlagen/lehren-verweise-pruefen.py --selbstprobe
    python -I -S docs/vorlagen/lehren-verweise-pruefen.py --lehren <lehren.md> --vorlage-selbst <datei> …   (nur IN der Vorlage)

Exit 0 = jeder gepruefte Verweis trifft einen Abschnitt; **1 = mindestens einer
nicht ODER die Ausnahme hat einen treffenden Verweis mitgenommen** (dann ist das
Muster zu weit, siehe unten); 2 = Aufruf- oder Lesefehler (fehlende Argumente,
Datei nicht lesbar, Lauf ohne -I -S).

WOFUER: Beim Uebernehmen einer Lehre aus der Vorlage werden die Nummern
repo-lokal (abgleich.md, Schritt 2d). Die Verweise IM TEXT der uebernommenen
Lehre bleiben dabei leicht stehen — und ein Verweis auf eine Vorlagen-Nummer
trifft im Kind-Repo eine ANDERE, meist existierende Lehre. Das erzeugt keine
Fehlermeldung, nur eine falsche Begruendung. Gemeldet aus einem Kind-Repo, das
elf Lehren uebernahm: acht interne Verweise in fuenf von ihnen, und ein
Altbestand-Verweis hatte zwei Abgleiche ueberlebt.

WAS ES PRUEFT
-------------
Abschnitte sind Zeilen der Form "## N." oder "## N " am Zeilenanfang der
Lehren-Datei. Verweise sind "§N" und "§§N-M" (beide Enden) in allen genannten
Dateien, die Lehren-Datei eingeschlossen. Ein Verweis auf eine Nummer ohne
Abschnitt ist ROT. Das faengt eine Richtung: einen Verweis ueber die eigene
Zaehlung hinaus. Zaehlt das Repo HOEHER als die Quelle des Verweises, trifft ein
stehen gelassener Verweis eine existierende andere Lehre — dazu unten.

VERWEISE IN DIE ZAEHLUNG DER VORLAGE (abgleich.md 2d: "Vorlage §N") werden
erkannt und NICHT gegen die eigene Zaehlung geprueft. Ein Verweis gehoert der
Vorlage, wenn das Wort "Vorlage" am Wortanfang hoechstens 20 Zeichen vor ihm
steht, ohne Satzteil-Trenner und ohne anderen Verweis dazwischen. Trenner sind
Komma, Semikolon, Gedankenstrich (– und —) sowie Punkt, Doppelpunkt, Ausrufe-
und Fragezeichen vor Leerraum; ein ASCII-Bindestrich mit Leerraum (" - ")
trennt NICHT. Die Meldung nennt ihre Zahl.

WAS ES NICHT PRUEFT — hier steht die Grenze, nicht im Urteil des Lesers
----------------------------------------------------------------------
- **Einen Verweis auf eine existierende, aber falsche Lehre.** Zeigt "§21" im
  Kind-Repo auf eine andere Lehre als in der Vorlage, sieht dieses Skript
  nichts: Die Nummer existiert. Genau dieser Fall war der teuerste der Meldung.
  Dagegen hilft nur, beim Uebernehmen jeden Verweis einzeln nachzuschlagen.
- **Verweise in anderer Schreibweise** ("Abschnitt 21", "Lehre 21", "siehe 21").
  Das Skript kennt nur das Zeichen §.
- **Fremde Paragrafen-Zaehlungen — die gefaehrlichste Klasse, weil sie FALSCHEN
  ALARM erzeugt.** In einem Projekttext steht "§ 43 B-KUVG" oder "§205 BAO";
  das Skript sieht eine Lehren-Nummer und meldet sie als Verweis ins Leere. Zwei
  Vorkehrungen: Eine Zahl mit unmittelbar folgendem Buchstaben (§32b) gilt nicht
  als Verweis, und `--ausser <muster>` nimmt Zeilen aus (Python-Regex, gegen die
  ganze Zeile geprueft). **Die Ausnahme darf nur Verweise wegnehmen, die INS
  LEERE zeigen** — dafuer ist sie da, denn fremde Zaehlungen treffen keinen
  Abschnitt. Nimmt sie einen mit, der TRIFFT, ist das Muster zu weit: Exit 1 mit
  der Zahl. Und die Erfolgsmeldung nennt Muster, uebersprungene Zeilen und
  entfernte Verweise; beide Zahlen gehoeren in das Abgleich-Issue. Wer
  Gesetzestexte fuehrt, setzt das Muster ENG im Gate-Kommando und nennt es
  dort. Ein Waechter, der falsch alarmiert, wird abgeschaltet — und dann
  schuetzt er nichts mehr. Dazu gehoert dieses Skript selbst: Seine Selbstprobe
  traegt Beispiel-Verweise im Quelltext. Wer die .py-Dateien mitprueft, nimmt es
  mit --ausser heraus; das Gate-Kommando oben prueft die Textdateien.
  Steht ein Lehren-Verweis mit einem Zitat in EINER Zeile ("Nach §1 gilt die
  Frist des § 43 B-KUVG"), gibt es kein passendes Muster: --ausser arbeitet
  zeilenweise. Das Zitat gehoert dann auf eine eigene Zeile.
- **Ein Muster, das GENAU die Verweise ins Leere wegnimmt**, legt die Pruefung
  still und bleibt gruen — es nimmt keinen treffenden mit. Das sieht nur, wer
  die Zahlen der Meldung liest; deshalb gehoeren sie ins Abgleich-Issue.
- **Code-Bloecke und Beispiele werden mitgelesen.** Ein § in einem Beispiel ist
  ein Verweis wie jeder andere; das ist Absicht, weil ein Beispiel mit falscher
  Nummer genauso in die Irre fuehrt. Umgekehrt gilt das auch fuer die
  ABSCHNITTS-Seite: Eine Zeile "## 9. Beispiel" in einem Code-Block zaehlt als
  Abschnitt und macht §9 gruen. Dort ist die Fehlrichtung still, nicht laut —
  ein Grund mehr, Verweise beim Uebernehmen nachzuschlagen.
- **Zaeune und Kommentare werden nur grob erkannt.** Jede Zeile, die nach
  Leerraum mit ``` oder ~~~ beginnt, schaltet den Zaun um, gleich welche
  Laenge, welches Zeichen und wie tief eingerueckt. Kommentare zaehlen nur,
  wenn "<!--" nach Leerraum am Zeilenanfang steht. Daraus zwei Richtungen:
  STILL (ein auskommentierter Kopf zaehlt wieder als Abschnitt, das Verhalten
  vor v1.19.0) nach einer Zeile "```x``` Text", einem einzelnen 3er in einem
  4er- oder ~~~-Zaun, einem Zaun ohne Ende oder einem um vier oder mehr
  Leerzeichen eingerueckten Zaun, und nach einem zweiten "<!--" auf der
  Zeile, auf der ein Kommentar endet (gerendert ist der Rest der Datei dann
  Kommentar, das Werkzeug zaehlt ihn). LAUT (ein Verweis wird rot): Ein
  Kommentar zwischen einem 3er-Paar in einem 4er- oder ~~~-Zaun versteckt
  den Kopf darin, und ein eingerueckter Kommentar zaehlt wie einer am
  Zeilenanfang. Die Ausloeser oben koennen je nach Folgetext auch in die
  andere Richtung wirken. Kein Fehler: "<!--" mitten in einer Zeile
  versteckt nichts. Das Verhalten ist an je einem Beispiel gemessen, das
  Rendern nur vom Blindpruefer (v1.19.1).
- **Vorlagen-Verweise gegen die Zaehlung der Vorlage.** Das Skript kennt deren
  Abschnitte nicht; "Vorlage §99" laeuft als Vorlagen-Verweis durch, auch wenn
  es dort keinen §99 gibt.
- **Ein eigener Verweis dicht hinter dem Wort "Vorlage" im selben Satzteil**
  ("die Vorlage gilt fuer §3") wird als Vorlagen-Verweis gelesen und NICHT
  geprueft — die stille Richtung (mit --vorlage-selbst entfaellt sie: dort wird
  auch er gegen die eigene Zaehlung geprueft). Sie braucht das Wort am
  Wortanfang, hoechstens 20 Zeichen davor und keinen Trenner; in zwei gemessenen
  Kind-Repos kam das nur bei echten Vorlagen-Verweisen vor. Wer so schreibt,
  setzt ein Komma oder formuliert um.
- **Andere Formen eines Vorlagen-Verweises** werden als eigene gelesen: Gibt es
  die Nummer in der eigenen Zaehlung nicht (darueber oder in einer Luecke),
  schlaegt das falsch an (laut); gibt es sie, trifft sie still eine andere
  eigene Lehre. Gemeint sind:
  nachgestellt ("§22 der Vorlage"),
  aufgezaehlt ("Vorlage §20 und §21": §21 gilt als eigener), mit einem Umbruch
  zwischen Wort und Verweis, oder nur mit Versionsstempel ("v1.10.0 §19" ohne das
  Wort). Abhilfe: das Wort vor jeden Verweis ("Vorlage §20 und Vorlage §21").
- **Ob die Lehre selbst richtig ist.** Das ist das Panel.

`--vorlage-selbst` — NUR in der Vorlage selbst: Dort zeigt „Vorlage §N" in die
eigene Zaehlung, und mit dem Schalter werden diese Verweise gegen die eigene
`lehren.md` GEPRUEFT statt nur gezaehlt. Seit v1.18.1 zitieren die
Verfahrensdokumente der Vorlage ihre Lehren als „Vorlage-Lehre §N": So zeigen
sie in jedem Kind-Repo, das die Dokumente kopiert, in die richtige Zaehlung, und
ohne den Schalter verloere die Vorlage die Pruefung ihrer eigenen Verweise. Ein
Kind-Repo setzt ihn nie — es wuerde Vorlagen-Verweise gegen die falsche Zaehlung
pruefen. Reihenfolge: `--lehren <datei>`, danach `--vorlage-selbst` und
`--ausser <muster>` in beliebiger Reihenfolge, je hoechstens einmal, dann die
Dateien.
"""

import sys

# Erst die Schalter, dann jeder andere Import. Ohne -I liegt das Verzeichnis
# dieser Datei vorn im Modulpfad: Eine Datei mit dem Namen eines Moduls der
# Standardbibliothek daneben (tempfile.py, re.py) wird statt seiner geladen und
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
    sys.stderr.write("Aufbau: lehren-verweise-pruefen.py laeuft nur mit -I -S: "
                     "<interpreter> -I -S lehren-verweise-pruefen.py ...\n")
    sys.exit(2)

import io
import os
import re
import tempfile

# Eine Abschnitts-Zeile darf auch am Dateiende ohne folgendes Zeichen stehen.
ABSCHNITT = re.compile(r"^##+\s*(\d+)(?:[.\s]|$)")
# Eine Spanne tragen nur ZWEI Paragrafenzeichen (§§28-38); ein einzelnes § mit
# Bindestrich ist ein Verweis plus eine andere Zahl, keine Spanne (Fremdstimme).
# Striche: Bindestrich, Halbgeviert UND Geviert — letzteres ist die Hausschrift
# dieser Vorlage und fehlte (Blindpruefer).
# Ein Buchstabe direkt hinter der Zahl macht sie zu einer fremden Zaehlung
# (§32b ASVG) — dann ist es kein Verweis auf eine Lehre (Gegenpruefer).
VERWEIS = re.compile(r"(§§?)\s*(\d+)(?![0-9]*[A-Za-zÄÖÜäöü])"
                     r"(?:\s*[-–—]\s*(\d+)(?![0-9]*[A-Za-zÄÖÜäöü]))?")


def lies(pfad: str) -> str:
    try:
        with io.open(pfad, encoding="utf-8-sig") as datei:
            return datei.read()
    except (OSError, UnicodeDecodeError) as fehler:
        sys.stderr.write("Aufruffehler: %s nicht lesbar (%s).\n"
                         % (pfad, type(fehler).__name__))
        raise SystemExit(2)


def abschnitte(text: str) -> set:
    # Eine auskommentierte Lehre gibt es nicht: Mit dem Kopf im HTML-Kommentar blieb
    # ein Verweis auf sie gruen (gemessen in einem Kind-Repo, v1.18.13). Als Kommentar
    # zaehlt nur einer am Zeilenanfang (nach Leerraum) ausserhalb eines Zauns, Grenzen
    # im Kopf unter WAS ES NICHT PRUEFT: "<!--" in Inline-Code
    # schluckte sonst echte Abschnitte (Blind- und Gegenpruefer v1.19.0). Ein Kommentar
    # ohne Ende bleibt stehen, er ist eher ein Tippfehler als eine Streichung.
    zeilen = text.splitlines()
    sichtbar = []
    i = 0
    zaun = False
    while i < len(zeilen):
        anfang = zeilen[i].lstrip()
        if anfang.startswith(("```", "~~~")):
            zaun = not zaun
        elif not zaun and anfang.startswith("<!--"):
            ende = next((j for j in range(i, len(zeilen)) if "-->" in zeilen[j]), None)
            if ende is not None:
                i = ende + 1
                continue
        sichtbar.append(zeilen[i])
        i += 1
    return {int(t.group(1)) for t in (ABSCHNITT.match(z) for z in sichtbar) if t}


# Das Wort, an dem ein Verweis in die Zaehlung der VORLAGE erkannt wird
# (abgleich.md 2d: Vorlagen-Lehren werden als "Vorlage §N" zitiert). Nur am
# WORTANFANG — "Brief-Vorlage" oder "Prompt-Vorlage" sind keine Marke, "Vorlagen"
# und "Vorlagen-Lehre" schon. Gross geschrieben, wie das Substantiv.
VORLAGE_MARKE = re.compile(r"(?<![A-Za-zÄÖÜäöüß-])Vorlage")
# Hoechstens so viele Zeichen zwischen dem Wort und dem Verweis. Gemessen an zwei
# Kind-Repos: alle 26 echten Vorlagen-Verweise haben hoechstens 11 dazwischen
# ("Vorlage** (v1.9.0 §18)"); die zwei Beinahe-Treffer, bei denen ein EIGENER
# Verweis durchrutschte, hatten 55 und 75. Beide Pruefer haben es gefunden.
VORLAGE_FENSTER = 20
# Ein Satzteil-Trenner zwischen Wort und Verweis loest die Bindung: Komma,
# Semikolon, Gedanken- und Halbgeviertstrich, Satzzeichen mit folgendem Leerraum
# (der Punkt in "v1.11.0" trennt nicht).
SATZTEIL_TRENNER = re.compile(r"[,;—–]|[.:!?](?=\s)")


def aufteilen(zeile: str) -> tuple:
    """(lokal, vorlage) — die Nummern dieser Zeile als Text, nach Zaehlung getrennt.

    Ein Verweis gehoert der VORLAGE, wenn das Wort "Vorlage" (am Wortanfang)
    hoechstens VORLAGE_FENSTER Zeichen vor ihm steht, ohne Satzteil-Trenner und
    ohne einen anderen Verweis dazwischen. Das deckt "Vorlage §25", "aus der
    Vorlage (v1.11.0 §20)" und "in der Vorlage als §30"; in "Vorlage §8, bei uns
    §3" bleibt die §3 lokal, ebenso in "Die Vorlage regelt das anders; bei uns
    gilt §23". Ohne diese Trennung meldete das Werkzeug in einem
    Kind-Repo, das 2d befolgt, elf korrekte Vorlagen-Verweise als Verweise ins
    Leere — und keine Ausnahme machte es gruen.
    """
    lokal, vorlage, vorher = [], [], 0
    for t in VERWEIS.finditer(zeile):
        nummern = [t.group(2)]
        if t.group(3) is not None and t.group(1) == "§§":
            nummern.append(t.group(3))
        abschnitt = zeile[vorher:t.start()]
        marken = list(VORLAGE_MARKE.finditer(abschnitt))
        der_vorlage = False
        if marken:
            zwischen = abschnitt[marken[-1].end():]
            der_vorlage = (len(zwischen) <= VORLAGE_FENSTER
                           and not SATZTEIL_TRENNER.search(zwischen))
        (vorlage if der_vorlage else lokal).extend(nummern)
        vorher = t.end()
    return lokal, vorlage


def rohnummern(zeile: str) -> list:
    """Die LOKALEN Nummern dieser Zeile als Text (ohne Vorlagen-Verweise).

    Eine Stelle fuer beide Wege: die gepruefte Zeile und die von `--ausser`
    uebersprungene. Ohne sie zaehlt der eine Weg anders als der andere.
    """
    return aufteilen(zeile)[0]


def verweise(text: str, ausser=None, uebersprungen=None, entfernt=None,
             vorlage=None, vorlage_selbst=False) -> list:
    """[(Zeilennummer, Nummer)] — bei §§N-M beide Enden; `ausser` ueberspringt Zeilen.

    `uebersprungen` und `entfernt` sind Listen, die die Aufrufer nur ZAEHLEN: die
    ausgenommenen Zeilen und die Verweise, die dabei WEGGEFALLEN sind. Auf ihren
    Inhalt verlaesst sich nichts. Die zweite Zahl ist die
    aussagekraeftige: Uebersprungene Zeilen ohne Verweis kosten nichts, und eine
    Ausnahme, die Verweise wegnimmt, muss sich zeigen (Blindpruefer v1.17.1).
    `vorlage` nimmt die Verweise in die Zaehlung der Vorlage auf; sie werden
    nicht gegen die eigene Zaehlung geprueft, aber gezaehlt und gemeldet —
    ausser mit `vorlage_selbst`: Dann IST dies die Vorlage, und sie werden
    zusaetzlich wie eigene geprueft.
    """
    gefunden = []
    for nr, zeile in enumerate(text.splitlines(), 1):
        if ausser is not None and ausser.search(zeile):
            if uebersprungen is not None:
                uebersprungen.append(nr)
            vom_vorlage = aufteilen(zeile)[1]
            if vorlage is not None and not vorlage_selbst:
                # Ein Vorlagen-Verweis bleibt einer, auch auf einer ausgenommenen
                # Zeile; sonst haengt die gemeldete Zahl am Muster (Pruefer v1.17.2).
                vorlage.extend(vom_vorlage)
            if entfernt is not None:
                # Nicht umwandeln: eine uebersprungene Zeile wird nicht geprueft,
                # also darf eine absurde Zahl darin auch nicht abbrechen.
                entfernt.extend(rohnummern(zeile))
                if vorlage_selbst:
                    # In der Vorlage SIND es eigene Verweise: Nimmt die Ausnahme
                    # einen treffenden mit, ist das Muster zu weit. Ohne das legte
                    # "--ausser ...|Vorlage-Lehre" alle Verweise der
                    # Verfahrensdokumente still, und die Meldung behauptete, sie
                    # seien geprueft (Fremd-, Blind- und Gegenpruefer v1.18.1).
                    # Sie zaehlen dann nicht als geprueft (nicht in `vorlage`).
                    entfernt.extend(vom_vorlage)
            continue
        lokal, fremd = aufteilen(zeile)
        if vorlage is not None:
            vorlage.extend(fremd)
        if vorlage_selbst:
            lokal = lokal + fremd
        for rohzahl in lokal:
            try:
                gefunden.append((nr, int(rohzahl)))
            except ValueError:
                # CPython begrenzt die Ziffernzahl von int(); ohne den Faenger
                # endet ein absurder Verweis im Traceback mit Exit 1, also im
                # Code fuer "Verweis ins Leere" (Blindpruefer).
                sys.stderr.write("Aufruffehler: Zeile %d traegt eine Zahl, die "
                                 "Python nicht umwandelt.\n" % nr)
                raise SystemExit(2)
    return gefunden


def pruefen(lehren: str, dateien: list, ausser=None, vorlage_selbst=False) -> tuple:
    """(geprueft, Funde, ausgenommene Zeilen, entfernte, davon treffende, Vorlagen-Verweise).

    Die letzte Zahl ist die entscheidende: Ein von der Ausnahme entfernter
    Verweis, der einen Abschnitt TRIFFT, ist ein echter Lehren-Verweis — dann ist
    das Muster zu weit. Fremde Zaehlungen treffen keinen Abschnitt.
    """
    vorhanden = abschnitte(lies(lehren))
    if not vorhanden:
        sys.stderr.write("Aufruffehler: %s hat keine Abschnitte der Form '## N.'.\n" % lehren)
        raise SystemExit(2)
    hoechste = max(vorhanden)
    funde, gesamt, ausgenommen, weg, weg_treffend, der_vorlage = [], 0, 0, 0, 0, 0
    for pfad in dateien:
        text = lies(pfad)
        raus, verloren, fremd = [], [], []
        for zeilennr, nummer in verweise(text, ausser, raus, verloren, fremd, vorlage_selbst):
            gesamt += 1
            if nummer not in vorhanden:
                grund = ("ueber der hoechsten Nummer %d" % hoechste
                         if nummer > hoechste else "es gibt keinen Abschnitt %d" % nummer)
                funde.append("%s:%d: Verweis §%d — %s" % (pfad, zeilennr, nummer, grund))
        ausgenommen += len(raus)
        weg += len(verloren)
        der_vorlage += len(fremd)
        for rohzahl in verloren:
            try:
                # Eine Zahl, die Python nicht umwandelt, trifft auch keinen
                # Abschnitt — hier darf sie nicht abbrechen.
                if int(rohzahl) in vorhanden:
                    weg_treffend += 1
            except ValueError:
                pass
    return gesamt, funde, ausgenommen, weg, weg_treffend, der_vorlage


def wache_vorn(quelltext: str) -> bool:
    """Beginnt die Datei mit Docstring, "import sys" und GENAU der Wache?

    Token fuer Token gegen eine feste Form verglichen. Frei sind nur der Text des
    Docstrings und der Meldung (eine Folge gewoehnlicher Textliterale, kein
    f-String, keine Bytes), Kommentare, Leerzeilen und Leerraum zwischen den
    Token; die Datei ist UTF-8 (ein BOM ist erlaubt). Die Fassungen davor verglichen einzelne
    Bedingungen am Syntaxbaum, und jede Panel-Runde fand die naechste, die sich
    streichen liess, waehrend ein Schatten gewann (Blind- und Gegenpruefer
    v1.18.5, drei Runden). Auch dieser Vergleich laesst sich abschwaechen (etwa
    Operatoren nur nach Typ); die Gegenproben unten halten das fest. Strenger
    als noetig: Eine gleichwertige Umformung gilt als falsch (rot, nicht gruen).
    """
    import codecs
    import io
    import tokenize
    weg = (tokenize.COMMENT, tokenize.NL, tokenize.ENDMARKER)

    def form(text):
        aus = []
        try:
            # Als BYTES zerlegt, wie der Interpreter liest: Eine erklaerte
            # Kodierung ausser UTF-8 machte einen Kommentar zu Code (utf-7,
            # unicode_escape, raw_unicode_escape), waehrend diese Pruefung ihn als
            # Kommentar verwarf (Blind- und Gegenpruefer v1.18.7, gemessen).
            for t in tokenize.tokenize(io.BytesIO(text.encode("utf-8")).readline):
                if t.type == tokenize.ENCODING:
                    # Schreibweisen von UTF-8 (utf8, U8, cp65001) sind UTF-8;
                    # "utf-8-sig" meldet der Tokenizer bei einem BOM nur bis 3.11.
                    if codecs.lookup(t.string).name not in ("utf-8", "utf-8-sig"):
                        return []
                    continue
                if t.type in weg:
                    continue
                if t.type == tokenize.STRING:
                    # Nur gewoehnlicher Text zaehlt als Text: Ein f-String ist bis
                    # Python 3.11 ein STRING-Token, und sein Ausdruck liefe beim
                    # Start; Bytes liessen die Meldung mit TypeError statt Exit 2
                    # enden (Fremdpruefer v1.18.7).
                    vorsatz = t.string[:len(t.string) - len(t.string.lstrip("rRbBuUfF"))]
                    if set(vorsatz.lower()) & set("fb"):
                        aus.append(("KEIN-TEXT", vorsatz))
                        continue
                    if aus and aus[-1] == ("TEXT", ""):
                        continue
                    aus.append(("TEXT", ""))
                else:
                    aus.append((tokenize.tok_name[t.type], t.string))
        except Exception:
            # Jede Ausnahme ist nein, nie gruen: TokenError, SyntaxError,
            # LookupError und UnicodeError (unbekannte Kodierung, unter 3.14)
            # und SystemError (NUL hinter der Wache, unter 3.12; Gegen- und
            # Blindpruefer v1.18.8).
            return []
        return aus

    soll = form('"""Kopf."""\nimport sys\n'
                "if not (sys.flags.isolated and sys.flags.no_site):\n"
                "    sys.stderr.write('Meldung')\n    sys.exit(2)\n")
    return bool(soll) and form(quelltext)[:len(soll)] == soll


def selbstprobe() -> int:
    """Faelle mit bekanntem Ergebnis; ohne sie ist dieses Skript Disziplin."""
    geprueft = [0]
    fehler = []

    def erwarte(name, ist, soll):
        geprueft[0] += 1
        if ist != soll:
            fehler.append("%s: %r, erwartet %r" % (name, ist, soll))

    erwarte("Abschnitte: '## 3. Titel'", abschnitte("## 3. Titel\n"), {3})
    erwarte("Abschnitte: '### 12 Titel'", abschnitte("### 12 Titel\n"), {12})
    erwarte("Abschnitte: Fliesstext zaehlt nicht", abschnitte("Der 3. Versuch\n"), set())
    erwarte("Abschnitte: im HTML-Kommentar zaehlt nicht",
            abschnitte("## 1. Bleibt\n<!--\n## 2. Weg\n-->\n## 3. Bleibt\n"), {1, 3})
    erwarte("Abschnitte: Kommentar ohne Ende bleibt stehen",
            abschnitte("<!-- offen\n## 2. Da\n"), {2})
    erwarte("Abschnitte: zwei Kommentare, der Abschnitt dazwischen bleibt",
            abschnitte("<!--\n## 1. W\n-->\n## 2. Da\n<!--\n## 3. W\n-->\n"), {2})
    erwarte("Abschnitte: Marke in Inline-Code schluckt nichts",
            abschnitte("## 1. A `<!--`\n## 2. B\n## 3. C `-->`\n"), {1, 2, 3})
    erwarte("Abschnitte: Marke im Zaun schluckt nichts",
            abschnitte("```\n<!--\n```\n## 2. B\n<!--\n## 3. W\n-->\n"), {2})
    erwarte("Abschnitte: '## Vor jedem Slice' zaehlt nicht",
            abschnitte("## Vor jedem Slice: fuenf Fragen\n"), set())
    erwarte("Verweise: einfach", [n for _, n in verweise("siehe §7 dort")], [7])
    erwarte("Verweise: mit Leerraum", [n for _, n in verweise("siehe § 7")], [7])
    erwarte("Verweise: Spanne mit Halbgeviert",
            [n for _, n in verweise("unsere §§28–38 hangen an")], [28, 38])
    erwarte("Verweise: Spanne mit Bindestrich",
            [n for _, n in verweise("§§4-6")], [4, 6])
    erwarte("Verweise: zwei in einer Zeile",
            [n for _, n in verweise("§17, §21")], [17, 21])
    erwarte("Verweise: Zeilennummer stimmt",
            verweise("nichts\nhier §5\n"), [(2, 5)])
    erwarte("Verweise: ohne Zahl kein Verweis", verweise("§ und weiter"), [])

    # Die Form "Vorlage §N" (abgleich.md 2d). Die ersten fuenf Faelle stehen so in
    # einem Kind-Repo, das 2d befolgt; dort meldete das Werkzeug elf korrekte
    # Vorlagen-Verweise als Verweise ins Leere (gemessen).
    erwarte("Vorlage: 'Vorlage §25'", aufteilen("Vorlage §25: Ein Befehl"), ([], ["25"]))
    erwarte("Vorlage: 'aus der Vorlage (v1.11.0 §20)'",
            aufteilen("Übernommen aus der Vorlage (v1.11.0 §20), mit Beleg"), ([], ["20"]))
    erwarte("Vorlage: 'in der Vorlage als §30'",
            aufteilen("Unser Fall, in der Vorlage als §30 verallgemeinert."), ([], ["30"]))
    erwarte("Vorlage: 'aus der Vorlage (dort §22'",
            aufteilen("Übernommen aus der Vorlage (dort §22, drei Belege"), ([], ["22"]))
    erwarte("Vorlage: 'Vorlage (v1.9.0 §18)' — Nummer, die es auch lokal gibt",
            aufteilen("Vorlage** (v1.9.0 §18). Zwei Projekte"), ([], ["18"]))
    erwarte("Vorlage: danach ein eigener Verweis bleibt lokal",
            aufteilen("Vorlage §8, bei uns §3"), (["3"], ["8"]))
    erwarte("Vorlage: ein Verweis VOR dem Wort bleibt lokal",
            aufteilen("Unser §4 kommt aus der Vorlage §21"), (["4"], ["21"]))
    erwarte("Vorlage: Spanne gehoert ganz der Vorlage",
            aufteilen("aus der Vorlage §§28–38"), ([], ["28", "38"]))
    erwarte("Vorlage: auch 'Vorlagen-Lehre'",
            aufteilen("Die Vorlagen-Lehre §21 sagt"), ([], ["21"]))
    erwarte("Vorlage: ohne das Wort alles lokal",
            aufteilen("Nach §1 und §2"), (["1", "2"], []))
    erwarte("Vorlage: verweise() liefert nur die lokalen",
            [n for _, n in verweise("Vorlage §20, dazu §1")], [1])
    _fremd = []
    verweise("Vorlage §20, dazu §1", vorlage=_fremd)
    erwarte("Vorlage: verweise() sammelt die Vorlagen-Verweise getrennt", _fremd, ["20"])

    # Die drei Bedingungen, jede einzeln. Die stille Richtung — ein EIGENER
    # Verweis rutscht als Vorlagen-Verweis durch — haben beide Pruefer an
    # echtem Text gezeigt, sobald der Absatz anders umbrochen war; die beiden
    # Zeilen hier sind diese Stellen, zusammengezogen.
    erwarte("Vorlage: Trenner — Gedankenstrich und Komma loesen die Bindung",
            aufteilen("an die Vorlage gemeldet — und bei uns behoben statt abgewartet, "
                      "weil §15 gilt"), (["15"], []))
    erwarte("Vorlage: Trenner — Komma und Semikolon",
            aufteilen("(Vorlage, Fund eines anderen Projekts — nicht dieses Repos; "
                      "eigene Funde stehen in §12)"), (["12"], []))
    erwarte("Vorlage: Trenner — Semikolon allein",
            aufteilen("Die Vorlage; §23"), (["23"], []))
    erwarte("Vorlage: Punkt in einer Versionsnummer trennt nicht",
            aufteilen("aus der Vorlage (v1.11.0 §20)"), ([], ["20"]))
    erwarte("Vorlage: Satzende mit Leerraum trennt",
            aufteilen("Das steht in der Vorlage. §7"), (["7"], []))
    erwarte("Vorlage: Wortanfang — ein Kompositum ist keine Marke",
            aufteilen("Die Brief-Vorlage §12"), (["12"], []))
    erwarte("Vorlage: klein geschrieben ist keine Marke",
            aufteilen("siehe vorlage §20"), (["20"], []))
    _genau = "Vorlage" + "x" * 19 + " §5"
    erwarte("Vorlage: Fenster — 20 Zeichen dazwischen binden noch",
            aufteilen(_genau), ([], ["5"]))
    erwarte("Vorlage: Fenster — 21 Zeichen dazwischen binden nicht",
            aufteilen("Vorlage" + "x" * 20 + " §5"), (["5"], []))
    erwarte("Vorlage: Fenster — 'Vorlagen-Version ... unser §4' bleibt lokal",
            aufteilen("Seit der Vorlagen-Version v1.16.0 gilt unser §4"), (["4"], []))
    erwarte("Vorlage: Aufzaehlung — nur der erste gehoert der Vorlage (benannte Grenze)",
            aufteilen("Vorlage §20 und §21"), (["21"], ["20"]))
    # Jeder Trenner einzeln, je innerhalb des Fensters: Sonst entschied in den
    # Faellen oben das Fenster, und ein Trenner liess sich streichen
    # (Folge-Issue zu v1.17.2, gemessen).
    for _zeichen in (",", "—", "–", ":", "!", "?"):
        erwarte("Vorlage: Trenner %r im Fenster loest die Bindung" % _zeichen,
                aufteilen("Vorlage%s bei uns §3" % _zeichen), (["3"], []))
    # Und mitten im Fenster, mit Text VOR dem Trenner: Sonst blieb ein Umbau
    # gruen, der den Trenner nur am Anfang des Zwischenraums sucht (match statt
    # search) — und ein eigener Verweis ins Leere lief still als Vorlagen-Verweis
    # durch (Blind- und Gegenpruefer v1.18.8, gemessen).
    for _zeichen in (",", ";", "—", "–", ".", ":", "!", "?"):
        erwarte("Vorlage: Trenner %r mitten im Fenster loest die Bindung" % _zeichen,
                aufteilen("Vorlage sagt%s bei uns §3" % _zeichen), (["3"], []))
    erwarte("Vorlage: Gedankenstrich ohne Leerraum trennt",
            aufteilen("Vorlage—bei uns §3"), (["3"], []))
    erwarte("Vorlage: Punkt vor einem Tab trennt",
            aufteilen("Vorlage sagt.\tbei uns §3"), (["3"], []))
    erwarte("Vorlage: ASCII-Bindestrich mit Leerraum trennt nicht (benannt)",
            aufteilen("Vorlage - §3"), ([], ["3"]))
    erwarte("Vorlage: zwei Marken — die LETZTE vor dem Verweis zaehlt",
            aufteilen("Vorlage steht weit vor dem Verweis und Vorlage §3"), ([], ["3"]))
    for _wort in ("TestVorlage", "PDFVorlage", "ÄVorlage", "ÖVorlage", "ÜVorlage",
                  "äVorlage", "öVorlage", "üVorlage", "MaßVorlage"):
        erwarte("Vorlage: ein Buchstabe direkt davor macht keine Marke (%s)" % _wort,
                aufteilen(_wort + " §3"), (["3"], []))
    erwarte("Verweise: Spanne mit Buchstaben am Ende zaehlt nur den Anfang",
            [n for _, n in verweise("§§1-9a")], [1])
    erwarte("Verweise: Spanne mit mehrstelligem Ende und Buchstaben zaehlt nur den Anfang",
            [n for _, n in verweise("§§1-99a")], [1])
    erwarte("Verweise: fremde Zaehlung mit Buchstabe (§32b) zaehlt nicht",
            verweise("Pflicht nach §32b ASVG"), [])
    erwarte("Verweise: §43 mit Gesetzesnamen zaehlt (nur --ausser hilft)",
            [n for _, n in verweise("Frist nach § 43 B-KUVG")], [43])
    erwarte("Verweise: --ausser nimmt die Zeile heraus",
            verweise("Frist nach § 43 B-KUVG", re.compile("B-KUVG")), [])
    erwarte("Verweise: Spanne mit Geviertstrich",
            [n for _, n in verweise("unsere §§28—38")], [28, 38])
    erwarte("Verweise: einzelnes § mit Strich ist KEINE Spanne",
            [n for _, n in verweise("siehe §28-38")], [28])
    erwarte("Abschnitte: '## 9' am Dateiende ohne Zeilenumbruch",
            abschnitte("## 9"), {9})

    with tempfile.TemporaryDirectory() as d:
        lehren = os.path.join(d, "lehren.md")
        text = os.path.join(d, "text.md")

        def schreib(pfad, inhalt):
            with io.open(pfad, "w", encoding="utf-8", newline="\n") as datei:
                datei.write(inhalt)

        schreib(lehren, "## 1. Eins\n## 2. Zwei\nsiehe §1\n")
        schreib(text, "Verweis auf §2 — gut.\n")
        gesamt, funde, _raus, _weg, _tr, _vl = pruefen(lehren, [lehren, text])
        erwarte("gruen: alle Verweise treffen", funde, [])
        erwarte("gruen: beide Dateien gelesen", gesamt, 2)

        schreib(text, "Verweis auf §9 — es gibt nur zwei.\n")
        gesamt, funde, _raus, _weg, _tr, _vl = pruefen(lehren, [lehren, text])
        erwarte("rot: Verweis ueber der hoechsten Nummer", len(funde), 1)
        erwarte("rot: Meldung nennt die hoechste Nummer",
                "ueber der hoechsten Nummer 2" in funde[0], True)
        erwarte("rot: Meldung nennt Datei und Zeile", ":1: Verweis §9" in funde[0], True)

        schreib(lehren, "## 1. Eins\n## 3. Drei\n")
        schreib(text, "Verweis auf §2 — die Nummer fehlt in der Mitte.\n")
        gesamt, funde, _raus, _weg, _tr, _vl = pruefen(lehren, [lehren, text])
        erwarte("rot: Luecke in der Nummerierung", len(funde), 1)
        erwarte("rot: Meldung nennt den fehlenden Abschnitt",
                "es gibt keinen Abschnitt 2" in funde[0], True)

        # Der Fall, den dieses Skript NICHT faengt — als Erwartung festgehalten,
        # damit niemand ihm mehr zutraut, als es kann.
        schreib(lehren, "## 1. Eins\n## 2. Zwei\n")
        schreib(text, "Verweis auf §1, gemeint war die Lehre, die hier §2 ist.\n")
        gesamt, funde, _raus, _weg, _tr, _vl = pruefen(lehren, [lehren, text])
        erwarte("Grenze: falscher, aber existierender Verweis bleibt unentdeckt", funde, [])

        schreib(text, "kein Verweis\n")
        gesamt, funde, _raus, _weg, _tr, _vl = pruefen(lehren, [text])
        erwarte("gruen: Datei ohne Verweise", (gesamt, funde), (0, []))

        # Die Ausnahme muss sich ZEIGEN — sonst legt ein zu weites Muster den
        # Waechter still (Blindpruefer der letzten Runde von v1.17.0).
        schreib(lehren, "## 1. Eins\n## 2. Zwei\n")
        schreib(text, "Verweis auf §1.\nFrist nach § 43 B-KUVG.\nNoch ein §2.\n")
        gesamt, funde, raus, weg, treffend, _vl = pruefen(lehren, [text], re.compile("B-KUVG"))
        erwarte("Ausnahme: zaehlt die uebersprungenen Zeilen", raus, 1)
        erwarte("Ausnahme: zaehlt die dabei entfernten Verweise", weg, 1)
        erwarte("Ausnahme: die uebrigen Verweise werden geprueft", (gesamt, funde), (2, []))
        gesamt, funde, raus, weg, treffend, _vl = pruefen(lehren, [text], re.compile("."))
        erwarte("Ausnahme: ein zu weites Muster nimmt alle Zeilen heraus", raus, 3)
        erwarte("Ausnahme: und dabei alle Verweise", weg, 3)
        erwarte("Ausnahme: dann bleibt kein Verweis uebrig", gesamt, 0)
        # Die entscheidende Zahl: wie viele der entfernten TREFFEN einen Abschnitt.
        # Fremde Zaehlungen treffen keinen, echte Lehren-Verweise schon.
        erwarte("Ausnahme: zaehlt die entfernten, die einen Abschnitt treffen",
                treffend, 2)
        gesamt, funde, raus, weg, treffend, _vl = pruefen(
            lehren, [text], re.compile("trifft-nichts"))
        erwarte("Ausnahme: ein Muster ohne Treffer nimmt nichts heraus", (raus, weg), (0, 0))
        erwarte("Ausnahme: ohne Muster wird nichts uebersprungen",
                pruefen(lehren, [text])[2:5], (0, 0, 0))
        # Eine Zeile OHNE Verweis kostet nichts: uebersprungen ja, entfernt nein.
        # Ohne diese Trennung machte der rote Fall einen legitimen Baum rot.
        schreib(text, "Nur Text, kein Verweis.\nNoch eine Zeile.\n")
        erwarte("Ausnahme: uebersprungene Zeile ohne Verweis entfernt keinen",
                pruefen(lehren, [text], re.compile("Nur Text"))[2:5], (1, 0, 0))
        # Zwei Dateien und ein Wert > 1: ohne diesen Fall blieben fuenf Mutationen
        # an der gedruckten Zahl gruen (Blindpruefer v1.17.1, gemessen).
        zweit = os.path.join(d, "zweit.md")
        schreib(text, "Frist nach § 43 B-KUVG.\nVerweis auf §1.\nNoch § 44 B-KUVG.\n")
        schreib(zweit, "Auch hier § 45 B-KUVG.\nUnd §2.\n")
        erwarte("Ausnahme: summiert ueber zwei Dateien",
                pruefen(lehren, [text, zweit], re.compile("B-KUVG"))[2:5], (3, 3, 0))
        # Und die TREFFENDEN je Datei: Ein ausgerueckter Zaehlblock lief nur fuer
        # die letzte Datei, und die Selbstprobe blieb gruen (Blindpruefer,
        # Nacharbeit 1 zu v1.18.4). Im Gate ist die letzte Datei ein Skript.
        schreib(text, "Siehe §1 (B-KUVG).\n")
        schreib(zweit, "Auch §2 (B-KUVG).\n")
        erwarte("Ausnahme: treffende aus beiden Dateien gezaehlt",
                pruefen(lehren, [text, zweit], re.compile("B-KUVG"))[3:5], (2, 2))

        # main() selbst: der Exit-Code-Vertrag des Kopfes. Ohne diese drei
        # Erwartungen liesse sich der Zweck des Werkzeugs still entfernen —
        # "if funde:" auf "if False:" gedreht blieb die Selbstprobe gruen und ein
        # Gate mit "... || exit 1" dauerhaft still (Blindpruefer, gemessen).
        # main() druckt dabei; stumm gestellt, weil eine gruene Selbstprobe im
        # Gate-Protokoll nicht nach einem Befund aussehen darf. Die abgefangene
        # Meldung wird gleich mitgepinnt.
        def stumm(argv):
            """(Exit-Code, gedruckte Ausgabe) — beide Stroeme abgefangen.

            SystemExit wird wie auf der Befehlszeile in einen Code uebersetzt:
            Einige Fehlerwege brechen ab, statt zurueckzugeben, und ohne diesen
            Faenger endete die ganze Selbstprobe still mit deren Code.
            """
            alt_out, alt_err = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = fang = io.StringIO()
            try:
                return main(argv), fang.getvalue()
            except SystemExit as ende:
                return (ende.code if isinstance(ende.code, int) else 1), fang.getvalue()
            finally:
                sys.stdout, sys.stderr = alt_out, alt_err

        schreib(lehren, "## 1. Eins\n## 2. Zwei\n")
        schreib(text, "Verweis auf §2.\n")
        rc, ausgabe = stumm(["prog", "--lehren", lehren, text])
        erwarte("main: alle Verweise treffen -> Exit 0", rc, 0)
        erwarte("main: gruene Meldung nennt die Zahl der Verweise",
                "1 Verweise in 1 Datei" in ausgabe, True)
        schreib(text, "Verweis auf §9.\n")
        rc, ausgabe = stumm(["prog", "--lehren", lehren, text])
        erwarte("main: Verweis ins Leere -> Exit 1", rc, 1)
        erwarte("main: rote Meldung nennt Datei, Zeile und Nummer",
                "text.md:1: Verweis §9" in ausgabe, True)
        erwarte("main: rote Meldung nennt die Regel 2d", "abgleich.md, 2d" in ausgabe, True)
        rc, ausgabe = stumm(["prog", "--lehren"])
        erwarte("main: fehlendes Argument -> Exit 2", rc, 2)
        # Die uebrigen Regeln des Vertrags, jede als eigene Mutation gepinnt
        # (Gegenpruefer: acht Regeln waren es nicht).
        schreib(text, "Verweis auf §1.\nFrist nach § 43 B-KUVG.\n")
        rc, ausgabe = stumm(["prog", "--lehren", lehren, text])
        erwarte("main: Gesetzeszitat ohne --ausser -> Exit 1", rc, 1)
        rc, ausgabe = stumm(["prog", "--lehren", lehren, "--ausser", "B-KUVG", text])
        erwarte("main: --ausser macht dieselbe Datei gruen", rc, 0)
        erwarte("main: die gruene Meldung nennt das Muster",
                "Ausnahme 'B-KUVG'" in ausgabe, True)
        erwarte("main: die gruene Meldung nennt die Zahl der uebersprungenen Zeilen",
                "1 Zeile(n) uebersprungen" in ausgabe, True)
        erwarte("main: die gruene Meldung nennt die entfernten Verweise",
                "1 Verweis(e) entfernt" in ausgabe, True)
        erwarte("main: die gruene Meldung verlangt beide Zahlen im Abgleich-Issue",
                "beide Zahlen gehoeren" in ausgabe and "Abgleich-Issue" in ausgabe,
                True)
        erwarte("main: ohne Ausnahme steht kein Ausnahme-Satz in der Meldung",
                "uebersprungen" in stumm(["prog", "--lehren", lehren, text])[1], False)
        # Die gedruckten Ziffern bei zwei Dateien und Werten > 1.
        schreib(text, "Frist nach § 43 B-KUVG.\nVerweis auf §1.\nNoch § 44 B-KUVG.\n")
        schreib(zweit, "Auch hier § 45 B-KUVG.\nUnd §2.\n")
        rc, ausgabe = stumm(["prog", "--lehren", lehren, "--ausser", "B-KUVG",
                             text, zweit])
        erwarte("main: zwei Dateien -> Exit 0", rc, 0)
        erwarte("main: gedruckte Zahlen stimmen bei mehreren Dateien",
                "3 Zeile(n) uebersprungen und dabei 3 Verweis(e) entfernt" in ausgabe,
                True)
        # Der BLOCKER: ein Baum, dessen Dateien nur fremde Zaehlungen tragen,
        # bleibt gruen — auch wenn die Ausnahme dort Verweise wegnimmt und keiner
        # uebrig bleibt. Die erste Fassung dieser Regel machte ihn rot, ohne
        # gruenen Ausweg (Blindpruefer v1.17.1, gemessen).
        schreib(text, "Frist nach § 43 B-KUVG.\n")
        rc, ausgabe = stumm(["prog", "--lehren", lehren, "--ausser", "B-KUVG", text])
        erwarte("main: nur fremde Zaehlungen, keine eigene -> gruen", rc, 0)
        erwarte("main: und meldet, dass ein Verweis entfernt wurde",
                "1 Verweis(e) entfernt" in ausgabe, True)
        # Ein Muster ohne Treffer aendert nichts.
        schreib(text, "Nur Text, kein Verweis.\n")
        erwarte("main: Muster ohne Treffer bleibt gruen",
                stumm(["prog", "--lehren", lehren, "--ausser", "trifft-nichts", text])[0], 0)
        # Und der rote Fall: die Ausnahme nimmt einen TREFFENDEN Verweis mit.
        schreib(text, "Verweis auf §1.\nFrist nach § 43 B-KUVG.\n")
        rc, ausgabe = stumm(["prog", "--lehren", lehren, "--ausser", ".", text])
        erwarte("main: Ausnahme nimmt einen treffenden Verweis mit -> Exit 1", rc, 1)
        erwarte("main: und sagt, dass das Muster zu weit ist",
                "Muster ist zu weit" in ausgabe, True)
        erwarte("main: der rote Fall nennt Muster und die drei Zahlen",
                "'.'" in ausgabe and "1 Verweis(e) mit, die einen Abschnitt TREFFEN"
                in ausgabe and "2 entfernten in 2 Zeile(n)" in ausgabe, True)
        # Ein enges Muster, das nur die fremde Zaehlung trifft, bleibt gruen —
        # OBWOHL ein eigener Verweis im Satz steht.
        erwarte("main: enges Muster neben einem echten Verweis bleibt gruen",
                stumm(["prog", "--lehren", lehren, "--ausser", "B-KUVG", text])[0], 0)
        rc, ausgabe = stumm(["prog", "--lehren", lehren, "--ausser", "[", text])
        erwarte("main: kaputtes --ausser-Muster -> Exit 2", rc, 2)
        rc, ausgabe = stumm(["prog", "--lehren", lehren, "--ausser", "x"])
        erwarte("main: --ausser ohne Datei -> Exit 2", rc, 2)
        schreib(lehren, "kein Abschnitt hier\n")
        schreib(text, "Verweis auf §1.\n")
        rc, ausgabe = stumm(["prog", "--lehren", lehren, text])
        erwarte("main: Lehren-Datei ohne '## N.' -> Exit 2", rc, 2)
        erwarte("main: Selbstprobe-Schalter wird exakt geprueft",
                stumm(["prog", "--selbstprobe", "zusatz"])[0], 2)
        # BOM: utf-8-sig, sonst ist die erste Ueberschrift unsichtbar
        with io.open(lehren, "w", encoding="utf-8-sig", newline="\n") as datei:
            datei.write("## 1. Eins\n")
        erwarte("Abschnitte: Datei mit BOM wird gelesen", abschnitte(lies(lehren)), {1})
        erwarte("Abschnitte: eine Raute genuegt NICHT", abschnitte("# 9. Titel\n"), set())
        # Eigener Lauf statt einer Variablen von weiter oben: ein spaeter
        # eingeschobener Fall hat "ausgabe" neu belegt, und die Erwartung pruefte
        # seither den falschen Text (beim Bauen dieser Runde passiert).
        _, hilfe = stumm(["prog"])
        # Der Fall aus dem Kind-Repo, Ende zu Ende: zwei eigene Abschnitte,
        # Vorlagen-Verweise mit Nummern darueber UND darunter. Vorher rot ohne
        # gruenen Ausweg; jetzt gruen, und die Meldung zaehlt sie.
        schreib(lehren, "## 1. Eins\n## 2. Zwei\n")
        schreib(text, "Übernommen aus der Vorlage (v1.11.0 §20).\n"
                      "Vorlage §2 — die Nummer gibt es auch hier.\n"
                      "Unser eigener Verweis §1.\n")
        erwarte("Vorlage: pruefen() zaehlt die Vorlagen-Verweise getrennt",
                pruefen(lehren, [text])[0:2] + pruefen(lehren, [text])[5:], (1, [], 2))
        rc, ausgabe = stumm(["prog", "--lehren", lehren, text])
        erwarte("main: Vorlagen-Verweise machen nicht rot", rc, 0)
        erwarte("main: die Meldung nennt die Zahl der Vorlagen-Verweise",
                "Dazu 2 Verweis(e) in der Form 'Vorlage §N'" in ausgabe, True)
        # Und die Ausnahme zaehlt sie nicht als "entfernt": Sie werden ohnehin
        # nicht geprueft, also nimmt ihr Ueberspringen nichts weg.
        rc, ausgabe = stumm(["prog", "--lehren", lehren, "--ausser", "Vorlage", text])
        erwarte("main: --ausser ueber Vorlagen-Zeilen bleibt gruen", rc, 0)
        erwarte("main: und entfernt dabei keinen eigenen Verweis",
                "dabei 0 Verweis(e) entfernt" in ausgabe, True)
        # Die Zahl der Vorlagen-Verweise ueber ZWEI Dateien: ohne diesen Fall
        # blieb "=" statt "+=" gruen, und auf echten Bestaenden verschwand der
        # Satz, weil die letzte Datei keinen traegt (beide Pruefer, gemessen).
        schreib(zweit, "Vorlage §31 und dazu Vorlage §32.\n")
        erwarte("Vorlage: pruefen() summiert die Vorlagen-Verweise ueber Dateien",
                pruefen(lehren, [text, zweit])[5], 4)
        schreib(zweit, "Nur §1.\n")
        erwarte("main: ohne Vorlagen-Verweise steht kein Vorlagen-Satz",
                "Form 'Vorlage" in stumm(["prog", "--lehren", lehren, zweit])[1], False)
        # Ausgenommene Zeilen: die Vorlagen-Verweise darauf werden trotzdem gezaehlt.
        rc, ausgabe = stumm(["prog", "--lehren", lehren, "--ausser", "Vorlage", text])
        erwarte("main: Vorlagen-Verweise auf ausgenommenen Zeilen zaehlen mit",
                "Dazu 2 Verweis(e) in der Form 'Vorlage §N'" in ausgabe, True)
        # Der rote Pfad mit Vorlagen-Verweisen: Hinweis und Zahl stehen dort auch.
        schreib(zweit, "Vorlage §20 und ein eigener §9.\n")
        rc, ausgabe = stumm(["prog", "--lehren", lehren, zweit])
        erwarte("main: roter Pfad mit Vorlagen-Verweis -> Exit 1", rc, 1)
        erwarte("main: roter Pfad nennt die Form 'Vorlage §N' als Abhilfe",
                "steht als 'Vorlage §N'" in ausgabe, True)
        erwarte("main: roter Pfad nennt die Zahl der Vorlagen-Verweise",
                "Dazu 1 Verweis(e) in der Form 'Vorlage §N'" in ausgabe, True)
        # --vorlage-selbst (v1.18.1): In der Vorlage zeigt "Vorlage §N" in die
        # eigene Zaehlung und wird mit dem Schalter GEPRUEFT. Ohne ihn bleibt
        # derselbe Text gruen — genau der Zustand, in dem die Vorlage die
        # Pruefung ihrer eigenen Verweise verloere.
        schreib(lehren, "## 1. Eins\n## 2. Zwei\n")
        schreib(zweit, "Vorlage-Lehre §2 und Vorlage-Lehre §99.\n")
        erwarte("vorlage-selbst: ohne Schalter gruen (Vorlagen-Verweise ungeprueft)",
                stumm(["prog", "--lehren", lehren, zweit])[0], 0)
        rc, ausgabe = stumm(["prog", "--lehren", lehren, "--vorlage-selbst", zweit])
        erwarte("vorlage-selbst: §99 ins Leere -> Exit 1", rc, 1)
        erwarte("vorlage-selbst: der Fund nennt §99", "Verweis §99" in ausgabe, True)
        erwarte("vorlage-selbst: pruefen() prueft beide und zaehlt sie als Vorlagen-Verweise",
                (pruefen(lehren, [zweit], None, True)[0], len(pruefen(lehren, [zweit], None, True)[1]),
                 pruefen(lehren, [zweit], None, True)[5]), (2, 1, 2))
        schreib(zweit, "Vorlage-Lehre §2 und ein eigener §1.\n")
        rc, ausgabe = stumm(["prog", "--lehren", lehren, "--vorlage-selbst", zweit])
        erwarte("vorlage-selbst: treffende -> gruen, die Meldung nennt den Schalter",
                (rc, "mit --vorlage-selbst gegen DIESE Zaehlung geprueft" in ausgabe), (0, True))
        erwarte("vorlage-selbst: Gesamtzahl enthaelt die Vorlagen-Verweise",
                "Verweise gruen: 2 Verweise" in ausgabe, True)
        # Reihenfolge der beiden Schalter frei, jeder hoechstens einmal.
        schreib(zweit, "Vorlage-Lehre §99 (B-KUVG).\nVorlage-Lehre §98.\n")
        erwarte("vorlage-selbst: nach --ausser wirkt er ebenso (Exit 1 an §98)",
                stumm(["prog", "--lehren", lehren, "--ausser", "B-KUVG", "--vorlage-selbst", zweit])[0], 1)
        erwarte("vorlage-selbst: vor --ausser wirkt er ebenso (Exit 1 an §98)",
                stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--ausser", "B-KUVG", zweit])[0], 1)
        erwarte("vorlage-selbst: doppelt -> Exit 2",
                stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--vorlage-selbst", zweit])[0], 2)
        erwarte("vorlage-selbst: --ausser doppelt -> Exit 2",
                stumm(["prog", "--lehren", lehren, "--ausser", "a", "--ausser", "b", zweit])[0], 2)
        erwarte("vorlage-selbst: Schalter ohne Datei -> Exit 2",
                stumm(["prog", "--lehren", lehren, "--vorlage-selbst"])[0], 2)
        erwarte("main: Aufruffehler nennt alle Aufrufformen, auch --vorlage-selbst",
                "--vorlage-selbst" in hilfe, True)
        # Ausnahme UND Schalter: Ein Vorlagen-Verweis auf einer ausgenommenen Zeile
        # ist in der Vorlage ein eigener — trifft er, ist das Muster zu weit
        # (Fremd-, Blind- und Gegenpruefer v1.18.1: vorher Exit 0, und die Meldung
        # nannte ihn "geprueft").
        schreib(zweit, "Vorlage-Lehre §1 (B-KUVG).\nVorlage-Lehre §2.\n")
        erwarte("vorlage-selbst + --ausser: treffender Vorlagen-Verweis entfernt -> Exit 1",
                stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--ausser", "B-KUVG", zweit])[0], 1)
        # Dieselbe Regel fuer einen EIGENEN Verweis unter dem Schalter: Ein Umbau,
        # der in der Vorlage nur noch die Vorlagen-Verweise als entfernt zaehlt,
        # blieb sonst gruen (Blindpruefer, Nacharbeit 1).
        schreib(zweit, "Ein eigener §1 (B-KUVG).\nVorlage-Lehre §2.\n")
        erwarte("vorlage-selbst + --ausser: treffender EIGENER Verweis entfernt -> Exit 1",
                stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--ausser", "B-KUVG", zweit])[0], 1)
        # Zwei Verweise auf EINER ausgenommenen Zeile, der treffende an zweiter
        # Stelle: Ein Umbau, der je Zeile nur den ersten als entfernt zaehlt, blieb
        # sonst gruen — fuer Vorlagen-Verweise unter dem Schalter und fuer eigene
        # schon seit v1.17.1 (Blindpruefer, Nacharbeit 2 zu v1.18.1).
        schreib(zweit, "Vorlage-Lehre §99 und Vorlage-Lehre §1 (B-KUVG).\nVorlage-Lehre §2.\n")
        erwarte("vorlage-selbst + --ausser: treffender zweiter Vorlagen-Verweis einer Zeile -> Exit 1",
                stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--ausser", "B-KUVG", zweit])[0], 1)
        schreib(zweit, "Ein §99 und ein §1 (B-KUVG).\nEin eigener §2.\n")
        erwarte("--ausser: treffender zweiter eigener Verweis einer Zeile -> Exit 1",
                stumm(["prog", "--lehren", lehren, "--ausser", "B-KUVG", zweit])[0], 1)
        # Und gespiegelt: der treffende an ERSTER Stelle. Sonst blieb ein Umbau
        # gruen, der je Zeile nur den LETZTEN zaehlt (Blind- und Gegenpruefer
        # v1.18.3, je gemessen).
        schreib(zweit, "Vorlage-Lehre §1 und Vorlage-Lehre §99 (B-KUVG).\nVorlage-Lehre §2.\n")
        erwarte("vorlage-selbst + --ausser: treffender erster Vorlagen-Verweis einer Zeile -> Exit 1",
                stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--ausser", "B-KUVG", zweit])[0], 1)
        schreib(zweit, "Ein §1 und ein §99 (B-KUVG).\nEin eigener §2.\n")
        erwarte("--ausser: treffender erster eigener Verweis einer Zeile -> Exit 1",
                stumm(["prog", "--lehren", lehren, "--ausser", "B-KUVG", zweit])[0], 1)
        # Gemischte Zeilen unter dem Schalter: ein Gesetzeszitat UND ein treffender
        # Vorlagen-Verweis, und umgekehrt ein Vorlagen-Verweis UND ein treffender
        # eigener. Ein Umbau, der je Zeile nur eine der beiden Arten als entfernt
        # zaehlt, blieb sonst gruen (Gegenpruefer, Nacharbeit 1 zu v1.18.3). Je
        # einmal steht der treffende hinten und vorn: Ein Umbau, der je Zeile nur
        # die Art des LETZTEN Verweises zaehlt, blieb mit nur der ersten Reihenfolge
        # gruen (Blindpruefer, Nacharbeit 2).
        schreib(zweit, "Frist nach § 43 B-KUVG, siehe Vorlage-Lehre §1.\nVorlage-Lehre §2.\n")
        erwarte("vorlage-selbst + --ausser: Gesetzeszitat und treffender Vorlagen-Verweis -> Exit 1",
                stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--ausser", "B-KUVG", zweit])[0], 1)
        schreib(zweit, "Vorlage-Lehre §99, dazu ein eigener §1 (B-KUVG).\nVorlage-Lehre §2.\n")
        erwarte("vorlage-selbst + --ausser: Vorlagen-Verweis und treffender eigener -> Exit 1",
                stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--ausser", "B-KUVG", zweit])[0], 1)
        schreib(zweit, "Vorlage-Lehre §1, dazu § 43 (B-KUVG).\nVorlage-Lehre §2.\n")
        erwarte("vorlage-selbst + --ausser: treffender Vorlagen-Verweis vor Gesetzeszitat -> Exit 1",
                stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--ausser", "B-KUVG", zweit])[0], 1)
        schreib(zweit, "Ein eigener §1, siehe Vorlage-Lehre §99 (B-KUVG).\nVorlage-Lehre §2.\n")
        erwarte("vorlage-selbst + --ausser: treffender eigener vor Vorlagen-Verweis -> Exit 1",
                stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--ausser", "B-KUVG", zweit])[0], 1)
        # Drei Verweise auf einer ausgenommenen Zeile, der treffende vorn, in der
        # Mitte und hinten, dazu einer, der nicht die kleinste Nummer ist, und eine
        # Spanne. Umbauten, die je Zeile hoechstens zwei, nur den ersten und den
        # letzten, nur die kleinste Nummer oder nur das erste Ende einer Spanne als
        # entfernt zaehlen, blieben sonst gruen (Blind- und Gegenpruefer v1.18.4).
        for art, vor in (("eigene", "ein "), ("Vorlagen", "Vorlage-Lehre ")):
            for fall in ("{v}§2, {v}§97 und {v}§98", "{v}§97, {v}§2 und {v}§0",
                         "{v}§97, {v}§98 und {v}§2", "{v}§§0-2"):
                zeile = fall.format(v=vor)
                schreib(zweit, "Siehe " + zeile + " (B-KUVG).\nVorlage-Lehre §2.\n")
                erwarte("vorlage-selbst + --ausser: %s, '%s' -> Exit 1" % (art, zeile),
                        stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--ausser",
                               "B-KUVG", zweit])[0], 1)
                # Dieselben Zeilen ohne Schalter, wie ein Projekt das Werkzeug
                # faehrt: Ein Umbau nur dieses Wegs blieb sonst gruen (Blindpruefer,
                # Nacharbeit 1 zu v1.18.4).
                if art == "eigene":
                    erwarte("--ausser ohne Schalter: '%s' -> Exit 1" % zeile,
                            stumm(["prog", "--lehren", lehren, "--ausser", "B-KUVG",
                                   zweit])[0], 1)
        # Der treffende ist nicht unter den zwei kleinsten Nummern: Lehren mit Luecke.
        # Ein Umbau, der nur die zwei kleinsten zaehlt, blieb sonst gruen (ebenda).
        luecke = os.path.join(d, "luecke.md")
        schreib(luecke, "## 1. Eins\n## 5. Fuenf\n")
        for art, vor, schalter in (("eigene", "ein ", ["--vorlage-selbst"]),
                                   ("Vorlagen", "Vorlage-Lehre ", ["--vorlage-selbst"]),
                                   ("eigene", "ein ", [])):
            zeile = "{v}§3, {v}§4 und {v}§5".format(v=vor)
            schreib(zweit, "Siehe " + zeile + " (B-KUVG).\nVorlage-Lehre §1.\n")
            erwarte("--ausser %s: %s, '%s' -> Exit 1" % (" ".join(schalter) or "ohne Schalter",
                                                          art, zeile),
                    stumm(["prog", "--lehren", luecke] + schalter + ["--ausser", "B-KUVG",
                                                                     zweit])[0], 1)
        # Mehrere Dateien bis main(): treffender Verweis nur in der ERSTEN.
        schreib(text, "Siehe Vorlage-Lehre §1 (B-KUVG).\n")
        schreib(zweit, "Vorlage-Lehre §2.\n")
        erwarte("vorlage-selbst + --ausser: treffender nur in der ersten Datei -> Exit 1",
                stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--ausser", "B-KUVG",
                       text, zweit])[0], 1)
        schreib(text, "Siehe §1 (B-KUVG).\n")
        schreib(zweit, "Nur §2.\n")
        erwarte("--ausser ohne Schalter: treffender nur in der ersten Datei -> Exit 1",
                stumm(["prog", "--lehren", lehren, "--ausser", "B-KUVG", text, zweit])[0], 1)
        schreib(zweit, "Vorlage-Lehre §99 (B-KUVG).\nVorlage-Lehre §2.\n")
        rc, ausgabe = stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--ausser", "B-KUVG", zweit])
        erwarte("vorlage-selbst + --ausser: nicht treffender entfernt -> gruen, als entfernt gezaehlt",
                (rc, "dabei 1 Verweis(e) entfernt" in ausgabe), (0, True))
        # Die ZAHL in der Meldung, nicht nur der Text: geprueft wird nur, was nicht
        # uebersprungen ist (Gegenpruefer: die Zahl liess sich durch 0 ersetzen).
        erwarte("vorlage-selbst: die Meldung zaehlt nur die gepruefte (1, nicht 2)",
                "Davon 1 in der Form 'Vorlage §N'" in ausgabe, True)
        schreib(zweit, "Vorlage-Lehre §1 und Vorlage-Lehre §2.\n")
        erwarte("vorlage-selbst: die Meldung nennt die Zahl (2)",
                "Davon 2 in der Form 'Vorlage §N'"
                in stumm(["prog", "--lehren", lehren, "--vorlage-selbst", zweit])[1], True)
        # Funde aus der ERSTEN von zwei Dateien: Ein Umbau, der die Funde je Datei
        # zuruecksetzte, blieb gruen (Blindpruefer, Nacharbeit 2 zu v1.18.4).
        schreib(text, "Siehe §99.\n")
        schreib(zweit, "Siehe §1.\n")
        erwarte("pruefen: Fund nur in der ersten Datei wird gemeldet",
                len(pruefen(lehren, [text, zweit])[1]), 1)
        erwarte("main: Fund nur in der ersten Datei -> Exit 1",
                stumm(["prog", "--lehren", lehren, text, zweit])[0], 1)
        # Und unter dem Schalter: Vorlagen-Verweis ins Leere nur in der ZWEITEN.
        schreib(text, "Vorlage-Lehre §1.\n")
        schreib(zweit, "Vorlage-Lehre §99.\n")
        erwarte("vorlage-selbst: Verweis ins Leere nur in der zweiten Datei -> Exit 1",
                stumm(["prog", "--lehren", lehren, "--vorlage-selbst", text, zweit])[0], 1)
        # Eine Spanne, die nur am ERSTEN Ende trifft (ebenda, K1).
        for art, vor, schalter in (("eigene", "ein ", []),
                                   ("Vorlagen", "Vorlage-Lehre ", ["--vorlage-selbst"])):
            schreib(zweit, "Siehe " + vor + "§§1-99 (B-KUVG).\nVorlage-Lehre §2.\n")
            erwarte("--ausser: %s Spanne, nur das erste Ende trifft -> Exit 1" % art,
                    stumm(["prog", "--lehren", lehren] + schalter
                          + ["--ausser", "B-KUVG", zweit])[0], 1)
        # Eine entfernte Nummer IN einer Luecke der Lehren trifft nichts: gruen.
        schreib(zweit, "Frist nach § 3 (B-KUVG).\nEin eigener §1.\n")
        erwarte("--ausser: entfernte Nummer in einer Luecke -> gruen",
                stumm(["prog", "--lehren", luecke, "--ausser", "B-KUVG", zweit])[0], 0)
        # Eine Zahl, die int() nicht umwandelt: in einer ausgenommenen Zeile gruen,
        # in einer geprueften ein Aufruffehler (Folge-Issue zu v1.17.1, je ein
        # Faenger, der sich sonst streichen liess).
        schreib(zweit, "Frist " + "§" + "9" * 6000 + " (B-KUVG).\nEin eigener §1.\n")
        erwarte("--ausser: ausgenommene Zeile mit 6000 Ziffern -> gruen",
                stumm(["prog", "--lehren", lehren, "--ausser", "B-KUVG", zweit])[0], 0)
        # Ob int() 6000 Ziffern ablehnt, haengt am Interpreter (Ziffernlimit seit
        # 3.11 und in Sicherheits-Releases davor). Ohne Limit ist es ein Verweis
        # ins Leere (Exit 1); mit Limit greift der Faenger (Exit 2). Die erste
        # Fassung setzte das Limit voraus (Fremdpruefer v1.18.8).
        try:
            int("9" * 6000)
            _soll_lang = 1
        except ValueError:
            _soll_lang = 2
        schreib(zweit, "Frist " + "§" + "9" * 6000 + ".\n")
        erwarte("main: gepruefte Zeile mit 6000 Ziffern -> Exit %d" % _soll_lang,
                stumm(["prog", "--lehren", lehren, zweit])[0], _soll_lang)
        # Das Muster unterscheidet Gross- und Kleinschreibung: Ein Umbau mit re.I
        # nahm "bao" mit, und ein treffender Verweis fiel still weg (Blindpruefer).
        schreib(zweit, "Siehe §1 der bao-Liste.\n")
        erwarte("--ausser: Muster unterscheidet Gross- und Kleinschreibung -> gruen",
                stumm(["prog", "--lehren", lehren, "--ausser", "BAO", zweit])[0], 0)
        # Nicht lesbare Dateien sind Aufruffehler (Exit 2), nicht Exit 1.
        erwarte("main: fehlende Datei -> Exit 2",
                stumm(["prog", "--lehren", lehren, os.path.join(d, "gibt-es-nicht.md")])[0], 2)
        with io.open(os.path.join(d, "latin.md"), "wb") as _f:
            _f.write("Grüße §1\n".encode("latin-1"))
        erwarte("main: Datei nicht in UTF-8 -> Exit 2",
                stumm(["prog", "--lehren", lehren, os.path.join(d, "latin.md")])[0], 2)
        # Der rote Pfad "zu weit" nennt die Vorlagen-Verweise und den Ausweg.
        schreib(zweit, "Nach §1 gilt die Frist des § 43 B-KUVG.\nVorlage §5 bleibt.\n")
        rc, ausgabe = stumm(["prog", "--lehren", lehren, "--ausser", "B-KUVG", zweit])
        erwarte("main: 'zu weit' nennt die Vorlagen-Verweise und den Ausweg",
                (rc, "Vorlagen-Verweise ('Vorlage §N'): 1" in ausgabe, "eigene Zeile" in ausgabe),
                (1, True, True))
        # Unter dem Schalter sagt dieselbe Meldung, dass sie geprueft sind.
        schreib(zweit, "Nach Vorlage-Lehre §1 gilt § 43 B-KUVG.\nVorlage-Lehre §2.\n")
        erwarte("main: 'zu weit' unter --vorlage-selbst nennt sie geprueft",
                "mit --vorlage-selbst gegen diese Zaehlung geprueft"
                in stumm(["prog", "--lehren", lehren, "--vorlage-selbst", "--ausser", "B-KUVG",
                          zweit])[1], True)
        # Der Funde-Pfad ohne Vorlagen-Verweise nennt keine "Dazu 0".
        schreib(zweit, "Nur §99.\n")
        rc, ausgabe = stumm(["prog", "--lehren", lehren, zweit])
        erwarte("main: Funde ohne Vorlagen-Verweise, kein 'Dazu'",
                (rc, "Dazu" in ausgabe), (1, False))
        erwarte("main: Aufruffehler nennt die Aufrufformen (dazu --vorlage-selbst oben)",
                "--selbstprobe" in hilfe and "--lehren" in hilfe
                and "--ausser" in hilfe, True)

    # Die Schalter-Wache am Kopf: ohne -I -S verweigert das Werkzeug den Lauf,
    # statt ungeschuetzt zu pruefen. Gemessen am echten Aufruf, nicht nachgebaut,
    # und fuer JEDE Haelfte: nur -I, nur -S, keiner — eine Wache, die nur einen
    # Schalter prueft, blieb sonst gruen (Blind- und Gegenpruefer v1.18.0, drei
    # Mutanten). Das Kind bekommt "--wache-probe", nicht "--selbstprobe": Ohne
    # Wache startete die erste Fassung sich selbst ohne Ende (Blindpruefer, ueber
    # 70 Prozesse). Ohne Wache endet es so mit einem Aufruffehler, dessen Meldung
    # nicht der Text der Wache ist — rot. Dazu eine Zeitgrenze. Und die STELLE der
    # Wache: Das Kind ist eine Kopie neben einer tempfile.py, die den Lauf mit
    # Exit 0 beendet. Steht die Wache hinter den Importen, gewinnt der Schatten
    # (Blindpruefer, Nacharbeit 1: die Wache hinter die Importe geschoben blieb
    # sonst gruen).
    import shutil
    import subprocess
    schattenort = tempfile.mkdtemp(prefix="lv-wache-")
    try:
        kopie = os.path.join(schattenort, os.path.basename(__file__))
        shutil.copy(os.path.abspath(__file__), kopie)
        with io.open(os.path.join(schattenort, "tempfile.py"), "w", encoding="utf-8") as f:
            f.write("raise SystemExit(0)\n")
        for name, schalter in (("keiner", []), ("nur -I", ["-I"]), ("nur -S", ["-S"])):
            try:
                kind = subprocess.run([sys.executable] + schalter + [kopie, "--wache-probe"],
                                      capture_output=True, timeout=60)
                ergebnis = (kind.returncode, b"laeuft nur mit -I -S" in kind.stderr)
            except subprocess.TimeoutExpired:
                ergebnis = ("Zeitgrenze", False)
            erwarte("Wache: Schalter %s, tempfile.py daneben -> Exit 2 mit der Meldung der Wache"
                    % name, ergebnis, (2, True))
    finally:
        shutil.rmtree(schattenort, ignore_errors=True)
    # Und STELLE und FORM, Token fuer Token, fuer jedes Modul: Die tempfile.py
    # oben deckt nur das eine, das sie nachbildet (wache_vorn()).
    with io.open(os.path.abspath(__file__), encoding="utf-8") as f:
        erwarte("Wache: erste Anweisung nach 'import sys', kein Import davor",
                wache_vorn(f.read()), True)
    # Die Pruefung selbst, an erfundenem Quelltext: die echte Form mit ja, jeder
    # gemessene Angriff und jede Umformung mit nein (Blind- und Gegenpruefer
    # v1.18.5; Fassung mit Token-Vergleich v1.18.7).
    k, s, j = '"""Kopf."""\n', "import sys\n", "import json\n"
    w = ("if not (sys.flags.isolated and sys.flags.no_site):\n"
         "    sys.stderr.write('x')\n    sys.exit(2)\n")
    for name, quelle in (
            ("Wache vor dem ersten Import", k + s + w + j),
            ("Meldung ueber zwei Zeilen, Kommentar dazwischen",
             k + "# Kopf\n" + s + w.replace("write('x')", "write('a '  # Teil\n                     'b')") + j),
            ("Datei mit BOM", "\ufeff" + k + s + w + j),
            ("Kodierungszeile utf8", "# -*- coding: utf8 -*-\n" + k + s + w + j)):
        erwarte("wache_vorn: %s -> ja" % name, wache_vorn(quelle), True)
    for name, quelle in (
            ("ohne Docstring", s + w),
            ("zwei Docstrings", k + k + s + w),
            ("Zuweisung statt Docstring", "__import__('json').x = 'Kopf.'\n" + s + w),
            ("Import vor 'import sys'", k + j + s + w),
            ("Wache hinter 'import json'", k + s + j + w),
            ("'import sys, json'", k + "import sys, json\n" + w),
            ("'import sys as s'", k + "import sys as s\n" + w),
            ("'import json' statt 'import sys'", k + j + w),
            ("'from subprocess import sys'", k + "from subprocess import sys\n" + w),
            ("nur 'import sys'", k + s),
            ("andere Bedingung", k + s + w.replace("(sys.flags.isolated and sys.flags.no_site)",
                                                    "sys.flags.isolated")),
            ("Bedingung mit 'and __import__'", k + s + w.replace("no_site):", "no_site) and __import__('json'):")),
            ("Import im Rumpf vorn", k + s + w.replace("    sys.stderr", "    import json\n    sys.stderr")),
            ("Import statt Meldung", k + s + w.replace("sys.stderr.write('x')", "import json")),
            ("Import statt sys.exit", k + s + w.replace("sys.exit(2)", "import json")),
            ("Anweisung nach sys.exit", k + s + w + "    import json\n"),
            ("sys.exit(0)", k + s + w.replace("sys.exit(2)", "sys.exit(0)")),
            ("print statt Meldung", k + s + w.replace("sys.stderr.write('x')", "print('x')")),
            ("print(2) statt sys.exit(2)", k + s + w.replace("sys.exit(2)", "print(2)")),
            ("Meldung mit zweitem Argument", k + s + w.replace("write('x')", "write('x', 'y')")),
            ("Meldung mit Schluesselwort", k + s + w.replace("write('x')", "write('x', end='')")),
            ("Meldung als Ausdruck mit __import__", k + s + w.replace("write('x')", "write(__import__('json').dumps(1))")),
            ("Meldung als Name", k + s + w.replace("write('x')", "write(x)")),
            ("Meldung leer", k + s + w.replace("write('x')", "write()")),
            ("Text plus Ausdruck", k + s + w.replace("write('x')", "write('x' + __import__('json').x)")),
            ("f-String als Meldung", k + s + w.replace("write('x')", "write(f'{__import__(1)}')")),
            ("Text und f-String als Meldung", k + s + w.replace("write('x')", "write('x' f'{1}')")),
            ("(__import__ and sys.exit)(2)", k + s + w.replace("sys.exit(2)", "(__import__('json') and sys.exit)(2)")),
            ("(__import__ and sys).exit(2)", k + s + w.replace("sys.exit(2)", "(__import__('json') and sys).exit(2)")),
            ("sys.exit(2, **...)", k + s + w.replace("sys.exit(2)", "sys.exit(2, **({} if __import__('json') else {}))")),
            ("Wache auf einer Zeile", k + s + "if not (sys.flags.isolated and sys.flags.no_site): "
                                        "sys.stderr.write('x'); sys.exit(2)\n" + j),
            ("Quelltext nicht lesbar", k + s + "if (\n"),
            ("zwei Token statt Docstring", "x\n" + s + w),
            ("Kodierung utf-7 mit verstecktem Import",
             "# -*- coding: utf-7 -*-\n" + k + "import sys  # +AAo-import json\n" + w),
            ("Kodierung raw_unicode_escape",
             "# -*- coding: raw_unicode_escape -*-\n" + k + "import sys  # \\u000aimport json\n" + w),
            ("Kodierung unicode_escape",
             "# -*- coding: unicode_escape -*-\n" + k + "import sys  # \\nimport json\n" + w),
            ("Kodierung latin-1", "# -*- coding: latin-1 -*-\n" + k + s + w),
            ("Tab-Einzug", k + s + w.replace("    sys.", "\tsys.")),
            ("zwei Leerzeichen Einzug", k + s + w.replace("    sys.", "  sys.")),
            ("rb-Bytes als Meldung", k + s + w.replace("write('x')", "write(rb'x')")),
            ("Kodierung undefined", "# -*- coding: undefined -*-\n" + k + s + w),
            ("NUL im Kommentar vor der Wache", k + s + "# \x00\n" + w),
            ("NUL hinter der Wache", k + s + w + "x = 1  # \x00\n"),
            ("eckige statt runde Klammern", k + s + w.replace("(sys.flags.isolated and sys.flags.no_site)",
                                                              "[sys.flags.isolated and sys.flags.no_site]")),
            ("Bytes als Meldung", k + s + w.replace("write('x')", "write(b'x')")),
            ("Bytes als Docstring", "b" + k + s + w),
            ("Text und Bytes als Meldung", k + s + w.replace("write('x')", "write('x' b'y')"))):
        erwarte("wache_vorn: %s -> nein" % name, wache_vorn(quelle), False)

    erwarte("mindestens 246 Erwartungen", geprueft[0] >= 246, True)
    if fehler:
        sys.stderr.write("Selbstprobe ROT: %d Abweichung(en)\n  " % len(fehler)
                         + "\n  ".join(fehler) + "\n")
        return 1
    print("Selbstprobe gruen: %d Erwartungen (Abschnitts- und Verweiserkennung, "
          "Spannen mit drei Strichen, Luecke, Meldungstext, die drei Exit-Codes von "
          "main). Nicht geprueft: ob ein Verweis auf die GEMEINTE Lehre zeigt — das "
          "kann dieses Skript nicht." % geprueft[0])
    return 0


def main(argv: list) -> int:
    # Ohne das scheitert die Ausgabe auf einer Konsole mit Codepage 850/437 an
    # einem Gedankenstrich, mit Exit 1 — eine gruene Probe risse so die
    # Gate-Zeile (`... || exit 1`) mit. Dieselbe Zeile steht in ast-gleich.py.
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if argv[1:] == ["--selbstprobe"]:
        return selbstprobe()

    if len(argv) < 4 or argv[1] != "--lehren":
        sys.stderr.write(
            "Aufruffehler: --lehren <lehren.md> und mindestens eine zu pruefende Datei.\n"
            "    python -I -S lehren-verweise-pruefen.py --lehren docs/agents/lehren.md "
            "docs/agents/*.md CLAUDE.md\n"
            "    python -I -S lehren-verweise-pruefen.py --lehren <lehren.md> "
            "--ausser \"B-KUVG|ASVG\" <datei> …\n"
            "    python -I -S lehren-verweise-pruefen.py --selbstprobe\n"
            "    python -I -S lehren-verweise-pruefen.py --lehren <lehren.md> --vorlage-selbst "
            "<datei> …   (nur in der Vorlage)\n")
        return 2

    lehren, rest = argv[2], argv[3:]
    ausser = None
    vorlage_selbst = False
    while rest[:1] in (["--ausser"], ["--vorlage-selbst"]):
        if rest[0] == "--vorlage-selbst":
            if vorlage_selbst:
                sys.stderr.write("Aufruffehler: --vorlage-selbst doppelt.\n")
                return 2
            vorlage_selbst = True
            rest = rest[1:]
            continue
        if ausser is not None:
            sys.stderr.write("Aufruffehler: --ausser doppelt — ein Muster, mit | verbunden.\n")
            return 2
        if len(rest) < 3:
            sys.stderr.write("Aufruffehler: --ausser braucht ein Muster und mindestens "
                             "eine Datei.\n")
            return 2
        try:
            ausser = re.compile(rest[1])
        except re.error as fehler:
            sys.stderr.write("Aufruffehler: --ausser ist kein gueltiges Muster (%s).\n"
                             % fehler)
            return 2
        rest = rest[2:]
    dateien = rest
    if not dateien:
        sys.stderr.write("Aufruffehler: keine zu pruefende Datei genannt.\n")
        return 2
    gesamt, funde, ausgenommen, entfernt, entfernt_treffend, der_vorlage = pruefen(
        lehren, dateien, ausser, vorlage_selbst)
    # Vorlagen-Verweise werden nicht geprueft, aber sichtbar gezaehlt: Wer sie
    # nicht sieht, haelt eine wachsende Zahl davon fuer "alles gut". Mit
    # --vorlage-selbst sind sie in der Gesamtzahl enthalten und geprueft.
    if vorlage_selbst:
        vorlage_satz = (" Davon %d in der Form 'Vorlage §N' — mit --vorlage-selbst gegen "
                        "DIESE Zaehlung geprueft (das ist die Vorlage)." % der_vorlage)
    else:
        vorlage_satz = (" Dazu %d Verweis(e) in der Form 'Vorlage §N' — nicht gegen die "
                        "eigene Zaehlung geprueft." % der_vorlage) if der_vorlage else ""
    # Die Ausnahme ist fuer FREMDE Zaehlungen da, und die treffen keinen Abschnitt.
    # Nimmt sie einen Verweis mit, der TRIFFT, hat sie einen echten Lehren-Verweis
    # verschluckt — dann ist das Muster zu weit, gleich wie viele uebrig bleiben.
    # Warum nicht "keiner uebrig": Das ist nicht entscheidbar. Genau so sieht ein
    # junges Repo aus, dessen Dateien nur fremde Zaehlungen tragen — die erste
    # Fassung dieser Regel machte es rot, ohne gruenen Ausweg (Blindpruefer
    # v1.17.1, gemessen). Die Zahl der treffenden ist dagegen eindeutig.
    if entfernt_treffend:
        sys.stderr.write(
            "Die Ausnahme %r nimmt %d Verweis(e) mit, die einen Abschnitt TREFFEN "
            "(von %d entfernten in %d Zeile(n)) — das Muster ist zu weit und legt "
            "die Pruefung teilweise still.\n"
            "Die Ausnahme ist fuer fremde Zaehlungen gedacht; die treffen keinen "
            "Abschnitt. Muster engen, bis diese Zahl 0 ist. Steht ein Lehren-Verweis "
            "mit einem Zitat in EINER Zeile, gehoert das Zitat auf eine eigene Zeile: "
            "--ausser arbeitet zeilenweise.\n"
            % (ausser.pattern, entfernt_treffend, entfernt, ausgenommen))
        # Auch hier die Vorlagen-Verweise: Sonst fehlte ihre Zahl genau im Pfad,
        # in dem ein Muster zu weit griff (Folge-Issue zu v1.17.2). Ein eigener
        # Satz, weil "Dazu"/"Davon" hier keine Gesamtzahl hat (Blindpruefer v1.18.8).
        if der_vorlage:
            sys.stderr.write("Vorlagen-Verweise ('Vorlage §N'): %d%s.\n" % (
                der_vorlage, " — mit --vorlage-selbst gegen diese Zaehlung geprueft"
                if vorlage_selbst else ", nicht gegen die eigene Zaehlung geprueft"))
        return 1
    if funde:
        sys.stderr.write("Verweise ins Leere (%d von %d):\n  " % (len(funde), gesamt)
                         + "\n  ".join(funde) + "\n"
                         "Beim Uebernehmen einer Lehre werden auch die Verweise IN ihrem "
                         "Text auf die eigene Zaehlung umgeschrieben (abgleich.md, 2d); "
                         "ein Verweis in die Zaehlung der Vorlage steht als 'Vorlage §N'.\n"
                         + (vorlage_satz.strip() + "\n" if vorlage_satz else ""))
        # Auch der rote Pfad nennt die Ausnahme: Sonst sieht niemand, dass neben
        # den Funden noch Verweise weggefallen sind (Blindpruefer v1.17.1).
        if ausser is not None:
            sys.stderr.write("Ausnahme %r: %d Zeile(n) uebersprungen, dabei %d "
                             "Verweis(e) entfernt, davon %d treffende.\n"
                             % (ausser.pattern, ausgenommen, entfernt,
                                entfernt_treffend))
        return 1
    # Muster und Zahlen gehoeren in die MELDUNG: Ein Gate, das nur den Exit-Code
    # liest, saehe sonst nicht, was die Ausnahme weggenommen hat. Ein zu weites
    # Muster faellt seit v1.17.1 nicht mehr nur auf, es wird rot (oben); die
    # Zahlen hier tragen den Fall, der GRUEN bleiben darf: fremde Zaehlungen, die
    # keinen Abschnitt treffen. Auch dann gehoeren sie ins Abgleich-Issue, damit
    # eine wachsende Ausnahme auffaellt.
    print("Verweise gruen: %d Verweise in %d Datei(en), alle treffen einen Abschnitt "
          "von %s.%s%s Nicht geprueft: ob ein Verweis die GEMEINTE Lehre trifft."
          % (gesamt, len(dateien), lehren, vorlage_satz,
             (" Ausnahme %r hat %d Zeile(n) uebersprungen und dabei %d Verweis(e) "
              "entfernt, keinen treffenden — beide Zahlen gehoeren in das "
              "Abgleich-Issue."
              % (ausser.pattern, ausgenommen, entfernt)) if ausser is not None else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
