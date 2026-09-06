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
  # Ein eigenes, leeres Bare-Repo als "origin". Braucht kein Netz und keine
  # Zugangsdaten, aber das Gate fragt seit der Panel-Nacharbeit auch die
  # Gegenseite nach dem Tag — ohne origin waere jeder Fixture-Lauf rot, und
  # zwar aus einem Grund, der mit dem geprueften Fall nichts zu tun hat.
  git init -q --bare "$ZB.git"
  git -C "$Z" remote add origin "$ZB.git"
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
# Das Gate liest seit dem ersten echten Release ZEILEN, nicht ein
# JSON-Objekt: "<sha> <status> <conclusion> <id>", eine je Lauf.
stub_gh() {
  ZS=$1
  SHA=${4:-$(git -C "$ZS" rev-parse HEAD)}
  mkdir -p "$STUBS"
  cat > "$STUBS/gh" <<STUB
#!/bin/sh
printf '%s %s %s 4711\n' "$SHA" "$2" "$3"
STUB
  chmod +x "$STUBS/gh"
}

# MEHRERE Laeufe auf demselben Stand. Das ist seit "cancel-in-progress" in
# ci.yml der Normalfall und nicht der Randfall — genau daran ist die erste
# Fassung des Gates beim ersten echten Release gescheitert.
# stub_gh_viele <verzeichnis> "<status> <conclusion>" ...
stub_gh_viele() {
  ZS=$1; shift
  SHA=$(git -C "$ZS" rev-parse HEAD)
  mkdir -p "$STUBS"
  echo '#!/bin/sh' > "$STUBS/gh"
  N=1
  for PAAR in "$@"; do
    echo "echo '$SHA $PAAR $N'" >> "$STUBS/gh"
    N=$((N + 1))
  done
  chmod +x "$STUBS/gh"
}

# gh antwortet ordentlich, aber kein Lauf passt auf den Stand: keine Zeile.
stub_gh_leer() {
  mkdir -p "$STUBS"
  printf '#!/bin/sh\nexit 0\n' > "$STUBS/gh"
  chmod +x "$STUBS/gh"
}

