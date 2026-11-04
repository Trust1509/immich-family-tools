#!/bin/sh
# baum-stoppen.sh — stoppt einen Prozess samt allen Nachkommen und belegt es.
#
#   sh docs/vorlagen/baum-stoppen.sh <pid>
#   PY=<absoluter Interpreter> sh docs/vorlagen/baum-stoppen.sh --selbstprobe
#
# <pid> ist die Prozessnummer, die die Shell kennt (`$!`, Spalte PID in `ps`).
#
# WARUM: Unter Git Bash erfasst `taskkill //T` die Kinder nicht, die eine Shell
# per Fork gestartet hat, und eine eigene Prozessgruppe legt eine Shell ohne
# Aufforderung nicht an; `kill` auf die Prozessnummer trifft nur den einen
# Prozess. Ein abgebrochener schwerer Lauf lief so als Waise weiter, waehrend
# die Rechner-Sperre schon frei war (gemessen, Blindpruefer v1.18.9).
#
# WIE: Den Baum sammeln, anhalten, bis er nicht mehr waechst, beenden, belegen.
# - Sammeln ueber die Elternnummer der Prozesse, die die Shell sieht
#   (/proc/<pid>/ppid unter Git Bash, /proc/<pid>/status unter Linux, sonst
#   ps). Unter Git Bash DAZU die Windows-Prozesstabelle (Win32_Process ueber
#   PowerShell): Eine Shell, die ein natives Programm startet (ein Interpreter
#   ruft `sh -c`), hat in /proc die Elternnummer 1 und haengt nur in der
#   Windows-Tabelle unter ihm; ihre Fork-Kinder haengen wieder nur in /proc
#   unter ihr (gemessen; Blind- und Gegenpruefer v1.18.12 fanden so ein
#   falsches Gruen). Ein Windows-Kind zaehlt nur, wenn es NACH seinem
#   Elternprozess gestartet ist — sonst traege eine neu vergebene Nummer einen
#   fremden Prozess in den Baum.
# - Anhalten (SIGSTOP) jede Runde, bis die Menge sich nicht mehr aendert;
#   bekannte Mitglieder bleiben, auch wenn ihr Elternprozess inzwischen endete
#   (Fremdpruefer v1.18.12). Native Windows-Prozesse lassen sich nicht anhalten.
# - Beenden: SIGKILL und unter Git Bash `taskkill /F` auf alle
#   Windows-Nummern des Baums, gebuendelt (ein Aufruf je Prozess brauchte rund
#   eine Sekunde, gemessen).
# - Belegen: Danach wird der Baum aus allen bekannten Mitgliedern neu gesammelt;
#   was noch lebt oder neu hinzukam, wird erneut beendet, hoechstens zehnmal.
#
# EXIT: 0 nur, wenn danach kein Prozess des Baums mehr lebt (Zombies zaehlen als
# beendet); die Schlusszeile nennt die Zahlen. 1: es lebt noch einer, oder der
# Baum kam innerhalb der Grenze (BAUM_STOPPEN_GRENZE Sekunden, Standard 60)
# nicht zur Ruhe — beendet wird trotzdem, was bekannt ist. 2: Aufruffehler,
# auch wenn <pid> ein Vorfahre dieses Aufrufs ist (sonst stuerbe der Aufrufer
# ohne Meldung, Gegenpruefer v1.18.12), oder die Prozesstabelle ist schon
# beim ersten Lesen nicht lesbar. Faellt die Windows-Tabelle spaeter aus (drei
# Versuche), ist das Exit 1: Ohne sie galt jeder Windows-Prozess als beendet,
# und das Werkzeug meldete gruen (Blindpruefer, Nacharbeit 1 zu v1.18.12).
#
# GRENZEN: Ein Nachkomme, der sich vom Baum loest, bevor sein Elternprozess
# angehalten ist (Elternnummer 1, etwa per `setsid` oder doppeltem Fork; auch
# zwischen dem ersten Lesen und dem Anhalten, gemessen unter Git Bash und
# Linux, Blindpruefer, Nacharbeit 1 zu v1.18.13), gehoert nicht mehr zum Baum; ebenso eine Waise, die ein Subreaper (etwa `systemd --user`) statt 1
# uebernimmt. Unter Git Bash ebenso ein Kind, das eine Shell im Hintergrund
# startet, bevor sie sich per `exec` durch ein natives Programm ersetzt
# (`helfer & exec python ...`): Es hat dann in /proc die Elternnummer 1, und
# sein Windows-Elternprozess ist beendet — keine der beiden Tabellen fuehrt zu
# ihm (gemessen, Blindpruefer, Nacharbeit 1 zu v1.18.12). Ebenso ein Enkel,
# den ein natives Programm ueber einen kurzlebigen Zwischenprozess startet
# (`cmd /c start`, Starter- und Daemon-Programme): Startet UND endet der
# Zwischenprozess zwischen zwei Lesungen, fuehrt die Elternnummer des Enkels zu
# keinem bekannten Knoten (gemessen, Blindpruefer v1.18.13); einen Zwischen-
# prozess, den ein Lesen noch sah, findet die Regel unten. Die Elternnummern
# verfolgen einen Baum also nicht lueckenlos. Nach Exit 0 zeigt unter Git Bash
# `ps -W` (auch native Prozesse; ohne Argumente und mit Elternnummer 0, eine
# Zuordnung zum Lauf gelingt nur ueber Namen und Startzeit oder ueber
# Win32_Process), sonst `ps -eo pid,ppid,lstart,args`, welche Programme noch
# laufen; wo es kein ps gibt (schlanke Container), /proc. Prozesse in einem
# Container (`docker run`) sind keine Nachkommen; der Container laeuft nach
# Exit 0 weiter (gemessen, ebenda). Startet ein natives Programm zwischen dem
# letzten Sammeln und dem Beenden ein Kind, findet das Belegen es ueber die
# Windows-Tabelle — auch, wenn der Elternprozess dann schon beendet ist, aber
# nur beim ERSTEN Lesen, bei dem er fehlt (er lebte beim vorigen), und nur,
# solange seine Nummer dann nicht neu vergeben ist. Bis v1.18.12 galt das fuer
# jedes spaetere Lesen: Wurde die Nummer neu vergeben und startete der fremde
# neue Besitzer ein Kind und endete, nahm das Werkzeug dieses fremde Kind in
# den Baum und beendete es (Blindpruefer, Nacharbeit 2 zu v1.18.12, am Code
# nachgerechnet). Bleibt: Startet ein fremder Zwischenbesitzer der Nummer
# zwischen zwei Lesungen, startet ein Kind und endet, kommt dieses fremde Kind
# in den Baum und wird beendet. Ebenso liegt zwischen
# dem Lesen der Windows-Tabelle und `taskkill` ein kurzes Fenster, in dem eine
# Nummer neu vergeben werden koennte.
# Haengt PowerShell, endet jeder Versuch nach 60 Sekunden; mit drei Versuchen
# kann ein Lesen rund drei Minuten dauern. OFFEN: Bricht PowerShell mitten in
# der Ausgabe ab (Teil-Tabelle, Exit-Status ungeprueft), gilt die Teil-Tabelle;
# fehlen darin die Prozesse des Baums, ist ein falsches Exit 0 moeglich
# (Blindpruefer, Nacharbeit 2 zu v1.18.13, mit einem Ersatz-PowerShell
# erzeugt, nicht mit echtem WMI).
#
# NUR FUER DIE SELBSTPROBE: BAUM_STOPPEN_PROBE=nicht-beenden laesst das
# Beenden aus; das Ergebnis ist dann immer Exit 1, nie ein falsches Exit 0.

