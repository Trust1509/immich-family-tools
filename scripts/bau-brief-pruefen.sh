#!/bin/sh
# Zeigt, WO in einem Bau-Brief die zehn Pflicht-Themen behandelt sein koennten.
#
#   sh scripts/bau-brief-pruefen.sh <brief.md>
#
# Selbstprobe nach jeder Aenderung an diesem Skript, an den Prueffragen oder an
# den Pflicht-Randbedingungen in bau-brief.md:
#   sh scripts/bau-brief-pruefen-selbsttest.sh
#
# DAS TRAGENDE PRINZIP: DIE ASYMMETRIE
# ------------------------------------
#   KEIN Treffer  -> keines der Suchwoerter eines Themas kommt im Brief vor.
#                    Starkes Signal, KEIN Beweis: Der Wortschatz unten ist
#                    fest, ein Brief kann das Thema mit anderen Woertern
#                    behandeln. Bei [KEIN TREFFER] sucht der Arbiter das
#                    seltenste Einzelwort des EIGENEN Briefs zu diesem Thema
#                    nach. Wortgruppen sind zusaetzlich schwaecher: grep
#                    arbeitet zeilenweise, eine Wortgruppe ueber einem Umbruch
#                    liefert null Treffer, obwohl sie dasteht (gemessen an
#                    umbrochener Markdown-Prosa, 08/2026).
#                    UND: wer diesem Skript eine eigene Suche zur Seite
#                    stellt, setzt LC_ALL=C davor UND schreibt kein
#                    Umlaut-Zeichen ins Muster, sondern "..?" (Begruendung
#                    bei LC_ALL unten). Beides ist noetig: Unter einer
#                    UTF-8-Locale ist ein CP1252-Brief fuer grep binaer, und
#                    "." trifft dort ein ungueltiges Byte nicht — gemessen:
#                    "pr..?ffrage" gegen "Pr\374ffragen" (CP1252) unter
#                    C.UTF-8 kein Treffer, unter C ein Treffer.
#   EIN Treffer   -> unbelastbar. Es kann Behandlung sein, Erwaehnung,
#                    Verneinung, Nachbarwort oder wiederverwendete Floskel.
#
# RISIKO-MUSTER: "Risiko: R2" oder "Risikoklasse: R2" auf einer Zeile — zwischen
# Wort und Klasse bis zu drei Bytes, die weder Buchstabe noch Ziffer sind
# (Leerzeichen, Tab, geschuetztes Leerzeichen als ein oder zwei Bytes; gemessen:
# mit " *" allein fielen Tab und geschuetztes Leerzeichen als [KEIN TREFFER]
# durch) —, oder eine Zeile, die auf "Risiko:" endet (Klasse umbrochen). Das Muster schaut die
# Folgezeile NICHT an — es verlangt den Doppelpunkt am Zeilenende, damit Prosa,
# die zufaellig auf "Risiko" umbricht, kein Kandidat wird. [[:space:]] statt
# Leerzeichen, weil ein Brief mit CRLF-Zeilenenden sonst "\r" vor dem Ende hat
# (gemessen: [KEIN TREFFER] bei vorhandenem Block 0).
#
# PRUEFFRAGEN: JE FRAGE EINE ZEILE, DIE MIT IHREM ANFANG BEGINNT. Frueher
# reichte ein Suchwort; dann je Frage ein Zaehlwort irgendwo im Brief. Beides
# fiel auf Alltagsprosa herein (gemessen, v1.15.2: ohne Frage 2 und mit "der
# Wert, der wahr ist" 11 von 11, Exit 0; ebenso "Behauptung", "Produkt-",
# "seine", "Eigenschaften"). Jetzt zaehlt eine Frage nur, wenn eine Zeile
# (nach Leerraum, Nummer, Aufzaehlungszeichen, entfernter Auszeichnung — genau:
# nach beliebig vielen Bytes, die kein Buchstabe a-z sind) mit den ersten zwei
# bis drei Woertern ihres fetten Fragesatzes beginnt ("schreibt dieser fix",
# "welchen pfad benutzt"). Prosa beginnt eine Zeile kaum so (gemessen gegen
# bau-brief.md und lehren.md: kein Treffer ausserhalb der Fragenzeilen).
# Ausgabe "k von N" und eine Zeile mit der Fundzeile je gefundener Frage;
# k = 0 -> [KEIN TREFFER]; 0 < k < N -> [UNVOLLSTAENDIG] mit den fehlenden
# Nummern, zaehlt als fehlendes Thema (Exit 1). Grenze siehe unten
# ("Prueffragen nur am Zeilenanfang").
#
# EINE EIGENE PRUEFFRAGE BRAUCHT ZWEI STELLEN: eine Zeile in "FRAGEN" hier UND
# die Frage selbst in bau-brief.md. Nur eine von beiden reicht NICHT — die
# Selbstprobe zaehlt die Fragen dort, haelt sie gegen die Zeilen hier und
# bricht mit Exit 2 ab, solange die Zahlen auseinanderlaufen.
# Form hier: "<Nummer>;<die ersten zwei bis drei Woerter, klein, Umlaut als
# ..?>", Nummer ab N+1 (abgleich.md 2e: projekteigene Nummern hinten
# anhaengen, nie zwischen die Vorlagen-Nummern). N ist die Zahl der Zeilen in
# FRAGEN und wird hier abgeleitet, nicht geschrieben: Vor v1.15.2 stand die 11
# an fuenf Stellen fest, und ein Brief ohne die zwoelfte Frage meldete
# "11 von 11", Exit 0 (gemessen).
#
# Deshalb behauptet dieses Skript kein "vorhanden" mehr. Es nennt Kandidaten
# MIT der Fundzeile, damit du in Sekunden urteilst statt den ganzen Brief zu
# lesen. Der Exit-Code faellt nur, wenn ein Thema NIRGENDS vorkommt (oder
# Prueffragen fehlen) — das ist die Richtung, in der eine Textsuche am meisten
# traegt (Grenzen unten).
#
# WAS ES NICHT KANN (gemessen, nicht vermutet; Herkunft je Grenze)
# -----------------------------------------------------------------
# * VERNEINUNGEN nicht von Behandlung unterscheiden (aus fuenf Projekten).
#   "Einen Rot-Beweis brauchst du hier eher nicht" traf als Thema "Nachweis".
#   Schlimmer: Bei "Fixtures" traf ausgerechnet die Zeile, die die Regel
#   VERLETZT ("nimm die Testdaten aus dem, was da ist"). Kandidaten mit
#   Verneinungswort werden deshalb markiert — als Hinweis, nicht als Urteil.
# * NACHBARWOERTER in deutscher Prosa (aus fuenf Projekten): "doku" trifft
#   "dokumentieren", ein Dateipfad in einer Beschreibung trifft wie ein
#   auszufuehrendes Kommando.
# * MEHRWORTIGE Muster am ZEILENUMBRUCH (eigene Messung, 08/2026): mehrere
#   THEMEN-Muster unten sind zweiwortig ("sichtbares verhalten", "ruft .* auf")
#   — in einem Brief mit harten Umbruechen koennen sie durchfallen. Die
#   Einzelwort-Alternativen je Zeile fangen das meist; wer einem
#   [KEIN TREFFER] misstraut, sucht das seltenste EINZELWORT nach.
# * FLOSKELN von slice-spezifischer Behandlung unterscheiden (aus fuenf
#   Projekten). Eine Standard-Regelzeile ("Fixtures erfunden, Rot-Beweis je
#   Test, Gates im Vordergrund") saettigt drei Themen auf einmal, ohne dass
#   eines fuer DIESEN Slice durchdacht waere. Jede Verschaerfung dagegen liefe
#   wieder auf Gliederungs-Urteile hinaus — deshalb bleibt es hier stehen statt
#   behoben zu werden.
# * FESTER WORTSCHATZ (eigene Messung, v1.15.2): Ein Thema, das der Brief mit
#   Woertern behandelt, die unten nicht stehen, meldet [KEIN TREFFER]
#   (Fehlalarm; vor v1.15.2 z. B. "cargo test && go vet" als Kommandos). Die
#   Gegenrichtung ist die gefaehrlichere und hat eine eigene Grenze:
# * WOERTLICHE PFLICHTTEXTE (eigene Messung, v1.15.2): Ein Suchwort, das in
#   den Prueffragen (bau-brief.md, Abschnitt "… Prueffragen vor der Landung")
#   vorkommt, erfuellt sein Thema in JEDEM Brief — die Fragen stehen woertlich darin. Ebenso ein
#   Suchwort aus einem Satz, den jeder Brief traegt (Abnahme "je Punkt womit
#   belegt"). In den Brief gehoert je Frage nur der FETTE Fragesatz; die
#   Suchwoerter sind trotzdem so gewaehlt, dass auch der vollstaendige
#   Fragentext mit Erklaertext kein anderes Thema erfuellt; dasselbe gilt fuer
#   die Pflicht-Randbedingungen (bau-brief.md, "Randbedingungen, die immer
#   mitmuessen"; bis v1.15.2 erfuellten "Pruef-Kommandos" und "endet mit einem
#   Nachweis" darin Kommandos und Nachweis ohne Block 5 und 6, gemessen) UND
#   fuer "Typische Fallen" (bau-brief.md), die woertlich in Briefe kopiert
#   werden: bis v1.15.2 erfuellten drei Fallen die Themen Sichtbares,
#   Nachweis und Fixtures ohne den jeweiligen Block, gemessen, schon mit einer
#   einzigen kopierten Falle. Das
#   haelt die Selbstprobe (bau-brief-pruefen-selbsttest.sh) — fuer den
#   eingebauten Muster-Brief mit diesen Pflichttexten und Alltagsprosa, nicht
#   fuer jeden denkbaren Brief: Sie wird rot, wenn dort ein fehlendes Thema
#   oder eine fehlende Frage nicht gemeldet wird.
# * PRUEFFRAGEN NUR AM ZEILENANFANG (eigene Messung, v1.15.2): Geprueft werden
#   nur die ersten zwei bis drei Woerter jeder Frage am Zeilenanfang. Eine
#   Frage, deren Rest umformuliert ist, zaehlt als vorhanden; eine Frage
#   mitten in einer Zeile ("Frage 2: Prueft dieser Test") oder mit anderem
#   Anfang zaehlt als fehlend (Fehlalarm). Eine Prosazeile, die zufaellig mit
#   einem Fragenanfang beginnt, zaehlt als Frage (Durchlass).
#
# Ein sauberer Lauf heisst: "nichts vergessen". Nicht: "Brief ist gut".
set -e

