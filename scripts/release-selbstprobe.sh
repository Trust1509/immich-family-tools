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
# Der Exit-Code reist IN der Ausgabe mit, als letzte Zeile.
#
# Die erste Fassung legte ihn in eine Datei — "letzter Status". Das ist ein
# SEITENKANAL: Ein Fall, der seine Ausgabe zwischenspeichert und spaeter prueft,
# wurde gegen den Status eines FREMDEN Laufs beurteilt. Gemessen vom
# Fremdpruefer: eine gespeicherte Ausgabe eines faelschlich erfolgreichen
# `bump` bestand, weil danach ein anderer, roter Lauf die Datei beschrieben
# hatte.
#
# Jetzt sind Ausgabe und Status untrennbar. `lauf_status` zeigte diese Form
# schon; sie gilt ab hier ueberall.
STATUSMARKE="__GATE_EXIT__="

lauf() {
  ZL=$1; shift
  RC=0
  AUS=$( cd "$ZL" && PATH="$STUBS:$PATH" sh scripts/release.sh "$@" 2>&1 ) || RC=$?
  printf '%s\n%s%s\n' "$AUS" "$STATUSMARKE" "$RC"
}

# Liest den Status aus einer Ausgabe, die `lauf` erzeugt hat.
status_aus() {
  echo "$1" | sed -n "s/^$STATUSMARKE//p" | tail -n 1
}

# lauf_status <verzeichnis> [argumente...] -> druckt NUR den Exit-Code.
#
# `lauf` wirft den Status per `|| true` weg, weil die meisten Faelle den TEXT
# pruefen. Genau daran ist die Probe fast gescheitert: Eine Ein-Zeichen-Mutation
# (`return 1` -> `return 0` im Abbruch) liess das Gate "Gate ROT ... Kein Tag."
# drucken UND danach taggen, mit Exit 0 — und die Selbstprobe meldete
# unveraendert alles gruen, weil keiner ihrer Faelle je einen Status ansah.
# Ein Gate wird nicht am Text abgefragt, sondern am Exit-Code.
lauf_status() {
  ZL=$1; shift
  # `|| RC=$?` statt `echo $?` danach: Unter `set -e` beendet ein
  # fehlschlagender Subshell-Aufruf die Funktion, BEVOR sie ihren Status
  # ausgeben kann — und ausgerechnet der Fehlerfall ist der, den diese
  # Faelle messen wollen. Dritter Auftritt derselben Falle in einer Sitzung;
  # sie sieht jedes Mal anders aus und ist jedes Mal dieselbe.
  #
  # Ausgabe: "<exit> <ausgabe in einer Zeile>". Die Ausgabe gehoert dazu,
  # weil "nicht 0" allein zwei voellig verschiedene Dinge bedeuten kann —
  # "das Gate hat abgelehnt" und "das Skript ist nie gelaufen". Die erste
  # Fassung warf sie nach /dev/null; vier der fuenf neuen Faelle konnten
  # danach ein syntaktisch totes release.sh nicht von einem arbeitenden
  # unterscheiden (Blindpruefer 20.09.2026).
  RC=0
  AUS=$( cd "$ZL" && PATH="$STUBS:$PATH" sh scripts/release.sh "$@" 2>&1 ) || RC=$?
  echo "$RC $(echo "$AUS" | tr '
' '|')"
}

# Trennt die beiden Bedeutungen von "nicht 0": Das Gate muss abgelehnt HABEN,
# nicht bloss irgendwie gestorben sein.
gate_hat_abgelehnt() {
  # Exit 1 ist die Ablehnung des Gates. Alles andere ist etwas anderes:
  # 2 = Aufruffehler, 127 = Kommando nicht gefunden, 2 aus der Shell =
  # Syntaxfehler. Die erste Fassung fragte nur "nicht 0" und hielt damit einen
  # ABSTURZ fuer eine kontrollierte Ablehnung — belegt mit der Mutation
  # `return 1` -> `kommando-das-es-nicht-gibt` (Exit 127), die unbemerkt blieb
  # (Fremdpruefer 20.09.2026).
  case "$1" in
    "1 "*) ;;
    *) return 1 ;;
  esac
  # Und die Ablehnung muss vom GATE stammen, nicht aus dem Nichts.
  case "$1" in
    *"Gate ROT"*) return 0 ;;
    *"FEHLER"*) return 0 ;;
    *) return 1 ;;
  esac
}

