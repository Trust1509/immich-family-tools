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
# Umwandlung ganz auf, `check-attr eol` bleibt dabei `lf`. Ausserdem teilen
# sich Attribut- und Index-Seite EINEN erlaubten Wert je Pfad (eine Datei mit
# `-text -eol`, deren Blob CRLF traegt, laesst sich nicht ausnehmen, ohne dass
# derselbe Eintrag auch faelschlich die Attribut-Seite deckte) — bewusst so
# gelassen (kein bekannter Fall braucht zwei Werte je Pfad; #118 Nacharbeit 1).
#
# AUSNAHMEN: zeilenweise in `scripts/zeilenenden-ausnahmen.txt` IM GEPRUEFTEN
# REPO (relativ zum Arbeitsbaum-Toplevel, nicht neben diesem Skript-File --
# die Selbstprobe prueft viele verschiedene Wegwerf-Repos gegen denselben
# Skript-Text und darf dabei nie die Ausnahmedatei DIESES Projekts lesen),
# je Zeile `<Pfad><TAB><erlaubter Wert>` (Wert z. B. `crlf` -- der Wert, den
# `check-attr`/`ls-files --eol` fuer GENAU diesen Pfad melden soll, nicht
# "alles ausser lf"). Der Pfad wird exakt und wortwoertlich verglichen (kein
# Glob, kein Praefix-, kein Muster-Vergleich, keine Gross-/Kleinschreibungs-
# Toleranz auf PFAD ODER WERT -- ein Wert `crlf` deckt weder `CRLF` noch
# `unset` (gemessen zu #118 Nacharbeit 2, Selbstprobe Faelle 54/55). Ein
# eingetragener Pfad, der nicht mehr versioniert ist, ist selbst ein Befund
# (veraltete Ausnahme) -- ebenso ein doppelter Eintrag, ein drittes Feld,
# eine Zeile ganz ohne TAB, ein leerer Pfad oder ein CR mitten in der Zeile
# (siehe unten, "Format der Ausnahmedatei"). Und ebenso ein Eintrag, der nie
# GREIFT (die eingetragene Datei ist sauber) -- die Erfolgsmeldung zaehlt nur
# tatsaechlich ANGEWANDTE Ausnahmen, nicht blosse Eintraege (gemessen zu #118
# Nacharbeit 2: eine Ausnahme auf einer bereits sauberen Datei blieb sonst
# unbemerkt stehen und die Erfolgsmeldung behauptete trotzdem, sie sei
# "angewendet" worden). Die Datei wird bewusst aus dem ARBEITSBAUM gelesen,
# nicht aus dem Index: Ein lokaler Lauf soll eine gerade erst bearbeitete,
# noch nicht gestagte Ausnahme sofort sehen; in der CI (frischer Checkout)
# sind Arbeitsbaum und Index ohnehin gleich, das Gate dort ist davon nicht
# betroffen. Heute: keine.
#
# #118 loeste damit den frueheren Mechanismus ab (Nacharbeit zu #104):
# `for a in $AUSNAHMEN` wertete die ungequotete Variable als Glob aus (`"*
# */* */*/*"` gab alles frei), konnte keinen Pfad mit Leerzeichen ausnehmen,
# und liess "alles ausser lf" durch statt eines konkreten Werts.
#
# Exit 0: alles LF. Exit 1: Befund, mit Liste. Exit 2: kein Arbeitsbaum eines
# Git-Repos (auch: bare, innerhalb von .git) ODER git selbst schlaegt fehl
# (`ls-files`, `ls-files --eol`) ODER die Ausnahmedatei existiert, ist aber
# nicht lesbar -- alles drei "das Werkzeug ist kaputt", nicht "ein Befund"
# (vorher liess ein fehlschlagendes `git ls-files` seinen eigenen Exit-Code
# (meist 128) durchfallen; jetzt einheitlich 2, mit eigener Meldung, wie beim
# fehlenden Arbeitsbaum oben. `check-attr` bleibt bei Exit 1 -- es ist zwar
# auch "Werkzeug kaputt", aber ein Fehlschlag dort ist praktisch nicht von
# einem Befund zu unterscheiden, ohne die Fallunterscheidung unnoetig zu
# verkomplizieren; die Meldung nennt die Ursache trotzdem woertlich). Ein
# leerer oder fehlender Index (0 Dateien) ist nur dann Exit 0, wenn die
# Ausnahmedatei selbst keinen Format-Befund und keinen Eintrag traegt --
# sonst waere jeder Eintrag zwangslaeufig veraltet (0 versionierte Dateien)
# und ein Format-Fehler bliebe unbemerkt (gemessen zu #118 Nacharbeit 2).
set -eu

