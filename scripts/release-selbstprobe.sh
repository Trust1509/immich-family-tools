#!/bin/sh
# Selbstprobe fuer scripts/release.sh.
#
#   sh scripts/release-selbstprobe.sh
#
# WARUM ES DIESE DATEI GIBT: Ein Gate ohne Selbstprobe ist eine Behauptung.
# Jede Pruefung in release.sh muss ROT werden koennen — sonst schuetzt sie
# nichts und niemand merkt es, weil ein Gate, das immer gruen ist, sich
# genauso anfuehlt wie eines, das funktioniert. Begruendung und Fall:
# docs/agents/lehren.md §21.
#
# WIE: Jeder Fall baut ein Wegwerf-Repo mit erfundenem Inhalt, laesst
# release.sh darauf los und prueft die EINZELNE Zeile, nicht den Exit-Code.
# Der Exit-Code allein waere zu grob — er wird in den Fixtures ohnehin rot,
# weil dort keine echte CI antwortet.
#
# Kein Netz, kein Push, keine echten Zugangsdaten. Das Repo ist oeffentlich.

set -e

WURZEL=$(cd "$(dirname "$0")/.." && pwd)
ARBEIT=$(mktemp -d 2>/dev/null || mktemp -d -t release-probe)
GRUEN=0
ROT=0

aufraeumen() { rm -rf "$ARBEIT"; }
trap aufraeumen EXIT

# ------------------------------------------------------- Fixture-Werkstatt

# baue <verzeichnis> <version-im-code> <changelog-kopf> <risiko-zeile>
# Legt ein vollstaendiges, GUELTIGES Repo an. Jeder Fall verbiegt danach
# genau eine Sache — so zeigt ein roter Lauf auf genau eine Ursache.
baue() {
  # Laeuft ohnehin in einer Kommandosubstitution, also in einer eigenen Shell —
  # trotzdem ein eigener Name, damit das nicht die tragende Annahme ist.
  ZB="$ARBEIT/$1"
  Z="$ZB"
  mkdir -p "$Z/scripts" "$Z/backend" "$Z/frontend/src"
  cp "$WURZEL/scripts/release.sh" "$Z/scripts/release.sh"

  printf 'APP_VERSION = "%s"\n' "$2" > "$Z/backend/version.py"
  printf 'export const APP_VERSION = "%s";\n' "$2" > "$Z/frontend/src/version.ts"
  printf '{\n  "name": "probe",\n  "version": "%s",\n  "private": true\n}\n' "$2" > "$Z/frontend/package.json"

  {
    printf '# Changelog\n\n'
    # "OHNE" heisst: gar kein Eintrag. Dann darf auch der Vorgaenger nicht
    # dastehen — sonst prueft der Fall etwas anderes, als sein Name sagt.
    # Genau daran ist er beim ersten Lauf vorbeigegangen.
    if [ "$3" != OHNE ]; then
      printf '%s\n\n' "$3"
      [ -n "$4" ] && printf '%s\n\n' "$4"
      printf '### Etwas\n\n- Erfundener Eintrag, nur fuer die Probe.\n\n'
      printf '## [0.9.0] – 2026-01-01\n\n- Vorgaenger.\n'
    else
      printf 'Diese Datei fuehrt keinen einzigen Versions-Eintrag.\n'
    fi
  } > "$Z/CHANGELOG.md"

  git -C "$Z" init -q
  # Identitaet in der Repo-Konfiguration, nicht nur je Kommando: "git tag -a"
  # legt ein Objekt mit Autor an und scheitert ohne sie. Beim ersten Lauf war
  # genau das die Ursache fuer "gruenes Gate, aber kein Tag" — und der Fehler
  # war unsichtbar, weil die Huelle ihn verschluckt hat.
  git -C "$Z" config user.email probe@example.invalid
  git -C "$Z" config user.name Probe
  git -C "$Z" add -A
  git -C "$Z" commit -qm "fixture"
  echo "$Z"
}

