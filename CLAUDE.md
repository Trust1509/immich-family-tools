# CLAUDE.md — Projektanweisungen

**Prozess-Stand: v1.12.2** — Stand der Vorlage, aus der dieses Projekt stammt.
Beim Abgleich mit einer neueren Vorlagen-Version hochsetzen; wie das geht, steht
in `docs/agents/abgleich.md` im Vorlagen-Repo `Trust1509/agent-projekt-template`
(dieses Repo führt selbst keine `abgleich.md`, weil sie nur beim Abgleichen
gebraucht wird, nicht im laufenden Betrieb). Diese Zeile bleibt im Projekt
stehen.

Immich Family Tools ist eine Companion-Web-App für selbst gehostetes Immich:
ein FastAPI-Backend und ein React/TS-Frontend in einem gemeinsamen Container,
für kontenübergreifendes Gesichts-Matching und geteilte Alben über die
Immich-REST-API. Es gibt keine eigene Datenbank — die gesamte Persistenz ist
eine einzige JSON-Datei (`accounts.json`) auf einem ZFS-Volume. Das Projekt
**erfordert Immich v3.x**.

**Profil: Anwendung ohne Datenbank.** Die gesamte Persistenz ist eine JSON-Datei;
es gibt kein Migrations-Framework, keinen Datenbank-Dienst und keine öffentlich
erreichbare Schnittstelle. Der **Prozess-Kern** (Panel, Bau-Brief, Rot-Beweis,
Release-Ritual, Betrieb) gilt vollständig. Die **Stack-Maschine**
(Migrationsköpfe, Roundtrips gegen eine echte Zieldatenbank,
Schnittstellen-Fuzzing) hat hier keinen Gegenstand — mit einer Ausnahme, die
zählt: Die Datenerhalt-Probe gilt sehr wohl, nur framework-frei, als Test gegen
das JSON-Alt-Format (`backend/tests/test_config_store.py`).

## Vor dem ersten Slice

**`docs/agents/lehren.md` lesen.** Fehlerklassen, die real getroffen haben —
Wächter, die grün sind ohne etwas zu beweisen; Seitenkanäle; Datenmigrationen,
deren Fehler kein Update mehr heilt; „weniger Abfragen", das langsamer ist —
plus ein eigener Abschnitt mit Funden aus diesem Projekt. Kostet fünf Minuten
und hat schon mehrfach einen Prod-Fund verhindert.

Für die meisten Schritte gibt es fertige Methoden-Anleitungen — welche, woher
und wann welche passt: `docs/agents/skills.md`.

## Arbeitsweise

**Issues sind der Arbeitsspeicher.** Jeder Fund, jede Entscheidung, jeder
zurückgestellte Punkt wird ein Issue — nicht eine Notiz im Chat. Siehe
`docs/agents/issue-tracker.md` und `docs/agents/triage-labels.md`.

**Ein Slice nach dem anderen.** Parallel nur, was sich nachweislich nicht
überschneidet (verschiedene Dateien, verschiedene Schichten). Sonst arbeiten zwei
Bauläufe im selben Arbeitsbaum und niemand weiß mehr, wem welche Änderung gehört.

**Der Hauptagent baut nicht selbst, er arbitriert.** Bauen macht ein Subagent mit
einem Bau-Brief (`docs/agents/bau-brief.md`), prüfen macht das Panel
(`docs/agents/panel.md`), entscheiden macht der Hauptagent — **und reproduziert
jeden Blocker am Code**, statt der Konvergenz der Prüfer zu glauben.

**Technisches selbst entscheiden, Fachliches fragen.** Bibliothekswahl,
Schnittstellen-Zuschnitt, Testform: selbst. Ob eine Zahlung auf eine
abgeschlossene Rechnung möglich sein soll: fragen. Im Zweifel: eine Annahme
formulieren, weiterbauen, die Annahme sichtbar machen.

## Risikoklasse je Slice — hier wird entschieden, was geprüft wird

