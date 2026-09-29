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
# bleibt (gemessen von der blinden Stimme zu Nacharbeit 1). Die Richtung gilt
# auch umgekehrt: Eine spaetere, case-insensitiv passende Regel kann unter
# ignorecase=true eine fruehere, exakt passende Regel verdecken — dort faengt
# NUR die Linux-Pruefung (ignorecase=false) den Befund (gemessen zu #118,
# Selbstprobe Fall 17).
#
# BEKANNTE GRENZEN (gemessen, nicht bewacht): Ein Blob mit einem EINZELNEN CR
# gilt git als binaer (`i/-text`) und faellt hier heraus; `* -text` hebt die
# Umwandlung ganz auf, `check-attr eol` bleibt dabei `lf`.
#
# AUSNAHMEN: zeilenweise in `scripts/zeilenenden-ausnahmen.txt` IM GEPRUEFTEN
# REPO (relativ zum Arbeitsbaum-Toplevel, nicht neben diesem Skript-File --
# die Selbstprobe prueft viele verschiedene Wegwerf-Repos gegen denselben
# Skript-Text und darf dabei nie die Ausnahmedatei DIESES Projekts lesen),
# je Zeile `<Pfad><TAB><erlaubter Wert>` (Wert z. B. `crlf` -- der Wert, den
# `check-attr`/`ls-files --eol` fuer GENAU diesen Pfad melden soll, nicht
# "alles ausser lf"). Der Pfad wird exakt und wortwoertlich verglichen (kein
# Glob, kein Praefix-, kein Muster-Vergleich). Ein eingetragener Pfad, der
# nicht mehr versioniert ist, ist selbst ein Befund (veraltete Ausnahme).
# Heute: keine.
#
# #118 loeste damit den frueheren Mechanismus ab (Nacharbeit zu #104):
# `for a in $AUSNAHMEN` wertete die ungequotete Variable als Glob aus (`"*
# */* */*/*"` gab alles frei), konnte keinen Pfad mit Leerzeichen ausnehmen,
# und liess "alles ausser lf" durch statt eines konkreten Werts.
#
# Exit 0: alles LF. Exit 1: Befund, mit Liste. Exit 2: kein Arbeitsbaum eines
# Git-Repos (auch: bare, innerhalb von .git).
set -eu

oben=$(git rev-parse --show-toplevel 2>/dev/null) || oben=""
[ -n "$oben" ] || { echo "zeilenenden: kein Arbeitsbaum eines Git-Repos"; exit 2; }
cd "$oben"

# Die Ausnahmedatei liegt IM GEPRUEFTEN REPO (siehe Kopf), nicht neben diesem
# Skript-File: Die Selbstprobe ruft diesen Text gegen viele verschiedene
# Wegwerf-Repos auf und legt dort bei Bedarf ihre eigene Ausnahmedatei an
# (siehe zeilenenden-selbstprobe.sh, Fall 15) -- ohne die echte
# scripts/zeilenenden-ausnahmen.txt dieses Projekts je zu beruehren oder von
# ihr beeinflusst zu werden.
ausnahmen_datei="scripts/zeilenenden-ausnahmen.txt"

# Gibt fuer Pfad $1 den erlaubten Wert aus der Ausnahmedatei aus (Exit 0),
# oder nichts mit Exit 1, wenn $1 dort nicht eingetragen ist. Zeilenweise,
# exakter String-Vergleich ("[" "="  ist keine Muster-, sondern eine reine
# Textprobe) -- kein Glob, kein Praefix-Vergleich, kein `case`-Muster.
ausnahme_wert() {
  [ -f "$ausnahmen_datei" ] || return 1
  while IFS= read -r zeile || [ -n "$zeile" ]; do
    case "$zeile" in
      ''|'#'*) continue ;;
    esac
    pfad=$(printf '%s\n' "$zeile" | cut -f1)
    wert=$(printf '%s\n' "$zeile" | cut -f2)
    if [ "$1" = "$pfad" ]; then
      printf '%s' "$wert"
      return 0
    fi
  done < "$ausnahmen_datei"
  return 1
}

# Erst die Dateiliste, getrennt: Scheitert `git ls-files`, bricht `set -e` hier
# ab, statt dass eine leere Pipe als "alles gruen" durchgeht.
dateien=$(git ls-files)
if [ -z "$dateien" ]; then echo "zeilenenden: 0 Dateien"; exit 0; fi
dateien_anzahl=$(printf '%s\n' "$dateien" | grep -c .)

# `check-attr` gibt je Datei eine Zeile "<pfad>: eol: <wert>". Alles ausser
# "lf" ist ein Befund — auch "unspecified" (Regel fehlt), "unset" (`-eol`),
# "set" (`eol` ohne Wert) und "LF" (Wert in Grossbuchstaben). Eigene
# Fehlermeldung statt eines stillen `set -e`-Abbruchs mit Gits eigenem Text.
if ! attr_linux=$(printf '%s\n' "$dateien" | git -c core.ignorecase=false check-attr --stdin eol 2>&1); then
  echo "zeilenenden: git check-attr (ignorecase=false) fehlgeschlagen: $attr_linux"
  exit 1
