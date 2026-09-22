#!/usr/bin/env python3
r"""Waechter: verhindert schreibende Zugriffe des Agenten auf die Produktivinstanz.

(Dieser Text ist roh, siehe das r vor den Anfuehrungszeichen: Der Hinweis zu
Pfaden mit Leerzeichen unter Schritt 2 zeigt JSON-Maskierung woertlich, und
ohne das r wuerde Python die Maskierung schon beim Lesen der Datei aufloesen
und das Beispiel unbrauchbar machen.)

VORLAGE — Konfiguration anlegen und scharf schalten, siehe unten. Diese .py
aendert ein Projekt NIE; Projekt-Daten (PREFIX, ALLOWLIST) stehen in der
Konfigurationsdatei neben dieser Datei, benannt wie sie selbst
(prod-readonly-hook.py liest prod-readonly-hook.json, ein umbenannter
mein_waechter.py liest mein_waechter.json).

WARUM DAS HIER LIEGT
--------------------
"Der Agent arbeitet auf der Produktivinstanz nur lesend" ist als Satz in einer
Anweisungsdatei eine Bitte. Sie wird meistens befolgt — meistens reicht nicht.
Ein Vorfall (zwei echte Belege in der Produktion angelegt, waehrend eigentlich
nur gelesen werden sollte) hat genau diese Klasse getroffen: nicht Boeswilligkeit,
sondern ein Agent, der die Regel im langen Kontext aus den Augen verlor.

Ein Waechter macht daraus Struktur: Der Aufruf kommt gar nicht erst durch.

ALLOWLIST, NICHT DENYLIST — fail-closed
---------------------------------------
Erlaubt wird aufgezaehlt, alles andere ist verboten. Andersherum waere es
fail-open: Jedes kuenftig gebaute Schreib-Werkzeug muesste jemand nachtragen,
sonst schluepft es durch. Vergisst man dagegen ein LESE-Werkzeug, wird es
geblockt, faellt sofort auf und wird nachgetragen — der harmlose Fehler.

Muster zu raten ("alles was mit _lesen endet") ist verlockend und falsch:
Lese-Werkzeuge heissen selten einheitlich. Aufzaehlen.

Was "Lese-Werkzeug" heisst — veraendert keinen Fachbestand; technische Seeds
(Einstellungen beim ersten Abruf anlegen, Modul-Initialisierung) benannt und
aus dem Lesepfad in die Einrichtung verschoben —, steht in
docs/agents/setup-checkliste.md, Schritt 7, Punkt 1 (Konfiguration in der
Quelle). Dieser Waechter prueft Namen, nicht Verhalten.

KONFIGURATION ALS DATEN, NICHT ALS QUELLTEXT
--------------------------------------------
Vor v1.15.2 standen PREFIX und ALLOWLIST als Python-Quelltext in dieser Datei.
Ein Tippfehler beim Nachtragen (Eintrag ohne Anfuehrungszeichen, offenes
Stringende, falsche Klammer) scheiterte beim IMPORT — vor jedem try — mit
Exit 1, und Exit 1 laesst der Client DURCH (gemessen: NameError, SyntaxError,
unpassende Klammer, ALLOWLIST = dict(...) je rc=1, schreibend wie lesend).
Jetzt liest main() die JSON-Datei INNERHALB des abgefangenen Bereichs: Jeder
Fehler darin blockiert mit Exit 2 (Liste unter Schritt 3).

WO DER WAECHTER LIEGT — UND WO NICHT
------------------------------------
Diese Datei und die Konfiguration im Repo sind die QUELLE: versioniert,
review-faehig, fuer jeden Agenten auffindbar, testbar. AUSGEFUEHRT werden
Kopien AUSSERHALB des Repos (im Agenten-Verzeichnis des Rechners).

Das ist Absicht: Wuerde der Waechter aus dem Repo heraus ausgefuehrt, das er
schuetzt, koennte ein Agent seinen eigenen Waechter durch eine Repo-Aenderung
entschaerfen — ein selbstmodifizierender Schutz ist keiner.

Preis dieser Trennung ist Drift: Repo-Quelle und installierte Kopie koennen
auseinanderlaufen. Deshalb gehoert ein Abgleich BEIDER Dateien in die LOKALEN
Gates (die CI sieht das Agenten-Verzeichnis nicht), z.B.

    cmp docs/vorlagen/prod-readonly-hook.py   ~/.claude/hooks/prod-readonly-hook.py   || exit 1
    cmp docs/vorlagen/prod-readonly-hook.json ~/.claude/hooks/prod-readonly-hook.json || exit 1
   (bei einem projekteigenen Dateinamen entsprechend beide Dateien; siehe
   Schritt 1 — zwei Waechter im selben Verzeichnis brauchen zwei Namen)

— als eigene Zeilen, nicht in einer Pipe. Quelle und Kopie heissen gleich. Die
Konfiguration wird in der Repo-Quelle ausgefuellt (versionierte
Projekt-Konfiguration), kopiert wird erst danach. Wer die Kopie ausfuellt statt
der Quelle, hat einen Abgleich, der immer rot ist. cmp ist auch gruen, wenn
BEIDE Dateien gleich kaputt sind — deshalb daneben die Gate-Probe (Schritt 4).
Und ein Test im Repo prueft die Allowlist in der JSON-Datei gegen den
tatsaechlichen Werkzeug-Katalog, damit ein neu gebautes Lese-Werkzeug auffaellt,
statt still blockiert zu werden. Die Allowlist aendert der Mensch, nicht der
Agent, der gerade blockiert wurde.

ZUERST: SCHREIBTUEREN AUFZAEHLEN, NICHT PAUSCHAL BLOCKIEREN
-----------------------------------------------------------
Bevor irgendein Waechter gebaut wird, die Tueren auflisten, durch die in die
Produktivinstanz geschrieben werden kann — und je Tuer festhalten, ob das
gewollt ist und wer sie bewacht:

    Tuer                          gewollt?   bewacht durch
    Agent in der Kommandozeile    nein       dieser Hook
    Desktop-Anwendung             ja         nichts (bewusst)
    Web-Oberflaeche               ja         Anmeldung
    Skripte auf dem Server        nein       kein Agentenzugang

Ohne diese Liste entsteht ein Satz wie "Produktion ist schreibgeschuetzt", der
falsch ist: Ein Hook im Agenten-Client schuetzt den AUFRUFER, nicht die
RESSOURCE. Andere Clients erreichen dieselbe Tuer ungehindert — und kein Test
zeigt das.

Real belegt an zwei Projekten: Derselbe technische Sachverhalt (Desktop kann
gegen Produktion schreiben) war einmal ein LOCH und einmal ein gewolltes
FEATURE. Eine pauschale Regel tut immer einem von beiden unrecht.

Ist eine Tuer gewollt, aber ungeschuetzt, gehoert der Schutz oft nicht in den
Client, sondern in den SERVER: Das Schreib-Werkzeug verweigert die Arbeit,
solange keine ausdrueckliche Freigabe gesetzt ist. Das wirkt fuer jeden Client,
liegt versioniert im Repo und ist testbar.

ZWEI FALLEN, DIE EINEN GRUENEN WAECHTER WIRKUNGSLOS MACHEN
-----------------------------------------------------------
Real passiert: Ein Waechter wurde exakt nach dieser Vorlage gebaut — Allowlist,
fail-closed, vier Testfaelle gruen, Sabotage-Runden mit Rot-Beweis, Abgleich
gegen den Werkzeug-Katalog. Er war trotzdem VOLLSTAENDIG wirkungslos.

(1) DER PRAEFIX KOMMT VOM CLIENT, NICHT VOM SERVER.
    Der Name eines MCP-Werkzeugs lautet mcp__<registrierungsschluessel>__<tool>.
    Der Registrierungsschluessel steht in der CLIENT-Konfiguration und ist frei
    waehlbar — er hat mit dem Projekt- oder Servernamen nichts zu tun. Ein
    geratener PREFIX passt auf nichts, und der Waechter laesst alles durch.
    Pruefen, nicht raten: den Schluessel in der Client-Konfiguration nachlesen.

(2) DER WAECHTER MUSS IN DEM CLIENT LIEGEN, DER DIE AUFRUFE MACHT.
    Wird der MCP-Server in einem anderen Client registriert (Desktop-Anwendung
    statt Kommandozeile, oder umgekehrt), regiert ein Hook im einen den anderen
    NICHT. Der Schreibpfad bleibt offen, waehrend alle Tests gruen sind.
    Erst klaeren, WO die Aufrufe entstehen — dann dort schuetzen.

Beides ist dieselbe Klasse wie der Waechter, der sich auf ein fremdes Praedikat
verlaesst: Die Testfaelle konstruieren ihre eigenen Eingaben und beweisen damit
nichts ueber die Eingaben, die das System wirklich erzeugt.

SCHARF SCHALTEN
---------------
1. KONFIGURATION in der REPO-QUELLE anlegen und committen:
     cp docs/vorlagen/prod-readonly-hook.example.json docs/vorlagen/prod-readonly-hook.json
   Darin "prefix" (genau "mcp__<schluessel>__") und "allowlist" (JSON-Liste
   der Lese-Werkzeuge, jeder Name mit dem PREFIX; ebenso jeder Name unter
   "geblockt") ausfuellen — sonst nichts
   (unbekannte Schluessel blockieren). Die Beispieldatei selbst blockiert
   jeden Aufruf: Ihre Platzhalter haben keine gueltige Form.
   Erst dann BEIDE Dateien ins Agenten-Verzeichnis kopieren (NICHT aus dem
   Repo heraus ausfuehren) — mit projekteigenem Namen, wenn dort mehr als ein
   Waechter liegt (siehe unten); der Name muss dann an DREI Stellen gleich
   sein: .py, .json und der "command" in den Agenten-Einstellungen (Schritt
   2), den auch die Gate-Zeile (Schritt 4) unveraendert traegt:
     cp docs/vorlagen/prod-readonly-hook.py   ~/.claude/hooks/⟨projekt⟩_prod_readonly.py
     cp docs/vorlagen/prod-readonly-hook.json ~/.claude/hooks/⟨projekt⟩_prod_readonly.json
   (ein Projekt allein darf beim Vorlagennamen bleiben)
   Der Waechter liest die JSON-Datei aus SEINEM eigenen Verzeichnis, und zwar
   die mit SEINEM Namen: <name>.py liest <name>.json. Deshalb: Liegen im
   Agenten-Verzeichnis die Waechter MEHRERER Projekte (bei diesem Client ist
   ~/.claude/hooks/ je Rechner gemeinsam), bekommt jeder Waechter einen
   projekteigenen Dateinamen — die .py UND die .json, gleich benannt
   (z. B. firma_prod_readonly.py + firma_prod_readonly.json). Vor v1.15.4
   las jeder Waechter fest "prod-readonly-hook.json": Der zweite Waechter im
   Verzeichnis las die Konfiguration des ERSTEN, dessen PREFIX seine
   Werkzeuge nicht trifft — alles durchgelassen, und keine Probe des ersten
   Projekts wurde rot (gemeldet und gemessen von einem Projekt mit zwei
   Waechtern auf einem Rechner). Der Drift-Abgleich (cmp, siehe oben)
   vergleicht danach beide Dateien.
   Optional darf die JSON einen Schluessel "geblockt" tragen (Objekt: Name ->
   Grund) fuer Lese-Werkzeuge, die BEWUSST nicht in der Allowlist stehen; der
   Waechter liest ihn nur auf Form, entscheidet aber nie danach — ein Name in
   allowlist UND geblockt ist ein Konfigurationsfehler und blockiert. Auch
   geblockt-Namen tragen den PREFIX: ohne ihn kann der Name kein Werkzeug
   dieses Namensraums sein, die Widerspruchspruefung gegen die allowlist
   greift nie, und der Eintrag ist eine stille Notiz (gemessen in einem
   Kind-Repo: "kunde_lesen" neben "mcp__x__kunde_lesen" ergab Exit 0 ohne
   Meldung).
   GRENZE, die kein Code hier schliesst: Eine FREMDE, aber formgueltige
   Konfiguration (die eines anderen Projekts unter dem eigenen Namen) erkennt
   der Waechter nicht — ihr PREFIX trifft die eigenen Werkzeuge nicht, und
   "anderer Namensraum" heisst durchlassen. Fail-open. Dagegen wirken nur der
   Namensbezug (<name>.json), die Gate-Probe (sie prueft den prefix gegen den
   Probe-Namen) und die Echtprobe. Deshalb: Name ZUERST festlegen, dann
   kopieren — nie eine Datei mit Vorlagennamen in ein Verzeichnis kopieren,
   in dem schon ein Waechter liegt.
2. In den Agenten-Einstellungen eintragen — mit einem Pfad AUSSERHALB des
   Repos (hier das Benutzerverzeichnis, nicht ./.claude/) und mit ABSOLUTEM
   Interpreter-Pfad:

     {"hooks": {"PreToolUse": [{"matcher": "<PREFIX>.*",
        "hooks": [{"type": "command",
                   "command": "⟨/absoluter/pfad/zu/python3⟩ -I -S ⟨/absoluter/pfad/zu⟩/.claude/hooks/⟨projekt⟩_prod_readonly.py"}]}]}}

   BEIDE Pfade absolut, mit "/", zitiert nur mit ", ohne ~, ohne $VARIABLEN,
   ohne % ^ ' # @ , (Metazeichen von cmd.exe und PowerShell — welche Shell
   der Client unter Windows nimmt, ist nicht belegt; am einfachsten ein
   Pfad ohne Leerzeichen): Die Gate-Probe
   (Schritt 4) verlangt genau diese Form und laesst nichts anderes zu — ein
   ~ im Beispiel haette jedes Kind-Repo dauerhaft falsch-rot gemacht
   (Blindpruefer, Nacharbeit 3).

   Warum absolut: Findet die Shell den Interpreter nicht ("python: not found"),
   endet der Aufruf mit Exit 127 — und der Client laesst jeden Exit ausser 2
   DURCH. Die fail-closed-Logik unten startet dann nie. Ein falscher oder
   spaeter veralteter absoluter Pfad (Python-Update, Versionsnummer im Pfad)
   endet ebenso mit 127; das faengt die Gate-Probe (Schritt 4) bei jedem
   Gate-Lauf.
   Warum "-I": isoliert. Ohne das Flag liegt das Verzeichnis des Skripts vorn
   im Modulpfad, und PYTHONPATH gilt mit — eine Datei "json.py" daneben oder
   irgendwo im PYTHONPATH wird dann statt der Standardbibliothek geladen. Der
   Import steht VOR main() und damit vor jedem Abfang: Scheitert er, endet der
   Aufruf mit Exit 1, und jeden Exit ausser 2 laesst der Client DURCH
   (gemessen, v1.15.2: json.py daneben, die beim Import scheitert — ohne "-I"
   rc=1 fuer ein schreibendes Werkzeug, mit "-I" rc=2). Laedt die fremde
   json.py dagegen sauber, entscheidet sie ueber Konfiguration und Eingabe des
   Waechters mit. "-I" schaltet beides ab und ignoriert zusaetzlich PYTHONHOME
   und die Benutzer-Paketverzeichnisse — aber NICHT das site-packages des
   Interpreters selbst: sitecustomize.py und .pth-Dateien dort laufen unter
   -I weiter, und das Verzeichnis ist oft ohne Admin schreibbar. Eine
   sitecustomize.py, die json.load umbiegt, liess Drift-Abgleich, Gate-Probe
   und Selbstprobe gruen und jeden Schreibaufruf durch (Gegenpruefer,
   Nacharbeit 4, gemessen). Deshalb "-I -S": -S laesst site ganz aus. Dieser
   Waechter braucht nur die Standardbibliothek. Die Grenze ist der
   Interpreter selbst: seine Standardbibliothek und die Konfigurationsdateien
   NEBEN ihm (python._pth, pyvenv.cfg), die -S nicht abschaltet — wer dort
   schreiben darf, ist nicht mehr Gegenstand dieser Probe (Gegenpruefer,
   Nacharbeit 5, gemessen).
   Pfad mit LEERZEICHEN: Er braucht Anfuehrungszeichen IM Kommando, und in
   JSON wird jedes davon zu \", jeder Backslash zu \\ — also
   "command": "\"C:/Program Files/Python312/python.exe\" -I -S C:/Users/…/⟨projekt⟩_prod_readonly.py".
   Einfacher ist ein Pfad ohne Leerzeichen und mit "/" statt Backslash.
3. TESTEN — Eingabe als JSON auf stdin, Exit 2 = blockiert. Fuer den
   schreibenden und den lesenden Fall ECHTE Werkzeugnamen aus dem
   Werkzeug-Katalog des Clients nehmen, nicht erfundene:
     schreibendes Werkzeug  -> blockiert
     lesendes Werkzeug      -> durchgelassen
     unbekannter Name       -> blockiert (fail-closed!)
     fremdes Werkzeug       -> unberuehrt
   Dazu der Rot-Beweis: in einer KOPIE unbekannte Namen durchlassen -> der
   dritte Fall muss rot werden; die Allowlist nicht lesen -> der zweite Fall
   muss sich aendern. Und ein aehnlich heissender Nicht-Prod-Name (anderer
   Schluessel mit gleichem Anfang) bleibt unberuehrt.
   Konfigurationsfehler blockieren JEDEN Aufruf (Exit 2) mit Meldung:
   JSON-Datei fehlt, ist leer, unlesbar oder kein gueltiges JSON; oberste
   Ebene kein Objekt; ein Schluessel doppelt, fehlend oder unbekannt; "prefix"
   kein String, nicht ausgefuellt, ohne abschliessendes "__", mit mehr als
   einem Schluesselsegment (z.B. "mcp__prod__rechnung__" — der liesse
   "mcp__prod__rechnung_anlegen" durch) oder mit einem Zeichen ausserhalb
   [A-Za-z0-9_-] im Schluessel (Leerzeichen, Tabulator, Zeilenumbruch, Punkt,
   Klammer — so ein PREFIX trifft keinen Namen und liesse alles durch);
   "allowlist" keine Liste (ein String
   liesse per "in" Teilstrings durch) oder ein Eintrag kein String bzw. ohne
   diesen PREFIX. Ebenso kaputte Eingabe oder interner Fehler.
   NICHT erkennbar ist ein PREFIX, der die Form hat, aber den falschen
   Schluessel nennt (z.B. "mcp__prod_alt__" statt "mcp__prod__"): er trifft
   nichts, und der Waechter laesst alles durch. Das faengt nur Schritt 5.
   "Nie Exit 1" gilt fuer DIESES Skript, sobald main() laeuft: Es endet dann
   nur mit 0 oder 2. VOR main() kann noch scheitern: der Interpreter startet
   nicht (Exit 127), die .py selbst ist beschaedigt (SyntaxError, Exit 1), ein
   Import der Standardbibliothek fehlt oder wird von einer fremden Datei
   gleichen Namens verdraengt (Exit 1 — deshalb "-I", Schritt 2). Diese Exits
   kommen nicht aus
   der Entscheidungslogik — und der Client laesst sie durch. Daher Schritt 4.
4. GATE-PROBE — eine Zeile im LOKALEN Gate, bei JEDEM Lauf, nicht einmalig.
   Werkzeug: docs/vorlagen/waechter-gate-probe.py (nur Standardbibliothek,
   kein Netz, liest nur):

     ⟨/absoluter/pfad/zu/python3⟩ -I -S docs/vorlagen/waechter-gate-probe.py \
       --einstellungen ⟨pfad/zu/den/agenten-einstellungen.json⟩ \
       --matcher '⟨PREFIX⟩.*' \
       --befehl '⟨der "command"-Wert aus den Agenten-Einstellungen, unveraendert⟩' \
       --unbekannt '⟨PREFIX⟩gate_probe_erfunden' \
       --lesend '⟨ein Name aus der allowlist⟩' \
       --quelle docs/vorlagen/prod-readonly-hook.py \
       --werkzeuge ⟨datei mit allen Werkzeugnamen des Namensraums, eine je Zeile⟩ || exit 1

   DERSELBE absolute Interpreter wie im Hook-Befehl (Schritt 2), Zeichen fuer
   Zeichen, mit denselben Schaltern -I -S — nicht nur wegen Exit 127, wenn
   "python" fehlt, sondern weil die Probe prueft, dass der Interpreter des
   Hook-Befehls zeichengleich DERSELBE ist wie der, mit dem sie selbst
   laeuft (normalisierter Pfad und samefile), und sich selbst ohne -I -S
   verweigert. Ein anderer Pfad ist rot: Ein sh-Skript namens python3-hook
   bestand die blosse Namensform und verzweigte; ein Hardlink des
   Interpreters an anderem Ort bestand samefile und loeste dort ein eigenes
   site-packages auf (Gegenpruefer, Nacharbeiten 3 und 4, gemessen).

   WAS SIE BEWEIST: Der Hook-Befehl ist genau <interpreter> -I -S <waechter.py>
   ohne Shell-Metazeichen ($ ~ % ^ ' # @ , Backslash …), der Interpreter ist
   der der Probe, die installierte .py ist byte-gleich mit --quelle
   (Pflicht) und importiert nur json, os, sys — ohne Alias, ohne from —
   und benutzt an diesen Modulen nur, was diese Vorlage braucht (zwei
   Allowlists, per Syntaxbaum bewiesen; darauf beruht -I -S); Attribute und
   Namen, die an anderen Objekten Prozesse starten oder an Interna kommen,
   faengt sie dazu (kein Beweis; Grenze im Kopf der Probe) —, der
   Waechter nennt auf --konfig-pfad genau diese .py und ihre .json, die
   .json ist gueltig, jeder Allowlist-Name steht in der Werkzeugliste
   (--werkzeuge, Pflicht), der Matcher trifft JEDEN Namen der Liste, und der
   Befehl blockiert jeden Namen ausserhalb der Allowlist (Exit 2) und laesst
   jeden innerhalb durch (Exit 0) — aufgerufen mit einer Eingabe wie der des
   Clients, mit NICHT-LEEREM tool_input (ein Waechter, der darauf verzweigt,
   war fuer eine Probe mit leerem tool_input unsichtbar; Gegenpruefer,
   Nacharbeit 4). Damit laeuft bei echten Aufrufen dieselbe Datei mit
   demselben Interpreter und derselben Umgebung wie in der Probe.
   WAS SIE NICHT ZEIGT: ob der Client GENAU diese Einstellungsdatei liest
   und den Waechter wirklich aufruft, ob der PREFIX den echten Schluessel
   nennt (Schritt 5), ob die Werkzeugliste VOLLSTAENDIG ist — fehlt ein
   Schreibwerkzeug darin und ist der Matcher genau darauf verengt, bleibt
   die Probe gruen; deshalb Liste aus dem Katalog des Servers erzeugen, nicht
   von Hand, und bei jedem neuen Werkzeug nachfuehren — und ob die ALLOWLIST
   nur Lese-Werkzeuge nennt (die Probe misst gegen die Allowlist, die der
   Waechter liest; ein Schreibwerkzeug darin bekommt Exit 0 und die Probe
   bleibt gruen) — und von der Quelle nur, was der Syntaxbaum sieht, nie
   ihre Absicht: Eine Waechter-Quelle, die geschrieben ist, um die Probe zu
   erkennen, erkennt sie (Kopf der Gate-Probe). Das
   prueft der Mensch beim Pflegen der Allowlist, der Diff im Repo und die
   Echtprobe (Schritt 5).
   Rot ausserdem bei: anderem Ereignis als PreToolUse, abgeschalteten Hooks
   (auch verschachtelt), "command" nicht zeichengenau, Befehl nur in einem
   fremden Feld, veraltetem Interpreter-Pfad, beschaedigter .py, kaputter
   oder fremder Konfiguration. Ihre eigene Richtigkeit prueft
   waechter-gate-probe-selbsttest.py (eigene Gate-Zeile, deterministisch).
5. ECHTPROBE — Pflicht beim Scharfschalten UND nach jeder Aenderung an der
   Konfiguration, an der Client-Registrierung (Schluessel, Client,
   Einstellungen) UND an dieser .py; ohne sie beweisen Schritt 3 und 4
   nichts ueber den Client — und nichts ueber eine Quelle, die geschrieben
   ist, um die Gate-Probe zu erkennen (die Probe prueft Installation und
   Umgebung, von der Quelle nur, was der Syntaxbaum sieht; Kopf der
   Gate-Probe). Die Absicht der Quelle prueft der Diff im Repo, und die
   Echtprobe prueft den echten Aufruf:
     In der INSTALLIERTEN ⟨projekt⟩_prod_readonly.json (die .json neben der
     installierten .py, Schritt 1) ein Lese-Werkzeug voruebergehend aus der
     "allowlist" nehmen. Dann im Agenten-Client einen
     ECHTEN Aufruf genau dieses Werkzeugs ausloesen. Er MUSS mit der
     Waechter-Meldung ("Waechter: ... nicht als lesend hinterlegt") abgelehnt
     werden. Nur das beweist zugleich: der Client ruft den Waechter, der
     Interpreter startet, der PREFIX passt.
     Geht der Aufruf durch: Der Waechter ist wirkungslos (falscher PREFIX,
     falscher Client, Interpreter fehlt) — NICHT weiterarbeiten, erst klaeren.
     Danach die Kopie zuruecksetzen und Drift-Abgleich und Gate-Probe gruen
     sehen.
     "Der Aufruf ging durch, der Waechter hat ihn also gesehen" ist KEIN
     Nachweis: Auf dem erlaubten Pfad gibt der Waechter nichts aus, und ein
     Waechter, der nie startet, laesst denselben Aufruf ebenso durch.
6. In CLAUDE.md vermerken, dass der Waechter existiert und NIE abgeschaltet
   wird — und dass neue Lese-Werkzeuge in prod-readonly-hook.json der
   Repo-Quelle nachzutragen sind (danach kopieren, Gate, Echtprobe).
"""

