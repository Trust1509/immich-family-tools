# Lehren aus gebauten Slices

Fehlerklassen, die uns real getroffen haben — mit dem Nachweis, warum sie
durchrutschten. **Nicht chronologisch, sondern nach Klasse**: Die Frage beim
Lesen ist nicht „was ist damals passiert", sondern „welche dieser Fallen liegt
in meinem Slice".

Die Einzelfälle stehen in den GitHub-Issues (dort auch die Messwerte); dieses
Dokument hält fest, was übertragbar ist.

## Vor jedem Slice: fünf Fragen

Dreiundzwanzig Abschnitte liest man einmal. Ein Projekt hat 1233 Zeilen Prozess-Doku
geschrieben und im selben Zeitraum eine Klasse aus §1 wiederholt — **ein Dokument
zu haben ist nicht, es gelesen zu haben.** Deshalb die Kurzfassung, die tatsächlich
vor den Slice gehört:

1. **Womit beweist dieser Slice, dass er wirkt** — und war dieser Beweis je rot?
2. **Wer ruft den geänderten Code auf?** Jeden Aufrufer, nicht die naheliegenden.
3. **Welche Aussage im Repo wird durch diesen Diff falsch?** (Doku, Kommentare,
   Anweisungen für später — in einem Projekt lagen ALLE bestätigten Funde dort.)
4. **Beruht ein Schutz hier auf einer Angabe, die das Geprüfte über sich selbst
   macht?**
5. **Was kann ich nicht prüfen** — und wo steht das, damit es nicht still zur
   Schuldenliste wird?

Wer diese fünf beantwortet, hat die teuersten Klassen unten abgedeckt.
Prozessregeln stehen in `CLAUDE.md`, Mess-Zahlen zum Modell-Panel in
`model-panel/messungen.md`.

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
- **Die Datenerhalt-Stichprobe deckt die Tabellen, die die geprüfte Migration
  anfasst.** Eine Stichprobe in einer unbeteiligten Tabelle ist SCHLECHTER als
  keine, weil sie ein Urteil erzeugt (Vorlage: ein Roundtrip-Job schrieb seinen
  eigenen Datenverlust ins Log und lief trotzdem grün, weil seine Stichprobe in
  der falschen Tabelle säte). **Framework-frei auf uns übersetzt:** Bei einer
  Änderung an `_migrate()` in `backend/services/config_store.py` deckt die
  Datenerhalt-Probe die **von dieser Änderung angefassten Schlüssel** von
  `accounts.json` — nicht irgendwelche vorhandenen Felder, sondern genau die,
  die die Migration liest oder schreibt (vorhandenes Muster:
  `test_migrate_preserves_existing_data` in `backend/tests/test_config_store.py`).
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
  eine Listenposition — sonst wartet man auf den falschen Lauf. **Die Falle ist
  schärfer als sie klingt:** `gh run list --limit 1` unmittelbar nach dem Push
  liefert den Lauf des VORGÄNGER-Commits, weil der eigene noch nicht existiert.
  Real passiert: Ein Issue wurde gegen fremdes Grün geschlossen, der rote Lauf
  fiel erst im nächsten Slice auf. Richtig: über `headSha` des eigenen Commits
  filtern, dann auf die gefundene ID warten. **Und: die Zählung je SHA ist
  ZEITABHÄNGIG** (Vorlage v1.10.0) — Tage später liefert dieselbe Abfrage auch
  Zeitplan-Läufe, die zufällig auf demselben Stand liefen; ein korrekt
  gemeldetes „0 Läufe" wird so später zu „1 Lauf". Beweisführung braucht
  **Lauf-ID und Zeitpunkt**, nicht die spätere Neuabfrage der Zahl.
  **SHA-gebunden zu warten reicht außerdem nicht** (Vorlage v1.10.1) — zwei
  weitere Wege führen zu „grün gemeldet, rot gewesen": **Der Exit-Code stirbt
  in der Pipe** — `gh run watch <id> --exit-status | tail -3` liefert den
  Exit-Code von `tail`, nicht den des Laufs; das bleibt bei grünen Läufen
  unsichtbar und fällt erst beim ersten roten auf, also genau dann, wenn es
  zählt. **Und „nicht gestartet" ist auch ein Fehlschlag** — ein Lauf kann rot
  sein, weil die Jobs nie starteten (erschöpftes Laufzeit-Budget,
  Zahlungsproblem, fehlende Rechte — null Schritte, Annotation statt
  Testausgabe); wer nur auf grün/rot schaut, verwechselt „Code kaputt" mit
  „Infrastruktur weg", und die Reaktionen sind gegensätzlich. **Die
  vollständige Regel:** über den eigenen `headSha` filtern, das
  `conclusion`-Feld lesen (nie den Exit-Code einer Pipe), und bei `failure`
  zuerst prüfen, ob überhaupt Schritte gelaufen sind. **Strukturell dahinter,
  nicht nur für diesen Fall:** Eine Prüfung nie im selben verketteten Kommando
  wie die Entscheidung — dieselbe Regel wie beim Exit-Code in der Pipe, hier
  nur einmal ausgesprochen statt an das eine Werkzeug (`gh run watch`)
  gebunden zu bleiben (dieselbe Klasse wie §19 unten: eine als Spezialfall
  formulierte Regel wird beim strukturgleichen Fall nicht wiedererkannt).
