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
# Eigener Zaehler fuer Faelle, die eine git-MINDESTVERSION brauchen (Fall 41)
# -- getrennt von UEBERSPRUNGEN, damit die "UEBERSPRUNGEN=0 ausserhalb von
# Windows"-Regel am Fussende unberuehrt bleibt (die ist ein Windows-Thema,
# keins der git-Version).
UEBERSPRUNGEN_VERSION=0
# Eigener Zaehler fuer Faelle, die eine BERECHTIGUNGSGRENZE brauchen (Fall
# 73) -- getrennt von UEBERSPRUNGEN, aus demselben Grund wie oben: weder
# Windows/NTFS (Eigentuemer) noch root (jedes System) sind ein Fall der
# "UEBERSPRUNGEN=0 ausserhalb von Windows"-Regel.
UEBERSPRUNGEN_BERECHTIGUNG=0

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

# Wie erwarte(), prueft aber zusaetzlich die URSACHE, nicht nur den
# Exit-Code: ein Text, der in der Ausgabe vorkommen MUSS ($4), optional ein
# Text, der NICHT vorkommen darf ($5), optional ein Verzeichnis vorne in PATH
# ($6, fuer Git-Attrappen -- siehe git_shim_* unten). Ohne das waere ein
# Mutant nicht von einem Befund aus einem ANDEREN Grund zu unterscheiden
# (gemessen zu #118 Nacharbeit 1: eine falsch-case-verglichene Ausnahme UND
# eine echte "veraltete Ausnahme" liefern beide Exit 1, nur eine der beiden
# Meldungen verschwindet unter dem Mutanten).
erwarte_text() {
  name=$1; soll=$2; wo=$3; muss=${4:-}; darf_nicht=${5:-}; pfad_praefix=${6:-}; waechter=${7:-$WAECHTER}
  if [ -n "$pfad_praefix" ]; then
    if ausgabe=$(cd "$wo" && PATH="$pfad_praefix:$PATH" sh "$waechter" 2>&1); then ist=0; else ist=$?; fi
  else
    if ausgabe=$(cd "$wo" && sh "$waechter" 2>&1); then ist=0; else ist=$?; fi
  fi
  fehler=""
  [ "$ist" = "$soll" ] || fehler="erwartet Exit $soll, bekam $ist"
  if [ -z "$fehler" ] && [ -n "$muss" ] && ! printf '%s\n' "$ausgabe" | grep -Fq -- "$muss"; then
    fehler="Meldung enthaelt nicht '$muss'"
  fi
  if [ -z "$fehler" ] && [ -n "$darf_nicht" ] && printf '%s\n' "$ausgabe" | grep -Fq -- "$darf_nicht"; then
    fehler="Meldung enthaelt unerwartet '$darf_nicht'"
  fi
  if [ -z "$fehler" ]; then
    BESTANDEN=$((BESTANDEN + 1))
  else
    FEHLGESCHLAGEN=$((FEHLGESCHLAGEN + 1))
    echo "FEHLGESCHLAGEN: $name — $fehler"
  fi
}

# Baut in Verzeichnis $1 einen git-Ersatz, der `check-attr --stdin eol`
# unter core.ignorecase=false ("linux"), =true ("windows") oder beiden
# ("beide") um die LETZTE Zeile kuerzt -- simuliert eine vorgeschaltete,
# kuerzende Pipe (z. B. `head -n N`) im Waechter selbst, ohne dessen Text zu
# veraendern. Alle anderen Git-Aufrufe reicht die Attrappe unveraendert an
# das echte `git` durch.
git_shim_kuerzt_attr() {
  d=$1; modus=$2
  mkdir -p "$d"
  echt=$(command -v git)
  cat > "$d/git" <<EOS
#!/bin/sh
kuerzen=false
fall="$modus"
alle="\$*"
if printf '%s' "\$alle" | grep -q 'check-attr'; then
  if printf '%s' "\$alle" | grep -q 'core.ignorecase=false'; then
    case "\$fall" in linux|beide) kuerzen=true ;; esac
  fi
  if printf '%s' "\$alle" | grep -q 'core.ignorecase=true'; then
    case "\$fall" in windows|beide) kuerzen=true ;; esac
  fi
fi
if [ "\$kuerzen" = true ]; then
  "$echt" "\$@" | sed '\$d'
else
  exec "$echt" "\$@"
fi
EOS
  chmod +x "$d/git"
}

# Baut in Verzeichnis $1 einen git-Ersatz, der `ls-files --eol` um die
# letzte Zeile kuerzt (fuer den Zeilenzahl-Abgleich der Index-Liste).
git_shim_kuerzt_eol() {
  d=$1
  mkdir -p "$d"
  echt=$(command -v git)
  cat > "$d/git" <<EOS
#!/bin/sh
case " \$* " in
  *' ls-files --eol'*) "$echt" "\$@" | sed '\$d' ;;
  *) exec "$echt" "\$@" ;;
esac
EOS
  chmod +x "$d/git"
}

# Baut in Verzeichnis $1 einen git-Ersatz, der BEIDE `check-attr`-Varianten
# UND `ls-files --eol` um dieselbe letzte Zeile kuerzt. Noetig, um den
# Mutanten zu isolieren, der die Dateizahl durch den (dann ebenso
# verkuerzten) Linux-Wert ersetzt (`dateien_anzahl=$attr_linux_anzahl`):
# kuerzt man NUR die beiden `check-attr`-Aufrufe (wie
# `git_shim_kuerzt_attr ... beide`), bleibt `ls-files --eol` unveraendert
# bei der echten Dateizahl und widerspricht der (unter diesem Mutanten
# verkuerzten) `dateien_anzahl` immer noch -- der Mutant waere dann nur durch
# Zufall "gefangen", nicht durch die eigentliche Luecke (gemessen zu #118
# Nacharbeit 1: mit nur zwei gekuerzten Listen blieb Fall 38 bestehen, obwohl
# der Mutant aktiv war).
git_shim_kuerzt_alles() {
  d=$1
  mkdir -p "$d"
  echt=$(command -v git)
  cat > "$d/git" <<EOS
#!/bin/sh
alle="\$*"
if printf '%s' "\$alle" | grep -q 'check-attr' || printf '%s' "\$alle" | grep -q 'ls-files --eol'; then
  "$echt" "\$@" | sed '\$d'
else
  exec "$echt" "\$@"
fi
EOS
  chmod +x "$d/git"
}

# Baut in Verzeichnis $1 einen git-Ersatz, der genau den Unterbefehl $2
# (z. B. "ls-files", ohne Argumente wie --eol) fehlschlagen laesst (stderr
# $3, Exit 128 -- wie ein echter Git-Fehler).
git_shim_schlaegt_fehl() {
  d=$1; unterbefehl=$2; meldung=$3
  mkdir -p "$d"
  echt=$(command -v git)
  cat > "$d/git" <<EOS
#!/bin/sh
if [ "\$1" = "-c" ]; then shift 2; fi
if [ "\$1" = "-c" ]; then shift 2; fi
if [ "\$1" = "$unterbefehl" ] && { [ "\$#" = 1 ] || [ "\$2" != "--eol" ]; }; then
  echo "$meldung" >&2
  exit 128
fi
exec "$echt" "\$@"
EOS
  chmod +x "$d/git"
}

# Baut in Verzeichnis $1 einen git-Ersatz, der `check-attr --stdin eol`
# (beide core.ignorecase-Varianten) leer ausgeben laesst, aber mit Exit 0 --
# ein Git, das "erfolgreich" nichts meldet.
git_shim_leere_attr_antwort() {
  d=$1
  mkdir -p "$d"
  echt=$(command -v git)
  cat > "$d/git" <<EOS
#!/bin/sh
case " \$* " in
  *' check-attr '*) cat >/dev/null; exit 0 ;;
  *) exec "$echt" "\$@" ;;