# LOCALE: DAS SKRIPT SETZT SIE SELBST, UND ZWAR AUF C (seit v1.15.0).
# Eine Aufrufkonvention ("setze LC_ALL davor") ist keine Schutzschicht — eine
# Meldung wurde mit genau dieser Konvention geschlossen, und 5 von 7 Mustern
# blieben defekt ("Zweck-Identität" als einzige Prueffragen-Zeile:
# [KEIN TREFFER], Exit 1, gemessen). Warum C und NICHT C.UTF-8 — auch
# gemessen: Unter einer UTF-8-Locale behandelt GNU grep ab 3.5 eine Datei mit
# ungueltigen UTF-8-Bytes als BINAER und gibt keine Trefferzeilen aus. Ein
# Brief, den ein Editor oder Windows-PowerShell in CP1252 gespeichert hat,
# lieferte dann [KEIN TREFFER] fuer Themen, die dastanden (Entwurf von v1.15.0,
# vom Blindpruefer gefunden, reproduziert). Unter C ist jedes Byte gueltig, und
# die Muster unten sind so gebaut, dass sie ohne Zeichenlogik auskommen.
LC_ALL=C
export LC_ALL

BRIEF="$1"
[ -n "$BRIEF" ] || { echo "Aufruf: sh scripts/bau-brief-pruefen.sh <brief.md>"; exit 2; }
[ -f "$BRIEF" ] || { echo "Nicht gefunden: $BRIEF"; exit 2; }

