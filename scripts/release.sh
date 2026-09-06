#!/bin/sh
# Release-Gate und Versions-Bump fuer Immich Family Tools.
#
#   sh scripts/release.sh pruefen <version>   # Trockenlauf, schreibt NICHTS
#   sh scripts/release.sh bump    <version>   # schreibt die Version in die Code-Stellen
#   sh scripts/release.sh tag     <version>   # setzt den Tag LOKAL, nur bei gruenem Gate
#
# DAS TRAGENDE PRINZIP: DIE NOTIZEN FUEHREN, DIE VERSION FOLGT.
# ------------------------------------------------------------
# Ein Tag ohne gepflegte Notizen zeigt dem Nutzer die Angaben der Vorversion —
# inklusive falscher Risiko-Kennzeichnung. Deshalb prueft dieses Skript den
# obersten CHANGELOG-Eintrag GEGEN die gewuenschte Version und nicht umgekehrt:
# "bump" weigert sich, solange der Eintrag nicht dasteht.
#
# WAS DIESES SKRIPT NICHT TUT — und zwar absichtlich:
#   - Es pusht nichts. Kein "git push", kein "gh release create".
#   - Es schreibt keine Notizen. Prosa in der Sprache des Nutzers ist Handarbeit.
#   - Es taggt nur lokal. Der irreversible Schritt bleibt beim Owner.
#
# EIN UEBERSPRUNGENER TEST IST KEIN BESTANDENER TEST.
# Faellt eine Pruefung aus (kein "gh", kein Netz, kein Lauf gefunden), ist das
# ROT — nicht "uebersprungen". Wer trotzdem weiter muss, setzt --ci-nicht-pruefen
# und bekommt die Zeile, dass dieser Lauf kein gruenes Gate war.
#
# Selbstprobe: sh scripts/release-selbstprobe.sh

set -e

# ---------------------------------------------------------------- Grundlagen

WURZEL=$(cd "$(dirname "$0")/.." && pwd)
FEHLER=0
CI_UNGEPRUEFT=0

# Die versionsfuehrenden Stellen. EIGENTUEMER dieser Liste ist
# docs/agents/release-ritual.md, Abschnitt "Grundsaetze" — kommt eine Stelle
# dazu, gehoert sie in BEIDE. Vier Stellen, drei davon maschinell gefuehrt:
#   backend/version.py        APP_VERSION = "x.y.z"
#   frontend/src/version.ts   export const APP_VERSION = "x.y.z";
#   frontend/package.json     "version": "x.y.z",
# Die vierte, CHANGELOG.md, ist Handarbeit und wird nur GEPRUEFT.

ok()   { printf '  OK      %s\n' "$1"; }
rot()  { printf '  FEHLER  %s\n' "$1"; FEHLER=$((FEHLER + 1)); }

# Liest die Version aus einer der drei Code-Stellen. Gibt nichts aus, wenn die
# Datei fehlt oder das Muster nicht passt — der Aufrufer behandelt das als rot.
version_aus() {
  case "$1" in
    backend/version.py)
      sed -n 's/^APP_VERSION *= *"\([^"]*\)".*/\1/p' "$WURZEL/$1" 2>/dev/null | head -1 ;;
    frontend/src/version.ts)
      sed -n 's/^export const APP_VERSION *= *"\([^"]*\)".*/\1/p' "$WURZEL/$1" 2>/dev/null | head -1 ;;
    frontend/package.json)
      sed -n 's/^  "version": *"\([^"]*\)".*/\1/p' "$WURZEL/$1" 2>/dev/null | head -1 ;;
  esac
}

# Der oberste CHANGELOG-Eintrag: die erste Zeile, die mit "## [" beginnt.
changelog_kopfzeile() {
  grep -n '^## \[' "$WURZEL/CHANGELOG.md" 2>/dev/null | head -1
}

# ------------------------------------------------------------------ Pruefung