set -u
LC_ALL=C
export LC_ALL

fehler() { echo "baum-stoppen: $*" >&2; }

GITBASH=""
[ -r "/proc/$$/winpid" ] && GITBASH=ja
ZEIT=""
command -v timeout >/dev/null 2>&1 && ZEIT="timeout 60"

# Die Prozesstabelle als Zeilen
#   M <pid> <ppid> <winpid oder ->      die Prozesse, die die Shell sieht
#   W <winpid> <eltern-winpid> <start>  Windows-Prozesse (nur Git Bash)
# Je Quelle EIN Lauf: grep liest weiter, wenn eine Datei zwischen Glob und
# Oeffnen verschwindet (awk brach dort ab und verlor die Wurzel; ein `cat` je
# Prozess brauchte bei 120 Prozessen sechs Sekunden — beides gemessen). Zombies
# und beendete Prozesse zaehlen nicht: unter Linux nach State in
# /proc/<pid>/status; unter Git Bash fuehrt /proc einen Zombie gar nicht in
# seiner Liste (nur direkt ueber die Nummer, mit seiner alten winpid) — der
# Glob unten sieht ihn also nie (gemessen; die Selbstprobe haelt es fest). Ein
# Prozess der Shell, dessen Windows-Prozess fehlt, gilt dort zudem als beendet.
# /proc/*/status zu lesen kostete unter Git Bash rund drei Sekunden je
# Durchlauf (gemessen). Die Weiche fragt den EIGENEN Eintrag,
# nie `ls /proc/*/x` (flackerte, wenn ein Prozess verschwand).
tabelle() {
    if [ -n "$GITBASH" ]; then
        grep -H '' /proc/[0-9]*/ppid /proc/[0-9]*/winpid 2>/dev/null \
          | sed -n -e 's#^/proc/\([0-9][0-9]*\)/ppid:\([0-9][0-9]*\)$#P \1 \2#p' \
                   -e 's#^/proc/\([0-9][0-9]*\)/winpid:\([0-9][0-9]*\)$#N \1 \2#p' \
          | awk '$1 == "P" { pp[$2] = $3 } $1 == "N" { wp[$2] = $3 }
                 END { for (p in pp) print "M", p, pp[p], ((p in wp) ? wp[p] : "-") }'
        MSYS_NO_PATHCONV=1 $ZEIT powershell.exe -NoProfile -NonInteractive -Command \
            'Get-CimInstance Win32_Process | ForEach-Object { "W {0} {1} {2}" -f $_.ProcessId, $_.ParentProcessId, ([int64]($_.CreationDate.Ticks)) }' \
            2>/dev/null | tr -d '\r'
    elif [ -r "/proc/$$/status" ]; then
        grep -H -e '^PPid:' -e '^State:' /proc/[0-9]*/status 2>/dev/null \
          | sed -n -e 's#^/proc/\([0-9][0-9]*\)/status:PPid:[[:space:]]*\([0-9][0-9]*\)$#P \1 \2#p' \
                   -e 's#^/proc/\([0-9][0-9]*\)/status:State:[[:space:]]*\([A-Za-z]\).*$#S \1 \2#p' \
          | awk '$1 == "P" { pp[$2] = $3 } $1 == "S" { st[$2] = $3 }
                 END { for (p in pp) if (st[p] != "Z" && st[p] != "X") print "M", p, pp[p], "-" }'
    else
        ps -A -o pid= -o ppid= -o stat= 2>/dev/null \
          | awk '$3 !~ /^Z/ { print "M", $1, $2, "-" }'
    fi
}

