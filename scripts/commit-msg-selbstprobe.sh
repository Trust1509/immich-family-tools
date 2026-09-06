#!/bin/sh
# Selbstprobe fuer .husky/commit-msg.
#
# WARUM ES DIESE DATEI GIBT: Die Behauptung "in N Richtungen gemessen" stand
# vorher nur in Prosa — ohne Kommando, ohne Stand, nicht nachrechenbar
# (docs/agents/lehren.md Paragraph 14: eine Zahl in einem Regeltext traegt das
# Kommando und den Stand, mit dem sie gemessen wurde). Und ein Waechter, dessen
# Lauf niemand erzwingt, macht seine Abdeckungszahl zur Beruhigung
# (Paragraph 18). Deshalb: eingecheckt, in der CI, mit Exit-Code.
#
# WIE: Jeder Fall ist eine Commit-Nachricht plus die Erwartung an den
# Exit-Code des Hooks. Die Faelle mit "git:" fahren zusaetzlich einen ECHTEN
# Commit in einem Wegwerf-Repo und vergleichen, was git wirklich SPEICHERT —
# denn genau darauf schaut die Plattform, nicht auf das, was der Hook sieht.
#
# HERKUNFT DER FAELLE: 1-4 aus dem urspruenglichen Rot-Beweis; 5-8 aus der
# blinden Erststimme (Trailer-Form, -v-Falschpositiv); 9-13 aus der zweiten
# blinden Stimme (Scheren-Umgehungen); 14-16 aus der GPT-Zweitstimme (die
# Umgehung, an der die dritte Hook-Fassung gescheitert ist, und die bewusste
# Ueberdeckung). Jeder Fall steht fuer einen Fehler, der einmal echt war.
set -e

