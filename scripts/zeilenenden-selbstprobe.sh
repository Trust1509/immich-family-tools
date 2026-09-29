#!/bin/sh
# Selbstprobe fuer scripts/zeilenenden.sh (#104, #118).
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
# LF im Arbeitsbaum, damit nur der INDEX die Antwort traegt; 9-16 die
# Mutanten des Waechters, die die blinde Stimme zu Nacharbeit 1 an der alten
# Probe vorbeibrachte (Negativliste statt Positivliste, `eol` ohne Wert, Wert
# in Grossbuchstaben, `i/mixed`, Gross-/Kleinschreibung der Muster, Aufruf aus
# einem Unterverzeichnis, Pfad der selbst ": eol: lf" enthaelt, Datei OHNE
# .md/.ts-Endung); 15 die benannte Ausnahme aus #118 (Pfadliste mit Wert je
# Pfad statt Glob, exakter statt Praefix-Vergleich bei Pfad UND Wert,
# veraltete Ausnahme); 17-19 weitere Funde aus #118 (nur die
# exakte, case-sensitive Pruefung haelt manche Befunde fest; Anker ohne `$`
# am Zeilenende; eine gekuerzte oder eingeschraenkte Pruefliste bleibt nicht
# mehr unbemerkt).
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

# 12. Muster in anderer Schreibweise: unter Windows (ignorecase=true) greift es.
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
#     Fall als UEBERSPRUNGEN gemeldet. Ausserhalb von Windows erzwingt diese
#     Probe UEBERSPRUNGEN=0 (siehe Fusszeile) — der Fall darf dort nicht
#     still durchrutschen, wenn `blob_in_index` aus anderem Grund scheitert.
r=$(neues_repo pfad_taeuscht)
printf 'x* eol=crlf\n' >> "$r/.gitattributes"
if blob_in_index "$r" 'x: eol: lf' 'a\n' 2>/dev/null; then
  erwarte "14 Pfad mit ': eol: lf'" 1 "$r"
else
  UEBERSPRUNGEN=$((UEBERSPRUNGEN + 1))
  echo "UEBERSPRUNGEN: 14 Pfad mit ':' (auf diesem System nicht anlegbar)"
fi

# 15. Benannte Ausnahme aus #118: dieselbe .bat ist ohne Eintrag ein Befund,
#     mit korrektem Pfad UND korrektem Wert nicht, mit falschem Wert, mit
#     falschem Pfad oder mit einer zusaetzlichen veralteten Ausnahme wieder.
#     Die Ausnahmedatei liegt im GEPRUEFTEN Wegwerf-Repo (`$r/scripts/...`,
#     wie der Waechter sie auch im echten Projekt sucht) -- nicht neben
#     diesem Skript. So bleibt jeder Fall unten von der echten
#     scripts/zeilenenden-ausnahmen.txt dieses Repos unabhaengig, und
#     umgekehrt: ein Eintrag dort stoert diese Faelle nie (belegt, siehe
#     "echte Tuer" im Bau-Bericht).
r=$(neues_repo ausnahme)
printf '*.bat text eol=crlf\n' >> "$r/.gitattributes"
printf 'echo a\n' > "$r/start.bat"
# "start" (ohne Endung) ist eine ZWEITE, echte, saubere Datei -- exakter
# Namensvetter des Praefix "start" aus Fall 15f. Ohne sie waere "start" als
# Ausnahme-Pfad in JEDEM Fall veraltet (nicht versioniert) und wuerde die
# veraltete-Ausnahme-Probe allein schon rot faerben, egal ob der Vergleich
# exakt oder praefixartig ist -- der Praefix-Befund waere unbeobachtbar.
printf 'sauber\n' > "$r/start"
git -C "$r" add start.bat start
erwarte "15a .bat eol=crlf ohne Ausnahme" 1 "$r"

mkdir -p "$r/scripts"

printf 'start.bat\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "15b .bat eol=crlf mit korrekter Ausnahme" 0 "$r"

printf 'start.bat\tlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "15c .bat eol=crlf mit falschem Wert in der Ausnahme" 1 "$r"

printf 'anderer/pfad.bat\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "15d .bat eol=crlf mit Ausnahme auf falschem Pfad" 1 "$r"

# 15f/15g: der Pfad "start" ist ein PRAEFIX von "start.bat", der Wert "cr"
# ein PRAEFIX von "crlf" -- beides muss trotzdem ein Befund bleiben. Faengt
# einen Praefix-Vergleich, falls der exakte String-Vergleich (`[ "$1" =
# "$pfad" ]` bzw. `[ "$erlaubt" = "$wert" ]`) je durch ein `case ... in
# $x*)` ersetzt wird.
printf 'start\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "15f .bat eol=crlf, Ausnahme-Pfad ist nur ein Praefix" 1 "$r"

printf 'start.bat\tcr\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "15g .bat eol=crlf, Ausnahme-Wert ist nur ein Praefix" 1 "$r"