# Die Tabelle, unter Git Bash nur mit Windows-Zeilen (drei Versuche); sonst
# Exit 1 und keine Ausgabe.
lies_tabelle() {
    v=0
    while [ "$v" -lt 3 ]; do
        t=$(tabelle)
        if [ -z "$GITBASH" ] || printf '%s\n' "$t" | grep -q '^W '; then
            printf '%s\n' "$t"; return 0
        fi
        v=$((v + 1)); sleep 1
    done
    return 1
}

# Der lebende Baum zur Wurzel $1 aus der Tabelle auf stdin, ausgehend von den
# bekannten Knoten $2 ("m<pid>" fuer Prozesse der Shell, "w<winpid>:<start>"
# fuer Windows-Prozesse). Ein bekannter Prozess der Shell bleibt nur, solange
# sein Elternprozess die Wurzel, ein bekannter Knoten oder 1 ist (Waisen haengen
# unter Linux an 1) — damit eine neu vergebene Nummer keinen fremden Prozess
# trifft. Ausgabe: die Knoten, bekannte zuerst, in EINER Zeile.
huelle() {
    awk -v wurzel="$1" -v bekannt="$2" -v zuletzt="${3:-}" '
        $1 == "M" { mpp[$2] = $3; mkind[$3] = mkind[$3] " " $2
                    if ($4 != "-") { mwin[$2] = $4; winm[$4] = winm[$4] " " $2 } }
        $1 == "W" { wpar[$2] = $3; wst[$2] = $4; wkind[$3] = wkind[$3] " " $2; hatw = 1 }
        # Ein Prozess der Shell lebt, wenn er in der Tabelle steht und — gibt es
        # die Windows-Tabelle — sein Windows-Prozess auch (sonst ist er ein
        # Zombie unter Git Bash).
        function da(k,   a, p) {
            if (substr(k, 1, 1) == "m") {
                p = substr(k, 2)
                return ((p in mpp) && (!hatw || ((p in mwin) && (mwin[p] in wst))))
            }
            split(substr(k, 2), a, ":"); return ((a[1] in wst) && wst[a[1]] == a[2])
        }
        function dazu(k) { if (!(k in drin) && da(k)) { drin[k] = 1; liste = liste " " k; neu = neu " " k } }
        END {
            n = split(bekannt, b, " ")
            for (i = 1; i <= n; i++) mitglied[b[i]] = 1
            for (i = 1; i <= n; i++) {
                k = b[i]
                if (k in drin) continue
                if (substr(k, 1, 1) == "m" && k != "m" wurzel) {
                    p = substr(k, 2)
                    if (!(("m" mpp[p]) in mitglied) && mpp[p] != 1) continue
                }
                dazu(k)
            }
            # Ein Windows-Prozess, der beim vorigen Lesen ($3) noch lebte und
            # jetzt fehlt: seine Kinder gehoeren weiter zum Baum (ein natives
            # Programm startete eines kurz vor dem Beenden, Blindpruefer,
            # Nacharbeit 1 zu v1.18.12) — nur in diesem einen Lesen und nur,
            # solange seine Nummer nicht neu vergeben ist (GRENZEN).
            n = split(zuletzt, b, " ")
            for (i = 1; i <= n; i++) {
                k = b[i]
                if (substr(k, 1, 1) != "w") continue
                split(substr(k, 2), a, ":")
                if (a[1] in wst) continue
                c = split(wkind[a[1]], kk, " ")
                for (j = 1; j <= c; j++)
                    if (wst[kk[j]] >= a[2]) dazu("w" kk[j] ":" wst[kk[j]])
            }
            stufe = neu
            while (stufe != "") {
                neu = ""; m = split(stufe, s, " ")
                for (i = 1; i <= m; i++) {
                    k = s[i]
                    if (substr(k, 1, 1) == "m") {
                        p = substr(k, 2)
                        c = split(mkind[p], kk, " ")
                        for (j = 1; j <= c; j++) dazu("m" kk[j])
                        if ((p in mwin) && (mwin[p] in wst)) dazu("w" mwin[p] ":" wst[mwin[p]])
                    } else {
                        split(substr(k, 2), a, ":"); x = a[1]
                        c = split(wkind[x], kk, " ")
                        for (j = 1; j <= c; j++)
                            if (wst[kk[j]] >= wst[x]) dazu("w" kk[j] ":" wst[kk[j]])
                        c = split(winm[x], kk, " ")
                        for (j = 1; j <= c; j++) dazu("m" kk[j])
                    }
                }
                stufe = neu
            }
            sub(/^ /, "", liste); print liste
        }'
}

