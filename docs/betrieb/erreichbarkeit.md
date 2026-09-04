# Erreichbarkeits-Wächter

**Muss außerhalb des überwachten Rechners laufen.** Der Healthcheck in
`docker-compose.yml` läuft im Container — stirbt der Host (Stromausfall,
Hardwaredefekt, Netzwerkausfall), schweigt der Healthcheck mit ihm. Ein
Wächter, der auf demselben Rechner sitzt, kann das Sterben genau dieses
Rechners per Definition nie melden. Der Abruf muss also von einer anderen
Maschine kommen.

In der vorhandenen Infrastruktur läuft bereits ein Uptime-Kuma-Wächter — hier
genügt ein zusätzlicher Eintrag, kein neuer Dienst.

## Monitor-Eintrag in Uptime-Kuma

1. **Monitor-Typ:** HTTP(s)
2. **URL:** `http://<server-ip>:3100/api/health`
3. **Methode:** GET
4. **Schlüsselwort-Prüfung aktivieren** (nicht nur "Monitor Type: HTTP(s)" mit
   reiner Statuscode-Prüfung!): Schlüsselwort `"status":"ok"`.
   Ein bloßer 200er beweist nur, dass irgendetwas auf dem Port antwortet —
   ein leerer Webserver, ein Reverse-Proxy mit Fehlerseite, ein falsch
   konfiguriertes Ziel liefern ebenfalls 200. Die Antwort der Anwendung
   selbst zu verlangen (`{"status":"ok", ...}`, siehe `GET /api/health` in
   `backend/main.py`) stellt sicher, dass tatsächlich die App geantwortet hat.
5. **Intervall:** bewusst wählen, nicht den Voreinstellungswert übernehmen.
   - Läuft der Uptime-Kuma-Wächter im selben (Heim-)Netz wie der Server, ist
     ein kurzes Intervall (z. B. 60 Sekunden) unproblematisch.
   - Ruft der Wächter über das öffentliche Internet ab (z. B. gehostet bei
     einem Anbieter, der die eigene Adresse als "fremd" sieht), können manche
     Gegenstellen häufige Anfrage-Serien als Missbrauch werten — dann lieber
     alle paar Minuten aus einem separaten Netz statt sekündlich.
   - In jedem Fall gilt: Intervall so wählen, dass ein Ausfall innerhalb einer
     für den Betrieb sinnvollen Zeit auffällt, ohne den Zielserver oder den
     Hoster unnötig zu belasten.
6. **Benachrichtigung** an den bestehenden Alarmierungskanal von Uptime-Kuma
   koppeln (derselbe, der für andere Dienste bereits eingerichtet ist).

## Rückstands-Check: „läuft es?" ist nicht „ist das Laufende aktuell?"

**Vertagt mit Bedingung — wirksam erst, wenn dieser Betriebs-Bausatz
installiert ist (Issue #54).** Bis dahin ist dieser Abschnitt Vorbereitung,
keine laufende Prüfung; nichts an der Produktivinstanz ändern.

„Antwortet die Anwendung" beweist nicht, dass sie den **aktuellen** Stand
ausliefert — ein Auslieferungs-Gate zwischen Tag und Rollout (siehe
`docs/agents/release-ritual.md`, Schritt 8) kann einen ungetaggten oder
veralteten Stand unbemerkt lange laufen lassen, während jeder Gate-Lauf und
jede Erreichbarkeitsprüfung grün bleiben.

**Kostet null zusätzliche Läufe:** `GET /api/health` liefert bereits
`{"status":"ok","version":APP_VERSION}` (`backend/main.py:160`,
`backend/version.py`) — dieselbe Antwort, die der Erreichbarkeits-Wächter
oben ohnehin abruft. Der Check ist ein Vergleich:

```
version aus GET /api/health   gegen   git describe --tags --abbrev=0
```

Weichen beide voneinander ab, ist entweder die Auslieferung hinter dem
letzten Tag zurück oder der Tag zeigt auf einen Stand, der nie ausgerollt
wurde — beides ein stiller Rückstand, den kein bestehender Wächter meldet.

## Abgrenzung zum Totmann-Schalter

Der Erreichbarkeits-Wächter prüft **"antwortet die Anwendung gerade"** — er
sagt nichts über den Zustand der Sicherung aus. Der Totmann-Schalter
(`docs/betrieb/totmann.md`) prüft das Gegenteil: **"ist ein Sicherungslauf in
der erwarteten Frist erfolgreich durchgelaufen"**. Beide zusammen decken die
zwei Wege ab, auf denen dieses System lautlos ausfallen kann.