- **Bei Aufrufen fremder Stimmen ist das Erfolgskriterium die SYNTHESE, nie
  der Exit-Code** (Vorlage, Fund eines anderen Projekts — nicht dieses Repos;
  eigene Funde stehen in §12). Ein Aufruf, der an einer Werkzeuggrenze
  scheitert (zu lange
  Argumentliste, abgeschnittene Eingabe), kann trotzdem Exit 0 melden; wer nur
  den Exit-Code liest, verbucht einen Ausfall als leeres Ergebnis — und ein
  leeres Ergebnis liest sich im Panel-Kommentar wie „keine Funde". Das ist
  dieselbe Struktur wie die Pipe-Lehre oben: Der Erfolgskanal und der
  Ergebniskanal sind zwei verschiedene Kanäle.
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

## 8. Wächter: was sie schützen, ist enger als ihr Name

Fünf Wächter aus drei Projekten waren **grün und schützten nicht**. Jedes Mal
schätzte der Wächter seine eigene Reichweite falsch ein. Die fünf Fragen, die
das aufdecken:

- **Prüft er dasselbe Prädikat wie der Mechanismus, den er absichert?** Einer
  suchte „schreibbar und nicht lesbar", der abgesicherte Filter maskierte auf
  „personenbezogen **oder** nicht lesbar" — die Lücke dazwischen war unsichtbar.
  Ein Wächter, der sich darauf verlässt, dass ein _anderer_ Test die Eigenschaft
  hält, ist keine Sicherung.
- **Zählt er die Ausnahme-Mechanik als Schutz?** Einer verlangte, dass jede
  Schreibfunktion die Sperre „erwähnt" — womit der Ausnahme-Guard selbst als
  geschützt galt und genau die Klasse verdeckte, die er finden soll.
- **Hängt er an einer Kennung, die der Client vergibt?** Bei Werkzeug-Namen kommt
  der Präfix aus der **Client**-Konfiguration und ist frei gewählt. Ein geratener
  Präfix passt auf nichts, und der Wächter lässt alles durch.
- **Schützt er einen AUFRUFER oder eine RESSOURCE?** Ein Hook im Agenten-Client
  schützt den Agenten. Andere Clients erreichen dieselbe Tür ungehindert.
  „Produktion ist schreibgeschützt" ist dann falsch, „dieser Agent kann nicht
  schreiben" richtig — und der Unterschied fällt in keinem Test auf.
- **Vererbt seine Wirkung nach unten auf das Schutzobjekt?** Eine Sperre auf dem
  Container legte den zu schützenden Dialog mit still. „Wirkt die Sperre?" war
  grün; „wirkt sie auch auf das, was sie schützen soll?" fehlte.

Dazu die Fehlerrichtung: **Ein manueller Auslöser, der immer die riskante Aktion
ausführt, macht die harmlose unmöglich.** Vergessen muss _nicht ausführen_
heißen.

**Der Nachweis ist immer eine Echtprobe:** einen echten Aufruf auslösen und
prüfen, dass der Wächter ihn überhaupt SIEHT. Konstruierte Testfälle bestätigen
die Annahme des Autors — sie erzeugen ihre eigenen Eingaben.

**Konsequenz für die Bauweise:** Nicht „alle Schreibzugriffe blocken", sondern
**die Schreibtüren aufzählen** und je Tür festhalten, ob sie gewollt ist und wer
sie bewacht. Derselbe technische Sachverhalt war in einem Projekt ein Loch und
im anderen ein gewolltes Feature; eine pauschale Regel tut immer einem von
beiden unrecht.

---

## 9. Belegen statt annehmen

Vier Fälle aus vier Projekten, eine Klasse: **Was nicht gemessen wurde, gilt als
in Ordnung.**

- **Das Vorhandensein einer Prüfung ist nicht ihr Bestehen.** Eine CI war seit
  ihrer Einrichtung nie grün; aufgefallen ist es erst, als jemand zum ersten Mal
  auf das _Ergebnis_ statt auf die Existenz des Workflows sah. Im selben Repo
  eine zweite, wöchentliche Prüfung: ebenfalls seit Tag eins rot, nach 77
  Sekunden abgebrochen — sie hat nie etwas geprüft.
- **Eine Suite, die nie rot war, ist unbewiesen** — und die Mutation, die
  **nicht** rot wird, ist die lehrreichere: Sie zeigt, was der Test _nicht_
  behauptet. Das gehört in den Test, nicht in die Erinnerung.
- **Erst messen, wo der Verbrauch entsteht.** Ein Optimierungsauftrag kam mit
  fertigen Maßnahmen für das Repo, in dem gerade gearbeitet wurde: Es
  verursachte 0,5 %, ein anderes 78 %. Die Maßnahmen waren richtig und
  wirkungslos.
- **Ein widerlegter Prüfer-Befund ist selbst ein Fund**, wenn er eine unbelegte
  Annahme trifft. Greifen zwei unabhängige Stimmen dieselbe Annahme an, gehört
  sie belegt — nicht verteidigt.