# Alle Knoten der Liste $* beenden: Prozesse der Shell mit SIGKILL, alle
# Windows-Nummern gebuendelt mit taskkill /F (je 40). Ein angehaltener Prozess
# der Shell starb unter Git Bash erst durch taskkill (gemessen).
beenden() {
    wps=""; zahl=0
    for k in "$@"; do
        case "$k" in
            m*) [ "${k#m}" = "$$" ] || kill -KILL "${k#m}" 2>/dev/null ;;
            w*) x=${k#w}; wps="$wps /PID ${x%%:*}"; zahl=$((zahl + 1))
                if [ "$zahl" -ge 40 ]; then
                    MSYS_NO_PATHCONV=1 taskkill /F $wps >/dev/null 2>&1; wps=""; zahl=0
                fi ;;
        esac
    done
    [ -z "$wps" ] || MSYS_NO_PATHCONV=1 taskkill /F $wps >/dev/null 2>&1
    for k in "$@"; do case "$k" in m*) kill -CONT "${k#m}" 2>/dev/null ;; esac; done
}

zaehle() { n=0; for k in $1; do case "$k" in "$2"*) n=$((n + 1)) ;; esac; done; echo "$n"; }

stoppen() {
    wurzel=$1
    case "$wurzel" in ''|*[!0-9]*) fehler "Aufruffehler: Prozessnummer erwartet, nicht '$wurzel'"; return 2 ;; esac
    [ "$wurzel" -gt 1 ] || { fehler "Aufruffehler: Prozessnummer $wurzel wird nie gestoppt"; return 2; }
    grenze=${BAUM_STOPPEN_GRENZE:-60}
    case "$grenze" in ''|*[!0-9]*) fehler "Aufruffehler: BAUM_STOPPEN_GRENZE ist keine Zahl"; return 2 ;; esac
    tab=$(lies_tabelle) \
        || { fehler "Aufbau: die Windows-Prozesstabelle ist nicht lesbar (PowerShell)"; return 2; }
    # Anhalten, bis die Menge sich nicht mehr aendert
    bekannt="m$wurzel"; vorher=""; stabil=""; beginn=$(date +%s); erster=ja
    while :; do
        if [ -z "$erster" ] && ! tab=$(lies_tabelle); then
            [ "${BAUM_STOPPEN_PROBE:-}" = nicht-beenden ] || beenden $baum
            fehler "ROT: die Windows-Prozesstabelle fiel aus; beendet ist, was bekannt war, belegt ist nichts"
            return 1
        fi
        baum=$(printf '%s\n' "$tab" | huelle "$wurzel" "$bekannt" "$vorher")
        if [ -n "$erster" ]; then
            erster=""
            case " $baum " in *" m$wurzel "*) ;; *)
                fehler "Aufruffehler: Prozess $wurzel lebt nicht (oder die Prozesstabelle zeigt ihn nicht)"
                return 2 ;;
            esac
            # Ist dieser Aufruf selbst im Baum, ist <pid> ein Vorfahre.
            ich_w=""; [ -n "$GITBASH" ] && ich_w=$(cat "/proc/$$/winpid" 2>/dev/null)
            for k in $baum; do
                case "$k" in "m$$"|"w$ich_w:"*)
                    fehler "Aufruffehler: Prozess $wurzel ist ein Vorfahre dieses Aufrufs"; return 2 ;;
                esac
            done
        fi
        for k in $baum; do case "$k" in "m$$") ;; m*) kill -STOP "${k#m}" 2>/dev/null ;; esac; done
        if [ "$baum" = "$vorher" ]; then stabil=ja; break; fi
        vorher=$baum; bekannt="$bekannt $baum"
        [ $(($(date +%s) - beginn)) -ge "$grenze" ] && break
    done
    alle=$baum
    # Beenden und belegen
    runde=0; rest=$baum
    while [ -n "$rest" ] && [ "$runde" -lt 10 ]; do
        [ "${BAUM_STOPPEN_PROBE:-}" = nicht-beenden ] || beenden $rest
        sleep 0.3
        tab=$(lies_tabelle) || {
            fehler "ROT: die Windows-Prozesstabelle fiel aus; belegt ist nichts"; return 1; }
        rest=$(printf '%s\n' "$tab" | huelle "$wurzel" "$bekannt $alle" "$rest")
        for k in $rest; do case " $alle " in *" $k "*) ;; *) alle="$alle $k" ;; esac; done
        runde=$((runde + 1))
    done
    if [ -n "$rest" ]; then
        [ "${BAUM_STOPPEN_PROBE:-}" = nicht-beenden ] && for k in $rest; do
            case "$k" in m*) kill -CONT "${k#m}" 2>/dev/null ;; esac; done
        fehler "ROT: es leben noch: $rest"
        return 1
    fi
    m=$(zaehle "$alle" m); w=$(zaehle "$alle" w)
    if [ -z "$stabil" ]; then
        fehler "ROT: Der Baum kam in $grenze s nicht zur Ruhe. Beendet ist, was bekannt war ($m Prozess(e) der Shell, $w Windows-Prozess(e)); was danach entstand, ist nicht belegt."
        return 1
    fi
    echo "baum-stoppen gruen: $m Prozess(e) der Shell und $w Windows-Prozess(e) gestoppt, keiner lebt mehr (Wurzel $wurzel)"
    return 0
}