oben=$(git rev-parse --show-toplevel 2>/dev/null) || oben=""
[ -n "$oben" ] || { echo "zeilenenden: kein Arbeitsbaum eines Git-Repos"; exit 2; }
cd "$oben"

# `-c core.quotePath=true`: Das Ergebnis von `ls-files`/`check-attr` muss mit
# der Schreibweise in `zeilenenden-ausnahmen.txt` zusammenpassen, egal welchen
# `core.quotePath`-Wert die aufrufende Umgebung zufaellig gesetzt hat (lokal
# oft `false`, CI-Default `true`) -- sonst ist ein exakt gequoteter
# Ausnahme-Eintrag nur auf EINER der beiden Seiten wirksam (gemessen zu #118
# Nacharbeit 1, siehe `zeilenenden-ausnahmen.txt`).
git() {
  command git -c core.quotePath=true "$@"
}

ausnahmen_datei="scripts/zeilenenden-ausnahmen.txt"

aufraeumen_dateien=""
aufraeumen() {
  # shellcheck disable=SC2086
  [ -z "$aufraeumen_dateien" ] || rm -f $aufraeumen_dateien
}
trap aufraeumen EXIT

# Die Ausnahmedatei wird EINMAL eingelesen, normalisiert (ein Byte-Order-Mark
# in der ERSTEN ZEILE DER DATEI abgestreift -- unabhaengig davon, ob diese
# Zeile ein Kommentar oder ein Eintrag ist; ein abschliessendes `\r` auf jeder
# Zeile entfernt -- ein lokal mit CRLF gespeicherter Eintrag griffe sonst
# unter Git-Bash, aber nicht unter Linux, still verschieden) und dabei auf
# Format-Fehler geprueft: doppelter Pfad, ein drittes Feld, ein leerer Pfad,
# eine Zeile ganz ohne TAB (kein Wert-Feld), ein zusaetzliches CR mitten in
# der Zeile oder ein doppeltes CR am Ende (Windows-Editoren liessen das sonst
# durch, waehrend ein Linux-`read` es unveraendert als Teil des Pfads oder
# Werts behandelt -- auf beiden Systemen gleich streng). Jeder dieser Faelle
# ist selbst ein Befund mit eigener Meldung (vorher: doppelt griff der erste
# Eintrag still, ein drittes Feld wurde stillschweigend ignoriert, ein leerer
# Pfad erschien nur als unleserliche Leerzeile in der veraltet-Liste, eine
# Zeile ohne TAB wurde als Pfad mit leerem, nie treffendem Wert akzeptiert,
# und ein CR mitten in der Zeile blieb Teil des Pfads oder Werts).
ausnahmen_norm=""
ausnahmen_anzahl=0
befund_ausnahmeformat=""
if [ -f "$ausnahmen_datei" ]; then
  # Eine vorhandene, aber unlesbare Ausnahmedatei (z. B. Rechte entzogen) ist
  # "Werkzeug kaputt", kein Befund -- und je nach `sh`-Implementierung liesse
  # eine fehlschlagende Umlenkung unter `set -eu` sonst einen uneinheitlichen,
  # shell-eigenen Fehlertext durch (dash: eigener Exit-Code ohne unser
  # `zeilenenden:`-Praefix; manche `ash`-Varianten: still Exit 0).
  if [ ! -r "$ausnahmen_datei" ]; then
    echo "zeilenenden: $ausnahmen_datei ist nicht lesbar"
    exit 2
  fi
  ausnahmen_norm=$(mktemp)
  gesehene_pfade=$(mktemp)
  aufraeumen_dateien="$aufraeumen_dateien $ausnahmen_norm $gesehene_pfade"
  cr=$(printf '\r')
  bom=$(printf '\357\273\277')
  zeilennr=0
  while IFS= read -r roh || [ -n "$roh" ]; do
    zeilennr=$((zeilennr + 1))
    zeile="${roh%"$cr"}"
    if [ "$zeilennr" -eq 1 ]; then
      zeile="${zeile#"$bom"}"
    fi
    case "$zeile" in
      ''|'#'*) continue ;;
    esac
    case "$zeile" in
      *"$cr"*)
        befund_ausnahmeformat="${befund_ausnahmeformat}zeilenenden: $ausnahmen_datei Zeile $zeilennr: zusaetzliches CR mitten in der Zeile oder doppelt am Ende