# lauf_ohne_gh <verzeichnis> [argumente...]
lauf_ohne_gh() {
  ZL=$1; shift
  RC=0
  AUS=$( cd "$ZL" && RELEASE_GH="$GH_GIBT_ES_NICHT" sh scripts/release.sh "$@" 2>&1 ) || RC=$?
  printf '%s\n%s%s\n' "$AUS" "$STATUSMARKE" "$RC"
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

  # DER HEBEL DIESES SLICES. Eine gemeldete FEHLER-Zeile ist nur dann ein
  # Befund, wenn das Gate deswegen auch rot ZURUECKKOMMT. Genau diese Luecke
  # war der BLOCKER aus #80: Eine Mutation `rot` -> `echo` liess das Gate
  # "FEHLER ... Das ist ROT" drucken UND danach "Gate gruen" mit Exit 0 — und
  # die Probe meldete unveraendert alles gruen, weil kein Fall den Status ansah.
  #
  # Die Pruefung haengt hier am Helfer, nicht an jedem einzelnen Fall: So gilt
  # sie fuer jeden bestehenden, ohne dass ihn jemand anfassen muss. Wie viele
  # das sind, steht hier bewusst nicht — die Zahl waechst mit jedem Fund
  # (lehren.md Paragraph 9); `grep -c 'erwarte '` sagt es jederzeit.
  if [ "$ART" = "FEHLER" ]; then
    # Der Status kommt aus DIESER Ausgabe, nicht aus einer Datei daneben. Eine
    # zwischengespeicherte Ausgabe bringt damit ihren eigenen Status mit.
    LETZTER=$(status_aus "$AUSGABE")
    [ -n "$LETZTER" ] || LETZTER="fehlt"
    # Exit 1 ist die Ablehnung des Gates. 127 (Kommando nicht gefunden) und 2
    # (Aufruf- oder Syntaxfehler) sind ABSTUERZE. Die erste Fassung fragte nur
    # "nicht 0" — und liess damit ein Gate durch, das NACH der FEHLER-Zeile
    # abstuerzte, `pruefe_ci` nie erreichte und dem Owner eine Shell-Meldung
    # hinterliess. Dieselbe Unterscheidung steht seit demselben Commit in
    # `gate_hat_abgelehnt`; sie fehlte ausgerechnet hier, wo sie die Mehrzahl
    # der Faelle traegt.
    if [ "$LETZTER" != "0" ] && [ "$LETZTER" != "1" ] && [ "$LETZTER" != "fehlt" ]; then
      printf '  FEHLGESCHLAGEN  %s\n' "$BESCHREIBUNG"
      printf '      das Gate kam mit %s zurueck — ein Absturz, keine Ablehnung\n' "$LETZTER"
      echo "$AUSGABE" | sed 's/^/      | /'
      ROT=$((ROT + 1))
      return
    fi
    if [ "$LETZTER" = "0" ]; then
      printf '  FEHLGESCHLAGEN  %s\n' "$BESCHREIBUNG"
      printf '      die Meldung steht da, aber das Gate kam mit 0 zurueck —\n'
      printf '      eine Meldung ohne Wirkung ist kein Befund\n'
      echo "$AUSGABE" | sed 's/^/      | /'
      ROT=$((ROT + 1))
      return
    fi
    if [ "$LETZTER" = "fehlt" ]; then
      printf '  FEHLGESCHLAGEN  %s\n' "$BESCHREIBUNG"
      printf '      kein Status vom letzten Lauf — die Wirkung ist unbelegt\n'
      ROT=$((ROT + 1))
      return
    fi
  fi

  if echo "$AUSGABE" | grep -v "^$STATUSMARKE" | treffer "$ART" "$TEIL"; then
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

# Die Schranke gegen Leerraum und unsichtbare Zeichen. Bis zur Nacharbeit von
# #80 war sie von KEINEM Fall gedeckt: Setzt man ihr Muster auf etwas, das nie
# vorkommt, bleibt die Probe gruen, waehrend das Gate wieder sieben
# Kaskadenzeilen erzeugt. Der Anlass des Slices selbst, ungeprueft eingebaut
# (Blindpruefer 20.09.2026).
MIT_UMBRUCH="1.5.0
"
erwarte "Version mit Zeilenumbruch wird abgelehnt" \
  FEHLER "kein MAJOR.MINOR.PATCH" "$(lauf "$Z" pruefen "$MIT_UMBRUCH")"
erwarte "Version mit Leerzeichen wird abgelehnt" \
  FEHLER "kein MAJOR.MINOR.PATCH" "$(lauf "$Z" pruefen "1.5.0 ")"
# Der Leerraum-Hinweis selbst war ungedeckt — dieselbe Klasse zum dritten Mal
# in diesem Slice: Der neue Zweig wurde eingebaut und nicht geprueft
# (Fremdpruefer 20.09.2026).
LEER_AUS=$(lauf_status "$Z" pruefen "1.5.0 ")
case "$LEER_AUS" in
  *"Leerraum oder einen Zeilenumbruch"*)
    printf '  bestanden   Leerraum bekommt den Leerraum-Hinweis
