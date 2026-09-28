#!/bin/sh
# Selbstprobe fuer scripts/zeilenenden.sh (#104).
#
# WARUM: Ein Waechter ohne Probe ist Disziplin, kein Waechter
# (docs/agents/lehren.md §18). Jeder Fall baut ein Wegwerf-Repo mit der
# `.gitattributes` DIESES Repos, veraendert es auf eine Weise, die das Ziel
# still aushebelt (oder eben nicht), und verlangt den erwarteten Exit-Code.
#
# HERKUNFT DER FAELLE: 2-5 die Rueckbau-Varianten, die die blinde Erststimme
# im Panel zu #104 gemessen hat (Regel geloescht, `*.md -eol`, `*.md !eol`,
# verschachtelte `.gitattributes` mit `eol=crlf`); 6 der Fund, dass
# `text=auto` einen Blob, der schon CRLF traegt, nicht normalisiert — hier mit
# LF im Arbeitsbaum, damit nur der INDEX die Antwort traegt; 9-15 die
# Mutanten des Waechters, die die blinde Stimme zu Nacharbeit 1 an der alten
# Probe vorbeibrachte (Negativliste statt Positivliste, `eol` ohne Wert, Wert
# in Grossbuchstaben, `i/mixed`, Gross-/Kleinschreibung der Muster, Aufruf aus
# einem Unterverzeichnis, Pfad, der selbst ": eol: lf" enthaelt) und die
# benannte Ausnahme.
set -eu

# Nie ins aufrufende Repo schreiben, auch nicht aus einem Hook heraus
# (gemessen: mit gesetztem GIT_DIR legte die alte Fassung dort Commits an).
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_COMMON_DIR 2>/dev/null || true

WURZEL=$(cd "$(dirname "$0")/.." && pwd)
WAECHTER="$WURZEL/scripts/zeilenenden.sh"
[ -f "$WAECHTER" ] || { echo "Waechter nicht gefunden: $WAECHTER"; exit 2; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
# Fall 8 ("kein Repo") darf nicht davon abhaengen, ob das Temp-Verzeichnis
# zufaellig in einem Git-Repo liegt.
GIT_CEILING_DIRECTORIES=$TMP
export GIT_CEILING_DIRECTORIES

BESTANDEN=0
FEHLGESCHLAGEN=0
UEBERSPRUNGEN=0

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

# Blob mit genau diesem Inhalt am Filter vorbei in den Index, Arbeitsbaum LF.
blob_in_index() {
  repo=$1; pfad=$2; inhalt=$3
  printf "$inhalt" > "$repo/.blob"
  blob=$(git -C "$repo" hash-object -w --no-filters "$repo/.blob")
  rm -f "$repo/.blob"
  git -C "$repo" -c core.protectNTFS=false update-index --add --cacheinfo 100644 "$blob" "$pfad"
}

erwarte() {
  name=$1; soll=$2; wo=$3; waechter=${4:-$WAECHTER}
  if (cd "$wo" && sh "$waechter" >/dev/null 2>&1); then ist=0; else ist=$?; fi
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

# 6. Ein Blob mit CRLF im Index, der Arbeitsbaum traegt LF.
r=$(neues_repo crlf_blob)
blob_in_index "$r" crlf.txt 'Zeile\r\n'
printf 'Zeile\n' > "$r/crlf.txt"
erwarte "6 CRLF-Blob im Index (Arbeitsbaum LF)" 1 "$r"

# 7. Eine Binaerdatei (NUL-Byte) ist kein Befund.
r=$(neues_repo binaer)
printf 'PNG\000\001\002\r\n' > "$r/bild.png"
git -C "$r" add bild.png
erwarte "7 Binaerdatei" 0 "$r"

# 8. Kein Git-Repo: Exit 2, nicht still gruen.
mkdir -p "$TMP/kein_repo"
erwarte "8 kein Repo" 2 "$TMP/kein_repo"

# 9. `eol` ohne Wert (check-attr meldet "set") — faellt durch eine Negativliste.
r=$(neues_repo md_eol_gesetzt)
printf '*.md eol\n' >> "$r/.gitattributes"
erwarte "9 *.md eol (set)" 1 "$r"

# 10. Wert in Grossbuchstaben.
r=$(neues_repo md_eol_gross)
printf '*.md eol=LF\n' >> "$r/.gitattributes"
erwarte "10 *.md eol=LF" 1 "$r"

# 11. Gemischte Zeilenenden im Index.
r=$(neues_repo gemischt)
blob_in_index "$r" m.md 'a\r\nb\n'
printf 'a\nb\n' > "$r/m.md"
erwarte "11 i/mixed" 1 "$r"

# 12. Muster in anderer Schreibweise: unter Windows (ignorecase) greift es.
r=$(neues_repo gross_klein)
printf '*.MD eol=crlf\n' >> "$r/.gitattributes"
erwarte "12 *.MD eol=crlf (Gross-/Kleinschreibung)" 1 "$r"

# 13. Aufruf aus einem Unterverzeichnis; der Befund liegt in der Wurzel.
r=$(neues_repo unterverzeichnis)
blob_in_index "$r" wurzel.txt 'x\r\n'
printf 'x\n' > "$r/wurzel.txt"
erwarte "13 aus frontend/, Befund in der Wurzel" 1 "$r/frontend"

# 14. Ein Pfad, der selbst ": eol: lf" enthaelt, mit eol=crlf — ein Anker am
#     Zeilenende verhindert, dass der Pfadname den Befund versteckt.
#     Git fuer Windows lehnt ':' in Pfaden grundsaetzlich ab; dort wird der
#     Fall als UEBERSPRUNGEN gemeldet, gezaehlt wird er in der CI (Linux).
r=$(neues_repo pfad_taeuscht)
printf 'x* eol=crlf\n' >> "$r/.gitattributes"
if blob_in_index "$r" 'x: eol: lf' 'a\n' 2>/dev/null; then
  erwarte "14 Pfad mit ': eol: lf'" 1 "$r"
else
  UEBERSPRUNGEN=$((UEBERSPRUNGEN + 1))
  echo "UEBERSPRUNGEN: 14 Pfad mit ':' (auf diesem System nicht anlegbar)"
fi

# 16. Falsches Attribut an einer Datei OHNE .md/.ts-Endung.
r=$(neues_repo ohne_endung)
printf '/hook eol=crlf\n' >> "$r/.gitattributes"
erwarte "16 Datei ohne Endung mit eol=crlf" 1 "$r"

# 15. Benannte Ausnahme: dieselbe .bat ist ohne Eintrag ein Befund, mit Eintrag nicht.
r=$(neues_repo ausnahme)
printf '*.bat text eol=crlf\n' >> "$r/.gitattributes"
printf 'echo a\n' > "$r/start.bat"
git -C "$r" add start.bat
erwarte "15a .bat eol=crlf ohne Ausnahme" 1 "$r"
sed 's/^AUSNAHMEN=""$/AUSNAHMEN="start.bat"/' "$WAECHTER" > "$TMP/waechter_mit_ausnahme.sh"
grep -q '^AUSNAHMEN="start.bat"$' "$TMP/waechter_mit_ausnahme.sh" || { echo "Ausnahme-Zeile nicht gefunden"; exit 2; }
erwarte "15b .bat eol=crlf mit Ausnahme" 0 "$r" "$TMP/waechter_mit_ausnahme.sh"

echo "$BESTANDEN bestanden, $FEHLGESCHLAGEN fehlgeschlagen, $UEBERSPRUNGEN uebersprungen"
[ "$FEHLGESCHLAGEN" -eq 0 ]