esac
EOS
  chmod +x "$d/git"
}

# Baut in Verzeichnis $1 einen git-Ersatz, der bei `check-attr --stdin eol`
# (core.ignorecase=false) eine reine Warnung auf STDERR ausgibt, den echten
# Aufruf aber sonst unveraendert durchreicht -- simuliert Gits eigene
# Warnungen (z. B. zu einem negativen `.gitattributes`-Muster), die frueher
# per `2>&1` in die Pruefliste gemischt wurden.
git_shim_stderr_warnung() {
  d=$1
  mkdir -p "$d"
  echt=$(command -v git)
  cat > "$d/git" <<EOS
#!/bin/sh
alle="\$*"
if printf '%s' "\$alle" | grep -q 'check-attr' && printf '%s' "\$alle" | grep -q 'core.ignorecase=false'; then
  echo "warning: simulierte Attrappen-Warnung" >&2
fi
exec "$echt" "\$@"
EOS
  chmod +x "$d/git"
}

# Wie oben, aber fuer die WINDOWS-Variante (core.ignorecase=true) -- Fall 43
# oben deckt nur die Linux-Seite; die Windows-Seite hatte denselben Mutanten
# (`2>&1` statt eigener Umlenkung, #118 Nacharbeit 2).
git_shim_stderr_warnung_win() {
  d=$1
  mkdir -p "$d"
  echt=$(command -v git)
  cat > "$d/git" <<EOS
#!/bin/sh
alle="\$*"
if printf '%s' "\$alle" | grep -q 'check-attr' && printf '%s' "\$alle" | grep -q 'core.ignorecase=true'; then
  echo "warning: simulierte Attrappen-Warnung (windows)" >&2
fi
exec "$echt" "\$@"
EOS
  chmod +x "$d/git"
}

# Baut in Verzeichnis $1 einen git-Ersatz, der `check-attr --stdin eol` fuer
# die Variante $2 ("linux" = ignorecase=false, "windows" = ignorecase=true,
# "beide") deterministisch scheitern laesst (Meldung $3 auf stderr, Exit
# 129 -- ein erfundener, git-untypischer Code, damit er nicht zufaellig mit
# einem echten git-Exit-Code verwechselt wird). Deterministisch statt eines
# echten, git-versionsabhaengigen Fehlers (siehe Fall 41/`GIT_ATTR_SOURCE`):
# das hier gilt unveraendert unter jeder Git-Version.
git_shim_attr_schlaegt_fehl() {
  d=$1; modus=$2; meldung=$3
  mkdir -p "$d"
  echt=$(command -v git)
  cat > "$d/git" <<EOS
#!/bin/sh
alle="\$*"
scheitern=false
if printf '%s' "\$alle" | grep -q 'check-attr'; then
  if printf '%s' "\$alle" | grep -q 'core.ignorecase=false'; then
    case "$modus" in linux|beide) scheitern=true ;; esac
  fi
  if printf '%s' "\$alle" | grep -q 'core.ignorecase=true'; then
    case "$modus" in windows|beide) scheitern=true ;; esac
  fi
fi
if [ "\$scheitern" = true ]; then
  cat >/dev/null
  echo "$meldung" >&2
  exit 129
fi
exec "$echt" "\$@"
EOS
  chmod +x "$d/git"
}

# Baut in Verzeichnis $1 einen git-Ersatz, der NUR `ls-files --eol`
# deterministisch scheitern laesst (Meldung $2, Exit 129) -- plain `ls-files`
# bleibt unangetastet, damit dieser Fall den Dateizaehler noch erreicht
# (anders als Fall 42, das plain `ls-files` selbst scheitern laesst).
git_shim_lsfiles_eol_schlaegt_fehl() {
  d=$1; meldung=$2
  mkdir -p "$d"
  echt=$(command -v git)
  cat > "$d/git" <<EOS
#!/bin/sh
# Der Waechter ruft \`git\` ueber eine eigene Funktion auf, die immer
# \`-c core.quotePath=true\` voranstellt -- diese Attrappe muss das
# ueberspringen, um an das eigentliche Unterkommando zu kommen.
alle="\$*"
case " \$alle " in
  *' ls-files --eol'*)
    echo "$meldung" >&2
    exit 129
    ;;
esac
exec "$echt" "\$@"
EOS
  chmod +x "$d/git"
}

# Baut in Verzeichnis $1 einen git-Ersatz, der bei `check-attr --stdin eol`
# (beide Varianten) genau EINE erfundene Zeile zusaetzlich ausgibt -- eine
# VERLAENGERTE statt einer gekuerzten Pruefliste. Faengt einen Mutanten, der
# den Zeilenzahl-Abgleich von `-ne` auf `-lt` aendert (nur "zu wenig" waere
# dann noch ein Befund, "zu viel" nicht mehr; gemessen zu #118 Nacharbeit 2,
# Gegenpruefer-N08).
git_shim_verlaengert_attr() {
  d=$1
  mkdir -p "$d"
  echt=$(command -v git)
  cat > "$d/git" <<EOS
#!/bin/sh
alle="\$*"
if printf '%s' "\$alle" | grep -q 'check-attr'; then
  "$echt" "\$@"
  echo "erfunden.txt: eol: lf"
else
  exec "$echt" "\$@"
fi
EOS
  chmod +x "$d/git"
}

# Wie oben, aber fuer `ls-files --eol` -- dieselbe VERLAENGERTE-statt-
# gekuerzte Pruefliste, auf der Index-Seite.
git_shim_verlaengert_eol() {
  d=$1
  mkdir -p "$d"
  echt=$(command -v git)
  cat > "$d/git" <<EOS
#!/bin/sh
case " \$* " in
  *' ls-files --eol'*)
    "$echt" "\$@"
    printf 'i/lf\terfunden.txt\n'
    ;;
  *) exec "$echt" "\$@" ;;
esac
EOS
  chmod +x "$d/git"
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
#     umgekehrt: ein Eintrag dort stoert diese Faelle nie (die "echte Tuer"
#     dazu ist der Lauf am echten Repo, siehe Block 5 im Nachweis).
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
# Text-Pruefung, nicht nur Exit-Code: Ein Mutant, der die Pruefliste vor
# `check-attr` auf eine feste Laenge kuerzt (z. B. `head -n 30`), faengt
# genau DIESEN Befund (Position 41 von 41) gar nicht mehr, wird aber ueber
# die Zeilenzahl-Probe trotzdem mit Exit 1 "gefangen" -- fuer den FALSCHEN
# Grund (gemessen zu #118 Nacharbeit 2, Gegenpruefer-G8/B20: auf zwei von
# drei gemessenen Plattformen ueberlebte dieser Mutant die ganze Selbstprobe
# unbemerkt, weil kein Fall bisher die tatsaechliche Fundzeile verlangte).
erwarte_text "19 Befund hinter vielen sauberen Dateien, in docs/" 1 "$r" "docs/befund.md: eol: crlf"

# ---------------------------------------------------------------------------
# Nacharbeit 1 zu #118: die Luecken aus dem Bau-Brief (Faelle 20-53).
# Jeder Fall nennt den Mutanten, den er faengt (Gegenpruefer M<n>, Blindpruefer
# M0<n>) oder, wo es keinen benannten Mutanten gibt, den Meldungs-/Format-Fehler
# aus dem Befund.
# ---------------------------------------------------------------------------

