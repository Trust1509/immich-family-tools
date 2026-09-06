# Bau-Brief: Vorlage für Aufträge an Bau-Subagenten

> **Der Bau-Brief ist die einzige Leitplanke, die den Bauer erreicht.**
> Regeln im Repo erreichen ihn nicht: Ein Bau-Subagent arbeitet den Brief ab,
> nicht `docs/agents/`. In fünf Projekten gemeldet, zweimal ist genau daran
> eine Pflichtregel gescheitert — sie stand im Repo und fehlte im Brief.
>
> Deshalb hat der Brief ein **Pflicht-Gerüst**. Fehlt ein Block, ist der Brief
> nicht fertig; vor jedem Absenden verbindlich:
> `LC_ALL=C.UTF-8 sh scripts/bau-brief-pruefen.sh <brief.md>`. Das Skript fängt den
> **vergessenen** Block — eine Floskel („Prüffragen wurden berücksichtigt")
> kann es davon nicht unterscheiden. Es ersetzt das Lesen nicht.

## Pflicht-Gerüst (Block 0 plus neun Blöcke, keiner leer)

```markdown
## 0 Risiko Risiko: R<n> — Auslöser: ⟨bei R3/R4 der Auslöser aus

                        der Tabelle in CLAUDE.md; bei R0 der R0-Auslöser; bei
                        R2 „Normalfall, gegen die Auslöser-Tabelle geprüft"⟩
```

## Pflicht-Gerüst (Fortsetzung: die neun Themen-Blöcke)

```markdown
## 1 Auftrag ⟨was gebaut wird, in zwei Sätzen⟩

## 2 Befund ⟨bereits verifiziert — NICHT neu recherchieren⟩

## 3 Konsumenten ⟨WER RUFT DEN GEÄNDERTEN CODE AUF? Jeden nennen.⟩

## 4 Sichtbares ⟨ändert der Slice sichtbares Verhalten? Doku-Folge?⟩

## 5 Nachweis ⟨Rot-Beweis je neuem Test, inkl. Verdrahtung;

                          bei ganzen Suiten zwei Mutationen⟩

## 6 Prüf-Kommandos ⟨ALLE, die die CI fährt — nicht nur die naheliegenden⟩

## 7 Fixtures ⟨erfunden, nie aus dem Kontext übernommen⟩

## 8 Randbedingungen ⟨Vordergrund, lokal committen, nicht pushen,

                          Umfang nicht erweitern⟩

## 9 Prüffragen ⟨die zehn Fragen unten, JE EINE ZEILE Antwort —

                          „trifft nicht zu" ist eine gültige Antwort,
                          Weglassen ist keine⟩
```

**Das Prüfskript mit gesetzter Locale aufrufen:**
`LC_ALL=C.UTF-8 sh scripts/bau-brief-pruefen.sh <brief.md>`. Ohne sie fällt
`setlocale` auf `C` zurück, wo es keine Fallfaltung für Mehrbyte-Zeichen gibt —
`grep -i` findet dann kein „Ü" zu „ü". Das Skript setzt die Locale nicht selbst.

**Historie, weil die Zahl in dieser Zeile zweimal falsch war:** Bis v1.13.1
trugen drei der zehn Themen-Muster literale Umlaute und fielen ohne Locale aus.
v1.14.0 ersetzte sie durch einen Punkt — was den Defekt tarnte statt behob, weil
ein Punkt **ein Byte** trifft und ein Umlaut aus zweien besteht. Seit dem
Abgleich auf v1.14.1 benutzen alle sieben Ersatzmuster `..?` und treffen unter
beiden Locales (gemessen, Kommando in der Offenlegung im Skript-Kopf). Was
weiterhin von der Locale abhängt, ist die **Fallfaltung** — `## 9 PRÜFFRAGEN`
in Versalien wird ohne sie nicht gefunden.

Gemessen an einem Sonden-Brief, dessen einzige Fundstelle die Überschrift
`## 9 PRÜFFRAGEN` war: ohne Locale meldet das Skript `[KEIN TREFFER]
Prüffragen`, mit Locale `Kandidat`. **Das ist der teuerste Fehler, den dieses
Skript machen kann** — nach seiner eigenen Asymmetrie ist „kein Treffer" das
belastbare Urteil, ein Falsch-Negativ hier sieht also aus wie ein Beweis.
Ob ein bestimmter Brief davon getroffen wird, hängt an seinem Wortlaut: Jedes
Thema hat mehrere Alternativen, und eine ASCII-Alternative rettet es.

**Seit v1.14.0 sucht das Skript umlautfrei** (`pr..?ffrage`, `zweck-identit.t`,
`verhalten .nder`) und entfernt Markdown-Auszeichnung vor der Suche. Gemessen
an einer Sonde mit `## 9 PRÜFFRAGEN` und `Risiko: **R2**`: ohne Locale traf das
alte Prüffragen-Muster **0**, das neue **1**; das alte Risiko-Muster traf durch
den Fettdruck **0**, nach der Bereinigung **1**.

**Der v1.14.0-Fix war jedoch selbst defekt, und wir weichen deshalb von der
Vorlagenfassung ab.** Ein einzelner Punkt trifft **ein Byte**, ein Umlaut
besteht aus zweien — von den sieben Ersatzmustern waren nur die beiden mit
`..?` zweibytefest. Die anderen fünf trafen unter `LC_ALL=C` **null** Zeilen.
Und der `VERBOTE`-Block hatte **beide** Fixes der Version nicht bekommen: Er
suchte mit literalem Umlaut und auf der unbereinigten Datei, fand
`nicht **ändern**` also nie.

Beides ist bei uns behoben (`..?` in allen sieben Mustern, `VERBOTE` auf der
bereinigten Datei), offengelegt als _war → ist → warum_ im Kopf des Skripts und
an die Vorlage gemeldet. **Wir haben nicht auf die Vorlage gewartet**, weil
dieses Skript hier vor jedem Bau-Brief verbindlich läuft und `lehren.md` §15
gilt: Eine Messung, die der Vorlage widerspricht, ist zuerst ein Befund über
die Vorlage — nicht ein Anlass, die eigene Messung umzudeuten. Die
Byte-Gleichheit mit der Vorlage ist der Zweck der Regel, nicht ihr Ziel.

Rot-Beweis der Abweichung an einer Sonde mit `nicht **ändern**` und
`erübrigt`, beides unter `LC_ALL=C`: Elternfassung 0 Hinweise und 0
Verneinungs-Warnungen, neue Fassung je 1.

**Der Aufruf mit `LC_ALL=C.UTF-8` bleibt trotzdem verbindlich** — er schützt
jetzt nicht mehr die Muster, sondern die Fallfaltung.

**Die Form bleibt trotzdem Teil der Regel** — aber aus einem anderen Grund als
früher. Die alte Fassung riet zu `Risiko: R<n> — …` und gegen
Versalien-Überschriften, um einen Werkzeug-Defekt zu umgehen; diese Umgehung
entfällt. Die Form steht jetzt für sich: Ein Brief ist ein Formular mit
festen Feldern, und ein Feld, das jeder anders beschriftet, ist maschinell
nicht mehr auffindbar — auch nicht mit einem reparierten Muster. Wer die Form
aufweicht, verlagert die Prüfung wieder auf das Lesen.

**Warum Block 9 existiert und nicht nur die Fragenliste:** Ein Projekt hat die
Prüffragen einen ganzen Slice lang nicht angewendet — sie standen seit dem
Abgleich in der eigenen `bau-brief.md`. Die Diagnose des Projekts trifft es:
_Das Prüfskript prüft Themen, nicht Fragen — und was das Skript nicht anmahnt,
fällt durch._ Als eigener Block fehlt er auffällig; als Liste im Fließtext
verschwindet er lautlos. Das ist §18 auf unsere eigene Neuerung angewandt:
Eine Regel, deren Auslassung nichts rot macht, ist eine Notiz.

**Block 3 ist der teuerste, wenn er fehlt** — in vier von fünf Projekten kam
darüber ein Fund, den sonst niemand hatte.

**Baut der Hauptagent selbst, entfällt der Empfänger — nicht das Gerüst.** Block
0 und die neun Themen werden dann vor dem ersten Commit durchgegangen, auch
ohne Bau-Subagenten. Eine gekürzte Eigenliste („nur die drei, die mir fehlen") ist
die falsche Antwort — sie schreibt den nächsten blinden Fleck fest, derselbe
Kurzfassung/Langfassung-Fehler eine Ebene tiefer. Ein gegenstandsloses Thema
kostet eine Zeile Begründung, und die ist billiger als eine selbst
zurechtgeschnittene Liste.

**Zuschnitt:** Betrifft ein Slice keine Testsuite (reine Doku, reine
Konfiguration, keine Code-Änderung), haben die Blöcke 5 (Nachweis) und 7
(Fixtures) keinen Gegenstand. Dann steht dort **eine Zeile Begründung** —
z. B. „Kein Gegenstand: der Slice ändert keinen ausführbaren Code der
Anwendung" — nicht nichts. `scripts/bau-brief-pruefen.sh` prüft nur
Anwesenheit von Inhalt, keine Qualität; ein leerer Block besteht die Prüfung
nicht, eine Begründungszeile schon.

**Was NICHT in den Brief gehört: Bewegungsverbote.** Ein Brief liefert Befunde,
keine gesperrten Zonen. Real passiert: Der Brief verbot, eine bestimmte Funktion
anzufassen — genau dort saß die Ein-Zeilen-Behebung eines Panel-Funds.

Ein Bau-Brief ist der Unterschied zwischen einem Slice, der beim ersten Panel
durchgeht, und einem, der drei Runden braucht. Die Punkte unten stehen alle,
weil ihr Fehlen einmal Geld gekostet hat.

**Modell-Stempel:** An jedem Bau-Commit hängt der mehrteilige Stempel
`Built-With: bau=<modell>; nacharbeit=<modell>; arbitriert=<modell> (<datum>)`
— nicht besetzte Rollen weglassen. Eine Welle hat oft mehrere Akteure (Bau,
Nacharbeit, Arbitrierung); ohne das feste Mehrteil-Format ist die
Herkunfts-Regel nach vier Wochen nicht mehr durchsetzbar, und jede Aussage über
Modellverhalten bleibt Anekdote.

**Den Stempel setzt der Hauptagent, nie der Bauer.** Der Bauer kennt seine
eigene Modell-Kennung nicht — er kann sie nur erfinden, und er tut es: In einem
Benchmark trugen **vier von vier** Erstbauten einen erfundenen Stempel, auch
nach ausdrücklicher Auflage im Brief. Ein erfundener Herkunftsstempel ist
schlimmer als keiner, weil er wie eine Messung aussieht und die ganze
Herkunfts-Buchführung entwertet. Der Brief gibt deshalb den Platzhalter vor:

```
Built-With: bau=<vom Orchestrator gesetzt>
```

Der Hauptagent ersetzt ihn beim Landen. Das ist dieselbe Klasse wie die
Prüffragen: Eine Auflage an einen Empfänger, der ihr strukturell nicht folgen
kann, ist keine Regel — siehe „Das Hintergrund-Warte-Muster" unten.

---

## Gerüst (ausformuliert)

```
Repo: ⟨Pfad⟩. Branch ⟨…⟩, HEAD ⟨…⟩. Baue Issue #⟨…⟩.

## 0 Risiko
Risiko: R<n> — Auslöser: ⟨welcher Auslöser aus der Tabelle in CLAUDE.md⟩

## 2 Befund (bereits verifiziert, nicht neu recherchieren)
⟨Was schon gemessen/geprüft ist — mit Datei:Zeile. Erspart dem Bauer die
Sucharbeit und verhindert, dass er zu einem anderen Schluss kommt als die
Vorarbeit.⟩

## 1 Auftrag
⟨Was gebaut werden soll. Bei mehreren Teilen: Reihenfolge und warum.⟩

## Fallen, die ich kenne
⟨Jede bekannte Stolperstelle explizit. Siehe „Typische Fallen" unten.⟩

## 3 Konsumenten
- Wer ruft den geänderten Code auf?

## 4 Sichtbares
- Ändert der Slice sichtbares Verhalten? (dann Doku im selben Slice)

## 5 Nachweis / 7 Fixtures
⟨Prüfbare Punkte, kein Fließtext. Je Punkt: womit belegt. Ohne Testsuite:
eine Zeile Begründung statt nichts.⟩

## 6 Prüf-Kommandos / 8 Randbedingungen
⟨Test-Kommandos VOLLSTÄNDIG, Zeitlimits, Vordergrund, nicht pushen, …⟩

## 9 Prüffragen
⟨die zehn Fragen unten, JE EINE ZEILE Antwort — „trifft nicht zu" ist eine
gültige Antwort, Weglassen ist keine⟩
```

---

## Die Pflichtfragen — warum sie drinstehen

**„Wer ruft den geänderten Code auf?" (Block 3)**
Die teuersten Fehler entstanden durch ungesehene Aufrufer: vier Auswahlfelder,
die nach einer Listen-Umstellung leer blieben; ein Frontend, das ein Feld noch
erwartete; ein Cockpit, dessen Hauptablauf durch eine neue Sperre starb. Der
Bauer soll die Konsumenten **auflisten**, nicht behaupten, es gäbe keine.

**„Ändert der Slice sichtbares Verhalten?" (Block 4)**
Wenn ja, gehört die Doku in denselben Slice. Sonst driftet sie, und der nächste
Agent glaubt ihr.

**„Rot-Beweis für jeden neuen Test." (Block 5)**
Den Fix sabotieren und zeigen, dass der Test fällt. **Auch die Verdrahtung
sabotieren** — die Frage lautet: „Welche einzelne Zeile könnte ich löschen, ohne
dass etwas rot wird?" Drei reale Fälle, in denen ein grüner Test nichts bewies,
stehen in `lehren.md`.

---

## Randbedingungen (Block 8), die immer mitmüssen

- **Alle** Prüf-Kommandos (Block 6) nennen, die die CI fährt. In diesem
  Projekt sind das:
  - `pytest -q backend/tests`
  - `python -m compileall -q backend`
  - im `frontend/`: `npm test`
  - im `frontend/`: `npm run build`
  - im `frontend/`: `npx tsc --noEmit`

  `pip-audit` und `npm audit` liegen seit Scheibe 1 **nicht** mehr auf dem
  Push-Pfad, sondern laufen wöchentlich in `.github/workflows/wochen-pruefung.yml`
  — sie gehören trotzdem in den Bau-Brief, wenn ein Slice Abhängigkeiten ändert,
  weil sie sonst niemand vor dem nächsten Montag sieht.

- Läufe im **Vordergrund**, Zeitlimits explizit. Keine Hintergrundprozesse, keine
  eigenen Subagenten.
- **Lokal committen, nicht pushen.** Landen entscheidet der Hauptagent nach dem Panel.
- Bei neuen Datenbank-Tests: Engine im `tearDown` entsorgen, gegen eine echt
  migrierte DB testen statt gegen ein frisch erzeugtes Schema.
- Wenn parallel ein anderer Slice läuft: **welche Dateien tabu sind**.
- Sprache/Zeichensatz-Regeln des Projekts.
- **Lange Kommandos und Pfade in Listenpunkten gehören in einen
  eingerückten Zaun-Block, nie in einen Inline-Code-Span.** Prettier bricht
  einen zu langen Inline-Code-Span sonst um und lässt die Fortsetzungszeile
  auf Spalte 0 fallen — und `prettier --check` läuft danach grün, weil
  Prettier den Zustand selbst hergestellt hat. Kein Gate fängt das; dritter
  Fall in einem Slice (siehe `lehren.md`).

---

## Typische Fallen (in den Brief kopieren, wenn einschlägig)

**Datenmigration.** Treffermenge kumulativ eng fassen. Downgrade muss den
_Rollback-Pfad_ heil lassen, nicht nur das Schema. Prüfen, ob Altbestand nach
der Änderung den alten _und_ den neuen Wert gleichzeitig zeigt.

**Aggregat statt Einzelabfragen.** Index-Deckung der korrelierten Spalten prüfen.
Konzentrierte _und_ gestreute Datenverteilung messen. Pfade prüfen, die das neue
Feld gar nicht lesen — sie zahlen trotzdem.

**Maskierte Daten / Mandantentrennung.** Nicht nur der Wert, auch **Reihenfolge,
Trefferzahl und Kappungsposition** dürfen nicht vom Geheimnis abhängen. Ein
Freitext-Label wird von feldbasierten Filtern nicht gefangen.

**Listen und Auswahlfelder.** Kappt die Tür? Sagt sie es? Wird aus der Liste
etwas _abgeleitet_, das still ausfällt, statt sichtbar zu degradieren?

**Wächter/Prüftests.** Enthalten die Testdaten den Fall überhaupt, um den es
geht? Fallen zwei Ordnungen zufällig zusammen? Kennt ein AST-Wächter das
_hausübliche_ Änderungsmuster oder nur die naive Form?

**Fremdcode.** Wir haben zwei zugelieferte Übersetzungs-PRs verarbeitet, und
die Linie war dabei nur implizit: **An fremdem Code wird nur korrigiert, wo
der Widerspruch im Artefakt selbst nachweisbar ist** — ein Wert, der der
eigenen Datei widerspricht; ein Schlüssel, den es nicht gibt. Nicht: was uns
besser gefiele. Jede solche Korrektur wird offengelegt als **war → ist →
warum**, damit der Zulieferer sie prüfen kann statt sie zu entdecken. Alles
andere ist eine Rückfrage, keine Änderung.

**Heuristik-Ablösung gilt pro Vorgang, nicht pro Element.** Wer eine Schätzung
durch eine exakte Quelle ersetzt, ersetzt sie für den ganzen Durchlauf. Ein
Vorgang, der für manche Elemente misst und für andere rät, liefert eine
Mischung, die niemand mehr auseinanderhalten kann — und die Fehlerursache
sitzt danach im Anteil, nicht im Verfahren.

---

## Nacharbeit nach dem Panel

Wer die Nacharbeit baut, entscheidet die **Art der Auflage** — siehe unten bei
„Der Nacharbeits-Brief ist ein Bau-Brief", nicht eine Vorliebe. Im Nachtrag:

- **Was bestätigt wurde**, nicht nur was zu tun ist. Sonst sucht der Bauer nach
  Problemen, die geprüft und in Ordnung sind.
- **Widerlegte Befunde ausdrücklich abräumen.** Prüfer irren; ein unkommentierter
  Fehlbefund kostet eine Runde.
- Je Punkt: Schwere, Fundstelle, **Nachweis**. „Wirkt unsauber" ist kein Auftrag.

Die Panel-Pflicht hängt am **gelandeten Zustand**, nicht am Slice — auch die
Nacharbeit selbst ist neuer Code und braucht ein eigenes (ggf. verkürztes)
Panel, siehe `panel.md`.

---

## Der Nacharbeits-Brief ist ein Bau-Brief

Panel-Auflagen sind **Anforderungen, keine Implementierungen** — die Freiheit,
die eine Auflage offenlässt, ist genau die Stelle, an der der nächste Defekt
entsteht (zweimal belegt, einmal _nachdem_ der erste Fall dokumentiert war).

Deshalb: Nacharbeit bekommt dasselbe Pflicht-Gerüst, plus zwei Blöcke:

```markdown
## 10 Bestätigt ⟨arbitrierte Auflagen, nummeriert, je mit Nachweis⟩

## 11 Ausdrücklich abgeräumt — hier ist NICHTS zu tun

                       ⟨widerlegte Fehlbefunde, damit der Bauer nicht sucht⟩
```

Block 11 wurde in einem anderen Projekt erfunden, weil `panel.md` zwar
„ausdrücklich abgeräumt" verlangt, aber nicht sagt, wo das steht. Ohne ihn
sucht der Bauer nach Fehlern, die es nicht gibt.

_Die Nummern 10 und 11 sind nicht kosmetisch: Bis v1.13.1 hießen diese Blöcke
9 und 10 — und Block 9 ist der Prüffragen-Block. Ein Nacharbeits-Brief hatte
damit **zwei Blöcke „9"**, beide legitim aussehend, und das Prüfskript kann
eine Nummern-Kollision nicht sehen (es sucht Themen, nicht Nummern). Nach
jedem Einfügen eines nummerierten Blocks deshalb einmal zählen:_

```bash
grep -o '^## [0-9]*' <brief.md> | sort | uniq -c
```

**Keine neuen Tests in der letzten Nacharbeitsrunde.** Wer in der Schlussrunde
noch einen Test bestellt, bestellt den einzigen Blocker, der am Ende offen
bleibt — genau so gemessen. Ein in der Schlussrunde erkannter Testbedarf wird
ein Issue, keine Auflage.

**Wer die Nacharbeit baut — nach der Art der Auflage, nicht nach Vorliebe:**

- **Mechanische Auflage** (benannter Fix an benannter Stelle, kein Entwurf
  berührt) → **derselbe Bauer.** Sein Kontext spart die Einarbeitung, und es
  gibt nichts zu hinterfragen.
- **Auflage, die den ENTWURF berührt** (eine Vorgabe wird umgekehrt, eine
  Struktur kommt dazu) → **frischer Bauer.** Der bisherige verteidigt seine
  eigene Konstruktion; ein frischer widerspricht produktiv. Real belegt: Der
  frische Bauer widersprach der arbitrierten Auflage und fand dabei einen
  Folgefehler.

_Verworfen wurde die pauschale Regel „immer derselbe, er hat den Kontext" —
Kontext ist bei Entwurfs-Auflagen genau das Hindernis. Und die pauschale Regel
„immer frisch" kostet bei Ein-Zeilen-Fixes mehr, als sie bringt. Beide
Varianten standen zuvor gleichzeitig in diesem Dokument, 60 Zeilen
auseinander — das war der eigentliche Fehler: Wer oben las, machte es anders
als wer unten las._

---

## Fixtures werden erfunden, nie aus dem Kontext übernommen

**Pflichtzeile in jeden Bau-Brief.** Ohne ausdrückliche Regel nimmt der Bauer die
Beispiele, die im Gespräch herumliegen — und das sind die echten.

Realer Verlauf, zweistufig, und die zweite Stufe ist der eigentliche Befund:
Ein Bau-Subagent brauchte einen Namen für ein Testszenario, erfand keinen,
sondern nahm den echten Namen einer realen Person aus dem Gesprächskontext und
schrieb ihn in einen committeten Seed. Beim Verifizieren gefunden und vor dem
Push ersetzt. **Danach** wurde daraus eine Regel formuliert — und in die Regel
selbst schrieb der Hauptagent denselben echten Namen als Beleg.

Die Klasse trifft also nicht nur den Bauer: Wer den Vorfall dokumentiert,
wiederholt ihn. Fälle anonymisieren, bis nur die Klasse übrig bleibt — im Code,
im Issue und in der Lehre.

**Für dieses Projekt besonders relevant:** Testdaten enthalten Personennamen aus
Gesichtserkennung. Ein Name aus einem echten Gesichtserkennungs-Match gehört
nicht in eine Fixture — auch nicht als „nur ein Beispiel".

## Der Rot-Beweis ist eine Schrittfolge, keine Warnung

Ein misslungener Rot-Beweis meldet **grün** — er sieht von außen genauso aus
wie ein gelungener. Drei Arten davon in einem einzigen Slice gemessen: Die
Sabotage war gar keine; die Sabotage kam im laufenden Artefakt nicht an; der
Bau scheiterte still, weil die Ausgabe nach `/dev/null` ging. Dazu ein
Rückbau per `git checkout --`, der die uncommittete Nacharbeit gleich mit
löschte. Deshalb nummeriert statt ermahnt:

1. **Committen.** Vor der ersten Mutation ein `wip`-Commit — sonst löscht der
   Rückbau Arbeit mit, die nie in der Mutation stand. Am Ende amenden.
2. **a) Die Sabotage im Quelltext belegen.** Nicht „ich habe geändert",
   sondern die geänderte Zeile zeigen.
   **b) Die Sabotage im laufenden Artefakt nachweisen.** Der Marker steht im
   **String**, nicht im Kommentar — ein Kommentar überlebt jeden Bau und
   beweist nichts über das, was wirklich läuft. Dieser Schritt ist der, an
   dem wir zuletzt selbst gescheitert sind: Eine Umlaut-Probe war grün, weil
   der Brief ein zusätzliches ASCII-Muster enthielt, das der Test fand.
