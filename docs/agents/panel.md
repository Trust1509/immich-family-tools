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

**Stimme 3 — günstige Drittstimme**, nur der Diff, kurze Antwort. Kostet fast
nichts. **Erwartung realistisch halten** (Messreihe über fünf Projekte): ein
exklusiver bestätigter Fund insgesamt, dem rund ein Dutzend Fehl- und
Überbefunde gegenüberstehen, zweimal aktiv irreführend zur Kernfrage. Der Grund
ist strukturell: **Die schweren Funde liegen in der Beziehung zwischen Diff und
Umgebung** — ein Bezeichner, der in einer nicht mitgelieferten Datei anders
lautet; eine Zusicherung in einer Datei, die der Diff nicht berührt. Diese
Klasse ist diff-only **prinzipiell** unsichtbar.

Daraus drei Regeln:

- **Sie zählt mit ihren FUNDEN, nie mit ihrer Freigabe.** Ein „landen" von einer
  Stimme, die nichts prüfen konnte, ist kein Gegengewicht zu einem Blocker —
  sonst steht im Panel-Kommentar eine dritte Überschrift, die wie eine zweite
  Meinung aussieht und keine ist.
- **Große Diffs schneiden.** Auf einem 85-KB-Diff wurde alles widerlegt, auf
  27 KB war dieselbe Stimme scharf.
- **Bei reinen Konfigurations-Diffs ohne Logik nicht einsetzen.** Dort produziert
  sie Inversionen, weil sie nichts hat, woran sie sich prüfen könnte — real
  behauptete sie exakt die Umkehrung des Sachverhalts.

Behalten lohnt trotzdem: Sie liefert **Konvergenz**, die einen Fund von einer
Meinung unterscheidet, und kostet Bruchteile eines Cents.

## Ablauf

**Schritt 0 — Erreichbarkeit der externen Stimmen vor dem Start prüfen**, nicht
mittendrin. Stimme 2 braucht ein lauffähiges `codex.sh` und den gepushten
Review-Zweig; Stimme 3 braucht Guthaben hinter `ask-api.py`. Beide Ausfälle
melden sich sonst erst, wenn der Slice schon als „gleich fertig" gilt.

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

**4. Nacharbeit** nach `bau-brief.md` — mit dem, was **bestätigt** wurde, und mit
ausdrücklich **abgeräumten** Fehlbefunden. Wer sie baut (derselbe Bauer oder ein
frischer), entscheidet die **Art der Auflage**, nicht eine Vorliebe — siehe
`bau-brief.md`, Abschnitt „Der Nacharbeits-Brief ist ein Bau-Brief".

**Die Regel hängt am GELANDETEN ZUSTAND, nicht am Slice.** Was am Ende auf dem
Hauptzweig liegt, ist geprüft — egal in wie vielen Anläufen es dorthin kam.
Damit ist Nacharbeit automatisch erfasst, ohne eine zweite Regel. Zwei Projekte
haben das Panel bei der Nacharbeit weggelassen mit der Begründung „setzt nur
bestätigte Befunde um"; beide Male entstand der neue Defekt genau dort. Eine
verkürzte zweite Runde (nur die blinde Stimme, zugeschnittener Auftrag) reicht —
in einem Fall fand sie sechs weitere Punkte, alle exklusiv.

## Arbitrieren: die Sonde, die verwirft, braucht den stärkeren Nachweis

Ein bestätigter Fund wird gefixt und nachgeprüft. Ein **verworfener verschwindet
für immer** — niemand sieht ihn je wieder an. Die Ad-hoc-Sonde des Arbiters ist
damit die gefährlichste Prüfung im ganzen Verfahren, und sie hatte bisher kein
Gegenstück zum Rot-Beweis.

Zweimal an einem Tag geschehen: Die Sonde prüfte die **bestätigende** statt der
widerlegenden Richtung, war technisch korrekt, grün — und die Schlussfolgerung
falsch. Einmal hätte das den schwersten Fund des Tages abgeräumt.

**Vor dem Verwerfen die Gegenfrage stellen: „Welche Eingabe würde der Stimme
recht geben?"** Wer sie nicht beantworten kann, hat nicht widerlegt, sondern
nicht reproduziert. Erwartungswerte VOR der Sonde festlegen — eine Sonde kann
ihre eigenen Befunde erzeugen.

**Drei Urteile statt zwei.** Zwischen „bestätigt" und „Fehlbefund" fehlt der
häufigste Fall:

- **bestätigt** — reproduziert, kommt in die Nacharbeit
- **richtiger Instinkt, falsche Begründung** — die Stimme zeigt auf eine echte
  Stelle und begründet sie falsch. **Der Fund bleibt**, die Begründung wird
  ersetzt. Ohne diese Kategorie wurden in einem Projekt zwei echte Befunde als
  Fehlbefunde abgeräumt.
- **widerlegt** — mit Nachweis, und mit beantworteter Gegenfrage oben.

**Schwere-Umstufung ist erlaubt und wird gekennzeichnet.** Der Arbiter darf hoch-
und herunterstufen (die Konsumenten-Frage macht aus einem Anzeigefehler regelmäßig
einen Schreibpfad-Fehler). Die Umstufung wird im Panel-Kommentar als solche
markiert, z. B. `P2 → P1 (arb.)`, sonst ist sie stille Meinung.

**Widersprechen sich zwei Stimmen, entscheidet die Reproduktion**, nicht die
Mehrheit und nicht die Plausibilität der Begründung.

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

Nicht jeder Slice braucht drei Stimmen. Welche Fälle ohne Panel landen dürfen
(abschließende Liste) und wann immer das volle Panel gilt — einschließlich
Herkunft — steht in `CLAUDE.md`, Abschnitt „Review-Panel". Diese Datei
wiederholt die Schwelle nicht, um Doppelpflege zu vermeiden; eine Schwelle hat
genau einen Eigentümer.

Der Grund für die Geschlossenheit der Trivial-Liste: „Ist das trivial?" ist
genau der Punkt, an dem der Ausführende unter Zeitdruck sich selbst freispricht.
Eine Aufzählung, die sich als Beispiel liest, macht mit der Zeit jeden Slice
trivial.

Beispiel für Herkunft als Pflichtfall: Ein zugelieferter Zweig war fachlich
unauffällig, tauschte aber einen dokumentierten Endpunkt gegen einen
ausdrücklich undokumentierten; alle mitgelieferten Tests waren grün — sie
stammten vom selben Autor und prüften dessen Annahme. Herkunft ist ein Risiko
eigener Art, unabhängig vom Thema. (Der Fall stammt aus diesem Projekt und
wurde als Vorlagen-Issue #2 zurückgemeldet.)

In diesem Repo fallen **Konfigurations- und Doku-Slices ohne Verhaltensänderung**
unter die Doku-Korrektur-Ausnahme aus `CLAUDE.md` bzw. sinngemäß unter reine
Testinfrastruktur — das ist eine Konkretisierung der dortigen Liste, keine
zusätzliche Ausnahme. Ändert ein Konfigurations-Slice sichtbares Verhalten,
gehört er nicht mehr hierher. Die Reduktion wird im Issue vermerkt, nicht
stillschweigend angewandt.
