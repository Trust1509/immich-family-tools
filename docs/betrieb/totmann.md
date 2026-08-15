# Totmann-Schalter

## Was er leistet

Ein Totmann-Schalter meldet **das Ausbleiben eines erfolgreichen Laufs**, nicht
den Fehler selbst. `sicherung.sh` sendet als allerletzte Zeile — nach Snapshot
UND Aufbewahrungsregel, siehe Kommentar im Skript — einen Ping an eine
Prüf-URL. Bleibt dieser Ping länger als die Erwartungsfrist aus, schlägt der
Totmann-Dienst Alarm.

Der Witz an dieser Umkehrung: es ist egal, **warum** der Ping ausbleibt —
Cron nie gestartet, Rechner ausgeschaltet, Netzwerk weg, Skript hängt, ein
stiller Fehler mitten im Snapshot. Ein normaler Fehler-Alarm setzt voraus,
dass etwas läuft, das den Fehler _melden_ kann. Der Totmann setzt das nicht
voraus — er merkt an, wenn niemand sich meldet.

## Warum er extern sein muss

Ein Totmann-Dienst auf demselben Rechner wie die Sicherung stirbt mit ihm —
und genau der Fall (Rechner tot, Sicherung läuft nicht mehr) ist der Fall, den
er eigentlich melden soll. Das ist keine Nebenbedingung, das ist der ganze
Zweck eines Totmannschalters: die Instanz, die das Schweigen bemerkt, darf
nicht selbst im selben Ausfall verstummen können.

"Extern" heißt konkret: andere Hardware, eigene Stromversorgung, eigener
Netzwerkpfad als der überwachte Server. Das kann sein:

- **healthchecks.io** (oder vergleichbarer Cloud-Dienst) — kostenlos für
  kleine Nutzung, kein eigener Betrieb nötig.
- Ein **selbst gehosteter** Totmann-Dienst (z. B. dieselbe Software
  selbstgehostet, oder ein minimaler eigener "letzter Ping vor X Minuten"
  -Wächter) — solange er auf einer **anderen** Maschine läuft als der
  überwachte Server. Läuft bereits ein zweiter Server oder eine externe
  VM/ein Kleinstserver in der eigenen Infrastruktur, ist das ebenso geeignet
  wie ein Cloud-Anbieter.

Beide Varianten sind gleichwertig — entscheidend ist ausschließlich die
physische/logische Trennung von der überwachten Maschine, nicht der Anbieter.

## Wie die Prüf-URL gesetzt wird

`sicherung.sh` liest die URL ausschließlich aus der Umgebungsvariable
`SICHERUNG_TOTMANN_URL` — sie steht **nirgends** hartkodiert im Skript oder im
Repo (jede Prüf-URL, die einen Lauf auslösen kann, ist im weiteren Sinn ein
Geheimnis: wer sie kennt, kann falsche "Erfolg"-Meldungen erzeugen). Setzen
z. B. über die Umgebung des Cron-Jobs oder eine lokale, nicht versionierte
Datei auf dem Server — siehe `docs/betrieb/README.md`, Aktivierungsschritt
"Ping-URL setzen".

## Erwartungsfrist

Die Frist sollte **leicht über** dem Sicherungsintervall liegen, nicht exakt
darauf:

- `sicherung.sh` läuft z. B. täglich → Erwartungsfrist ca. 26–30 Stunden.
  Das toleriert einen einmalig leicht verspäteten Lauf (Server-Neustart,
  Wartungsfenster), erkennt aber zuverlässig einen komplett ausgebliebenen Tag.
- Zu knapp gewählt (z. B. exakt 24 Stunden) erzeugt Fehlalarme bei jeder
  kleinen Verzögerung. Zu großzügig gewählt (z. B. 3 Tage) verzögert die
  echte Meldung unnötig.

## Abgrenzung zum Erreichbarkeits-Wächter

Siehe `docs/betrieb/erreichbarkeit.md`, Abschnitt "Abgrenzung". Kurzfassung:
Totmann prüft die Sicherung, Erreichbarkeits-Wächter prüft die laufende
Anwendung — beide sind nötig, keiner ersetzt den anderen.