3. **Messen ohne Pipe.** Der Exit-Code ist die Antwort. Eine Pipe verschluckt
   ihn (`set -o pipefail` ist nicht überall gesetzt), und `grep` auf der
   Ausgabe misst die Formulierung statt das Ergebnis.
4. **Zurücknehmen und den Baum prüfen.** `git status` und `git diff` danach,
   nicht davor.

Zwei Zuschnitt-Regeln dazu:

- **Die Mutation trifft die gesamte betroffene Menge**, nicht ihren ersten
  Vertreter. Gemessen: Ein Beweis leerte nur den ersten Abschnitt und war
  deshalb grün an der Stelle, an der er hätte rot sein müssen.
- **Ein Rot-Beweis mutiert eine Zeile, die im Diff steht.** Vier grüne Tests
  gegen null geänderte Zeilen bestätigen die Ausgangslage, nicht den Fix.

## Rot-Beweis gilt auch für ganze Suiten

Der Rot-Beweis für einzelne Tests reicht nicht, wenn eine ganze Suite als
Sicherheitsnetz gemeldet wird (Rauchtests, Vor-Release-Sets). Vor der Meldung
**zwei bekannte Fehler absichtlich wieder einbauen** und beobachten.

Der Fall, der **nicht** rot wird, ist der lehrreichere: In einem realen Versuch
fing die Suite die eine Regression und die andere nicht — weil der Zugangsschutz
an zwei unabhängigen Strängen hing und der Test nur einen berührte. Was die
Suite **nicht** behauptet, gehört in den Test geschrieben, nicht in die
Erinnerung.

