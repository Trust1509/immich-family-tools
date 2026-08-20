#!/bin/sh
# Prueft, ob ein Bau-Brief alle Pflicht-Bloecke traegt.
#
#   sh scripts/bau-brief-pruefen.sh <brief.md>
#
# WARUM ES DAS GIBT
# -----------------
# Der Bau-Brief ist die einzige Leitplanke, die den Bauer erreicht. Regeln im
# Repo erreichen ihn nicht — ein Bau-Subagent arbeitet den Brief ab, nicht
# docs/agents/. In fuenf Projekten gemeldet; zweimal ist genau daran eine
# Pflichtregel gescheitert: Sie stand im Repo und fehlte im Brief.
#
# Eine Regel, die nur als Text existiert, haengt an einem Menschen, der beim
# Kopieren nichts vergisst. Dieses Skript macht das Fehlen sichtbar.
#
# Es prueft die ANWESENHEIT der Bloecke, nicht ihre Qualitaet — einen leeren
# Block erkennt es, einen schlecht ausgefuellten nicht. Das ist Absicht: Es
# ersetzt das Nachdenken nicht, es faengt das Vergessen.
set -e

BRIEF="$1"
[ -n "$BRIEF" ] || { echo "Aufruf: sh scripts/bau-brief-pruefen.sh <brief.md>"; exit 2; }
[ -f "$BRIEF" ] || { echo "Nicht gefunden: $BRIEF"; exit 2; }

# Blocknummer|Kurzname|Suchmuster (case-insensitive)
BLOECKE="1|Auftrag|auftrag
2|Befund|befund
3|Konsumenten|konsument
4|Sichtbares|sichtbar
5|Nachweis|nachweis|rot-beweis
6|Kommandos|kommando|pruef|prüf
7|Fixtures|fixture
8|Randbedingungen|randbedingung"

FEHLT=0
LEER=0
echo "Bau-Brief: $BRIEF"
echo

OLDIFS=$IFS
IFS='
'
for Z in $BLOECKE; do
  NR=$(echo "$Z" | cut -d'|' -f1)
  NAME=$(echo "$Z" | cut -d'|' -f2)
  MUSTER=$(echo "$Z" | cut -d'|' -f3-)

  ZEILE=$(grep -n -i -E "^#+ *$NR\b|^#+ .*($MUSTER)" "$BRIEF" | head -1 | cut -d: -f1 || true)
  if [ -z "$ZEILE" ]; then
    printf '  [FEHLT]  %s %s\n' "$NR" "$NAME"
    FEHLT=$((FEHLT + 1))
    continue
  fi

  # Inhalt bis zur naechsten Ueberschrift: mindestens eine nicht-leere Zeile?
  INHALT=$(sed -n "$((ZEILE + 1)),\$p" "$BRIEF" | sed -n '/^#\{1,\} /q;p' | grep -c '[^[:space:]]' || true)
  if [ "$INHALT" -eq 0 ]; then
    printf '  [LEER]   %s %s  (Zeile %s)\n' "$NR" "$NAME" "$ZEILE"
    LEER=$((LEER + 1))
  else
    printf '  ok       %s %s\n' "$NR" "$NAME"
  fi
done
IFS=$OLDIFS

echo
# Bewegungsverbote: der Brief liefert Befunde, keine gesperrten Zonen.
VERBOTE=$(grep -n -i -E "nicht anfassen|nicht ändern|nicht aendern|finger weg|tabu" "$BRIEF" || true)
if [ -n "$VERBOTE" ]; then
  echo "HINWEIS — moegliches Bewegungsverbot im Brief:"
  echo "$VERBOTE" | sed 's/^/    /'
  echo "  Ein Brief liefert Befunde, keine gesperrten Zonen. Real passiert: Das"
  echo "  Verbot lag genau auf der Ein-Zeilen-Behebung eines Panel-Funds."
  echo
fi

if [ "$FEHLT" -gt 0 ] || [ "$LEER" -gt 0 ]; then
  echo "NICHT FERTIG: $FEHLT Block/Bloecke fehlen, $LEER leer."
  echo "Ein unvollstaendiger Brief erreicht den Bauer trotzdem — nur ohne die Regel."
  exit 1
fi

echo "Alle acht Bloecke vorhanden und gefuellt."
echo "Geprueft ist damit die Anwesenheit, nicht die Qualitaet."
exit 0