# VOR main() stehen nur Importe der Standardbibliothek und Definitionen. Was
# hier noch scheitern kann (Interpreter fehlt, diese Datei beschaedigt), endet
# mit einem Exit ausser 2 — das faengt die Gate-Probe (Schritt 4), nicht dieser
# Code. Alles, was ein Projekt aendert, wird erst in main() im try gelesen.
import json
import os
import sys

# Die Konfiguration heisst wie diese Datei (<name>.py -> <name>.json), damit
# zwei Waechter im selben Verzeichnis zwei Konfigurationen lesen. os.path
# folgt keinem Symlink: Der Client ruft den Link-Pfad auf, also zaehlt dessen
# Name — bewusst so.
KONFIG_NAME = os.path.splitext(os.path.basename(__file__))[0] + ".json"
KONFIG_SCHLUESSEL = frozenset({"prefix", "allowlist"})
KONFIG_OPTIONAL = frozenset({"geblockt"})  # Name -> Grund; nur Form, nie Entscheidung

EXIT_BLOCKIEREN = 2  # Exit-Code 2 = Aufruf ablehnen, stderr geht an den Agenten

# Zeichen, aus denen ein Registrierungsschluessel bestehen darf. Alles andere
# (Leerzeichen, Tabulator, Zeilenumbruch, Punkt, Klammer, Platzhalter) ergibt
# einen PREFIX, der auf KEINEN Werkzeugnamen passt — und ein PREFIX, der nichts
# trifft, laesst alles durch (fail-OPEN). Gemessen bis v1.15.2: "mcp__ prod__",
# "mcp__prod.alt__" und ein PREFIX mit Zeilenumbruch galten als gueltige Form,
# und der schreibende Aufruf endete mit rc=0.
SCHLUESSEL_ZEICHEN = frozenset(
    "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789" "_-"
)