'; GRUEN=$((GRUEN + 1)) ;;
  *)
    printf '  FEHLGESCHLAGEN  Leerraum ohne passenden Hinweis: %s
' "$LEER_AUS"; ROT=$((ROT + 1)) ;;
esac

# Anlass: Der Owner rief am 07.09.2026 auf SEINEM Rechner `pruefen v1.6.0` auf
# (nach einer falschen Anweisung von mir). Das Gate lehnte richtig ab — und
# fuhr danach ALLE weiteren Pruefungen mit der unlesbaren Version weiter:
# acht Fehlerzeilen, von denen sieben Folgen der ersten waren. Die Ursache
# stand oben und ging in ihren eigenen Symptomen unter.
#
# Ein Gate, dessen Ausgabe man erst sortieren muss, hat seine Aufgabe
# verfehlt. Deshalb drei Faelle, die den Abbruch festnageln:
AUSG=$(lauf "$Z" pruefen v1.5.0)
# `|| true`: `grep -c` gibt bei NULL Treffern Exit 1 zurueck, die Zuweisung
# erbt ihn, und `set -e` beendet die Selbstprobe mitten im Lauf — ohne
# Bilanzzeile, mit rund 50 nie gefahrenen Faellen und ohne Hinweis warum.
# Gemessen von der blinden Panel-Stimme an genau diesem Fehlerbild.
ANZAHL=$(echo "$AUSG" | grep -c "FEHLER" || true)
if [ "$ANZAHL" = "1" ]; then
  printf '  bestanden   %s
' "ungueltige Version bricht ab statt zu kaskadieren (1 Fehlerzeile)"
  GRUEN=$((GRUEN + 1))
else
  printf '  FEHLGESCHLAGEN  %s
' "ungueltige Version bricht ab statt zu kaskadieren"
  printf '      erwartet: genau 1 FEHLER-Zeile, gezaehlt: %s
' "$ANZAHL"
  echo "$AUSG" | sed 's/^/      | /'
  ROT=$((ROT + 1))
fi
# Direkt geprueft statt ueber `erwarte`: Der Hinweis ist keine OK/FEHLER-Zeile,
# und `erwarte` sucht genau nach dieser Form. Die erste Fassung dieses Falls
# rief `erwarte` trotzdem auf und war deshalb rot — richtig rot, aber aus dem
# falschen Grund.
if echo "$AUSG" | grep -q "OHNE fuehrendes v"; then
  printf '  bestanden   %s
' "der Abbruch nennt die wahrscheinliche Ursache"
  GRUEN=$((GRUEN + 1))
else
  printf '  FEHLGESCHLAGEN  %s
