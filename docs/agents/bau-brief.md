# Bau-Brief: Vorlage für Aufträge an Bau-Subagenten

Ein Bau-Brief ist der Unterschied zwischen einem Slice, der beim ersten Panel
durchgeht, und einem, der drei Runden braucht. Die Punkte unten stehen alle,
weil ihr Fehlen einmal Geld gekostet hat.

---

## Gerüst

```
Repo: ⟨Pfad⟩. Branch ⟨…⟩, HEAD ⟨…⟩. Baue Issue #⟨…⟩.

## Befund (bereits verifiziert, nicht neu recherchieren)
⟨Was schon gemessen/geprüft ist — mit Datei:Zeile. Erspart dem Bauer die
Sucharbeit und verhindert, dass er zu einem anderen Schluss kommt als die
Vorarbeit.⟩

## Auftrag
⟨Was gebaut werden soll. Bei mehreren Teilen: Reihenfolge und warum.⟩

## Fallen, die ich kenne
⟨Jede bekannte Stolperstelle explizit. Siehe „Typische Fallen" unten.⟩

## Pflichtfragen
- Wer ruft den geänderten Code auf?
- Ändert der Slice sichtbares Verhalten? (dann Doku im selben Slice)

## Abnahme
⟨Prüfbare Punkte, kein Fließtext. Je Punkt: womit belegt.⟩

## Randbedingungen
⟨Test-Kommandos VOLLSTÄNDIG, Zeitlimits, Vordergrund, nicht pushen, …⟩
```

---

## Die Pflichtfragen — warum sie drinstehen

**„Wer ruft den geänderten Code auf?"**
Die teuersten Fehler entstanden durch ungesehene Aufrufer: vier Auswahlfelder,
die nach einer Listen-Umstellung leer blieben; ein Frontend, das ein Feld noch
erwartete; ein Cockpit, dessen Hauptablauf durch eine neue Sperre starb. Der
Bauer soll die Konsumenten **auflisten**, nicht behaupten, es gäbe keine.

**„Ändert der Slice sichtbares Verhalten?"**
Wenn ja, gehört die Doku in denselben Slice. Sonst driftet sie, und der nächste
Agent glaubt ihr.

**„Rot-Beweis für jeden neuen Test."**
Den Fix sabotieren und zeigen, dass der Test fällt. **Auch die Verdrahtung
sabotieren** — die Frage lautet: „Welche einzelne Zeile könnte ich löschen, ohne
dass etwas rot wird?" Drei reale Fälle, in denen ein grüner Test nichts bewies,
stehen in `lehren.md`.

---

## Randbedingungen, die immer mitmüssen

- **Alle** Prüf-Kommandos nennen, die die CI fährt. In diesem Projekt sind das:
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