# Thema|Suchmuster (erweiterte Regex, case-insensitive, ganzes Dokument)
#
# WORTSCHATZ GEMESSEN, v1.15.2:
# * Befund enthielt "beleg" und "gemessen". Prueffrage 6 ("belegt") und 10
#   ("gemessen") stehen woertlich in jedem Brief, "belegt" dazu in der
#   Abnahme — ein Brief OHNE Befund-Block kam als Kandidat durch (gemessen:
#   Brief aus Bloecken 0-9, Block 2 weggelassen -> DURCHLASS). Beide gestrichen.
# * Kommandos enthielt "tsc" ohne Wortgrenze: traf "deutsch" und "Entscheid"
#   (Durchlass), waehrend "cargo test && go vet" [KEIN TREFFER] meldete
#   (Fehlalarm). Jetzt Wortgrenze portabel als ([^a-z]|$) statt \b, dazu die
#   gaengigen Werkzeuge anderer Stacks; "kommando" ersetzt "pr..?f-kommando".
# * Mit dem VOLLSTAENDIGEN Fragentext (fett + Erklaertext) blieben fuenf Themen
#   stumm (gemessen, Blind- und Gegenpruefer v1.15.2): "Pruefauftrag" (Frage 8)
#   hielt Auftrag, "schwersten Befund" (8) Befund, "unter Konsumenten" (8)
#   Konsumenten, "Mutation" (5) und "Rot-Beweis" (7) Nachweis, "Testdatenbank"
#   (5) Fixtures. Deshalb: "auftrag" nur am Wortanfang; "befund" und
#   "konsument" nur am Zeilenanfang (nach Auszeichnung, Nummer, Aufzaehlung)
#   oder direkt vor ":"; "rot-beweis" und "mutation" ebenso; "testdaten" nicht
#   vor "b". Verlust: "der Befund" mitten in einer Prosazeile ohne ":" traegt
#   das Thema nicht mehr — die Ueberschrift "## 2 Befund" traegt es.
THEMEN="Risiko|risiko(klasse)?:?[^a-z0-9]{0,3}r[0-9]|risiko(klasse)?:[[:space:]]*$
Auftrag|(^|[^a-z])auftrag|zu bauen|gebaut wird|umzusetzen
Befund|^[^a-z]*befund|befund[a-z]*:|verifiziert|festgestellt|ausgangslage
Konsumenten|^[^a-z]*konsument|konsument[a-z]*:|ruft .* auf|aufrufer|caller|wer ruft
Sichtbares|sichtbares verhalten|verhalten ..?nder|handbuch|nutzer-doku|sichtbar
Nachweis|^[^a-z]*(rot-beweis|mutation)|(rot-beweis|mutation)[a-z]*:|rotbeweis|sabotier|nachweis|gegenprobe
Kommandos|kommando|gates\.sh|pytest|npm |pnpm |yarn |(^|[^a-z])tsc([^a-z]|$)|cargo |go (test|vet|build)|make |mvn |gradle|dotnet |ruff|eslint|uv run
Fixtures|fixture|testdaten([^b]|$)|seed
Randbedingungen|randbedingung|nicht pushen|vordergrund|leitplanke"