"
        continue
        ;;
    esac
    pfad=$(printf '%s\n' "$zeile" | cut -f1)
    felder=$(printf '%s\n' "$zeile" | awk -F'\t' '{print NF}')
    if [ -z "$pfad" ]; then
      befund_ausnahmeformat="${befund_ausnahmeformat}zeilenenden: $ausnahmen_datei Zeile $zeilennr: leerer Pfad
"
      continue
    fi
    if [ "$felder" -lt 2 ]; then
      befund_ausnahmeformat="${befund_ausnahmeformat}zeilenenden: $ausnahmen_datei Zeile $zeilennr ($pfad): kein TAB (nur <Pfad>, kein <Wert>-Feld)
"
      continue
    fi
    if [ "$felder" -gt 2 ]; then
      befund_ausnahmeformat="${befund_ausnahmeformat}zeilenenden: $ausnahmen_datei Zeile $zeilennr ($pfad): drittes Feld ist nicht erlaubt (nur <Pfad><TAB><Wert>)
"
    fi
    if grep -Fxq -- "$pfad" "$gesehene_pfade" 2>/dev/null; then
      befund_ausnahmeformat="${befund_ausnahmeformat}zeilenenden: $ausnahmen_datei Zeile $zeilennr: doppelter Eintrag fuer $pfad (der erste gewinnt)
"
    else
      printf '%s\n' "$pfad" >> "$gesehene_pfade"
    fi
    printf '%s\n' "$zeile" >> "$ausnahmen_norm"
    ausnahmen_anzahl=$((ausnahmen_anzahl + 1))
  done < "$ausnahmen_datei"
fi

# Gibt fuer Pfad $1 den erlaubten Wert aus der (normalisierten) Ausnahmedatei
# aus (Exit 0), oder nichts mit Exit 1, wenn $1 dort nicht eingetragen ist.
# Zeilenweise, exakter String-Vergleich ("[" "="  ist keine Muster-, sondern
# eine reine Textprobe) -- kein Glob, kein Praefix-Vergleich, kein
# `case`-Muster, keine Gross-/Kleinschreibungs-Toleranz.
ausnahme_wert() {
  [ -n "$ausnahmen_norm" ] || return 1
  while IFS= read -r zeile; do
    pfad=$(printf '%s\n' "$zeile" | cut -f1)
    wert=$(printf '%s\n' "$zeile" | cut -f2)
    if [ "$1" = "$pfad" ]; then
      printf '%s' "$wert"
      return 0
    fi
  done < "$ausnahmen_norm"
  return 1
}

# Erst die Dateiliste, getrennt: Scheitert `git ls-files`, bricht `set -e`
# ohne die eigene Fehlerbehandlung ab und liesse Gits eigenen Exit-Code (meist
# 128) durchfallen -- der Kopf verspricht aber nur 0/1/2. Eigene Meldung,
# eigener Exit 2 ("Werkzeug kaputt", nicht "Befund"). STDERR getrennt
# gehalten (kein `2>&1`), aus demselben Grund wie bei `check-attr` unten:
# eine blosse Warnung auf stderr soll nicht in die Dateiliste einfliessen.
ls_files_warnung=$(mktemp)
aufraeumen_dateien="$aufraeumen_dateien $ls_files_warnung"
if ! dateien=$(git ls-files 2>"$ls_files_warnung"); then
  echo "zeilenenden: git ls-files fehlgeschlagen: $(cat "$ls_files_warnung")"
  exit 2
