#!/bin/sh
# Selbstprobe fuer scripts/bau-brief-pruefen.sh.
#
#   sh scripts/bau-brief-pruefen-selbsttest.sh [teil ...]
#
# WOFUER: Das Pruefskript soll ein fehlendes Thema und eine fehlende Prueffrage
# melden. Das bricht still, sobald ein Suchwort eines Themas in einem Text
# steht, den JEDER Brief traegt (die elf Prueffragen, die
# Pflicht-Randbedingungen), oder sobald Alltagsprosa ein Muster erfuellt
# ("der Wert, der wahr ist" hielt bis v1.15.2 eine fehlende Frage fuer
# vorhanden). lehren.md §21: eine Regel, deren Auslassung nichts rot macht,
# ist eine Notiz — diese Probe ist der Waechter dafuer.
#
# WAS SIE PRUEFT — UND WAS NICHT: Sie prueft das Skript gegen EINEN
# eingebauten, erfundenen Muster-Brief. Der traegt alle woertlich
# mitzunehmenden Texte aus docs/agents/bau-brief.md (die Prueffragen,
# einmal nur fett, einmal voll in der Zeilenaufteilung der Datei, einmal je
# Frage auf eine Zeile gezogen; die Punkte unter "Randbedingungen, die immer
# mitmuessen"; die Absaetze unter "Typische Fallen") und je Block einen Absatz
# Alltagsprosa mit Nachbarwoertern
# (Produktion, Produkt-, seine, Behauptung, wahr, Eigenschaft, Dokumentation,
# erfunden, belegt, gemessen, Test, Issue, Umfang, Risiko in Auszeichnung) UND
# je einer Zeile, die MIT dem Anfang einer Prueffrage BEGINNT, ohne die Frage
# zu sein ("Schreibt", "Prueft", "Welche", "Waehlt", "Gilt", "Ist jede",
# "Welchen", "Zaehlt") — ein verkuerztes Fragen-Muster wird daran rot
# (gemessen, v1.15.2: zehn Verkuerzungen ueberlebten die Probe, weil keine
# Prosazeile so begann).
# Gruen heisst: In DIESEM Brief wird jedes fehlende Thema und jede fehlende
# Frage gemeldet. Es heisst NICHT, dass das in jedem denkbaren Brief so ist
# (Grenzen im Kopf von bau-brief-pruefen.sh).
#
# Daraus baut sie:
#   * den vollstaendigen Brief            -> muss Exit 0 geben;
#   * je Thema einen Brief ohne dessen Block -> Exit 1, genau dieses Thema
#     gemeldet, kein anderes;
#   * je Frage einen Brief ohne diese Frage -> Exit 1, Prueffragen mit genau
#     dieser Nummer als fehlend gemeldet (die Prosa mit "wahr", "seine" usw.
#     bleibt im Brief);
#   * einen Brief mit nur einer zitierten Frage -> Prueffragen gemeldet.
# Die Fallen-Absaetze haengen an JEDEM dieser Briefe — ein fehlendes Thema
# muss trotz ihnen gemeldet werden.
# Beides je in UTF-8, CP1252 (wenn iconv vorhanden ist — sonst wird das gesagt
# und der Teil uebersprungen) und mit CRLF-Zeilenenden.
#
# WANN: nach jeder Aenderung an bau-brief-pruefen.sh, an den Prueffragen, an
# den Pflicht-Randbedingungen oder an "Typische Fallen" in bau-brief.md. Im
# Kind-Repo gehoert sie ins
# lokale Gate. Exit 0 = gruen, Exit 1 = mindestens eine Abweichung (Klartext je
# Abweichung), Exit 2 = Aufbau kaputt (Texte nicht lesbar oder unbekannter
# Teil).
#
# EIGENE PRUEFFRAGEN: Die Zahl der Fragen ist NICHT fest. Sie wird aus
# bau-brief.md gezaehlt und gegen die Zeilen in FRAGEN von
# bau-brief-pruefen.sh gehalten; Exit 2 nur, wenn die beiden Zahlen
# auseinanderlaufen (mit Klartext, welche Datei welche Zahl hat). Eine eigene
# Frage (Nummer ab N+1, abgleich.md 2e) gehoert deshalb an BEIDE Stellen: eine
# Zeile in FRAGEN und die Frage in bau-brief.md — vor v1.15.2 verlangte diese
# Probe genau elf und endete sonst mit Exit 2.
# Die UEBERSCHRIFT des Fragen-Abschnitts wird ZAHLFREI gelesen (1a unten), das
# Zahlwort darin darf also mitwachsen.
#
# DAUER: 201 Laeufe des Pruefskripts bei elf Prueffragen, je weiterer Frage
# neun mehr. Unter Linux Sekunden, unter Git Bash
# (Windows) mehrere Minuten, weil dort jeder Prozessstart um 45 ms kostet
# (gemessen: rund 2 s je Lauf). Wer dort in Teilen laufen lassen will, nennt
# sie als Argumente — ohne Argument laeuft alles:
#   sh scripts/bau-brief-pruefen-selbsttest.sh fett voll einzeilig
#   sh scripts/bau-brief-pruefen-selbsttest.sh fragen-utf8 fragen-cp1252 fragen-crlf
# ("fragen" steht fuer alle drei Fragen-Teile.)
#
# Nur sh, sed, grep, tr, cat, cp, iconv (optional).
set -u
LC_ALL=C
export LC_ALL