WURZEL=$(cd "$(dirname "$0")/.." && pwd)
HOOK="$WURZEL/.husky/commit-msg"
[ -f "$HOOK" ] || { echo "Hook nicht gefunden: $HOOK"; exit 2; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

BESTANDEN=0
FEHLGESCHLAGEN=0
SCHERE='# ------------------------ >8 ------------------------'
# Zusammengesetzt, damit diese DATEI die Kennung nicht als zusammenhaengende
# Zeichenfolge traegt — sie wird von den Faellen unten erzeugt, nicht zitiert.
K='[skip'' ci]'
K2='[ci'' skip]'

pruefe() {
  NAME="$1"; ERWARTET="$2"; DATEI="$3"
  # `set -e` wuerde die Probe beim ERSTEN erwarteten Rot beenden — und eine
  # Selbstprobe, die an ihrem eigenen Zweck stirbt, meldet null Faelle statt
  # eines Fehlers. Deshalb der Status ueber eine Bedingung, nicht ueber $?.
  if sh "$HOOK" "$DATEI" > "$TMP/ausgabe" 2>&1; then RC=0; else RC=$?; fi
  if [ "$RC" = "$ERWARTET" ]; then
    printf '  bestanden   %s\n' "$NAME"
    BESTANDEN=$((BESTANDEN + 1))
  else
    printf '  FEHLER      %s (erwartet Exit %s, war %s)\n' "$NAME" "$ERWARTET" "$RC"
    sed 's/^/                /' "$TMP/ausgabe"
    FEHLGESCHLAGEN=$((FEHLGESCHLAGEN + 1))
  fi
}

# Faehrt einen ECHTEN Commit und prueft, ob die Kennung in der GESPEICHERTEN
# Nachricht landet. Das ist die Frage, die zaehlt — der Hook sieht eine andere
# Datei als die, die git am Ende schreibt.
pruefe_gespeichert() {
  NAME="$1"; ERWARTET_TREFFER="$2"; DATEI="$3"; ART="$4"
  R="$TMP/repo$$"; rm -rf "$R"; mkdir -p "$R"
  ( cd "$R" && git init -q . &&
    git config user.email probe@example.invalid && git config user.name Probe
    if [ "$ART" = "editor" ]; then
      # Der -v-Weg: git oeffnet einen Editor, haengt den Diff unter die
      # Scheren-Zeile und raeumt danach mit cleanup=scissors auf. Das ist ein
      # ANDERER Weg als -F, und nur auf diesem Weg schneidet git ueberhaupt ab.
      printf '#!/bin/sh\ncp "%s" "$1"\n' "$DATEI" > "$R/ed.sh"
      GIT_EDITOR="sh $R/ed.sh" git commit --allow-empty -q -v -e -m "platzhalter"
    else
      git commit --allow-empty -q -F "$DATEI"
    fi ) 2>/dev/null
  TREFFER=$(cd "$R" && git log -1 --format=%B | grep -c "skip ci" || true)
  rm -rf "$R"
  if [ "$TREFFER" = "$ERWARTET_TREFFER" ]; then
    printf '  bestanden   %s\n' "$NAME"
    BESTANDEN=$((BESTANDEN + 1))
  else
    printf '  FEHLER      %s (erwartet %s Treffer in der gespeicherten Nachricht, war %s)\n' \
      "$NAME" "$ERWARTET_TREFFER" "$TREFFER"
    FEHLGESCHLAGEN=$((FEHLGESCHLAGEN + 1))
  fi
}

echo "Selbstprobe .husky/commit-msg"
echo

printf 'feat: x\n\nSatz mit %s im Rumpf.\n' "$K"              > "$TMP/f01"
printf 'chore: doku %s\n\nRumpf ohne alles.\n' "$K"           > "$TMP/f02"
printf 'feat: sauber\n\nNichts hier.\n'                       > "$TMP/f03"
printf 'feat: variante\n\nZeile mit %s drin.\n' "$K2"         > "$TMP/f04"
printf 'feat: trailer\n\nRumpf.\n\n\nskip-checks: true\n'     > "$TMP/f05"
printf 'feat: trailer eng\n\nRumpf.\n\n\nskip-checks:true\n'  > "$TMP/f06"
{ printf 'fix: ci.yml angefasst\n\nSauberer Rumpf.\n'
  printf '%s\n' "$SCHERE"
  printf '# Do not modify or remove the line above.\n'
  printf '# Everything below it will be ignored.\n'
  printf 'diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n'
  printf 'index 1111111..2222222 100644\n'
  printf -- '--- a/.github/workflows/ci.yml\n'
  printf -- '+++ b/.github/workflows/ci.yml\n'
  printf '@@ -1,3 +1,4 @@\n'
  printf ' unveraendert\n'
  printf '+  # Commits mit %s werden uebersprungen\n' "$K"; }  > "$TMP/f07"
printf 'docs: hook\n\nErwaehnt den skip-checks-Trailer ohne Doppelpunkt.\n'  > "$TMP/f08"
printf 'feat: y\n\nRumpf.\n# Hinweis: %s in einer Kommentarzeile\n' "$K"     > "$TMP/f09"
{ printf 'process: Abgleich\n\nRumpf.\n'; printf '%s\n' "$SCHERE"; printf '%s\n' "$K"; }  > "$TMP/f10"
{ printf 'feat: t2\n\n'; printf '%s\n' "$SCHERE"; printf '\n\nskip-checks: true\n'; }     > "$TMP/f11"
{ printf 'feat: c3\n\n'; printf '# -- >8 --\n'; printf '%s\n' "$K"; }                     > "$TMP/f12"
{ printf 'feat: dazwischen\n\n'; printf '%s\n' "$SCHERE"; printf '%s\n' "$K"
  printf 'diff --git a/x b/x\n+irgendwas\n'; }                                           > "$TMP/f13"
# 14: die Umgehung, an der Fassung 3 gescheitert ist — Kennung HINTER dem
# Diff-Kopf, aber selbst keine Diff-Zeile.
{ printf 'subject\n\n'; printf '%s\n' "$SCHERE"
  printf 'diff --git a/f.txt b/f.txt\n'; printf '%s\n' "$K"; }                           > "$TMP/f14"
printf 'feat: bindestrich\n\nZeile mit [skip-ci] drin.\n'                                > "$TMP/f15"
printf 'feat: konfig\n\nEine Konfigzeile:\nskip-checks: false\n\nKein echter Trailer.\n' > "$TMP/f16"

pruefe "01 Klammer im Rumpf"                              1 "$TMP/f01"
pruefe "02 Klammer in der Betreffzeile"                   0 "$TMP/f02"
pruefe "03 keine Kennung"                                 0 "$TMP/f03"
pruefe "04 Schreibvariante im Rumpf"                      1 "$TMP/f04"
pruefe "05 skip-checks-Trailer mit Leerzeichen"           1 "$TMP/f05"
pruefe "06 skip-checks-Trailer ohne Leerzeichen"          1 "$TMP/f06"
pruefe "07 echter -v-Diff darf NICHT ablehnen"            0 "$TMP/f07"
pruefe "08 Trailer nur erwaehnt, ohne Doppelpunkt"        0 "$TMP/f08"
pruefe "09 Kennung in einer Kommentarzeile"               1 "$TMP/f09"
pruefe "10 Scheren-Zeile ohne Diff, Klammer"              1 "$TMP/f10"
pruefe "11 Scheren-Zeile ohne Diff, Trailer"              1 "$TMP/f11"
pruefe "12 eigene kurze Scheren-Zeile"                    1 "$TMP/f12"
pruefe "13 Kennung zwischen Schere und Diff-Kopf"         1 "$TMP/f13"
pruefe "14 Kennung HINTER dem Diff-Kopf (Fassung-3-Loch)" 1 "$TMP/f14"
pruefe "15 Beinahe-Form [skip-ci], bewusst abgelehnt"     1 "$TMP/f15"
pruefe "16 skip-checks im Fliesstext, bewusst abgelehnt"  1 "$TMP/f16"

echo
echo "Und was git WIRKLICH speichert — die Frage, auf die es ankommt:"
# 17: der Fall, den Fassung 3 durchliess. git speichert die Kennung, der Hook
#     muss ihn also ablehnen (Fall 14 oben) — beides zusammen ist der Beweis.
pruefe_gespeichert "17 Fall 14 per -F: Kennung landet in der Nachricht" 1 "$TMP/f14" datei
# 18: derselbe Dateiinhalt auf dem ECHTEN -v-Weg. Nur hier schneidet git ab,
#     und nur deshalb darf der Hook Fall 07 durchlassen. Wuerde git auch hier
#     speichern, waere die Ausnahme im Hook falsch.
pruefe_gespeichert "18 Fall 07 per -v: git schneidet, keine Kennung"    0 "$TMP/f07" editor
# 19: derselbe Inhalt wie 18, aber per -F uebergeben. Dann speichert git ihn
#     vollstaendig — und der Hook greift NICHT. Das ist die im Hook benannte
#     Restluecke, hier als Messung festgehalten statt als Behauptung. Wer sie
#     schliesst, muss diesen Fall auf 0 drehen.
pruefe_gespeichert "19 Restluecke: Fall 07 per -F speichert die Kennung" 1 "$TMP/f07" datei

echo
echo "$BESTANDEN bestanden, $FEHLGESCHLAGEN fehlgeschlagen"
[ "$FEHLGESCHLAGEN" -eq 0 ] || exit 1
