#!/usr/bin/env python3
r"""Gate-Probe fuer prod-readonly-hook.py: STRUKTUR statt Teilstring, IDENTITAET
statt Form.

(Roher Text, siehe das r vor den Anfuehrungszeichen: Der Aufruf unten nutzt
Backslash am Zeilenende als Fortsetzung.)

VORLAGE — eine Zeile im LOKALEN Gate, bei JEDEM Lauf, mit DEMSELBEN
absoluten Interpreter, der im Hook-Befehl steht:

    ⟨/absoluter/pfad/zu/python3⟩ -I -S docs/vorlagen/waechter-gate-probe.py \
      --einstellungen ⟨pfad/zu/den/agenten-einstellungen.json⟩ \
      --matcher '⟨PREFIX⟩.*' \
      --befehl '⟨der "command"-Wert aus den Agenten-Einstellungen, unveraendert⟩' \
      --unbekannt '⟨PREFIX⟩gate_probe_erfunden' \
      --lesend '⟨ein Name aus der allowlist⟩' \
      --quelle docs/vorlagen/prod-readonly-hook.py \
      --werkzeuge ⟨datei mit allen Werkzeugnamen des Namensraums, eine je Zeile⟩ || exit 1

WAS SIE BEWEIST (Exit 0 nur, wenn ALLES gilt)
---------------------------------------------
1. Die Einstellungsdatei ist lesbares JSON mit einem Objekt an der Spitze.
2. Kein bekannter Schalter schaltet die Hooks ab (AUS_SCHALTER / AN_SCHALTER,
   rekursiv ueber alle Ebenen).
3. Unter hooks.PreToolUse gibt es einen Eintrag mit GENAU diesem Matcher
   (fehlender, leerer und null-Matcher zaehlen als "bewacht alles").
4. In dessen "hooks"-Liste steht ein Eintrag mit "type": "command" und GENAU
   dem erwarteten Befehl — zeichengenau, nicht als Teilstring.
4a. DER BEFEHL IST  <interpreter> -I -S <waechter.py>  UND NICHTS SONST:
   * vier Woerter nach Shell-Regeln, in der Mitte -I -S in dieser Reihenfolge.
     -I: keine Umgebungsvariablen, keine Benutzer-Pakete, kein Skriptpfad;
     -S: kein site — keine sitecustomize.py, keine .pth aus dem site-packages
     des Interpreters. Ohne -S entscheidet, wer dort schreiben darf (ohne
     Admin, gemessen), ueber jeden Aufruf mit: Eine sitecustomize.py, die
     json.load umbiegt, liess alles gruen und jeden Schreibaufruf durch
     (Gegenpruefer, Nacharbeit 4). Waechter und Probe brauchen nur die
     Standardbibliothek;
   * keine Shell-Metazeichen im ganzen Befehl ($ ` ~ * ? [ ] { } ; & | < >
     ( ) ! % ^ ' # @ , Zeilenumbruch) und kein Backslash (Pfade mit "/",
     zitiert nur mit ") — sonst waere, was die Probe liest, nicht das, was
     die Shell ausfuehrt (Gegenpruefer: ein $NICHTGESETZT im Pfad liess die
     Probe eine byte-gleiche Datei pruefen, waehrend sh eine Fremdfassung
     startete). Die Liste vereinigt sh, cmd.exe (% ^ , und ', das cmd.exe
     nicht als Anfuehrungszeichen kennt — gemessen: sh und cmd.exe oeffnen
     dann verschiedene Dateien) und PowerShell (# @ , `): Welche Shell der
     Client unter Windows nimmt, ist nicht belegt (ein fremdes Hook-Projekt
     brauchte dort einen Hook ohne Shell), also sind alle drei verboten;
   * der Interpreter ist DERSELBE PFAD wie der, mit dem diese Probe laeuft:
     zeichengleich nach Pfad-Normalisierung UND os.path.samefile gegen
     sys.executable. (Normalisierung, gemessen: os.path.abspath macht
     absolut, loest "." und ".." auf und setzt auf Windows "/" zu "\" —
     deshalb besteht der mit "/" geschriebene Hook-Befehl gegen
     sys.executable, das "\" traegt; os.path.normcase gleicht zusaetzlich
     die Gross-/Kleinschreibung an, auf POSIX aendert es nichts.) Das ist
     mehr als ein Pfad, dessen Name mit "python" beginnt (ein sh-Skript
     namens python3-hook bestand die Form und verzweigte), und mehr als
     dieselbe Datei (ein Hardlink des Interpreters an anderem Ort
     bestand samefile und loeste dort sein eigenes site-packages auf; beides
     Gegenpruefer, gemessen). Deshalb steht in der Gate-Zeile derselbe
     absolute Interpreter wie im Hook-Befehl, Zeichen fuer Zeichen;
   * die .py ist ein absoluter Pfad auf eine vorhandene Datei.
4b. Die .py ist BYTE-GLEICH mit --quelle (Pflicht). Ohne das kann die
   Kopie verzweigen — auf tool_input, auf ein Argument — und alles andere
   bleibt gruen (Blindpruefer, gemessen). Mit Form (4a) und Identitaet (4b)
   laeuft bei echten Aufrufen dieselbe Datei mit demselben Interpreter und
   derselben Umgebung wie in dieser Probe: -I -S laesst nur die
   Standardbibliothek des Interpreters zu, und die ist die Grenze
   (Echtprobe). Damit die Probe dasselbe misst, muss sie SELBST mit -I -S
   laufen — sonst Aufbau-Fehler (Exit 2).
   Und die .py IMPORTIERT NUR json, os, sys — als "import x", ohne Alias,
   ohne "from" — und BENUTZT AN DIESEN MODULEN NUR, was die Vorlage braucht:
   sys.argv/exit/stderr/stdin/stdout, os.path mit abspath/basename/dirname/
   join/splitext, json.dumps/load. Die drei Namen kommen nur als
   Attribut-Basis vor, nie als Wert — und os.path ebenso (es ist selbst ein
   Modul und traegt sys; "p = os.path; p.sys.path" war der Weg der fuenften
   Runde). Das sind zwei Allowlists (Importe und Modul-Attribute), per
   Syntaxbaum gemessen, und DAS ist, was diese Pruefung BEWEIST: Kein Import
   holt die Umgebung zurueck, die -S ausschliesst — weder ueber sys.path
   (den die Quelle nicht anfassen kann, auch nicht als os.sys.path oder s =
   sys), noch ueber sys.modules, meta_path, remote_exec, monitoring oder was
   der Interpreter in einer spaeteren Version an sys und os anbaut. Vier
   Panel-Runden hatten je einen weiteren Weg an den drei Modulen gefunden
   (from-Import, Alias, getattr, Frames, sys.path.insert, os.sys.path,
   sys.remote_exec), solange die Regel eine Denylist war; die Allowlist
   macht die Liste ueberfluessig. Dazu FAENGT sie (kein Beweis): Attribute
   wie system, popen, exec*, spawn*, fork, modules, environ, exc_info,
   settrace, remove, rename, renames, symlink, chmod, os.open, fdopen,
   pwrite, ftruncate (ein Waechter aendert nichts am Dateisystem; .write nur
   an sys.stdout und sys.stderr fuer seine Meldung), jedes Attribut mit "_"
   am Anfang (ausser __name__) und die Reflexionswege zu Rahmen, Code und
   Generatoren (f_*, tb_*, gi_*, cr_*, ag_*, co_*) — an jedem Empfaenger;
   Namen wie eval, exec, __import__, getattr, globals, vars, builtins — auch
   als Wert; Zeichenketten, die ein solches Modul oder eine solche Funktion
   benennen; open() nur als direkter Aufruf, lesend, mit woertlichem Modus,
   ohne * und **, nie als Wert; kein Umbiegen erlaubter Modulattribute
   (sys.stdout = …, del sys.argv). Der Fang gilt fuer Objekte jenseits der
   drei Module (Zeichenketten, Dateien, Klassen); an den Modulen selbst gilt
   die Allowlist. Auch der Fang ist eine Liste: Was nicht darin steht,
   faengt er nicht (Gegenpruefer, dritte Runde: os.open + os.write standen
   nicht darin, waehrend der Kopf "write" nannte). Die erlaubten Attribute
   liefern Objekte, an denen nur noch der Fang gilt: Dateiobjekte
   (sys.stdin/stdout/stderr), die Liste sys.argv, Ergebnisse von os.path.*
   und json.load — und die FUNKTIONEN selbst (os.path.join, json.load,
   sys.exit): Ein Funktionsobjekt traegt sein Modul (__globals__, __self__),
   erreichbar nur ueber "__"-Attribute, und die sperrt der Fang, nicht die
   Allowlist (Blindpruefer, sechste Runde). Format-Zeichenketten koennen
   solche Attribute LESEN ('{0.__globals__[os]}'.format(os.path.join)), aber
   nichts aufrufen — ein Leck, kein Ausbruch. Und die Standardbibliothek
   laedt sich selbst nach, ohne dass ein import dasteht ('x'.encode('idna')
   laedt encodings.idna) — aus dem Interpreter, nie aus der -S-Umgebung;
   auch das sieht der Baum nicht. Alles Grenze, nicht Zusage. GRENZE,
   ausdruecklich: Ein Fang sperrt die bekannten Wege, nicht alle. Python
   bietet Reflexion ueber Rahmen, Klassen und Namensraeume, die sich nie
   vollstaendig aufzaehlen laesst; jede Panel-Runde fand einen weiteren Weg
   (Literalname os; from-Import; Alias; getattr;
   sys._getframe().f_builtins). Eine Quelle, die die Probe taeuschen will,
   gehoert zur Klasse "Quelle taeuscht Probe" — die prueft der Diff im Panel
   (kritische Datei, volles R3), nicht die Probe (siehe WAS SIE NICHT
   ZEIGT). Was ein Projekt daraus mitnimmt: Der Waechter bleibt byte-gleich
   mit der geprueften Vorlage; wer ihn aendert, aendert eine kritische
   Datei.
4c. Der Waechter nennt auf --konfig-pfad genau diese .py und die .json
   daneben unter seinem Namen und blockiert dabei (Exit 2). Die .json ist
   lesbar (ohne doppelte Schluessel, ohne unbekannte Schluessel), "prefix"
   hat die Waechter-Form mcp__<schluessel>__ (ein Segment: kein "__" darin,
   kein "_" am Rand; einzelne "_" und "-" sind erlaubt), "allowlist" ist
   eine Liste von Namen mit diesem prefix, "geblockt" (freiwillig) ein
   Objekt Name -> Grund ohne Ueberschneidung mit der allowlist, --unbekannt
   beginnt mit dem prefix, --lesend steht in der allowlist, und jeder
   Allowlist-Name steht in der Werkzeugliste. Die .json-Punkte (Schluessel,
   prefix-Form, allowlist, geblockt, Ueberschneidung) prueft der Waechter
   selbst und blockiert bei jedem Verstoss alles — die Probe nennt hier nur
   den Grund genauer als "lesender Name gibt Exit 2". --unbekannt, --lesend
   und die Werkzeugliste kennt nur die Probe.
5. Der Matcher TRIFFT jeden Namen der Werkzeugliste (--werkzeuge, Pflicht:
   Katalog des Servers, eine Zeile je Name oder JSON-Liste, im Repo gepflegt
   wie die Allowlist) und dazu drei Probe-Namen (den festen unbekannten und
   zwei je Lauf gebildete). Die Probe-Namen sind eine Stichprobe; die Liste
   ist der Beweis — und die Probe kann nicht pruefen, ob die Liste
   VOLLSTAENDIG ist (fehlt ein Schreibwerkzeug in der Liste und ist der
   Matcher genau darauf verengt, bleibt sie gruen; Gegenpruefer). Deshalb:
   Liste aus dem Katalog erzeugen, nicht von Hand, und bei jedem neuen
   Werkzeug nachfuehren — mindestens jeder Allowlist-Name muss drinstehen.
6. Der Befehl, mit einer Eingabe wie der des Clients aufgerufen (session_id,
   hook_event_name, cwd und ein NICHT-LEERES tool_input mit Feldern, wie sie
   ein echter Aufruf traegt), gibt fuer jeden Probe-Namen Exit 2, fuer
   --lesend Exit 0, fuer jeden Listen-Namen ausserhalb der allowlist 2 und
   innerhalb 0. Nicht-leer, weil ein Waechter, der auf leeres tool_input
   verzweigt, fuer eine Probe mit leerem tool_input unsichtbar war
   (Gegenpruefer, Nacharbeit 4). Das schliesst EINE Form; die Klasse bleibt
   eine Grenze (unten).

ANNAHME HINTER SCHRITT 5 (ausdruecklich, weil nicht belegbar)
--------------------------------------------------------------
Nach welcher Regel der Client einen "matcher" mit einem Werkzeugnamen
vergleicht, steht in keiner Quelle, die diese Probe nachlesen koennte. Der
Matcher gilt hier als treffend, wenn EINE von drei Lesarten zutrifft:
Regex-Suche im Namen; der Name beginnt mit dem Matcher; leerer, fehlender
oder "*"-Matcher trifft alles.

WAS SIE NICHT ZEIGT
-------------------
Ob der Client diese Einstellungsdatei liest und den Waechter wirklich ruft,
und ob der PREFIX der echte Registrierungsschluessel ist — das zeigt nur die
ECHTPROBE (prod-readonly-hook.py, Schritt 5). Ob die Werkzeugliste
vollstaendig ist (oben). Bei Erfolg schreibt die Probe eine Zeile auf stdout
(Befehlsform, Zahl der echten Aufrufe, Grenzen) — ohne sie ist im Gate-Protokoll
"lief gruen" nicht von "lief nicht" zu unterscheiden. Ebenfalls NICHT geprueft:
ob ein ZWEITER PreToolUse-Eintrag denselben Matcher traegt; die Probe nimmt den
ersten passenden Befehl und meldet nicht, wie viele es gibt. Traegt ein zweiter
Eintrag eine "allow"-Entscheidung, kann er den Waechter aushebeln, ohne dass
diese Probe es sieht (gemeldet aus einem Kind-Repo; ob der Client "allow" ueber
Exit 2 stellt, ist nicht gemessen). Ob die ALLOWLIST nur Lese-Werkzeuge enthaelt: Die
Probe misst gegen die Allowlist, die der Waechter liest — steht ein
Schreibwerkzeug darin, erwartet sie Exit 0 und bekommt ihn (Blindpruefer);
das prueft nur ein Mensch beim Pflegen der Allowlist und die Echtprobe mit
einem echten Schreib-Namen.

DIE PROBE PRUEFT INSTALLATION UND UMGEBUNG — von der Quelle nur, was der
Syntaxbaum sieht (4b), nie ihre Absicht. Eine
Waechter-Quelle, die geschrieben ist, um diese Probe zu erkennen, erkennt
sie — sie kann diesen Code lesen und findet immer ein Merkmal, das nur die
Probe traegt (die Feldmenge von tool_input, die Form der session_id, ein
Feld, das nur der Client schickt; Gegenpruefer und Blindpruefer haben je
eine andere Fassung gebaut: Quelle und Kopie byte-gleich, cmp gruen, Probe
gruen, Selbstprobe gruen, jeder Schreibaufruf durch). Zufaellige Felder
wuerden das naechste Merkmal nur verschieben. Gegen eine solche Quelle hilft
nur, was die Quelle selbst prueft: der Diff im Repo (Panel, Review — jede
Zeile der .py ist dort sichtbar) und die ECHTPROBE, die deshalb auch nach
jeder Aenderung an der .py Pflicht ist (prod-readonly-hook.py, Schritt 5).
Ebenso die Umgebung des Interpreters jenseits von site: -S schaltet
sitecustomize und .pth aus site-packages ab, nicht die Konfigurationsdateien
NEBEN dem Interpreter (python._pth, pyvenv.cfg) und nicht seine
Standardbibliothek — wer dort schreiben darf, steht innerhalb der Grenze
"Interpreter" (Gegenpruefer, Nacharbeit 5: eine python._pth stellte ein
fremdes json vor die Standardbibliothek; die Selbstprobe wurde rot, weil
._pth no_site erzwingt und ihr Fall "Probe ohne -S" kippt — ein Fang, kein
Beweis). Ueber welche Shell der Client den Befehl startet (sh, cmd.exe,
PowerShell — oder gar keine): nicht belegt. Die Metazeichen aller drei
sind verboten; gemessen wird hier aber nur ueber "sh -c" (Abfrage und
Aufrufe). Startet ein Client ohne Shell, sind Anfuehrungszeichen Teil des
Pfads — dann laeuft ein zitierter Pfad mit Leerzeichen nicht; deshalb
Pfade ohne Leerzeichen bevorzugen. Was bleibt, zeigt die Echtprobe. Ein
Client kann Einstellungen aus mehreren Dateien
zusammenfuehren; geprueft wird die genannte. Die Liste der Abschalt-Namen
deckt die gaengigen. Die eigene Richtigkeit dieser Probe prueft
waechter-gate-probe-selbsttest.py (Umgebungsvariable WAECHTER_GATE_PROBE_SEED
saet den Zufall der Probe-Namen — nur fuer die Selbstprobe).

Exit 0 = alles gilt; 1 = rot (Grund auf stderr); 2 = Aufbau (Argumente, sh).
"""