class KonfigFehler(Exception):
    pass


def blockieren(grund: str) -> int:
    # Die Meldung darf die Entscheidung nie kippen: Scheitert die Ausgabe
    # (z.B. Konsolenkodierung bei einem exotischen Werkzeugnamen), bleibt es
    # beim Blockieren.
    try:
        sys.stderr.buffer.write(f"Waechter: {grund}\n".encode("utf-8", "replace"))
        sys.stderr.flush()
    except BaseException:
        pass
    return EXIT_BLOCKIEREN


def praefix_gueltig(praefix: object) -> bool:
    # Ein nicht ausgefuellter, unscharfer oder zu enger PREFIX ist fail-OPEN
    # (trifft nichts, zu viel oder zu wenig) — deshalb wird er wie ein Fehler
    # behandelt, nicht still hingenommen. Form: mcp__<schluessel>__, der
    # Schluessel ist EIN Segment aus SCHLUESSEL_ZEICHEN (kein "__" darin, nicht
    # mit "_" am Rand); die Zeichenmenge schliesst die Platzhalter ⟨⟩ der
    # Beispieldatei AUS. (Die ausgelieferte Beispieldatei scheitert schon
    # eine Zeile frueher, an startswith("mcp__") — die Zeichenmenge traegt
    # erst bei einer Form wie mcp__⟨projekt⟩__. Blockiert wird sie so oder
    # so.)
    # Einen Schluessel mit richtiger Form, aber falschem Namen erkennt diese
    # Pruefung nicht — dafuer ist die Echtprobe (Schritt 5) da; ein Schluessel
    # mit Grossbuchstaben ist eine gueltige Form, ob er der RICHTIGE ist, zeigt
    # ebenfalls nur die Echtprobe.
    if not isinstance(praefix, str):
        return False
    if not (praefix.startswith("mcp__") and praefix.endswith("__")):
        return False
    schluessel = praefix[len("mcp__"):-len("__")]
    return (
        len(schluessel) > 0
        and "__" not in schluessel
        and not schluessel.startswith("_")
        and not schluessel.endswith("_")
        and all(zeichen in SCHLUESSEL_ZEICHEN for zeichen in schluessel)
    )