# 20. Index-Ausnahme mit korrektem Wert deckt einen echten CRLF-Blob im
#     Index -- die Index-Seite der Ausnahme war bisher ungeprueft (Fall 6
#     hat KEINE Ausnahme). Faengt Gegenpruefer-M20 (`index_wert="${index_wert#i/}"`
#     durch die Konstante `nie` ersetzt: ohne echten Wert bliebe jede
#     Index-Ausnahme wirkungslos und dieser Fall faelschlich rot).
r=$(neues_repo index_ausnahme_ok)
blob_in_index "$r" crlf.txt 'Zeile\r\n'
printf 'Zeile\n' > "$r/crlf.txt"
mkdir -p "$r/scripts"
printf 'crlf.txt\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "20 Index-CRLF mit korrekter Ausnahme (crlf)" 0 "$r"

# 21. Dieselbe Datei, aber die Ausnahme nennt einen FALSCHEN Wert -- bleibt
#     Befund. Faengt Gegenpruefer-M3 / Blindpruefer-M03 (`[ "$erlaubt" =
#     "$index_wert" ] || printf ...` durch `: || printf ...` ersetzt, also
#     nie ausgefuehrt -- jede Index-Ausnahme wuerde dann JEDEN Wert decken).
r=$(neues_repo index_ausnahme_falsch)
blob_in_index "$r" crlf.txt 'Zeile\r\n'
printf 'Zeile\n' > "$r/crlf.txt"
mkdir -p "$r/scripts"
printf 'crlf.txt\tlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "21 Index-CRLF mit falschem Ausnahme-Wert bleibt Befund" 1 "$r"

# 22. "i/mixed" ist NICHT durch eine Ausnahme mit Wert "crlf" gedeckt --
#     unterschiedliche Werte, keine Toleranz ("mixed wie crlf").
r=$(neues_repo index_mixed_nicht_crlf)
blob_in_index "$r" m.txt 'a\r\nb\n'
printf 'a\nb\n' > "$r/m.txt"
mkdir -p "$r/scripts"
printf 'm.txt\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "22 i/mixed mit Ausnahme-Wert crlf (falscher Wert) bleibt Befund" 1 "$r"

# 23/24. Ein leerer Wert (Tab, dann nichts) ist kein Jokerzeichen -- weder
#     auf der Index- noch auf der Attribut-Seite. Faengt Blindpruefer-M08
#     (leerer erlaubter Wert wird als Treffer fuer JEDEN Wert akzeptiert).
r=$(neues_repo index_ausnahme_leerer_wert)
blob_in_index "$r" crlf.txt 'Zeile\r\n'
printf 'Zeile\n' > "$r/crlf.txt"
mkdir -p "$r/scripts"
printf 'crlf.txt\t\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "23 Index-Ausnahme mit leerem Wert ist kein Joker" 1 "$r"

r=$(neues_repo attr_ausnahme_leerer_wert)
printf '*.bat text eol=crlf\n' >> "$r/.gitattributes"
printf 'echo\n' > "$r/start.bat"
git -C "$r" add start.bat
mkdir -p "$r/scripts"
printf 'start.bat\t\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "24 Attr-Ausnahme mit leerem Wert ist kein Joker" 1 "$r"

# 25-27. Der Ausnahme-PFAD wird exakt und wortwoertlich verglichen -- kein
#     Glob, kein Muster, keine Zeichenklasse. Faengt Gegenpruefer-M1/M14
#     (Pfad-Vergleich per `case "$1" in $pfad)` statt `[ "$1" = "$pfad" ]`).
#     WICHTIG: Exit-Code allein reicht hier NICHT -- ein solcher Pfad ist
#     zugleich KEINE echte, versionierte Datei, also faengt ihn die
#     veraltete-Ausnahme-Pruefung ohnehin (Exit 1, aber aus dem FALSCHEN
#     Grund; gemessen: Fall 25 blieb mit blossem Exit-Code-Vergleich unter
#     Gegenpruefer-M1 gruen). Die Meldungszeile fuer den echten Befund
#     (start.bat) muss deshalb ausdruecklich vorkommen.
r=$(neues_repo glob_pfad)
printf '*.bat text eol=crlf\n' >> "$r/.gitattributes"
printf 'echo\n' > "$r/start.bat"
git -C "$r" add start.bat
mkdir -p "$r/scripts"
printf '?*\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "25 Ausnahme-Pfad '?*' (Glob) deckt start.bat nicht" 1 "$r" "start.bat: eol: crlf"

printf '*.bat\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "26 Ausnahme-Pfad '*.bat' (Glob) deckt start.bat nicht" 1 "$r" "start.bat: eol: crlf"

printf '[s]tart.bat\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "27 Ausnahme-Pfad '[s]tart.bat' (Glob) deckt start.bat nicht" 1 "$r" "start.bat: eol: crlf"

# 28. Der erlaubte WERT wird ebenso exakt verglichen -- "*" ist die
#     Zeichenkette "*", kein Joker. Faengt Gegenpruefer-M15. Hier ist der
#     Ausnahme-PFAD ("start.bat") echt und versioniert, die veraltete-Pruefung
#     kann also nicht mit hineinspielen -- reiner Exit-Code reicht.
printf 'start.bat\t*\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "28 Ausnahme-Wert '*' (Glob) bleibt Befund" 1 "$r"

# 29. Veraltete Pruefung: ein Ausnahme-Pfad, der nur ein SUBSTRING einer
#     echten Datei ist ("sta" in "start.bat"), ist selbst keine versionierte
#     Datei. Faengt Gegenpruefer-M5/M6, Blindpruefer-M05 (`grep -Fxq` ohne
#     `-x` bzw. als `grep -q`: ein Substring "deckt" dann jede Datei, die
#     ihn enthaelt).
r=$(neues_repo veraltet_substring)
printf 'echo\n' > "$r/start.bat"
git -C "$r" add start.bat
mkdir -p "$r/scripts"
printf 'sta\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "29 veraltete Ausnahme 'sta' (Substring von start.bat)" 1 "$r"

# 30. Veraltete Pruefung ist case-sensitiv: "START.BAT" ist nicht dieselbe
#     Datei wie das echte, saubere "start.bat". Faengt Blindpruefer-M13
#     (`grep -Fxq` durch `grep -Fxiq` ersetzt).
r=$(neues_repo veraltet_gross_klein)
printf 'echo\n' > "$r/start.bat"
git -C "$r" add start.bat
mkdir -p "$r/scripts"
printf 'START.BAT\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "30 veraltete Ausnahme 'START.BAT' (Gross-/Kleinschreibung)" 1 "$r"

# 31. Der Ausnahme-LOOKUP ist ebenso case-sensitiv: eine Ausnahme fuer
#     "START.BAT" darf NICHT den echten Befund auf "start.bat" decken. Die
#     Meldungszeile fuer start.bat muss trotz der falsch geschriebenen
#     Ausnahme weiter erscheinen -- Exit-Code allein wuerde einen
#     case-insensitiven Lookup NICHT von der (dann zusaetzlichen) veraltete-
#     Meldung fuer "START.BAT" unterscheiden koennen (WICHTIG 5, "Faelle
#     unterscheiden Ursachen nicht"). Faengt Blindpruefer-M17.
r=$(neues_repo lookup_gross_klein)
printf '*.bat text eol=crlf\n' >> "$r/.gitattributes"
printf 'echo\n' > "$r/start.bat"
git -C "$r" add start.bat
mkdir -p "$r/scripts"
printf 'START.BAT\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "31 Ausnahme 'START.BAT' deckt 'start.bat' nicht (Gross-/Klein)" 1 "$r" "start.bat: eol: crlf"