fi
if [ -z "$dateien" ]; then
  # 0 Dateien ist nur dann folgenlos, wenn die Ausnahmedatei selbst sauber
  # ist: Ein leerer oder fehlender Index (z. B. `GIT_INDEX_FILE` zeigt ins
  # Leere, `.git/index` geloescht) darf einen Format-Befund in der
  # Ausnahmedatei nicht verdecken -- und jeder eingetragene Ausnahme-Pfad ist
  # gegen 0 versionierte Dateien zwangslaeufig veraltet (gemessen zu #118
  # Nacharbeit 2: die alte Fassung meldete hier "0 Dateien" mit Exit 0, noch
  # bevor die Ausnahmedatei ueberhaupt geprueft wurde).
  if [ -n "$befund_ausnahmeformat" ] || [ -n "$ausnahmen_norm" ]; then
    if [ -n "$befund_ausnahmeformat" ]; then
      printf '%s' "$befund_ausnahmeformat"
    fi
    if [ -n "$ausnahmen_norm" ] && [ -s "$ausnahmen_norm" ]; then
      echo "zeilenenden: veraltete Ausnahme(n) in $ausnahmen_datei (0 Dateien versioniert):"
      cut -f1 "$ausnahmen_norm"
    fi
    exit 1
  fi
  echo "zeilenenden: 0 Dateien"
  exit 0
fi
dateien_anzahl=$(printf '%s\n' "$dateien" | grep -c . || true)

# `check-attr` gibt je Datei eine Zeile "<pfad>: eol: <wert>". Alles ausser
# "lf" ist ein Befund — auch "unspecified" (Regel fehlt), "unset" (`-eol`),
# "set" (`eol` ohne Wert) und "LF" (Wert in Grossbuchstaben). Eigene
# Fehlermeldung statt eines stillen `set -e`-Abbruchs mit Gits eigenem Text.
# STDOUT und STDERR bleiben getrennt (kein `2>&1`): Eine blosse Git-Warnung
# auf stderr (z. B. zu einem negativen `.gitattributes`-Muster) landete sonst
# als zusaetzliche Zeile in der Pruefliste und taeuschte dort faelschlich
# eine gekuerzte Pruefliste vor (gemessen zu #118 Nacharbeit 1).
attr_linux_warnung=$(mktemp)
attr_windows_warnung=$(mktemp)
aufraeumen_dateien="$aufraeumen_dateien $attr_linux_warnung $attr_windows_warnung"
if ! attr_linux=$(printf '%s\n' "$dateien" | git -c core.ignorecase=false check-attr --stdin eol 2>"$attr_linux_warnung"); then
  echo "zeilenenden: git check-attr (ignorecase=false) fehlgeschlagen: $(cat "$attr_linux_warnung")"
  exit 1
fi
if ! attr_windows=$(printf '%s\n' "$dateien" | git -c core.ignorecase=true check-attr --stdin eol 2>"$attr_windows_warnung"); then
  echo "zeilenenden: git check-attr (ignorecase=true) fehlgeschlagen: $(cat "$attr_windows_warnung")"
  exit 1
fi