pruefe_format() {
  case "$1" in
    [0-9]*.[0-9]*.[0-9]*)
      # Punkte zaehlen und auf Ziffern pruefen, damit "1.2.3.4" und "1.2.x"
      # nicht durchrutschen — der Glob oben allein waere zu grosszuegig.
      if [ "$(echo "$1" | tr -cd '.' | wc -c)" -eq 2 ] &&
         [ -z "$(echo "$1" | tr -d '0-9.')" ] &&
         [ -n "$(echo "$1" | cut -d. -f1)" ] &&
         [ -n "$(echo "$1" | cut -d. -f2)" ] &&
         [ -n "$(echo "$1" | cut -d. -f3)" ]; then
        ok "Versionsformat: $1"
        return 0
      fi ;;
  esac
  rot "Versionsformat: '$1' ist kein MAJOR.MINOR.PATCH"
}

pruefe_changelog() {
  VERSION=$1
  KOPF=$(changelog_kopfzeile)

  if [ -z "$KOPF" ]; then
    rot "CHANGELOG.md: kein Eintrag der Form '## [x.y.z] – JJJJ-MM-TT' gefunden"
    return
  fi

  ZEILENNR=$(echo "$KOPF" | cut -d: -f1)
  TEXT=$(echo "$KOPF" | cut -d: -f2-)

  # Version im obersten Eintrag
  KOPF_VERSION=$(echo "$TEXT" | sed -n 's/^## \[\([^]]*\)\].*/\1/p')
  if [ "$KOPF_VERSION" = "$VERSION" ]; then
    ok "CHANGELOG.md: oberster Eintrag ist [$VERSION] (Zeile $ZEILENNR)"
  else
    rot "CHANGELOG.md: oberster Eintrag ist [$KOPF_VERSION], erwartet [$VERSION] (Zeile $ZEILENNR)"
    rot "  -> Die Notizen fuehren. Erst den Eintrag schreiben, dann bumpen."
    return
  fi

  # Datum. KEIN Klammerausdruck fuer den Trenner: Die Hausform benutzt den
  # Halbgeviertstrich U+2013, und ein Mehrbyte-Zeichen in [...] matcht ohne
  # gesetzte Locale einzelne BYTES statt des Zeichens — "[–-]" hat den
  # GUELTIGEN Kopf abgelehnt. Von der Selbstprobe gefunden; gleiche Klasse wie
  # der Umlaut-Befund in docs/agents/bau-brief.md. Deshalb alles zwischen "]"
  # und der Jahreszahl ueberspringen, ohne den Trenner zu benennen.
  DATUM=$(echo "$TEXT" | sed -n 's/^## \[[^]]*\][^0-9]*\([0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]\).*/\1/p')
  if [ -n "$DATUM" ]; then
    ok "CHANGELOG.md: Datum $DATUM"
  else
    rot "CHANGELOG.md: kein gueltiges Datum JJJJ-MM-TT in der Kopfzeile: $TEXT"
  fi

  # Risiko-Kennzeichnung innerhalb des obersten Eintrags, also bis zur
  # naechsten "## ["-Zeile. Ohne sie zeigt der Tag dem Nutzer die Einstufung
  # der Vorversion — genau der Fall, den das Ritual im Grundsatz beschreibt.
  ENDE=$(awk -v start="$ZEILENNR" 'NR > start && /^## \[/ { print NR; exit }' "$WURZEL/CHANGELOG.md")
  [ -n "$ENDE" ] || ENDE=$(wc -l < "$WURZEL/CHANGELOG.md")
  RISIKO=$(awk -v a="$ZEILENNR" -v b="$ENDE" 'NR >= a && NR <= b' "$WURZEL/CHANGELOG.md" |
           sed -n 's/^\*\*Risk: *\(safe\|backup\|breaking\)\*\* *$/\1/p' | head -1)
  if [ -n "$RISIKO" ]; then
    ok "CHANGELOG.md: Risiko-Kennzeichnung '$RISIKO'"
  else
    rot "CHANGELOG.md: im Eintrag [$VERSION] fehlt eine Zeile '**Risk: safe|backup|breaking**'"
  fi
}

pruefe_code_stellen() {
  VERSION=$1
  for DATEI in backend/version.py frontend/src/version.ts frontend/package.json; do
    IST=$(version_aus "$DATEI")
    if [ -z "$IST" ]; then
      rot "$DATEI: keine Version gefunden (Datei fehlt oder Muster passt nicht)"
    elif [ "$IST" = "$VERSION" ]; then
      ok "$DATEI: $IST"
    else
      rot "$DATEI: $IST, erwartet $VERSION"
    fi
  done
}