# 32. Die Ausnahmedatei kann eine letzte Zeile OHNE abschliessenden
#     Zeilenumbruch haben (z. B. von einem Editor ohne Abschluss-Newline
#     gespeichert) -- sie muss trotzdem als Ausnahme gelten. Faengt
#     Gegenpruefer-M11 / Blindpruefer-M06 (`|| [ -n "$zeile" ]` entfernt).
r=$(neues_repo ausnahme_ohne_newline)
printf '*.bat text eol=crlf\n' >> "$r/.gitattributes"
printf 'echo\n' > "$r/start.bat"
git -C "$r" add start.bat
mkdir -p "$r/scripts"
printf 'start.bat\tcrlf' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "32 Ausnahmedatei ohne abschliessenden Zeilenumbruch" 0 "$r"

# 33/34. Ein Befund unter scripts/ bzw. backend/ (nicht nur unter docs/ wie
#     in Fall 19) muss gefunden werden. Faengt Gegenpruefer-M13 (`git
#     ls-files ':!scripts'`) und Blindpruefer-M09 (`':!scripts' ':!backend'`):
#     Dateizahl UND Pruefliste schrumpfen dabei GEMEINSAM, die
#     Zeilenzahl-Probe allein sieht das nicht. WICHTIG: Exit-Code allein
#     reicht NICHT -- ein Mutant, der `git ls-files` filtert, laesst
#     `ls-files --eol` (unveraendert) UND die gefilterte Liste auseinander-
#     laufen; das faengt zwar auch die NEUE Zeilenzahl-Probe fuer die
#     Index-Liste (Fall 40) und liefert dabei ZUFAELLIG ebenfalls Exit 1,
#     aber mit einer ANDEREN Meldung ("gekuerzte Pruefliste" statt der
#     Fundzeile) -- ohne Text-Pruefung waere der Mutant faelschlich als
#     gefangen gezaehlt, obwohl der eigentliche Befund (eigene.md) gar nicht
#     mehr auftaucht (gemessen zu #118 Nacharbeit 1).
r=$(neues_repo pfad_scripts)
printf 'scripts/eigene.md eol=crlf\n' >> "$r/.gitattributes"
mkdir -p "$r/scripts"
printf 'x\n' > "$r/scripts/eigene.md"
git -C "$r" add -A
erwarte_text "33 Befund unter scripts/ (nicht docs/)" 1 "$r" "eigene.md: eol: crlf"

r=$(neues_repo pfad_backend)
printf 'backend/eigene.md eol=crlf\n' >> "$r/.gitattributes"
mkdir -p "$r/backend"
printf 'x\n' > "$r/backend/eigene.md"
git -C "$r" add -A
erwarte_text "34 Befund unter backend/ (nicht docs/)" 1 "$r" "eigene.md: eol: crlf"

# 35/36. Dieselbe Falle auf der INDEX-Seite (`ls-files --eol`): ein
#     CRLF-Blob unter backend/ bzw. frontend/src/. Faengt Blindpruefer-M10
#     (`ls-files --eol ':!backend' ':!frontend/src'`). Dieselbe
#     Text-Pruefung wie bei 33/34, aus demselben Grund (der Mutant laesst
#     `ls-files` und `ls-files --eol` auseinanderlaufen und wird durch die
#     neue Zeilenzahl-Probe zufaellig auch mit Exit 1 gefasst, aber ohne die
#     eigentliche Fundzeile).
r=$(neues_repo index_backend)
mkdir -p "$r/backend"
printf 'x\n' > "$r/backend/eigene.txt"
blob_in_index "$r" backend/eigene.txt 'x\r\n'
erwarte_text "35 CRLF-Blob im Index unter backend/" 1 "$r" "eigene.txt"

r=$(neues_repo index_frontend_src)
mkdir -p "$r/frontend/src"
printf 'x\n' > "$r/frontend/src/eigene.txt"
blob_in_index "$r" frontend/src/eigene.txt 'x\r\n'
erwarte_text "36 CRLF-Blob im Index unter frontend/src/" 1 "$r" "eigene.txt"

# 37. Nur die WINDOWS-Haelfte der Zeilenzahl-Probe gekuerzt (sauberes
#     Repo, keine echten Befunde) -- ein Mutant, der nur die windows-Klausel
#     des Abgleichs entfernt, bleibt sonst unbemerkt, weil die linux-Klausel
#     allein nichts findet. Faengt Gegenpruefer-M16; zusammen mit Fall 38
#     auch M7/M01 (die Probe ganz entfernen).
r=$(neues_repo shim_windows_kuerzung)
git_shim_kuerzt_attr "$TMP/shim37" windows
erwarte_text "37 Windows-Haelfte der check-attr-Pruefliste gekuerzt" 1 "$r" "unpassende Pruefliste" "" "$TMP/shim37"

# 38. BEIDE Haelften um dieselbe Zeile gekuerzt -- ein Mutant, der die
#     Dateizahl durch den (dann ebenso verkuerzten) Linux-Wert ERSETZT
#     (`dateien_anzahl=$attr_linux_anzahl`), macht den Abgleich trivial wahr;
#     eine einseitige Kuerzung wie Fall 37 faengt ihn NICHT (die andere,
#     unveraenderte Seite widerspricht dann immer noch der echten
#     Dateizahl). Faengt Blindpruefer-M14.
#     WICHTIG: Es muessen ALLE DREI Listen (`check-attr` linux, `check-attr`
#     windows, UND `ls-files --eol`) gemeinsam gekuerzt werden -- kuerzt man
#     nur die beiden `check-attr`-Listen, bleibt `ls-files --eol` bei der
#     echten Dateizahl und widerspricht der (unter diesem Mutanten
#     verkuerzten) `dateien_anzahl` weiterhin; der Mutant waere dann nur
#     durch die NEUE Index-Zeilenzahl-Probe zufaellig gefangen, nicht durch
#     die eigentliche Luecke (gemessen zu #118 Nacharbeit 1: mit nur zwei
#     gekuerzten Listen blieb dieser Fall trotz aktivem Mutanten gruen).
r=$(neues_repo shim_beide_kuerzung)
git_shim_kuerzt_alles "$TMP/shim38"
erwarte_text "38 alle drei Pruefliste gleich gekuerzt" 1 "$r" "" "" "$TMP/shim38"

# 39. Ein Befund, der NUR unter core.ignorecase=true (Windows) sichtbar ist,
#     auf einer Datei OHNE .md-Endung. Faengt Blindpruefer-M16 (Windows-Lauf
#     auf `*.md`-Dateien eingeschraenkt UND die Zeilenzahl-Probe entfernt --
#     ohne Letzteres waere JEDES Test-Repo mit einer Nicht-.md-Datei schon an
#     Fall 1 gescheitert).
r=$(neues_repo windows_nur_bat)
printf '*.BAT eol=crlf\n' >> "$r/.gitattributes"
printf 'echo\n' > "$r/start.bat"
git -C "$r" add start.bat
erwarte_text "39 *.BAT eol=crlf nur unter ignorecase=true sichtbar (start.bat)" 1 "$r" "start.bat: eol: crlf"

# 40. Zeilenzahl-Probe der INDEX-Liste (`ls-files --eol`): eine gekuerzte
#     Antwort muss ebenso auffallen wie bei `check-attr` oben -- neu in
#     #118 Nacharbeit 1 (vorher gab es fuer diese Liste gar keinen Abgleich;
#     Selbsttest der eigenen neuen Pruefung).
r=$(neues_repo shim_eol_kuerzung)
git_shim_kuerzt_eol "$TMP/shim40"
erwarte_text "40 ls-files --eol Pruefliste gekuerzt" 1 "$r" "ls-files --eol hat" "" "$TMP/shim40"