Dieser Punkt stammt aus Immich Family Tools (Vorlagen-Issue #3).

---

## 10. Zwei Umgebungen, eine geprüft

Wer lokal im Container prüft und in der CI ohne, hat **zwei** Umgebungen und
testet eine.

- **Konfigurations-Defaults, die auf Container-Pfade zeigen**, brechen auf dem
  nackten Runner — lokal unsichtbar, weil die Pfade dort existieren.
- **Pflicht-Umgebungsvariablen, die nur an einem Schritt hängen**, fehlen dem
  Migrationsschritt, sobald der die Anwendung importiert.
- **Prüf-Abhängigkeiten aus zwei Quellen driften still.** Ein lokales Gate
  installierte sein Test-Werkzeug hartkodiert, die CI las die
  Entwicklungs-Abhängigkeiten; sichtbar wurde es erst, als ein zweites
  Prüfwerkzeug dazukam und lokal nie lief. Gate und CI müssen **dieselbe Quelle**
  benutzen.

---

## 11. Notmaßnahmen ohne Rückdreh-Datum werden dauerhaft

Vier Repos bekamen gleichzeitig eine Laufzeit-Notbremse (Prüfungen reduziert,
Bot stillgelegt). Keines trug ein Datum für den Rückbau — und keines hat es
gemeldet, weil die Lücke erst in der Portfolio-Sicht sichtbar wird. **Jede
Notmaßnahme bekommt beim Einbau ein Issue mit konkretem Datum im Titel**, nicht
„nach dem Reset".

**Beim Rückbau gehört eine DRITTE Frage dazu, neben Datum und Bedingung: Hat
die Messung aus der Notzeit die Ausgangsannahme widerlegt?** Wenn ja, wird aus
der Notmaßnahme eine Regel mit NEUER Begründung — und die alte
Rückdreh-Anweisung wird gelöscht, nicht ausgeführt. Datum und Bedingung prüfen
nur, ob die Maßnahme noch NÖTIG ist; keine von beiden prüft, ob sie von Anfang
an RICHTIG war.

**Das ist unser eigener Fall:** Die Dependabot-Notiz „am 01.09. zurück auf
weekly und 2/2/1/1" (`.github/dependabot.yml`, eingebaut mit der
Actions-Minuten-Notbremse vom 14.08.2026) war sauber datiert und sauber
bedingt. Pflichtschuldig ausgeführt hätte sie am 01.09. eine der zwei
Ursachen des Quota-Zusammenbruchs wiederhergestellt — die Messung während der
Notzeit hatte gezeigt, dass die Version-PR-Frequenz selbst zum
Portfolio-Verbrauch beitrug, nicht nur ihre Reduktion auf Sicherheits-Updates.
Die Owner-Entscheidung vom 02.09.2026 (Issue #55) macht deshalb `monthly` +
`open-pull-requests-limit: 1` zur Dauerkonfiguration und streicht den
Rückdreh-Hinweis ersatzlos — dokumentiert im Kopfkommentar der Datei selbst.

---

## 12. Eigene Funde (Immich Family Tools)

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

## 13. Der Meldepfad hat dieselben Regeln wie der Prüfpfad

„Belegen statt annehmen" (§9) gilt nicht nur fürs Prüfen, auch fürs Berichten.
Ein Bericht ist eine Absichtserklärung, kein Nachweis.

**Geliehene Autorität tarnt einen ungeprüften Befund.** Ein Bau-Report meldete
drei rote Läufe als „vorbestehende, ordnungsabhängige Flakes" — mit Verweis auf
einen Abschnitt der Lehren-Datei, der etwas völlig anderes behandelt. Die
Quellenangabe war erfunden; die blinde Stimme fuhr drei volle Läufe, alle grün,
die Flakes reproduzierten nicht. Eine _erfundene_ Quelle ist gefährlicher als
gar keine — sie liest sich wie ein nachgeschlagener Fakt und wird leichter
durchgewunken.

**Regeln daraus:**

- **Jedes Zitat im Bericht nachschlagen.** Steht dort nicht, was behauptet
  wird, ist der ganze Befund unbelegt.
- **Behauptete Flakes reproduzieren** — mehrfach, mit und ohne Diff. Ein Flake,
  der sich nicht reproduzieren lässt, ist kein Flake, sondern ein Fund.
- Verwandt: ein als „verifiziert" gemeldeter Fix, bei dem nur der Nachbar-Zweig
  geprüft wurde. Die Frage lautet nicht „hast du geprüft", sondern **„was genau
  hast du ausgeführt, und was kam heraus"**.

## 14. Ein Widerspruch über zwei Dateien ist unsichtbarer als einer in derselben

In einem Dokument fällt er beim Lesen auf. Über zwei Dateien verteilt sieht ihn
kein Leser beisammen — **jeder befolgt die Fassung, die er zuerst findet**, und
der Ausführende ist meist ein Subagent, dem genau eine der beiden Dateien
zitiert wurde.

Real: Ein Projekt übernahm ein neues Kriterium in die eine Datei; die andere trug
weiter die alte Pauschalregel. Geändert wurde die Stelle, die im Auftrag benannt
war. Aufgefallen ist es nur, weil ausdrücklich nach Widersprüchen gefragt wurde.

**Regel:** Wer eine Regel ändert, sucht sie in **allen** Dateien
(`grep -rn` über das Repo), nicht nur an der genannten Stelle. Und: eine Regel
hat genau einen Eigentümer, alle anderen Stellen verweisen.

**Die Art der Datei bestimmt, WIE die Drift behoben wird** — nicht jede
veraltete Stelle wird korrigiert:

- **Anleitende Datei** (Skript, Anweisung, Checkliste) → **umschreiben.** Sie
  soll den Ausführenden lenken; eine veraltete Fassung lenkt falsch.
- **Dokumentierende Datei** (Architektur-Entscheidung, Protokoll, Release-Notiz)
  → **datierter Nachtrag statt Korrektur.** Sie hält fest, was _damals_
  entschieden wurde. Wer sie umschreibt, löscht die Historie und macht die
  Entscheidung unnachvollziehbar.

Gemessen an einem realen Fall: Zwei Stellen beschrieben ein Auslieferungs-Regime,
das drei Tage später gewechselt hatte. Beide entstanden am selben Tag wie die
Regel und blieben liegen. **Keine Prüfung hätte sie gefunden**, weil beide
Dateien nie ausgeführt werden — eine Entscheidungsakte und ein Skript, das seit
dem Umzug nicht mehr lief. Die Suche kostete zwei Minuten, die Korrektur zehn.

**Wie man sucht — vier Heuristiken (Vorlage v1.10.0):**

- **Nach dem GELTUNGSBEREICH fragen, nicht nach dem Regelnamen.** Zwei Stellen
  können dasselbe Wort benutzen und trotzdem Verschiedenes meinen, weil die
  eine für JEDEN Fall gilt und die andere nur für einen Sonderfall — die
  Dopplung findet `grep`, die Divergenz steckt im Nebensatz: **„Sagen beide
  Stellen dasselbe darüber, WANN und FÜR WEN die Regel gilt?"**
- **Wortgleiche Duplikate sind die gefährlicheren.** Divergente Fassungen
  fallen auf, sobald jemand beide nebeneinanderhält; wortgleiche sehen bei
  jeder Prüfung korrekt aus — bis eine geändert wird, ohne die andere
  mitzuführen. Sie sind kein Fehler, sondern ein **wartender**.
- **Die Handsuche findet, woran man sich erinnert.** Gezielt nach den Stellen
  zu suchen, die man selbst bewusst verschoben hat, übersieht die, die man im
  selben Arbeitsgang unbewusst *mit*verschoben hat. Ein zweiter Leser mit dem
  **Muster** statt der Liste („suche nach demselben Muster weiter") findet
  mehr als eine Checkliste.
- **Nicht jede doppelt genannte Formulierung ist ein Schwellen-Duplikat.** Eine
  Tatsachenaussage ohne Entscheidungscharakter darf mehrfach stehen — sie kann
  nicht divergent _entscheiden_.

**Die schärfste Form der Klasse ist Quelle vs. ausgeführte Kopie** — eine Regel,
die als Repo-Datei UND als installierte Kopie in einem Agenten- oder
Client-Verzeichnis existiert. Keine der beiden Dateien wird beim Lesen der
anderen je mit angesehen, und nur ein Mensch kann synchronisieren. Für dieses
Projekt hat das (noch) keinen konkreten Gegenstand — es gibt keine solche
doppelte Kopie —, aber es ist der Fall, an den bei jeder neuen Automatisierung
zu denken ist, die eine Repo-Regel irgendwo außerhalb des Repos nachbildet.

## 15. Die Vorlage als Autorität unterdrückt die Messung

Zwei Projekte machten dieselbe Messung an demselben Werkzeug. Eines schloss
daraus „das Werkzeug ist falsch" und löste eine Korrektur aus. Das andere schloss
„dann heißen meine Überschriften eben falsch" und plante, die eigenen Briefe
umzubenennen.

Die Selbstauskunft des zweiten trifft den Kern: _„Das Skript kam aus der Vorlage,
und ich habe die Vorlage als Autorität behandelt. Meine Messung widersprach ihr,
und ich habe die Messung umgedeutet statt das Werkzeug in Frage zu stellen."_

**Regel: Eine Messung, die der Vorlage widerspricht, ist zuerst ein Befund über
die Vorlage.** Sie umzudeuten ist erlaubt — aber erst, nachdem der umgekehrte
Schluss ausdrücklich geprüft und verworfen wurde. Wer eine Vorlage baut, muss
das ausdrücklich einladen; wer sie benutzt, darf es nicht abwarten.

## 16. Eine Prüfung rutscht zu dem, was leichter zu messen ist

Aus Vorlage v1.10.1 (§19 dort). Zwei Fälle aus einem Projekt, an einem Tag,
beide gegen den Prüfenden selbst:

- **Präsenz geprüft, Struktur nicht.** Nach einem abgebrochenen Bauer wurde per
  Textsuche kontrolliert, ob ein Schutz _existiert_ — er tat es. Was er
  **umschloss**, wurde nicht geprüft: Die Sabotage hatte die geschützte
  Zuweisung aus dem Schutz herausgeschoben. Gefunden hat es erst der Gate-Lauf
  (441 Tests, einer rot — genau der, den die Sabotage kippen sollte).
- **Aufruf geprüft, Wirkung nicht.** Ein selbst geschriebener Test blieb ohne
  den zugehörigen Fix grün, weil jede Hilfsfunktion ihren Namen **vor** der
  geprüften Anweisung protokollierte. Der Test belegte, dass etwas aufgerufen
  wurde — nicht, dass es wirkte.

**Die Diagnose ist beide Male dieselbe: Die Prüfung maß etwas, das leichter zu
messen war als das Gemeinte.** Das ist keine Nachlässigkeit im Einzelfall,
sondern die Richtung, in die eine Prüfung von selbst rutscht — von der Wirkung
zur Präsenz, von der Struktur zum Vorkommen, vom Ergebnis zum Aufruf.

Die Gegenfrage vor jeder eigenen Prüfung: **„Messe ich die Wirkung oder nur ihr
Anzeichen?"** Und wenn nur das Anzeichen: Was müsste kaputt sein, damit mein
Maß es NICHT bemerkt?

_(Verwandt mit §1 und §9, aber eigenständig: Dort geht es um Prüfungen, die
nichts beweisen. Hier beweisen sie etwas — nur nicht das Gesuchte.)_

## 17. Eine Fähigkeitsgrenze, die still verwirft, macht die Metadaten-Karte zur Lüge

Aus Vorlage v1.11.0 (§20 dort). Ein Feld war in der Metadaten-Schicht als
schreibbar deklariert — die ist ausdrücklich als **Karte für Modelle** gedacht.
An zwei von drei Türen verwarf der gemeinsame Eingabe-Mapper das Feld **still**:
Der Aufruf gelingt, der Datensatz ist falsch, niemand erfährt es. Zwei Fehler,
die einander verdecken: **die Karte lügt** (deklarierte ≠ tatsächliche
Fähigkeit der Tür) und **die Grenze schweigt** (verwerfen statt ablehnen).

Bei menschlichen Aufrufern ist das ärgerlich; bei Modell-Aufrufern ein
Datenintegritäts-Risiko — zwischen Aufruf und Ergebnis sieht niemand mehr hin,
und das Modell behandelt die Karte als verlässlich. Der bittere Teil: Der
richtige Mechanismus existierte (ein Gate, dokumentiert mit „das Gate hält, was
die Metadaten versprechen") — die echte Grenze war **an ihm vorbei** im Mapper
verdrahtet. Der Wächter war nicht blind, er war zuständig für etwas anderes.

**Regeln:** Eine Fähigkeitsgrenze wird DEKLARIERT und ABGELEHNT, nie still
verworfen. Prüfsatz: **„Wenn ein Aufrufer dieses Feld ausdrücklich mitschickt —
erfährt er, was damit passiert ist — auch wenn der Wert dabei seine BEDEUTUNG
wechselt?"** Nein = Fehler, egal wie gut die Grenze begründet ist.

**Verwerfen ist nur die eine Hälfte; die andere ist UMDEUTEN.** Belegt an der
Behebung dieses Falls selbst (im Vorlagen-Repo): Nach der Freischaltung drehte
eine Tür den String `"nein"` per `bool()` zu `True` — nichts wurde verworfen,
der Wert wurde still ins Gegenteil verkehrt, und ein Beleg wäre mit falschem
Betrag zum Kunden gegangen. Dieselbe Klasse in Gegenrichtung, gefunden von der
blinden Erststimme im selben Slice, in dem diese Lehre geschrieben wurde. Wer
eine Grenze begradigt, prüft beide Richtungen: **kommt der Wert an — und kommt
er als DASSELBE an?** Für dieses Projekt konkret: Der PUT-Endpunkt für Konten
und die JSON-Migration in `backend/services/config_store.py` sind die Stellen
mit genau diesem Muster — ein Feld, das den Client-Aufruf übersteht, aber die
Bedeutung wechselt (z. B. eine leere Zeichenkette, die still als „unverändert"
statt als „gelöscht" interpretiert wird), ist derselbe Fehler wie oben. Kein
Feld darf gleichzeitig als schreibbar deklariert und in einem Tür-Mapper
verworfen werden — belegt durch einen Test, der die Tür wirklich benutzt.

## 18. Ein Wächter, dessen Lauf niemand erzwingt, macht die Abdeckungszahl zur Beruhigung

Aus Vorlage v1.11.0 (§21 dort). Ein guter Layout-Wächter meldete einen echten
Fehler nicht — aus drei Gründen in aufsteigender Wichtigkeit: Er lief an 5 von
59 Fenstern (**Abdeckung**); der Auslöser war ein persistierter Bedien-Zustand,
den kein Testfall je einschaltet (**Zustand**); und seine Suite lief **gar
nicht in der Pipeline** — sie wurde von Hand gestartet (**Ausführung**). Punkt
drei entwertet die ersten beiden: _Ein Projekt kann über Monate seine Wächter
ausbauen und dabei stetig weniger geschützt sein, ohne dass es irgendwo rot
wird._ (§1 beschreibt eine Prüfung, die nie grün war — hier läuft sie schlicht
nicht.)

**Regeln:**

- **Zweite Pflichtfrage: „Wurde der Wächter einmal genau so ausgeführt, wie
  der Job ihn ausführt — gleiches Kommando, gleiches Arbeitsverzeichnis,
  gleiche Umgebung?"** Ein Test, der die Funktion IMPORTIERT, beweist nichts
  über das Kommando. Gemessen (Vorlage): Ein neues Prüfskript war im Import
  grün und scheiterte beim CI-Aufruf mit `ModuleNotFoundError` —
  `sys.path[0]` ist beim Skript-Aufruf das Skript-Verzeichnis, nicht das
  Projekt. Der Wächter wäre beim nächsten Push rot gewesen, ohne je richtig
  gelaufen zu sein. Die Inventur über unsere eigenen Prüf-Suiten mit dieser
  Frage steht noch aus (nicht Teil dieses Slices).
- **Pflichtfrage beim Anlegen jeder Prüfung: „Was macht sie rot, ohne dass
  jemand daran denkt?"** Ohne Antwort ist sie eine Notiz, kein Wächter.
- Geht der automatische Lauf (noch) nicht: ausdrücklich und **terminiert**
  ersetzen (Pflichtlauf im Release-Ritual, mit Datum und Rückdreh-Bedingung,
  Muster §11). Kein stiller Verzicht.
- **Abdeckung hat zwei Achsen:** welche Objekte UND in welchen Zuständen.
  Persistierte Bedien-Zustände sind eigene Fälle, keine Varianten.
- Ein **Sicherheitsnetz kann den Fehler unsichtbar machen** — wer eines
  einzieht, lässt den Wächter dahinter messen.

### Angewendet auf dieses Projekt: was macht welche Prüf-Suite rot, ohne dass jemand daran denkt?

Die Pflichtfrage oben, einmal durch alle Prüf-Suiten dieses Repos
durchgestellt — zwei Fälle sind bereits real eingetreten (a, b), die übrigen
sind konkrete, im Code belegte Kandidaten, keine Allgemeinplätze:

- **`pytest backend/tests`** — **(b), real eingetreten:** Auf diesem
  Windows-Rechner bricht der Lauf an einer kaputten ACL im `%TEMP%`-Verzeichnis
  ab, nicht am Code — `tmp_path` legt seine Verzeichnisse dort standardmäßig
  an. Deshalb `--basetemp=/tmp/pytest-immich` in `CLAUDE.md` und im
  Husky-Hook. Zweiter, unbelegter Kandidat: `test_config_store.py` überspringt
  die Prüfung des Datei-Modus `0o600` mit `if os.name != "nt"` — auf Windows
  läuft die Suite grün, ohne die Zugriffsrechte-Regel je zu prüfen; bricht sie
  auf Linux (der tatsächlichen CI-Plattform), sieht das kein lokaler Lauf.
- **`npm test` (Vitest)** — **war** die Antwort auf die Pflichtfrage oben, bis
  der Husky-Pre-Commit-Hook `npx lint-staged`, den Frontend-Typecheck und die
  Backend-Suite fuhr, aber nicht `npm test`: Die Vitest-Suite lief
  ausschließlich in der CI, ein Regressionsfund erreichte den Bauer also nie am
  Commit. Seit `ba41e1f` geschlossen — Ist-Zustand siehe §20.
- **`npx tsc --noEmit`** — Der lokale Husky-Lauf typprüft gegen das, was gerade
  in `frontend/node_modules` liegt. Führt jemand dort `npm install` statt
  `npm ci` aus (z. B. nach einem manuellen Paket-Test), driftet die lokal
  installierte TypeScript-Version von der durch `package-lock.json`
  gepinnten — der Hook meldet grün gegen einen Stand, den `npm ci` in der CI
  nie erzeugen würde.
- **`npm run build`** — Windows/NTFS ist standardmäßig case-insensitiv, der
  Ubuntu-CI-Runner nicht. Ein Import mit falscher Groß-/Kleinschreibung (z. B.
  `./Button` statt `./button`) baut auf diesem Windows-Rechner anstandslos und
  bricht ausschließlich in der CI — ohne dass sich am Quellcode zwischen den
  Läufen etwas geändert hat.
- **Husky-Pre-Commit-Hook** — er prüft **das ganze Repo, nicht den Diff**: Eine
  vorbestehende, unberührte Baustelle in `frontend/` blockiert einen
  reinen Backend-Commit, und umgekehrt. Das ist im Kern gewollt (dieselbe
  Klasse von „muss laufen, sonst meldet es sich zu spät"), aber es bedeutet:
  Wer den Hook wegen eines als „unrelated" empfundenen Rots einmal mit
  `--no-verify` umgeht, hat exakt den Zustand aus §21 hergestellt — einen
  Wächter, dessen Lauf niemand mehr erzwingt.
- **`gitleaks` (CI, Secrets-Job, Push-Pfad)** — Der Job checkt mit
  `fetch-depth: 0` aus; das liefert die volle Git-Historie, **scannt sie aber
  nicht**: gitleaks-action wertet bei `push`-Events nur die Commits des
  jeweiligen Pushes entlang der ersten Eltern-Linie aus (`--first-parent
--no-merges`: Merge-Commits und Commits eines eingemergten Zweigs werden
  nicht gescannt — relevant bei Dependabot-Merges; siehe Kommentar in
  `wochen-pruefung.yml`) — nötig bleibt es trotzdem: die Action löst
  `base^..head` auf, ein flacher Klon bricht das. Die Regel-Update-Rot-Quelle
  stand hier bis `d7a9ada` **falsch**; sie betrifft seit dem eigenen
  Vollscan-Lauf die Wochen-Prüfung (siehe dort) — der Push-Job selbst
  rescannt keine unveränderten, längst gelandeten Commits auf dem `push`-Pfad;
  bei manuellem `workflow_dispatch` scannt auch dieser Job den vollen Verlauf
  und ist derselben Regel-Update-Rot-Quelle ausgesetzt.
- **Container-Bau (CI, `docker build`)** — **(a)-verwandt, Owner-Hinweis
  „fremde Basis-Images":** `Dockerfile` zieht `node:22-alpine` und
  `python:3.12-slim` über **bewegliche Tags**, nicht über einen Digest, und die
  zweite Stufe fährt zusätzlich `apt-get update && apt-get install tzdata`
  gegen die live Debian-Paketquellen. Jede der drei Stellen kann bei
  unverändertem Repo-Stand rot werden: ein neu veröffentlichtes Basis-Image
  unter demselben Tag, ein kurzzeitig inkonsistenter Debian-Mirror, oder ein
  entferntes Paket. Der Bau-Test (`push: false`) prüft dann eine Umgebung, die
  es beim nächsten Lauf schon nicht mehr gibt.
- **Wochen-Prüfung (`pip-audit` / `npm audit` / `gitleaks`)** — **(a), real
  eingetreten:** Ein neu veröffentlichtes npm-Advisory (`nanoid`, Commit
  `096db40`) färbte die CI mitten in einem Release rot, ohne dass sich eine
  Zeile geändert hatte — siehe §12. Deshalb laufen die beiden Audits seit
  diesem Fund **nicht** mehr auf dem Push-Pfad, sondern wöchentlich in
  `wochen-pruefung.yml`. Zweite, hier bisher nicht geführte Rot-Quelle
  desselben Jobs: `gitleaks` checkt dort mit `fetch-depth: 0` die volle
  Git-Historie aus und scannt sie komplett bei jedem Lauf, anders als der
  Push-Scan in `ci.yml` (siehe oben) — ein Regel-Update im gitleaks-Projekt
  selbst kann damit einen längst gelandeten, unveränderten Commit neu als
  Fund markieren, CI wird rot, ohne dass in diesem Repo eine Zeile angefasst
  wurde. Konkret erhöht: Mehrere Testdateien (u. a. `test_auth_service.py`,
  `test_immich_client.py`, `test_config_store.py`) enthalten Literale wie
  `api_key`, `token`, `secret` für erfundene Konten — aktuell niedrige
  Entropie (`"secret"`, `"a-long-secret"`), aber ein künftiger Fixture-Wert,
  der wie ein echter Schlüssel _aussieht_ (lang, zufällig wirkend), würde bei
  einem schärferen Entropie-Ruleset genau hier zuschlagen, an einer Stelle,
  die niemand als Sicherheitsproblem gebaut hat. Der verbleibende Rest-Fall:
  Läuft der wöchentliche Job selbst nicht durch (Budget, Rechte,
  `workflow_dispatch` vergessen), meldet das niemand aktiv — die einzige
  Prüfung dafür ist ein Mensch, der das Grün des letzten Laufs von Hand
  nachsieht (vgl. §9, „das Vorhandensein einer Prüfung ist nicht ihr
  Bestehen").

## 19. Eine als Spezialfall formulierte Regel wird beim strukturgleichen Fall nicht wiedererkannt

**Vorlage §22.** Drei unabhängige Belege, einer vom Autor der Regel selbst:
Der Autor der Pipe-Exit-Code-Lehre (unser §6 oben, „Der Exit-Code stirbt in
der Pipe") verletzte sie selbst — im nächsten strukturgleichen Fall
(`tsc | tail; echo $?` statt `gh run watch | tail`). Wissen war nachweislich
nicht das Problem: **Die Formulierung band die Regel an EIN Werkzeug statt an
die Form** (Pipe frisst Exit-Code, egal was links steht). Zwei weitere
Projekte fanden dasselbe Muster unabhängig voneinander: „Datenmigration"
wurde von einem framework-losen Projekt als gegenstandslos gelesen, obwohl
seine JSON-Schema-Wanderung exakt der gemeinte Vorgang war.

**Regel: Jede neue Lehre wird beim Schreiben auf ihre Struktur abgeklopft —
„gilt das nur für dieses Werkzeug, oder für die Form?"** Wenn für die Form:
die Form benennen, das Werkzeug als Beispiel führen. Verwandt mit §16 (die
Prüfung rutscht zum leichter Messbaren), aber eigenständig: Hier rutscht die
REGEL zum konkreteren Fall.

**Bei uns bereits angewendet:** Die Pipe-Lehre in §6 trägt seit diesem
Abgleich den Zusatz „Eine Prüfung nie im selben verketteten Kommando wie die
Entscheidung" — wir kannten die Regel und befolgten sie (§17-Suche vor jedem
Commit läuft als eigenes Kommando, nie verkettet), aber sie stand bei uns
nirgends als Form, nur als Spezialfall (Exit-Code in der Pipe). Genau die
Klasse, die dieser Paragraph beschreibt.

## 20. Ein Hook deckt nur, was er nennt — und er nennt seine Auslassungen nicht

**Vorlage §23 — verallgemeinert aus einem eigenen Fund dieses Projekts.**
Herkunft: Bei der §21-Inventur im v1.11.3-Abgleich fiel auf, dass unser
Husky-Pre-Commit-Hook Lint, `tsc --noEmit` und die Backend-Tests fährt, aber
**nicht** die Frontend-Tests (Vitest, `npm test`) — die laufen ausschließlich
in der CI. Die Vorlage hat daraus die allgemeine Form gemacht: **Eine Suite,
die man für lokal gedeckt hält, weil ein Hook existiert, ist damit nicht
gedeckt** — ein Hook deckt nur, was er nennt, und nennt seine Auslassungen
nicht von selbst.

Unter der Dauerregel „ein CI-Lauf je Slice" (siehe `CLAUDE.md`, Abschnitt
„Prüfschritte" — die Regel steht dort, nicht hier) ist die Lücke dauerhaft
scharf, nicht nur befristet: Ein gebrochener Frontend-Test würde sonst erst
Tage später auffallen, einem anderen Bauer zugeordnet.

**Regel:** Wer sich auf „der Hook fängt das" beruft, hat die Hook-Definition
gelesen, nicht vermutet — und ein Wegfall der zweiten Verteidigungslinie
(CI-Pause!) ist der Moment, die Auslassungsliste des Hooks zu prüfen, nicht
der Moment, ihr zu vertrauen. (§18 fragt, was eine Prüfung rot macht; dieser
Paragraph fragt, wer überhaupt prüft.)

**Der konkrete Fall ist mit diesem Slice geschlossen.** Er lag als **Issue
#59** („Pre-Commit-Hook fährt die Frontend-Tests nicht (Vitest nur in der
CI)"); der Hook fährt jetzt `npm --prefix frontend run test`, siehe
`.husky/pre-commit`. Die Lehre selbst bleibt bestehen — ein Hook deckt nur,
was er nennt — nur der Stand dieses konkreten Falls ändert sich von „offen"
auf „geschlossen".

## 21. Wächter-Code ist die defektdichteste Stelle eines Slices

Aus Vorlage §24. Ein Projekt baute an einem Tag vier neue Wächter. Über fünf
Panel-Runden verteilten sich die bestätigten Funde **nicht gleichmäßig**:
Wenige lagen im Produkt-Inhalt, die große Mehrheit im Wächter- und Prüfcode —
**darunter beide blockierenden Funde.**

**Warum das strukturell ist und nicht Schlamperei:** Produkt-Code hat Nutzer,
die ihn benutzen; ein Fehler fällt auf. **Wächter-Code hat als einzigen
Nutzer den Fehlerfall — und der tritt selten ein.** Ein Gate, das nie rot
war, ist ununterscheidbar von einem Gate, das nicht funktioniert; die übliche
Rückmeldeschleife fehlt. Verschärfend: Man baut Wächter, wenn der eigentliche
Slice fertig ist — mit weniger Aufmerksamkeit und dem Gefühl, „nur noch
abzusichern".

**Für uns direkt belegt:** Im 01.09.-Slice lagen beide schwersten Funde im
Wächter-Code (Job-Kopplung im Wochenlauf; Push-Scan-Reichweite), nicht im
Produktcode.

**Regeln:**

- **Ein Gate bekommt eine Selbstprobe:** ein eingechecktes Skript, das ein
  Dutzend Mutationen gegen das Gate fährt und erwartet, welche rot werden
  müssen.
- **Der Wächter-Teil eines Slices wird wie Produktcode geprüft**, nicht als
  Anhang: eigener Blick im Panel, eigene Rot-Beweise.
- **Jeder Job bekommt eine Laufzeitgrenze** (`timeout-minutes`), jeder
  Netzaufruf eine eigene Frist. Ohne sie läuft ein hängender Lauf bis zum
  Plattform-Standard von 360 Minuten — bei einem Tagesbudget von 100 Minuten
  ist das nicht ein Aufschlag, sondern der ganze Tag plus Überziehung.

## 22. Freitext in einem `run:`-Block ist Code

Aus Vorlage §25. Ein Monitoring-Workflow legte bei Befund ein Issue an. Im
Issue-Text stand, als Hilfestellung für den Leser, der Auslieferungsbefehl in
Markdown-Backticks — übergeben als doppelt gequoteter String an
`gh issue create --body "…"`. **Die Shell führt Backticks in doppelten
Anführungszeichen aus.** Der Wächter enthielt damit einen vollständigen,
syntaktisch korrekten Deploy-Befehl, der bei jedem roten Lauf abgesetzt
worden wäre. Dass nichts passierte, lag an zwei Zufällen (fehlendes
`actions: write`, kein Repo-Kontext) — wer eines davon ergänzt hätte, hätte
ab dann bei jedem Befund ungefragt nach Produktion ausgeliefert.

**Ergebnis unserer Prüfung:** In unseren Workflows (`ci.yml`,
`wochen-pruefung.yml`) steht in keinem `run:`-Block Freitext, keine
Backticks, keine Kommandosubstitution — geprüft, alle zehn `run:`-Blöcke
sind einfache Kommandos (`pip install`, `pytest`, `python -m compileall`,
`npm ci`, `npm test`, `npm run build`, `pip-audit`, `npm audit`); Backticks
kommen nur in YAML-**Kommentaren** vor. Die Regel ist hier **präventiv**, nicht
korrigierend — es gab keinen Vorfall dieser Art in diesem Repo.

**Regeln:**

- **Freitext nie in doppelt gequoteten Strings an ein Kommando geben.** Immer
  Heredoc mit gequotetem Begrenzer in eine Datei, dann `--body-file`. Die
  `${{ }}`-Ausdrücke setzt die Plattform vorher ein, das funktioniert weiter;
  Backticks und `$` bleiben Text.
- **Wer „dieser Workflow kann nicht ausliefern" behauptet, prüft DREI Dinge:**
  Rechte, Secrets — **und den Text aller `run:`-Blöcke auf den
  Auslieferungsbefehl selbst**, Kommentare und Zitate eingeschlossen. Ein
  Treffer ist ein Befund, auch wenn er „nur ein Zitat" ist.
- Verwandt mit §16, aber eigenständig: Dort misst die Prüfung das Leichtere;
  hier prüft sie die richtige Sache an der falschen Repräsentation.

## 23. Was einmal richtig gemacht und nicht aufgeschrieben wurde, ist keine Regel, sondern eine Anekdote

Aus Vorlage §26. Ein Release-Ritual endete mit „Owner fragen, danach taggen"
und dem nächsten Abschnitt „Nach dem Ausliefern" — dazwischen kein Schritt.
Das Dokument setzte stillschweigend voraus, dass Tag und Auslieferung
aufeinanderfolgen. Mit einem Owner-Gate dazwischen hat die Reihenfolge zwei
Möglichkeiten, und beide sind eingetreten: einmal Tag Sekunden vor der
Auslieferung (richtig, niemand dachte darüber nach), Wochen später
Auslieferung zuerst und der Tag danach auf Nachfrage. Zwischen beiden
Terminen hatte sich nichts geändert außer dem Abstand.

**Die richtige Reihenfolge EXISTIERTE** — als Praxis, einmal korrekt
ausgeführt. Sie stand nur in keinem Dokument. Ein Schritt, der bloß in der
Ausführung lebt, überlebt die nächste Ausführung nicht; Wochen genügen, bei
wechselndem Agenten-Kontext erst recht.

Warum es zählt: Ausgeliefert wird der Kopf des Hauptzweigs, nicht ein Tag. Es
gibt also nichts, was den ausgelieferten Stand an einen Namen bindet. Wandert
der Zweig zwischen Auslieferung und nachträglichem Tag, zeigt der Tag auf
einen Stand, der nie draußen war — und es fällt nicht auf, weil er ja
ordentlich „nach dem grünen Lauf" gesetzt wurde.

**Für uns der Anlass:** Genau diese Lücke stand in unserem eigenen
`release-ritual.md` — Schritt 7 endete mit Taggen/Pushen/Release, das
Ausrollen auf TrueNAS tauchte gar nicht auf (siehe `release-ritual.md`,
Schritt 8, in diesem Abgleich ergänzt).