pruefe_tag_frei() {
  if git -C "$WURZEL" rev-parse -q --verify "refs/tags/v$1" >/dev/null 2>&1; then
    rot "Tag v$1 existiert bereits"
  else
    ok "Tag v$1 ist frei"
  fi
}

pruefe_baum_sauber() {
  if [ -n "$(git -C "$WURZEL" status --porcelain)" ]; then
    rot "Arbeitsbaum ist nicht sauber — der Tag wuerde einen Stand benennen, der nirgends liegt"
    git -C "$WURZEL" status --porcelain | sed 's/^/          /'
  else
    ok "Arbeitsbaum sauber"
  fi
}

pruefe_ci() {
  if [ "$CI_UNGEPRUEFT" -eq 1 ]; then
    rot "CI-PRUEFUNG UEBERSPRUNGEN (--ci-nicht-pruefen) — DIESER LAUF IST KEIN GRUENES GATE"
    return
  fi
  # Der Name des Werkzeugs ist ueberschreibbar, damit die Selbstprobe seinen
  # AUSFALL beweisen kann, ohne am PATH zu operieren (das war die erste
  # Fassung und haette auf einem CI-Laeufer, wo git und gh im selben
  # Verzeichnis liegen, nicht funktioniert). Faellt der Name ins Leere, ist
  # das ROT — der Schalter kann also kein falsches Gruen erzeugen.
  GH=${RELEASE_GH:-gh}
  if ! command -v "$GH" >/dev/null 2>&1; then
    rot "CI nicht pruefbar: '$GH' nicht gefunden. Das ist ROT, nicht 'uebersprungen'."
    return
  fi
  SHA=$(git -C "$WURZEL" rev-parse HEAD)
  KURZ=$(echo "$SHA" | cut -c1-7)
  ERGEBNIS=$(cd "$WURZEL" && "$GH" run list --limit 20 \
               --json headSha,status,conclusion,databaseId \
               --jq "[.[] | select(.headSha == \"$SHA\")] | first" 2>/dev/null || true)
  if [ -z "$ERGEBNIS" ] || [ "$ERGEBNIS" = "null" ]; then
    rot "CI: kein Lauf fuer HEAD ($KURZ) gefunden — ROT, nicht 'noch nicht da'"
    return
  fi
  STATUS=$(echo "$ERGEBNIS" | sed -n 's/.*"status":"\([^"]*\)".*/\1/p')
  SCHLUSS=$(echo "$ERGEBNIS" | sed -n 's/.*"conclusion":"\([^"]*\)".*/\1/p')
  LAUF=$(echo "$ERGEBNIS" | sed -n 's/.*"databaseId":\([0-9]*\).*/\1/p')
  GEMELDET=$(echo "$ERGEBNIS" | sed -n 's/.*"headSha":"\([^"]*\)".*/\1/p')
  # Die Filterung steckt im --jq-Ausdruck, also in fremdem Code. Wir pruefen
  # sein Ergebnis nach: ein Lauf, der einen anderen Stand meldet, ist kein
  # Beleg fuer diesen. Genau so wurde hier einmal ein Issue gegen fremdes
  # Gruen geschlossen (docs/agents/lehren.md §6).
  if [ "$GEMELDET" != "$SHA" ]; then
    rot "CI: Lauf $LAUF meldet $(echo "$GEMELDET" | cut -c1-7), nicht HEAD ($KURZ)"
    return
  fi
  if [ "$STATUS" = "completed" ] && [ "$SCHLUSS" = "success" ]; then
    ok "CI gruen fuer HEAD (Lauf $LAUF)"
  else
    rot "CI fuer HEAD: status=$STATUS conclusion=$SCHLUSS (Lauf $LAUF)"
  fi
}