**Mutationen für Rot-Beweise laufen in einem Wegwerf-Worktree, nicht im
Arbeitsbaum.** Realer Vorfall in diesem Repo: Ein Bauer wollte für einen
Rot-Beweis eine Fehlerbehandlung im Arbeitsbaum entfernen; die
Sicherheitsprüfung der Werkzeugkette hat die Bearbeitung blockiert —
nachvollziehbar, das Entfernen eines `try/catch` sieht wie eine Schwächung
aus. Der Bauer wich auf einen anderen Weg aus, fuhr die Mutation, nahm sie
zurück und berichtete offen. Das Ergebnis war sauber, das Muster ist es
nicht: „blockiert, also anderen Weg suchen" darf nicht zur Gewohnheit werden.

Stattdessen auf dem gemessenen Commit mutieren:

```bash
git worktree add --detach <pfad> <commit>
# … mutieren, messen …
git worktree remove --force <pfad>
```

Drei Gründe, knapp: (1) Der lebende Code wird nicht angefasst, also löst die
Mutation keine Schutzprüfung aus — und niemand muss sie umgehen. (2) Die
Rücknahme entfällt, der Baum wird weggeworfen; damit entfällt auch die
Beweislast „ist wirklich alles zurückgenommen?". (3) Ein beschädigter
Prüfgegenstand kann nicht versehentlich zurückbleiben.