# Zeilenzahl von `check-attr` gegen die Dateizahl pruefen: Eine verkuerzte
# Pipe davor (z. B. `head -n 30`) blieb sonst gruen und meldete trotzdem
# Erfolg fuer `$dateien_anzahl` Dateien -- die Zahl kam aus `$dateien`, nicht
# aus den tatsaechlich geprueften Zeilen (gemessen zu #118). `|| true` haengt
# an jedem `grep -c`, weil `grep` bei 0 Treffern Exit 1 liefert: Unter
# `set -e` risse das den Waechter sonst still ab, ohne je die eigene
# Fehlermeldung unten zu zeigen (gemessen zu #118 Nacharbeit 1) -- eine leere
# `check-attr`-Antwort soll ein BEFUND sein, kein stiller Absturz.
attr_linux_anzahl=$(printf '%s\n' "$attr_linux" | grep -c . || true)
attr_windows_anzahl=$(printf '%s\n' "$attr_windows" | grep -c . || true)
# `-ne`, nicht `-lt`: eine PIPE, die die Liste VERLAENGERT (z. B. eine
# Git-Warnung, die entgegen der Trennung oben doch in die Liste rutscht),
# ist ebenso ein Befund wie eine, die sie kuerzt -- ein reines "zu wenig"
# uebersaehe eine zu LANGE Liste (gemessen zu #118 Nacharbeit 2).
if [ "$attr_linux_anzahl" -ne "$dateien_anzahl" ] || [ "$attr_windows_anzahl" -ne "$dateien_anzahl" ]; then
  echo "zeilenenden: git check-attr hat $attr_linux_anzahl/$attr_windows_anzahl Zeilen fuer $dateien_anzahl Dateien geliefert (unpassende Pruefliste, zu kurz oder zu lang?)"
  exit 1
fi

# Der Anker `$` ist Absicht: ohne ihn wuerde `grep -v` eine Zeile wie
# "a.md: eol: lfx" schon deshalb ausschliessen, weil sie die Zeichenkette
# ": eol: lf" als Praefix enthaelt -- der Befund verschwindet lautlos
# (gemessen zu #118, Selbstprobe Fall 18).
falsches_attribut=$(printf '%s\n%s\n' "$attr_linux" "$attr_windows" | grep -v ': eol: lf$' | sort -u || true)

# `ls-files --eol`: erste Spalte ist der Index. `i/crlf` und `i/mixed` sind
# Befunde; `i/-text` (Binaerdatei) und `i/none` (leer) nicht. Dieselbe
# Fehler- und Zeilenzahl-Behandlung wie oben, aus demselben Grund: ein
# fehlschlagendes oder gekuerztes `ls-files --eol` blieb sonst unbemerkt
# (gemessen zu #118 Nacharbeit 1).
eol_warnung=$(mktemp)
aufraeumen_dateien="$aufraeumen_dateien $eol_warnung"
if ! eol_liste=$(git ls-files --eol 2>"$eol_warnung"); then
  echo "zeilenenden: git ls-files --eol fehlgeschlagen: $(cat "$eol_warnung")"
  exit 2
fi
eol_liste_anzahl=$(printf '%s\n' "$eol_liste" | grep -c . || true)
# `-ne`, aus demselben Grund wie beim check-attr-Abgleich oben: eine zu LANGE
# Liste ist ebenso ein Befund wie eine zu kurze.
if [ "$eol_liste_anzahl" -ne "$dateien_anzahl" ]; then
  echo "zeilenenden: git ls-files --eol hat $eol_liste_anzahl Zeilen fuer $dateien_anzahl Dateien geliefert (unpassende Pruefliste, zu kurz oder zu lang?)"
  exit 1
fi
crlf_im_index=$(printf '%s\n' "$eol_liste" | awk '$1 == "i/crlf" || $1 == "i/mixed"')

# Angewandte Ausnahmen: eine Datei je tatsaechlich GREIFENDER Ausnahme (nicht
# je Eintrag in der Ausnahmedatei -- ein Eintrag fuer eine Datei, die schon
# sauber ist, greift nie und ist selbst ein Befund, siehe unten). Eine Datei
# statt einer Variable, weil beide Schleifen unten in einer eigenen Subshell
# laufen (`$(...)`); eine dort gesetzte Variable ginge beim Verlassen der
# Subshell verloren, eine Datei nicht (dasselbe Muster wie `gesehene_pfade`
# oben; gemessen zu #118 Nacharbeit 2).
ausnahme_angewandt=$(mktemp)
aufraeumen_dateien="$aufraeumen_dateien $ausnahme_angewandt"