gate() {
  VERSION=$1
  echo "Release-Gate fuer v$VERSION"
  echo "Trockenlauf: dieses Kommando schreibt nichts."
  echo
  pruefe_format "$VERSION"
  pruefe_changelog "$VERSION"
  pruefe_code_stellen "$VERSION"
  pruefe_tag_frei "$VERSION"
  pruefe_baum_sauber
  pruefe_ci
  echo
  if [ "$FEHLER" -eq 0 ]; then
    echo "Gate gruen. Naechster Schritt (Owner-Entscheidung):"
    echo "    sh scripts/release.sh tag $VERSION"
    echo "    git push origin v$VERSION"
    return 0
  fi
  echo "Gate ROT: $FEHLER Punkt(e). Kein Tag."
  return 1
}

# ---------------------------------------------------------------------- bump

bump() {
  VERSION=$1
  echo "Bump auf $VERSION"

  # Die Notizen fuehren: ohne passenden CHANGELOG-Eintrag wird nichts
  # geschrieben. Sonst entsteht genau der Zustand, den das Gate verhindern
  # soll — Code auf der neuen Nummer, Notizen auf der alten.
  KOPF_VERSION=$(changelog_kopfzeile | sed -n 's/^[0-9]*:## \[\([^]]*\)\].*/\1/p')
  if [ "$KOPF_VERSION" != "$VERSION" ]; then
    echo "  FEHLER  CHANGELOG.md fuehrt [$KOPF_VERSION], nicht [$VERSION]."
    echo "          Erst den Notizen-Eintrag schreiben. Die Notizen fuehren."
    return 1
  fi

  sed -i.bak "s/^APP_VERSION = \".*\"/APP_VERSION = \"$VERSION\"/" "$WURZEL/backend/version.py"
  sed -i.bak "s/^export const APP_VERSION = \".*\";/export const APP_VERSION = \"$VERSION\";/" "$WURZEL/frontend/src/version.ts"
  sed -i.bak "s/^  \"version\": \".*\",/  \"version\": \"$VERSION\",/" "$WURZEL/frontend/package.json"
  rm -f "$WURZEL/backend/version.py.bak" "$WURZEL/frontend/src/version.ts.bak" "$WURZEL/frontend/package.json.bak"

  for DATEI in backend/version.py frontend/src/version.ts frontend/package.json; do
    IST=$(version_aus "$DATEI")
    if [ "$IST" = "$VERSION" ]; then
      ok "$DATEI -> $IST"
    else
      rot "$DATEI steht auf '$IST' statt '$VERSION' — sed hat nicht gegriffen"
    fi
  done
  [ "$FEHLER" -eq 0 ] || return 1
  echo
  echo "Geschrieben. Jetzt committen, landen lassen, CI abwarten — dann:"
  echo "    sh scripts/release.sh pruefen $VERSION"
  return 0
}

# ----------------------------------------------------------------------- tag

tag() {
  VERSION=$1
  gate "$VERSION" || return 1
  git -C "$WURZEL" tag -a "v$VERSION" -m "v$VERSION"
  echo
  echo "Tag v$VERSION lokal gesetzt. Er ist noch NIRGENDS."
  echo "Der Push ist eine Owner-Entscheidung:"
  echo "    git push origin v$VERSION"
  echo
  echo "Danach Schritt 8 des Rituals — der Tag geht der Auslieferung voraus."
}

# --------------------------------------------------------------------- Start

BEFEHL=""
VERSION=""
for ARG in "$@"; do
  case "$ARG" in
    --ci-nicht-pruefen) CI_UNGEPRUEFT=1 ;;
    -*) echo "Unbekannter Schalter: $ARG" >&2; exit 2 ;;
    *) if [ -z "$BEFEHL" ]; then BEFEHL=$ARG; else VERSION=$ARG; fi ;;
  esac
done

if [ -z "$BEFEHL" ] || [ -z "$VERSION" ]; then
  echo "Aufruf: sh scripts/release.sh pruefen|bump|tag <version> [--ci-nicht-pruefen]" >&2
  exit 2
fi

case "$BEFEHL" in
  pruefen) gate "$VERSION" ;;
  bump)    bump "$VERSION" ;;
  tag)     tag "$VERSION" ;;
  *) echo "Unbekannter Befehl: $BEFEHL" >&2; exit 2 ;;
esac