' "der Abbruch nennt die wahrscheinliche Ursache"
  echo "$AUSG" | sed 's/^/      | /'
  ROT=$((ROT + 1))
fi
# Und die Kopfzeile darf bei ungueltiger Eingabe gar nicht erst erscheinen —
# sie las sich vorher als "Release-Gate fuer vv1.5.0", also wie ein Tippfehler
# des Skripts statt wie einer des Aufrufers.
if echo "$AUSG" | grep -q "vv"; then
  printf '  FEHLGESCHLAGEN  %s
' "Kopfzeile zeigt kein doppeltes v"
  echo "$AUSG" | sed 's/^/      | /'
  ROT=$((ROT + 1))
else
  printf '  bestanden   %s
' "Kopfzeile zeigt kein doppeltes v"
  GRUEN=$((GRUEN + 1))
fi

# Die Argumentpruefung des Gates — bis zur Nacharbeit von #80 ebenfalls
# ungedeckt, obwohl ihr Kommentar im Produkt sie ausfuehrlich begruendet. Sie
# benutzt Exit 2 (Aufruffehler), nicht Exit 1 (Ablehnung), deshalb direkt
# geprueft statt ueber `erwarte`.
pruefe_aufruf() {
  BESCHR=$1; shift
  RC=0
  ( cd "$Z" && PATH="$STUBS:$PATH" sh scripts/release.sh "$@" >/dev/null 2>&1 ) || RC=$?
  if [ "$RC" = "2" ]; then
    printf '  bestanden   %s\n' "$BESCHR"; GRUEN=$((GRUEN + 1))
  else
    printf '  FEHLGESCHLAGEN  %s (Exit %s statt 2)\n' "$BESCHR" "$RC"; ROT=$((ROT + 1))
  fi
}
pruefe_aufruf "ein drittes Positionsargument wird abgelehnt" pruefen 1.5.0 9.9.9
pruefe_aufruf "ein unbekannter Schalter wird abgelehnt"      pruefen 1.5.0 --gibt-es-nicht
pruefe_aufruf "eine fehlende Version wird abgelehnt"         pruefen
# Ein VERTIPPTER Befehl war vollstaendig ungedeckt: `*) exit 0` liess
# `release.sh vertippt 1.5.0` wortlos mit Erfolg enden — ein Gate, das nichts
# prueft und Erfolg meldet (Fremdpruefer 20.09.2026).
pruefe_aufruf "ein unbekannter Befehl wird abgelehnt"        vertippt 1.5.0

# Und die Diagnose gehoert dazu: Ein Exit 2 ohne Erklaerung schickt den
# Aufrufer ins Leere.
AUFRUF_AUS=$( cd "$Z" && PATH="$STUBS:$PATH" sh scripts/release.sh pruefen 2>&1 || true )
case "$AUFRUF_AUS" in
  *"Aufruf: sh scripts/release.sh"*)
    printf '  bestanden   der Aufruffehler nennt die richtige Aufrufform
'; GRUEN=$((GRUEN + 1)) ;;
  *)
    printf '  FEHLGESCHLAGEN  Aufruffehler ohne Aufrufform: %s
' "$AUFRUF_AUS"; ROT=$((ROT + 1)) ;;
esac

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

# Der `bump`-Pfad ohne passenden Notizen-Eintrag ging bis zur zweiten
# Nacharbeit von #80 an `erwarte` vorbei und prueste nur Text und
# Dateizustand — die dritte Stelle derselben Defektklasse (Fremdpruefer
# 20.09.2026). Hier als Wirkungspruefung nachgezogen.
pruefe_wirkung() {
  BESCHR=$1; ERWARTETER=$2; shift 2
  RC=0
  ( cd "$Z" && PATH="$STUBS:$PATH" sh scripts/release.sh "$@" >/dev/null 2>&1 ) || RC=$?
  if [ "$RC" = "$ERWARTETER" ]; then
    printf '  bestanden   %s\n' "$BESCHR"; GRUEN=$((GRUEN + 1))
  else
    printf '  FEHLGESCHLAGEN  %s (Exit %s statt %s)\n' "$BESCHR" "$RC" "$ERWARTETER"; ROT=$((ROT + 1))
  fi
}

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