selbstprobe() {
    geprueft=0; fehl=""
    erwarte() { geprueft=$((geprueft + 1)); [ "$2" = "$3" ] || fehl="$fehl
  - $1: erwartet '$3', bekommen '$2'"; }
    PY=${PY:-}
    ich=$0
    # POSIX-Form, auch bei TMPDIR=C:/...: Unten steht $d in PATH, und dort zerfaellt
    # der Pfad am Laufwerks-Doppelpunkt; die Attrappe wurde nie gefunden und die
    # Probe war rot (gemessen in einem Kind-Repo, v1.18.13).
    # Scheitert mktemp, bricht die Probe ab: Unter dash ist 'cd ""' ein Erfolg, d waere
    # das Arbeitsverzeichnis, und die Notbremse loeschte es (Gegenpruefer v1.19.0).
    d=$(mktemp -d) || { echo "baum-stoppen Selbstprobe: kein Arbeitsverzeichnis (mktemp)" >&2; exit 2; }
    d=$(CDPATH= cd -- "$d" && pwd) || { echo "baum-stoppen Selbstprobe: Arbeitsverzeichnis nicht erreichbar" >&2; exit 2; }
    # Das Orakel sind Listen, die die Prozesse der Probe SELBST schreiben, nicht
    # die Sammel-Funktionen dieses Werkzeugs (Blindpruefer v1.18.12). Jede
    # Nummer landet auch in der Notbremse: Wird die Probe rot oder bricht ab,
    # beendet sie alles, was sie gestartet hat (vorher blieb eine endlose
    # Fork-Schleife stehen, Blindpruefer v1.18.12).
    # Ohne Arbeitsverzeichnis: Exit 2 statt gruen und ohne etwas zu loeschen.
    if [ -z "${BAUM_STOPPEN_INNERE_PROBE:-}" ]; then
        ich_ganz=$(CDPATH= cd -- "$(dirname "$ich")" && pwd)/$(basename "$ich")
        (cd "$d" && : > kanarie && TMPDIR="$d/gibt-es-nicht" BAUM_STOPPEN_INNERE_PROBE=1 sh "$ich_ganz" --selbstprobe >/dev/null 2>&1)
        erwarte "ohne Arbeitsverzeichnis Exit 2" "$?" "2"
        [ -e "$d/kanarie" ]; erwarte "ohne Arbeitsverzeichnis bleibt das cwd stehen" "$?" "0"
    fi
    notbremse() {
        # Ein angehaltener Prozess der Shell starb unter Git Bash erst durch
        # taskkill (Blindpruefer, Nacharbeit 1 zu v1.18.12).
        for p in $(cat "$d"/*.liste 2>/dev/null); do
            if [ -n "$GITBASH" ]; then
                w=$(cat "/proc/$p/winpid" 2>/dev/null) \
                    && MSYS_NO_PATHCONV=1 taskkill /F /PID "$w" >/dev/null 2>&1
            fi
            kill -KILL "$p" 2>/dev/null
        done
        if [ -n "$GITBASH" ]; then
            for p in $(cat "$d"/*.win 2>/dev/null); do MSYS_NO_PATHCONV=1 taskkill /F /PID "$p" >/dev/null 2>&1; done
        fi
        rm -rf "$d"
    }
    trap notbremse EXIT
    trap 'exit 130' INT TERM
    lebt_noch() { r=""; for p in $(cat "$1" 2>/dev/null); do
        if [ -r "/proc/$$/status" ]; then
            z=$(sed -n 's/^State:[[:space:]]*\([A-Za-z]\).*/\1/p' "/proc/$p/status" 2>/dev/null)
            case "$z" in ''|Z|X) ;; *) r="$r $p" ;; esac
        else
            kill -0 "$p" 2>/dev/null && case "$(ps -o stat= -p "$p" 2>/dev/null)" in Z*) ;; *) r="$r $p" ;; esac
        fi
    done; echo "${r:-keiner}"; }
    warte_liste() { i=0; while [ "$i" -lt 100 ]; do
        [ "$(wc -l < "$1" 2>/dev/null || echo 0)" -ge "$2" ] && return 0
        sleep 0.2; i=$((i + 1)); done; return 1; }
    # Ein Baum: Wurzel -> sleep, Shell -> zwei sleep; alle fuenf in der Liste
    baum5() {
        : > "$1"
        sh -c 'echo $$ >> "$0"; sleep 600 & echo $! >> "$0"
               sh -c '"'"'echo $$ >> "$0"; sleep 600 & echo $! >> "$0"; sleep 600 & echo $! >> "$0"; wait'"'"' "$0" &
               wait' "$1" >/dev/null 2>&1 &
        warte_liste "$1" 5
    }

    # 0. Die Huelle mit erfundenen Tabellen (keine echten Prozesse): Kinder eines
    #    beendeten Windows-Prozesses nur im ersten Lesen danach und nur, wenn
    #    seine Nummer nicht neu vergeben ist (Blindpruefer, Nacharbeit 2 zu
    #    v1.18.12).
    erfunden='M 10 1 900