fi
if ! attr_windows=$(printf '%s\n' "$dateien" | git -c core.ignorecase=true check-attr --stdin eol 2>&1); then
  echo "zeilenenden: git check-attr (ignorecase=true) fehlgeschlagen: $attr_windows"
  exit 1
fi

# Zeilenzahl von `check-attr` gegen die Dateizahl pruefen: Eine verkuerzte
# Pipe davor (z. B. `head -n 30`) blieb sonst gruen und meldete trotzdem
# Erfolg fuer `$dateien_anzahl` Dateien -- die Zahl kam aus `$dateien`, nicht
# aus den tatsaechlich geprueften Zeilen (gemessen zu #118).
attr_linux_anzahl=$(printf '%s\n' "$attr_linux" | grep -c .)
attr_windows_anzahl=$(printf '%s\n' "$attr_windows" | grep -c .)
if [ "$attr_linux_anzahl" -ne "$dateien_anzahl" ] || [ "$attr_windows_anzahl" -ne "$dateien_anzahl" ]; then
  echo "zeilenenden: git check-attr hat $attr_linux_anzahl/$attr_windows_anzahl Zeilen fuer $dateien_anzahl Dateien geliefert (gekuerzte Pruefliste?)"
  exit 1
fi

# Der Anker `$` ist Absicht: ohne ihn wuerde `grep -v` eine Zeile wie
# "a.md: eol: lfx" schon deshalb ausschliessen, weil sie die Zeichenkette
# ": eol: lf" als Praefix enthaelt -- der Befund verschwindet lautlos
# (gemessen zu #118, Selbstprobe Fall 18).
falsches_attribut=$(printf '%s\n%s\n' "$attr_linux" "$attr_windows" | grep -v ': eol: lf$' | sort -u || true)

# `ls-files --eol`: erste Spalte ist der Index. `i/crlf` und `i/mixed` sind
# Befunde; `i/-text` (Binaerdatei) und `i/none` (leer) nicht.
eol_liste=$(git ls-files --eol)
crlf_im_index=$(printf '%s\n' "$eol_liste" | awk '$1 == "i/crlf" || $1 == "i/mixed"')

befund_attr=""
if [ -n "$falsches_attribut" ]; then
  befund_attr=$(printf '%s\n' "$falsches_attribut" | while IFS= read -r z; do
    pfad="${z%: eol: *}"
    wert="${z##*: eol: }"
    if erlaubt=$(ausnahme_wert "$pfad"); then
      [ "$erlaubt" = "$wert" ] || printf '%s\n' "$z"
    else
      printf '%s\n' "$z"
    fi
  done)
fi
befund_index=""
if [ -n "$crlf_im_index" ]; then
  befund_index=$(printf '%s\n' "$crlf_im_index" | while IFS= read -r z; do
    pfad=$(printf '%s' "$z" | cut -f2)
    index_wert=$(printf '%s' "$z" | awk '{print $1}')
    index_wert="${index_wert#i/}"
    if erlaubt=$(ausnahme_wert "$pfad"); then
      [ "$erlaubt" = "$index_wert" ] || printf '%s\n' "$z"
    else
      printf '%s\n' "$z"
    fi
  done)
fi

# Veraltete Ausnahmen: ein eingetragener Pfad, der nicht mehr versioniert
# ist, blieb sonst unbemerkt stehen.
befund_veraltet=""
if [ -f "$ausnahmen_datei" ]; then
  befund_veraltet=$(while IFS= read -r zeile || [ -n "$zeile" ]; do
    case "$zeile" in ''|'#'*) continue ;; esac
    pfad=$(printf '%s\n' "$zeile" | cut -f1)
    printf '%s\n' "$dateien" | grep -Fxq -- "$pfad" || printf '%s\n' "$pfad"
  done < "$ausnahmen_datei")
fi

if [ -n "$befund_attr" ] || [ -n "$befund_index" ] || [ -n "$befund_veraltet" ]; then
  if [ -n "$befund_attr" ]; then
    echo "zeilenenden: Dateien ohne eol=lf (.gitattributes pruefen; absichtlich CRLF -> $ausnahmen_datei):"
    printf '%s\n' "$befund_attr"
  fi
  if [ -n "$befund_index" ]; then
    echo "zeilenenden: Blobs mit CRLF im Index (git add --renormalize . ; absichtlich CRLF -> $ausnahmen_datei):"
    printf '%s\n' "$befund_index"
  fi
  if [ -n "$befund_veraltet" ]; then
    echo "zeilenenden: veraltete Ausnahme(n) in $ausnahmen_datei (Pfad nicht mehr versioniert):"
    printf '%s\n' "$befund_veraltet"
  fi
  exit 1
fi
echo "zeilenenden: $dateien_anzahl Dateien, alle eol=lf, kein CRLF im Index"