Jeder Slice bekommt im Bau-Brief eine Risikoklasse mit Auslöser (Block 0:
`Risiko: R<n> — Auslöser: …`). **Die Klasse wird aus Auslösern abgeleitet,
nicht frei vergeben** — kleine Diff-Größe stuft einen R3-Auslöser nie herunter
(sechs Zeilen an einer Berechtigungsgrenze sind R3). Im Zweifel gilt die
höhere Klasse; **die Abstufung nach unten braucht die Begründung, nicht die
nach oben.**

| Klasse | Auslöser (abschließend)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | Mindestprüfung                                                                                                                                                                                                                        |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **R0** | reine Testinfrastruktur ohne Verhaltensänderung (ein neuer Test ist das NICHT); Doku-Korrektur ohne ausgelieferten Inhalt; Typisierung ohne Verhaltensänderung                                                                                                                                                                                                                                                                                                                                                                                                    | lokale Gates                                                                                                                                                                                                                          |
| _R1_   | **keine frei vergebbare Klasse** — benannte Verkürzung innerhalb von R2 für genau einen Fall: Nacharbeit mit ausschließlich mechanischen Auflagen                                                                                                                                                                                                                                                                                                                                                                                                                 | blinde Erststimme allein; Begründung unter den ausgelassenen Stimmen                                                                                                                                                                  |
| **R2** | alles ohne R0-, R3- oder R4-Auslöser (der Normalfall)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | blinde Erststimme + unabhängige Zweitstimme                                                                                                                                                                                           |
| **R3** | Datenmigration — unabhängig davon, ob ein Migrations-Framework beteiligt ist: Gemeint ist der VORGANG, bestehende Daten werden unumkehrbar umgewandelt (auch eine selbstheilende JSON-Schema-Wanderung ist eine); Berechtigungs-/Datenschutzlogik; Geld/Steuern; Außenwirkung über eine Schnittstelle; **Fremdcode** — Produktionscode, den ein FREMDES System beigesteuert hat (Patch eines Anbietermodells, zugelieferter Zweig, übernommener Schnipsel). **NICHT gemeint: der eigene Bau-Subagent** — sonst ist der Auslöser immer erfüllt und R2 verschwindet | volles Panel + risikospezifische Probe durch die echte Tür                                                                                                                                                                            |
| **R4** | irreversible Daten-/Prod-Wirkung; fachlich nicht rückholbare Entscheidung                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | R3 + ausdrückliche Owner-Freigabe. **Ein projekteigenes Release-Gate mit breiteren Auslösern bleibt davon unberührt** — diese Spalte sagt, ab wann die VORLAGE eine Freigabe verlangt, nicht, ab wann euer Projekt sie verlangen darf |

„Klein" und „gut rückrollbar" sind Urteile, keine Auslöser — und Urteile sind
der Punkt, an dem sich der Ausführende unter Druck freispricht.