# Der entscheidende Stub: Er ANTWORTET UNTERSCHIEDLICH, je nachdem ob der
# Aufrufer --workflow mitgibt. Ohne Filter kommt ein gruener Fremd-Lauf
# (bei uns real: "Dependency Graph"), mit Filter der abgebrochene CI-Lauf.
# Damit wird der Filter selbst pruefbar: Nimmt jemand ihn heraus, faellt die
# Zusicherung um. Ohne diesen Stub waere der Filter eine Behauptung.
stub_gh_fremdlauf() {
  ZS=$1
  SHA=$(git -C "$ZS" rev-parse HEAD)
  mkdir -p "$STUBS"
  cat > "$STUBS/gh" <<STUB
#!/bin/sh
for A in "\$@"; do
  if [ "\$A" = "--workflow" ]; then
    printf '%s completed cancelled 33960519974\n' "$SHA"
    exit 0
  fi
done
printf '%s completed success 33960522227\n' "$SHA"
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
#
# Der Teilstring wird WOERTLICH verglichen, nicht als regulaerer Ausdruck.
# Die erste Fassung gab ihn an grep, und "[1.5.0]" ist dort eine
# Zeichenklasse: Sie trifft jede Zeile mit einer 1, 5, 0 oder einem Punkt.
# Gemessen — "  OK  irgendwas mit einer 5 drin" hat das Muster bestanden.
# Die Aufrufstellen waren zwar escaped, aber die naechste haette es nicht
# sein muessen, und der Fehler waere ein FALSCHES GRUEN gewesen: die Probe
# haette bestaetigt, was sie nie geprueft hat. Von Stimme 3 angestossen,
# in der Wirkung schaerfer als dort beschrieben.
treffer() {
  MUSTER_ART=$1; MUSTER_TEIL=$2
  while IFS= read -r ZEILE; do
    case "$ZEILE" in
      "  $MUSTER_ART "*)
        case "$ZEILE" in *"$MUSTER_TEIL"*) return 0 ;; esac ;;
    esac
  done
  return 1
}
erwarte() {
  BESCHREIBUNG=$1; ART=$2; TEIL=$3; AUSGABE=$4
  if echo "$AUSGABE" | treffer "$ART" "$TEIL"; then
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
erwarte "passender Eintrag" OK "oberster Eintrag ist [1.5.0]" "$(lauf "$Z" pruefen 1.5.0)"
Z2=$(baue f2 1.5.0 '## [1.4.9] – 2026-09-06' "$RISIKO_GUT")
erwarte "Eintrag fuehrt eine andere Version" FEHLER "erwartet [1.5.0]" "$(lauf "$Z2" pruefen 1.5.0)"
Z3=$(baue f3 1.5.0 OHNE "$RISIKO_GUT")
erwarte "gar kein Eintrag" FEHLER "kein Eintrag der Form" "$(lauf "$Z3" pruefen 1.5.0)"

echo "3  Datum in der Kopfzeile"
Z4=$(baue f4 1.5.0 '## [1.5.0] – 6. September 2026' "$RISIKO_GUT")
erwarte "Datum in Prosa wird abgelehnt" FEHLER "kein gueltiges Datum" "$(lauf "$Z4" pruefen 1.5.0)"
Z5=$(baue f5 1.5.0 '## [1.5.0] - 2026-09-06' "$RISIKO_GUT")
erwarte "Bindestrich statt Halbgeviertstrich ist erlaubt" OK "Datum 2026-09-06" "$(lauf "$Z5" pruefen 1.5.0)"
Z5b=$(baue f5b 1.5.0 '## [1.5.0]' "$RISIKO_GUT")
erwarte "gar kein Datum in der Kopfzeile" FEHLER "kein gueltiges Datum" "$(lauf "$Z5b" pruefen 1.5.0)"

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
  erwarte "$DATEI weicht ab" FEHLER "$DATEI: 1.4.4, erwartet 1.5.0" "$(lauf "$ZX" pruefen 1.5.0)"
done
ZP="$ARBEIT/f5-pkg"; mkdir -p "$ZP"; cp -r "$Z/." "$ZP/"
printf '{\n  "name": "probe",\n  "version": "1.4.4",\n  "private": true\n}\n' > "$ZP/frontend/package.json"
git -C "$ZP" -c user.email=p@example.invalid -c user.name=P commit -qam "drift"
erwarte "frontend/package.json weicht ab" FEHLER "frontend/package.json: 1.4.4, erwartet 1.5.0" "$(lauf "$ZP" pruefen 1.5.0)"
ZF="$ARBEIT/f5-fehlt"; mkdir -p "$ZF"; cp -r "$Z/." "$ZF/"
rm "$ZF/backend/version.py"
git -C "$ZF" -c user.email=p@example.invalid -c user.name=P commit -qam "weg"
erwarte "Datei fehlt ganz" FEHLER "keine Version gefunden" "$(lauf "$ZF" pruefen 1.5.0)"

echo "6  Tag bereits vergeben"
erwarte "Tag ist frei" OK "Tag v1.5.0 ist frei" "$(lauf "$Z" pruefen 1.5.0)"
ZT="$ARBEIT/f6-tag"; mkdir -p "$ZT"; cp -r "$Z/." "$ZT/"
git -C "$ZT" tag v1.5.0
erwarte "Tag existiert schon (lokal)" FEHLER "existiert bereits (lokal)" "$(lauf "$ZT" pruefen 1.5.0)"
# Der Tag liegt auf origin, lokal nicht. Ohne die Fern-Abfrage meldet das
# Gate "frei" und erst der Push scheitert — von der blinden Panel-Stimme
# angemerkt. Der Tag wird in EINEM Klon gesetzt und in das gemeinsame
# Bare-Repo gepusht; der zweite Klon weiss lokal nichts davon.
ZFERN="$ARBEIT/f6-fern"; mkdir -p "$ZFERN"; cp -r "$Z/." "$ZFERN/"
# EIGENES Bare-Repo fuer diesen Fall. Beide Klone erben sonst das origin von
# f1, und der gepushte Tag laege danach auch fuer die Abschnitte 9 und 11 dort
# — die haben daraufhin "Tag existiert auf origin" gemeldet und ihren eigenen
# Fehlschlag erzeugt. Die Sonde hatte sich selbst vergiftet.
git init -q --bare "$ARBEIT/f6-origin.git"
git -C "$ZT" remote set-url origin "$ARBEIT/f6-origin.git"
git -C "$ZFERN" remote set-url origin "$ARBEIT/f6-origin.git"
git -C "$ZT" push -q origin v1.5.0
erwarte "Tag liegt auf origin" FEHLER "auf origin" "$(lauf "$ZFERN" pruefen 1.5.0)"
# Nicht erreichbares origin: nicht pruefbar heisst nicht bestanden.
ZKAPUTT="$ARBEIT/f6-kaputt"; mkdir -p "$ZKAPUTT"; cp -r "$Z/." "$ZKAPUTT/"
git -C "$ZKAPUTT" remote set-url origin "$ARBEIT/gibt-es-nicht.git"
erwarte "origin nicht erreichbar" FEHLER "nicht pruefbar" "$(lauf "$ZKAPUTT" pruefen 1.5.0)"

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
erwarte "roter Lauf"             FEHLER "fehlgeschlagene Laeufe" "$(lauf "$Z" pruefen 1.5.0)"
stub_gh "$Z" in_progress ""
erwarte "Lauf noch unterwegs"    FEHLER "laeuft noch"         "$(lauf "$Z" pruefen 1.5.0)"
stub_gh "$Z" completed success 0000000000000000000000000000000000000000
erwarte "Zeile meldet fremden Stand, zaehlt nicht" FEHLER "kein Lauf fuer HEAD" "$(lauf "$Z" pruefen 1.5.0)"
# gh antwortet, aber KEIN Lauf passt. Diese Zeile fehlte in der ersten
# Fassung — und eine Mutation, die genau sie auf "ok" dreht, blieb dadurch
# unentdeckt, bei unveraendert "39 bestanden, 0 fehlgeschlagen". Von der
# blinden Panel-Stimme gefunden und mit genau dieser Mutation belegt.
stub_gh_leer
erwarte "gh antwortet, kein Lauf passt" FEHLER "kein Lauf fuer HEAD" "$(lauf "$Z" pruefen 1.5.0)"
stub_gh "$Z" completed success
erwarte "gruener Lauf auf HEAD"  OK     "CI gruen fuer HEAD"  "$(lauf "$Z" pruefen 1.5.0)"

# Mehrere Laeufe auf einem Stand — der Fall, an dem die erste Fassung beim
# ersten echten Release gescheitert ist. Ein ABGEBROCHENER Lauf traegt kein
# Urteil: Er wurde von unserer eigenen concurrency-Regel weggeschaltet, bevor
# er eines faellen konnte. Er darf ein Gruen also weder ersetzen noch kippen.
stub_gh_viele "$Z" "completed cancelled" "completed success"
erwarte "abgebrochen PLUS gruen zaehlt als gruen" OK "abgebrochen und ohne Urteil" "$(lauf "$Z" pruefen 1.5.0)"
stub_gh_viele "$Z" "completed cancelled" "completed cancelled"
erwarte "nur abgebrochene sind KEIN Urteil" FEHLER "nur abgebrochene" "$(lauf "$Z" pruefen 1.5.0)"
stub_gh_viele "$Z" "completed success" "completed failure"
erwarte "ein Fehlschlag neben einem Gruen kippt es" FEHLER "fehlgeschlagene Laeufe" "$(lauf "$Z" pruefen 1.5.0)"
stub_gh_viele "$Z" "completed success" "in_progress "
erwarte "ein noch laufender Lauf haelt das Gate auf" FEHLER "laeuft noch" "$(lauf "$Z" pruefen 1.5.0)"
stub_gh_viele "$Z" "completed success" "completed success"
erwarte "zwei gruene sind gruen" OK "CI gruen fuer HEAD" "$(lauf "$Z" pruefen 1.5.0)"
# Der Workflow-Filter: ein gruener FREMD-Lauf auf demselben Stand darf das
# Gate nicht befriedigen. Der Stub antwortet je nachdem, ob --workflow
# mitkommt — ohne Filter der gruene Fremdlauf, mit Filter der abgebrochene
# CI-Lauf. Real gemessen an 8e46bf1: CI cancelled, Dependency Graph gruen.
stub_gh_fremdlauf "$Z"
erwarte "Fremdlauf zaehlt nicht als CI" FEHLER "nur abgebrochene" "$(lauf "$Z" pruefen 1.5.0)"

echo "9  Das gruene Gate als Ganzes"
# Stub zurueck auf gruen — Abschnitt 8 hat ihn zuletzt auf den Fremdlauf
# gestellt, und ohne das Zuruecksetzen pruefte dieser Abschnitt einen
# Zustand, den er nicht meint.
stub_gh "$Z" completed success
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

echo "12 Mutationen GEGEN DAS GATE — tragen die Pruefungen ueberhaupt Gewicht?"
# Bis hierher mutiert diese Probe nur FIXTURES. Das beweist, dass ein
# kaputter Eingang gefunden wird — nicht, dass die pruefende Zeile Gewicht
# traegt. Genau diese Luecke hat die blinde Panel-Stimme aufgemacht: Sie hat
# release.sh:184 von "rot" auf "ok" gedreht, und die Probe meldete
# unveraendert "39 bestanden, 0 fehlgeschlagen".
#
# docs/agents/lehren.md §21 verlangt woertlich Mutationen GEGEN DAS GATE.
# Hier stehen sie. Je Fall: eine Zeile in release.sh verbiegen und zeigen,
# dass der zugehoerige Fall daraufhin FALSCH gruen wuerde — die Zusicherung
# also an dieser Zeile haengt und nicht an einer anderen.

# mutiere <name> <vorlage-fixture> <alt> <neu> -> Verzeichnis
#
# Ersetzt WOERTLICH, mit awk und index()/substr() statt sed: Die Muster
# enthalten "$", "[", Klammern und Anfuehrungszeichen, und als regulaerer
# Ausdruck wuerde davon das Falsche gelesen. awk gibt es auf beiden Zielen
# (Git Bash und ubuntu-latest); python schied aus, weil "python -" mit
# Heredoc hier durch einen Shim laeuft, der die Ausgabe mit Warnungen
# zumuellt und auf dem Laeufer anders heissen kann.
#
# Der Zaehler ist tragend: Trifft das Muster nicht GENAU einmal, bricht die
# Mutation ab, statt still nichts zu tun — sonst waere jede spaetere
# "bestanden"-Zeile aus dem falschen Grund gruen.
mutiere() {
  ZM="$ARBEIT/mut-$1"
  mkdir -p "$ZM"; cp -r "$2/." "$ZM/"
  awk -v alt="$3" -v neu="$4" '
    { n = index($0, alt)
      if (n > 0) { $0 = substr($0, 1, n - 1) neu substr($0, n + length(alt)); treffer++ }
      print }
    END { if (treffer != 1) {
            printf "MUSTER-FEHLER: %d Treffer statt 1\n", treffer > "/dev/stderr"
            exit 3 } }
  ' "$2/scripts/release.sh" > "$ZM/scripts/release.sh"
  echo "$ZM"
}

# ueberlebt <beschreibung> <ausgabe> <teilstring-der-verschwinden-muss>
# Bestanden heisst hier: Die Mutation hat die Pruefung TATSAECHLICH
# ausgeschaltet. Damit ist belegt, dass die Zeile die Zusicherung traegt.
ueberlebt() {
  if echo "$2" | treffer FEHLER "$3"; then
    printf '  FEHLGESCHLAGEN  %s — Mutation blieb wirkungslos, die Zusicherung haengt woanders\n' "$1"
    echo "$2" | sed 's/^/      | /'
    ROT=$((ROT + 1))
  else
    printf '  bestanden   %s\n' "$1"
    GRUEN=$((GRUEN + 1))
  fi
}

stub_gh_leer
ZM1=$(mutiere ci-ausfall "$Z" \
  'rot "CI: kein Lauf fuer HEAD ($KURZ) gefunden' \
  'ok "CI (kein Lauf gefunden, nehmen wir mal an)" # rot "CI: kein Lauf fuer HEAD ($KURZ) gefunden')
ueberlebt "der Ausfall-Zweig traegt die Zusicherung 'kein Lauf gefunden'" \
  "$(lauf "$ZM1" pruefen 1.5.0)" "kein Lauf fuer HEAD"

stub_gh_fremdlauf "$Z"
ZM2=$(mutiere workflow-filter "$Z" '--workflow ci.yml --limit 60' '--limit 60')
ueberlebt "der Workflow-Filter traegt: ohne ihn gewinnt der gruene Fremdlauf" \
  "$(lauf "$ZM2" pruefen 1.5.0)" "nur abgebrochene"

stub_gh "$Z" completed success
ZM3=$(mutiere risiko "$Z" \
  'rot "CHANGELOG.md: im Eintrag [$VERSION] fehlt eine Zeile' \
  'ok "Risiko egal" # rot "CHANGELOG.md: im Eintrag [$VERSION] fehlt eine Zeile')
ZM3O="$ARBEIT/mut-risiko-ohne"; mkdir -p "$ZM3O"; cp -r "$ZM3/." "$ZM3O/"
cp "$Z6/CHANGELOG.md" "$ZM3O/CHANGELOG.md"
git -C "$ZM3O" -c user.email=p@example.invalid -c user.name=P commit -qam "risiko raus"
ueberlebt "die Risiko-Pruefung traegt" \
  "$(lauf "$ZM3O" pruefen 1.5.0)" "fehlt eine Zeile"

ZM4=$(mutiere baum "$Z" \
  'rot "Arbeitsbaum ist nicht sauber' \
  'ok "Baum egal" # rot "Arbeitsbaum ist nicht sauber')
echo "dreck" >> "$ZM4/CHANGELOG.md"
ueberlebt "die Sauberkeits-Pruefung traegt" \
  "$(lauf "$ZM4" pruefen 1.5.0)" "nicht sauber"

ZM5=$(mutiere headsha "$Z" \
  '[ "$Z_SHA" = "$SHA" ] || continue' \
  'true # [ "$Z_SHA" = "$SHA" ] || continue')
stub_gh "$ZM5" completed success 0000000000000000000000000000000000000000
ueberlebt "die headSha-Pruefung je Zeile traegt" \
  "$(lauf "$ZM5" pruefen 1.5.0)" "kein Lauf fuer HEAD"

stub_gh "$Z" completed success
ZM6=$(mutiere codestellen "$Z" \
  'rot "$DATEI: $IST, erwartet $VERSION"' \
  'ok "$DATEI egal" # rot "$DATEI: $IST, erwartet $VERSION"')
printf 'APP_VERSION = "1.4.4"\n' > "$ZM6/backend/version.py"
git -C "$ZM6" -c user.email=p@example.invalid -c user.name=P commit -qam "drift"
ueberlebt "die Versions-Gleichheit traegt" \
  "$(lauf "$ZM6" pruefen 1.5.0)" "erwartet 1.5.0"

echo
echo "$GRUEN bestanden, $ROT fehlgeschlagen"
[ "$ROT" -eq 0 ] || exit 1