# 41. `check-attr` kann selbst fehlschlagen (z. B. eine ungueltige
#     GIT_ATTR_SOURCE) -- eigene Meldung statt eines rohen Git-Fehlers.
#     GIT_ATTR_SOURCE gibt es erst ab git 2.40 -- unter einer aelteren
#     Version kennt git die Variable nicht und dieser Fall wuerde dort ohne
#     jeden Zusammenhang mit dem Waechter rot (nicht UEBERSPRUNGEN, ein
#     EIGENER Zaehler: die "UEBERSPRUNGEN=0 ausserhalb von Windows"-Regel am
#     Fussende gilt nur fuer Fall 14/53, git-Versionen sind kein
#     Windows-Thema; gemessen zu #118 Nacharbeit 2).
git_version_roh=$(git --version 2>/dev/null | sed 's/^git version //')
git_version_major=$(printf '%s' "$git_version_roh" | cut -d. -f1)
git_version_minor=$(printf '%s' "$git_version_roh" | cut -d. -f2)
git_genuegt_2_40=true
case "$git_version_major" in ''|*[!0-9]*) git_genuegt_2_40=false ;; esac
case "$git_version_minor" in ''|*[!0-9]*) git_genuegt_2_40=false ;; esac
if [ "$git_genuegt_2_40" = true ]; then
  if [ "$git_version_major" -lt 2 ]; then
    git_genuegt_2_40=false
  elif [ "$git_version_major" -eq 2 ] && [ "$git_version_minor" -lt 40 ]; then
    git_genuegt_2_40=false
  fi
fi
if [ "$git_genuegt_2_40" = true ]; then
  r=$(neues_repo attr_source_fehler)
  if ausgabe=$(cd "$r" && GIT_ATTR_SOURCE=gibtsnicht sh "$WAECHTER" 2>&1); then ist=0; else ist=$?; fi
  fehler=""
  [ "$ist" = 1 ] || fehler="erwartet Exit 1, bekam $ist"
  if [ -z "$fehler" ] && ! printf '%s\n' "$ausgabe" | grep -Fq -- "check-attr"; then
    fehler="Meldung enthaelt nicht 'check-attr'"
  fi
  # Darf NICHT ueber die generische Zeilenzahl-Meldung "gefangen" werden
  # (Gegenpruefer-B02: der Fehlerzweig selbst wird per `|| true` entfernt,
  # der Ausfall faellt dann zufaellig ueber den Zeilenzahl-Abgleich auf --
  # mit der FALSCHEN Meldung, aber demselben Exit-Code).
  if [ -z "$fehler" ] && printf '%s\n' "$ausgabe" | grep -Fq -- "unpassende Pruefliste"; then
    fehler="Meldung ist die generische Zeilenzahl-Meldung, nicht die echte check-attr-Fehlermeldung"
  fi
  if [ -z "$fehler" ]; then
    BESTANDEN=$((BESTANDEN + 1))
  else
    FEHLGESCHLAGEN=$((FEHLGESCHLAGEN + 1))
    echo "FEHLGESCHLAGEN: 41 GIT_ATTR_SOURCE=gibtsnicht — $fehler (Exit $ist): $ausgabe"
  fi
else
  UEBERSPRUNGEN_VERSION=$((UEBERSPRUNGEN_VERSION + 1))
  echo "UEBERSPRUNGEN (git $git_version_roh < 2.40, kennt GIT_ATTR_SOURCE nicht): 41 GIT_ATTR_SOURCE=gibtsnicht"
fi

# 41b/41c. Deterministische, git-versionsunabhaengige Gegenstuecke zu Fall 41:
#     `check-attr` scheitert je Variante ueber eine Attrappe, nicht ueber
#     eine echte, versionsabhaengige git-Fehlbedienung. Faengt Blindpruefer-
#     M03/M07/M10 (Windows-Variante meldet faelschlich Exit 0, die
#     Fehlermeldung verliert ihren Meldungstext, oder der Exit-Code wird zu
#     2 statt 1) sowie Gegenpruefer-N04/B02 zuverlaessig auf jeder Plattform.
r=$(neues_repo attr_linux_shim_fehler)
git_shim_attr_schlaegt_fehl "$TMP/shim41b" linux "fatal: simulierter check-attr-Fehler (linux)"
erwarte_text "41b check-attr (ignorecase=false) scheitert deterministisch" 1 "$r" \
  "check-attr (ignorecase=false) fehlgeschlagen: fatal: simulierter check-attr-Fehler (linux)" \
  "unpassende Pruefliste" "$TMP/shim41b"

r=$(neues_repo attr_windows_shim_fehler)
git_shim_attr_schlaegt_fehl "$TMP/shim41c" windows "fatal: simulierter check-attr-Fehler (windows)"
erwarte_text "41c check-attr (ignorecase=true) scheitert deterministisch" 1 "$r" \
  "check-attr (ignorecase=true) fehlgeschlagen: fatal: simulierter check-attr-Fehler (windows)" \
  "unpassende Pruefliste" "$TMP/shim41c"

# 41d. `git ls-files --eol` scheitert deterministisch (Exit 2, nicht Gits
#     eigener Code, nicht Exit 0/1) -- faengt Blindpruefer-M02/M09 und
#     Gegenpruefer-N01 (Exit 2 der Eol-Fehlerbehandlung auf 0 bzw. 1
#     geaendert). Anders als Fall 42 (plain `ls-files` scheitert) betrifft
#     das NUR `ls-files --eol`, die Dateiliste selbst bleibt intakt.
r=$(neues_repo eol_shim_fehler)
git_shim_lsfiles_eol_schlaegt_fehl "$TMP/shim41d" "fatal: simulierter ls-files---eol-Fehler"
erwarte_text "41d git ls-files --eol scheitert deterministisch (Exit 2)" 2 "$r" \
  "ls-files --eol fehlgeschlagen: fatal: simulierter ls-files---eol-Fehler" "" "$TMP/shim41d"

# 42. `git ls-files` schlaegt fehl (kaputtes Git) -- Exit 2, nicht Gits
#     eigener Exit-Code (meist 128); der Kopf verspricht nur 0/1/2.
r=$(neues_repo lsfiles_fehler)
git_shim_schlaegt_fehl "$TMP/shim42" ls-files "fatal: simulierter ls-files-Fehler"
# Der genaue stderr-Inhalt MUSS in der Meldung stehen, nicht nur die
# statische Umrahmung "ls-files fehlgeschlagen" -- sonst faengt dieser Fall
# einen Mutanten nicht, der `$(cat "$ls_files_warnung")` aus der Meldung
# entfernt (gemessen zu #118 Nacharbeit 2, Blindpruefer-M06).
erwarte_text "42 git ls-files fehlgeschlagen (Exit 2, nicht 128)" 2 "$r" "ls-files fehlgeschlagen: fatal: simulierter ls-files-Fehler" "" "$TMP/shim42"

# 43. Eine blosse Git-WARNUNG auf stderr bei `check-attr` darf nicht in die
#     Pruefliste gelangen (kein `2>&1`) -- ein sauberes Repo bleibt trotz
#     Warnung gruen. Selbstkontrolle zuerst: Ohne den Nachweis, dass die
#     Attrappe die Warnung UEBERHAUPT erzeugt, entschaerft sich dieser Fall
#     selbst (ein Mutant, der die PATH-Attrappe unwirksam macht, saehe genau
#     gleich aus wie ein Erfolg -- gemessen zu #118 Nacharbeit 2,
#     Gegenpruefer-N34: die Warnung kam in der alten Fassung nie nachweislich
#     an).
r=$(neues_repo attr_stderr_warnung)
git_shim_stderr_warnung "$TMP/shim43"
if ! (PATH="$TMP/shim43:$PATH" command git -c core.ignorecase=false check-attr --stdin eol </dev/null 2>&1 >/dev/null | grep -Fq -- "simulierte Attrappen-Warnung"); then
  FEHLGESCHLAGEN=$((FEHLGESCHLAGEN + 1))
  echo "FEHLGESCHLAGEN: 43-Selbstkontrolle — die Attrappe erzeugt die Warnung nicht, der Fall wuerde nichts pruefen"