**Hinweis für den Abgleich (Owner-vorlagepflichtig):** Die Tabelle besitzt die
PRÜFTIEFE (wer prüft, wie tief). Das RELEASE-GATE — wer vor einem Release
freigibt — ist eine eigene, projekteigene Größe: Ein Projekt darf breitere
Freigabe-Auslöser haben als R4 (etwa „jede Migration braucht Owner-OK"), und
die Tabelle ersetzt so ein Gate NICHT. Wer sein breiteres Gate zugunsten der
R4-Zeile aufgeben will, tut das als ausdrückliche, veto-fähige
Owner-Entscheidung — nie als Nebenwirkung der Übernahme. Real passiert: Eine
frühere Fassung dieser Zeile erklärte sich zum „Namen für" das bestehende
Riskant-Gate und verengte damit in einem Projekt sechs Freigabe-Auslöser
stillschweigend auf einen; bemerkt hat es der Abgleich, nicht die Übernahme.

**Projektspezifisch — Anwendung des Auslösers „Datenmigration":** Dieses
Projekt hat kein Alembic, aber `backend/services/config_store.py` führt beim
Start eine selbstheilende JSON-Schema-Migration aus (`SCHEMA_VERSION`,
`_migrate()`), die ungeprüft in die einzige persistente Datei des Projekts
(`accounts.json`) schreibt — und fällt damit unter den Auslöser
„Datenmigration" der Tabelle oben (R3). Einmal hier festgelegt, damit es nicht
erneut diskutiert werden muss.

Das Verfahren je Klasse beschreibt `docs/agents/panel.md`; diese Tabelle ist
der einzige Eigentümer der PRÜFTIEFEN-Auslöser. (Über Release-Freigaben
entscheidet sie nur bis R4 hinauf — projekteigene, breitere Gates siehe
Hinweis oben.)

## Review-Panel

Verbindlich nach **jedem Slice mit Klasse R2 oder höher** (siehe „Risikoklasse
je Slice" oben), vor dem Landen. Nur R0-Slices landen ohne Panel.

Drei Stimmen (blinde Erststimme, unabhängiges Modell, günstige Drittstimme —
bei R3 durch eine zweite blinde Claude-Repo-Stimme ersetzt), Ablauf,
Arbitrierung und Panel-Kommentar-Form stehen vollständig in
`docs/agents/panel.md` — keine Kurzfassung darüber hinaus, um Doppelpflege zu
vermeiden. Modellnamen und Aufrufkommandos der Stimmen 2 und 3 für dieses
Projekt stehen ebenfalls dort.

## Bau-Brief

Jeder Bau-Auftrag folgt dem Pflicht-Gerüst aus `docs/agents/bau-brief.md` —
Block 0 (`Risiko: R<n> — Auslöser: …`) plus acht Themen-Blöcke, keiner leer.
**Vor jedem Absenden verbindlich:** `sh scripts/bau-brief-pruefen.sh <brief.md>`.
Details, Begründungen und projektspezifische Prüf-Kommandos stehen dort, nicht
hier.

## Release

**Schwelle „gefahrlos":** nur Code, keine Migration — dafür gilt bei grüner CI
eine stehende Owner-Freigabe zum Taggen; jede Migration (Stufe backup oder
breaking) bleibt Owner-Sache und wird vor dem Tag gefragt, im Zweifel die
vorsichtigere Stufe.

Diese Schwelle ist das Release-Gate — und sie ist **breiter als R4**: Die
Risikoklassen-Tabelle oben hat sie nie ersetzt und ersetzt sie nicht. Dass
diese Schwelle hier überlebt hat, obwohl eine ältere Fassung der R4-Zeile sich
zum „Namen dafür" erklärte, liegt an der Ein-Eigentümer-Regel: Eine Schwelle
hat bei uns genau einen Eigentümer, und der Eigentümer dieser Schwelle ist
dieser Abschnitt, nicht die Tabelle. Diese Regel hat hier einen realen Schaden
verhindert, den ein anderes Projekt erlitten hat (siehe „Hinweis für den
Abgleich" bei der Risikoklassen-Tabelle oben).

**Folgerung aus unserer eigenen v1.11.3-Festlegung (dem Owner vorgelegt,
veto-fähig):** Weil der Auslöser „Datenmigration" bei uns framework-frei gilt,
zählt eine Änderung an der selbstheilenden JSON-Schema-Migration
(`backend/services/config_store.py`, `SCHEMA_VERSION`, `_migrate()`) als
Migration auch für diese Release-Schwelle — ein Release mit einer solchen
Änderung ist nicht „gefahrlos" und wird vor dem Tag gefragt. Dieser Punkt
folgt zwar aus einer bereits getroffenen Festlegung, ist aber selbst eine
Aussage über das Release-Gate und damit Owner-Gebiet.

Ablauf, welche Dateien die Version führen und alle
Details stehen in `docs/agents/release-ritual.md` — keine weitere
Kurzfassung hier.

## Prüfschritte

**Ein CI-Lauf je Slice, nicht je Push.** Bau, Panel und Nacharbeit landen mit
`[skip ci]`; nur der **gelandete Endstand** eines Slices läuft durch die CI.
Reine Doku-Pushes filtert `paths-ignore` (`.github/workflows/ci.yml`) von
selbst weg. Lokale Gates (der Husky-Hook) sind die **Verifikation** und
bleiben Pflicht; die CI ist die **Gegenprobe**, nicht der Erstlauf. Warum:
Das Portfolio-Tagesbudget für GitHub Actions liegt bei 100 Minuten über alle
Repos des Owners (Auslöser: 2701/3000 Portfolio-Minuten am 14.08.2026
verbraucht) — dieses Repo selbst ist PUBLIC und ein Lauf hier kostet 0
abgerechnete Minuten (Abrechnungs-API, belegt für alle Läufe seit 11.08.,
auch während der früheren Notbremse), aber die Regel gilt trotzdem: als
Portfolio-Disziplin (dieselbe Arbeitsweise in allen Repos) und weil sie
sofort real wird, sollte dieses Repo je auf privat umgeschaltet werden. Was
davon dauerhaft bleibt, weil es Qualität nicht kostet: ein pytest-Job statt
zwei, kein `pull_request`-Trigger im Trunk-Workflow, `concurrency` mit
Abbruch (Tag-Läufe ausgenommen), `paths-ignore`. Diese Regel steht **hier**
und nur hier — `release-ritual.md` und `docs/agents/lehren.md` verweisen bei
Bedarf, sie wiederholen sie nicht.

Ohne `pull_request`-Trigger laufen Dependabot-PRs ohne Vor-Merge-CI; der Lauf
auf `main` nach dem Merge ist ihr Gate — wird er rot, den Merge revertieren,
nicht reparieren.

Ein Prüfschritt, den nur die CI kennt, wird lokal nie gefahren und meldet sich
zum ungünstigsten Zeitpunkt — genau so ist `npm audit` in diesem Repo einmal
rot geworden, mitten in einem Release, ohne dass sich eine Zeile geändert
hatte. Deshalb hier **alle** Kommandos, die die CI fährt:

**Push-Pfad (`.github/workflows/ci.yml`, bei Push auf `main`/`release/**`
und bei Tags, außer bei reinem Doku-Push — Pfadfilter greifen bei Tag-Pushes
nicht):\*\*

- Backend: `pytest -q backend/tests`
- Backend: `python -m compileall -q backend`
- Frontend (in `frontend/`): `npm ci`
- Frontend (in `frontend/`): `npm test`
- Frontend (in `frontend/`): `npm run build` (enthält `tsc`)
- Container: `docker build` des Gesamt-Images (`push: false`, reiner Bau-Test)
- Secrets: `gitleaks` gegen die Commits des Pushes (bei `workflow_dispatch`:
  voller Verlauf)

Zusätzlich lokal vor jedem Commit (Husky-Pre-Commit-Hook, nicht Teil der CI,
aber dieselbe Klasse von „muss laufen, sonst meldet es sich zu spät"):

- `npx lint-staged` (prettier)
- Frontend (in `frontend/`): `npm run typecheck` (= `tsc --noEmit`)
- Frontend (in `frontend/`): `npm run test` (= `vitest run`, kein Watch-Modus)
- Backend: `pytest backend/tests/ --basetemp=/tmp/pytest-immich -q`

**Wochen-Prüfung (`.github/workflows/wochen-pruefung.yml`, montags 04:00 +
`workflow_dispatch`, bewusst **nicht** auf dem Push-Pfad):**

- Backend: `pip-audit -r backend/requirements.txt`
- Frontend (in `frontend/`): `npm audit --audit-level=high`
- Secrets: `gitleaks` gegen den vollen Verlauf — schließt die Lücke, die der
  Push-Scan systembedingt lässt (siehe `ci.yml`, Kommentar am
  `paths-ignore`), im Wochenrhythmus

## Produktivinstanz

Sonden gegen die laufende Immich-Instanz **nur lesend**. Schreibpfade
ausschließlich gegen Testdaten. Das ist ein Minimum, keine Lösung — die
strukturelle Lösung ist ein Immich-API-Key mit ausschließlich lesenden
Rechten (Immich kann granulare Rechte je Key vergeben, siehe Issue #53). Bis
dieser Read-Only-Key im Agenten-Kontext hinterlegt ist, gilt die Regel oben als
das, was tatsächlich durchsetzbar ist.

**Kein technischer Wächter — bewusst.** Ein Hook, der Werkzeugaufrufe abfängt,
liefe hier ins Leere: Die Zugriffe gehen per `curl` aus einer Shell, nicht über
einen MCP-Server. Sollte Immich je als MCP angebunden werden, gilt die Fassung
aus Vorlage v1.3.1 — und zwar mit ihren beiden Korrekturen: Der Präfix
`mcp__<schlüssel>__<tool>` stammt aus der **Client**-Konfiguration und ist frei
gewählt (ein geratener Präfix passt auf nichts), und der Wächter muss in dem
Client liegen, der die Aufrufe tatsächlich macht. Vor dem Scharfschalten die
**Echtprobe**: einen echten Aufruf auslösen und nachweisen, dass der Wächter ihn
überhaupt sieht. Ohne diesen Nachweis prüfen die Testfälle nur selbst erzeugte
Eingaben und beweisen nichts über die, die das System wirklich produziert.

## Umgang mit Geheimnissen

Der Agent trägt **keine** Schlüssel, Tokens oder Passwörter ein — auch nicht auf
Zuruf und auch nicht in eine private Datei. Er darf Platzhalter setzen, das
Format erklären und die Stelle vorbereiten; eingetragen wird vom Menschen.
`.env.example` zeigt, welche Werte gebraucht werden.

**Und die Gegenrichtung, hier real passiert:** Ein Geheimnis, das zum Sondieren
in ein Agenten-Gespräch kopiert wird, liegt danach in einem System, das es
speichert — es gilt als offengelegt und gehört rotiert, unabhängig davon, ob es
je missbraucht wurde. Deshalb gehört in den Kontext nur ein Schlüssel, dessen
Offenlegung verkraftbar ist: der Read-Only-Key aus dem Abschnitt oben, nie der
schreibberechtigte.

## Projektspezifisches

**Zweisprachigkeit.** Nutzersichtbare UI-Texte sind zweisprachig (DE/EN) über
`frontend/src/i18n.tsx` mit Typ-Parität — jeder neue Text in **beiden**
Sprachen, echte Umlaute, kein ASCII-Ersatz.

**Sync-Log.** Einträge tragen `message_key` + `message_params`; das deutsche
`details`-Feld bleibt als Fallback für Alt-Einträge bestehen, nicht für neue
Einträge verwenden.

**JSON-Migration.** Die Migration in `backend/services/config_store.py`
(`SCHEMA_VERSION`) ist rein additiv und schreibt in die einzige persistente
Datei des Projekts. Sie fällt unter **R3** (siehe „Risikoklasse je Slice"
oben). Änderungen dort brauchen einen Test gegen das Alt-Format (vorhandenes
Muster: Auffüllen der Felder UND Datenerhalt, siehe
`backend/tests/test_config_store.py`).

## Betrieb

Sobald echte Menschen echte Daten in der Anwendung haben, gilt
`docs/agents/betrieb.md`: Sicherung **mit Rückspiel-Probe**, Totmann-Schalter,
Erreichbarkeits-Wächter. Grundsatz: Ein Erfolgssignal, das in der Anwendung
selbst lebt, schweigt genau dann, wenn der Rechner stirbt. Offene Punkte laufen
als Issue #54.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (Trust1509/immich-family-tools). External PRs are a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
