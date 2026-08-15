#!/usr/bin/env bash
# sicherung.sh -- taegliche ZFS-Sicherung des Immich-Family-Tools-Datensatzes.
#
# WARUM ein eigenes Skript und nicht nur "zfs snapshot":
# - Ohne Aufbewahrungsregel wachsen Snapshots unbegrenzt und fuellen den Pool.
# - Ohne Totmann-Ping am Ende meldet ein ausbleibender Lauf sich NIE von
#   selbst -- der Rechner, der die Sicherung machen sollte, ist derselbe, der
#   auch das Ausbleiben melden muesste, und schweigt mit ihm, wenn er stirbt.
# - accounts.json enthaelt Immich-API-Schluessel -- jede Kopie davon (auch ein
#   Snapshot) ist selbst ein Geheimnis und braucht dieselbe Sorgfalt wie das
#   Original (Zugriff nur fuer 3006:3006, keine unverschluesselte Ablage
#   ausserhalb des Pools ohne zusaetzlichen Schutz).
#
# WICHTIG -- Reihenfolge im Skript:
# Der Totmann-Ping steht als ALLERLETZTE Zeile, NACH der letzten pruefenden
# Anweisung (Snapshot erstellt UND verifiziert, Aufbewahrung durchgelaufen).
# Er steht bewusst NICHT am Anfang und NICHT irgendwo dazwischen, wo auch ein
# Teilerfolg hindurchlaeuft (z.B. Snapshot erstellt, aber das Aufraeumen alter
# Snapshots fehlgeschlagen) -- sonst meldet der Totmann "alles gut" fuer einen
# Lauf, der in Wahrheit nichts brauchbares gesichert hat. set -e sorgt dafuer,
# dass jede vorherige Zeile das Skript sofort beendet, wenn sie fehlschlaegt;
# der Ping wird also nur erreicht, wenn wirklich alles davor durchgelaufen ist.
#
# AKTIVIERUNG (macht der Mensch, nicht dieses Skript -- siehe docs/betrieb/README.md):
# Dieses Skript tut beim blossen Kopieren auf den Server NICHTS. Es muss
# ausfuehrbar gemacht, mit echten Werten fuer DATASET befuellt, die Umgebungs-
# variable SICHERUNG_TOTMANN_URL gesetzt und per cron eingetragen werden.

set -euo pipefail

# --- Konfiguration -----------------------------------------------------
# ZFS-Datensatz, der /mnt/HDDs/Applications/immich-family-tools/data traegt.
# Platzhalter -- der Owner traegt den echten Pool-/Datensatznamen ein.
DATASET="<pool>/<dataset>"          # z.B. "HDDs/Applications/immich-family-tools/data"
SNAPSHOT_PREFIX="autobackup"
RETENTION_COUNT=14                  # wie viele taegliche Snapshots behalten werden

# Die Ping-URL kommt AUSSCHLIESSLICH aus der Umgebung -- niemals hier
# hartkodieren, sonst landet ein Geheimnis im Klartext im Repo. Siehe
# docs/betrieb/totmann.md fuer Format und Herkunft dieser URL.
: "${SICHERUNG_TOTMANN_URL:?SICHERUNG_TOTMANN_URL ist nicht gesetzt -- siehe docs/betrieb/totmann.md}"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
SNAPSHOT_NAME="${DATASET}@${SNAPSHOT_PREFIX}-${TIMESTAMP}"

# --- Sicherung -----------------------------------------------------------
echo "Erstelle Snapshot ${SNAPSHOT_NAME} ..."
zfs snapshot "${SNAPSHOT_NAME}"

# Explizit verifizieren statt nur dem Exit-Code von "zfs snapshot" zu
# vertrauen -- macht die Absicht sichtbar und faengt auch stille
# Inkonsistenzen ab (z.B. ein ZFS-Treiber, der 0 zurueckgibt, aber den
# Snapshot nicht anlegt).
if ! zfs list -t snapshot -H -o name | grep -qx "${SNAPSHOT_NAME}"; then
  echo "FEHLER: Snapshot ${SNAPSHOT_NAME} wurde nach dem Erstellen nicht gefunden." >&2
  exit 1
fi

# --- Aufbewahrung ----------------------------------------------------------
echo "Bereinige alte Snapshots (behalte die juengsten ${RETENTION_COUNT}) ..."

# Erst die vollstaendige Liste holen (schlaegt set -e fehl, wenn "zfs list"
# selbst scheitert -- das SOLL fatal sein).
ALLE_SNAPSHOTS="$(zfs list -t snapshot -H -o name -S creation)"

# Dann auf unsere Snapshots filtern. "|| true" hier ist bewusst: kein Treffer
# ist ein legitimer Zustand (z.B. beim allerersten Lauf), kein Fehler.
EIGENE_SNAPSHOTS="$(printf '%s\n' "${ALLE_SNAPSHOTS}" | grep "^${DATASET}@${SNAPSHOT_PREFIX}-" || true)"

# Alles ab Position RETENTION_COUNT+1 (aeltere Snapshots, da nach
# Erstellungsdatum absteigend sortiert) sind Kandidaten zum Entfernen.
ALTE_SNAPSHOTS="$(printf '%s\n' "${EIGENE_SNAPSHOTS}" | tail -n "+$((RETENTION_COUNT + 1))")"

if [ -n "${ALTE_SNAPSHOTS}" ]; then
  printf '%s\n' "${ALTE_SNAPSHOTS}" | while IFS= read -r snap; do
    [ -n "${snap}" ] || continue
    echo "  entferne ${snap}"
    zfs destroy "${snap}"
  done
fi

# --- Abschluss: Totmann-Ping ------------------------------------------------
# ALLERLETZTE Zeile des Skripts -- siehe Kommentar am Kopf, warum das so
# bleiben muss.
curl -fsS -m 10 --retry 3 "${SICHERUNG_TOTMANN_URL}" >/dev/null
echo "Sicherung abgeschlossen, Totmann-Ping gesendet."
