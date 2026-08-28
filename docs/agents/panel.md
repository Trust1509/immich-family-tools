# Review-Panel: drei Stimmen über denselben Diff

Nach **jedem Slice mit Klasse R2 oder höher** (siehe `CLAUDE.md`, „Risikoklasse
je Slice"), vor dem Landen. Das Panel hat in der Praxis
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

### PII-Grenze

Stimme 2 (GPT über Codex) und Stimme 3 (DeepSeek über API) sind **fremde
Dienste**. Gesichts- und Personendaten aus den Immich-Fotobeständen — Namen,
die aus einem Gesichtserkennungs-Match stammen, e-Mail-Adressen echter Nutzer,
alles, was eine reale Person identifiziert — sind PII und gehen **nie** in
einem Diff an eine dieser beiden Stimmen. Erlaubt sind nur Code und **erfundene**
Fixtures (siehe `bau-brief.md`, Abschnitt „Fixtures werden erfunden"). Das ist
hier keine Theorie: Ein Personenname aus der Gesichtserkennung könnte über
Testdaten oder ein Log-Beispiel unbemerkt in einen Diff geraten, der dann an
Stimme 2 oder 3 geht.

Praktisch heißt das: Vor dem Push des Review-Zweigs (Stimme 2) und vor dem
Zusammenstellen des Diffs für Stimme 3 **den Diff selbst gegen diese Klasse
lesen** — nicht nur den Code, der ihn erzeugt hat. Im Zweifelsfall (ein
Fixture-Wert könnte ein echter Treffer sein): nicht schicken, sondern die
Stimme mit einem anonymisierten Ersatzwert im Diff weglassen oder auf die
zweite blinde Claude-Repo-Stimme (siehe „Verfahren je Risikoklasse", R3)
ausweichen — die bleibt lokal und verlässt den eigenen Agenten-Kontext nie.

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

**Klumpenrisiko bei R3:** Seit der Zweitblind-Regel hängen zwei von drei
Stimmen am selben Kontingent. Drei Antworten darauf:

1. Bei knappem Kontingent laufen die beiden Claude-Stimmen ZUERST, die
   Fremdstimmen danach.
2. **Ersatzregel:** Fällt die Zweitblind-Stimme am Kontingent, übernimmt die
   GPT-Stimme die adversariale Rahmung in einem zweiten Lauf **mit vollem
   Quelltext-Zugriff**. Die Regel schreibt das ERGEBNIS vor, nicht den
   Transport — Review-Branch, Commit-Snapshot oder Quelltext inline sind
   gleichwertig, solange die Quelle `git show HEAD:`-Stand ist (Quellen-Regel
   gilt unverändert). Real belegt: In einer Sandbox ohne Datei-Zugriff trug
   die Inline-Variante den einzigen echten Treffer der Runde. Teurer, aber
   definiert statt improvisiert. **Bei uns gilt dazu ausdrücklich:** Der
   Transport „Quelltext inline" schickt Quelltext an die GPT-Stimme, also an
   einen fremden Dienst — die PII-Grenze oben gilt für diesen Transport
   unverändert weiter. Diese Ersatzregel ist eine Aussage über den Transport,
   keine Ausnahme von der PII-Grenze.
3. Die bestehende Regel „Panel nie auf den letzten Moment" wiegt bei R3
   doppelt.

Bei uns ist das Klumpenrisiko nicht theoretisch: Unsere R3-Besetzung ist seit
v1.11.3 blinde Erststimme + GPT-Stimme + zweite blinde Claude-Repo-Stimme
(siehe „Verfahren je Risikoklasse" unten) — auch bei uns hängen zwei von drei
Stimmen am selben Claude-Kontingent.

Werkzeug nicht verfügbar, kein Guthaben, Dienst down: **mit zweien weitermachen
und es dem Owner sagen.** Nicht stillschweigend reduzieren — und die fehlende
Stimme nachholen, solange der Slice noch nicht ausgeliefert ist. Genau so wurde
einmal ein Seitenkanal gefunden, den die anderen beiden übersehen hatten.

## Verfahren je Risikoklasse

**Die Auslöser-Tabelle besitzt `../../CLAUDE.md`** — dort wird entschieden,
welche Klasse ein Slice hat. Diese Datei wiederholt die Schwelle nicht, um
Doppelpflege zu vermeiden; eine Schwelle hat genau einen Eigentümer. Hier
steht nur, was je Klasse zu tun ist:

- **R0** — lokale Gates genügen. Kein Panel-Kommentar nötig; der Commit nennt
  den R0-Auslöser. Konfigurations- und Doku-Slices ohne Verhaltensänderung
  fallen hierunter.
- **R2** (Normalfall) — blinde Erststimme + unabhängige Zweitstimme (Stimme 2),
  fester Panel-Kommentar. Die Drittstimme ist bei R2 optional (ihr gemessenes
  Profil: Konvergenz-Lieferant, kaum exklusive Funde); wird sie weggelassen,
  steht der Grund unter ihrer Überschrift.
  _Verkürzung „R1":_ Nacharbeit mit ausschließlich mechanischen Auflagen darf
  mit der blinden Erststimme allein geprüft werden — Begründung unter den
  Überschriften der ausgelassenen Stimmen.
- **R3** — volles Panel **plus eine risikospezifische Probe durch die echte
  Tür** (Datenerhalt-Probe für die JSON-Migration, Berechtigungs-Sonde,
  Schnittstellen-Aufruf von außen — je nach Auslöser). **Stimme 3 wird bei R3
  durch eine zweite blinde Claude-Repo-Stimme ersetzt** — ein zweiter frischer
  Subagent mit vollem Repo-Zugriff wie Stimme 1, aber **adversarial gerahmt**:
  Sein Auftrag lautet ausdrücklich, den Befund der ersten blinden Stimme zu
  **widerlegen**, nicht zu bestätigen. Grund: R3-Auslöser sind die Fälle mit
  dem größten Schaden bei Fehleinschätzung — dort zählt Repo-Kontext mehr als
  eine dritte, aber blinde Meinung, und die PII-Grenze oben schließt ohnehin
  aus, einen R3-Diff (typischerweise die JSON-Migration oder Personendaten-Pfade)
  an die günstige Fremdstimme zu schicken.
- **R4** — wie R3, und der Slice landet erst nach ausdrücklicher
  Owner-Freigabe. Version/Release bleiben bis dahin unangetastet.

Beispiel für Fremdcode als R3-Auslöser: Ein zugelieferter Zweig war fachlich
unauffällig, tauschte aber einen dokumentierten Endpunkt gegen einen
ausdrücklich undokumentierten; alle mitgelieferten Tests waren grün — sie
stammten vom selben Autor und prüften dessen Annahme. Fremdcode ist ein Risiko
eigener Art, unabhängig vom Thema — **nicht** der eigene Bau-Subagent, siehe
Tabelle in `CLAUDE.md`. (Der Fall stammt aus diesem Projekt und wurde als
Vorlagen-Issue #2 zurückgemeldet.)