import json
import os
import random
import re
import shlex
import subprocess
import sys
import types

AUS_SCHALTER = frozenset({"disablehooks", "disableallhooks", "hooksdisabled", "nohooks"})
AN_SCHALTER = frozenset({"enablehooks", "hooksenabled"})
EREIGNIS = "PreToolUse"
ROT = 1
AUFBAU = 2
# sh, cmd.exe und PowerShell zusammen; dazu ' # @ , (cmd.exe kennt ' nicht
# als Anfuehrungszeichen, PowerShell liest # @ , besonders). Zitiert wird
# nur mit ".
METAZEICHEN = set("$`~*?[]{};&|<>()!%^'#@,\n\\")
# Was der Waechter importieren darf — als "import x", ohne Alias, ohne from.
ERLAUBTE_MODULE = frozenset({"json", "os", "sys"})
# Und was er an diesen Modulen benutzen darf — genau das, was die Vorlage
# braucht (gemessen am Syntaxbaum der Vorlage). Alles andere an sys/os/json
# ist rot: sys.path, sys.modules, sys.remote_exec, sys.monitoring, os.sys,
# os.remove, os.environ … — ohne dass jemand eine Liste nachfuehren muss,
# wenn der Interpreter neue Wege bekommt (Gegenpruefer, vierte Runde:
# os.sys.path und das in Python 3.14 neue sys.remote_exec).
ERLAUBTE_MODUL_ATTRIBUTE = types.MappingProxyType({
    "sys": frozenset({"argv", "exit", "stderr", "stdin", "stdout"}),
    "os": frozenset({"path"}),
    "os.path": frozenset({"abspath", "basename", "dirname", "join", "splitext"}),
    "json": frozenset({"dumps", "load"}),
})
# Attribute, die an keinem Empfaenger vorkommen duerfen (os.system ebenso wie
# o.system oder sys.modules['os'].system); dazu jedes Attribut mit "_" am
# Anfang (ausser __name__) und sys.path (siehe quelle_pruefen).
VERBOTENE_ATTRIBUTE = frozenset({"system", "popen", "fork", "forkpty", "startfile", "posix_spawn",
                                 "posix_spawnp", "modules", "kill", "killpg", "putenv", "environ",
                                 "eval", "exec", "compile", "load_module", "import_module",
                                 "exc_info", "settrace", "setprofile", "audit", "addaudithook",
                                 "mro", "call_tracing", "meta_path", "path_hooks", "excepthook",
                                 "displayhook", "breakpointhook", "unraisablehook",
                                 # ein Waechter aendert nichts am Dateisystem
                                 "remove", "unlink", "rename", "replace", "rmdir", "removedirs",
                                 "mkdir", "makedirs", "symlink", "link", "chmod", "chown", "chdir",
                                 "truncate", "utime", "add_dll_directory", "open", "fdopen", "pwrite",
                                 "renames", "ftruncate", "dup", "dup2", "sendfile", "copy_file_range",
                                 "writev", "pwritev", "posix_fallocate", "splice",
                                 "path_importer_cache", "getenv", "unsetenv", "fchmod", "fchown",
                                 "lchown", "lchmod", "mknod", "mkfifo"})
