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

**Dieser Abschnitt beantwortet: ist das Laufende aktuell?** — verglichen wird
gegen den **neuesten Tag im Repo**. Schritt 8 des Release-Rituals
(`docs/agents/release-ritual.md`) beantwortet eine andere Frage — **habe ich
ausgeliefert, was ich ausgecheckt habe?** — als Selbstprüfung der gerade
laufenden Auslieferung gegen den **gerade ausgecheckten Tag**, nicht gegen
den neuesten. Beide Referenzwerte fallen nur zusammen, solange zwischen dem
Auschecken und dem Vergleich kein neuerer Tag entstanden ist.

**Vertagt mit Bedingung und Termin — wirksam erst, wenn dieser
Betriebs-Bausatz installiert ist (Issue #54, Owner-Sache, keine
Zwangsinstallation). Nachfrage-Termin 31.10.2026** (Muster `lehren.md` §11:
terminiert statt stillem Verzicht). Bis dahin ist dieser Abschnitt
Vorbereitung, keine laufende Prüfung; nichts an der Produktivinstanz ändern.

**Ersatz bis dahin — mit einer wichtigen Grenze:** Der Handvergleich in
Schritt 8 des Release-Rituals läuft **nur im Moment der Auslieferung** — er
fängt, ob **diese eine** Auslieferung das ausliefert, was ausgecheckt wurde.
Er fängt **nicht** den Rückstand, der **zwischen** zwei Auslieferungen
entsteht: Ein Check, der nur beim Ausliefern feuert, sieht per Konstruktion
nie, was danach passiert. Kein vollwertiger Ersatz für die vertagte
Automatik — nur ihr Teilstück für den Auslieferungs-Augenblick. Was die
Rückstands-Klasse tatsächlich fängt, ist der **periodische Lauf** (Cron auf
dem Wächter-Host, siehe unten) — der bleibt auf #54 vertagt, Nachfrage-Termin
unverändert 31.10.2026.

**Der Fall, für den dieser Abschnitt geschrieben wurde, ist bereits
eingetreten:** Die Produktivinstanz lief mit `1.4.3`, während `v1.4.4` seit
19.08.2026 getaggt und released war — 17 Tage stiller Rückstand, jeder
bestehende Wächter grün. Der Handvergleich in Schritt 8 hätte das nicht
gemeldet: Zwischen dem Tag und diesem Fund fand keine neue Auslieferung
statt, bei der Schritt 8 hätte laufen können. Das ist der Beweis, dass die
Klasse nicht theoretisch ist.

„Antwortet die Anwendung" beweist nicht, dass sie den **aktuellen** Stand
ausliefert — ein Auslieferungs-Gate zwischen Tag und Rollout (siehe
`docs/agents/release-ritual.md`, Schritt 8) kann einen ungetaggten oder
veralteten Stand unbemerkt lange laufen lassen, während jeder Gate-Lauf und
jede Erreichbarkeitsprüfung grün bleiben.

**Das ist kein Nebenprodukt der Erreichbarkeitsprüfung ohne eigenen Lauf:**
Der Uptime-Kuma-Wächter oben führt nur eine statische Schlüsselwort-Prüfung
aus (Abschnitt oben) — er kann kein `git describe`/`git tag` ausführen und
nicht gegen einen dynamischen Wert vergleichen. Der Vergleich braucht einen
zweiten Ausführungskontext: einen eigenen Lauf (Cron auf dem Wächter-Host mit
flachem Klon) **oder** den in Schritt 8 vorhandenen Teil-Ersatz, der nur die
einzelne Auslieferung selbst prüft (siehe oben).

`GET /api/health` liefert bereits
`{"status":"ok","version":APP_VERSION,"commit":GIT_SHA}` (`backend/main.py`,
`backend/version.py`) — dieselbe Antwort, die der Erreichbarkeits-Wächter
oben ohnehin abruft. `commit` ist seit #68 dabei: `GIT_SHA` kommt aus dem
Docker-Build-Argument gleichen Namens (`Dockerfile`, `docker-compose.yml`,
`docs/agents/release-ritual.md`, Schritt 9) und bleibt `"unknown"`, wenn
dieses Argument beim Bauen fehlte — kein Absturz, keine erfundene Zahl. Der
Versionsvergleich ist ein Vergleich mit Präfix-Normalisierung: `/api/health`
liefert die Version als `<x.y.z>` ohne führendes „v" (Platzhalter für die
jeweils laufende Zahl — der Präfix-Punkt gilt unabhängig davon, welche
Version das im Einzelfall ist), Tags tragen es. Zwei echte Zeilen statt einer
Mischung aus Prosa und Shell:

```
version="v$(curl -s http://<host>:3100/api/health | jq -r .version)"
tag=$(git fetch --tags && git tag --list 'v[0-9]*' --sort=-v:refname | head -1)
```

(Vorbehalt zu `--sort=-v:refname`: Ein Vorabversions-Tag wie `v1.4.4-rc1`
sortiert damit über `v1.4.4` — heute latent, da wir keine solchen Tags
führen.)

