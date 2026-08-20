# Bau-Brief: Vorlage für Aufträge an Bau-Subagenten

> **Der Bau-Brief ist die einzige Leitplanke, die den Bauer erreicht.**
> Regeln im Repo erreichen ihn nicht: Ein Bau-Subagent arbeitet den Brief ab,
> nicht `docs/agents/`. In fünf Projekten gemeldet, zweimal ist genau daran
> eine Pflichtregel gescheitert — sie stand im Repo und fehlte im Brief.
>
> Deshalb hat der Brief ein **Pflicht-Gerüst**. Fehlt ein Block, ist der Brief
> nicht fertig; das ist prüfbar — vor jedem Absenden verbindlich:
> `sh scripts/bau-brief-pruefen.sh <brief.md>`.

## Pflicht-Gerüst (alle acht Blöcke, keiner leer)

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
```

**Block 3 ist der teuerste, wenn er fehlt** — in vier von fünf Projekten kam
darüber ein Fund, den sonst niemand hatte.

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

**Modell-Stempel:** Der Bauer hängt an seinen Commit `Built-With: <modell>
(<datum>)` an — sonst ist die Herkunfts-Regel nach vier Wochen nicht mehr
durchsetzbar, und jede Aussage über Modellverhalten bleibt Anekdote.

---

## Gerüst (ausformuliert)

```
Repo: ⟨Pfad⟩. Branch ⟨…⟩, HEAD ⟨…⟩. Baue Issue #⟨…⟩.

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

---

## Nacharbeit nach dem Panel

Denselben Subagenten weiterbeauftragen, nicht einen neuen — er hat den Kontext.
Im Nachtrag:

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
## 9 Bestätigt ⟨arbitrierte Auflagen, nummeriert, je mit Nachweis⟩

## 10 Ausdrücklich abgeräumt — hier ist NICHTS zu tun

                       ⟨widerlegte Fehlbefunde, damit der Bauer nicht sucht⟩
```

Block 10 wurde in einem anderen Projekt erfunden, weil `panel.md` zwar
„ausdrücklich abgeräumt" verlangt, aber nicht sagt, wo das steht. Ohne ihn
sucht der Bauer nach Fehlern, die es nicht gibt.

**Frischer Bauer statt desselben:** Bewährt hat sich auch, die Nacharbeit an
einen _anderen_ Subagenten zu geben. In einem Fall widersprach der frische
Bauer der arbitrierten Auflage produktiv und fand dabei einen Folgefehler.

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

## Rot-Beweis gilt auch für ganze Suiten

Der Rot-Beweis für einzelne Tests reicht nicht, wenn eine ganze Suite als
Sicherheitsnetz gemeldet wird (Rauchtests, Vor-Release-Sets). Vor der Meldung
**zwei bekannte Fehler absichtlich wieder einbauen** und beobachten.

Der Fall, der **nicht** rot wird, ist der lehrreichere: In einem realen Versuch
fing die Suite die eine Regression und die andere nicht — weil der Zugangsschutz
an zwei unabhängigen Strängen hing und der Test nur einen berührte. Was die
Suite **nicht** behauptet, gehört in den Test geschrieben, nicht in die
Erinnerung.

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