# .write/.writelines nur an sys.stdout/sys.stderr (Meldungen des Waechters)
SCHREIBATTRIBUTE = frozenset({"write", "writelines"})
# Attribut-Anfaenge: exec*/spawn* (Prozesse) und die Reflexionswege zu
# Rahmen, Code und Generatoren (f_builtins, tb_frame, gi_frame, co_code …)
# sowie jedes Attribut mit "_" am Anfang (Interna, z. B. _getframe).
VERBOTENE_ATTRIBUT_ANFAENGE = ("exec", "spawn", "f_", "tb_", "gi_", "cr_", "ag_", "co_", "_")
# Namen, die nirgends vorkommen duerfen — auch nicht als Wert (f = eval).
VERBOTENE_NAMEN = frozenset({"eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr",
                             "globals", "locals", "vars", "builtins", "__builtins__", "breakpoint",
                             "__loader__", "__spec__", "memoryview"})
# Zeichenketten, die als Modul- oder Funktionsname dienen koennten.
VERBOTENE_ZEICHENKETTEN = frozenset({"subprocess", "socket", "ctypes", "importlib", "os", "sys",
                                     "builtins", "runpy", "multiprocessing", "system", "popen",
                                     "fork", "posix_spawn", "startfile", "modules", "environ",
                                     "exc_info", "settrace", "_getframe", "f_builtins", "f_globals"})
