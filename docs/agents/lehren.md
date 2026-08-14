# Lehren aus gebauten Slices

Fehlerklassen, die uns real getroffen haben — mit dem Nachweis, warum sie
durchrutschten. **Nicht chronologisch, sondern nach Klasse**: Die Frage beim
Lesen ist nicht „was ist damals passiert", sondern „welche dieser Fallen liegt
in meinem Slice".

Die Einzelfälle stehen in den GitHub-Issues (dort auch die Messwerte); dieses
Dokument hält fest, was übertragbar ist. Prozessregeln stehen in `CLAUDE.md`,
Mess-Zahlen zum Modell-Panel in `model-panel/messungen.md`.

---

## 1. Wächter und Tests: grün heißt nicht bewiesen

Die teuerste Klasse. Sie ist uns an einem einzigen Tag **dreimal unabhängig**
begegnet, jedes Mal mit identisch grüner Suite.

**Ein grüner Wächter beweist nur so viel, wie seine Testdaten hergeben.**
Der Wertfluss-Wächter prüfte die PII-Klasse über alle Lese-Werkzeuge — sein
Marker landete aber nie im Namen eines _Privat_-Lieferanten, weil der Demo-Seed
nur Firmen anlegt. Der Wächter lief jahrelang brav über einen Fall, den es in
seinen Daten nicht gab (#348).

**Testdaten können die Wirkung vortäuschen.** Eine Fixture war so angelegt, dass
die id-Reihenfolge zufällig mit der neuen fachlichen Sortierung übereinstimmte.
Streicht man den Sortierblock ersatzlos, bleiben alle Tests grün (#349).

**Mocks können genau den Kernfix verdecken.** Der Mock lieferte einen Lieferanten
ohne UID — dadurch rendert der Reverse-Charge-Hinweis in _keinem_ Test, also
gerade die Funktion nicht, für die der Slice gebaut wurde (#340).

**Und die Verdrahtung selbst war entfernbar.** Verschluckt man das
`maskiert=`-Kwarg an beiden MCP-Aufrufstellen — die einzigen zwei Zeilen, die
den Schutz an die Cloud-Tür bringen — läuft die komplette Suite grün (#349).

### Regeln daraus

- **Rot-Beweis für jeden neuen Test.** Den Fix sabotieren und zeigen, dass der
  Test fällt. Ein Test ohne Rot-Beweis ist eine Behauptung.
- **Auch die Verdrahtung sabotieren**, nicht nur die Logik. Die Frage lautet:
  „Welche einzelne Zeile könnte ich löschen, ohne dass etwas rot wird?"
- **Testdaten müssen den Unterschied erzwingen.** Wenn zwei Ordnungen/Zustände
  zufällig zusammenfallen, beweist der Test nichts — Anlagereihenfolge drehen.
- **Prosa-Listen driften.** Wo Doku eine Menge aufzählt (Konsumenten, Türen,
  Felder), soll ein Test Doku und Code _maschinell_ abgleichen. Beispiel:
  `frontend/src/lieferantenKonsumenten.waechter.test.ts` liest den Docstring der
  REST-Tür und alle Frontend-Quellen und erzwingt Deckungsgleichheit.
- **Zähl-Wächter sehen keine Kosten.** Ein SELECT-Zähler bleibt bei 2 Abfragen
  grün, während die Tür 6,6 s braucht. Wer ein Aggregat baut, muss das tragende
  Teil separat festnageln — z.B. per `EXPLAIN`, dass der Planer den Index
  wirklich _nimmt_ (#341).
- **AST-Wächter müssen das Hausmuster kennen.** Ein Wächter, der nur literale
  Attributzuweisungen (`x.feld = …`) sieht, verfehlt das hier übliche
  `aktualisiere() → _setze()` mit `setattr`-Schleife. Immer mit der
  _hausüblichen_ Schreibweise gegenproben, nicht nur mit der naiven (#344).

---

## 2. Cloud-Tür und PII: die Ausgabe darf keine Funktion des Geheimnisses sein

**Die Sortierreihenfolge ist ein Kanal.** Listen lieferten Pseudonyme, sortierten
aber nach dem Klartext-Namen. Gemessen: Ein geschützter Vorname war über die
Reihenfolge in 46 Cloud-Aufrufen rekonstruierbar — die Cloud darf Firmen mit
frei gewähltem Namen anlegen, das ergibt eine adaptive binäre Suche. Die
Kappungsgrenze liefert dasselbe Bit sogar ohne Probe-Datensatz (#348).

**Übertragbare Wächter-Form:** Mehrere geschützte Datensätze anlegen, ihre
Klartexte **untereinander vertauschen**, und verlangen, dass Reihenfolge und
Trefferposition unverändert bleiben. Das lockt die Klasse, nicht den Fundort.

**Weitere Kanäle derselben Art:**

- Suche, die über maskierte Spalten matcht → Treffer/kein-Treffer verrät den Wert.
  Auch der **Zähler** muss mitgefiltert werden, sonst sagt „0 Treffer, gesamt: 3".
- **Sekundengenau sortieren, minutengenau ausgeben** — die Reihenfolge verrät,
  was die Ausgabe abschneidet (#349).
- **Labels sind Freitext** und werden vom feldbasierten Filter _nicht_ gefangen.
  Wer einen Namen in ein Trefferlabel schreibt, umgeht die Maskierung (#348).
- **Abgeleitete Felder ohne Modell-Attribut** rutschen leicht durch einen
  fail-closed-Filter, weil sie in keiner Spaltenliste stehen (#346).

**Lese- und Schreibrichtung sind verschieden.** Ein Feld kann auswärts sensibel
und einwärts harmlos sein: Lesen lässt gespeicherte PII hinaus, Schreiben bringt
Text herein. Die alte Fabrik koppelte beides hart und sperrte deshalb einen
harmlosen Schreibweg mit (#344). **Aber:** Ein Feld, das schreibbar und zugleich
unlesbar ist, erzeugt die Gefahr des _blinden Überschreibens_ — dann braucht es
eine bewusste Entscheidung Anlegen / Ergänzen / Ersetzen-mit-Modus.

---

## 3. Datenmigrationen: hier ist das Panel am meisten wert

Fehler in einer Migration sind **nicht per Update heilbar**. Eine einzige
Migration (#346) brauchte drei Anläufe, jeder mit echtem Fund:

1. **Zu breit** — globales Suchen-und-Ersetzen über alle Vorlagen; fremde
   Vorlagen hätten ihren Platzhalter ersatzlos verloren.
2. **Nicht umkehrbar** — der Downgrade war ein Leerlauf. Unser Deploy rollt bei
   Bau-Fehlschlag **automatisch** zurück; die alte Programmfassung brauchte den
   entfernten Marker aber, um zu funktionieren. Ein Rollback hätte still
   verschlechtert.
3. **Zu gierig** — gemessener Datenverlust: eine Schwester-Position mit gleichem
   Präfix verlor ihren echten Klammertext, unwiederbringlich.

### Regeln daraus

- Treffermenge **kumulativ** eng fassen (nur diese Entität, nur diese Form, und
  alles überspringen, was zeichengenau einem legitimen Nachbarn entspricht).
- **Downgrade muss den Rollback-Pfad heil lassen** — nicht nur „das Schema
  zurück", sondern „die alte Programmfassung funktioniert wieder".
- Bei **Umklassifizierung eines Feldes**: prüfen, ob der Altbestand danach den
  alten _und_ den neuen Wert gleichzeitig zeigt. Zwei widersprüchliche Angaben
  untereinander sind schlimmer als der Ausgangszustand.
- Migrationstest **gegen eine `alembic upgrade head`-DB**, nicht gegen
  `create_all` — und die Engine im `tearDown` entsorgen (sonst PG-Zeilenlock).
- `CREATE INDEX` sperrt auf PG die Tabelle. Prüfen, wer währenddessen schreiben
  darf (der MCP-Container hing an `service_started`, nicht `service_healthy`).
- **Erweitern und Verengen nie im selben Release** (Expand–Contract): erst
  additiv das Neue anlegen, dann den Code umstellen, das Alte **später**
  entfernen. Eine Feld-Umwidmung, die beides auf einmal tat, hat in Produktion
  gekracht, weil ein Konsument noch die alte Bedeutung las.
- **Ein sauber durchlaufender Downgrade beweist keinen Datenerhalt.** Das
  Rückwärts-Skript kann fehlerfrei sein und trotzdem Zeilen verlieren — deshalb
  im Roundtrip-Test einen bekannten Datensatz schreiben und danach wieder
  auslesen.
- Roundtrip **kurz** halten (vorwärts → einen Schritt zurück → vorwärts). Der
  Voll-Roundtrip bis zum Anfang prüft Rückwärts-Skripte, die nie jemand
  ausführt, wenn der Rückweg im Ernstfall „Sicherung + altes Abbild" ist.

---

## 4. Performance: weniger Abfragen heißt nicht schneller

Die Schlagzeile „1352 → 3 SELECTs" misst **Round-Trips, nicht Kosten**. Ohne
Index skalierte das neue Aggregat quadratisch: 1 000 Kunden 2 229 ms, 2 000
Kunden 9 110 ms — der Vorzustand lag bei 3 165 bzw. 11 237 ms. Das Aggregat
holte rund ein Fünftel, **der Index die restlichen zwei Größenordnungen**
(19 bzw. 39 ms). Nebenbei verteuerte es unbeteiligte Pfade um Faktor 3, obwohl
MCP und Chat das Feld gar nicht lesen (#341).

### Regeln daraus

- **Index-Deckung der korrelierten Spalten prüfen**, bevor ein Aggregat gebaut
  wird. (Alle vier Beleg-Fremdschlüssel auf `kunde_id` waren jahrelang ohne.)
- **Konzentrierte UND gestreute Verteilung messen.** Die eigentliche Achse war
  die Zahl der _belegfreien_ Kunden — nur die können im `OR` nicht früh
  abbrechen. Bei breit gestreuten Daten ist die Klasse in der Messung unsichtbar.
- **Pfade prüfen, die das Feld gar nicht lesen** — ein `column_property` wird bei
  jedem SELECT der Entität mitgerechnet.
- Vor dem Umbau messen, nach dem Umbau messen, **und die Zahl in den Report**.

---

## 5. Stille Ausfälle: die Klasse, die niemand meldet

Eine gekappte Liste ist kein Fehler, den man sieht — sie ist eine, die _fehlt_.
Real getroffen hat es uns dreimal:

- 607 importierte Artikel waren an der KI-Tür unauffindbar, weil die Liste
  alphabetisch bei den ersten 100 endete (#345).
- Der **Reverse-Charge-Vorschlag** verschwand, sobald der Lieferant hinter der
  200er-Kappe lag — er braucht Land und UID. Kein Fehler, keine Meldung, nur
  eine fehlende Hilfe bei einer steuerlich heiklen Entscheidung (#340).
- Das **Ur-Beleg-Auswahlfeld einer Gutschrift** ist ab 200 Eingangsrechnungen
  unbrauchbar; damit greift die steuerliche Attribut-Übernahme nie (#351).

### Regeln daraus

- Eine Liste, die kappt, **muss es sagen** (Gesamtzahl + Kappungs-Flag). Ein
  Sprachmodell kann sonst „das sind alle" nicht von „das ist der Anfang"
  unterscheiden und behauptet Falsches über den Bestand.
- **Unterscheiden, wozu die Liste dient:** In einem Auswahlfeld muss jeder
  Eintrag auffindbar sein (vollständig laden oder serverseitig suchen); eine
  Tabelle zum Durchblättern braucht nur den Hinweis.
- **Prüfen, ob aus der Liste etwas _abgeleitet_ wird.** Ein Label degradiert
  sichtbar zu `#12` — eine Ableitung verschwindet spurlos. Genau dort gehört
  der sichtbare Hinweis hin, nicht die Konsolenwarnung.
- Voll-Load hat einen Preis: Auswahlfelder rendern ohne Virtualisierung _alle_
  Optionen (#352).

---

## 6. Betrieb und Werkzeuge

- **MCP-Clients holen die Werkzeugliste einmal beim Verbinden** und lesen sie nie
  neu. Nach einem Release mit geänderter Werkzeug-Signatur sendet ein alter
  Client neue Parameter gar nicht mit — er verwirft sie still gegen sein
  zwischengespeichertes Schema. Abhilfe: Client komplett neu starten (ein neues
  Gespräch reicht nicht). **Diagnose-Kniff:** die _Antwortform_ prüfen, nicht den
  Werkzeug-Katalog — die Form kommt vom Server, der Katalog vom Client.
- **Die Frontend-CI fährt ZWEI Typprüfungen:** `npx tsc --noEmit` über ganz `src`
  und zusätzlich `tsc -p tsconfig.strict.json` über eine Datei-Auswahl. Wer nur
  die strikte laufen lässt, sieht Fehler in Dateien nicht, die dort nicht
  gelistet sind.
- **CI-Wachen nur run-id-gepinnt** (`gh run watch <id> --exit-status`), nie über
  eine Listenposition — sonst wartet man auf den falschen Lauf.
- **SQLite ≠ PostgreSQL.** Negative `LIMIT`/`OFFSET` sind auf SQLite folgenlos
  und auf PG ein Fehler; `ILIKE` ist auf SQLite ASCII-only. Ein Test, der die DB
  durch SQLite ersetzt, prüft im PG-Job **nicht** PostgreSQL.
- **Sperrdateien gehören derselben Paketmanager-Hauptversion wie das Abbild.**
  Wird eine Sperrdatei von einer anderen Hauptversion erzeugt (lokaler Wrapper,
  Abhängigkeits-Bot), ist sie lokal und in der CI grün und bricht im Abbild.
  Deshalb: Sperrdateien im Container der Zielversion erzeugen, und die
  **installierte Menge** gegen die Sperrdatei prüfen — ein Wächter, der nur die
  _Anforderung_ prüft, ist grün und beweist nichts (Randbedingungen pinnen nur,
  was angefordert wurde).
- **Bewegliche Tags bei fremden CI-Bausteinen** (`@v4`) sind eine offene Tür:
  wer den Tag umhängt, läuft beim nächsten Push mit. Auf Commit-SHA pinnen —
  der garantiert Unveränderlichkeit, aber **nicht Herkunft**: beim Setzen
  prüfen, dass der SHA aus dem erwarteten Repo stammt.
- **Prüfungen, die von fremden Ereignissen rot werden** (Abhängigkeits-Scans),
  gehören nicht auf den Push-Pfad. Ein neu veröffentlichtes CVE blockiert sonst
  eine Auslieferung, an der sich nichts geändert hat — und erzieht dazu, rote
  Läufe wegzuklicken.
- **Sicherungen fallen still aus.** Der Auszug lief, die Datei war da, täglich
  neu — und im Ernstfall unbrauchbar. Zwei Konsequenzen: regelmäßig ein
  **Probe-Rückspiel** in eine Wegwerf-Datenbank mit fachlicher Stichprobe, und
  ein **Totmann-Schalter** von außen (das Ausbleiben des Erfolgs meldet, nicht
  der Fehler). Siehe `betrieb.md`.

---

## 7. Was das Panel wert war

Von den Slices dieser Serie hat das Review-Panel **jeden zweiten Erstbau
gestoppt** — nicht wegen Kleinigkeiten, sondern wegen Funden, die in Produktion
wehgetan hätten: ein Workflow-Bruch im Auftrags-Cockpit, ein rekonstruierbarer
Kundenname, ein unwiederbringlicher Datenverlust in einer Migration.

Die **blinde Erststimme** (frischer Prüfer, nur Diff und Repo, kein Bau-Kontext)
lieferte dabei überproportional die schwersten Funde. Der Grund ist strukturell:
Wer den Bau begleitet hat, liest die Absicht statt des Codes.

Nicht jede Stimme trifft. Die Diff-only-Stimme irrt regelmäßig Richtung
zu-streng und liest gelegentlich die Vorher-Seite eines Diffs. **Jeden Blocker
am Code reproduzieren** — Prüfer-Konvergenz ersetzt keine Reproduktion.

---

## 8. Eigene Funde (Immich Family Tools)

**Fremd-API-Annahmen gehören belegt, nicht geglaubt.** Ein zugelieferter Zweig
tauschte einen dokumentierten Endpunkt gegen einen undokumentierten (in der
API-Beschreibung als ausgeschlossen markiert). Alle Tests grün — sie stammten
vom selben Autor wie die Annahme. Regel: Bei Fremd-Code die API-Annahme gegen
die Quelle der Fremd-Software prüfen, nicht gegen die mitgelieferten Tests.

**Ein widerlegter Prüfer-Befund ist selbst ein Fund.** Zwei Stimmen griffen
dieselbe Annahme an, beide irrten — die Annahme war trotzdem nirgends belegt
und stimmte nur zufällig für die eingesetzte Version. Regel: Was mehrere
Stimmen für falsch halten, gehört belegt, nicht nur verteidigt.

**Scans auf dem Push-Pfad blockieren fremde Ereignisse.** Ein neu
veröffentlichtes npm-Advisory färbte die CI mitten in einem Release rot, ohne
dass sich eine Zeile geändert hatte (Commit `096db40`). Seitdem laufen sie in
`wochen-pruefung.yml`.