echo "13 Der Exit-Code — die einzige Antwort, auf die sich ein Aufrufer verlaesst"
# Diese Faelle gab es bis zum 07.09.2026 NICHT. Dass ein ROTES Gate auch rot
# zurueckgibt, war nie belegt — genau das traf die Mutation der blinden Stimme.
#
# Die erste Fassung dieses Kommentars behauptete, die Probe habe "58 Faelle
# lang ausschliesslich Text geprueft". Das stimmt nicht: Der GRUENE Fall wurde
# schon vor diesem Slice ueber den Exit-Code geprueft (Abschnitt 9). Falsch war
# nur die rote Richtung. Nachgemessen, Blindpruefer 20.09.2026.
ZE=$(baue f13 1.5.0 "$KOPF_GUT" "$RISIKO_GUT")
stub_gh "$ZE" completed success

ST=$(lauf_status "$ZE" pruefen 1.5.0)
case "$ST" in
  "0 "*) printf '  bestanden   gruenes Gate gibt 0 zurueck\n'; GRUEN=$((GRUEN + 1)) ;;
  *) printf '  FEHLGESCHLAGEN  gruenes Gate gibt 0 zurueck (war: %s)\n' "$ST"; ROT=$((ROT + 1)) ;;
esac

ST=$(lauf_status "$ZE" pruefen v1.5.0)
if gate_hat_abgelehnt "$ST"; then
  printf '  bestanden   unlesbare Version: das Gate LEHNT AB, stirbt nicht bloss\n'; GRUEN=$((GRUEN + 1))
else
  printf '  FEHLGESCHLAGEN  unlesbare Version: %s\n' "$ST"; ROT=$((ROT + 1))
fi

# Der Produktwechsel DIESER Runde: Der Hinweis ist fallabhaengig geworden. Bis
# eben deckte ihn kein einziger Fall — man konnte ihn wieder unbedingt machen,
# und die Probe blieb 63/0 (Blindpruefer 20.09.2026).
case "$ST" in
  *"OHNE fuehrendes v"*)
    printf '  bestanden   v-Eingabe bekommt den v-Hinweis\n'; GRUEN=$((GRUEN + 1)) ;;
  *)
    printf '  FEHLGESCHLAGEN  v-Eingabe ohne v-Hinweis: %s\n' "$ST"; ROT=$((ROT + 1)) ;;
esac
# Eine dritte v-Form, die in keinem Fixture vorkommt: Mit `v1.5.0|v1.6.0`
# statt `v[0-9]*` blieben die beiden Faelle oben gruen (Fremdpruefer).
STV=$(lauf_status "$ZE" pruefen v9.9.9)
case "$STV" in
  *"OHNE fuehrendes v"*)
    printf '  bestanden   auch eine unbekannte v-Form bekommt den v-Hinweis\n'; GRUEN=$((GRUEN + 1)) ;;
  *)
    printf '  FEHLGESCHLAGEN  v9.9.9 ohne v-Hinweis: %s\n' "$STV"; ROT=$((ROT + 1)) ;;
esac
STX=$(lauf_status "$ZE" pruefen 1.5.x)
case "$STX" in
  *"OHNE fuehrendes v"*)
    printf '  FEHLGESCHLAGEN  1.5.x bekommt faelschlich den v-Hinweis: %s\n' "$STX"; ROT=$((ROT + 1)) ;;
  *"MAJOR.MINOR.PATCH aus Ziffern"*)
    printf '  bestanden   Nicht-v-Eingabe bekommt den allgemeinen Hinweis\n'; GRUEN=$((GRUEN + 1)) ;;
  *)
    printf '  FEHLGESCHLAGEN  1.5.x ohne brauchbaren Hinweis: %s\n' "$STX"; ROT=$((ROT + 1)) ;;
esac