else
  erwarte_text "43 Git-Warnung auf stderr bei check-attr bleibt aussen vor" 0 "$r" "" "simulierte Attrappen-Warnung" "$TMP/shim43"
fi

# 44. Eine LEERE, aber erfolgreiche (Exit 0) `check-attr`-Antwort ist ein
#     Befund mit klarer Meldung -- kein stiller Abbruch mitten im Skript
#     (`grep -c .` liefert bei 0 Treffern Exit 1 und riss unter `set -e`
#     bisher den ganzen Waechter ohne jede Ausgabe ab).
r=$(neues_repo attr_leere_antwort)
git_shim_leere_attr_antwort "$TMP/shim44"
erwarte_text "44 leere check-attr-Antwort mit Exit 0 (kein stiller Abbruch)" 1 "$r" "unpassende Pruefliste" "" "$TMP/shim44"

# 45. Ein doppelter Eintrag (derselbe Pfad zweimal) ist selbst ein Befund
#     mit klarer Meldung -- vorher gewann der erste Eintrag still.
r=$(neues_repo ausnahme_doppelt)
mkdir -p "$r/scripts"
printf 'README.md\tlf\nREADME.md\tlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "45 doppelter Eintrag in der Ausnahmedatei" 1 "$r" "doppelter Eintrag"

# 46. Ein drittes Feld (z. B. eine Begruendung) ist nicht erlaubt und
#     selbst ein Befund -- vorher wurde es stillschweigend ignoriert.
r=$(neues_repo ausnahme_drittes_feld)
mkdir -p "$r/scripts"
printf 'README.md\tlf\tBegruendung\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "46 drittes Feld in der Ausnahmedatei" 1 "$r" "drittes Feld"

# 47. Ein leerer Pfad (Zeile beginnt mit Tab) ist selbst ein Befund mit
#     klarer Meldung -- vorher nur eine unleserliche Leerzeile in der
#     veraltet-Liste.
r=$(neues_repo ausnahme_leerer_pfad)
mkdir -p "$r/scripts"
printf '\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "47 leerer Pfad in der Ausnahmedatei" 1 "$r" "leerer Pfad"

# 48. Ein Byte-Order-Mark VOR dem ersten Eintrag der Ausnahmedatei wird
#     abgestreift, nicht als veraltete Ausnahme mit BOM-Muell im Pfad
#     gemeldet.
r=$(neues_repo ausnahme_bom)
printf '*.bat text eol=crlf\n' >> "$r/.gitattributes"
printf 'echo\n' > "$r/start.bat"
git -C "$r" add start.bat
mkdir -p "$r/scripts"
printf '\357\273\277start.bat\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "48 BOM vor dem ersten Ausnahme-Eintrag wird erkannt" 0 "$r"

# 49. Eine mit CRLF gespeicherte Ausnahmedatei (z. B. von einem Editor unter
#     Windows lokal, unversioniert) wird normalisiert -- ein
#     abschliessendes `\r` je Zeile ist kein Teil des Pfads oder Werts.
r=$(neues_repo ausnahme_crlf_datei)
printf '*.bat text eol=crlf\n' >> "$r/.gitattributes"
printf 'echo\n' > "$r/start.bat"
git -C "$r" add start.bat
mkdir -p "$r/scripts"
printf 'start.bat\tcrlf\r\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "49 CRLF-Zeilenende in der Ausnahmedatei wird normalisiert" 0 "$r"

# 50. Die Erfolgsmeldung nennt die Zahl der angewendeten Ausnahmen -- sonst
#     behauptet sie "alle eol=lf", obwohl eine Ausnahme gegriffen hat.
r=$(neues_repo erfolg_nennt_ausnahmen)
printf '*.bat text eol=crlf\n' >> "$r/.gitattributes"
printf 'echo\n' > "$r/start.bat"
git -C "$r" add start.bat
mkdir -p "$r/scripts"
printf 'start.bat\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "50 Erfolgsmeldung nennt Zahl der Ausnahmen" 0 "$r" "1 Ausnahme"

# 51. Ein Pfad MIT Leerzeichen in der Ausnahmedatei ist eine ganz normale
#     Zeile, kein Kommentar und keine Leerzeile. Faengt Blindpruefer-M12
#     (der Skip-Filter `''|'#'*` bekommt `|*" "*` dazu und ueberspringt jede
#     Zeile mit einem Leerzeichen irgendwo -- trifft fast jeden Pfad mit
#     Leerzeichen).
r=$(neues_repo ausnahme_pfad_leerzeichen)
printf '*.bat text eol=crlf\n' >> "$r/.gitattributes"
printf 'echo\n' > "$r/a b.bat"
git -C "$r" add -A
mkdir -p "$r/scripts"
printf 'a b.bat\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "51 Ausnahme-Pfad mit Leerzeichen greift" 0 "$r"

# 52. Ein "#" MITTEN im Pfad (nicht am Zeilenanfang) macht eine
#     Ausnahme-Zeile nicht zum Kommentar. Faengt Blindpruefer-M22 (der
#     Skip-Filter `''|'#'*` wird zu `''|*'#'*` und ueberspringt jede Zeile,
#     die irgendwo ein "#" enthaelt).
r=$(neues_repo ausnahme_pfad_raute)
printf 'echo\n' > "$r/a#b.bat"
printf '*.bat text eol=crlf\n' >> "$r/.gitattributes"
git -C "$r" add -A
mkdir -p "$r/scripts"
printf 'a#b.bat\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "52 Ausnahme-Pfad mit '#' mitten im Namen greift" 0 "$r"

# 53. Derselbe taeuschende Pfad wie in Fall 14 (": eol: lf" im Namen), aber
#     diesmal MIT einer passenden Ausnahme -- die muss greifen. Faengt
#     Blindpruefer-M11 (`pfad="${z%: eol: *}"` durch `${z%%: eol: *}`
#     ersetzt: die kuerzeste statt der laengsten Endung wird abgeschnitten,
#     der extrahierte Pfad waere dann "x" statt "x: eol: lf" und die
#     Ausnahme faende ihn nicht). Windows lehnt ':' in Pfaden ab (siehe
#     Fall 14); die Fusszeile unten erzwingt UEBERSPRUNGEN=0 ausserhalb von
#     Windows.
r=$(neues_repo pfad_laengster)
printf 'x* eol=crlf\n' >> "$r/.gitattributes"
if blob_in_index "$r" 'x: eol: lf' 'a\n' 2>/dev/null; then
  mkdir -p "$r/scripts"
  printf 'x: eol: lf\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
  erwarte "53 Pfad-Extraktion bei ': eol: lf' im Namen, mit passender Ausnahme" 0 "$r"
else
  UEBERSPRUNGEN=$((UEBERSPRUNGEN + 1))
  echo "UEBERSPRUNGEN: 53 Pfad mit ':' (auf diesem System nicht anlegbar)"
fi

# ---------------------------------------------------------------------------
# Nacharbeit 2 zu #118: die Luecken aus dem Bau-Brief (Faelle 54-73).
# ---------------------------------------------------------------------------

# 54/55. `core.quotePath=true` wird vom Waechter ERZWUNGEN, unabhaengig vom
#     lokalen Wert (hier bewusst auf false gesetzt) -- ein Pfad mit
#     Sonderzeichen (Umlaut) erscheint dann in Gits C-Quoting, und nur eine
#     Ausnahme in GENAU dieser quotierten Form greift; die rohe UTF-8-Form
#     greift NICHT. Faengt Blindpruefer-M01, Gegenpruefer-N06/N07.
r=$(neues_repo umlaut_quotepath)
git -C "$r" config core.quotePath false
printf '*.bat text eol=crlf\n' >> "$r/.gitattributes"
umlaut_datei=$(printf 't\303\244.bat')
printf 'echo\n' > "$r/$umlaut_datei"
git -C "$r" add -A
mkdir -p "$r/scripts"
printf '"t\\303\\244.bat"\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "54 Umlaut-Pfad, Ausnahme in C-Quoting-Form greift (core.quotePath lokal false)" 0 "$r"

