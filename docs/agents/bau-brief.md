# Bau-Brief: Vorlage für Aufträge an Bau-Subagenten

> **Der Bau-Brief ist die einzige Leitplanke, die den Bauer erreicht.**
> Regeln im Repo erreichen ihn nicht: Ein Bau-Subagent arbeitet den Brief ab,
> nicht `docs/agents/`. In fünf Projekten gemeldet, zweimal ist genau daran
> eine Pflichtregel gescheitert — sie stand im Repo und fehlte im Brief.
>
> Deshalb hat der Brief ein **Pflicht-Gerüst**. Fehlt ein Block, ist der Brief
> nicht fertig; das ist prüfbar — vor jedem Absenden verbindlich:
> `sh scripts/bau-brief-pruefen.sh <brief.md>`.

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

## 9 Prüffragen ⟨die acht Fragen unten, JE EINE ZEILE Antwort —

                          „trifft nicht zu" ist eine gültige Antwort,
                          Weglassen ist keine⟩
```

**Warum Block 9 existiert und nicht nur die Fragenliste:** Ein Projekt hat die
Prüffragen einen ganzen Slice lang nicht angewendet — sie standen seit dem
Abgleich in der eigenen `bau-brief.md`. Die Diagnose des Projekts trifft es:
_Das Prüfskript prüft Themen, nicht Fragen — und was das Skript nicht anmahnt,
fällt durch._ Als eigener Block fehlt er auffällig; als Liste im Fließtext
verschwindet er lautlos. Das ist §21 auf unsere eigene Neuerung angewandt:
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

**Modell-Stempel:** Der Bauer hängt an seinen Commit den mehrteiligen Stempel
`Built-With: bau=<modell>; nacharbeit=<modell>; arbitriert=<modell> (<datum>)`
an — nicht besetzte Rollen weglassen. Eine Welle hat oft mehrere Akteure (Bau,
Nacharbeit, Arbitrierung); ohne das feste Mehrteil-Format ist die
Herkunfts-Regel nach vier Wochen nicht mehr durchsetzbar, und jede Aussage über
Modellverhalten bleibt Anekdote.

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
⟨die acht Fragen unten, JE EINE ZEILE Antwort — „trifft nicht zu" ist eine
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
## 9 Bestätigt ⟨arbitrierte Auflagen, nummeriert, je mit Nachweis⟩

## 10 Ausdrücklich abgeräumt — hier ist NICHTS zu tun

                       ⟨widerlegte Fehlbefunde, damit der Bauer nicht sucht⟩
```

Block 10 wurde in einem anderen Projekt erfunden, weil `panel.md` zwar
„ausdrücklich abgeräumt" verlangt, aber nicht sagt, wo das steht. Ohne ihn
sucht der Bauer nach Fehlern, die es nicht gibt.

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

## Ablage: der Brief gehört dorthin, wo die blinde Stimme ihn findet

**Der Bau-Brief wird beim Start des Slices als Issue-Kommentar gepostet** (oder
unter `docs/agents/briefe/<issue>.md` committet) — nicht nur an den Bauer
übergeben. Der Prompt der blinden Stimme nennt dann die Fundstelle („Brief:
Issue #N, Kommentar vom …").

Gemessen, in beide Richtungen: In einem Slice lag der Brief nur im Scratchpad
des Hauptagenten. Prüffrage 6 konnte deshalb nur gegen Code und CHANGELOG
laufen — und fand dort eine **erfundene Zahl** (vier Stellen behaupteten einen
Fehlercode, den das Produkt nie liefert). Am Brief gemessen wäre sie zwei
Runden früher aufgefallen. Im Folge-Slice lag der Brief als Issue-Kommentar
vor: Die Stimme lieferte eine Tabelle _Behauptung → stimmt/stimmt nicht →
Beleg_, zwei Behauptungen darin „überschärft".

Nebeneffekt, der allein den Aufwand trägt: **Der Owner sieht die Annahmen des
Briefs vor dem Bau**, nicht erst im Panel.

**Für uns gilt der Issue-Kommentar als Regelweg, nicht die freie Wahl der
Vorlage:** Unser `paths-ignore` filtert `**.md` aus dem Push-Pfad heraus — ein
Brief unter `docs/agents/briefe/<issue>.md` würde also keinen CI-Lauf
auslösen und geräuschlos an der Dauerregel „ein Lauf je Slice" vorbeilaufen;
außerdem sieht der Owner die Annahmen so im Issue, nicht erst im commiteten
Repo-Stand.

## Acht Prüffragen vor der Landung — mechanisch stellbar, alle aus Messungen

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
   Datenpaket der Oberfläche. (§21 in neuer Gestalt: Der Wächter lief, aber
   am falschen Objekt.)
8. **Zählt der Slice seine eigene Zusage ab?** Wer „kein X mehr über Y"
   verspricht, zählt die Y. Gemessen: Ein Slice versprach Dichtigkeit für
   einen Sprachassistenten mit acht Werkzeugen und schloss eines; der Brief
   listete unter „Konsumenten" genau dieses eine.