VERBEN = ("anlegen", "erstellen", "loeschen", "aktualisieren", "setzen", "erfassen",
          "stornieren", "umbuchen", "zuweisen", "speichern", "eintragen", "aendern",
          "entfernen", "verschieben", "freigeben", "abschliessen", "importieren",
          "schreiben", "senden", "buchen", "exportieren")

if os.environ.get("WAECHTER_GATE_PROBE_SEED"):
    random.seed(os.environ["WAECHTER_GATE_PROBE_SEED"])


class KeineShell(Exception):
    pass


def rot(*zeilen) -> int:
    for zeile in zeilen:
        sys.stderr.write("Waechter-Gate-Probe: " + zeile + "\n")
    return ROT


def normalisiert(name: str) -> str:
    return "".join(z for z in name.lower() if z.isalnum())


def argumente(argv: list) -> dict:
    erwartet = ("--einstellungen", "--matcher", "--befehl", "--unbekannt", "--lesend",
                "--quelle", "--werkzeuge", "--konfig")
    # Nur --matcher (leer = Eintrag ohne matcher) und --konfig sind freiwillig.
    # --quelle und --werkzeuge sind PFLICHT: ohne Quelle kann die .py selbst
    # verzweigen, ohne Liste ist der Matcher-Beweis eine Stichprobe (beides
    # gemessen). Ein leerer Wert schaltete beide Pruefungen frueher still ab.
    freiwillig = ("--matcher", "--konfig")
    werte = {}
    rest = list(argv)
    while rest:
        schluessel = rest.pop(0)
        if schluessel not in erwartet:
            raise ValueError("unbekanntes Argument " + repr(schluessel))
        if schluessel in werte:
            raise ValueError(schluessel + " doppelt")
        if not rest:
            raise ValueError(schluessel + " ohne Wert")
        werte[schluessel] = rest.pop(0)
    fehlend = [s for s in erwartet if s not in werte and s not in freiwillig]
    if fehlend:
        raise ValueError("fehlende Argumente: " + " ".join(fehlend))
    for schluessel, wert in werte.items():
        if wert == "" and schluessel not in freiwillig:
            raise ValueError(schluessel + " ist leer")
    for schluessel in freiwillig:
        werte.setdefault(schluessel, "")
    return werte


def schalter_pruefen(objekt, pfad="") -> list:
    funde = []
    if isinstance(objekt, dict):
        for schluessel, wert in objekt.items():
            hier = pfad + "." + str(schluessel) if pfad else str(schluessel)
            kurz = normalisiert(str(schluessel))
            if kurz in AUS_SCHALTER and wert:
                funde.append(hier + " = " + json.dumps(wert))
            if kurz in AN_SCHALTER and not wert:
                funde.append(hier + " = " + json.dumps(wert))
            funde.extend(schalter_pruefen(wert, hier))
    elif isinstance(objekt, list):
        for nummer, wert in enumerate(objekt):
            funde.extend(schalter_pruefen(wert, pfad + "[" + str(nummer) + "]"))
    return funde


