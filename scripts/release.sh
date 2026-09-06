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
      sed -n 's/^APP_VERSION *= *"\([^"]*\)".*/\1/p' "$WURZEL/$1" 2>/dev/null | head -n 1 ;;
    frontend/src/version.ts)
      sed -n 's/^export const APP_VERSION *= *"\([^"]*\)".*/\1/p' "$WURZEL/$1" 2>/dev/null | head -n 1 ;;
    frontend/package.json)
      # Die zwei Leerzeichen sind ABSICHT, kein Zufall der Formatierung: Sie
      # binden den Treffer an die oberste Ebene. Ein "version"-Feld tiefer im
      # Baum (in einem Abhaengigkeits-Block) traegt mehr Einrueckung und darf
      # hier nicht mitgelesen werden. Wird die Datei je anders eingerueckt,
      # findet dieses Muster nichts — und das Gate wird rot, nicht falsch
      # gruen. Prettier haelt die zwei Leerzeichen; siehe .lintstagedrc.
      sed -n 's/^  "version": *"\([^"]*\)".*/\1/p' "$WURZEL/$1" 2>/dev/null | head -n 1 ;;
  esac
}

# Der oberste CHANGELOG-Eintrag: die erste Zeile, die mit "## [" beginnt.
changelog_kopfzeile() {
  grep -n '^## \[' "$WURZEL/CHANGELOG.md" 2>/dev/null | head -n 1
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
           sed -n 's/^\*\*Risk: *\(safe\|backup\|breaking\)\*\*[[:space:]]*$/\1/p' | head -n 1)
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
    rot "Tag v$1 existiert bereits (lokal)"
    return
  fi
  # Auch die Gegenseite fragen. Ein Tag, den jemand anders schon gepusht hat,
  # ist lokal unsichtbar, solange niemand geholt hat — "frei" waere dann eine
  # Aussage ueber den eigenen Schreibtisch, nicht ueber die Welt, und erst der
  # Push wuerde scheitern. Von der blinden Panel-Stimme angemerkt.
  # Antwortet die Gegenseite nicht, ist das ROT: nicht pruefbar heisst nicht
  # bestanden.
  FERN=$(git -C "$WURZEL" ls-remote --tags origin "refs/tags/v$1" 2>/dev/null) || FERN="FEHLGESCHLAGEN"
  if [ "$FERN" = "FEHLGESCHLAGEN" ]; then
    rot "Tag v$1: origin nicht erreichbar — nicht pruefbar, also ROT"
  elif [ -n "$FERN" ]; then
    rot "Tag v$1 existiert bereits auf origin (lokal nicht geholt)"
  else
    ok "Tag v$1 ist frei, lokal und auf origin"
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
  # --workflow ci.yml IST TRAGEND, nicht Kosmetik. Ohne den Filter genuegt
  # IRGENDEIN Lauf auf diesem Stand, und dieses Repo hat mehrere Quellen, die
  # praktisch immer gruen sind (Dependency Graph, Dependabot Updates,
  # Wochen-Pruefung). Gemessen an 8e46bf1: der CI-Lauf war CANCELLED, der
  # Dependency-Graph-Lauf gruen, und das Gate meldete "CI gruen" — ein
  # falsches Gruen an der einzigen Stelle, die etwas ueber den Code sagt.
  # Von der blinden Panel-Stimme gefunden, Ende zu Ende reproduziert.
  # Die headSha-Nachpruefung unten faengt das NICHT: Der Fremdlauf meldet
  # denselben Stand. Verwandt mit docs/agents/lehren.md §6, aber eine eigene
  # Klasse — dort war es der falsche Commit, hier der falsche Workflow.
  #
  # ALLE Laeufe dieses Stands, eine Zeile je Lauf. NICHT "first".
  #
  # Die erste Fassung nahm den neuesten Lauf und fragte, was er sagt. Am
  # ersten echten Release ist sie genau daran gescheitert: Auf dem Stand lagen
  # ein abgebrochener und ein gruener CI-Lauf, "first" erwischte den
  # abgebrochenen, das Gate wurde rot. Das ist kein Randfall, sondern die
  # Folge unserer EIGENEN ci.yml — "cancel-in-progress" bricht den Push-Lauf
  # ab, sobald ein zweiter auf demselben Zweig startet. Ein Gate, das mit der
  # normalen Arbeitsweise des Repos nicht vereinbar ist, wird umgangen statt
  # repariert.
  #
  # Die Regel jetzt: Ein ABGEBROCHENER Lauf traegt kein Urteil — er wurde
  # weggeschaltet, bevor er eines faellen konnte. Er zaehlt also weder fuer
  # noch gegen. Alles andere zaehlt:
  #   kein Lauf                        -> ROT (nicht "noch nicht da")
  #   nur abgebrochene                 -> ROT (kein Urteil vorhanden)
  #   irgendein Fehlschlag             -> ROT, auch neben einem gruenen
  #   irgendetwas laeuft noch          -> ROT
  #   mindestens ein gruener, sonst nichts Schlechtes -> gruen
  #
  # Die Zeilenform ersetzt zugleich das Feld-Lesen per sed am JSON-Objekt.
  # Der headSha steht in JEDER Zeile und wird in JEDER Zeile nachgeprueft —
  # die Filterung steckt im jq-Ausdruck, also in fremdem Code, und genau so
  # wurde hier einmal ein Issue gegen fremdes Gruen geschlossen (§6).
  ZEILEN=$(cd "$WURZEL" && "$GH" run list --workflow ci.yml --limit 60 \
             --json headSha,status,conclusion,databaseId \
             --jq ".[] | \"\(.headSha) \(.status) \(.conclusion) \(.databaseId)\"" \
             2>/dev/null || true)
  GRUENE=""; SCHLECHTE=""; ABGEBROCHEN=""; OFFEN=""
  for_each_lauf() {
    while read -r Z_SHA Z_STATUS Z_SCHLUSS Z_ID; do
      [ "$Z_SHA" = "$SHA" ] || continue
      if [ "$Z_STATUS" != "completed" ]; then
        OFFEN="$OFFEN $Z_ID($Z_STATUS)"
      else
        case "$Z_SCHLUSS" in
          success)   GRUENE="$GRUENE $Z_ID" ;;
          cancelled) ABGEBROCHEN="$ABGEBROCHEN $Z_ID" ;;
          *)         SCHLECHTE="$SCHLECHTE $Z_ID($Z_SCHLUSS)" ;;
        esac
      fi
    done
    printf '%s|%s|%s|%s\n' "$GRUENE" "$SCHLECHTE" "$ABGEBROCHEN" "$OFFEN"
  }
  # Die Schleife laeuft in einer Pipeline, also in einer Subshell — ihre
  # Variablen ueberleben sie nicht. Deshalb kommt das Ergebnis als eine Zeile
  # zurueck und wird hier zerlegt.
  BILANZ=$(printf '%s\n' "$ZEILEN" | for_each_lauf)
  GRUENE=$(echo "$BILANZ" | cut -d'|' -f1)
  SCHLECHTE=$(echo "$BILANZ" | cut -d'|' -f2)
  ABGEBROCHEN=$(echo "$BILANZ" | cut -d'|' -f3)
  OFFEN=$(echo "$BILANZ" | cut -d'|' -f4)

  if [ -n "$SCHLECHTE" ]; then
    rot "CI fuer HEAD ($KURZ): fehlgeschlagene Laeufe:$SCHLECHTE"
  elif [ -n "$OFFEN" ]; then
    rot "CI fuer HEAD ($KURZ): laeuft noch:$OFFEN — abwarten, nicht taggen"
  elif [ -n "$GRUENE" ]; then
    if [ -n "$ABGEBROCHEN" ]; then
      ok "CI gruen fuer HEAD (Lauf$GRUENE; abgebrochen und ohne Urteil:$ABGEBROCHEN)"
    else
      ok "CI gruen fuer HEAD (Lauf$GRUENE)"
    fi
  elif [ -n "$ABGEBROCHEN" ]; then
    rot "CI fuer HEAD ($KURZ): nur abgebrochene Laeufe:$ABGEBROCHEN — kein Urteil, also ROT"
  else
    rot "CI: kein Lauf fuer HEAD ($KURZ) gefunden — ROT, nicht 'noch nicht da'"
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

  # Formatpruefung ZUERST. Ohne sie schreibt bump bereitwillig eine Version,
  # die das Gate danach nie mehr annimmt ("1.5.0-rc1"), und man kommt nur von
  # Hand wieder heraus. Von der blinden Panel-Stimme gefunden.
  pruefe_format "$VERSION"
  [ "$FEHLER" -eq 0 ] || return 1

  # Erst ALLE Zieldateien pruefen, dann schreiben. Sonst steht nach einem
  # Abbruch in der Mitte genau die Drift da, die dieses Skript verhindern
  # soll — backend auf der neuen Nummer, package.json auf der alten.
  for DATEI in backend/version.py frontend/src/version.ts frontend/package.json; do
    [ -f "$WURZEL/$DATEI" ] || rot "$DATEI fehlt"
  done
  if [ "$FEHLER" -ne 0 ]; then
    echo "          Nichts geschrieben."
    return 1
  fi

  # Die Notizen fuehren: ohne passenden CHANGELOG-Eintrag wird nichts
  # geschrieben. Sonst entsteht genau der Zustand, den das Gate verhindern
  # soll — Code auf der neuen Nummer, Notizen auf der alten.
  KOPF_VERSION=$(changelog_kopfzeile | sed -n 's/^[0-9]*:## \[\([^]]*\)\].*/\1/p')
  if [ "$KOPF_VERSION" != "$VERSION" ]; then
    echo "  FEHLER  CHANGELOG.md fuehrt [$KOPF_VERSION], nicht [$VERSION]."
    echo "          Erst den Notizen-Eintrag schreiben. Die Notizen fuehren."
    return 1
  fi

  # Je Datei: schreiben, Sicherungskopie SOFORT weg. Ein gemeinsames "rm" am
  # Ende wird bei "set -e" nie erreicht, wenn das zweite sed abbricht — dann
  # bleibt eine .bak liegen, macht den Arbeitsbaum schmutzig und das Gate rot
  # aus einem Grund, der nichts mit dem Release zu tun hat.
  #
  # Das package.json-Muster laesst das Komma OFFEN ("[,]*" statt ","). Die
  # erste Fassung verlangte es und haette eine Datei, in der "version" das
  # letzte Feld ist, gar nicht angefasst. Zerstoert haette sie sie nicht —
  # nachgemessen, das Muster kann kein Komma erfinden, wo keins steht —, aber
  # sie waere still unveraendert geblieben und erst am Nachtest aufgefallen.
  schreibe() {
    DATEI="$WURZEL/$1"
    sed -i.bak "$2" "$DATEI"
    rm -f "$DATEI.bak"
  }
  schreibe backend/version.py \
    "s/^APP_VERSION = \".*\"/APP_VERSION = \"$VERSION\"/" || true
  schreibe frontend/src/version.ts \
    "s/^export const APP_VERSION = \".*\";/export const APP_VERSION = \"$VERSION\";/" || true
  schreibe frontend/package.json \
    "s/^\(  \"version\": \)\"[^\"]*\"/\1\"$VERSION\"/" || true

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
    *)
      # Ein drittes Positionsargument wird ABGELEHNT, nicht stillschweigend
      # verarbeitet: "pruefen 1.5.0 9.9.9" hat vorher 9.9.9 geprueft und die
      # 1.5.0 verschluckt. Ein Gate, das mehrdeutige Eingabe irgendwie
      # auslegt, prueft nicht das, was der Aufrufer meinte.
      if [ -z "$BEFEHL" ]; then BEFEHL=$ARG
      elif [ -z "$VERSION" ]; then VERSION=$ARG
      else echo "Zu viele Argumente: '$ARG' nach '$BEFEHL $VERSION'" >&2; exit 2
      fi ;;
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