**`commit` deckt die Lücke, die der Versionsvergleich allein lässt:** Ein
Commit NACH dem Tag ohne Versionsbump meldet weiterhin die alte, getaggte
Nummer — der Versionsvergleich oben bliebe dann still grün, obwohl der
laufende Stand nicht mehr der getaggte ist. Wer Commit gegen Commit
vergleichen will statt Version gegen Version:

```
laufender_commit=$(curl -s http://<host>:3100/api/health | jq -r .commit)
tag_commit=$(git rev-list -n 1 "$tag")
```

Ein `laufender_commit` von `"unknown"` bedeutet nicht „Stand unbekannt gleich
gut", sondern „ohne `GIT_SHA`-Build-Argument gebaut" — dieser Vergleich ist
dann nicht aussagekräftig, unabhängig davon, ob der tatsächliche Stand
zufällig passt.

**Nicht `git describe --tags --abbrev=0`:** Das liefert nicht den letzten
Tag, sondern den letzten von HEAD **erreichbaren** Tag — unabhängig davon,
ob `git fetch --tags` gelaufen ist. Zeigt HEAD auf einen Stand, von dem aus
ein neuerer Tag nicht erreichbar ist, bleibt der Check still grün, obwohl
der Tag im Repo existiert (reproduziert: `git describe --tags --abbrev=0
5b78f0b~20` → `v1.4.3` — obwohl `v1.4.4` heute im Repo existiert, ist der
Tag von diesem älteren Stand aus nicht erreichbar).

Weichen `$version` und `$tag` voneinander ab, ist entweder die Auslieferung
hinter dem letzten Tag zurück oder der Tag zeigt auf einen Stand, der nie
ausgerollt wurde — beides ein stiller Rückstand, den kein bestehender
Wächter meldet. Ein `git pull` beim Ausliefern liefert den Zweigkopf, nicht
den Tag: Liegt nach dem Tag ein ungebumpter Commit auf dem Zweig, meldet
`/api/health` weiter die alte, zum Tag passende Zahl — der Check wäre nach
der Normalisierung **grün**, obwohl der getaggte Stand nie draußen war.
Deshalb checkt Schritt 8 des Release-Rituals den Tag aus, nicht den
Zweigkopf.

**Was er zeigt und was nicht — Stand vor Slice S7:** Er fängt „Auslieferung
liegt Versionen zurück". Er fängt **nicht** „ausgeliefert wurde ein Commit
nach dem Tag ohne Versionsbump" — dafür bräuchte es den Build-SHA in
`/api/health`.

**Seit Slice S7 (#68) gibt es diesen Build-SHA:** `/api/health` liefert
zusätzlich `commit` — den Commit, aus dem das laufende Abbild gebaut wurde
(Docker-Build-Argument `GIT_SHA`, gesetzt beim `docker build`/`docker compose
build`, siehe `docs/agents/release-ritual.md`, Schritt 9). Fehlt das
Argument (alter Baubefehl, Bau ohne Docker), steht dort `"unknown"` — die App
startet trotzdem, der Vergleich unten erkennt das dann als offensichtliche
Abweichung, nicht als stilles Grün.

Der exakte Vergleich lautet damit **Commit gegen Commit**, nicht mehr Version
gegen Version:

```
commit=$(curl -s http://<host>:3100/api/health | jq -r .commit)
tag=$(git fetch --tags && git tag --list 'v[0-9]*' --sort=-v:refname | head -1)
tag_commit=$(git rev-list -n 1 "$tag")
```

Weichen `$commit` und `$tag_commit` voneinander ab (oder ist `$commit`
`"unknown"`), ist entweder ein ungetaggter Stand ausgeliefert, oder der
Baubefehl hat `GIT_SHA` nicht gesetzt — beides ein Fund. Dieser Vergleich
fängt jetzt auch den Fall, den der Versions-Vergleich oben strukturell nicht
sehen kann: einen Commit nach dem Tag ohne Versionsbump, weil `commit` sich
bei jedem neuen Commit ändert, `version` aber nur bei einem bewussten Bump.

**Was sich NICHT geändert hat:** Der **periodische Lauf**, der diesen
Vergleich automatisch und wiederkehrend fährt (Cron auf dem Wächter-Host),
bleibt auf Issue #54 vertagt — Slice S7 liefert nur den Rohstoff (`commit` in
`/api/health`), nicht die Automatisierung. Der Handvergleich in Schritt 8 des
Release-Rituals kann ab sofort denselben Commit-Vergleich nutzen, läuft aber
weiterhin nur im Auslieferungsaugenblick (siehe die Abgrenzung oben).

## Abgrenzung zum Totmann-Schalter

Der Erreichbarkeits-Wächter prüft **"antwortet die Anwendung gerade"** — er
sagt nichts über den Zustand der Sicherung aus. Der Totmann-Schalter
(`docs/betrieb/totmann.md`) prüft das Gegenteil: **"ist ein Sicherungslauf in
der erwarteten Frist erfolgreich durchgelaufen"**. Beide zusammen decken die
zwei Wege ab, auf denen dieses System lautlos ausfallen kann.
