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

**Was die diff-only-Stimme kann, und warum sie nicht bloß die billige ist:**
Ihre Stärke ist die **Struktur der Regel**, nicht der Einzelfall. Gemessen: In
einem Datenschutz-Slice sagte sie als einzige „nicht landen" — die
Redigierungsgrenze war als Negativliste gebaut („keine Ausnahme eingetragen,
also veröffentlichbar"). Beide Repo-Stimmen hatten denselben Punkt gesehen und
zum Hinweis abgestuft, weil sie **gemessen** hatten, dass heute kein solcher
Fall erreichbar ist. Beide Einschätzungen waren korrekt — aber „heute nicht
erreichbar" ist kein Argument gegen eine Regel, die morgen halten muss, und der
Umbau auf eine Positivliste war zehn Zeilen.

**Daraus die Arbitrierungs-Regel:** Stuft eine Repo-Stimme einen STRUKTURELLEN
Befund mit „aktuell nicht erreichbar" ab, ist das begründungspflichtig — wer
garantiert, dass es so bleibt? Das ist die Umkehrung der üblichen Richtung:
Sonst gewinnt die Messung immer, und genau die Messung, die die Repo-Stimmen
stark macht, macht sie hier milder.

**Stimme 3 — abhängig von der Risikoklasse.** Bei R2 (wenn besetzt): die
günstige diff-only-Fremdstimme, nur der Diff, kurze Antwort, kostet fast
nichts. **Bei R3: eine zweite blinde Claude-Repo-Stimme mit adversarialer
Rahmung** — Begründung und Beleg unter „Verfahren je Risikoklasse". Zur
diff-only-Stimme: **Erwartung realistisch halten** (Messreihe über fünf
Projekte): ein exklusiver bestätigter Fund insgesamt, dem rund ein Dutzend
Fehl- und Überbefunde gegenüberstehen, zweimal aktiv irreführend zur
Kernfrage.

Der Grund ist strukturell, nicht modellabhängig: **Die schweren Funde liegen
in der Beziehung zwischen Diff und Umgebung** — ein Bezeichner, der in einer
nicht mitgelieferten Datei anders lautet; eine Zusicherung in einer Datei, die
der Diff nicht berührt. Diese Klasse ist diff-only **prinzipiell** unsichtbar.

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

## Der Fragetyp bestimmt, was ein Panel wert ist

Der stärkste Zahlenbefund der Messreihe betrifft nicht die Stimmen, sondern die
Frage: Bei Annahmen über **fremde Systeme** (eine API, ein SDK, ein Dienst) waren
3 von 4 schweren Funden falsch; bei **eigener Semantik** 5 von 7 richtig.

Modelle beurteilen eigenen Code zuverlässig und fremde Systeme nicht — **und
Konvergenz hilft dort nicht**, weil zwei Stimmen denselben veralteten Quellstand
heranziehen. Geht es um ein fremdes System, ersetzt die Primärquelle das Panel
nicht, sondern geht ihm voraus.

## Die Stimmen einrichten

Auf diesem Rechner bereits eingerichtet — hier die konkreten Kommandos für
dieses Projekt, damit sie kopierbar bleiben.

### Stimme 1 — blinde Erststimme

**Woher:** aus der Agenten-CLI selbst, die ohnehin benutzt wird. Kein Konto,
keine Kosten, keine Installation.

**Aufsetzen:** frischer Reviewer-Subagent, bekommt **nur Diff + Repo-Pfad**,
nie den Bau-Brief, nie den Bericht des Bauers. Ein zweites Fenster derselben
Sitzung ist **kein** Ersatz — es sieht die Historie.

### Stimme 2 (GPT über Codex-CLI) — unabhängiges Modell mit Repo-Zugriff

```bash
sh /c/Users/manue/.claude/Immich/model-panel/codex.sh exec --skip-git-repo-check --sandbox read-only -c 'model_reasoning_effort="high"' '<Prüfauftrag>'
```

Kennt den lokalen Arbeitsbaum nicht — sie braucht den gepushten Review-Zweig.
**Ihr Prüfauftrag schließt den Abgleich Commit gegen Bau-Brief ein:** Sie
erreicht den Brief (Issue-Kommentar) unabhängig vom Arbeitsbaum des
Hauptagenten — anders als die blinde Erststimme, die den Brief nie bekommt
(siehe `bau-brief.md`, Abschnitt „Ablage").

Zwei Fallstricke, die real zwei Anläufe gekostet haben:

- **Muss aus dem zu prüfenden Arbeitsverzeichnis heraus laufen** — der Wrapper
  mountet das aktuelle Verzeichnis.
- **Ohne `--skip-git-repo-check` bricht sie ab**, wenn das Verzeichnis kein
  Git-Repo ist.

### Stimme 3 (DeepSeek über API, R2-Besetzung) — günstige diff-only-Stimme

```bash
python /c/Users/manue/.claude/Immich/model-panel/ask-api.py --model deepseek/deepseek-v4-pro --max-tokens 32768 --stdin-anhang '<Prüfauftrag>' < diff.patch
```

Bei R3 ersetzt durch eine zweite blinde Claude-Repo-Stimme mit adversarialer
Rahmung, keine diff-only-Fremdstimme — siehe „Verfahren je Risikoklasse".

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

```bash
# 1. Review-Branch pushen (die externen Stimmen brauchen ihn)
git push -f origin <commit>:refs/heads/review/<issue>-<kurzname>
```

**Schritt 0 — Erreichbarkeit der externen Stimmen vor dem Start prüfen**, nicht
mittendrin — Kommandos und Fallstricke siehe „Die Stimmen einrichten" oben,
Hintergrund (Sitzungslimits, Puffer vor dem Release) siehe „Verfügbarkeit ist
Teil der Planung" unten. Beide Ausfälle melden sich sonst erst, wenn der Slice
schon als „gleich fertig" gilt.

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

**Auch eine Text-Suche mit null Treffern ist so eine Sonde** — sie verwirft die
Aussage eines anderen. Zwei gemessene Wege, auf denen sie falsch verwirft:
grep arbeitet zeilenweise, eine Wortgruppe über einem Prosa-Umbruch liefert
null Treffer, obwohl der Satz dasteht; und ohne `-i` verfehlt „Synthese" das
„SYNTHESE" im Text. Beides hätte beinahe einen KORREKTEN Bauer-Bericht als
Fehlbefund abgeräumt. Bevor eine Null-Treffer-Suche etwas verwirft:
**`LC_ALL=C.UTF-8` voranstellen**, `-i` setzen und das **seltenste Einzelwort**
suchen — ein Einzelwort kann nicht umbrochen werden. Ohne die Locale faltet
`-i` keine Umlaute, und die Sonde verwirft dann einen korrekten Befund mit
einer Zahl, die nach Beweis aussieht.

**Beleg (Vorlagen-CHANGELOG v1.12.3, nicht dieses Projekt — Korrektur der
Brief-Prämisse):** Der Vorfall stammt aus der Vorlage selbst, gemeldet von P4:
Zweimal wollte dort ein Arbiter eine Bauer-Aussage nachprüfen, bekam null
Treffer und hätte beinahe einen KORREKTEN Bericht als Fehlbefund verworfen —
einmal wegen fehlender Groß-/Kleinschreibung, einmal wegen eines
Zeilenumbruchs mitten in der gesuchten Wortgruppe. Für uns ist die Regel
präventiv übernommen, ohne eigenen Vorfall dieser Art.

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

### Stimme 3 — ⟨R2: Drittstimme (diff-only) / R3: zweite blinde Repo-Stimme (adversarial)⟩

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

## Eine Stimme bewusst weglassen — erlaubt, wenn begründet

„Nie stillschweigend reduzieren" heißt nicht „nie reduzieren". Ein Projekt hat
in zwei Nacharbeits-Runden die Stimmen 2 und 3 **nicht** eingesetzt und das im
Panel-Kommentar begründet: Der Gegenstand war Sitzungs- und
Transaktionsverhalten über vier Aufrufe — also die Beziehung zwischen Diff und
Umgebung, für diff-only prinzipiell unsichtbar, und kein Feld, in dem die zweite
Stimme in der Erstrunde stark gewesen war.

Das ist die richtige Anwendung: **Die Begründung steht unter der Überschrift der
Stimme, nicht die Auslassung.** Wer eine Stimme weglässt, weil sie am Gegenstand
nichts leisten kann, trifft eine Entscheidung; wer sie weglässt, ohne es zu
sagen, verliert sie.

## Verfügbarkeit ist Teil der Planung

**Ein Panel, das an einem fremden Limit hängt, ist keine verlässlich verfügbare
Prüfung.** Gemessen: Zwei Subagenten starben an Sitzungslimits — einer mitten im
Rot-Beweis (die Sabotage stand danach zwei Tage im Code), einer mitten im Panel
(eine komplette Runde musste wiederholt werden).

Verkraftbar war das nur, weil nichts ausgeliefert war. **Wer zwischen Panel und
Release wenig Puffer hat, plant das Panel nicht auf den letzten Moment** — und
behandelt einen abgebrochenen Prüflauf wie einen abgebrochenen Bau: erst
Zustand feststellen, dann fortsetzen.

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
   gilt unverändert). **Die Ersatzregel ist eine Aussage über den Transport,
   keine Ausnahme von der PII-Grenze:** Was einer Fremdstimme nicht gegeben
   werden darf, darf ihr auch inline nicht gegeben werden — wer nur eine der
   beiden Regeln liest, darf sie nicht als Aufhebung der anderen lesen können.
   Real belegt: In einer Sandbox ohne Datei-Zugriff trug die Inline-Variante
   den einzigen echten Treffer der Runde. Teurer, aber definiert statt
   improvisiert.
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
  _Verkürzung „R1":_ Auslöser und Mindestprüfung stehen in der Tabelle
  (`../../CLAUDE.md`, Zeile _R1_) — hier nur das Verfahrens-Detail: Die
  Begründung der Verkürzung steht unter den Überschriften der ausgelassenen
  Stimmen, nicht als Fließtext.
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

## Stimmen-Besetzung nach Diff-Typ

Der Panel-UMFANG folgt der Risikoklasse; die STIMMEN-BESETZUNG folgt dem
Diff-Typ. Gemessen über sieben Slices in zwei Projekten:

- **Backend-Logik** — Zweit- und Drittstimme tragen (exklusive Funde,
  unabhängige Konvergenz). Volle Besetzung nach Klasse.
- **Frontend/Anzeige-Text** — die blinde Erststimme ist die einzige tragend
  gemessene Stimme (drei exklusive Funde bei einem „nur Labels"-Diff) und
  genügt allein; diff-only-Fremdstimmen sind hier nachweislich stumm.

Wer von der Klassen-Besetzung nach Diff-Typ abweicht, schreibt den Diff-Typ
und den Grund unter die Überschrift der ausgelassenen Stimme — und nennt
beides in der Bilanz, damit die Messreihe weiterwächst.

**Für uns unmittelbar relevant:** Unser Repo ist gemischt (FastAPI-Backend +
React-Frontend), die Regel entscheidet also bei jedem Produkt-Slice mit, ob
ein R2-Slice zwei Stimmen bekommt oder eine — ein frontend-lastiger R2-Slice
bekommt danach eine Stimme statt zwei.

**Das ist eine Besetzungsentscheidung nach gemessenem Diff-Typ, kein
Freibrief, die Drittstimme generell wegzulassen:** Sie bleibt bei
Backend-Logik und gemischten Diffs gesetzt, und die Begründungspflicht beim
Abstufen (oben, „Warum drei") gilt unverändert für das, was eine gesetzte
Stimme findet — die beiden Regeln beantworten verschiedene Fragen (ob eine
Stimme sitzt vs. wie ihr Fund gewertet wird).

## Vorabprüfung: nicht „antwortet sie?", sondern „kann sie etwas ausführen?"

Die übliche Vorabprüfung („sag OK") testet den Modell-Aufruf, nicht die
Werkzeuge dahinter. Gemessen: Eine containerisierte Zweitstimme konnte
**keinen einzigen Befehl ausführen** (`bwrap: No permissions to create a new
namespace`) — das Modell lief normal, die Vorabprüfung war grün.

Eine Stimme, die nichts ausführen kann, aber weiter antwortet, liefert ein
Ergebnis, das äußerlich wie ein geprüftes aussieht: gleiche Form, gleiche
Schwere-Angaben, gleicher Tonfall — ohne einen ausgeführten Befehl darunter.
Im gemessenen Fall ging es gut, weil das Modell den Ausfall selbst erkannte und
offenlegte. **Das war Sorgfalt des Modells, nicht Eigenschaft des Verfahrens.**

**Regel:** Die Vorabprüfung setzt einen BEFEHL ab, dessen Ausgabe zurückkommen
muss — `git rev-parse HEAD` gegen den erwarteten Stand genügt. Kommt sie nicht,
ist die Stimme ausgefallen und der Ausfall-Vermerk gilt.

**Und in der Ergebnisform:** Konnte eine Stimme ihre Werkzeuge nicht nutzen,
steht das **unter ihrer Überschrift**. Eine Freigabe aus reiner Lektüre ist
etwas anderes als eine aus Reproduktion, und der Unterschied gehört in den
Kommentar, nicht nur ins Gedächtnis des Arbiters.

**Für uns bereits scharf geworden:** Genau dieser Fehler ist hier passiert.
Der Step-0-Trivialruf an Stimme 2 (GPT über Codex-CLI) ging durch, weil er
keinen Dateizugriff brauchte; der echte Prüfauftrag scheiterte danach an
`bwrap`-Rechten im Sandbox-Container. Der Vorabprüf-Befehl für Stimme 2 in
diesem Projekt ist deshalb nicht „sag Hallo", sondern ein Kommando, dessen
Ausgabe zurückkommen muss:

```bash
sh /c/Users/manue/.claude/Immich/model-panel/codex.sh exec --skip-git-repo-check --sandbox read-only -c 'model_reasoning_effort="high"' 'git rev-parse HEAD'
```

## Stimmen mit Repo-Zugriff arbeiten in eigenen Worktrees

Jede Claude-Stimme bekommt einen eigenen `git worktree` auf dem gemessenen
Commit; Mutationen und Container tragen ein stimmen-eigenes Präfix, das
Aufräumen wird nachgewiesen. Der Hauptagent darf den Hauptbaum währenddessen
weiterbewegen.

Gemessen: Eine Erststimme lief im Hauptbaum, während dort Nacharbeit
einfloss — ihr Bericht beginnt mit „Der Prüfgegenstand hat sich während des
Reviews bewegt", und sie musste zwei Stände auseinanderhalten. Zwei Stimmen mit
Mutationstests im selben Baum kollidieren zusätzlich.

Der Nebeneffekt ist der eigentliche Gewinn: **Die Nacharbeit kann beginnen,
bevor die letzte Stimme fertig ist** — die Stimmen prüfen den Commit, nicht den
Baum. Das ist die Quellen-Regel unten zu Ende gedacht.

**Für uns belegt:** Im 01.09.-Slice hat der Arbiter während laufender Stimmen
im selben Arbeitsbaum gearbeitet. Das konkrete Kommando für uns:

```bash
git worktree add ../immich-family-tools-panel-<stimme> <commit>
# … Stimme prüft dort …
git worktree remove ../immich-family-tools-panel-<stimme>
```

## Quellen-Regel: Keine Stimme sieht den Arbeitsbaum

Der Kontext jeder Stimme kommt aus `git show HEAD:<pfad>` oder einem
Commit-Diff — NIE aus dem Arbeitsbaum. Sobald irgendeine Stimme oder ein
Prüflauf mutieren darf (Mutationstests!), ist der Arbeitsbaum kein definierter
Zustand mehr. Gemessen: Eine Fremdstimme meldete ihren schwersten Befund gegen
eine Zeile, die in Wahrheit ein Mutations-Marker (`# MUT2`) war — der Befund
las sich völlig plausibel und verschwand erst beim Neulauf gegen
`git show HEAD:`. Der Fehler ist von außen unsichtbar; nur die Quelle schützt.

## Fremdstimmen: kein Netz, und Ausfall heißt Ausfall

Der Auftrag an jede Fremdmodell-Stimme enthält ein ausdrückliches
**Suchverbot** (kein Web-Zugriff, keine Recherche nach Repo, Commit oder
Namen). Gemessen: Eine Stimme, deren Sandbox ausfiel, erfand nichts — suchte
aber selbstständig im Netz nach Commit-Hash und Repo-Name. In einem Repo mit
sprechenden Namen wäre das ein Abfluss. Und ein Werkzeug-/Sandbox-Ausfall wird
als AUSFALL gemeldet, nie als Stimme mit dünnem Ergebnis.

**Bei uns scharf:** Unser Repo ist öffentlich (`Trust1509/immich-family-tools`
auf GitHub). Eine Fremdstimme, die bei einem Werkzeugausfall im Netz
nachsieht, findet das Repo und den Commit — und liest dann einen anderen
Stand als den geprüften, ohne dass das im Ergebnis sichtbar wird. Das
Suchverbot ist deshalb keine allgemeine Vorsicht, sondern verhindert hier
einen konkreten, erreichbaren Fehlerpfad.