ZF=$(baue f13b 1.4.4 "$KOPF_GUT" "$RISIKO_GUT")
ST=$(lauf_status "$ZF" pruefen 1.5.0)
if gate_hat_abgelehnt "$ST"; then
  printf '  bestanden   rotes Gate LEHNT AB, stirbt nicht bloss\n'; GRUEN=$((GRUEN + 1))
else
  printf '  FEHLGESCHLAGEN  rotes Gate: %s\n' "$ST"; ROT=$((ROT + 1))
fi

# bump gehoert genauso geprueft wie tag: Es SCHREIBT, und eine unlesbare
# Version darf dabei nichts anfassen.
#
# Der CHANGELOG-Kopf traegt hier ABSICHTLICH die unlesbare Form. Sonst
# blockiert die Notizen-Pruefung den Bump ohnehin, und der Fall waere gruen,
# ohne die Formatschranke je zu beruehren.
ZB=$(baue f13d 1.5.0 '## [v1.6.0] – 2026-09-06' "$RISIKO_GUT")
# Alle DREI Versionsdateien, und zwar VORHER gegen NACHHER — nicht "steht der
# alte Wert noch da".
#
# Die erste Fassung suchte die alten Werte im Inhalt. Das ist kein
# Unveraendert-Beweis: Eine Mutation, die etwas ANHAENGT, laesst den alten Wert
# stehen und kam damit durch — selbst gemessen, bevor es jemand anders fand.
# Ein Vergleich des ganzen Inhalts kann das nicht.
#
# `|| true`, weil eine fehlende Datei sonst unter `set -e` die Probe vor der
# Bilanz beendet.
versionsdateien() {
  { cat "$1/backend/version.py" "$1/frontend/src/version.ts" "$1/frontend/package.json"; } 2>&1 || true
}
VORHER=$(versionsdateien "$ZB")
ST=$(lauf_status "$ZB" bump v1.6.0)
NACHHER=$(versionsdateien "$ZB")
UNVERAENDERT=0
[ "$VORHER" = "$NACHHER" ] && UNVERAENDERT=1
if gate_hat_abgelehnt "$ST" && [ "$UNVERAENDERT" = "1" ]; then
  printf '  bestanden   bump mit unlesbarer Version schreibt nichts und lehnt ab\n'; GRUEN=$((GRUEN + 1))
else
  printf '  FEHLGESCHLAGEN  bump mit unlesbarer Version: %s\n' "$ST"
  printf '      Versionsdateien danach:\n'; printf '%s\n' "$VORHER" | sed 's/^/      | /'
  ROT=$((ROT + 1))
fi
# Die FRUEHE Formatschranke in `bump` isoliert: Faellt sie weg, uebernimmt die
# Zaehlzeile dahinter — das Ergebnis bleibt "abgelehnt", aber die Meldung
# erscheint ZWEIMAL. Genau daran war ihr Verlust bisher nicht zu erkennen
# (Fremdpruefer 20.09.2026).
ANZ=$(printf '%s' "$ST" | tr '|' '
' | grep -c "ist kein MAJOR.MINOR.PATCH" || true)
if [ "$ANZ" = "1" ]; then
  printf '  bestanden   bump meldet den Formatfehler genau einmal
'; GRUEN=$((GRUEN + 1))
else
  printf '  FEHLGESCHLAGEN  bump meldet den Formatfehler %sx — die fruehe Schranke fehlt
' "$ANZ"; ROT=$((ROT + 1))
fi
# Nicht nur DASS bump ablehnt, sondern dass er SAGT warum. Loescht man die
# Hinweiszeilen, bricht bump wortlos ab — und der Fall oben merkte es nicht.
case "$ST" in
  *"OHNE fuehrendes v"*)
    printf '  bestanden   bump nennt die Ursache, statt wortlos abzubrechen\n'; GRUEN=$((GRUEN + 1)) ;;
  *)
    printf '  FEHLGESCHLAGEN  bump bricht ohne Begruendung ab: %s\n' "$ST"; ROT=$((ROT + 1)) ;;