Dieselbe Überlegung fordert `docs/agents/panel.md` seit v1.13.0 bereits für
die Stimmen — hier gilt sie für den Bauer.

---

## Was im Bericht des Bauers zu prüfen ist

Ein Bericht ist eine Absichtserklärung, kein Nachweis. Zwei Muster haben sich als
gefährlich erwiesen, beide **nicht böswillig** — Modelle vervollständigen
plausibel:

- **Erfundene Quellenangaben.** Ein Report meldete drei rote Läufe als
  „vorbestehende, ordnungsabhängige Flakes" — **mit Verweis auf einen Abschnitt
  der Lehren-Datei, der etwas völlig anderes behandelt.** Die blinde Stimme fuhr
  drei volle Läufe: alle grün, die Flakes reproduzierten nicht. Geliehene
  Autorität tarnt einen ungeprüften Befund, und die _erfundene_ Quelle ist
  gefährlicher als gar keine — sie liest sich wie ein nachgeschlagener Fakt und
  wird leichter durchgewunken.
  → **Jedes Zitat im Bericht nachschlagen.** Steht dort nicht, was behauptet wird,
  ist der ganze Befund unbelegt.
- **Behauptete Flakes.** Wer einen roten Lauf als Flake abtut, muss ihn
  **reproduzieren** — mehrfach, mit und ohne Diff. Ein Flake, der sich nicht
  reproduzieren lässt, ist kein Flake, sondern ein Fund.