# stub_gh <verzeichnis> <status> <conclusion> [sha]
# Ein falsches "gh" im PATH, damit auch der GRUENE CI-Pfad beweisbar ist.
# Ohne das waere "CI gruen" die einzige Zeile, die nie jemand gesehen hat.
#
# Der Stub liegt AUSSERHALB des Fixture-Repos. Lag er darin, machte er den
# Arbeitsbaum schmutzig und die Sauberkeits-Pruefung rot — die Sonde haette
# ihren eigenen Befund erzeugt. Genau einmal passiert, deshalb steht es hier.
STUBS="$ARBEIT/stub-bin"
stub_gh() {
  ZS=$1
  SHA=${4:-$(git -C "$ZS" rev-parse HEAD)}
  mkdir -p "$STUBS"
  cat > "$STUBS/gh" <<STUB
#!/bin/sh
printf '{"databaseId":4711,"headSha":"%s","status":"%s","conclusion":"%s"}\n' "$SHA" "$2" "$3"
STUB
  chmod +x "$STUBS/gh"
}

# Fuer den Fall "Werkzeug fehlt": release.sh liest den Namen des Werkzeugs
# aus RELEASE_GH. Ein Name, den es nicht gibt, probt den Ausfall — ueberall
# gleich. Die erste Fassung schnitt stattdessen den PATH zurecht; das haette
# auf einem CI-Laeufer versagt, wo git und gh im selben Verzeichnis liegen,
# und die Probe waere dort rot geworden, ohne dass etwas kaputt war.
GH_GIBT_ES_NICHT=gh-existiert-hier-nicht

# lauf <verzeichnis> [argumente...] -> Ausgabe auf stdout, Exit unterdrueckt
# EIGENE VARIABLENNAMEN, und zwar mit Absicht: POSIX sh kennt kein "local".
# Die erste Fassung schrieb hier "Z=$1" — damit zeigte die globale
# Fixture-Variable $Z ab dem ersten Aufruf auf das ZULETZT gepruefte Repo.
# Abschnitt 11 hat dadurch das absichtlich rote Fixture getaggt und den
# Fehlschlag dem Skript angelastet. Die Huelle war der Defekt, nicht das Gate.
lauf() {
  ZL=$1; shift
  (cd "$ZL" && PATH="$STUBS:$PATH" sh scripts/release.sh "$@" 2>&1) || true
}

# lauf_ohne_gh <verzeichnis> [argumente...]
lauf_ohne_gh() {
  ZL=$1; shift
  (cd "$ZL" && RELEASE_GH="$GH_GIBT_ES_NICHT" sh scripts/release.sh "$@" 2>&1) || true
}

# erwarte <beschreibung> <OK|FEHLER> <teilstring> <ausgabe>
erwarte() {
  BESCHREIBUNG=$1; ART=$2; TEIL=$3; AUSGABE=$4
  if echo "$AUSGABE" | grep -q "^  $ART .*$TEIL"; then
    printf '  bestanden   %s\n' "$BESCHREIBUNG"
    GRUEN=$((GRUEN + 1))
  else
    printf '  FEHLGESCHLAGEN  %s\n' "$BESCHREIBUNG"
    printf '      erwartet: eine Zeile "%s ... %s"\n' "$ART" "$TEIL"
    echo "$AUSGABE" | sed 's/^/      | /'
    ROT=$((ROT + 1))
  fi
}

KOPF_GUT='## [1.5.0] – 2026-09-06'
RISIKO_GUT='**Risk: safe**'

echo "Selbstprobe fuer scripts/release.sh"
echo "Jede Pruefung muss rot werden koennen. Wegwerf-Repos unter $ARBEIT"
echo

# ------------------------------------------------------------------- Faelle