# Je Prueffrage die ersten Woerter ihres fetten Fragesatzes: Nummer;Muster
# (grep -E, Kleinbuchstaben, Umlaut als "..?"). Das Muster gilt nur am
# Zeilenanfang hinter ANFANG. Die Zahl der Zeilen hier IST N — eine eigene
# Frage ist eine Zeile mehr (Nummer ab N+1) UND die Frage in bau-brief.md.
# Neue oder geaenderte Fragen: Muster gegen bau-brief.md und lehren.md zaehlen
# (LC_ALL=C grep -c -i -E) — ein Treffer ausserhalb der Fragenzeilen ist ein
# Fund; die Selbstprobe prueft den Muster-Brief mit Alltagsprosa.
ANFANG='[^a-z]*'
FRAGEN="1;schreibt dieser fix
2;pr..?ft dieser test
3;welche geschwister-routinen
4;w..?hlt eine routine
5;gilt die rot-zahl
6;ist jede behauptung
7;welchen pfad benutzt
8;z..?hlt der slice
9;welche eigenschaft hat
10;welche real verschiedenen
11;welche projekt-pr..?misse"

# UMLAUTFREI UND BYTE-ROBUST: "grep -i" faltet unter C kein Ü/Ä/Ö
# (gemessen: "## 9 PRÜFFRAGEN" fiel als [KEIN TREFFER] durch), also steht in
# keinem Muster ein Umlaut. Jeder Umlaut ist "..?" — trifft "ü" als zwei Bytes
# (UTF-8-Datei), als ein Byte (CP1252-Datei) und "ue" als Ersatzschreibung. EIN Punkt reicht NICHT:
# Die v1.14.0-Fassung schrieb "entf.ll", "er.brigt", "zweck-identit.t" —
# der Kommentar nannte sie "analog", sie waren es nicht (v1.15.0, nachgemessen).
# Regel fuer jede Ersatzschreibung: sie muss die BYTE-Zahl treffen, sonst
# tarnt der Fix den Defekt.
VERNEINUNG="nicht|kein|entf..?ll|braucht.*nicht|er..?brigt|weiss ich nicht|wei..? ich nicht"