VARIANTEN=""
FRAGEN_ARTEN=""
[ "$#" -gt 0 ] || set -- fett voll einzeilig fragen
for TEIL in "$@"; do
  case "$TEIL" in
    fett|voll|einzeilig) VARIANTEN="$VARIANTEN $TEIL" ;;
    fragen) FRAGEN_ARTEN="$FRAGEN_ARTEN utf8 cp1252 crlf" ;;
    fragen-utf8|fragen-cp1252|fragen-crlf) FRAGEN_ARTEN="$FRAGEN_ARTEN ${TEIL#fragen-}" ;;
    *) echo "Unbekannter Teil: $TEIL (erlaubt: fett voll einzeilig fragen fragen-utf8 fragen-cp1252 fragen-crlf)"; exit 2 ;;
  esac
done

HIER=$(dirname "$0")
SKRIPT="$HIER/bau-brief-pruefen.sh"
VORLAGE="$HIER/../docs/agents/bau-brief.md"
[ -f "$SKRIPT" ] || { echo "Nicht gefunden: $SKRIPT"; exit 2; }
[ -f "$VORLAGE" ] || { echo "Nicht gefunden: $VORLAGE"; exit 2; }

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
ROT=0
LAEUFE=0
rot() { echo "ROT: $*"; ROT=$((ROT + 1)); }

# --- 1. Woertliche Pflichttexte aus bau-brief.md lesen ----------------------
# 1a. Prueffragen. Die Ueberschrift wird ZAHLFREI gesucht ("## <Zahlwort>
# Prueffragen vor der Landung"): Vor v1.15.3 stand hier "## Elf Pr" — eine
# zwoelfte Frage zwingt zum Umbenennen der Ueberschrift, und danach las diese
# Probe null Fragen und brach mit Exit 2 ab. Wer die Ueberschrift ganz anders
# nennt, zieht das Muster hier mit (die Meldung unten sagt das).
tr -d '\r' < "$VORLAGE" | sed -n '/^## .*ffragen vor der Landung/,$p' | sed '1d' | sed '/^## /,$d' > "$T/abschnitt"
: > "$T/fett"
: > "$T/voll"
: > "$T/einzeilig"
AKT=""
N=0
abschliessen() {
  if [ -n "$AKT" ]; then
    printf '%s\n' "$AKT" >> "$T/einzeilig"
    printf '%s\n' "$AKT" | sed 's/^\([0-9]*\)\. \*\*\([^*]*\)\*\*.*$/\1. **\2**/' >> "$T/fett"
    printf '%s\n' "   Antwort: trifft nicht zu." >> "$T/fett"
  fi
  AKT=""
}
while IFS= read -r L; do
  case "$L" in
    [0-9]*'. **'*)
      abschliessen
      N=$((N + 1))
      AKT=$L
      printf '%s\n' "$L" >> "$T/voll"
      ;;
    ' '*)
      if [ -n "$AKT" ]; then
        AKT="$AKT $(printf '%s' "$L" | sed 's/^ *//')"
        printf '%s\n' "$L" >> "$T/voll"
      fi
      ;;
    *)
      abschliessen
      ;;
  esac