echo "1  Versionsformat"
Z=$(baue f1 1.5.0 "$KOPF_GUT" "$RISIKO_GUT")
erwarte "gueltige Version wird angenommen" OK "Versionsformat: 1.5.0" "$(lauf "$Z" pruefen 1.5.0)"
erwarte "1.5 wird abgelehnt"      FEHLER "kein MAJOR.MINOR.PATCH" "$(lauf "$Z" pruefen 1.5)"
erwarte "1.5.0.1 wird abgelehnt"  FEHLER "kein MAJOR.MINOR.PATCH" "$(lauf "$Z" pruefen 1.5.0.1)"
erwarte "1.5.x wird abgelehnt"    FEHLER "kein MAJOR.MINOR.PATCH" "$(lauf "$Z" pruefen 1.5.x)"
erwarte "v1.5.0 wird abgelehnt"   FEHLER "kein MAJOR.MINOR.PATCH" "$(lauf "$Z" pruefen v1.5.0)"

echo "2  Oberster CHANGELOG-Eintrag"
erwarte "passender Eintrag" OK "oberster Eintrag ist \[1.5.0\]" "$(lauf "$Z" pruefen 1.5.0)"
Z2=$(baue f2 1.5.0 '## [1.4.9] – 2026-09-06' "$RISIKO_GUT")
erwarte "Eintrag fuehrt eine andere Version" FEHLER "erwartet \[1.5.0\]" "$(lauf "$Z2" pruefen 1.5.0)"
Z3=$(baue f3 1.5.0 OHNE "$RISIKO_GUT")
erwarte "gar kein Eintrag" FEHLER "kein Eintrag der Form" "$(lauf "$Z3" pruefen 1.5.0)"

echo "3  Datum in der Kopfzeile"
Z4=$(baue f4 1.5.0 '## [1.5.0] – 6. September 2026' "$RISIKO_GUT")
erwarte "Datum in Prosa wird abgelehnt" FEHLER "kein gueltiges Datum" "$(lauf "$Z4" pruefen 1.5.0)"
Z5=$(baue f5 1.5.0 '## [1.5.0] - 2026-09-06' "$RISIKO_GUT")
erwarte "Bindestrich statt Halbgeviertstrich ist erlaubt" OK "Datum 2026-09-06" "$(lauf "$Z5" pruefen 1.5.0)"

echo "4  Risiko-Kennzeichnung"
erwarte "safe wird erkannt" OK "Risiko-Kennzeichnung 'safe'" "$(lauf "$Z" pruefen 1.5.0)"
Z6=$(baue f6 1.5.0 "$KOPF_GUT" '')
erwarte "fehlende Zeile" FEHLER "fehlt eine Zeile" "$(lauf "$Z6" pruefen 1.5.0)"
Z7=$(baue f7 1.5.0 "$KOPF_GUT" '**Risk: vielleicht**')
erwarte "unbekannte Stufe" FEHLER "fehlt eine Zeile" "$(lauf "$Z7" pruefen 1.5.0)"
# Die Zeile muss IM obersten Eintrag stehen. Eine im Vorgaenger zaehlt nicht —
# sonst schleppt jeder Release die Einstufung des letzten mit.
Z8="$ARBEIT/f8"; mkdir -p "$Z8"; cp -r "$Z6/." "$Z8/"
printf '\n**Risk: breaking**\n' >> "$Z8/CHANGELOG.md"
git -C "$Z8" -c user.email=p@example.invalid -c user.name=P commit -qam "risiko unten"
erwarte "Kennzeichnung im Vorgaenger zaehlt nicht" FEHLER "fehlt eine Zeile" "$(lauf "$Z8" pruefen 1.5.0)"

echo "5  Die drei Code-Stellen"
erwarte "alle drei passen" OK "backend/version.py: 1.5.0" "$(lauf "$Z" pruefen 1.5.0)"
for PAAR in "backend/version.py|APP_VERSION = \"1.4.4\"" \
            "frontend/src/version.ts|export const APP_VERSION = \"1.4.4\";" ; do
  DATEI=$(echo "$PAAR" | cut -d'|' -f1)
  INHALT=$(echo "$PAAR" | cut -d'|' -f2-)
  ZX="$ARBEIT/f5-$(echo "$DATEI" | tr '/.' '--')"
  mkdir -p "$ZX"; cp -r "$Z/." "$ZX/"
  echo "$INHALT" > "$ZX/$DATEI"
  git -C "$ZX" -c user.email=p@example.invalid -c user.name=P commit -qam "drift"
  erwarte "$DATEI weicht ab" FEHLER "1.4.4, erwartet 1.5.0" "$(lauf "$ZX" pruefen 1.5.0)"