def wo_steht(objekt, gesucht: str, pfad="") -> list:
    funde = []
    if isinstance(objekt, dict):
        for schluessel, wert in objekt.items():
            funde.extend(wo_steht(wert, gesucht, (pfad + "." if pfad else "") + str(schluessel)))
    elif isinstance(objekt, list):
        for nummer, wert in enumerate(objekt):
            funde.extend(wo_steht(wert, gesucht, pfad + "[" + str(nummer) + "]"))
    elif isinstance(objekt, str) and gesucht in objekt:
        funde.append(pfad or "<Wurzel>")
    return funde


def matcher_von(eintrag: dict):
    wert = eintrag.get("matcher")
    return "" if wert is None else wert


def trifft(matcher: str, werkzeug: str) -> bool:
    if matcher in ("", "*"):
        return True
    try:
        if re.search(matcher, werkzeug) is not None:
            return True
    except re.error:
        pass
    return werkzeug.startswith(matcher)


def benannt(matcher: str) -> str:
    return repr(matcher) if matcher else "'' (kein oder leerer matcher)"


def eintrag_finden(einstellungen: dict, matcher: str, befehl: str):
    haken = einstellungen.get("hooks")
    if not isinstance(haken, dict):
        return False, "kein Objekt 'hooks' in den Einstellungen"
    liste = haken.get(EREIGNIS)
    if not isinstance(liste, list) or not liste:
        vorhanden = sorted(str(s) for s in haken)
        return False, ("kein Eintrag unter hooks." + EREIGNIS + " (gefunden: "
                       + (", ".join(vorhanden) if vorhanden else "nichts") + ")")
    gesehene_matcher, passend = [], []
    for eintrag in liste:
        if not isinstance(eintrag, dict):
            continue
        gesehene_matcher.append(repr(eintrag.get("matcher")))
        if matcher_von(eintrag) == matcher:
            passend.append(eintrag)
    if not passend:
        return False, ("kein " + EREIGNIS + "-Eintrag mit dem Matcher " + benannt(matcher)
                       + " (eingetragen: " + (", ".join(gesehene_matcher) or "nichts") + ")")
    gesehene_befehle = []
    for eintrag in passend:
        for h in eintrag.get("hooks") or []:
            if not isinstance(h, dict):
                continue
            gesehene_befehle.append(repr(h.get("type")) + " -> " + repr(h.get("command")))
            if h.get("type") == "command" and h.get("command") == befehl:
                return True, ""
    return False, ("der erwartete Befehl steht NICHT als command dieses Matchers; "
                   "eingetragen ist: " + (", ".join(gesehene_befehle) or "nichts"))