done < "$T/abschnitt"
abschliessen

# Die Zahl der Fragen ist Daten, keine Konstante: Sie kommt aus der Vorlage
# und muss zu den Zeilen in FRAGEN des Pruefskripts passen. Abgebrochen wird
# nur, wenn die beiden auseinanderlaufen — eine projekteigene zwoelfte Frage
# (abgleich.md 2e) laeuft damit ohne Eingriff mit.
NF=$(grep -c -E '^(FRAGEN=")?[0-9][0-9]*;' "$SKRIPT")
[ "$N" -ge 11 ] || { echo "Aufbau: nur $N Prueffragen in $VORLAGE gelesen (erwartet mindestens 11 — die Vorlage fuehrt elf). Der Abschnitt wird an einer Ueberschrift '## ...ffragen vor der Landung' erkannt; heisst sie anders, das Muster in 1a mitziehen"; exit 2; }
[ "$N" -eq "$NF" ] || { echo "Aufbau: $VORLAGE fuehrt $N Prueffragen, $SKRIPT fuehrt $NF Muster in FRAGEN — erst gleichziehen (je Frage eine Zeile in FRAGEN, Nummer ab 12 fuer projekteigene)"; exit 2; }
if grep -v '^   Antwort' "$T/fett" | grep -qv '\*\*$'; then
  echo "Aufbau: nicht jede Frage hat einen fetten Fragesatz auf ihrer Nummernzeile:"
  grep -v '^   Antwort' "$T/fett" | grep -v '\*\*$'
  exit 2
fi

# 1b. Pflicht-Randbedingungen: die Aufzaehlungspunkte samt Folgezeilen
tr -d '\r' < "$VORLAGE" | sed -n '/^## Randbedingungen, die immer/,/^---/p' | grep -E '^(- |  )' > "$T/randbedingungen"
RB=$(grep -c '^- ' "$T/randbedingungen")
[ "$RB" -ge 5 ] || { echo "Aufbau: nur $RB Pflicht-Randbedingungen in $VORLAGE gelesen (erwartet mindestens 5)"; exit 2; }

# 1c. "Typische Fallen": die Absaetze, nicht der kursive Hinweis darueber.
# Ab der ersten fett beginnenden Zeile, ohne die abschliessende Trennlinie —
# derselbe Gedanke wie das grep in 1b: Was in den Brief kopiert wird, ist der
# Aufzaehlungs- bzw. Absatz-Text, nicht die Anweisung an den Schreiber.
tr -d '\r' < "$VORLAGE" | sed -n '/^## Typische Fallen/,/^---/p' | sed -n '/^\*\*/,$p' | sed '$d' > "$T/fallen"
FA=$(grep -c '^\*\*' "$T/fallen")
[ "$FA" -ge 5 ] || { echo "Aufbau: nur $FA Absaetze unter 'Typische Fallen' in $VORLAGE gelesen (erwartet mindestens 5)"; exit 2; }

