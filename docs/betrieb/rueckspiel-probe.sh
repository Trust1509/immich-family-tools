#!/usr/bin/env bash
# rueckspiel-probe.sh -- fachliche Rueckspiel-Probe fuer die ZFS-Sicherung.
#
# WARUM "Rueckspiel lief ohne Fehler" NICHT genuegt:
# Ein Rueckspiel kann syntaktisch fehlerfrei durchlaufen und trotzdem eine
# leere, veraltete oder kaputte Datei liefern -- z.B. wenn der geklonte
# Snapshot vor der letzten Kontenanlage lag, wenn accounts.json durch einen
# Bug leer geschrieben wurde, oder wenn schlicht der falsche Snapshot
# erwischt wurde. "Datei existiert" ist gruen. "Exit-Code 0 beim Klonen" ist
# gruen. Beides kann gruen sein, waehrend der Inhalt fehlt. Deshalb prueft
# dieses Skript den INHALT fachlich: Konten vorhanden, Anzahl verwalteter
# Alben plausibel, ein bekannter Albumname tatsaechlich da, schema_version
# gesetzt. Jede dieser Pruefungen hat eine eigene, sprechende Fehlermeldung
# und einen von 0 verschiedenen Exit-Code bei Fehlschlag.
#
# Klont NIE in die laufenden Daten zurueck -- immer in ein Wegwerf-Ziel
# (PROBE_DATASET), das am Ende dieses Skripts wieder entfernt wird (auch bei
# einem Fehlschlag mittendrin, per trap).
#
# Aufruf: rueckspiel-probe.sh <bekannter-albumname> [mindest-anzahl-alben]
#   <bekannter-albumname>     Name eines Albums, von dem der Mensch VOR dem
#                             Lauf weiss, dass es zum Zeitpunkt des jüngsten
#                             Snapshots existiert haben sollte.
#   [mindest-anzahl-alben]    Optional, Default 1. Untergrenze fuer
#                             managed_albums -- "plausibel" ist hier bewusst
#                             als einstellbare Untergrenze umgesetzt statt als
#                             hartkodierte Zahl, weil die tatsaechlich
#                             erwartete Anzahl sich mit der Nutzung aendert.
#
# AKTIVIERUNG (macht der Mensch, nicht dieses Skript -- siehe docs/betrieb/README.md):
# Dieses Skript tut beim blossen Kopieren auf den Server NICHTS. Es muss
# ausfuehrbar gemacht, mit echten Werten fuer DATASET/PROBE_DATASET befuellt
# und beim terminierten Rueckspiel-Probe-Termin von Hand ausgefuehrt werden.
#
# Voraussetzung: jq (JSON-Auswertung von accounts.json).

set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Aufruf: $0 <bekannter-albumname> [mindest-anzahl-alben]" >&2
  exit 2
fi

ERWARTETER_ALBUMNAME="$1"
MINDEST_ALBEN="${2:-1}"

# --- Konfiguration -----------------------------------------------------
DATASET="<pool>/<dataset>"                   # derselbe Datensatz wie in sicherung.sh
SNAPSHOT_PREFIX="autobackup"
PROBE_DATASET="<pool>/rueckspiel-probe-tmp"  # Wegwerf-Ziel -- NIE der Produktions-Datensatz

# --- Aufraeumen garantiert, auch bei Fehlschlag mittendrin ------------------
cleanup() {
  if zfs list -H -o name "${PROBE_DATASET}" >/dev/null 2>&1; then
    echo "Raeume Wegwerf-Ziel ${PROBE_DATASET} auf ..."
    zfs destroy -r "${PROBE_DATASET}"
  fi
}
trap cleanup EXIT

# Falls von einem vorherigen, abgebrochenen Lauf noch ein Rest existiert:
cleanup

# --- Juengsten Snapshot ermitteln ------------------------------------------
LATEST_SNAPSHOT="$(zfs list -t snapshot -H -o name -S creation | grep "^${DATASET}@${SNAPSHOT_PREFIX}-" | head -n 1 || true)"

if [ -z "${LATEST_SNAPSHOT}" ]; then
  echo "FEHLER: Kein Snapshot mit Praefix '${SNAPSHOT_PREFIX}' auf ${DATASET} gefunden." >&2
  exit 1
fi

echo "Klone ${LATEST_SNAPSHOT} nach ${PROBE_DATASET} (Wegwerf-Ziel) ..."
zfs clone "${LATEST_SNAPSHOT}" "${PROBE_DATASET}"

PROBE_MOUNTPOINT="$(zfs get -H -o value mountpoint "${PROBE_DATASET}")"
ACCOUNTS_JSON="${PROBE_MOUNTPOINT}/accounts.json"

if [ ! -f "${ACCOUNTS_JSON}" ]; then
  echo "FEHLER: ${ACCOUNTS_JSON} existiert nicht im geklonten Snapshot." >&2
  exit 1
fi

# --- Fachliche Pruefungen ---------------------------------------------------
# Jede Pruefung laeuft unabhaengig und sammelt in FEHLER, statt beim ersten
# Treffer abzubrechen -- ein Probe-Lauf soll auf einen Blick zeigen, welche
# ALLER Erwartungen verletzt sind, nicht nur die erste.
FEHLER=0

ANZAHL_ACCOUNTS="$(jq '.accounts | length' "${ACCOUNTS_JSON}")"
if [ "${ANZAHL_ACCOUNTS}" -le 0 ]; then
  echo "FEHLER: 0 Konten in ${ACCOUNTS_JSON} -- erwartet mindestens 1." >&2
  FEHLER=1
else
  echo "OK: ${ANZAHL_ACCOUNTS} Konto/Konten gefunden."
fi

ANZAHL_ALBEN="$(jq '.managed_albums | length' "${ACCOUNTS_JSON}")"
if [ "${ANZAHL_ALBEN}" -lt "${MINDEST_ALBEN}" ]; then
  echo "FEHLER: ${ANZAHL_ALBEN} verwaltete(s) Album/Alben, erwartet mindestens ${MINDEST_ALBEN}." >&2
  FEHLER=1
else
  echo "OK: ${ANZAHL_ALBEN} verwaltete(s) Album/Alben (>= ${MINDEST_ALBEN})."
fi

ALBUM_GEFUNDEN="$(jq --arg name "${ERWARTETER_ALBUMNAME}" '[.managed_albums[] | select(.album_name == $name)] | length' "${ACCOUNTS_JSON}")"
if [ "${ALBUM_GEFUNDEN}" -lt 1 ]; then
  echo "FEHLER: Bekanntes Album '${ERWARTETER_ALBUMNAME}' nicht in ${ACCOUNTS_JSON} gefunden." >&2
  FEHLER=1
else
  echo "OK: Album '${ERWARTETER_ALBUMNAME}' gefunden."
fi

SCHEMA_VERSION="$(jq '.schema_version' "${ACCOUNTS_JSON}")"
if [ "${SCHEMA_VERSION}" = "null" ]; then
  echo "FEHLER: schema_version ist nicht gesetzt in ${ACCOUNTS_JSON}." >&2
  FEHLER=1
else
  echo "OK: schema_version = ${SCHEMA_VERSION}."
fi

if [ "${FEHLER}" -ne 0 ]; then
  echo "Rueckspiel-Probe FEHLGESCHLAGEN -- Inhalt der Sicherung ist nicht vertrauenswuerdig." >&2
  exit 1
fi

echo "Rueckspiel-Probe erfolgreich: Inhalt der Sicherung fachlich bestaetigt."