def gleich(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def befehlsform(befehl: str) -> tuple:
    # Liefert (interpreter, py, fehler).
    boese = sorted(set(befehl) & METAZEICHEN)
    if boese:
        return "", "", ("der Hook-Befehl enthaelt Shell-Metazeichen " + repr("".join(boese))
                        + " — er muss genau die Form <interpreter> -I -S <waechter.py> haben, sonst "
                        "ist, was die Probe liest, nicht das, was die Shell ausfuehrt (sh, cmd.exe "
                        "oder PowerShell). Pfade absolut, mit '/', zitiert nur mit \", ohne "
                        "$ ~ % ^ ' # @ , Backslash.")
    try:
        woerter = shlex.split(befehl, posix=True)
    except ValueError as fehler:
        return "", "", "Befehl nicht zerlegbar (" + str(fehler) + ")"
    if len(woerter) != 4 or woerter[1] != "-I" or woerter[2] != "-S":
        return "", "", ("der Hook-Befehl muss genau die Form <interpreter> -I -S <waechter.py> "
                        "haben — kein Wrapper, kein Zusatz, -S nicht weglassen (gefunden: "
                        + repr(woerter) + ")")
    interp, py = woerter[0], woerter[3]
    if not os.path.isabs(interp) or not os.path.isfile(interp):
        return "", "", "der Interpreter muss ein absoluter Pfad auf eine vorhandene Datei sein (gefunden: " + repr(interp) + ")"
    if not gleich(interp, sys.executable) or os.path.normcase(os.path.abspath(interp)) \
            != os.path.normcase(os.path.abspath(sys.executable)):
        return "", "", ("der Interpreter im Hook-Befehl (" + interp + ") ist nicht zeichengleich "
                        "derselbe, mit dem diese Probe laeuft (" + sys.executable + ") — die "
                        "Gate-Zeile nutzt denselben absoluten Interpreter wie der Hook-Befehl; ein "
                        "anderer Pfad koennte ein Wrapper oder ein Hardlink mit eigenem "
                        "site-packages sein.")
    if not os.path.isabs(py) or not py.endswith(".py"):
        return "", "", "der Waechter muss ein absoluter Pfad auf eine .py sein (gefunden: " + repr(py) + ")"
    if not os.path.isfile(py):
        return "", "", "die .py des Befehls gibt es nicht: " + py
    return interp, py, ""


def quelle_pruefen(py: str) -> str:
    # Der Waechter darf genau json, os, sys importieren — als "import x", ohne
    # Alias, ohne "from". Attribute und Namen, die Prozesse starten, Module
    # nachladen oder an Interna kommen, sind ueberall verboten, egal an
    # welchem Empfaenger sie haengen. Liefert "" oder den Grund.
    import ast
    try:
        with open(py, "rb") as datei:
            baum = ast.parse(datei.read(), filename=py)
    except (OSError, SyntaxError, ValueError) as fehler:
        return "die .py ist nicht als Python lesbar (" + type(fehler).__name__ + "): " + py
    funde = []
    aufruf_funktionen = {id(k.func) for k in ast.walk(baum) if isinstance(k, ast.Call)}
    attribut_basen = {id(k.value) for k in ast.walk(baum) if isinstance(k, ast.Attribute)}
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            for a in knoten.names:
                if a.name not in ERLAUBTE_MODULE or a.asname:
                    funde.append("import " + a.name + (" as " + a.asname if a.asname else ""))
        elif isinstance(knoten, ast.ImportFrom):
            funde.append("from " + str(knoten.module) + " import …")
        elif isinstance(knoten, ast.Attribute):
            # Kette bis zur Wurzel: an sys/os/json nur die erlaubten Attribute
            kette, wurzel = [knoten.attr], knoten.value
            while isinstance(wurzel, ast.Attribute):
                kette.append(wurzel.attr); wurzel = wurzel.value
            kette.reverse()
            if isinstance(wurzel, ast.Name) and wurzel.id in ERLAUBTE_MODUL_ATTRIBUTE:
                if not isinstance(knoten.ctx, ast.Load):
                    # kein Umbiegen erlaubter Modulattribute (sys.stdout = …, del os.path)
                    funde.append(wurzel.id + "." + ".".join(kette) + " zugewiesen")
                if kette[0] not in ERLAUBTE_MODUL_ATTRIBUTE[wurzel.id]:
                    funde.append(wurzel.id + "." + kette[0])
                elif wurzel.id == "os" and len(kette) > 1 and kette[1] not in ERLAUBTE_MODUL_ATTRIBUTE["os.path"]:
                    funde.append("os.path." + kette[1])
                elif wurzel.id == "os" and len(kette) == 1 and id(knoten) not in attribut_basen:
                    # os.path ist selbst ein Modul (es traegt sys): nur als Basis, nie als Wert
                    funde.append("os.path als Wert")
            if knoten.attr in SCHREIBATTRIBUTE:
                # Empfaengerkette muss bei sys.stdout oder sys.stderr beginnen
                kette, wurzel = [], knoten.value
                while isinstance(wurzel, ast.Attribute):
                    kette.append(wurzel.attr); wurzel = wurzel.value
                if not (isinstance(wurzel, ast.Name) and wurzel.id == "sys" and kette
                        and kette[-1] in ("stdout", "stderr")):
                    funde.append("." + knoten.attr + " (nicht an sys.stdout/sys.stderr)")
            if knoten.attr != "__name__" and (knoten.attr in VERBOTENE_ATTRIBUTE \
                    or knoten.attr.startswith(VERBOTENE_ATTRIBUT_ANFAENGE)):
                funde.append("." + knoten.attr)
        elif isinstance(knoten, ast.Name):
            if knoten.id in VERBOTENE_NAMEN:
                funde.append(knoten.id)
            elif knoten.id == "open" and id(knoten) not in aufruf_funktionen:
                funde.append("open als Wert")
            elif knoten.id in ERLAUBTE_MODULE and id(knoten) not in attribut_basen:
                # sys/os/json nur als Attribut-Basis — nie als Wert (s = sys)
                funde.append(knoten.id + " als Wert")
        elif isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Name) and knoten.func.id == "open":
            # open() nur lesend, mit wörtlichem Modus, ohne *args/**kwargs
            if any(isinstance(a, ast.Starred) for a in knoten.args) or any(kw.arg is None for kw in knoten.keywords):
                funde.append("open(*…)")
            modus = knoten.args[1] if len(knoten.args) > 1 else None
            for kw in knoten.keywords:
                if kw.arg == "mode":
                    modus = kw.value
            if modus is not None and (not isinstance(modus, ast.Constant) or not isinstance(modus.value, str)
                                      or set(modus.value) & set("wax+")):
                funde.append("open(…, schreibend)")
        elif isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
            if knoten.value in VERBOTENE_NAMEN or knoten.value in VERBOTENE_ZEICHENKETTEN:
                funde.append(repr(knoten.value))
    if funde:
        return ("die .py will mehr als ein Waechter braucht (nur json, os, sys, ohne Alias und "
                "ohne from; keine Prozesse, kein Nachladen, keine Interna): "
                + ", ".join(sorted(set(funde))[:8]) + " — " + py)
    return ""