Verwandt: Ein als „verifiziert" gemeldeter Fix, bei dem nur der Nachbar-Zweig
geprüft wurde. Die Frage lautet nicht „hast du geprüft", sondern **„was genau hast
du ausgeführt, und was kam heraus"**.

## Das Hintergrund-Warte-Muster

Ein wiederkehrendes Bauer-Verhalten, **elf dokumentierte Fälle über zwei
Projektgenerationen**: Der Bauer legt die Gates in den Hintergrund und endet mit
„warte auf das Ergebnis des Hintergrundlaufs" — obwohl die Randbedingung im
Brief das ausdrücklich untersagt. **Die Brief-Zeile allein verhindert es
nicht.** Zwei Mechanismen wirken:

**Inzwischen 10 von 10 Fällen, und die Deutung hat sich geschärft: Die
Brief-Zeile kann nicht wirken, weil der Empfänger sie nicht befolgen KANN.** Das
Bau-Modell legt lange Läufe strukturell in den Hintergrund und wartet auf ein
Signal, das seine Ausführungsumgebung nie liefert. Auch doppelte, ausdrückliche
Formulierung im Brief ändert daran nichts (getestet).

**Deshalb gehört das nicht in den Bau-Brief, sondern eine Ebene höher:**

1. **In die Systeminstruktion des Bauers** (nicht in den Auftrag): Gates
   blockierend im Vordergrund, keine Hintergrundläufe. Das nimmt den Anlass an
   der Stelle, an der er entsteht.