done
ZP="$ARBEIT/f5-pkg"; mkdir -p "$ZP"; cp -r "$Z/." "$ZP/"
printf '{\n  "name": "probe",\n  "version": "1.4.4",\n  "private": true\n}\n' > "$ZP/frontend/package.json"
git -C "$ZP" -c user.email=p@example.invalid -c user.name=P commit -qam "drift"
erwarte "frontend/package.json weicht ab" FEHLER "1.4.4, erwartet 1.5.0" "$(lauf "$ZP" pruefen 1.5.0)"
ZF="$ARBEIT/f5-fehlt"; mkdir -p "$ZF"; cp -r "$Z/." "$ZF/"
rm "$ZF/backend/version.py"
git -C "$ZF" -c user.email=p@example.invalid -c user.name=P commit -qam "weg"
erwarte "Datei fehlt ganz" FEHLER "keine Version gefunden" "$(lauf "$ZF" pruefen 1.5.0)"

echo "6  Tag bereits vergeben"
erwarte "Tag ist frei" OK "Tag v1.5.0 ist frei" "$(lauf "$Z" pruefen 1.5.0)"
ZT="$ARBEIT/f6-tag"; mkdir -p "$ZT"; cp -r "$Z/." "$ZT/"
git -C "$ZT" tag v1.5.0
erwarte "Tag existiert schon" FEHLER "existiert bereits" "$(lauf "$ZT" pruefen 1.5.0)"

echo "7  Arbeitsbaum"
erwarte "sauberer Baum" OK "Arbeitsbaum sauber" "$(lauf "$Z" pruefen 1.5.0)"
ZS="$ARBEIT/f7-dreck"; mkdir -p "$ZS"; cp -r "$Z/." "$ZS/"
echo "unsauber" >> "$ZS/CHANGELOG.md"
erwarte "schmutziger Baum" FEHLER "nicht sauber" "$(lauf "$ZS" pruefen 1.5.0)"

echo "8  CI — der Kern: ein ausgefallener Test ist ROT, nicht 'uebersprungen'"
# Erst nachweisen, dass der erfundene Werkzeugname wirklich ins Leere zeigt.
# Sonst prueft der naechste Fall nichts und sieht trotzdem gruen aus.
if command -v "$GH_GIBT_ES_NICHT" >/dev/null 2>&1; then
  printf '  FEHLGESCHLAGEN  "%s" existiert doch — der Ausfall ist nicht probierbar\n' "$GH_GIBT_ES_NICHT"
  ROT=$((ROT + 1))
else
  printf '  bestanden   Vorbedingung: "%s" gibt es nicht\n' "$GH_GIBT_ES_NICHT"
  GRUEN=$((GRUEN + 1))
  erwarte "Werkzeug fehlt" FEHLER "nicht gefunden" "$(lauf_ohne_gh "$Z" pruefen 1.5.0)"
fi
erwarte "mit --ci-nicht-pruefen" FEHLER "KEIN GRUENES GATE"   "$(lauf "$Z" pruefen 1.5.0 --ci-nicht-pruefen)"
stub_gh "$Z" completed failure
erwarte "roter Lauf"             FEHLER "conclusion=failure"  "$(lauf "$Z" pruefen 1.5.0)"
stub_gh "$Z" in_progress ""
erwarte "Lauf noch unterwegs"    FEHLER "status=in_progress"  "$(lauf "$Z" pruefen 1.5.0)"
stub_gh "$Z" completed success 0000000000000000000000000000000000000000
erwarte "Lauf meldet fremden Stand" FEHLER "nicht HEAD"       "$(lauf "$Z" pruefen 1.5.0)"
stub_gh "$Z" completed success
erwarte "gruener Lauf auf HEAD"  OK     "CI gruen fuer HEAD"  "$(lauf "$Z" pruefen 1.5.0)"

