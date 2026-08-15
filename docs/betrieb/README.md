# Betriebs-Bausatz (Issue #54)

Dieses Verzeichnis enthält den vorbereiteten, aber **nicht installierten**
Betriebs-Bausatz für Rückspiel-Probe, Totmann-Schalter und
Erreichbarkeits-Wächter (siehe `docs/agents/betrieb.md` für den Maßstab,
Issue #54 für den aktuellen Stand).

**Nichts hier ist scharf geschaltet.** Kein cron-Eintrag existiert, kein
Dienst läuft, `docker-compose.yml` ist unverändert. Ein `docker compose up`
verhält sich heute genauso wie vor diesem Commit. Alle Dateien sind ein
Bausatz, den der Owner in einem bewussten Schritt installiert — mit
Platzhaltern statt echter Server-Adressen, Datensatznamen und URLs, weil der
Agent, der diesen Bausatz gebaut hat, keine Geheimnisse einträgt (siehe
Abschnitt "Umgang mit Geheimnissen" in `CLAUDE.md`).

## Inhalt

| Datei                 | Zweck                                                                         |
| --------------------- | ----------------------------------------------------------------------------- |
| `sicherung.sh`        | ZFS-Snapshot des Daten-Datasets, Aufbewahrungsregel, Totmann-Ping am Ende     |
| `rueckspiel-probe.sh` | Klont den jüngsten Snapshot in ein Wegwerf-Ziel und prüft den Inhalt fachlich |
| `erreichbarkeit.md`   | Anleitung für den Uptime-Kuma-Monitoreintrag                                  |
| `totmann.md`          | Anleitung für den externen Totmann-Dienst                                     |

## Vorschlag für `docker-compose.yml` (nicht eingetragen)

Dieser Bausatz braucht **keine** Änderung an `docker-compose.yml` — die
Skripte laufen außerhalb des Containers, direkt auf dem TrueNAS-Host, weil
sie `zfs`-Kommandos brauchen, die im Container nicht verfügbar sind (und dort
auch nicht verfügbar sein sollten — ZFS-Verwaltung gehört auf den Host).
Falls der Owner die Skripte stattdessen containerisiert ausführen möchte,
wäre folgender Ansatz eine Option — hier nur als Vorschlag notiert, nicht
umgesetzt:

```yaml
# Nur als Beispiel -- NICHT in docker-compose.yml eingetragen.
# Eigener kleiner Cron-Container mit ZFS-Zugriff auf den Host (z.B. via
# privilegiertem Mount oder Host-Cron statt Container-Cron), der
# sicherung.sh periodisch ausfuehrt.
```

Empfehlung: **Host-Cron statt Container-Cron**, weil `zfs snapshot`/`zfs
clone`/`zfs destroy` Host-Rechte brauchen, die man einem Anwendungscontainer
nicht geben sollte.

## Aktivierungsanleitung (macht der Owner, in einem Rutsch)

1. `sicherung.sh` und `rueckspiel-probe.sh` auf den TrueNAS-Server kopieren
   (z. B. nach `/root/scripts/immich-family-tools/` oder einen vergleichbaren
   Ort außerhalb des Docker-Volumes).
2. Beide Skripte ausführbar machen: `chmod 700 sicherung.sh rueckspiel-probe.sh`
   (0700 wie beim Daten-Verzeichnis — die Skripte selbst sind unkritisch, aber
   liegen im selben Vertrauensbereich).
3. In `sicherung.sh` und `rueckspiel-probe.sh` die Platzhalter
   `<pool>/<dataset>` und `<pool>/rueckspiel-probe-tmp` durch die echten
   ZFS-Namen ersetzen.
4. Totmann-Dienst einrichten (siehe `totmann.md`) und die Prüf-URL **nicht**
   im Skript, sondern als Umgebungsvariable `SICHERUNG_TOTMANN_URL` setzen
   (z. B. in der Cron-Umgebung oder einer lokalen, nicht versionierten
   `.env`-Datei auf dem Server).
5. cron-Zeile für `sicherung.sh` eintragen (täglich, z. B. `crontab -e`):
   ```
   # Beispiel, Uhrzeit an bestehende Wartungsfenster anpassen:
   0 3 * * * SICHERUNG_TOTMANN_URL="<ping-url>" /root/scripts/immich-family-tools/sicherung.sh >> /var/log/immich-family-tools-sicherung.log 2>&1
   ```
6. **Ersten Lauf von Hand anstoßen und beobachten** — nicht blind dem ersten
   Cron-Lauf vertrauen. Prüfen: Snapshot existiert (`zfs list -t snapshot`),
   alte Snapshots werden nach Ablauf der Aufbewahrungsregel entfernt, der
   Totmann-Dienst hat den Ping registriert.
7. Uptime-Kuma-Monitor anlegen wie in `erreichbarkeit.md` beschrieben.
8. **Termin für die erste Rückspiel-Probe in den Kalender eintragen**
   (vierteljährlich, wiederkehrend) — inklusive eines bekannten Albumnamens,
   der zu diesem Zeitpunkt sicher existiert, als Parameter für
   `rueckspiel-probe.sh <bekannter-albumname>`.

## Checkliste (aus `docs/agents/betrieb.md`)

- [ ] Automatischer Auszug läuft, verschlüsselt, mit Aufbewahrungsregel
- [ ] **Rückspiel-Probe terminiert** (Kalendereintrag, nicht Vorsatz)
- [ ] Totmann-Ping am Ende des Sicherungslaufs
- [ ] Erreichbarkeits-Wächter, Frequenz mit dem Hoster verträglich
- [ ] Fehler-Sammlung eingebaut (spätestens nach dem ersten stillen Fehler —
      bewusst **nicht** Teil dieses Bausatzes, siehe Issue #54)
- [ ] Wiederherstellungs-Anleitung geschrieben — **und einmal befolgt**, nicht
      nur aufgeschrieben
