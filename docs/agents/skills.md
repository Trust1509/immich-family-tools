# Skills: was der Prozess voraussetzt

Der Ablauf in `../../CLAUDE.md` (Abschnitt „Arbeitsweise") benennt Schritte —
Grillen, Zerlegen, Bauen, Prüfen. Für die meisten davon gibt es fertige
**Skills**: abrufbare Anleitungen, die der Agent lädt und befolgt, statt die
Methode jedes Mal neu zu erfinden.

**Woher:** [`mattpocock/skills`](https://github.com/mattpocock/skills). Zwei
Installationswege, **einen** wählen — beide bedeuten jeden Skill doppelt:

```bash
claude plugins install mattpocock-skills   # verwaltetes Bündel, aktualisiert sich
npx skills@latest add mattpocock/skills    # editierbare Kopien, auswählbar
```

Bei der zweiten Variante fragt der Installer, welche Skills mitkommen —
**`setup-matt-pocock-skills` muss dabei sein.**

**Wichtig — Skills liegen pro RECHNER, nicht pro Repo.** Sie werden global
installiert (typischerweise unter `~/.claude/skills/`) und gelten dann für alle
Projekte. Ein frisch geklontes Repo bringt sie **nicht** mit. Auf einem neuen
Rechner sind sie also einmal einzurichten, sonst laufen Verweise ins Leere —
auch der in `triage-labels.md`.

**Nur empfehlen, was existiert.** Die Liste unten ist eine Momentaufnahme.
Bevor ein Skill in einem Auftrag genannt wird: nachsehen, ob er auf diesem
Rechner wirklich vorhanden ist. Erfundene Skill-Namen sind eine teure Art,
Zeit zu verlieren.

---

## Einmal pro Repo

**`setup-matt-pocock-skills`** — richtet das Repo für die Skills ein:
Issue-Tracker-Anbindung, das Triage-Vokabular (die fünf Rollen, die
`triage-labels.md` auf die echten Label-Namen abbildet) und die Doku-Ablage.
Gehört in die Setup-Checkliste, bevor der erste Slice läuft.

---

## Phase 0 — bevor irgendetwas gebaut wird

Der teuerste Fehler ist, hier zu sparen: Ein Agent baut sonst das, was plausibel
klingt, und das ist selten das Gemeinte.

| Skill                     | Wofür                                                                                                      |
| ------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **`grilling`**            | Die Idee im Verhör scharf stellen — Fragen einzeln, mit Empfehlung, bis die Spezifikation baubar ist       |
| **`grill-with-docs`**     | Dasselbe, aber mit abgestimmter Planung und Domänenmodell — die gründlichere Variante für größere Vorhaben |
| **`grill-me`**            | Umgekehrte Richtung: der Agent grillt **dich**, wenn du selbst noch nicht weißt, was du willst             |
| **`domain-modeling`**     | Die zentralen Begriffe und ihre Invarianten festklopfen                                                    |
| **`ubiquitous-language`** | Ein Glossar, das Code, Doku und Gespräch dieselben Wörter benutzen lässt                                   |
| **`decision-mapping`**    | Entscheidungen mit Alternativen und Konsequenzen sichtbar machen, statt sie im Chat zu verlieren           |

## Von der Spezifikation zur Arbeit

| Skill           | Wofür                                                               |
| --------------- | ------------------------------------------------------------------- |
| **`to-prd`**    | Aus der Grilling-Diskussion ein Anforderungsdokument synthetisieren |
| **`to-issues`** | Die Spezifikation in **vertikale Slices** zerlegen — je ein Issue   |
| **`triage`**    | Issue-Status pflegen (die fünf Rollen aus `triage-labels.md`)       |

## Fundament und Leitplanken

| Skill                            | Wofür                                                                                                                           |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **`setup-pre-commit`**           | Prüfungen beim Commit statt beim Ärgernis                                                                                       |
| **`git-guardrails-claude-code`** | Hooks gegen gefährliche Git-Befehle. **Zuschnitt prüfen:** Wer bewusst direkt auf den Hauptzweig pusht, muss das erlaubt lassen |

## Beim Bauen

| Skill                     | Wofür                                                                                     |
| ------------------------- | ----------------------------------------------------------------------------------------- |
| **`tdd`**                 | Test zuerst, rot-grün-refaktorieren — passt zur Rot-Beweis-Pflicht aus dem Bau-Brief      |
| **`implement`**           | Einen abgestimmten Plan abarbeiten                                                        |
| **`codebase-design`**     | Modulschnitt und tiefe Schnittstellen                                                     |
| **`design-an-interface`** | Mehrere Entwürfe für dieselbe Schnittstelle nebeneinander, statt den erstbesten zu nehmen |
| **`prototype`**           | Wegwerf-Prototyp zur Validierung — bewusst ohne Prozess-Zeremonie                         |

## Beim Prüfen und Reparieren

| Skill                               | Wofür                                                                             |
| ----------------------------------- | --------------------------------------------------------------------------------- |
| **`review`**                        | Änderungen gegen Standards **und** Spezifikation prüfen, in parallelen Subagenten |
| **`diagnosing-bugs`**               | Strukturierte Diagnose-Schleife statt Rateversuchen                               |
| **`improve-codebase-architecture`** | Architektur-Schwachstellen scannen                                                |
| **`request-refactor-plan`**         | Einen Refactor in sichere Mini-Commits planen                                     |
| **`qa`**                            | Konversationelle Fehlermeldung → Issues                                           |
| **`resolving-merge-conflicts`**     | Bei laufendem Merge- oder Rebase-Konflikt                                         |

**Verhältnis zum Panel:** `review` **ersetzt das Panel nicht.** Es fährt mehrere
Subagenten desselben Anbieters gegen Standards und Spezifikation — wertvoll, aber
nicht unabhängig im Sinne des Panels. Das Panel lebt davon, dass Stimme 2 und 3
von _anderen_ Anbietern kommen und die blinde Erststimme den Bau-Kontext nicht
kennt. `review` ist eine gute Vorstufe, kein Ersatz.

## Sitzungswechsel und Orientierung

| Skill          | Wofür                                                                    |
| -------------- | ------------------------------------------------------------------------ |
| **`handoff`**  | Zwischenstand so übergeben, dass die nächste Sitzung weiterarbeiten kann |
| **`ask-matt`** | Router, wenn unklar ist, welcher Skill passt                             |

---

## Wie sie benutzt werden

Ein Teil der Skills wird vom Modell **selbst** gezogen, wenn die Aufgabe passt
(Grilling, Domänenmodell, TDD, Diagnose, Architektur, Review). Ein anderer Teil
wird **gerufen** — vom Menschen oder vom Hauptagenten, wenn er den Schritt
bewusst setzen will (`to-prd`, `to-issues`, `triage`, `prototype`,
`request-refactor-plan`, `qa`).

Die nützliche Haltung: **Skill beim Namen nennen und in einem Satz begründen,
warum er hier passt** — dann ist nachvollziehbar, welcher Methode ein Ergebnis
folgt, und ein falsch gewählter Skill fällt auf.

## Was Skills nicht sind

Sie ersetzen keine Regel aus `../../CLAUDE.md`. Ein Skill ist eine **Methode**;
der Prozess ist die **Verbindlichkeit**. `tdd` sagt, wie man test-first arbeitet
— dass jeder neue Test einen Rot-Beweis braucht, sagt der Bau-Brief. Wo beide
etwas zum selben Thema sagen, gilt der Prozess.
