# Release-Ritual

## Grundsätze

**Version und Notizen im selben Commit.** Ein Tag ohne gepflegte Notizen zeigt
dem Nutzer die Angaben der Vorversion — inklusive falscher Risiko-Kennzeichnung.
Ein Skript-Gate, das genau das abfängt, hat sich bewährt: Es bricht ab, wenn die
Versionsnummer nicht zum obersten Notizen-Eintrag passt.

In diesem Projekt führen **vier** Dateien die Version, alle im selben Commit:
`backend/version.py`, `frontend/src/version.ts`, `frontend/package.json` und
`CHANGELOG.md`.

**Risiko ehrlich kennzeichnen.** Bewährte Stufen:

| Stufe     | Bedeutung                              |
| --------- | -------------------------------------- |
| gefahrlos | nur Code, keine Migration              |
| backup    | Datenbank-Migration — Backup empfohlen |
| breaking  | Hinweise beachten, Backup zwingend     |

**Im Zweifel die vorsichtigere Stufe.** Eine Index-Migration verändert keine
Daten — trotzdem „backup", damit die Kennzeichnung verlässlich bleibt. Ein Flag,
das mal so und mal so gemeint ist, wird ignoriert.

**Der Tag ist eine Owner-Entscheidung.** Der Agent bereitet vor und meldet
„tag-fertig"; getaggt wird auf Ansage — sofern nicht ausdrücklich vorab
freigegeben.

Seit Scheibe 1 lösen Tags in diesem Repo überhaupt CI aus (`tags: ["v*"]` im
Trigger von `ci.yml`) — vorher konnte „Tag erst nach grüner CI" gar nicht
geprüft werden, weil ein Tag-Ref nie einen Lauf erzeugte. Damit ist die
Bedingung jetzt tatsächlich überprüfbar. Für **gefahrlose Patch-Releases mit
grüner CI** gilt eine stehende Owner-Freigabe; **Riskantes** (Stufe backup oder
breaking) bleibt Owner-Sache und wird vor dem Tag gefragt.

## Ablauf

1. **Alles gelandet**, CI grün (jeden Lauf **run-id-gepinnt** beobachten, nie über
   eine Listenposition — sonst wartet man auf den falschen Lauf).
2. **Version bumpen** an allen Stellen, die sie führen.
3. **Notizen-Eintrag** ganz oben: Titel, Risiko, „Neu", „Bitte testen".
   In der Sprache des Nutzers, nicht in der des Codes: _was er merkt_, nicht
   welche Funktion umgebaut wurde.
4. **Frischer Build** — sonst prüft das Rauchtest-Set einen veralteten Stand.
5. **Rauchtest-Set** über die kritischen Abläufe, Desktop **und** mobil, hell und
   dunkel.
6. **Trockenlauf** des Release-Skripts.
7. **Owner fragen.** Danach taggen, pushen, Release anlegen.

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
