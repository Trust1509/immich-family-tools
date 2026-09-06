# Release-Ritual

## Grundsätze

**Version und Notizen im selben Commit.** Ein Tag ohne gepflegte Notizen zeigt
dem Nutzer die Angaben der Vorversion — inklusive falscher Risiko-Kennzeichnung.
Ein Skript-Gate, das genau das abfängt, hat sich bewährt: Es bricht ab, wenn die
Versionsnummer nicht zum obersten Notizen-Eintrag passt.

In diesem Projekt führen **vier** Dateien die Version, alle im selben Commit:
`backend/version.py`, `frontend/src/version.ts`, `frontend/package.json` und
`CHANGELOG.md`. Die ersten drei schreibt `sh scripts/release.sh bump <version>`,
die vierte ist Handarbeit — Prosa in der Sprache des Nutzers schreibt kein
Skript.

**Diese Liste hat hier ihren Eigentümer**, und `scripts/release.sh` führt
dieselbe Liste ein zweites Mal, weil ein Skript sie nicht erraten kann. Kommt
eine fünfte Stelle dazu (etwa die Build-Kennung aus Issue #68), gehört sie in
**beide** — sonst entsteht genau die Zwei-Dateien-Drift aus `lehren.md` §17.
Das Skript nennt diese Datei in seinem Kopfkommentar, damit die Verbindung von
beiden Seiten sichtbar ist.

**Die Notizen führen, die Version folgt.** `bump` weigert sich zu schreiben,
solange der oberste CHANGELOG-Eintrag nicht bereits die Zielversion trägt.
Andernfalls entsteht der Zustand, den die Risiko-Kennzeichnung verhindern
soll: Code auf der neuen Nummer, Notizen auf der alten.

**Die Risiko-Stufe steht als eigene Zeile im Eintrag** und wird vom Gate
geprüft, sonst zeigt der Tag die Einstufung der Vorversion:

```
## [1.5.0] – 2026-09-06

**Risk: safe**
```

`safe` / `backup` / `breaking` entsprechen den drei Stufen unten. Die Zeile
muss **innerhalb** des obersten Eintrags stehen; eine im Vorgänger zählt
nicht. Alte Einträge werden **nicht** rückwirkend ergänzt — der Changelog ist
eine dokumentierende Datei (`lehren.md` §17).

**Risiko ehrlich kennzeichnen.** Bewährte Stufen:

| Stufe     | im CHANGELOG | Bedeutung                              |
| --------- | ------------ | -------------------------------------- |
| gefahrlos | `safe`       | nur Code, keine Migration              |
| backup    | `backup`     | Datenbank-Migration — Backup empfohlen |
| breaking  | `breaking`   | Hinweise beachten, Backup zwingend     |

Die mittlere Spalte gibt es, weil die Prozess-Dateien deutsch sind und der
`CHANGELOG.md` englisch: „gefahrlos" und `safe` sind **dieselbe** Stufe, und
die Schwelle in `CLAUDE.md`, Abschnitt „Release", meint genau diese Zeile.
Ohne die Zuordnung wären es zwei Vokabulare für eine Entscheidung.

**Im Zweifel die vorsichtigere Stufe.** Eine Index-Migration verändert keine
Daten — trotzdem „backup", damit die Kennzeichnung verlässlich bleibt. Ein Flag,
das mal so und mal so gemeint ist, wird ignoriert.

**Der Tag ist eine Owner-Entscheidung.** Der Agent bereitet vor und meldet
„tag-fertig"; getaggt wird auf Ansage — sofern nicht ausdrücklich vorab
freigegeben.

**Modell-Stempel am Release-Commit.** Wie an jedem Bau-Commit (siehe
`docs/agents/bau-brief.md`) hängt auch der Release-Commit den mehrteiligen
Stempel an: `Built-With: bau=<modell>; nacharbeit=<modell>;
arbitriert=<modell> (<datum>)` — nicht besetzte Rollen weglassen. Ohne das ist
die Herkunfts-Regel nach vier Wochen nicht mehr durchsetzbar, und jede Aussage
über Modellverhalten bleibt Anekdote.

Seit Scheibe 1 lösen Tags in diesem Repo überhaupt CI aus (`tags: ["v*"]` im
Trigger von `ci.yml`) — vorher konnte „Tag erst nach grüner CI" gar nicht
geprüft werden, weil ein Tag-Ref nie einen Lauf erzeugte. Damit ist die
Bedingung jetzt tatsächlich überprüfbar. Welche Risikostufe eine stehende
Owner-Freigabe zum Taggen erlaubt, steht in `CLAUDE.md`, Abschnitt „Release"
(Schwelle „gefahrlos") — diese Datei wiederholt sie nicht.

## Ablauf

1. **Alles gelandet**, CI grün (jeden Lauf **run-id-gepinnt** beobachten, nie über
   eine Listenposition — sonst wartet man auf den falschen Lauf). **Falle:**
   `gh run list --limit 1` direkt nach dem Push liefert oft den Lauf des
   **Vorgänger-Commits**, weil der eigene noch nicht existiert — real wurde so
   ein Issue gegen fremdes Grün geschlossen. Über den eigenen `headSha` filtern,
   dann auf die gefundene Lauf-ID warten. Details in `docs/agents/lehren.md` §6.

   **„Kein Lauf zum `headSha` gefunden" ist ROT, nicht „noch nicht da".** Das
   ist keine Formulierungsfrage: Nur diese Lesart hat den Vorfall aus §24
   überhaupt sichtbar gemacht — ein Commit auf `main`, der **null** Läufe
   auslöste, weil seine eigene Nachricht die CI-Überspring-Kennung enthielt.
   Ein Lauf, den es nie gab, hinterlässt nichts; wer „null Läufe" als „warte
   noch" liest, wartet für immer und taggt irgendwann trotzdem. Der Beleg für
   „ein CI-Lauf je Slice" ist damit nicht die Absicht, sondern die Abfrage:

   ```bash
   gh run list --workflow ci.yml --limit 60 --json headSha,status,conclusion \
     --jq "[.[] | select(.headSha == \"$(git rev-parse HEAD)\")]"
   ```

   Eine leere Liste ist ein Befund, keine Wartemeldung.

   **`--workflow ci.yml` ist tragend, nicht Kosmetik** — und die naheliegende
   Kurzform ist gemessen falsch. Wer stattdessen alle Läufe zum `headSha`
   zählt (`actions/runs?head_sha=…` mit `.total_count`), bekommt an Commit
   `8e46bf1` die Antwort `2` und liest sie als „Läufe da, alles gut":

   ```
   Configured Graph Update: pip in /backend | success | dynamic/dependabot/update-graph
   CI                                       | cancelled | .github/workflows/ci.yml
   ```

   Der grüne Lauf ist ein **fremder** Workflow, der eigene war abgebrochen —
   und ein abgebrochener Lauf trägt kein Urteil. Genau dieses falsche Grün hat
   `scripts/release.sh` schon einmal produziert, bevor der Filter hinzukam
   (Begründung dort im Kopf von `pruefe_ci`). Die Frage lautet nie „gibt es
   einen Lauf", sondern **„gibt es einen grünen CI-Lauf, und steht nichts
   Schlechtes daneben"**.

   `scripts/release.sh pruefen` setzt das in Schritt 6 durch; diese Zeile
   steht hier, weil Schritt 1 die Stelle ist, an der man beim Landen hinsieht —
   und der Vorfall lag Wochen vor dem Release.

2. **Version bumpen** an allen Stellen, die sie führen.
3. **Notizen-Eintrag** ganz oben: Titel, Risiko, „Neu", „Bitte testen".
   In der Sprache des Nutzers, nicht in der des Codes: _was er merkt_, nicht
   welche Funktion umgebaut wurde.
4. **Frischer Build** — sonst prüft Schritt 5 einen veralteten Stand. (Die
   Vorlage begründet diesen Schritt mit dem Rauchtest-Set; solange es das
   hier nicht gibt, gilt er für die Handprobe genauso.)
5. **Rauchtest-Set** über die kritischen Abläufe, Desktop **und** mobil, hell und
   dunkel. **Dieses Set gibt es hier noch nicht** — der Schritt ist damit
   ehrlich gesagt ein Vorsatz, kein Gate. Was ihm fehlt und warum er einen
   Wegwerf-Stapel braucht statt der laufenden Instanz, steht in Issue #75;
   bis dahin bleibt es Handprobe. Ein Schritt, der so tut, als liefe er, ist
   schlimmer als einer, der zugibt, dass er es nicht tut.
6. **Trockenlauf** des Release-Skripts:

   ```
   sh scripts/release.sh pruefen <version>
   ```

   Schreibt nichts. Grün heißt: Versionsformat gültig, oberster
   CHANGELOG-Eintrag trägt genau diese Version mit ISO-Datum und
   Risiko-Kennzeichnung, alle drei Code-Stellen stehen darauf, der Tag ist
   frei, der Arbeitsbaum sauber, und für **HEAD** liegt ein grüner CI-Lauf
   vor. Fällt eine Prüfung aus — kein `gh`, kein Lauf gefunden —, ist das
   **rot**, nicht „übersprungen": Ein ausgefallener Test ist kein
   bestandener Test.

   Das Gate prüft sich selbst: `sh scripts/release-selbstprobe.sh` zeigt für
   jede einzelne Prüfung einen roten und einen grünen Lauf gegen
   Wegwerf-Repos. Sie läuft im `backend`-Job der CI mit, weil ein Wächter,
   dessen Lauf niemand erzwingt, nichts beweist (`lehren.md` §18).

   **Was die Selbstprobe NICHT zeigt: dass das Skript auf dem Rechner des
   Owners läuft.** `release.sh` ist ein Owner-Skript — der Tag ist eine
   Owner-Entscheidung, die Auslieferung geschieht auf dem TrueNAS-Host. Bisher
   lief es ausschließlich in der Agenten-Umgebung und in der CI, also zweimal
   an derselben Stelle vorbei. Ein Ritual-Skript gilt erst als Gate, wenn der
   Owner es **einmal selbst ausgeführt** und die Ausgabe zurückgemeldet hat
   (`lehren.md` §26). Bis dahin steht sein Zustand auf „ungeprüft auf dem
   Zielrechner", nicht auf „grün".

7. **Owner fragen.** Danach taggen, pushen, Release anlegen.
8. **Ausliefern** — als eigener Schritt, nicht als Fortsetzung von 7. **Der
   Tag geht der Auslieferung VORAUS.** Für uns auf dem TrueNAS-Host, durch
   den **Owner** — der Agent tut das nicht selbst (Produktivinstanz, siehe
   `CLAUDE.md`):

   ```
   git fetch --tags && git checkout v<version> && docker compose up -d --build
   ```

   Der Tag wird ausgecheckt, nicht der Zweigkopf: Mit einem Owner-Gate
   zwischen 7 und 8 ist „seit dem Tag ist auf dem Zweig etwas dazugekommen"
   der Normalfall, und ein `git pull` würde genau das mit ausliefern. Ein
   nachträglich gesetzter Tag ist eine Rekonstruktion, keine Tatsache:
   Wandert der Zweig dazwischen, benennt er einen Stand, der nie draußen
   war. Begründung und Fall: `lehren.md` §23.
   Danach von Hand die Auslieferungs-Selbstprüfung (bis Issue #54
   automatisiert ist, Nachfrage-Termin 31.10.2026) — **nicht** der
   Rückstands-Check aus `docs/betrieb/erreichbarkeit.md`, der eine andere
   Frage beantwortet: Sie beantwortet „habe ich ausgeliefert, was ich
   ausgecheckt habe?" — Version aus `/api/health` gegen den **gerade
   ausgecheckten Tag** vergleichen, nicht gegen den neuesten Tag im Repo.
   Was sie zeigt und was nicht — insbesondere, dass sie den Rückstand
   zwischen zwei Auslieferungen nicht fängt — steht in
   `docs/betrieb/erreichbarkeit.md`.

## Notizen schreiben

Was der Nutzer merkt, nicht was umgebaut wurde:

> ❌ „`loeschbar` ist jetzt ein `column_property` mit korrelierten EXISTS"
> ✅ „Die Kundenliste lädt deutlich schneller. Bisher fragte die App für jeden
> Kunden vier Mal nach, ob er noch Belege hat — nur um das Mülleimer-Symbol
> richtig anzuzeigen."

**Nach einem Folge-Slice gegenlesen.** Ein Eintrag kann durch den nächsten Slice
unwahr werden. Real passiert: Ein Punkt versprach „für die Cloud unlesbar",
während der Folge-Slice genau das aufgehoben hatte — im „Was ist neu" stand
damit eine falsche Datenschutz-Zusage.

## Nach dem Ausliefern

**Prüfen, ob es wirklich läuft** — die Antwort einer Schnittstelle sagt mehr als
eine Versionsanzeige. Und: Clients, die Werkzeug-Beschreibungen zwischenspeichern
(MCP), müssen nach Signatur-Änderungen neu verbinden; sonst senden sie neue
Parameter gar nicht erst mit und es sieht aus, als hätte das Release nicht
gewirkt.
