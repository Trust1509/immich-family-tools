# Review-Panel: drei Stimmen über denselben Diff

Nach **jedem nicht-trivialen Slice**, vor dem Landen. Das Panel hat in der Praxis
jeden zweiten Erstbau gestoppt — nicht wegen Kleinigkeiten, sondern wegen Funden,
die in Produktion wehgetan hätten.

## Warum drei, und warum eine davon blind

**Stimme 1 — blinde Erststimme.** Ein _frischer_ Reviewer-Subagent, der **nur den
Diff und das Repo** bekommt: nicht den Bau-Brief, nicht den Bericht des Bauers,
nicht die Diskussion. Er darf Sonden fahren (Tests, eigene Messungen), aber nichts
ändern.

Das ist die wichtigste Regel des ganzen Verfahrens. Wer den Bau begleitet hat —
auch der Hauptagent — liest die **Absicht** statt des Codes. Die blinde Stimme
liefert deshalb überproportional die schwersten Funde: einen rekonstruierbaren
Kundennamen über die Sortierreihenfolge, einen gemessenen Datenverlust in einer
Migration, einen Testaufbau, der den eigenen Fix nie berührt.

**Stimme 2 — unabhängiges Modell** über denselben Diff. Bringt eine andere
Fehler-Intuition mit. Kennt den lokalen Arbeitsbaum nicht, arbeitet über einen
gepushten Review-Branch.

**Stimme 3 — günstige Drittstimme**, nur der Diff, kurze Antwort. Trifft seltener,
kostet fast nichts, und die Treffer sind echt.

## Ablauf

Die drei Stimmen dieses Setups, mit den konkreten Kommandos:

**Stimme 1 (blind):** frischer Reviewer-Subagent, bekommt **nur Diff + Repo-Pfad**,
nie den Bau-Brief.

**Stimme 2 (GPT über Codex-CLI):**

```bash
sh /c/Users/manue/.claude/Immich/model-panel/codex.sh exec --skip-git-repo-check --sandbox read-only -c 'model_reasoning_effort="high"' '<Prüfauftrag>'
```

Zwei Fallstricke, die real zwei Anläufe gekostet haben:

- **Muss aus dem zu prüfenden Arbeitsverzeichnis heraus laufen** — der Wrapper
  mountet das aktuelle Verzeichnis.
- **Ohne `--skip-git-repo-check` bricht sie ab**, wenn das Verzeichnis kein
  Git-Repo ist.

**Stimme 3 (DeepSeek, diff-only):**

```bash
python /c/Users/manue/.claude/Immich/model-panel/ask-api.py --model deepseek/deepseek-v4-pro --max-tokens 32768 --stdin-anhang '<Prüfauftrag>' < diff.patch
```

Ablauf in Reihenfolge:

```bash
# 1. Review-Branch pushen (die externen Stimmen brauchen ihn)
git push -f origin <commit>:refs/heads/review/<issue>-<kurzname>
```

**2. Alle drei parallel starten**, nicht nacheinander — sie brauchen zusammen
20–40 Minuten, sequenziell wäre das ein Vielfaches.

**3. Arbitrieren.** Jeden Blocker **am Code reproduzieren**. Prüfer-Konvergenz
ersetzt keine Reproduktion: Zwei Stimmen können denselben Fehler machen, und die
diff-only-Stimme liest gelegentlich die Vorher-Seite eines Diffs und meldet
einen längst gefixten Zustand.

**4. Nacharbeit** an denselben Subagenten, der gebaut hat (Kontext bleibt) — mit
dem, was **bestätigt** wurde, und mit ausdrücklich **abgeräumten** Fehlbefunden.

## Prüfaufträge, die sich bewährt haben

Nicht „prüfe den Diff", sondern **eine Behauptung zum Widerlegen**:

> Die Behauptung lautet: ⟨X⟩. Versuche das zu WIDERLEGEN. Denk an Umwege:
> ⟨konkrete Kandidaten⟩.

Dazu:

- **Nennen, was schon geprüft und ohne Befund ist** — sonst laufen alle drei
  dieselben Wege ab.
- **Ausdrücklich erlauben, nichts zu finden.** Sonst wird etwas erfunden.
- **Je Fund: Schwere, Datei:Zeile, Nachweis.** Kein Nachweis, kein Fund.
- Abschluss: **ein Satz Gesamturteil** (landen ja/nein).

## Fragen, die überdurchschnittlich oft etwas finden

- „Wer ruft den geänderten Code auf? Prüfe **jeden** Aufrufer."
- „Bricht die neue Strenge einen legitimen Ablauf?"
- „Ist der Wächter wirklich schärfer, oder wurde er anderswo aufgeweicht?"
- „Welche einzelne Zeile könnte ich löschen, ohne dass ein Test rot wird?"
- „Enthalten die Testdaten den Fall überhaupt, um den es geht?"
- „Gibt es einen Rückkanal — Fehlermeldungen, Reihenfolge, Zähler, Timing?"

## Der Panel-Kommentar hat eine feste Form

Das Ergebnis wird als Kommentar am Issue festgehalten — **immer in dieser
Gliederung**, eine Überschrift je Stimme, auch wenn eine Stimme nichts gefunden
hat:

```markdown
## Panel ⟨Slice⟩

### Stimme 1 — blinde Erststimme

### Stimme 2 — unabhängiges Modell

### Stimme 3 — Drittstimme (diff-only)

### Arbitrierung

⟨je Fund: reproduziert / verworfen, und von welcher Stimme er kam⟩
```

**Warum so streng:** Ein Panel-Ergebnis in Fließtext zeigt nicht, **wer**
gesprochen hat. Es liest sich vollständig, egal ob drei Stimmen geprüft haben
oder zwei — das Fehlen ist keine sichtbare Lücke, sondern eine unsichtbare.
Genau das ist in einem laufenden Projekt passiert: dass über mehrere Slices nur
zweistimmig geprüft worden war, fiel erst später auf, und nicht am
Panel-Ergebnis. Drei Überschriften drehen das um — eine leere Überschrift
springt ins Auge, ein fehlender Absatz nicht.

Deshalb: **Fällt eine Stimme aus, steht unter ihrer Überschrift der Grund** —
„kein Guthaben, Owner informiert am ⟨Datum⟩" — und nie einfach nichts. Ein Slice
ohne vollständiges oder ausdrücklich vermerkt-verkürztes Panel gilt als **nicht
geprüft** und wird nicht ausgeliefert.

## Wenn eine Stimme ausfällt

Werkzeug nicht verfügbar, kein Guthaben, Dienst down: **mit zweien weitermachen
und es dem Owner sagen.** Nicht stillschweigend reduzieren — und die fehlende
Stimme nachholen, solange der Slice noch nicht ausgeliefert ist. Genau so wurde
einmal ein Seitenkanal gefunden, den die anderen beiden übersehen hatten.

## Verhältnismäßigkeit

Nicht jeder Slice braucht drei Stimmen. Eine Änderung an der Testinfrastruktur,
eine Doku-Korrektur, ein Ein-Zeilen-Fix mit offensichtlichem Test: eigene
Prüfung reicht. **Immer volles Panel** bei: Datenmigrationen, Datenschutz- und
Berechtigungslogik, allem was Geld oder Steuern berührt, und allem, was über eine
Schnittstelle nach außen geht.

In diesem Repo dürfen zusätzlich **Konfigurations- und Doku-Slices** ohne volles
Panel landen — die Reduktion wird dann im Issue vermerkt, nicht stillschweigend
angewandt.