# --- 2. Muster-Brief (erfunden), Bloecke 0-8 --------------------------------
# Jeder Block traegt Alltagsprosa mit Nachbarwoertern. Die Prosa eines Blocks
# darf kein Suchwort eines ANDEREN Themas enthalten — sonst ist die Probe
# selbst blind. Mitten in Block 3 steht ein Fragenanfang ausserhalb des
# Zeilenanfangs ("welchen Pfad benutzt"), damit ein Muster ohne Zeilenanker
# auffaellt.
#
# Dazu traegt die Prosa Zeilen, die MIT dem Anfang einer Prueffrage BEGINNEN,
# ohne die Frage zu sein — je eine fuer jeden Fragenanfang: "Schreibt",
# "Prueft", "Welche" (Eigenschaft / reale / Projektnummer), "Waehlt", "Gilt",
# "Ist jede", "Welchen", "Zaehlt". Ohne sie ueberlebte ein verkuerztes
# Fragen-Muster die Probe: Keine Prosazeile begann so, also war ein Muster aus
# dem ersten Wort so gut wie das volle (gemessen, v1.15.2 — sechs
# Verkuerzungen von zwei Pruefern, vier weitere beim Nachmessen). Diese Zeilen
# duerfen die VOLLEN Muster nicht treffen, nur die verkuerzten; wer eine Frage
# aendert, prueft das hier nach (Mutation: Muster auf das ERSTE WORT kuerzen,
# die Probe muss rot werden). Die Zweiwort-Kuerzung reicht als Mutation NICHT:
# gemessen (je elf Kuerzungen, debian:bookworm-slim) faengt die Probe sie nur
# bei Frage 6, 9 und 10 — dort teilen die Prosazeilen oben die ersten ZWEI
# Woerter. Bei den uebrigen sechs dreiwortigen Mustern teilen sie nur das
# erste, deshalb bleibt die Zweiwort-Kuerzung dort gruen.
# Frage 3 und 11 haben nur zwei Woerter — dort ist die Zweiwort-Kuerzung gar
# keine. Die Einwort-Kuerzung ist bei allen elf rot.
cat > "$T/b0" <<'EOF'
# Bau-Brief: Exportknopf fuer die Kundenliste

## 0 Risiko
**Risiko:** **R2** — Auslöser: Normalfall, gegen die Auslöser-Tabelle geprüft.
Basis: Repo /srv/beispiel, Zweig main, erwarteter Commit 1a2b3c4.
Die Produktion läuft nachts; das Produkt-Team hat seine Wünsche gesammelt.
Schreibt der Knopf eine zweite Datei, wächst die Ablage.

EOF
cat > "$T/b1" <<'EOF'
## 1 Auftrag
Issue 12: Die Kundenliste bekommt einen Knopf, der die Liste als CSV liefert.
Abnahme:
- CSV enthält alle Spalten der Liste — je Punkt womit belegt: Testausgabe.
Zum Umfang: Die Dokumentation erklärt seinem Team den Knopf; die Behauptung
im Issue ist wahr, und die Eigenschaft der Liste bleibt.
Prüft der Nachtlauf die Spaltenbreite, bleibt seine Antwort gleich.

EOF
cat > "$T/b2" <<'EOF'
## 2 Befund
Bereits verifiziert: `liste.py:40` sortiert nach Name; `export.py` fehlt noch.
Gemessen am Test von gestern: Die Zahl ist nicht erfunden, sondern belegt;
eine Eigenschaft der Produktion bleibt wahr, seine Grenze auch.
Gilt der Rabatt noch, zeigt die Liste ihn in Klammern.

EOF
cat > "$T/b3" <<'EOF'
## 3 Konsumenten
Die Listenansicht und die Schnittstelle /kunden; niemand sonst.
Offen ist nur, welchen Pfad benutzt die Nachtschicht im Produkt-Frontend;
die Behauptung dazu steht im Issue und ist belegt.
Wählt der Nutzer die Kurzform, bleibt die Spaltenfolge erhalten.

EOF
cat > "$T/b4" <<'EOF'
## 4 Sichtbares
Neuer Knopf in der Oberfläche; Handbuch-Abschnitt „Kundenliste" ergänzen.
Seine Dokumentation wächst im selben Issue; das Produkt behält jede Eigenschaft.
Zählt die Liste ihre Zeilen selbst, stimmt die Fußzeile.

EOF
cat > "$T/b5" <<'EOF'
## 5 Nachweis
Rot-Beweis: Spalte im Export auskommentieren, Test wird rot; Gegenprobe grün.
Gemessen am Produktionsabzug; jeder Test ist belegt, nichts ist erfunden.
Welchen Namen die Spalte trägt, entscheidet der Kopfsatz.

EOF
cat > "$T/b6" <<'EOF'
## 6 Prüf-Kommandos
pytest -q
Der Umfang der Tests ist gemessen und belegt; seine Laufzeit steht im Issue.
Ist jede Spalte gefüllt, bleibt die Sortierung stabil.
Welche realen Namen die Liste zeigt, steht in der Fußnote.
Welche Projektnummer die Liste führt, entscheidet der Kopfsatz.

