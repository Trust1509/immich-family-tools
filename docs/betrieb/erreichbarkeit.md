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

## Abgrenzung zum Totmann-Schalter

Der Erreichbarkeits-Wächter prüft **"antwortet die Anwendung gerade"** — er
sagt nichts über den Zustand der Sicherung aus. Der Totmann-Schalter
(`docs/betrieb/totmann.md`) prüft das Gegenteil: **"ist ein Sicherungslauf in
der erwarteten Frist erfolgreich durchgelaufen"**. Beide zusammen decken die
zwei Wege ab, auf denen dieses System lautlos ausfallen kann.