2. **Als fester Ablaufschritt des Orchestrators**, nicht als Brief-Auflage: Der
   Nachstoß („Ergebnis selbst prüfen, Report abliefern") wird **eingeplant**,
   nicht als Reaktion auf ein Versäumnis improvisiert. Er wirkt zuverlässig
   (10/10), die Brief-Zeile nachweislich nicht.

Der Zustand „wartet auf Ergebnis" ist **kein Report** — er wird nie als
Abschluss akzeptiert.

_Die allgemeine Lehre dahinter: Eine Regel an einen Empfänger, der ihr
strukturell nicht folgen kann, ist keine Regel, sondern eine Beschwerde. Sie
gehört dorthin, wo das Verhalten entsteht._

**Damit ist die frühere Randbedingung „Vordergrund, keine
Hintergrundprozesse" (Block 8) als VERTAGT-MIT-BEDINGUNG aufgehoben.** Beim
v1.11.3-Abgleich stand hier nur die eine Zeile „Läufe im Vordergrund,
Zeitlimits explizit. Keine Hintergrundprozesse, keine eigenen Subagenten." —
diese Sektion sagt mehr: warum die Brief-Zeile allein nicht wirkt und wohin
die Regel gehört (Systeminstruktion + fester Orchestrator-Schritt statt
Brief-Auflage). Die Zeile in Block 8 bleibt als Randbedingung stehen; diese
Sektion ist die Begründung dahinter, die vorher fehlte.

---

## Wenn ein Bauer mitten im Rot-Beweis stirbt

Der Rot-Beweis ist das einzige Ritual, das den Code **absichtlich kaputt macht**.
Bricht die Sitzung dabei ab, beschreibt der letzte Bericht den Zustand _davor_
(„alle Tests bestehen, jetzt der Rot-Beweis") — wer das liest und nicht
nachsieht, übernimmt Sabotage als fertige Arbeit.

**Wiederaufnahme-Protokoll, immer in dieser Reihenfolge:**

1. `git status` und `git diff` lesen, **bevor** irgendetwas gebaut wird.
2. `git log --oneline origin/main..HEAD` — was ist lokal, was gepusht?
3. Den letzten Bericht als **Absichtserklärung** lesen, nicht als Zustand.
4. Erst dann weiterbauen — und nichts doppelt.

---

## Die Wahrheit des Briefs: Behauptungen sind Bringschuld des Schreibers

Zweimal in einer Woche war die Fehlerquelle nicht der Bauer, sondern der
Brief. Drei Regeln daraus:

**„Dasselbe Muster wie Y" ist erst eine gültige Brief-Aussage, wenn Y wirklich
gelesen wurde und seine Schutzschichten AUFGEZÄHLT und in den Auftrag
übernommen sind.** Real: Der echte Zwilling trug drei Schutzschichten, die die
Kopie nicht bekam — die blinde Stimme fand es, weil sie den Zwilling las. Ohne
die Aufzählung erbt die Kopie nur den Namen, nicht den Schutz.

**Eine Umfangsgrenze gilt für neue Features, nie für die Blast-Radius-Prüfung
einer Default-Änderung.** Wer einen globalen Default oder Wert ändert, prüft
ALLE Leser — auch die ausgeklammerten. Real: Der Bauer hielt sich regelkonform
an „nur Konsument X" und meldete statt zu fixen; ein ausgeklammerter Pfad las
den scharf geschalteten Default. Regelkonform und trotzdem falsch heißt: Die
Grenze war zu weit formuliert, nicht der Bauer zu wörtlich.

**Der Bauer korrigiert eine falsche Brief-Prämisse mit Beleg — das ist
erwünschtes Verhalten, kein Ungehorsam.** Zwei Belege: Ein Bauer suchte den im
Brief angenommenen Helfer, fand ihn nicht im Baum und korrigierte die Annahme
im Report; ein anderer korrigierte die R-Einstufung des Auftraggebers am
Tabellentext. Der Brief ist Anleitung, kein Dogma; verifizierte Gegenbelege
gehören in den Report.

## Den Orchestrator prüft niemand — außer er bestellt die Prüfung

Alles, was der Hauptagent selbst schreibt, ging an Panel und Gates vorbei:
Bau-Briefe, Issue-Texte, CHANGELOG-Einträge, Panel-Kommentare. Kein Gate liest
sie — und in jeder Bilanz traf ein erheblicher Teil der bestätigten Funde nicht
den Bauer, sondern den Auftraggeber; bei uns zuletzt sieben von fünfzehn über
drei Slices, darunter drei Blocker.

**Seit v1.14.1 ist das teilweise geschlossen, und der Unterschied gehört
benannt:** Der Bau-Brief geht als Issue-Kommentar an die **zweite** Stimme
(Abschnitt „Ablage" unten), und der Panel-Diff enthält die
Orchestrator-Texte des Slices (`panel.md`, „Der Prüfgegenstand schließt die
Orchestrator-Texte ein"). Ungeprüft bleibt, was **außerhalb** eines Slices
entsteht: Meldungen an die Vorlage, Antworten an Projektfremde, dieser Absatz
hier. Für die gilt weiterhin nur die eigene Sorgfalt — was schwächer ist, als
es sich anfühlt.

Fünf Regeln, die den Orchestrator in den Prüfbereich holen:

- **Jeder Brief mit einer Empfehlung trägt die Klausel: „Prüfe meine
  Einschätzung, statt sie zu übernehmen."** Ohne sie liest der Bauer eine
  Vermutung als Befund. Der Satz kostet eine Zeile und ist die einzige
  Stelle, an der der Brief seine eigene Fehlbarkeit zugibt.
- **Verhaltensvorgaben des Briefs sind Widerlegungs-Auftrag mindestens einer
  Stimme.** Gemessen: Der schwerste Fund eines Slices war die Folge einer
  Brief-Vorgabe — und die blinde Stimme, die den Brief kannte, hakte sie ab
  statt sie zu prüfen. Was der Brief anordnet, muss jemand angreifen dürfen.
- **Eine Fundstelle aus einem Ticket ist ein Verdacht, keine Tatsache.** Sie
  wird im Brief als Verdacht markiert und vom Bauer nachgemessen. Ein Ticket
  ist ein Gedächtnisstand, kein Messwert — und altert.
- **Ein Brief bestellt eine Tatsache an genau einer Stelle.** Dieselbe Zahl
  in Block 2 und Block 5 driftet beim ersten Nachtrag; dann steht im Brief
  ein Widerspruch, den der Bauer nach Belieben auflöst.
- **Jede Brief-Option nennt die Umgebung, in der sie läuft.** Bei uns kein
  Gedankenspiel: Die Codex-Stimme läuft in einem Container ohne
  `bwrap`-Rechte; eine Option, die dort einen Dateizugriff voraussetzt, ist
  kein Weg, sondern ein Totalausfall — in einem gemessenen Fall 0 von 3
  Stimmen.

**Ausgelieferte Orchestrator-Texte sind Produkt.** CHANGELOG-Einträge,
Issue-Texte und Antworten an Projektfremde unterliegen denselben Stilregeln
wie der Code (echte Umlaute, keine internen Kürzel roh) **und derselben
Prüfung** — der Panel-Diff enthält sie, siehe `panel.md`. Sie sind
Außenwirkung; das ist bei uns ein R3-Auslöser, wenn sie über eine
Schnittstelle nach außen gehen.

**Der Brief in einem öffentlichen Repo trägt keine Zugangswege.** Unsere
Briefe werden als Issue-Kommentar gepostet, und dieses Repo ist öffentlich.
Adressen von Instanzen, Kontonamen, Pfade zu Schlüsseldateien, die Form eines
Tokens: nichts davon gehört hinein — auch nicht als Beispiel, auch nicht
erfunden-aber-echt-aussehend. Was der Bauer an Zugang braucht, bekommt er
außerhalb des Briefs.

**Der Bericht des Bauers ist die Abschlussantwort, keine Datei im Repo.**
Gemessen: Zwei von drei Läufen legten ihn in den Arbeitsbaum, einer committete
ihn. Ein Bericht im Baum ist ein Messartefakt, das die Repo-Stimmen dann als
Quelle lesen — siehe `panel.md`, „Messartefakte".

## Ablage: der Brief gehört dorthin, wo die zweite Stimme ihn findet

**Die blinde Erststimme bleibt blind — sie bekommt den Brief nicht** (siehe
`panel.md`, die Blindheitsregel wohnt dort). Die Messung _Commit gegen
Brief_ ist Auftrag der **zweiten Stimme**: Sie erreicht den Brief unabhängig
vom Arbeitsbaum des Hauptagenten, und der Owner sieht die Annahmen des
Briefs vor dem Bau, nicht erst im Panel.

**Der Bau-Brief wird beim Start des Slices als Issue-Kommentar gepostet** —
nicht nur an den Bauer übergeben. Der Prompt der zweiten Stimme nennt dann
die Fundstelle („Brief: Issue #N, Kommentar vom …").

Gemessen, in beide Richtungen: In einem Slice lag der Brief nur im Scratchpad
des Hauptagenten. Prüffrage 6 konnte deshalb nur gegen Code und CHANGELOG
laufen — und fand dort eine **erfundene Zahl** (vier Stellen behaupteten einen
Fehlercode, den das Produkt nie liefert). Am Brief gemessen wäre sie zwei
Runden früher aufgefallen. Im Folge-Slice lag der Brief als Issue-Kommentar
vor: Die zweite Stimme lieferte eine Tabelle _Behauptung → stimmt/stimmt
nicht → Beleg_, zwei Behauptungen darin „überschärft".

**Für uns gilt der Issue-Kommentar als Regelweg, nicht die freie Wahl der
Vorlage:** So bleibt der Brief außerhalb des versionierten Prozess-Stands,
statt als Datei im Repo mitzulaufen — und der Owner sieht die Annahmen im
Issue, nicht erst im commiteten Repo-Stand.

## Zehn Prüffragen vor der Landung — mechanisch stellbar, alle aus Messungen

1. **Schreibt dieser Fix an einer Stelle, die vorher nur las — und wer teilt
   sich die Zielzeilen?** (Ein Fix machte einen inerten Pfad aktiv und schuf
   damit den stillen Verlustweg, den er beheben sollte.)
2. **Prüft dieser Test, was wahr bleiben MUSS — oder nur, was sich nicht
   ändern DARF?** (Ein Test nagelte die Nebenbedingung fest und zementierte
   den Ausfall des Zwecks: eine 26 Monate zu großzügige Präklusionsfrist,
   grün abgesichert.)
3. **Welche Geschwister-Routinen haben denselben Aufbau, und warum bleiben
   sie so?** „Bewusst später" ist eine gültige Antwort — Fehlen keine.
   (Ein Pfad wurde transaktional, Anlegen und Löschen mit identischem Aufbau
   blieben zurück.)
4. **Wählt eine Routine eine Zeile aus UND legt bei Nichtpassung eine neue
   an?** Dann läuft die Auswahl über die Identität des Zwecks, nie über eine
   Reihenfolge — sonst wächst der Bestand mit jedem Aufruf. (Gemessen: vier
   offene Fristen nach drei Korrekturen, `.first()` fand immer die falsche.
   Bitter: Eine frühere, richtige deterministische Sortierung machte den
   Defekt reproduzierbar statt selten.)
5. **Gilt die Rot-Zahl auch mit Kontext?** „N Tests rot" zählt nur zusammen
   mit Lauf-Umfang (eine Datei / ganze Suite) und Zustand der Testdatenbank
   (frisch/befüllt). Gemessen: dieselbe Mutation ergab 1, 6 oder 26 rote
   Tests je nach Quelle — die nackte Zahl ist eine Erinnerung, keine Messung,
   und landet doch als harte Zusage im Code.
6. **Ist jede Behauptung im Brief belegt oder als Annahme markiert?**
   (Siehe „Die Wahrheit des Briefs" oben.)
7. **Welchen Pfad benutzt das PRODUKT wirklich?** Ein Test, der die Zusage auf
   einem Pfad beweist, den die Oberfläche nie aufruft, ist eine Beruhigung,
   keine Prüfung. Gemessen: Tests bewiesen einen Direkt-Aufruf, das Produkt
   nutzt einen anderen Weg — der Schutzzweig war unerreichbar, der Kanal tot,
   alles grün. Der Rot-Beweis stellt den ECHTEN Aufrufweg nach, mit dem
   Datenpaket der Oberfläche. (§8 in neuer Gestalt: Der Wächter lief, aber
   am falschen Objekt.)
8. **Zählt der Slice seine eigene Zusage ab?** Wer „kein X mehr über Y"
   verspricht, zählt die Y. Gemessen: Ein Slice versprach Dichtigkeit für
   einen Sprachassistenten mit acht Werkzeugen und schloss eines; der Brief
   listete unter „Konsumenten" genau dieses eine.
   _Diese Frage wirkt als **Prüferfrage** stärker denn als Bauerfrage und
   steht deshalb auch im Prüfauftrag der Stimmen (`panel.md`): Wer die Zusage
   geschrieben hat, zählt sie anders nach als wer sie zum ersten Mal liest._
9. **Welche Eigenschaft hat die Antwort, die es NUR gibt, wenn die Funktion
   wirklich läuft?** Gemessen: Eine Suite war vor und nach dem Fix identisch
   grün — die Funktion tat wochenlang nichts, und niemand sah es, weil kein
   Test etwas prüfte, das ihre Ausführung voraussetzt. Zwei Kopfzeilen der
   Antwort haben es dann entschieden. Die Frage sucht das Merkmal, das eine
   nicht ausgeführte Funktion nicht fälschen kann.
10. **Wer hat den Schlüssel heute NICHT — und ist das dieselbe Person wie
    „frische Installation"?** Ein Owner-Entscheid ist eine **Anforderung, kein
    Abnahmekriterium**: Er sagt, was gelten soll, nicht dass es gilt. Gemessen
    als Erst-Rollout-Fehler — ein richtiger Entscheid, dessen Folge niemand
    abnahm, in 27 Review-Läufen genau **einmal** gefunden. Für uns die
    konkrete Form: Ein Konto ohne hinterlegten Immich-Schlüssel und eine
    frische `accounts.json` sind **zwei** Zustände, nicht einer.