def ohne_doppelte_schluessel(paare: list) -> dict:
    # json.load nimmt bei doppeltem Schluessel still den letzten — eine zweite
    # "allowlist" weiter unten ersetzte die erste unbemerkt.
    ergebnis = {}
    for schluessel, wert in paare:
        if schluessel in ergebnis:
            raise KonfigFehler(f"Schluessel '{schluessel}' doppelt")
        ergebnis[schluessel] = wert
    return ergebnis


def konfig_laden(pfad: str) -> tuple:
    # Liefert (PREFIX, ALLOWLIST als frozenset) oder wirft KonfigFehler.
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            konfig = json.load(datei, object_pairs_hook=ohne_doppelte_schluessel)
    except KonfigFehler:
        raise
    except FileNotFoundError:
        raise KonfigFehler(f"{KONFIG_NAME} fehlt neben dem Waechter ({pfad})")
    except Exception as fehler:
        # leer, unlesbar, kein gueltiges JSON, falsche Kodierung
        raise KonfigFehler(f"{KONFIG_NAME} nicht lesbar ({type(fehler).__name__})")

    if not isinstance(konfig, dict):
        raise KonfigFehler(f"{KONFIG_NAME}: oberste Ebene ist kein Objekt")
    unbekannt = sorted(set(konfig) - KONFIG_SCHLUESSEL - KONFIG_OPTIONAL)
    if unbekannt:
        raise KonfigFehler(f"{KONFIG_NAME}: unbekannte Schluessel {unbekannt}")
    fehlend = sorted(KONFIG_SCHLUESSEL - set(konfig))
    if fehlend:
        raise KonfigFehler(f"{KONFIG_NAME}: fehlende Schluessel {fehlend}")

    praefix = konfig["prefix"]
    if not praefix_gueltig(praefix):
        raise KonfigFehler(
            "prefix ist nicht ausgefuellt oder hat nicht die Form "
            "'mcp__<schluessel>__' mit genau einem Schluesselsegment aus "
            "[A-Za-z0-9_-]"
        )

    liste = konfig["allowlist"]
    # Eine Liste aus Strings, die alle im geschuetzten Namensraum liegen. Ein
    # String statt einer Liste liesse per "in" jeden Teilstring durch; ein
    # Eintrag ohne PREFIX ist ein Tippfehler, der still nie greift.
    if not isinstance(liste, list):
        raise KonfigFehler("allowlist ist keine Liste")
    for eintrag in liste:
        if not (
            isinstance(eintrag, str)
            and eintrag.startswith(praefix)
            and eintrag[len(praefix):].strip()
            and "⟨" not in eintrag
        ):
            raise KonfigFehler(
                f"allowlist-Eintrag {eintrag!r} ist kein Werkzeugname mit dem prefix"
            )
    geblockt = konfig.get("geblockt", {})
    if not isinstance(geblockt, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in geblockt.items()
    ):
        raise KonfigFehler(f"{KONFIG_NAME}: geblockt muss ein Objekt Name -> Grund sein")
    # Ein geblockt-Eintrag ohne PREFIX trifft kein Werkzeug dieses Namensraums;
    # die Widerspruchspruefung unten liefe ins Leere und der Eintrag waere eine
    # stille Notiz statt einer Pflegeaussage.
    for name in sorted(geblockt):
        if not (name.startswith(praefix) and name[len(praefix):].strip()
                and "⟨" not in name):
            raise KonfigFehler(
                f"{KONFIG_NAME}: geblockt-Eintrag {name!r} ist kein Werkzeugname mit dem prefix"
            )
    beides = sorted(set(geblockt) & set(liste))
    if beides:
        # Ein Name in allowlist UND geblockt ist ein Widerspruch in der Pflege
        # — still durchlassen waere die falsche Richtung (Gegenpruefer).
        raise KonfigFehler(f"{KONFIG_NAME}: in allowlist UND geblockt: {beides}")
    return praefix, frozenset(liste)