printf '%s\tcrlf\n' "$umlaut_datei" > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "55 Umlaut-Pfad, Ausnahme in roher UTF-8-Form greift NICHT" 1 "$r"

# 56/57. Der erlaubte WERT wird exakt und case-sensitiv verglichen -- eine
#     Ausnahme fuer 'crlf' deckt weder 'CRLF' (Grossbuchstaben) noch 'unset'
#     (`-eol`). Faengt Blindpruefer-M05/M25 (Wert-Vergleich wird zu einem
#     Joker fuer die woertliche Zeichenkette "crlf" bzw. case-insensitiv).
r=$(neues_repo wert_grossbuchstaben_ausnahme)
printf '*.md eol=CRLF\n' >> "$r/.gitattributes"
mkdir -p "$r/scripts"
printf 'README.md\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "56 Wert 'CRLF' (Grossbuchstaben) mit Ausnahme-Wert 'crlf' bleibt Befund" 1 "$r" "README.md: eol: CRLF"

r=$(neues_repo wert_unset_ausnahme)
printf '*.md -eol\n' >> "$r/.gitattributes"
mkdir -p "$r/scripts"
printf 'README.md\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "57 Wert 'unset' (-eol) mit Ausnahme-Wert 'crlf' bleibt Befund" 1 "$r" "README.md: eol: unset"

# 58/59. Ein Pfad-Ausschluss bei `git ls-files`/`ls-files --eol` (z. B.
#     ':!*.sh' oder ':!.*') nimmt eine Datei aus Pruefliste UND Dateizahl
#     zugleich -- eine Zeilenzahl-Probe sieht das nicht. Faengt
#     Blindpruefer-M04 (Ausschluss von *.sh/*.py) und M22 (Ausschluss von
#     Punkt-Pfaden).
r=$(neues_repo pfad_xsh)
printf 'x.sh eol=crlf\n' >> "$r/.gitattributes"
printf 'echo\n' > "$r/x.sh"
git -C "$r" add -A
erwarte_text "58 Befund unter x.sh (Pfad-Ausschluss *.sh)" 1 "$r" "x.sh: eol: crlf"

r=$(neues_repo pfad_punktverzeichnis)
mkdir -p "$r/.husky"
printf '.husky/pre-commit eol=crlf\n' >> "$r/.gitattributes"
printf 'echo\n' > "$r/.husky/pre-commit"
git -C "$r" add -A
erwarte_text "59 Befund unter .husky/ (Pfad-Ausschluss Punkt-Pfade)" 1 "$r" "pre-commit: eol: crlf"

# 60/61. `-ne`, nicht `-lt`: eine VERLAENGERTE Pruefliste (eine erfundene
#     Zusatzzeile) ist ebenso ein Befund wie eine gekuerzte. Faengt
#     Gegenpruefer-N08 (Zeilenzahl-Abgleich von `-ne` auf `-lt` geaendert --
#     "zu wenig" bleibt dann ein Befund, "zu viel" nicht mehr).
r=$(neues_repo verlaengerte_pruefliste_attr)
git_shim_verlaengert_attr "$TMP/shim60"
erwarte_text "60 check-attr liefert eine Zeile zu viel (verlaengerte Pruefliste, N08)" 1 "$r" "unpassende Pruefliste" "" "$TMP/shim60"

r=$(neues_repo verlaengerte_pruefliste_eol)
git_shim_verlaengert_eol "$TMP/shim61"
erwarte_text "61 ls-files --eol liefert eine Zeile zu viel (verlaengerte Pruefliste, N08)" 1 "$r" "unpassende Pruefliste" "" "$TMP/shim61"

# 62. Die veraltete-Ausnahme-Pruefung nutzt `grep -Fxq -- "$pfad"` MIT dem
#     Trenner `--`: ein Ausnahme-Pfad, der selbst wie eine grep-Option
#     aussieht (`-eREADME.md`), darf `grep` nicht dazu bringen, ihn als
#     Option statt als Suchtext zu lesen (das wuerde faelschlich "README.md"
#     im echten Dateibestand treffen und die veraltete Ausnahme verstecken).
#     Faengt Gegenpruefer-B21 (`--` entfernt).
r=$(neues_repo veraltet_dash_e_pfad)
mkdir -p "$r/scripts"
dash_e_pfad='-eREADME.md'
printf '%s\tlf\n' "$dash_e_pfad" > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "62 veraltete Ausnahme mit Pfad '-eREADME.md' (grep ohne --)" 1 "$r" "veraltete Ausnahme"

# 63. Auf der INDEX-Seite wird der Pfad per `cut -f2` (TAB-getrennt) statt
#     `awk '{print $NF}'` (leerzeichen-getrennt) gelesen -- ein Pfad MIT
#     Leerzeichen muss vollstaendig ankommen, nicht nur sein letztes Wort.
#     Faengt Gegenpruefer-N24.
r=$(neues_repo index_leerzeichen_ausnahme)
printf 'x\n' > "$r/a b.txt"
blob_in_index "$r" 'a b.txt' 'x\r\n'
mkdir -p "$r/scripts"
printf 'a b.txt\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte "63 Index-Pfad mit Leerzeichen, Ausnahme greift (cut -f2, nicht awk NF)" 0 "$r"

# 64. Dieselbe Trennung von STDOUT/STDERR wie bei Fall 43, aber fuer die
#     WINDOWS-Variante (core.ignorecase=true) -- Fall 43 deckt nur Linux.
#     Faengt Blindpruefer-M08, Gegenpruefer-N27 (`2>&1` statt eigener
#     Umlenkung fuer die Windows-Variante).
r=$(neues_repo attr_stderr_warnung_windows)
git_shim_stderr_warnung_win "$TMP/shim64"
if ! (PATH="$TMP/shim64:$PATH" command git -c core.ignorecase=true check-attr --stdin eol </dev/null 2>&1 >/dev/null | grep -Fq -- "simulierte Attrappen-Warnung (windows)"); then
  FEHLGESCHLAGEN=$((FEHLGESCHLAGEN + 1))
  echo "FEHLGESCHLAGEN: 64-Selbstkontrolle — die Attrappe erzeugt die Warnung nicht, der Fall wuerde nichts pruefen"
else
  erwarte_text "64 Git-Warnung auf stderr bei check-attr (windows) bleibt aussen vor" 0 "$r" "" "simulierte Attrappen-Warnung (windows)" "$TMP/shim64"
fi

# 65/66. Angewandte statt blosser Eintraege: eine Ausnahme fuer eine bereits
#     SAUBERE, versionierte Datei greift nie und ist selbst ein Befund
#     ("nutzlose Ausnahme") -- die Erfolgsmeldung zaehlt nur tatsaechlich
#     ANGEWANDTE Ausnahmen (gemessen zu #118 Nacharbeit 2: vorher liess sich
#     das mit "1 Ausnahme(n) angewendet" schoenreden, obwohl nichts griff).
r=$(neues_repo nutzlose_ausnahme)
mkdir -p "$r/scripts"
printf 'README.md\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "65 nutzlose Ausnahme auf sauberer, versionierter Datei ist ein Befund" 1 "$r" "nutzlose Ausnahme"

