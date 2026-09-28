#!/bin/sh
# Selbstprobe fuer scripts/zeilenenden.sh (#104).
#
# WARUM: Ein Waechter ohne Probe ist Disziplin, kein Waechter
# (docs/agents/lehren.md §18). Jeder Fall baut ein Wegwerf-Repo mit der
# `.gitattributes` DIESES Repos, veraendert es auf eine Weise, die das Ziel
# still aushebelt, und verlangt den erwarteten Exit-Code.
#
# HERKUNFT DER FAELLE: 2-5 sind die Rueckbau-Varianten, die die blinde
# Erststimme im Panel zu #104 gemessen hat (Regel geloescht, `*.md -eol` als
# spaetere Zeile, verschachtelte `.gitattributes` mit `eol=crlf`); 6 ist der
# Fund, dass `text=auto` einen Blob, der schon CRLF traegt, nicht normalisiert.
# 7 prueft, dass eine Binaerdatei kein Befund ist.
set -eu

WURZEL=$(cd "$(dirname "$0")/.." && pwd)
WAECHTER="$WURZEL/scripts/zeilenenden.sh"
[ -f "$WAECHTER" ] || { echo "Waechter nicht gefunden: $WAECHTER"; exit 2; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

BESTANDEN=0
FEHLGESCHLAGEN=0

# Ein Wegwerf-Repo mit der echten .gitattributes, einer .md-, einer .ts-
# und einer Datei ohne Endung — alles LF, alles eingecheckt.
neues_repo() {
  r="$TMP/$1"
  mkdir -p "$r/frontend"
  git -C "$r" init -q
  git -C "$r" config user.email probe@example.invalid
  git -C "$r" config user.name probe
  git -C "$r" config core.autocrlf false
  cp "$WURZEL/.gitattributes" "$r/.gitattributes"
  printf 'Text\n' > "$r/README.md"
  printf 'export const a = 1;\n' > "$r/frontend/a.ts"
  printf '#!/bin/sh\necho hook\n' > "$r/hook"
  git -C "$r" add -A
  git -C "$r" commit -q -m basis
  echo "$r"
}

erwarte() {
  name=$1; soll=$2; repo=$3
  if (cd "$repo" && sh "$WAECHTER" >/dev/null 2>&1); then ist=0; else ist=$?; fi
  if [ "$ist" = "$soll" ]; then
    BESTANDEN=$((BESTANDEN + 1))
  else
    FEHLGESCHLAGEN=$((FEHLGESCHLAGEN + 1))
    echo "FEHLGESCHLAGEN: $name — erwartet Exit $soll, bekam $ist"
  fi
}

# 1. Sauberer Stand: kein Befund.
r=$(neues_repo sauber)
erwarte "1 sauber" 0 "$r"

# 2. Regel `* text=auto eol=lf` geloescht.
r=$(neues_repo ohne_regel)
grep -v '^\* text=auto eol=lf' "$r/.gitattributes" > "$r/ga" && mv "$r/ga" "$r/.gitattributes"
erwarte "2 Regel geloescht" 1 "$r"

# 3. Spaetere Zeile hebt eol fuer *.md auf.
r=$(neues_repo md_minus_eol)
printf '*.md -eol\n' >> "$r/.gitattributes"
erwarte "3 *.md -eol" 1 "$r"

# 4. Spaetere Zeile setzt eol fuer *.md zurueck auf unspezifiziert.
r=$(neues_repo md_ausrufe_eol)
printf '*.md !eol\n' >> "$r/.gitattributes"
erwarte "4 *.md !eol" 1 "$r"

# 5. Verschachtelte .gitattributes mit eol=crlf.
r=$(neues_repo verschachtelt)
printf '*.ts text eol=crlf\n' > "$r/frontend/.gitattributes"
git -C "$r" add frontend/.gitattributes
erwarte "5 frontend/.gitattributes eol=crlf" 1 "$r"

# 6. Ein Blob, der schon CRLF traegt (am Filter vorbei eingecheckt).
r=$(neues_repo crlf_blob)
printf 'Zeile\r\n' > "$r/crlf.txt"
blob=$(git -C "$r" hash-object -w --no-filters "$r/crlf.txt")
git -C "$r" update-index --add --cacheinfo 100644 "$blob" crlf.txt
erwarte "6 CRLF-Blob im Index" 1 "$r"

# 7. Eine Binaerdatei (NUL-Byte) ist kein Befund.
r=$(neues_repo binaer)
printf 'PNG\000\001\002\r\n' > "$r/bild.png"
git -C "$r" add bild.png
erwarte "7 Binaerdatei" 0 "$r"

# 8. Kein Git-Repo: Exit 2, nicht still gruen.
mkdir -p "$TMP/kein_repo"
erwarte "8 kein Repo" 2 "$TMP/kein_repo"

echo "$BESTANDEN bestanden, $FEHLGESCHLAGEN fehlgeschlagen"
[ "$FEHLGESCHLAGEN" -eq 0 ]