esac
# ROT-BEWEIS-VERMERK, damit dieser Fall nicht als bewiesen gilt, ohne es zu
# sein: `bump` ist tiefengestaffelt. Die Mutation "Abbruchblock entfernen"
# laesst ihn NICHT durch — es greift die Zeile `[ "$FEHLER" -eq 0 ] || return 1`
# unmittelbar danach. Rot wird der obere Fall erst, wenn BEIDE fallen.
#
# Die erste Fassung dieses Vermerks nannte stattdessen die Sammelpruefung vor
# dem Schreiben ("Nichts geschrieben."). Das war falsch — und gefaehrlich
# falsch: Wer die Zaehlzeile kuenftig fuer redundant haelt, weil der Vermerk
# den Schutz woanders verortet, entfernt genau die tragende Schranke. In
# diesem Fixture laeuft die Sammelpruefung gar nicht an, weil alle drei
# Dateien vorhanden sind (Blindpruefer 20.09.2026).

# Der Kern: Das Gate darf nach einem Abbruch NICHT taggen. Abschnitt 11 prueft
# das nur fuer eine formatgueltige Version und laeuft deshalb gar nicht durch
# den Abbruchpfad.
ZT2=$(baue f13c 1.5.0 "$KOPF_GUT" "$RISIKO_GUT")
ST=$(lauf_status "$ZT2" tag v1.5.0)
# OHNE Pipe: `git tag -l | tr ...` liefert den Status von `tr`, nicht von
# `git`. Ein gescheitertes `git` (kaputtes Repo) wurde damit zur leeren
# Tagliste — also zu einem bestandenen Fall (Fremdpruefer 20.09.2026).
TAGROH=$(git -C "$ZT2" tag -l) || TAGROH="GIT-FEHLER"
TAGS=$(printf '%s' "$TAGROH" | tr '\n' ' ')
if gate_hat_abgelehnt "$ST" && [ -z "$TAGS" ]; then
  printf '  bestanden   tag mit unlesbarer Version setzt nichts und lehnt ab\n'; GRUEN=$((GRUEN + 1))
else
  printf '  FEHLGESCHLAGEN  tag mit unlesbarer Version: %s | Tags: %s\n' "$ST" "$TAGS"; ROT=$((ROT + 1))
fi
echo
echo "$GRUEN bestanden, $ROT fehlgeschlagen"

# MINDESTZAHL — ein Waechter gegen den stillen Verlust von Faellen.
#
# Der Abschluss prueft sonst nur `ROT = 0`, und damit ist 65/0 genauso gruen
# wie 66/0: Wer einen Fall loescht, merkt es nicht (Fremdpruefer 20.09.2026).
#
# Die Zahl gehoert hierher und NICHT in einen Regeltext — hier ist sie ein
# Waechter, dort waere sie eine Erinnerung, die mit jedem Fund veraltet
# (lehren.md Paragraph 9). Wer Faelle ergaenzt, zieht sie mit.
# Der Wert ist GEMESSEN, nicht geschaetzt: ein voller Lauf meldet 67. Die
# erste Fassung dieser Zeile stand auf 70, weil ich sie geschrieben habe,
# bevor ich gezaehlt hatte — dieselbe Reflexbewegung, die in diesem Repo schon
# dreimal eine Zusage vor ihrer Messung erzeugt hat.
#
# "Mindestens", nicht "genau": Ein verlorener Fall faellt auf, ein
# hinzugefuegter blockiert nicht.
MINDESTENS=76
if [ "$((GRUEN + ROT))" -lt "$MINDESTENS" ]; then
  echo "FEHLER: nur $((GRUEN + ROT)) Faelle gelaufen, erwartet mindestens $MINDESTENS."
  echo "        Ein Fall fehlt."
  # Der Halbsatz "oder die Probe ist unterwegs gestorben" stand hier eine
  # Fassung lang und war unerreichbar: Stirbt die Probe unter `set -e`, wird
  # diese Zeile nie ausgefuehrt. Der Abbruch ist trotzdem rot — der Exit-Code
  # traegt das —, aber nicht wegen dieser Pruefung (Blindpruefer 20.09.2026).
  exit 1
fi

[ "$ROT" -eq 0 ] || exit 1