echo "9  Das gruene Gate als Ganzes"
AUSGABE=$(lauf "$Z" pruefen 1.5.0)
if echo "$AUSGABE" | grep -q "Gate gruen"; then
  printf '  bestanden   alle Pruefungen gruen -> "Gate gruen"\n'; GRUEN=$((GRUEN + 1))
else
  printf '  FEHLGESCHLAGEN  das vollstaendig gute Fixture ergibt kein gruenes Gate\n'
  echo "$AUSGABE" | sed 's/^/      | /'; ROT=$((ROT + 1))
fi
if (cd "$Z" && PATH="$STUBS:$PATH" sh scripts/release.sh pruefen 1.5.0 >/dev/null 2>&1); then
  printf '  bestanden   Exit-Code 0 im gruenen Fall\n'; GRUEN=$((GRUEN + 1))
else
  printf '  FEHLGESCHLAGEN  gruenes Gate, aber Exit-Code != 0\n'; ROT=$((ROT + 1))
fi

echo "10 bump schreibt nur, wenn die Notizen fuehren"
ZB=$(baue f10 1.4.4 "$KOPF_GUT" "$RISIKO_GUT")
AUSGABE=$(lauf "$ZB" bump 1.5.0)
erwarte "bump zieht backend nach"  OK "backend/version.py -> 1.5.0" "$AUSGABE"
erwarte "bump zieht frontend nach" OK "frontend/src/version.ts -> 1.5.0" "$AUSGABE"
erwarte "bump zieht package.json nach" OK "frontend/package.json -> 1.5.0" "$AUSGABE"
ZN=$(baue f10b 1.4.4 '## [1.4.4] – 2026-08-19' "$RISIKO_GUT")
AUSGABE=$(lauf "$ZN" bump 1.5.0)
if echo "$AUSGABE" | grep -q "Die Notizen fuehren"; then
  printf '  bestanden   bump verweigert ohne passenden Notizen-Eintrag\n'; GRUEN=$((GRUEN + 1))
else
  printf '  FEHLGESCHLAGEN  bump haette ohne Notizen-Eintrag schreiben duerfen\n'
  echo "$AUSGABE" | sed 's/^/      | /'; ROT=$((ROT + 1))
fi
if grep -q '1.4.4' "$ZN/backend/version.py"; then
  printf '  bestanden   und hat dabei NICHTS geschrieben\n'; GRUEN=$((GRUEN + 1))
else
  printf '  FEHLGESCHLAGEN  bump hat trotz Verweigerung geschrieben\n'; ROT=$((ROT + 1))
fi

echo "11 tag setzt nichts bei rotem Gate"
ZG=$(baue f11 1.4.4 "$KOPF_GUT" "$RISIKO_GUT")
lauf "$ZG" tag 1.5.0 >/dev/null
if git -C "$ZG" rev-parse -q --verify refs/tags/v1.5.0 >/dev/null 2>&1; then
  printf '  FEHLGESCHLAGEN  Tag wurde trotz rotem Gate gesetzt\n'; ROT=$((ROT + 1))
else
  printf '  bestanden   kein Tag bei rotem Gate\n'; GRUEN=$((GRUEN + 1))
fi
stub_gh "$Z" completed success
lauf "$Z" tag 1.5.0 >/dev/null
if git -C "$Z" rev-parse -q --verify refs/tags/v1.5.0 >/dev/null 2>&1; then
  printf '  bestanden   Tag bei gruenem Gate gesetzt\n'; GRUEN=$((GRUEN + 1))
else
  printf '  FEHLGESCHLAGEN  gruenes Gate, aber kein Tag\n'; ROT=$((ROT + 1))
fi

echo
echo "$GRUEN bestanden, $ROT fehlgeschlagen"
[ "$ROT" -eq 0 ] || exit 1