# AUSZEICHNUNG VOR DER SUCHE ENTFERNEN: "Risiko: **R2**" fiel durch das Muster
# "risiko: r[0-9]" — ein falsch-negativer Treffer durch Markdown-Fettdruck,
# also ein Bruch der Asymmetrie. Das Werkzeug passt sich dem Brief an, nicht
# der Brief dem Werkzeug. Zeilennummern bleiben erhalten (sed arbeitet je Zeile).
# trap VOR dem ersten Schreibzugriff: stirbt sed (set -e), bleibt sonst die
# Temp-Datei liegen. Eingabe per Umleitung, nicht als Argument: ein Brief
# namens "-brief.md" war fuer sed eine Option (gemessen: Exit 4).
BEREINIGT=$(mktemp)
trap 'rm -f "$BEREINIGT"' EXIT
sed 's/[*_`]//g' < "$BRIEF" > "$BEREINIGT"

OHNE=0
echo "Bau-Brief: $BRIEF"
echo "Kein Treffer heisst: keines der Suchwoerter kommt vor — starkes Signal, kein Beweis (fester Wortschatz;"
echo "seltenstes Einzelwort des eigenen Briefs nachsuchen). Ein Treffer ist ein KANDIDAT — bitte lesen."
echo

OLDIFS=$IFS
IFS='
'
# WENIGE PROZESSE: Unter Git Bash kostet jeder Prozessstart um 45 ms (gemessen,
# v1.15.2) — die fruehere Fassung mit echo|cut je Zeile brauchte 12 s je Brief,
# die Selbstprobe mit ueber hundert Laeufen waere unbenutzbar. Deshalb
# Parameter-Expansion statt echo|cut, "grep -m 2" statt "| head -2", printf
# "%.88s" statt cut, EIN Verneinungs-grep je Thema und fuer alle Prueffragen
# zusammen ein grep, ein tr und ein sed.
for Z in $THEMEN; do
  NAME=${Z%%|*}
  MUSTER=${Z#*|}
  TREFFER=$(grep -n -i -E -m 2 "$MUSTER" "$BEREINIGT" || true)

  if [ -z "$TREFFER" ]; then
    printf '  [KEIN TREFFER]  %s\n' "$NAME"
    OHNE=$((OHNE + 1))
    continue
  fi

  printf '  Kandidat        %s\n' "$NAME"
  # Welche Fundzeile ein Verneinungswort traegt — geprueft wird der angezeigte
  # Text (ohne Zeilennummer und Einrueckung, 88 Zeichen). Ausgabe "<lfd. Nr>:…"
  NEG="
$(printf '%s\n' "$TREFFER" | sed 's/^[0-9]*:[[:space:]]*//; s/^\(.\{88\}\).*$/\1/' | grep -n -i -E "$VERNEINUNG" || true)"
  I=0
  for T in $TREFFER; do
    I=$((I + 1))
    ZL=${T%%:*}
    TXT=${T#*:}
    TXT=${TXT#"${TXT%%[![:space:]]*}"}
    printf '      Z%-5s %.88s\n' "$ZL" "$TXT"
    case "$NEG" in
      *"
$I:"*)
        printf '            ^ enthaelt ein Verneinungswort — behandelt der Satz das Thema\n'
        printf '              oder BESTELLT er es ab?\n'
        ;;
    esac
  done
done

ALLE=""
SEDPROG=""
ANZAHL=0
for F in $FRAGEN; do
  ANZAHL=$((ANZAHL + 1))
  ALLE="$ALLE${ALLE:+|}${F#*;}"
  SEDPROG="${SEDPROG}s/^([0-9]+):${ANFANG}${F#*;}.*\$/${F%%;*}:\1/p;"
done
# Fundzeilen "Zeile:Text" -> "Frage:Zeile" (tr vor sed: sed -E kennt kein
# portables Gross/Klein-Ignorieren).
FUNDE=$(grep -n -i -E "^${ANFANG}(${ALLE})" "$BEREINIGT" | tr 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' 'abcdefghijklmnopqrstuvwxyz' | sed -n -E "$SEDPROG" || true)
K=0
FEHLT=""
ZEILEN=""
for F in $FRAGEN; do
  NR=${F%%;*}
  ERSTE=""
  for G in $FUNDE; do
    if [ "${G%%:*}" = "$NR" ]; then ERSTE=${G#*:}; break; fi
  done
  if [ -n "$ERSTE" ]; then
    K=$((K + 1))
    ZEILEN="$ZEILEN $NR:Z$ERSTE"
  else
    FEHLT="$FEHLT $NR"
  fi
done
IFS=$OLDIFS

if [ "$K" -eq 0 ]; then
  printf '  [KEIN TREFFER]  Prüffragen (0 von %s)\n' "$ANZAHL"
  OHNE=$((OHNE + 1))
elif [ "$K" -lt "$ANZAHL" ]; then
  printf '  [UNVOLLSTAENDIG] Prüffragen: %s von %s — fehlt:%s\n' "$K" "$ANZAHL" "$FEHLT"
  printf '      Frage:Zeile%s\n' "$ZEILEN"
  OHNE=$((OHNE + 1))
else
  printf '  Kandidat        Prüffragen: %s von %s (je Frage eine Zeile, die mit ihrem Anfang beginnt — ob der Satz vollstaendig und woertlich ist, entscheidest du)\n' "$K" "$ANZAHL"
  printf '      Frage:Zeile%s\n' "$ZEILEN"
fi

echo
# Auf dem BEREINIGTEN Brief und byte-robust — beide v1.14.0-Fixes galten hier
# nicht: "**nicht** anfassen" und "NICHT ÄNDERN" fielen durch (v1.15.0, gemessen).
VERBOTE=$(grep -n -i -E "nicht anfassen|nicht ..?ndern|nicht aendern|finger weg|tabu" "$BEREINIGT" || true)
if [ -n "$VERBOTE" ]; then
  echo "HINWEIS — pruefe, ob das eine UMFANGSGRENZE oder ein URTEIL ist:"
  echo "$VERBOTE" | sed 's/^/    /'
  echo "  Grenze aus Umfang/Rechten ist legitim und gehoert in Block 8."
  echo "  Verbot aus URTEIL (\"das ist ok, sieh nicht hin\") ist schaedlich."
  echo
fi

if [ "$OHNE" -gt 0 ]; then
  echo "$OHNE von 10 Themen fehlen im Brief (kein Suchwort / Prueffragen unvollstaendig)."
  echo "Das ist der starke Teil dieser Pruefung: entweder gegenstandslos (dann"
  echo "eine Zeile Begruendung in den Brief), vergessen — oder mit Woertern"
  echo "behandelt, die das Skript nicht kennt (seltenstes Einzelwort nachsuchen)."
  exit 1
fi

echo "Zu allen 10 Themen gibt es Kandidaten."
echo "Ob sie das Thema BEHANDELN, entscheidest du an den Zeilen oben —"
echo "das Skript kann Erwaehnung, Verneinung und Floskel nicht unterscheiden."
exit 0
