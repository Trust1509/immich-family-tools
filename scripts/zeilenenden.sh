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
# Exit 0: alles LF. Exit 1: Befund, mit Liste. Exit 2: kein Git-Repo.
set -eu

git rev-parse --git-dir >/dev/null 2>&1 || { echo "zeilenenden: kein Git-Repo"; exit 2; }
cd "$(git rev-parse --show-toplevel)"

# `check-attr` gibt je Datei eine Zeile "<pfad>: eol: <wert>". Alles ausser
# "lf" ist ein Befund — auch "unspecified" (Regel fehlt) und "unset" (`-eol`).
falsches_attribut=$(git ls-files | git check-attr --stdin eol | grep -v ': eol: lf$' || true)

# `ls-files --eol`: erste Spalte ist der Index. `i/crlf` und `i/mixed` sind
# Befunde; `i/-text` (Binaerdatei) und `i/none` (leer) nicht.
crlf_im_index=$(git ls-files --eol | awk '$1 == "i/crlf" || $1 == "i/mixed"')

if [ -n "$falsches_attribut" ] || [ -n "$crlf_im_index" ]; then
  if [ -n "$falsches_attribut" ]; then
    echo "zeilenenden: Dateien ohne eol=lf (.gitattributes pruefen):"
    echo "$falsches_attribut"
  fi
  if [ -n "$crlf_im_index" ]; then
    echo "zeilenenden: Blobs mit CRLF im Index (git add --renormalize .):"
    echo "$crlf_im_index"
  fi
  exit 1
fi
echo "zeilenenden: $(git ls-files | wc -l | tr -d ' ') Dateien, alle eol=lf, kein CRLF im Index"
