# Skills: was der Prozess voraussetzt

Der Ablauf in `../../CLAUDE.md` (Abschnitt „Arbeitsweise") benennt Schritte —
Grillen, Zerlegen, Bauen, Prüfen. Für die meisten davon gibt es fertige
**Skills**: abrufbare Anleitungen, die der Agent lädt und befolgt, statt die
Methode jedes Mal neu zu erfinden.

**Woher:** [`mattpocock/skills`](https://github.com/mattpocock/skills).

**Gemessen am 03.11.2026 auf dem Entwicklungsrechner** — und das Ergebnis weicht
von der Vorlage ab, deshalb steht es hier und nicht ihr Text:

```bash
ls -1 "$HOME/.claude/skills/" | wc -l     # 36
```

Installiert ist **Weg B** (editierbare Kopien), und zwar ein Stand VOR der
Umbenennungswelle im Quell-Repo. Die Vorlage v1.19.1 prüfte ihre Namen gegen
Plugin `mattpocock-skills` 1.3.1 (Commit `49dd158`, 09.10.2026) und führt dort
acht Namen, die es hier **nicht** gibt:

| Vorlagen-Name    | hier                                   |
| ---------------- | -------------------------------------- |
| `to-spec`        | fehlt — hier heißt er noch `to-prd`    |
| `to-tickets`     | fehlt — hier heißt er noch `to-issues` |
| `code-review`    | fehlt — hier heißt er noch `review`    |
| `research`       | fehlt                                  |
| `wayfinder`      | fehlt                                  |
| `pr`             | fehlt                                  |
| `retro`          | fehlt                                  |
| `implement-spec` | fehlt — hier gibt es nur `implement`   |

Umgekehrt liegen hier fünf Skills, die das Quell-Repo laut Vorlage nicht mehr
führt: `design-an-interface`, `qa`, `request-refactor-plan`,
`resolving-merge-conflicts`, `decision-mapping`. Und `ubiquitous-language` liegt
hier noch separat, obwohl er upstream in `domain-modeling` aufgegangen ist.

**Die Liste unten nennt deshalb die Namen, die auf DIESEM Rechner existieren**,
mit dem Vorlagen-Namen in Klammern, wo er abweicht. Das ist die Anwendung der
Regel „Nur empfehlen, was existiert" auf die Vorlage selbst: Ihre Namensliste
ist für dieses Projekt eine Behauptung über eine fremde Umgebung, und sie ist
hier gemessen falsch.

**Folge für den Owner, außerhalb dieses Repos:** Die globale
`~/.claude/CLAUDE.md` nennt `/to-prd`, `/to-issues` und `ubiquitous-language`.
Diese drei liegen auf diesem Rechner und funktionieren heute — auf einem
frischen Rechner und in jeder Cloud-Sitzung laufen sie ins Leere. Geändert wird
das nicht von hier aus: Die globale Datei hält persönliche Arbeitsweisen und
wird **nicht** ins Repo kopiert (Vorlagen-Entscheid 2026-10-17); eine Kopie je
Repo liefe auseinander.

Zwei Installationswege, **einen** wählen — beide bedeuten jeden Skill doppelt:

```bash
# Weg A: als Plugin (verwaltetes Bündel, Aktualisierungen kommen automatisch)
claude plugin marketplace add mattpocock/skills
claude plugin install mattpocock-skills@mattpocock

# Weg B: als editierbare Kopien (auswählbar, liegen offen) — hier installiert
npx skills@latest add mattpocock/skills
```

Weg A braucht zuerst den Marktplatz: `claude plugins install mattpocock-skills`
allein scheiterte in einer frischen Umgebung mit „not found in any configured
marketplace" (von der Vorlage gemessen, hier nicht nachgeprüft — Weg A ist hier
nicht installiert). Bei Weg B fragt der Installer, welche Skills mitkommen —
**`setup-matt-pocock-skills` muss dabei sein**, der richtet neue Repos für die
übrigen ein.

**Wichtig — Skills liegen pro RECHNER, nicht pro Repo, und nicht pro Sitzung.**
Sie werden global installiert (hier unter `~/.claude/skills/`) und gelten dann
für alle Projekte auf diesem Rechner. Ein frisch geklontes Repo bringt sie
**nicht** mit. Auf einem neuen Rechner sind sie einmal einzurichten, sonst
laufen Verweise ins Leere — auch der in `triage-labels.md`.

**Cloud-Sitzungen haben kein `~/.claude` des Owners.** Eine Sitzung in der Cloud
startet jedes Mal in einem frischen Container. Dort fehlen still, ohne
Fehlermeldung: alle Skills, die globale `~/.claude/CLAUDE.md`, die
Panel-Werkzeuge außerhalb des Repos und ein Prod-Wächter. Deshalb:

- Die beiden Kommandos von Weg A gehören ins **Setup-Skript der
  Cloud-Umgebung**. Achtung: Weg A bringt die **neuen** Namen aus der Tabelle
  oben mit, nicht die hier installierten — ein Auftrag, der `/to-prd` nennt,
  läuft dort ins Leere, und einer, der `/to-spec` nennt, läuft hier ins Leere.
  Wer beides bedienen muss, nennt den Schritt statt des Skills.
- Ein R3-Panel ist in einer Cloud-Sitzung nur vollständig, wenn das Werkzeug des
  Fremdprüfers und sein Schlüssel dort bereitstehen. Sonst ist das ein
  vermerkter **Ausfall** der Stimme, keine stille Verkürzung (`panel.md`, „Wenn
  eine Stimme ausfällt").
- Was das Projekt in jeder Umgebung braucht, gehört in die Projekt-`CLAUDE.md`,
  nicht nach `~/.claude`.

**Nur empfehlen, was existiert.** Bevor ein Skill in einem Auftrag genannt wird:
nachsehen, ob er auf diesem Rechner — bzw. in dieser Sitzung — wirklich
vorhanden ist. Erfundene oder veraltete Skill-Namen sind eine teure Art, Zeit zu
verlieren. Die Tabelle oben ist der Beleg, dass das keine Vorsichtsregel ist:
Acht Namen aus einer geprüften Vorlagenfassung existieren hier nicht.

**Liste prüfen — bei jedem Abgleich, weil das Quell-Repo sich bewegt.** Die
Namen dieser Datei gegen beides halten: den Rechner (`ls ~/.claude/skills/`) und
das Quell-Repo. Bei einer Abweichung den **Inhalt** vergleichen, nicht nur den
Namen:

```bash
gh api repos/mattpocock/skills/contents/.claude-plugin/plugin.json --jq .content | base64 -d
```

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

| Skill                     | Wofür                                                                                                                                                              |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **`grilling`**            | Die Idee im Verhör scharf stellen — Fragen einzeln, mit Empfehlung, bis die Spezifikation baubar ist                                                               |
| **`grill-with-docs`**     | Dasselbe, aber mit abgestimmter Planung und Domänenmodell — die gründlichere Variante für größere Vorhaben                                                         |
| **`grill-me`**            | Umgekehrte Richtung: der Agent grillt **dich**, wenn du selbst noch nicht weißt, was du willst                                                                     |
| **`domain-modeling`**     | Die zentralen Begriffe und ihre Invarianten festklopfen. Upstream ist `ubiquitous-language` hierin aufgegangen (Glossar und ADRs); hier liegen beide noch getrennt |
| **`ubiquitous-language`** | Ein Glossar, das Code, Doku und Gespräch dieselben Wörter benutzen lässt. Upstream entfallen, hier vorhanden                                                       |
| **`decision-mapping`**    | Entscheidungen mit Alternativen und Konsequenzen sichtbar machen, statt sie im Chat zu verlieren. Upstream entfallen, hier vorhanden                               |

## Von der Spezifikation zur Arbeit

| Skill           | Wofür                                                                                                             |
| --------------- | ----------------------------------------------------------------------------------------------------------------- |
| **`to-prd`**    | Aus der Grilling-Diskussion ein Anforderungsdokument synthetisieren. Upstream `to-spec` — hier nicht installiert  |
| **`to-issues`** | Die Spezifikation in **vertikale Slices** zerlegen — je ein Issue. Upstream `to-tickets` — hier nicht installiert |
| **`triage`**    | Issue-Status pflegen (die fünf Rollen aus `triage-labels.md`)                                                     |

## Fundament und Leitplanken

| Skill                            | Wofür                                                                                                                           |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **`setup-pre-commit`**           | Prüfungen beim Commit statt beim Ärgernis                                                                                       |
| **`git-guardrails-claude-code`** | Hooks gegen gefährliche Git-Befehle. **Zuschnitt prüfen:** Wer bewusst direkt auf den Hauptzweig pusht, muss das erlaubt lassen |

## Beim Bauen

| Skill                     | Wofür                                                                                                                         |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **`tdd`**                 | Test zuerst, rot-grün-refaktorieren — passt zur Rot-Beweis-Pflicht aus dem Bau-Brief                                          |
| **`implement`**           | Einen abgestimmten Plan abarbeiten. Upstream gibt es daneben `implement-spec`, hier nicht installiert                         |
| **`codebase-design`**     | Modulschnitt und tiefe Schnittstellen                                                                                         |
| **`design-an-interface`** | Mehrere Entwürfe für dieselbe Schnittstelle nebeneinander, statt den erstbesten zu nehmen. Upstream entfallen, hier vorhanden |
| **`prototype`**           | Wegwerf-Prototyp zur Validierung — bewusst ohne Prozess-Zeremonie                                                             |

## Beim Prüfen und Reparieren

| Skill                               | Wofür                                                                                                                              |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **`review`**                        | Änderungen gegen Standards **und** Spezifikation prüfen, in parallelen Subagenten. Upstream `code-review` — hier nicht installiert |
| **`diagnosing-bugs`**               | Strukturierte Diagnose-Schleife statt Rateversuchen                                                                                |
| **`improve-codebase-architecture`** | Architektur-Schwachstellen scannen                                                                                                 |
| **`request-refactor-plan`**         | Einen Refactor in sichere Mini-Commits planen. Upstream entfallen, hier vorhanden                                                  |
| **`qa`**                            | Konversationelle Fehlermeldung → Issues. Upstream entfallen, hier vorhanden                                                        |
| **`resolving-merge-conflicts`**     | Bei laufendem Merge- oder Rebase-Konflikt. Upstream entfallen, hier vorhanden                                                      |

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