EOF
cat > "$T/b7" <<'EOF'
## 7 Fixtures
Erfundene Kunden „Anna Beispiel" und „Otto Muster".
Keine Behauptung über die echte Produktion; wahr sein muss nur der Test.
Welche Eigenschaft der Liste bleibt, steht im Issue.

EOF
{
  printf '%s\n' "## 8 Randbedingungen" "Im Vordergrund, lokal committen, nicht pushen."
  cat "$T/randbedingungen"
  printf '%s\n' "Der Umfang bleibt, seine Grenzen sind belegt und gemessen." ""
} > "$T/b8"
printf '%s\n' "## 9 Prüffragen" > "$T/b9kopf"

THEMEN="Risiko Auftrag Befund Konsumenten Sichtbares Nachweis Kommandos Fixtures Randbedingungen Prüffragen"

# brief <ziel> <fragendatei> <ausgelassener block oder -1>
# Ein cat-Aufruf je Brief: Unter Git Bash kostet jeder Prozessstart um 45 ms.
# "$T/fallen" haengt an JEDEM Brief, auch am Brief ohne Block k: Die Fallen
# werden woertlich kopiert, also muss ein fehlendes Thema TROTZ ihnen gemeldet
# werden (gemessen bis v1.15.2: eine einzige kopierte Falle hielt Sichtbares,
# Nachweis oder Fixtures gruen).
brief() {
  set --  "$1" "$2" "$3" "$T/b0" "$T/b1" "$T/b2" "$T/b3" "$T/b4" "$T/b5" "$T/b6" "$T/b7" "$T/b8" "$T/b9kopf" "$2"
  ZIEL=$1
  AUSLASSEN=$3
  shift 3
  BI=0
  for DATEI in "$@"; do
    shift
    if [ "$BI" != "$AUSLASSEN" ] && ! { [ "$AUSLASSEN" = 9 ] && [ "$BI" -ge 9 ]; }; then
      set -- "$@" "$DATEI"
    fi
    BI=$((BI + 1))
  done
  cat "$@" "$T/fallen" > "$ZIEL"
}

# kodieren <quelle> <art> <ziel>; Rueckgabe 1 = Art nicht verfuegbar
kodieren() {
  case "$2" in
    utf8) cp "$1" "$3" ;;
    crlf) CR=$(printf '\r'); sed "s/\$/$CR/" "$1" > "$3" ;;
    cp1252)
      command -v iconv > /dev/null 2>&1 || return 1
      iconv -c -f UTF-8 -t CP1252 "$1" > "$3" 2> /dev/null
      [ -s "$3" ] || return 1
      ;;
  esac
  return 0
}

laufen() { # <brief> -> $RC, Ausgabe in $T/aus
  LAEUFE=$((LAEUFE + 1))
  sh "$SKRIPT" "$1" > "$T/aus" 2>&1
  RC=$?
}

# gemeldete Themen (Name je Zeile) aus [KEIN TREFFER]- und [UNVOLLSTAENDIG]-Zeilen
gemeldet() {
  sed -n -E 's/^  \[(KEIN TREFFER|UNVOLLSTAENDIG)\] *([^ :(]*).*$/\2/p' "$T/aus"
}

CP1252_DA=1
command -v iconv > /dev/null 2>&1 || { CP1252_DA=0; echo "HINWEIS: iconv fehlt — CP1252-Teil uebersprungen."; }

# --- 3. Vollstaendiger Brief und Leave-one-out je Thema ---------------------
for VAR in $VARIANTEN; do
  for ART in utf8 cp1252 crlf; do
    [ "$ART" = cp1252 ] && [ "$CP1252_DA" = 0 ] && continue
    brief "$T/roh" "$T/$VAR" -1
    kodieren "$T/roh" "$ART" "$T/brief.md" || { rot "$VAR/$ART: Kodierung fehlgeschlagen"; continue; }
    laufen "$T/brief.md"
    if [ "$RC" -ne 0 ]; then
      rot "$VAR/$ART: vollstaendiger Brief gibt Exit $RC statt 0; gemeldet: $(gemeldet)"
    fi
    I=0
    for THEMA in $THEMEN; do
      brief "$T/roh" "$T/$VAR" "$I"
      kodieren "$T/roh" "$ART" "$T/brief.md"
      laufen "$T/brief.md"
      G=$(gemeldet)
      if [ "$RC" -ne 1 ] || [ "$G" != "$THEMA" ]; then
        rot "$VAR/$ART: ohne Block $I ($THEMA) Exit $RC, gemeldet: '${G}' — erwartet Exit 1 und genau '$THEMA'"
      fi
      I=$((I + 1))
    done
  done