r=$(neues_repo zwei_angewandte_ausnahmen)
printf '*.bat text eol=crlf\n' >> "$r/.gitattributes"
printf 'echo\n' > "$r/a.bat"
printf 'echo\n' > "$r/b.bat"
git -C "$r" add -A
mkdir -p "$r/scripts"
printf 'a.bat\tcrlf\nb.bat\tcrlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "66 Erfolgsmeldung zaehlt zwei tatsaechlich angewandte Ausnahmen" 0 "$r" "2 Ausnahme"

# 67/68/69. Eine Zeile ganz ohne TAB (kein Wert-Feld), ein CR mitten in der
#     Zeile und ein doppeltes CR am Ende sind je ein eigener Formatbefund --
#     vorher wurden sie stillschweigend als Pfad mit leerem/verunreinigtem
#     Wert bzw. Teil des Pfads/Werts behandelt.
r=$(neues_repo ausnahme_ohne_tab)
mkdir -p "$r/scripts"
printf 'README.md\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "67 Zeile ohne TAB in der Ausnahmedatei ist ein Formatbefund" 1 "$r" "kein TAB"

r=$(neues_repo ausnahme_cr_mitten_in_zeile)
mkdir -p "$r/scripts"
printf 'README.md\rx\tlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "68 CR mitten in der Zeile der Ausnahmedatei ist ein Formatbefund" 1 "$r" "CR mitten in der Zeile"

r=$(neues_repo ausnahme_cr_doppelt_am_ende)
mkdir -p "$r/scripts"
printf 'README.md\tlf\r\r\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
erwarte_text "69 doppeltes CR am Ende einer Zeile der Ausnahmedatei ist ein Formatbefund" 1 "$r" "CR mitten in der Zeile"

# 70/71/72. Ein leerer oder fehlender Index (`GIT_INDEX_FILE` zeigt ins
#     Leere) darf einen Format-Befund der Ausnahmedatei nicht verdecken und
#     macht jeden eingetragenen Pfad zwangslaeufig veraltet (0 versionierte
#     Dateien) -- vorher meldete die alte Fassung hier sofort "0 Dateien"
#     mit Exit 0, noch bevor die Ausnahmedatei ueberhaupt gelesen wurde.
#     Fall 72 ist die Gegenprobe: OHNE Ausnahmedatei bleibt 0 Dateien
#     weiterhin folgenlos (Exit 0) -- die neue Pruefung darf das nicht
#     mitreissen.
r=$(neues_repo index_fehlt_mit_formatfehler)
mkdir -p "$r/scripts"
printf 'README.md\tlf\tBegruendung\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
if ausgabe=$(cd "$r" && GIT_INDEX_FILE="$TMP/idx_fehlt70" sh "$WAECHTER" 2>&1); then ist=0; else ist=$?; fi
fehler70=""
[ "$ist" = 1 ] || fehler70="erwartet Exit 1, bekam $ist"
if [ -z "$fehler70" ] && ! printf '%s\n' "$ausgabe" | grep -Fq -- "drittes Feld"; then
  fehler70="Meldung enthaelt nicht 'drittes Feld'"
fi
if [ -z "$fehler70" ]; then
  BESTANDEN=$((BESTANDEN + 1))
else
  FEHLGESCHLAGEN=$((FEHLGESCHLAGEN + 1))
  echo "FEHLGESCHLAGEN: 70 fehlender Index verdeckt Format-Befund nicht — $fehler70 (Exit $ist): $ausgabe"
fi

r=$(neues_repo index_fehlt_mit_ausnahme)
mkdir -p "$r/scripts"
printf 'README.md\tlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
if ausgabe=$(cd "$r" && GIT_INDEX_FILE="$TMP/idx_fehlt71" sh "$WAECHTER" 2>&1); then ist=0; else ist=$?; fi
fehler71=""
[ "$ist" = 1 ] || fehler71="erwartet Exit 1, bekam $ist"
if [ -z "$fehler71" ] && ! printf '%s\n' "$ausgabe" | grep -Fq -- "veraltete Ausnahme"; then
  fehler71="Meldung enthaelt nicht 'veraltete Ausnahme'"
fi
if [ -z "$fehler71" ]; then
  BESTANDEN=$((BESTANDEN + 1))
else
  FEHLGESCHLAGEN=$((FEHLGESCHLAGEN + 1))
  echo "FEHLGESCHLAGEN: 71 fehlender Index meldet Ausnahme nicht als veraltet — $fehler71 (Exit $ist): $ausgabe"
fi

r="$TMP/leer_0dateien"; mkdir -p "$r"
git -C "$r" init -q
git -C "$r" config user.email probe@example.invalid
git -C "$r" config user.name probe
erwarte "72 0 Dateien, keine Ausnahmedatei bleibt Exit 0" 0 "$r"

# 73. Eine VORHANDENE, aber unlesbare Ausnahmedatei ist "Werkzeug kaputt"
#     (Exit 2), kein Befund und kein stiller Erfolg -- je nach `sh` liesse
#     eine fehlschlagende Umlenkung unter `set -eu` sonst einen
#     uneinheitlichen, shell-eigenen Fehlertext durch. `chmod 000` entzieht
#     den Lesezugriff auf ZWEI Arten nicht: unter NTFS/Windows dem
#     Eigentuemer nie (gemessen: `[ -r ]` bleibt wahr), und auf jedem System
#     nicht dem ROOT-Benutzer (gemessen in einem Docker-Container: dort laeuft
#     alles als root, `[ -r ]` bleibt auch unter Linux wahr -- #118
#     Nacharbeit 2). Eigener Zaehler statt UEBERSPRUNGEN: Die Windows-Regel am
#     Fussende gilt nur fuer Fall 14/53 (Doppelpunkt im Pfad); ein
#     root-Container ist kein Windows-Fall und darf die Regel nicht ausloesen.
r=$(neues_repo ausnahme_unlesbar)
mkdir -p "$r/scripts"
printf 'README.md\tlf\n' > "$r/scripts/zeilenenden-ausnahmen.txt"
chmod 000 "$r/scripts/zeilenenden-ausnahmen.txt"
if [ -r "$r/scripts/zeilenenden-ausnahmen.txt" ]; then
  UEBERSPRUNGEN_BERECHTIGUNG=$((UEBERSPRUNGEN_BERECHTIGUNG + 1))
  echo "UEBERSPRUNGEN (Berechtigung): 73 unlesbare Ausnahmedatei (dieses System/dieser Benutzer entzieht den Lesezugriff nicht)"
  chmod 644 "$r/scripts/zeilenenden-ausnahmen.txt"
else
  erwarte_text "73 unlesbare Ausnahmedatei (Exit 2)" 2 "$r" "nicht lesbar"
  chmod 644 "$r/scripts/zeilenenden-ausnahmen.txt"
fi

# 74. Ohne jede angewandte Ausnahme darf die Erfolgsmeldung keine Ausnahme-
#     Zahl nennen -- faengt einen Mutanten, der den neuen "$angewandt_zahl
#     -gt 0"-Zweig durch "-ge 0" ersetzt (dasselbe Muster wie Blindpruefer-
#     M15 auf der alten `ausnahmen_anzahl`-Zaehlung).
r=$(neues_repo ohne_jede_ausnahme)
erwarte_text "74 Erfolgsmeldung ohne Ausnahmen nennt keine Ausnahmezahl" 0 "$r" "" "Ausnahme"

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

echo "$BESTANDEN bestanden, $FEHLGESCHLAGEN fehlgeschlagen, $UEBERSPRUNGEN uebersprungen, $UEBERSPRUNGEN_VERSION wegen git-Mindestversion uebersprungen, $UEBERSPRUNGEN_BERECHTIGUNG wegen Berechtigung uebersprungen"
[ "$FEHLGESCHLAGEN" -eq 0 ]