befund_attr=""
if [ -n "$falsches_attribut" ]; then
  befund_attr=$(printf '%s\n' "$falsches_attribut" | while IFS= read -r z; do
    pfad="${z%: eol: *}"
    wert="${z##*: eol: }"
    if erlaubt=$(ausnahme_wert "$pfad"); then
      if [ "$erlaubt" = "$wert" ]; then
        printf '%s\n' "$pfad" >> "$ausnahme_angewandt"
      else
        printf '%s\n' "$z"
      fi
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
      if [ "$erlaubt" = "$index_wert" ]; then
        printf '%s\n' "$pfad" >> "$ausnahme_angewandt"
      else
        printf '%s\n' "$z"
      fi
    else
      printf '%s\n' "$z"
    fi
  done)
fi

# Veraltete Ausnahmen: ein eingetragener Pfad, der nicht mehr versioniert
# ist, blieb sonst unbemerkt stehen. Exakter, ganzer-Zeilen-Vergleich
# (`-F` -- kein Muster/keine Regex; `-x` -- die ganze Zeile, kein Substring;
# ohne `-x` waere ein Ausnahme-Pfad wie "sta" schon durch die Datei
# "start.bat" "gedeckt", ohne selbst je eine Datei zu sein). Case-sensitiv:
# ein Eintrag, der sich nur in Gross-/Kleinschreibung von der echten,
# versionierten Datei unterscheidet, ist selbst kein versionierter Pfad und
# bleibt eine veraltete Ausnahme (gemessen zu #118 Nacharbeit 1).
befund_veraltet=""
if [ -n "$ausnahmen_norm" ]; then
  befund_veraltet=$(while IFS= read -r zeile; do
    pfad=$(printf '%s\n' "$zeile" | cut -f1)
    printf '%s\n' "$dateien" | grep -Fxq -- "$pfad" || printf '%s\n' "$pfad"
  done < "$ausnahmen_norm")
fi

# Nutzlose Ausnahmen: ein Eintrag fuer eine versionierte, aber SAUBERE Datei
# greift nie -- die Erfolgsmeldung zaehlte bisher jeden EINTRAG als
# "angewendet", auch wenn er nie eine Datei deckte (gemessen zu #118
# Nacharbeit 2: `README.md<TAB>crlf` auf einer sauberen README.md ergab
# "1 Ausnahme(n) angewendet", obwohl die Ausnahme nichts tat, und eine
# ruhende Ausnahme blieb so unbemerkt stehen). Ein bereits veralteter Pfad
# (oben) wird hier ausgelassen -- der ist schon dort ein eigener Befund, ein
# zweiter waere nur Rauschen.
befund_nutzlos=""
if [ -n "$ausnahmen_norm" ]; then
  befund_nutzlos=$(while IFS= read -r zeile; do
    pfad=$(printf '%s\n' "$zeile" | cut -f1)
    printf '%s\n' "$dateien" | grep -Fxq -- "$pfad" || continue
    grep -Fxq -- "$pfad" "$ausnahme_angewandt" 2>/dev/null || printf '%s\n' "$pfad"
  done < "$ausnahmen_norm")
fi

if [ -n "$befund_attr" ] || [ -n "$befund_index" ] || [ -n "$befund_veraltet" ] || [ -n "$befund_ausnahmeformat" ] || [ -n "$befund_nutzlos" ]; then
  if [ -n "$befund_ausnahmeformat" ]; then
    printf '%s' "$befund_ausnahmeformat"
  fi
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
  if [ -n "$befund_nutzlos" ]; then
    echo "zeilenenden: nutzlose Ausnahme(n) in $ausnahmen_datei (Datei ist sauber, die Ausnahme greift nie -- entfernen):"
    printf '%s\n' "$befund_nutzlos"
  fi
  exit 1
fi
angewandt_zahl=$(sort -u "$ausnahme_angewandt" | grep -c . || true)
if [ "$angewandt_zahl" -gt 0 ]; then
  echo "zeilenenden: $dateien_anzahl Dateien, alle eol=lf, kein CRLF im Index ($angewandt_zahl Ausnahme(n) angewendet)"
else
  echo "zeilenenden: $dateien_anzahl Dateien, alle eol=lf, kein CRLF im Index"
fi