done

# --- 4. Prueffragen: je Frage weglassen, je Kodierung -----------------------
for ART in $FRAGEN_ARTEN; do
  [ "$ART" = cp1252 ] && [ "$CP1252_DA" = 0 ] && continue
  for VAR in fett voll einzeilig; do
    NR=1
    while [ "$NR" -le "$N" ]; do
      # Frage NR (mit ihren Folgezeilen) aus der Fragendatei entfernen
      NAECHSTE=$((NR + 1))
      sed "/^$NR\. \*\*/,/^$NAECHSTE\. \*\*/{ /^$NAECHSTE\. \*\*/!d; }" "$T/$VAR" > "$T/ohne"
      brief "$T/roh" "$T/ohne" -1
      kodieren "$T/roh" "$ART" "$T/brief.md" || { rot "fragen/$ART: Kodierung fehlgeschlagen"; break; }
      laufen "$T/brief.md"
      if [ "$RC" -ne 1 ] || ! grep -qE "^  \[UNVOLLSTAENDIG\] Pr[^ ]*: $((N - 1)) von $N .*fehlt: $NR\$" "$T/aus"; then
        rot "$VAR/$ART: ohne Frage $NR Exit $RC, Zeile: '$(grep -E 'Pr[^ ]*ffragen' "$T/aus")' — erwartet Exit 1 und '$((N - 1)) von $N … fehlt: $NR'"
      fi
      NR=$NAECHSTE
    done
  done

  # --- 5. Nur eine zitierte Frage (Frage 2) ---------------------------------
  # Erwartet werden alle Nummern ausser der 2 — auch eine projekteigene.
  OHNE2=""
  NR=1
  while [ "$NR" -le "$N" ]; do
    [ "$NR" = 2 ] || OHNE2="$OHNE2 $NR"
    NR=$((NR + 1))
  done
  grep -E '^2\. \*\*' "$T/fett" > "$T/eine"
  brief "$T/roh" "$T/eine" -1
  kodieren "$T/roh" "$ART" "$T/brief.md"
  laufen "$T/brief.md"
  if [ "$RC" -ne 1 ] || ! grep -qE "^  \[UNVOLLSTAENDIG\] Pr[^ ]*: 1 von $N .*fehlt:$OHNE2\$" "$T/aus"; then
    rot "$ART: nur Frage 2 zitiert: Exit $RC, Prueffragen nicht als '1 von $N, fehlt:$OHNE2' gemeldet"
  fi
done

echo
if [ "$ROT" -gt 0 ]; then
  echo "Selbstprobe ROT: $ROT Abweichung(en) in $LAEUFE Laeufen."
  exit 1
fi
GEPRUEFT=""
KODS="UTF-8, CP1252, CRLF"
[ "$CP1252_DA" = 1 ] || { KODS="UTF-8, CRLF"; FRAGEN_ARTEN=$(printf '%s' "$FRAGEN_ARTEN" | sed 's/ cp1252//g'); }
[ -n "$VARIANTEN" ] && GEPRUEFT="jedes fehlende Thema (Fragen-Varianten:$VARIANTEN; $KODS)"
[ -n "$FRAGEN_ARTEN" ] && GEPRUEFT="$GEPRUEFT${GEPRUEFT:+ und }jede fehlende Frage (Kodierungen:$FRAGEN_ARTEN)"
echo "Selbstprobe gruen: $LAEUFE Laeufe. Gegen den eingebauten Muster-Brief (Pflichttexte aus bau-brief.md und Alltagsprosa) gemeldet: $GEPRUEFT."
echo "Nicht geprueft: andere Briefe; nicht gewaehlte Teile."
exit 0
