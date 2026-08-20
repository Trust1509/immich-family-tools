#!/bin/sh
# Sucht die acht Pflicht-Themen in einem Bau-Brief.
#
#   sh scripts/bau-brief-pruefen.sh <brief.md>
#
# WAS DIESES SKRIPT MISST — UND WAS NICHT
# ---------------------------------------
# Es misst, ob jedes der acht Pflicht-Themen im Brief VORKOMMT. Mehr nicht.
#
# Es kann NICHT beurteilen, ob ein Thema tragfaehig behandelt ist. Acht
# Ueberschriften mit je einem Fuellwort besteht es. Wer aus einem gruenen Lauf
# "der Brief ist fertig" liest, macht genau den Fehler, den lehren.md §5
# beschreibt: das Vorhandensein einer Pruefung mit ihrem Bestehen verwechseln.
#
# Die erste Fassung (v1.8.0) hat genau das getan — sie suchte nur
# UEBERSCHRIFTEN und faellte darauf ein Urteil ueber Vollstaendigkeit. Ein
# Brief, der alle acht Themen als Aufzaehlung unter einer gemeinsamen
# Ueberschrift trug und vom Bauer befolgt wurde, fiel durch. Gemeldet aus einem
# Projekt, das die Fassung rueckwirkend auf drei echte Briefe angewandt hat.
#
# Deshalb sucht diese Fassung im GANZEN Dokument, nicht nur in Ueberschriften,
# und sagt im Ergebnis, was sie geprueft hat.
set -e

BRIEF="$1"
[ -n "$BRIEF" ] || { echo "Aufruf: sh scripts/bau-brief-pruefen.sh <brief.md>"; exit 2; }
[ -f "$BRIEF" ] || { echo "Nicht gefunden: $BRIEF"; exit 2; }

# Thema|Suchmuster (erweiterte Regex, case-insensitive, ganzes Dokument)
THEMEN="Auftrag|auftrag|zu bauen|gebaut wird
Befund|befund|verifiziert|festgestellt
Konsumenten|konsument|ruft .* auf|aufrufer|caller
Sichtbares|sichtbar|verhalten aender|verhalten änder|doku|handbuch
Nachweis|rot-beweis|rotbeweis|sabotier|mutation
Kommandos|gates\.sh|pytest|npm |tsc|pruef-kommando|prüf-kommando|kommando
Fixtures|fixture|testdaten|seed
Randbedingungen|randbedingung|nicht pushen|vordergrund|umfang"

FEHLT=0
GEFUNDEN=0
echo "Bau-Brief: $BRIEF"
echo "Geprueft wird: kommt jedes Pflicht-Thema vor? (nicht: ist es gut behandelt)"
echo

OLDIFS=$IFS
IFS='
'
for Z in $THEMEN; do
  NAME=$(echo "$Z" | cut -d'|' -f1)
  MUSTER=$(echo "$Z" | cut -d'|' -f2-)
  TREFFER=$(grep -n -i -E "$MUSTER" "$BRIEF" | head -1 || true)
  if [ -z "$TREFFER" ]; then
    printf '  [FEHLT]  %-16s\n' "$NAME"
    FEHLT=$((FEHLT + 1))
  else
    ZL=$(echo "$TREFFER" | cut -d: -f1)
    printf '  gefunden %-16s Zeile %s\n' "$NAME" "$ZL"
    GEFUNDEN=$((GEFUNDEN + 1))
  fi
done
IFS=$OLDIFS

echo
VERBOTE=$(grep -n -i -E "nicht anfassen|nicht ändern|nicht aendern|finger weg|tabu" "$BRIEF" || true)
if [ -n "$VERBOTE" ]; then
  echo "HINWEIS — pruefe, ob das eine UMFANGSGRENZE oder ein URTEIL ist:"
  echo "$VERBOTE" | sed 's/^/    /'
  echo "  Grenze aus Umfang/Rechten (\"ausserhalb dieses Slices\", \"kein Token-Scope\")"
  echo "  ist legitim und gehoert in Block 8. Verbot aus URTEIL (\"das ist ok, sieh"
  echo "  nicht hin\") ist schaedlich — real lag so ein Verbot genau auf der"
  echo "  Ein-Zeilen-Behebung eines Panel-Funds."
  echo
fi

if [ "$FEHLT" -gt 0 ]; then
  echo "$FEHLT von 8 Themen kommen im Brief NICHT vor."
  echo "Das ist ein Fund, kein Urteil: Pruefe, ob das Thema hier gegenstandslos"
  echo "ist (dann eine Zeile Begruendung in den Brief) oder vergessen wurde."
  exit 1
fi

echo "Alle 8 Themen kommen vor."
echo "NICHT geprueft: ob sie tragfaehig behandelt sind. Das bleibt Kopfarbeit —"
echo "insbesondere Block 3 (wer ruft den geaenderten Code auf) und Block 5"
echo "(Rot-Beweis inkl. Verdrahtung)."
exit 0
