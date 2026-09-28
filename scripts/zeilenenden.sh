#!/bin/sh
# Waechter fuer die Zeilenenden (#104).
#
# WAS ER PRUEFT: dass `.gitattributes` fuer JEDE versionierte Datei `eol=lf`
# setzt und dass kein Blob im Index CRLF oder gemischte Zeilenenden traegt.
#
# WARUM ES IHN GIBT: Das Ziel von #104 — der Arbeitsbaum traegt auch unter
# `core.autocrlf=true` LF, damit `npx prettier --check .` lokal verwertbar ist
# — laesst sich in der CI selbst nicht beobachten: Der Linux-Laeufer checkt
# ohnehin LF aus, sein Prettier-Lauf bleibt gruen, auch wenn die Regel weg ist.
# Gemessen von der blinden Erststimme: Regel geloescht, `*.md -eol` als
# spaetere Zeile oder eine verschachtelte `frontend/.gitattributes` mit
# `eol=crlf` — nichts im Repo merkte es. Dieser Waechter fragt deshalb die
# ATTRIBUTE ab (`git check-attr`), nicht den Arbeitsbaum, und dazu den Index
# (`git ls-files --eol`), weil `text=auto` einen Blob, der schon CRLF traegt,
# nicht normalisiert.
#
# ZWEIMAL, mit und ohne `core.ignorecase`: Unter Windows (ignorecase=true)
# vergleicht git die Muster in `.gitattributes` ohne Ruecksicht auf Gross-/
# Kleinschreibung, unter Linux mit. Eine Zeile `*.MD eol=crlf` bringt dem
# Windows-Arbeitsplatz CRLF, waehrend ein Lauf nur mit den Linux-Regeln gruen
# bleibt (gemessen von der blinden Stimme zu Nacharbeit 1).
#
# BEKANNTE GRENZEN (gemessen, nicht bewacht): Ein Blob mit einem EINZELNEN CR
# gilt git als binaer (`i/-text`) und faellt hier heraus; `* -text` hebt die
# Umwandlung ganz auf, `check-attr eol` bleibt dabei `lf`.
#
# AUSNAHMEN: Eine Datei, die absichtlich CRLF traegt (etwa eine `.bat` mit
# `eol=crlf` oder eine byte-genaue Testdatei mit `-text`), steht mit Pfad und
# Grund in AUSNAHMEN — sonst waere der einzige Ausweg, die Regel zu loeschen.
# Heute: keine.
AUSNAHMEN=""
#
# Exit 0: alles LF. Exit 1: Befund, mit Liste. Exit 2: kein Arbeitsbaum eines
# Git-Repos (auch: bare, innerhalb von .git).
set -eu

oben=$(git rev-parse --show-toplevel 2>/dev/null) || oben=""
[ -n "$oben" ] || { echo "zeilenenden: kein Arbeitsbaum eines Git-Repos"; exit 2; }
cd "$oben"

ausgenommen() {
  for a in $AUSNAHMEN; do [ "$1" = "$a" ] && return 0; done
  return 1
}

# Erst die Dateiliste, getrennt: Scheitert `git ls-files`, bricht `set -e` hier
# ab, statt dass eine leere Pipe als "alles gruen" durchgeht.
dateien=$(git ls-files)
if [ -z "$dateien" ]; then echo "zeilenenden: 0 Dateien"; exit 0; fi

# `check-attr` gibt je Datei eine Zeile "<pfad>: eol: <wert>". Alles ausser
# "lf" ist ein Befund — auch "unspecified" (Regel fehlt), "unset" (`-eol`),
# "set" (`eol` ohne Wert) und "LF" (Wert in Grossbuchstaben).
attr_linux=$(printf '%s\n' "$dateien" | git -c core.ignorecase=false check-attr --stdin eol)
attr_windows=$(printf '%s\n' "$dateien" | git -c core.ignorecase=true check-attr --stdin eol)
falsches_attribut=$(printf '%s\n%s\n' "$attr_linux" "$attr_windows" | grep -v ': eol: lf$' | sort -u || true)

# `ls-files --eol`: erste Spalte ist der Index. `i/crlf` und `i/mixed` sind
# Befunde; `i/-text` (Binaerdatei) und `i/none` (leer) nicht.
eol_liste=$(git ls-files --eol)
crlf_im_index=$(printf '%s\n' "$eol_liste" | awk '$1 == "i/crlf" || $1 == "i/mixed"')

befund_attr=""
if [ -n "$falsches_attribut" ]; then
  befund_attr=$(printf '%s\n' "$falsches_attribut" | while IFS= read -r z; do
    ausgenommen "${z%: eol: *}" || printf '%s\n' "$z"; done)
fi
befund_index=""
if [ -n "$crlf_im_index" ]; then
  befund_index=$(printf '%s\n' "$crlf_im_index" | while IFS= read -r z; do
    ausgenommen "$(printf '%s' "$z" | cut -f2)" || printf '%s\n' "$z"; done)
fi

if [ -n "$befund_attr" ] || [ -n "$befund_index" ]; then
  if [ -n "$befund_attr" ]; then
    echo "zeilenenden: Dateien ohne eol=lf (.gitattributes pruefen; absichtlich CRLF -> AUSNAHMEN in scripts/zeilenenden.sh):"
    printf '%s\n' "$befund_attr"
  fi
  if [ -n "$befund_index" ]; then
    echo "zeilenenden: Blobs mit CRLF im Index (git add --renormalize . ; absichtlich CRLF -> AUSNAHMEN):"
    printf '%s\n' "$befund_index"
  fi
  exit 1
fi
echo "zeilenenden: $(printf '%s\n' "$dateien" | grep -c .) Dateien, alle eol=lf, kein CRLF im Index"