printf 'start.bat\tcrlf\nnicht/mehr/vorhanden.md\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "15e veraltete Ausnahme (Pfad nicht mehr versioniert)" 1 "$r"

rm -f "$r/scripts/zeilenenden-ausnahmen.txt"

# 16. Falsches Attribut an einer Datei OHNE .md/.ts-Endung — faengt einen
#     Mutanten, der nur diese zwei Endungen prueft.
r=$(neues_repo ohne_endung)
printf '/hook eol=crlf\n' >> "$r/.gitattributes"
erwarte "16 Datei ohne Endung mit eol=crlf" 1 "$r"

# 17. Nur die exakte (Linux-, ignorecase=false) Pruefung haelt diesen Befund
#     fest: Eine spaetere, case-insensitiv passende Regel (`*.MD eol=lf`)
#     ueberschreibt unter ignorecase=true die frueher passende, exakte Regel
#     (`README.md eol=crlf`) und versteckt den Befund dort. Gemessen (#118):
#     unter core.ignorecase=false bleibt `README.md: eol: crlf`, unter
#     core.ignorecase=true wird daraus `README.md: eol: lf`.
r=$(neues_repo nur_linux_haelt_fest)
printf 'README.md eol=crlf\n*.MD eol=lf\n' >> "$r/.gitattributes"
erwarte "17 nur ignorecase=false faengt README.md eol=crlf" 1 "$r"

# 18. Anker-Mutant, ueberall anlegbar (kein ':' im Pfad noetig): `*.md
#     eol=lfx` ist kein Befund mehr, wenn der Vergleich `': eol: lf'` den
#     Anker `$` verliert — die Zeichenkette ": eol: lf" ist Praefix von
#     ": eol: lfx" und wuerde durch `grep -v` ohne Anker mit ausgefiltert.
r=$(neues_repo anker_ohne_dollar)
printf '*.md eol=lfx\n' >> "$r/.gitattributes"
erwarte "18 *.md eol=lfx (Anker-Mutant)" 1 "$r"

# 19. Ein Befund weit hinten in einer grossen, nach Pfad sortierten
#     Dateiliste, unter docs/. Nachweis fuer zwei Mutanten aus #118:
#     - eine Pipe, die die Pruefliste vor `check-attr` kuerzt (z. B.
#       `head -n 30`), sieht diesen Befund gar nicht mehr, meldet aber
#       unveraendert `$dateien_anzahl` Dateien als "alle eol=lf";
#     - ein Pfad-Ausschluss bei `git ls-files` (z. B. `git ls-files
#       ':!docs'`) nimmt die Datei aus der Pruefung UND aus der Dateizahl,
#       ohne dass eine Zeilenzahl-Probe das noch sehen koennte.
#     40 sauber benannte Dateien sortieren vor "docs/..." (c < d), der Befund
#     liegt an Position 41.
repo_gross() {
  r="$TMP/gross"
  mkdir -p "$r/docs"
  git -C "$r" init -q
  git -C "$r" config user.email probe@example.invalid
  git -C "$r" config user.name probe
  git -C "$r" config core.autocrlf false
  cp "$WURZEL/.gitattributes" "$r/.gitattributes"
  i=1
  while [ "$i" -le 40 ]; do
    printf 'Text\n' > "$r/clean_$(printf '%02d' "$i").md"
    i=$((i + 1))
  done
  printf 'docs/befund.md eol=crlf\n' >> "$r/.gitattributes"
  printf 'Text\n' > "$r/docs/befund.md"
  git -C "$r" add -A
  git -C "$r" commit -q -m basis
  echo "$r"
}
r=$(repo_gross)
erwarte "19 Befund hinter vielen sauberen Dateien, in docs/" 1 "$r"

# Ausserhalb von Windows darf Fall 14 nie stillschweigend uebersprungen
# werden (dort ist ':' in Pfaden erlaubt) — sonst koennte ein scheiterndes
# `blob_in_index` die Probe in der CI unbemerkt gruen lassen. Auf Windows ist
# das Uebersprungen dagegen die einzig moegliche, dokumentierte Folge.
plattform_windows=false
case "$(uname -s 2>/dev/null || echo '')" in
  MINGW*|MSYS*|CYGWIN*) plattform_windows=true ;;
esac
if [ "$UEBERSPRUNGEN" -gt 0 ] && [ "$plattform_windows" = false ]; then
  FEHLGESCHLAGEN=$((FEHLGESCHLAGEN + 1))
  echo "FEHLGESCHLAGEN: $UEBERSPRUNGEN Fall/Faelle ausserhalb von Windows uebersprungen — hier nicht erlaubt"
fi

echo "$BESTANDEN bestanden, $FEHLGESCHLAGEN fehlgeschlagen, $UEBERSPRUNGEN uebersprungen"
[ "$FEHLGESCHLAGEN" -eq 0 ]