def konfig_erfragen(befehl: str, py: str) -> tuple:
    try:
        ergebnis = subprocess.run(["sh", "-c", befehl + " --konfig-pfad"], input=b"",
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        raise KeineShell()
    antwort = None
    for z in ergebnis.stdout.decode("utf-8", "replace").strip().splitlines():
        try:
            kandidat = json.loads(z)
        except ValueError:
            continue
        if isinstance(kandidat, dict) and isinstance(kandidat.get("py"), str) \
                and isinstance(kandidat.get("konfig"), str):
            antwort = kandidat
    if ergebnis.returncode != 2 or antwort is None:
        return "", ("der Waechter beantwortet die Konfig-Abfrage (--konfig-pfad) nicht mit "
                    "Exit 2 und Antwort (Exit " + str(ergebnis.returncode) + ") — ein Waechter "
                    "vor v1.15.4, oder nicht die Vorlage")
    if not gleich(antwort["py"], py):
        return "", "der Waechter nennt eine andere .py (" + antwort["py"] + ") als der Befehl (" + py + ")"
    erwartet = os.path.join(os.path.dirname(os.path.abspath(py)),
                            os.path.splitext(os.path.basename(py))[0] + ".json")
    if not gleich(antwort["konfig"], erwartet):
        return "", ("der Waechter nennt eine .json (" + antwort["konfig"] + "), die nicht neben "
                    "seiner .py unter seinem Namen liegt (" + erwartet + ")")
    return antwort["konfig"], ""


def ohne_doppelte_schluessel(paare: list) -> dict:
    ergebnis = {}
    for schluessel, wert in paare:
        if schluessel in ergebnis:
            raise ValueError("Schluessel '" + schluessel + "' doppelt")
        ergebnis[schluessel] = wert
    return ergebnis


def konfig_pruefen(pfad: str, unbekannt: str, lesend: str) -> tuple:
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            konfig = json.load(datei, object_pairs_hook=ohne_doppelte_schluessel)
    except FileNotFoundError:
        return "", [], "neben der .py liegt keine " + os.path.basename(pfad) + " (" + pfad + ")"
    except Exception as fehler:
        return "", [], ("Konfiguration nicht lesbar (" + type(fehler).__name__ + ": " + str(fehler)
                        + "): " + pfad)
    if not isinstance(konfig, dict) or not isinstance(konfig.get("prefix"), str):
        return "", [], "Konfiguration ohne prefix: " + pfad
    praefix = konfig["prefix"]
    schluessel = praefix[5:-2] if praefix.startswith("mcp__") and praefix.endswith("__") else ""
    if (not re.fullmatch(r"mcp__[A-Za-z0-9_-]+__", praefix) or "__" in schluessel
            or schluessel.startswith("_") or schluessel.endswith("_")):
        return "", [], ("prefix " + repr(praefix) + " hat nicht die Form mcp__<schluessel>__ "
                        "(ein Segment: kein '__' darin, kein '_' am Rand): " + pfad)
    fremd = sorted(set(konfig) - {"prefix", "allowlist", "geblockt"})
    if fremd:
        return praefix, [], ("Konfiguration mit unbekannten Schluesseln " + repr(fremd)
                             + " — der Waechter blockiert damit alles: " + pfad)
    allowlist = konfig.get("allowlist")
    if not isinstance(allowlist, list) or not all(isinstance(e, str) for e in allowlist):
        return praefix, [], "Konfiguration ohne gueltige allowlist (Liste von Namen): " + pfad
    geblockt = konfig.get("geblockt", {})
    if not isinstance(geblockt, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                 for k, v in geblockt.items()):
        return praefix, allowlist, ("geblockt ist kein Objekt Name -> Grund (Strings) — der Waechter "
                                    "blockiert damit alles: " + pfad)
    beides = sorted(set(geblockt) & set(allowlist))
    if beides:
        return praefix, allowlist, ("in allowlist UND geblockt: " + ", ".join(beides[:5])
                                    + " — der Waechter blockiert damit alles: " + pfad)
    ohne = [e for e in allowlist if not e.startswith(praefix)]
    if ohne:
        return praefix, allowlist, "allowlist-Eintraege ohne den prefix: " + ", ".join(ohne[:5])
    if not unbekannt.startswith(praefix):
        return praefix, allowlist, ("prefix " + repr(praefix) + " trifft den Probe-Namen "
                                    + repr(unbekannt) + " nicht — Konfiguration eines anderen "
                                    "Namensraums")
    if lesend not in allowlist:
        return praefix, allowlist, ("--lesend " + repr(lesend) + " steht nicht in der allowlist "
                                    "der Konfiguration, die der Waechter liest")
    return praefix, allowlist, ""


def weitere_namen(praefix: str, allowlist: list) -> list:
    # Stichprobe neben der Werkzeugliste: nur Buchstaben, Segmente 4-12, eines
    # ab 8, und ein Name aus Allowlist-Stamm plus Schreibverb. Namen, die
    # selbst in der allowlist stehen, werden neu gezogen.
    buchstaben = "abcdefghijklmnopqrstuvwxyz"

    def segment(lo, hi):
        return "".join(random.choice(buchstaben) for _ in range(random.randint(lo, hi)))

    staemme = []
    for eintrag in allowlist:
        rest = eintrag[len(praefix):] if eintrag.startswith(praefix) else eintrag
        teile = [t for t in rest.split("_") if t]
        if teile:
            staemme.append("_".join(teile[:-1]) if len(teile) >= 2 else teile[0])
    for _ in range(50):
        teile = [segment(4, 12) for _ in range(random.randint(1, 3))]
        teile.insert(random.randint(0, len(teile)), segment(8, 12))
        formfrei = praefix + "_".join(teile)
        stamm = random.choice(staemme) if staemme else segment(4, 9)
        mit_verb = praefix + stamm + "_" + random.choice(VERBEN)
        if formfrei not in allowlist and mit_verb not in allowlist and formfrei != mit_verb:
            return [formfrei, mit_verb]
    return [praefix + segment(8, 12) + "_" + segment(8, 12), praefix + segment(8, 12) + "_anlegen"]


def werkzeuge_lesen(pfad: str) -> tuple:
    try:
        with open(pfad, "r", encoding="utf-8-sig") as datei:
            text = datei.read()
    except Exception as fehler:
        return [], "Werkzeugliste nicht lesbar (" + type(fehler).__name__ + "): " + pfad
    text = text.strip()
    if text.startswith("["):
        try:
            daten = json.loads(text)
        except ValueError:
            return [], "Werkzeugliste ist kein gueltiges JSON: " + pfad
        if not isinstance(daten, list) or not all(isinstance(n, str) for n in daten):
            return [], "Werkzeugliste (JSON) enthaelt Eintraege, die keine Namen sind: " + pfad
        namen = daten
    else:
        namen = [z.strip() for z in text.splitlines() if z.strip() and not z.strip().startswith("#")]
    namen = list(dict.fromkeys(namen))
    if not namen:
        return [], "Werkzeugliste ist leer: " + pfad
    return namen, ""


def aufrufen(befehl: str, werkzeug: str) -> int:
    eingabe = json.dumps({
        "session_id": "%032x" % random.getrandbits(128),
        "hook_event_name": EREIGNIS,
        "cwd": os.getcwd(),
        "tool_name": werkzeug,
        # nicht leer — ein Waechter, der auf tool_input verzweigt, muss es hier sehen
        "tool_input": {"id": random.randint(1, 99999), "text": "gate-probe %x" % random.getrandbits(32),
                       "filter": {"aktiv": True, "seite": random.randint(1, 9)}},
    }).encode("utf-8")
    try:
        ergebnis = subprocess.run(["sh", "-c", befehl], input=eingabe,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        raise KeineShell()
    return ergebnis.returncode


def main(argv: list) -> int:
    # Ohne das scheitert die Ausgabe auf einer Konsole mit Codepage 850/437 an
    # einem Gedankenstrich, und der Traceback beendet die Probe mit Exit 1 —
    # eine gruene Probe risse so die Gate-Zeile (`... || exit 1`) mit.
    # PYTHONIOENCODING hilft nicht: -I ignoriert es (gemessen). Dieselbe Zeile
    # steht in panel-stimme3.py und ast-gleich.py.
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if not (sys.flags.isolated and sys.flags.no_site):
        sys.stderr.write("Aufbau: diese Probe muss mit demselben Interpreter und denselben Schaltern "
                         "laufen wie der Hook-Befehl: <interpreter> -I -S waechter-gate-probe.py …\n")
        return AUFBAU
    try:
        werte = argumente(argv)
    except ValueError as fehler:
        sys.stderr.write(
            "Aufruf: ⟨/absoluter/pfad/zu/python3⟩ -I -S waechter-gate-probe.py "
            "--einstellungen <datei> [--matcher <matcher>] --befehl <command> "
            "--unbekannt <name> --lesend <name> --quelle <repo-.py> --werkzeuge <datei> "
            "[--konfig <pfad>]\n" + str(fehler) + "\n")
        return AUFBAU

    pfad = werte["--einstellungen"]
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            einstellungen = json.load(datei)
    except FileNotFoundError:
        return rot("Einstellungsdatei fehlt: " + pfad)
    except Exception as fehler:
        return rot("Einstellungsdatei nicht lesbar (" + type(fehler).__name__ + "): " + pfad)
    if not isinstance(einstellungen, dict):
        return rot("Einstellungsdatei: oberste Ebene ist kein Objekt: " + pfad)

    aus = schalter_pruefen(einstellungen)
    if aus:
        return rot("Hooks sind abgeschaltet: " + "; ".join(aus))

    gefunden, grund = eintrag_finden(einstellungen, werte["--matcher"], werte["--befehl"])
    if not gefunden:
        meldungen = [grund]
        andere = wo_steht(einstellungen, werte["--befehl"])
        if andere:
            meldungen.append("der Befehl steht (als Teilstring) in: " + ", ".join(andere)
                             + " — dort ruft der Client ihn nicht.")
        return rot(*meldungen)

    interp, py, fehler = befehlsform(werte["--befehl"])
    if fehler:
        return rot(fehler)
    if gleich(py, werte["--quelle"]):
        return rot("--quelle ist die installierte .py selbst (" + py + ") — der Vergleich waere "
                   "leer. --quelle ist die Quelle im Repo.")
    try:
        with open(py, "rb") as a, open(werte["--quelle"], "rb") as b:
            if a.read() != b.read():
                return rot("die installierte .py (" + py + ") ist nicht byte-gleich mit der "
                           "Quelle " + werte["--quelle"] + " — Drift oder Fremdfassung.")
    except OSError as fehler:
        return rot("Quelle oder .py nicht lesbar (" + type(fehler).__name__ + "): " + werte["--quelle"]
                   + " / " + py)
    fehler = quelle_pruefen(py)
    if fehler:
        return rot(fehler)

    liste, fehler = werkzeuge_lesen(werte["--werkzeuge"])
    if fehler:
        return rot(fehler)

    try:
        konfig, fehler = konfig_erfragen(werte["--befehl"], py)
    except KeineShell:
        sys.stderr.write("Aufbau: 'sh' nicht gefunden — diese Probe ruft den eingetragenen "
                         "Befehl mit 'sh -c' auf, wie das lokale Gate.\n")
        return AUFBAU
    if fehler:
        return rot(fehler)
    if werte["--konfig"] and not gleich(werte["--konfig"], konfig):
        return rot("--konfig " + repr(werte["--konfig"]) + " ist nicht die Datei, die der Waechter "
                   "liest (" + konfig + ").")

    praefix, allowlist, fehler = konfig_pruefen(konfig, werte["--unbekannt"], werte["--lesend"])
    if fehler:
        return rot(fehler, "Ein Waechter mit fremder, fehlender oder kaputter Konfiguration "
                   "bewacht diesen Namensraum nicht.")
    fremde = [n for n in liste if not n.startswith(praefix)]
    if fremde:
        return rot("die Werkzeugliste enthaelt Namen ausserhalb des prefix " + repr(praefix)
                   + ": " + ", ".join(fremde[:5]))
    fehlend = [n for n in allowlist if n not in liste]
    if fehlend:
        return rot("die Werkzeugliste ist unvollstaendig — Allowlist-Namen fehlen darin: "
                   + ", ".join(fehlend[:5]) + " (Liste aus dem Katalog erzeugen, nicht von Hand).")

    namen = [werte["--unbekannt"]] + weitere_namen(praefix, allowlist)
    for name in namen + liste:
        if not trifft(werte["--matcher"], name):
            return rot("der Eintrag bewacht diesen Namensraum nicht vollstaendig: der Matcher "
                       + benannt(werte["--matcher"]) + " trifft " + repr(name)
                       + " weder als Regex-Suche noch als Praefix.",
                       "Der Client ruft den Waechter fuer dieses Werkzeug nicht.")

    try:
        for name in namen:
            rc = aufrufen(werte["--befehl"], name)
            if rc != 2:
                return rot("Probe-Name " + repr(name) + " gibt Exit " + str(rc) + " statt 2.",
                           "127 = Interpreter fehlt oder Pfad veraltet; 1 = installierte .py "
                           "beschaedigt; 0 = Waechter wirkungslos.")
        rc = aufrufen(werte["--befehl"], werte["--lesend"])
        if rc != 0:
            return rot("lesender Name " + repr(werte["--lesend"]) + " gibt Exit " + str(rc)
                       + " statt 0.", "Exit 2 hier heisst: Konfiguration kaputt, oder der "
                       "Waechter blockiert mehr als die allowlist erlaubt.")
        for name in liste:
            rc = aufrufen(werte["--befehl"], name)
            soll = 0 if name in allowlist else 2
            if rc != soll:
                return rot("Werkzeug " + repr(name) + " aus der Liste gibt Exit " + str(rc)
                           + " statt " + str(soll) + ".")
    except KeineShell:
        sys.stderr.write("Aufbau: 'sh' nicht gefunden.\n")
        return AUFBAU
    # Ohne Meldung ist im Gate-Protokoll "lief gruen" nicht von "lief nicht" zu
    # unterscheiden (gemeldet aus einem Kind-Repo). Die Zeile nennt, was wirklich
    # gelaufen ist, nicht nur dass etwas lief.
    print("Gate-Probe gruen: Befehlsform " + repr(werte["--befehl"]) + "; "
          + str(len(namen) + 2 + len(liste)) + " echte Aufrufe gegen den erwarteten "
          "Exit-Code (abgelehnte und erlaubte Namen, dazu die Konfig-Abfrage); "
          "Quelle und installierte Kopie sind byte-gleich. Nicht geprueft: der "
          "Client selbst, die Vollstaendigkeit der Werkzeugliste, und ein ZWEITER "
          "PreToolUse-Eintrag mit demselben Matcher — die Probe sieht nur ihren "
          "eigenen und meldet nicht, wenn es mehr gibt.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