def entscheiden(ereignis: object, praefix: str, allowlist: frozenset) -> int:
    if not isinstance(ereignis, dict):
        return blockieren("Eingabe ist kein JSON-Objekt — blockiert.")

    werkzeug = ereignis.get("tool_name")
    if not isinstance(werkzeug, str) or not werkzeug:
        # Ohne Werkzeugnamen laesst sich nicht belegen, dass der Aufruf NICHT
        # gegen die Produktivinstanz geht.
        return blockieren("Eingabe ohne gueltigen tool_name — blockiert.")

    if not werkzeug.startswith(praefix):
        return 0  # anderer Namensraum, nicht unsere Zustaendigkeit

    if werkzeug in allowlist:
        return 0

    return blockieren(
        f"'{werkzeug}' ist nicht als lesend hinterlegt und wird gegen die "
        f"Produktivinstanz blockiert.\n"
        f"Wenn es wirklich nur liest: der Mensch traegt es in {KONFIG_NAME} der "
        f"Repo-Quelle ein, kopiert die Datei nach draussen (Drift-Abgleich und "
        f"Gate-Probe im lokalen Gate) und faehrt die Echtprobe.\n"
        f"Wenn es schreibt: gegen den Teststand arbeiten."
    )


def main() -> int:
    try:
        pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), KONFIG_NAME)
        if "--konfig-pfad" in sys.argv[1:]:
            # ABFRAGEMODUS fuer die Gate-Probe: Der Waechter nennt selbst, welche
            # Datei er liest — die Probe leitet das nicht mehr aus dem Befehlstext
            # ab (ein Wrapper mit Koeder-Argument liess sie eine andere Datei
            # pruefen als die, die lief; Gegenpruefer, v1.15.4-Panel).
            # Er BLOCKIERT dabei trotzdem (Exit 2): Haengt jemand "--konfig-pfad"
            # an den eingetragenen Hook-Befehl, wird dadurch nichts geoeffnet,
            # sondern jeder Aufruf abgelehnt — laut und fail-closed.
            try:
                sys.stdout.write(json.dumps({"py": os.path.abspath(__file__),
                                             "konfig": pfad}) + "\n")
                sys.stdout.flush()
            except Exception:
                pass
            return blockieren("Abfragemodus (--konfig-pfad) — antwortet nur der "
                              "Gate-Probe und blockiert jeden Werkzeugaufruf.")
        try:
            praefix, allowlist = konfig_laden(pfad)
        except KonfigFehler as fehler:
            return blockieren(
                f"Konfiguration ungueltig: {fehler} — blockiert, bis der "
                f"Waechter konfiguriert ist."
            )
        try:
            ereignis = json.load(sys.stdin)
        except Exception:
            # Unlesbare Eingabe ist kein Freibrief.
            return blockieren("Eingabe nicht lesbar — blockiert.")
        return entscheiden(ereignis, praefix, allowlist)
    except BaseException as fehler:
        # Ein Absturz endet sonst mit Exit 1 — und Exit 1 laesst der Client als
        # "nicht blockierender Fehler" DURCH. Jeder unerwartete Fehler blockiert.
        # Das deckt nur Fehler INNERHALB von main(): Startet der Interpreter
        # gar nicht (Exit 127) oder ist diese Datei beschaedigt, kommt der Exit
        # nicht von hier — Gate-Probe (Schritt 4) und Echtprobe (Schritt 5).
        return blockieren(f"interner Fehler ({type(fehler).__name__}) — blockiert.")


if __name__ == "__main__":
    sys.exit(main())