W 900 1 4000
W 200 100 5600'
    h=$(printf '%s\n' "$erfunden" | huelle 10 "m10 w100:5000" "w100:5000")
    case " $h " in *" w200:5600 "*) z=ja ;; *) z="$h" ;; esac
    erwarte "Huelle: Kind eines eben beendeten Windows-Prozesses gehoert dazu" "$z" ja
    h=$(printf '%s\n' "$erfunden" | huelle 10 "m10 w100:5000" "m10")
    case " $h " in *" w200:"*) z="$h" ;; *) z=nein ;; esac
    erwarte "Huelle: nicht mehr in einem spaeteren Lesen" "$z" nein
    h=$(printf '%s\n' "$erfunden" 'W 100 1 7000' | huelle 10 "m10 w100:5000" "w100:5000")
    case " $h " in *" w200:"*) z="$h" ;; *) z=nein ;; esac
    erwarte "Huelle: nicht, wenn die Nummer neu vergeben ist" "$z" nein

    # 0b. Ein Zombie steht nicht in der Tabelle: ein Kind endet unter einem
    #     Elternprozess, der es nicht abholt. Unter Linux haelt das den Filter
    #     nach State fest, unter Git Bash die gemessene Eigenschaft von /proc
    #     (Gegenpruefer v1.18.13 fragte nach Zombies mit alter winpid).
    sh -c 'sleep 0.2 & echo $! > "$0"; exec sleep 5' "$d/zombie.liste" >/dev/null 2>&1 &
    zw=$!; echo "$zw" >> "$d/zombie.liste.wurzel"; i=0
    while [ ! -s "$d/zombie.liste" ] && [ "$i" -lt 50 ]; do sleep 0.1; i=$((i + 1)); done
    sleep 1.5
    zp=$(cat "$d/zombie.liste" 2>/dev/null)
    zs=$(sed -n 's/^State:[[:space:]]*\([A-Za-z]\).*/\1/p' "/proc/${zp:-0}/status" 2>/dev/null)
    erwarte "Zombie entstanden (State Z)" "${zs:-keiner}" Z
    z=$(tabelle | awk -v p="${zp:-0}" '$1 == "M" && $2 == p { print "steht drin" }')
    erwarte "Zombie fehlt in der Tabelle" "${z:-fehlt}" fehlt
    cp "$d/zombie.liste.wurzel" "$d/zw.liste"

    # 1. Aufruffehler, auch ein Vorfahre als Wurzel
    sh "$ich" >/dev/null 2>&1; erwarte "ohne Argument" "$?" 2
    sh "$ich" abc >/dev/null 2>&1; erwarte "keine Zahl" "$?" 2
    sh "$ich" 1 >/dev/null 2>&1; erwarte "Nummer 1" "$?" 2
    sh "$ich" 999999999 >/dev/null 2>&1; erwarte "toter Prozess" "$?" 2
    sh -c 'sh "$0" $$; echo "rc $?"' "$ich" > "$d/vorfahre.aus" 2>&1
    erwarte "eigener Vorfahre -> Exit 2, der Aufrufer lebt weiter" "$(cat "$d/vorfahre.aus" | tail -1)" "rc 2"

    # 2. Ein Baum aus Shells
    baum5 "$d/b2.liste"
    aus=$(sh "$ich" "$(head -1 "$d/b2.liste")" 2>&1); rc=$?
    erwarte "Shell-Baum: Exit" "$rc" 0
    erwarte "Shell-Baum: keiner lebt" "$(lebt_noch "$d/b2.liste")" keiner
    case "$aus" in "baum-stoppen gruen: 5 Prozess(e) der Shell"*) z=ja ;; *) z="$aus" ;; esac
    erwarte "Schlusszeile nennt die Zahl" "$z" ja

    # 3. Gegenproben: nur die Wurzel beenden laesst Waisen — mit kill, und
    #    unter Git Bash auch mit taskkill //T auf ihre Windows-Nummer
    for weg in kill taskkill; do
        [ "$weg" = taskkill ] && [ -z "$GITBASH" ] && continue
        baum5 "$d/g$weg.liste"; w=$(head -1 "$d/g$weg.liste")
        if [ "$weg" = kill ]; then kill -KILL "$w" 2>/dev/null
        else MSYS_NO_PATHCONV=1 taskkill /T /F /PID "$(cat "/proc/$w/winpid")" >/dev/null 2>&1; fi
        sleep 1
        erwarte "Gegenprobe $weg auf die Wurzel laesst Waisen" \
            "$([ "$(lebt_noch "$d/g$weg.liste")" != keiner ] && echo ja || echo nein)" ja
    done

    # 4. Ein Baum, der waehrend des Stoppens weiter Kinder startet
    : > "$d/b4.liste"
    sh -c 'echo $$ >> "$0"; while :; do sleep 600 & echo $! >> "$0"; sleep 0.05; done' "$d/b4.liste" >/dev/null 2>&1 &
    warte_liste "$d/b4.liste" 4
    sh "$ich" "$(head -1 "$d/b4.liste")" >/dev/null 2>&1; rc=$?
    erwarte "wachsender Baum: Exit" "$rc" 0
    sleep 0.5
    erwarte "wachsender Baum: kein Kind aus der Liste lebt" "$(lebt_noch "$d/b4.liste")" keiner

    # 5. Kommt der Baum nicht zur Ruhe, ist das Exit 1 (Grenze 0: eine Runde)
    baum5 "$d/b5.liste"
    BAUM_STOPPEN_GRENZE=0 sh "$ich" "$(head -1 "$d/b5.liste")" >/dev/null 2>&1
    erwarte "nicht zur Ruhe gekommen -> Exit 1" "$?" 1

    # 6. Die Schlusspruefung wirkt: ohne Beenden Exit 1, und der Baum lebt noch
    baum5 "$d/b6.liste"
    BAUM_STOPPEN_PROBE=nicht-beenden sh "$ich" "$(head -1 "$d/b6.liste")" >/dev/null 2>&1
    erwarte "ohne Beenden -> Exit 1" "$?" 1
    erwarte "ohne Beenden lebt der Baum noch" "$(($(lebt_noch "$d/b6.liste" | wc -w)))" 5

    # 6b. Unter Git Bash: Faellt die Windows-Tabelle nach dem ersten Lesen aus,
    #     ist das Exit 1 (vorher gruen, Blindpruefer, Nacharbeit 1 zu v1.18.12).
    if [ -n "$GITBASH" ]; then
        echada=$(command -v powershell.exe)
        mkdir "$d/ausfall"
        printf '%s\n' '#!/bin/sh' \
            "n=\$(cat '$d/ausfall/zaehler' 2>/dev/null || echo 0)" \
            "echo \$((n + 1)) > '$d/ausfall/zaehler'" \
            '[ "$n" -ge 1 ] && exit 1' \
            "exec '$echada' \"\$@\"" > "$d/ausfall/powershell.exe"
        chmod +x "$d/ausfall/powershell.exe"
        baum5 "$d/b6b.liste"
        PATH="$d/ausfall:$PATH" sh "$ich" "$(head -1 "$d/b6b.liste")" >/dev/null 2>&1
        erwarte "Windows-Tabelle faellt spaeter aus -> Exit 1" "$?" 1
    fi

    nativ=""
    if [ -n "$PY" ]; then
        nativ=", Interpreter mit Kind, Interpreter mit Shell"
        # 7. Ein Interpreter mit eigenem Kind: Das Kind schreibt seine Nummer
        #    (unter Git Bash die Windows-Nummer, die nur tasklist sieht).
        printf '%s\n' 'import os, subprocess, sys, time' \
            'kind = "import os, sys, time; open(sys.argv[1] + \".tmp\", \"w\").write(str(os.getpid())); os.replace(sys.argv[1] + \".tmp\", sys.argv[1]); time.sleep(600)"' \
            'subprocess.Popen([sys.executable, "-I", "-S", "-c", kind, sys.argv[1]])' \
            'time.sleep(600)' > "$d/eltern.py"
        "$PY" -I -S "$d/eltern.py" "$d/kind.win" >/dev/null 2>&1 &
        w=$!; echo "$w" > "$d/b7.liste"
        i=0; while [ ! -s "$d/kind.win" ] && [ "$i" -lt 75 ]; do sleep 0.2; i=$((i + 1)); done
        kpid=$(cat "$d/kind.win" 2>/dev/null)
        erwarte "Interpreter mit Kind: Kind gestartet" "$([ -n "$kpid" ] && echo ja || echo nein)" ja
        [ -n "$GITBASH" ] || cp "$d/kind.win" "$d/b7k.liste" 2>/dev/null
        sh "$ich" "$w" >/dev/null 2>&1
        erwarte "Interpreter mit Kind: Exit" "$?" 0
        sleep 1
        if [ -n "$GITBASH" ]; then
            da=$(MSYS_NO_PATHCONV=1 tasklist /FI "PID eq ${kpid:-0}" /NH 2>/dev/null | grep -c " ${kpid:-0} " || true)
        else
            da=0; [ "$(lebt_noch "$d/b7k.liste")" = keiner ] || da=1
        fi
        erwarte "Interpreter mit Kind: das Kind lebt nicht mehr" "$da" 0

        # 8. Ein Interpreter startet eine Shell, die per Fork Kinder hat. Unter
        #    Git Bash hat diese Shell in /proc die Elternnummer 1 (Blind- und
        #    Gegenpruefer v1.18.12: falsches Gruen).
        shpfad=$(command -v sh)
        [ -n "$GITBASH" ] && command -v cygpath >/dev/null 2>&1 && shpfad=$(cygpath -w "$shpfad")
        printf '%s\n' 'import subprocess, sys, time' \
            'subprocess.Popen([sys.argv[1], "-c", "echo $$ >> \"$0\"; sleep 600 & echo $! >> \"$0\"; sleep 600 & echo $! >> \"$0\"; wait", sys.argv[2]])' \
            'time.sleep(600)' > "$d/huelle.py"
        : > "$d/b8.liste"
        "$PY" -I -S "$d/huelle.py" "$shpfad" "$d/b8.liste" >/dev/null 2>&1 &
        w=$!; echo "$w" > "$d/b8w.liste"
        warte_liste "$d/b8.liste" 3
        erwarte "Interpreter mit Shell: Shell und Kinder gestartet" "$(wc -l < "$d/b8.liste")" 3
        sh "$ich" "$w" >/dev/null 2>&1
        erwarte "Interpreter mit Shell: Exit" "$?" 0
        sleep 0.5
        erwarte "Interpreter mit Shell: keiner aus der Liste lebt" "$(lebt_noch "$d/b8.liste")" keiner
    fi
    if [ -n "$fehl" ]; then
        echo "baum-stoppen Selbstprobe ROT:$fehl" >&2
        return 1
    fi
    # 19 immer; dazu 6 mit PY, 2 unter Git Bash (Gegenprobe mit taskkill, Ausfall)
    soll=19; [ -n "$PY" ] && soll=$((soll + 6)); [ -n "$GITBASH" ] && soll=$((soll + 2))
    [ "$geprueft" -ge "$soll" ] || { echo "baum-stoppen Selbstprobe ROT: nur $geprueft statt $soll Erwartungen" >&2; return 1; }
    echo "baum-stoppen Selbstprobe gruen: $geprueft Erwartungen (Huelle mit erfundenen Tabellen, Zombie, Aufruffehler und Vorfahre, Shell-Baum, Gegenprobe Wurzel allein, wachsender Baum, keine Ruhe, Schlusspruefung$nativ)"
}

case "${1:-}" in
    --selbstprobe) selbstprobe; exit $? ;;
    '') fehler "Aufruffehler: sh baum-stoppen.sh <pid> | --selbstprobe"; exit 2 ;;
    *) [ $# -eq 1 ] || { fehler "Aufruffehler: genau eine Prozessnummer"; exit 2; }
       stoppen "$1"; exit $? ;;
esac
