#!/bin/sh
# Zeigt, WO in einem Bau-Brief die zehn Pflicht-Themen behandelt sein koennten.
#
#   sh scripts/bau-brief-pruefen.sh <brief.md>
#
# DAS TRAGENDE PRINZIP: DIE ASYMMETRIE
# ------------------------------------
#   KEIN Treffer  -> belastbar NUR bei Einzelwort-Mustern. grep arbeitet
#                    zeilenweise: Eine Wortgruppe, die ueber einen Umbruch
#                    faellt, liefert null Treffer, obwohl sie dasteht
#                    (gemessen an umbrochener Markdown-Prosa, 08/2026).
#                    Einzelwoerter koennen nicht umbrochen werden.
#                    UND: wer diesem Skript eine eigene Suche zur Seite
#                    stellt, setzt LC_ALL=C.UTF-8 davor — ohne Locale faltet
#                    "grep -i" keine Umlaute (gemessen: 1 von 2 Zeilen), und
#                    zwar nur bei Nicht-ASCII, also ausgerechnet bei den
#                    deutschen Fachwoertern.
#   EIN Treffer   -> unbelastbar. Es kann Behandlung sein, Erwaehnung,
#                    Verneinung, Nachbarwort oder wiederverwendete Floskel.
#
# Deshalb behauptet dieses Skript kein "vorhanden" mehr. Es nennt Kandidaten
# MIT der Fundzeile, damit du in Sekunden urteilst statt den ganzen Brief zu
# lesen. Der Exit-Code faellt nur, wenn ein Thema NIRGENDS vorkommt — das ist
# die einzige Richtung, in der eine Textsuche belastbar ist.
#
# WAS ES NICHT KANN (gemessen, nicht vermutet — aus fuenf Projekten)
# -------------------------------------------------------------------
# * VERNEINUNGEN nicht von Behandlung unterscheiden. "Einen Rot-Beweis
#   brauchst du hier eher nicht" traf als Thema "Nachweis". Schlimmer: Bei
#   "Fixtures" traf ausgerechnet die Zeile, die die Regel VERLETZT ("nimm die
#   Testdaten aus dem, was da ist"). Kandidaten mit Verneinungswort werden
#   deshalb markiert — als Hinweis, nicht als Urteil.
# * NACHBARWOERTER in deutscher Prosa: "doku" trifft "dokumentieren", ein
#   Dateipfad in einer Beschreibung trifft wie ein auszufuehrendes Kommando.
# * MEHRWORTIGE Muster am ZEILENUMBRUCH: mehrere THEMEN-Muster unten sind
#   zweiwortig ("sichtbares verhalten", "ruft .* auf") — in einem Brief mit
#   harten Umbruechen koennen sie durchfallen. Die Einzelwort-Alternativen
#   je Zeile fangen das meist; wer einem [KEIN TREFFER] misstraut, sucht das
#   seltenste EINZELWORT nach.
# * FLOSKELN von slice-spezifischer Behandlung unterscheiden. Eine
#   Standard-Regelzeile ("Fixtures erfunden, Rot-Beweis je Test, Gates im
#   Vordergrund") saettigt drei Themen auf einmal, ohne dass eines fuer DIESEN
#   Slice durchdacht waere. Jede Verschaerfung dagegen liefe wieder auf
#   Gliederungs-Urteile hinaus — deshalb bleibt es hier stehen statt behoben
#   zu werden.
#
# Ein sauberer Lauf heisst: "nichts vergessen". Nicht: "Brief ist gut".
set -e

BRIEF="$1"
[ -n "$BRIEF" ] || { echo "Aufruf: sh scripts/bau-brief-pruefen.sh <brief.md>"; exit 2; }
[ -f "$BRIEF" ] || { echo "Nicht gefunden: $BRIEF"; exit 2; }

# Thema|Suchmuster (erweiterte Regex, case-insensitive, ganzes Dokument)
THEMEN="Risiko|risiko: r[0-9]|risiko r[0-9]
Auftrag|auftrag|zu bauen|gebaut wird|umzusetzen
Befund|befund|beleg|verifiziert|festgestellt|gemessen|ausgangslage
Konsumenten|konsument|ruft .* auf|aufrufer|caller|wer ruft
Sichtbares|sichtbares verhalten|verhalten aender|verhalten änder|handbuch|nutzer-doku|sichtbar
Nachweis|rot-beweis|rotbeweis|sabotier|mutation|nachweis
Kommandos|gates\.sh|pytest|npm |tsc|prüf-kommando|pruef-kommando
Fixtures|fixture|testdaten|seed
Randbedingungen|randbedingung|nicht pushen|vordergrund|leitplanke
Prüffragen|prüffrage|prueffrage|welchen pfad|wahr bleiben|zweck-identität"

VERNEINUNG="nicht|kein|entfäll|entfall|braucht.*nicht|erübrigt|weiss ich nicht|weiß ich nicht"

OHNE=0
echo "Bau-Brief: $BRIEF"
echo "Kein Treffer ist belastbar. Ein Treffer ist ein KANDIDAT — bitte lesen."
echo

OLDIFS=$IFS
IFS='
'
for Z in $THEMEN; do
  NAME=$(echo "$Z" | cut -d'|' -f1)
  MUSTER=$(echo "$Z" | cut -d'|' -f2-)
  TREFFER=$(grep -n -i -E "$MUSTER" "$BRIEF" | head -2 || true)

  if [ -z "$TREFFER" ]; then
    printf '  [KEIN TREFFER]  %s\n' "$NAME"
    OHNE=$((OHNE + 1))
    continue
  fi

  printf '  Kandidat        %s\n' "$NAME"
  echo "$TREFFER" | while IFS= read -r T; do
    ZL=$(echo "$T" | cut -d: -f1)
    TXT=$(echo "$T" | cut -d: -f2- | sed 's/^[[:space:]]*//' | cut -c1-88)
    if echo "$TXT" | grep -qiE "$VERNEINUNG"; then
      printf '      Z%-5s %s\n' "$ZL" "$TXT"
      printf '            ^ enthaelt ein Verneinungswort — behandelt der Satz das Thema\n'
      printf '              oder BESTELLT er es ab?\n'
    else
      printf '      Z%-5s %s\n' "$ZL" "$TXT"
    fi
  done
done
IFS=$OLDIFS

echo
VERBOTE=$(grep -n -i -E "nicht anfassen|nicht ändern|nicht aendern|finger weg|tabu" "$BRIEF" || true)
if [ -n "$VERBOTE" ]; then
  echo "HINWEIS — pruefe, ob das eine UMFANGSGRENZE oder ein URTEIL ist:"
  echo "$VERBOTE" | sed 's/^/    /'
  echo "  Grenze aus Umfang/Rechten ist legitim und gehoert in Block 8."
  echo "  Verbot aus URTEIL (\"das ist ok, sieh nicht hin\") ist schaedlich."
  echo
fi

if [ "$OHNE" -gt 0 ]; then
  echo "$OHNE von 10 Themen kommen im Brief NIRGENDS vor."
  echo "Das ist der belastbare Teil dieser Pruefung: entweder gegenstandslos"
  echo "(dann eine Zeile Begruendung in den Brief) oder vergessen."
  exit 1
fi

echo "Zu allen 10 Themen gibt es Kandidaten."
echo "Ob sie das Thema BEHANDELN, entscheidest du an den Zeilen oben —"
echo "das Skript kann Erwaehnung, Verneinung und Floskel nicht unterscheiden."
exit 0
