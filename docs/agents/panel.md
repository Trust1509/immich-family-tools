# Review-Panel: bis zu drei Stimmen über denselben Diff

Vor dem Landen eines nicht-trivialen Slices; wie viele Stimmen, sagt die
Risiko-Tabelle in `../../CLAUDE.md`. Das Panel hat in der Praxis
jeden zweiten Erstbau gestoppt — nicht wegen Kleinigkeiten, sondern wegen Funden,
die in Produktion wehgetan hätten.

## Warum bis zu drei, und warum eine davon blind

**Die drei Rollen tragen Namen, die sagen, was sie tun** (v1.15.0; vorher
„blinde Erststimme", „unabhängige Zweitstimme", „Arm C"/„Zweitblind-Stimme" —
„Arm C" stammte aus einem Pilot und bedeutete in einem späteren Benchmark etwas
anderes, niemand konnte es ohne Nachschlagen lesen):

| Name            | Wer                                                                                              | Kennt den Brief?                                                                | Wann                                                                           |
| --------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| **Blindprüfer** | frischer Claude-Subagent, nur Diff + Repo                                                        | nein                                                                            | immer (ab R2); in der Nacharbeit die Standardbesetzung (Schwelle: `CLAUDE.md`) |
| **Fremdprüfer** | Modell eines anderen Anbieters, Repo-Zugriff                                                     | kann (dann mit dem Auftrag, gegen den Brief zu messen — `bau-brief.md`, Ablage) | ab R2                                                                          |
| **Gegenprüfer** | zweite frische Claude-Stimme mit **Widerlegungsauftrag** (Aufsichts-/Angreifer-/Schadensrahmung) | nein                                                                            | Pflicht bei R3, optional bei R2                                                |

Die Überschriften im Panel-Kommentar bleiben nummeriert (`Stimme 1 —
Blindprüfer`), damit ältere Kommentare vergleichbar bleiben.

**Stimme 1 — Blindprüfer.** Ein _frischer_ Reviewer-Subagent, der **nur den
Diff und das Repo** bekommt: nicht den Bau-Brief, nicht den Bericht des Bauers,
nicht die Diskussion. Er darf Sonden fahren (Tests, eigene Messungen), aber nichts
ändern.

Das ist die wichtigste Regel des ganzen Verfahrens. Wer den Bau begleitet hat —
auch der Hauptagent — liest die **Absicht** statt des Codes. Der Blindprüfer
liefert deshalb überproportional die schwersten Funde: einen rekonstruierbaren
Kundennamen über die Sortierreihenfolge, einen gemessenen Datenverlust in einer
Migration, einen Testaufbau, der den eigenen Fix nie berührt.

**Stimme 2 — Fremdprüfer:** ein unabhängiges Modell über denselben Diff. Bringt eine andere
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

**Stimme 3 — abhängig von der Risikoklasse.** Bei R2 (wenn besetzt): entweder
die günstige diff-only-Fremdstimme oder der **Gegenprüfer** — zu unterscheiden,
denn gemessen liefern sie Gegensätzliches (siehe „Verfahren je Risikoklasse").
**Bei R3: der Gegenprüfer** — Begründung und Beleg unter „Verfahren je
Risikoklasse". Zur
diff-only-Stimme: **Erwartung realistisch halten** (Messreihe über fünf Projekte): ein
exklusiver bestätigter Fund insgesamt, dem rund ein Dutzend Fehl- und
Überbefunde gegenüberstehen, zweimal aktiv irreführend zur Kernfrage.

Der Grund ist strukturell, nicht modellabhängig: **Die schweren Funde liegen in
der Beziehung zwischen Diff und Umgebung** — ein Bezeichner, der in einer nicht
mitgelieferten Datei anders lautet; eine Zusicherung in einer Datei, die der Diff
nicht berührt. Diese Klasse ist diff-only **prinzipiell** unsichtbar.

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

Einmal je Rechner, nicht je Projekt. **Ohne diesen Abschnitt kann ein frischer
Klon das Panel nicht fahren** — die Kommandos gehören anschließend ausgefüllt in
dieses Dokument, damit sie kopierbar sind.

### Stimme 1 — Blindprüfer

**Woher:** aus der Agenten-CLI selbst, die ohnehin benutzt wird. Kein Konto,
keine Kosten, keine Installation.

**Voraussetzung:** Die CLI muss **Subagenten** starten können, die einen eigenen,
leeren Kontext bekommen. Kann sie das nicht, gibt es keinen Blindprüfer —
und dann fehlt genau die Stimme, die erfahrungsgemäß die schwersten Funde
liefert. Ein zweites Fenster derselben Sitzung ist **kein** Ersatz: Es sieht die
Historie.

**Pflichtzeile in jedem Prüfauftrag:** „Beende jeden eigenen Hintergrundlauf
VOR dem Bericht — über seine Prozessnummer, nie über den Programmnamen — und
nenne ihn in der Schlusszeile ‚Eigene Läufe am Ende: …'."
Die Schlusszeile allein reicht nicht — sie ist ein Formfeld, das eine Stimme
auch mit einem laufenden Prozess wahrheitsgemäß ausfüllen kann. **Kein Gate
macht das rot**: Der Arbiter sieht die offenen Läufe nur, wenn er selbst
nachsieht — er tut es, bevor er den Bericht verwertet (`lehren.md` §37).
Dasselbe gilt für den Nachweisweg der R2-Ausnahme unten: `ast-gleich.py` läuft
nur, wenn jemand daran denkt.

**Und eine Stimme räumt nur ihre eigenen Prozesse ab.** Gemessen im Panel zu
v1.16.0: Eine Stimme beendete einen hängenden Lauf mit einem rechnerweiten
`taskkill /F /IM python.exe` und hat das offengelegt — der Griff trifft jeden
Python-Prozess auf dem Rechner, auch die einer parallelen Sitzung. In den
Prüfauftrag gehört deshalb: **eigene Läufe über ihre Prozessnummer beenden,
nie über den Programmnamen.**

**Aufsetzen:** Der Prüfauftrag enthält den Diff oder den Vergleichsbereich, das
Repo — und ausdrücklich **nicht** den Bau-Brief, den Bericht des Bauers oder die
Diskussion. Der Subagent darf lesen und Sonden fahren, aber nichts ändern.
Den **Tracker-Zugang entziehen, wo möglich** (dort liegt der Brief als
Issue-Kommentar); wo das Werkzeug ihn trotzdem hat (`gh` über die Shell), ist
der Blindprüfer nur per Auftrag getrennt — dann gehört die negative Probe unten
ausdrücklich gegen den Brief-Kommentar gefahren.

**Blindheit wird BELEGT, nicht behauptet.** Ein Auftragstext ohne Brief macht
eine Stimme nicht blind, wenn sie Brief, Bauer-Bericht oder frühere
Panel-Kommentare über ihre Werkzeuge trotzdem erreicht (Repo-Ablage, Issue-
Zugriff, eingehängte Verzeichnisse). Gemessen in einem Benchmark: Die
Bewertungsrolle bekam das ganze Arbeitsverzeichnis eingehängt — **8 von 8**
verbotenen Artefakten (Zuordnung, Vorbefunde, Bilanzen) waren lesbar, über
mehrere Serien unbemerkt. Nach dem Umbau auf „nur das Nötige einhängen" 0 von 8. Deshalb vor einer Serie einmal eine **negative Probe** über die tatsächlichen
Zugänge der Stimme (versucht, die verbotenen Dateien zu lesen — muss scheitern)
**und die Gegenprobe**, dass das Nötige da ist. Nur die erste Hälfte ist von
einem leeren Mount nicht zu unterscheiden.

**Der Prüfauftrag geht als Datei, nicht als Argument.** An der Argumentgrenze
des Betriebssystems liefert der Aufruf Exit 0 und eine leere Stimme —
gemessen bei 48 KB, zwei Review-Läufe ungültig, ohne Fehlermeldung.

**Wer nie blind sein kann: der Orchestrator.** Er hat gebaut, gepusht,
Worktrees angelegt; Diff-Größen, Dateinamen und Reihenfolge verraten ihm jede
Zuordnung. Gemessen: In einem verblindeten Vergleich war die Zuordnung nach dem
Aufbereiten faktisch bekannt. Das ist keine Schwäche, die sich wegorganisieren
lässt — also wird sie **benannt**: Wo Verblindung zählt (Bewertung,
Vergleich), laufen die Stimmen in einer mechanischen Schleife ohne
Zwischenentscheidung des Orchestrators, und der Zeitpunkt, ab dem er entblindet
war, steht im Ergebnis.

### Stimme 2 — Fremdprüfer: unabhängiges Modell mit Repo-Zugriff

**Woher:** die CLI eines _anderen_ Anbieters als dem der Hauptagenten-CLI. Meist
über ein bestehendes Abo, nicht über einen API-Schlüssel — das ist der günstigste
Weg, wenn ohnehin eins vorhanden ist.

**Warum containerisiert:** Solche CLIs bringen eine eigene Laufzeit mit. Die
gehört nicht auf den Arbeitsrechner (siehe `lehren.md` §10, „Zwei Umgebungen,
eine geprüft"),
sondern in ein Abbild; die Anmeldung überlebt in einem Volume:

```dockerfile
# Dockerfile.stimme2 — Beispielgerüst
FROM <laufzeit-basisabbild>
RUN <installationsbefehl der Anbieter-CLI>
WORKDIR /arbeit
```

```sh
# stimme2.sh
docker run --rm -it -v stimme2-home:/root -v "$PWD:/arbeit" stimme2 "$@"
```

**Einmalig:** Anmeldung im Container (`sh stimme2.sh login`), danach liegt sie im
Volume.

**Fallstricke, teuer gelernt:**

- Die Stimme kennt den lokalen Arbeitsbaum **nicht**. Sie braucht einen
  **gepushten Review-Zweig** — ungepushte Commits sieht sie nie.
- **Einen Windows-Worktree nicht in den Container einhängen.** Seine
  `.git`-Datei zeigt auf einen Windows-Pfad, den der Linux-Container nicht
  auflösen kann — jedes `git`-Kommando endet mit Exit 128 (gemessen). Die
  Stimme bekommt ein vollständiges Repo: einen Klon des Review-Zweigs oder ein
  `git archive` des gemessenen Commits.
- Manche CLIs brechen ab, wenn das Arbeitsverzeichnis kein Repo ist, oder wenn
  ihnen Sandbox-Rechte fehlen. Beides meldet sich erst nach Minuten. Deshalb
  steht die Erreichbarkeitsprüfung im Ablauf **vor** dem Start.
- Im Prompt einen Block **„Bewusste Entscheidungen (NICHT als Fund melden)"**
  mitgeben, sonst verbrennt die Stimme ihren Zug an Design-Entscheidungen.
- Ein Durchlauf dauert lang und ist gesprächig. Aufruf im Hintergrund starten und
  **in eine Datei** schreiben, nie in eine Pipe.

### Stimme 3 (R2-Besetzung) — günstige diff-only-Stimme über eine API

**Woher:** ein Anbieter mit OpenAI-kompatibler Schnittstelle; Aggregatoren sind
praktisch, weil sich das Modell wechseln lässt, ohne etwas umzubauen.

**Kosten:** Größenordnung Cent je Review, nicht Euro. Guthaben aufladen und im
Blick behalten — ein leeres Guthaben ist der häufigste Ausfall dieser Stimme.

**Fertiges Werkzeug liegt bei:** `docs/vorlagen/panel-stimme3.py`. Es braucht
zwei Umgebungsvariablen aus einer `.env` **außerhalb** des Repos:

```
PANEL_API_BASE=https://<anbieter>/api/v1
PANEL_API_KEY=<schlüssel>
```

```sh
git diff <basis>..<kopf> > stimme3.diff || exit 1
python docs/vorlagen/panel-stimme3.py \
    --model ⟨anbieter/modell⟩ --max-tokens 32768 --stdin-anhang \
    "⟨Prüfauftrag⟩" < stimme3.diff > review-stimme3.md
```

**Fallstricke:** Den Diff **nicht per Pipe** übergeben — in
`git diff … | python …` geht der Exit von `git diff` verloren (dieselbe Klasse
wie die Kopf-Zählung in `ci.yml`); erst in eine Datei, Exit prüfen, dann per
Umleitung. Ausgabe in eine Datei, nie in eine Pipe. Bei großen Diffs
`--max-tokens` großzügig — reicht das Budget nicht, verbraucht das Modell alles
im Nachdenk-Anteil und die Antwort kommt leer oder abgeschnitten zurück.

**Exit-Code lesen, nicht die Datei:** 0 = Antwort vollständig geschrieben
(`finish_reason` „stop"); 1 = Ausfall (HTTP-Fehler, HTTP-Umleitung, Netz, Antwort
kein JSON-Objekt, Antwort in unerwarteter Form (Objekt an der Wurzel, andere
Form in der Tiefe), keine Wahl in der Antwort, Fehlerobjekt in einer
200-Antwort, **leere Antwort**,
**abgeschnittene Antwort** — `finish_reason` nicht „stop", etwa „length"); 2 =
Aufruf- oder Konfigurationsfehler (Variablen fehlen, **`--stdin-anhang` mit
leerem Anhang** — dann wird nichts gesendet). Bei 1 und 2 gilt „Wenn eine
Stimme ausfällt" unten — eine leere oder halbe Datei ist nie ein dünnes
Ergebnis.

### Eingetragen: unsere Aufrufe

Die diff-only-Stimme und `ast-gleich.py` liegen **im Repo** unter
`docs/vorlagen/` — byte-identisch mit der Vorlage (`panel-stimme3.py`
74be4dd, `ast-gleich.py` 0e9b6dc, geprüft beim Abgleich auf v1.16.0). Dieselben
Dateien liegen portfolioweit unter
`C:\Users\manue\.claude\Immich\model-panel\` und tragen dort **denselben
Blob**; welche der beiden aufgerufen wird, ist heute dasselbe Werkzeug. Der
Wrapper der Fremdstimme (`codex.sh`) liegt nur portfolioweit, weil er eine
Container-Anbindung dieses Rechners ist und nichts ist, was ein Klon dieses
Repos gebrauchen könnte.

Die `.env` mit `PANEL_API_BASE` und `PANEL_API_KEY` liegt **außerhalb** des
Repos — Pfad hier, Inhalt nirgends.

**Fremdprüfer (GPT über die Codex-CLI):**

```bash
sh /c/Users/manue/.claude/Immich/model-panel/codex.sh exec --skip-git-repo-check -c 'model_reasoning_effort="high"' '<Prüfauftrag>'
```

`--sandbox read-only` steht hier seit 06.09.2026 **nicht** mehr, und das ist
keine Stilfrage: Die Stimme lief eineinhalb Wochen als AUSFALL, weil Codex
innerhalb unseres Containers noch eine eigene Bubblewrap-Sandbox aufbauen
wollte und daran scheiterte (`bwrap: No permissions to create a new
namespace`). Der Wrapper setzt jetzt
`--dangerously-bypass-approvals-and-sandbox` — Codex nennt das Flag selbst
„intended solely for running in environments that are externally sandboxed",
und der Container **ist** diese Umgebung.

**Der Schutz liegt seitdem im Mount, nicht in der inneren Sandbox:** Der
Wrapper hängt das Arbeitsverzeichnis **schreibgeschützt** ein — strenger als
vorher, denn mit `--sandbox workspace-write` hätte eine Stimme in den echten
Arbeitsbaum schreiben können. Gemessen in beide Richtungen: Die Vorabprüfung
liefert den erwarteten `HEAD` zurück; ein Schreibversuch endet mit
`Failed to write file /work/…`, und im Arbeitsbaum entsteht nichts. (Wer
wirklich schreiben muss — Bau statt Review — setzt `CODEX_RW=1`. Für eine
Panel-Stimme ist das falsch.)

**Was der Mount NICHT ersetzt: die Quellen-Regel.** Der Wrapper hängt das
_aktuelle_ Verzeichnis ein, nicht den geprüften Commit. Fürs Panel gehört die
Stimme deshalb auf einen Wegwerf-Klon auf dem gemessenen Stand:

```bash
git clone -q --no-hardlinks . ../codex-klon && git -C ../codex-klon checkout -q <commit>
cd ../codex-klon && sh …/codex.sh exec --skip-git-repo-check -c 'model_reasoning_effort="high"' '<Prüfauftrag>'
```

Zwei Fallstricke, die real zwei Anläufe gekostet haben: Sie **muss aus dem zu
prüfenden Verzeichnis heraus** laufen (der Wrapper mountet das aktuelle), und
**ohne `--skip-git-repo-check` bricht sie ab**, wenn das Verzeichnis kein
Git-Repo ist.

**Diff-only-Stimme (R2-Besetzung):**

```bash
git diff <basis>..<kopf> > stimme3.diff || exit 1
python docs/vorlagen/panel-stimme3.py     --model deepseek/deepseek-v4-pro --max-tokens 32768 --stdin-anhang     '<Prüfauftrag>' < stimme3.diff > review-stimme3.md
```

**Dieser Aufruf hat sich mit dem Abgleich auf v1.16.0 geändert.** Bis dahin
stand hier `ask-api.py`. Das Werkzeug meldet **Ausfälle als Exit 0** — eine
leere oder abgeschnittene Antwort sah damit aus wie ein dünnes Ergebnis, nicht
wie ein Ausfall. Genau diese Klasse beschreibt die Vorlage oben unter
„Exit-Code lesen, nicht die Datei". Wer den alten Aufruf noch irgendwo stehen
hat, tauscht ihn.

Bekannte Eigenheit beider Fremdstimmen: Sie irren Richtung **zu streng** und
lesen gelegentlich die Vorher-Seite eines Diffs als den geltenden Stand.

### PII-Grenze

Fremdmodelle sind fremde Dienste. Personenbezogene oder geschäftliche Daten
gehen nicht ohne ausdrückliche Freigabe dorthin. Bei Repos mit solchen Daten:
den **Diff inline** übergeben, statt einer Stimme Repo-Zugriff zu geben — und
Seed-/Testdaten grundsätzlich erfinden, nie aus dem Kontext übernehmen.

**Bei uns konkret:** Gesichts- und Personendaten aus den Immich-Fotobeständen
— Namen, die aus einem Gesichtserkennungs-Match stammen, e-Mail-Adressen
echter Nutzer, alles, was eine reale Person identifiziert — sind PII und gehen
**nie** in einem Diff an den Fremdprüfer oder eine diff-only-Stimme. Erlaubt
sind nur Code und **erfundene** Fixtures (`bau-brief.md`, „Fixtures werden
erfunden"). Das ist keine Theorie: Ein Personenname aus der Gesichtserkennung
kann über Prüfdaten oder ein Log-Beispiel unbemerkt in einen Diff geraten.
Praktisch: Vor dem Push des Review-Zweigs und vor dem Zusammenstellen des
Diffs **den Diff selbst gegen diese Klasse lesen** — nicht nur den Code, der
ihn erzeugt hat. Im Zweifel nicht schicken, sondern auf den Gegenprüfer
ausweichen; der bleibt lokal.

## Ablauf

```bash
# 1. Review-Branch pushen (die externen Stimmen brauchen ihn)
git push -f origin <commit>:refs/heads/review/<issue>-<kurzname>
```

**Panel VOR dem Landen heißt: Review-Zweig pushen, Hauptzweig nicht.** Der Diff
geht so zu den Stimmen: Stimme 1 bekommt den Vergleichsbereich lokal, Stimme 2
den gepushten Zweig. Stimme 3 hängt an der Besetzung: bei R2 (wenn besetzt)
entweder die diff-only-Stimme — sie bekommt den Diff über die
Standardeingabe — oder der Gegenprüfer; bei R3 der Gegenprüfer, der im
`git archive`-Baum mit dem Vergleichsbereich als Datei misst (unten, „Stimmen
mit Repo-Zugriff arbeiten in eigenen Worktrees"). Eine Stimme,
die den Zweig nicht sieht, prüft einen alten Stand — das hat einen kompletten
Lauf gekostet.

**Modell und Stand gehören ins Ergebnis.** Je Stimme in der Überschrift
(`### Stimme 2 — Fremdprüfer (⟨Modell⟩, 2026-08-19)`, Form wie in
`panel-kommentar.md`). Das Commit-Format
besitzt `../../CLAUDE.md` — dort steht, welche Rollen aufgeführt werden und wie;
hier steht nur, dass es gemacht wird. _(Nachtrag 2026-08-20: An dieser Stelle
stand bis v1.9.1 eine eigene, einteilige Fassung des Formats — eine Drift nach
§14, gemeldet von einem Projekt, drei Stunden nachdem die Regel dagegen
geschrieben wurde.)_ Zwei Gründe: Die Herkunfts-Regel
ist sonst nach vier Wochen nicht mehr durchsetzbar — „wer hat das gebaut" steht
nirgends. Und jede Aussage über Modellverhalten bleibt Anekdote, solange das
einzelne Ergebnis den Modellstand nicht trägt. Anbieter ziehen still nach,
deshalb das Datum.

**1b. Erreichbarkeit der externen Stimmen prüfen — VOR dem Start, nicht
mittendrin.** Stimme 2 braucht den gepushten Zweig und ein lauffähiges Werkzeug
(zweimal gescheitert: kein Git-Repo im Arbeitsverzeichnis, dann fehlende
Sandbox-Rechte). Ist Stimme 3 die diff-only-Stimme (nur bei R2), braucht sie
Guthaben; ist sie der Gegenprüfer, braucht sie Sitzungskontingent der eigenen
CLI (siehe „Verfügbarkeit"). Diese Ausfälle melden sich sonst erst, wenn der
Slice schon als „gleich fertig" gilt.

**2. Alle Stimmen der Klasse parallel starten**, nicht nacheinander — sie
brauchen zusammen 20–40 Minuten, sequenziell wäre das ein Vielfaches.

**3. Arbitrieren.** Jeden Blocker **am Code reproduzieren**. Prüfer-Konvergenz
ersetzt keine Reproduktion: Zwei Stimmen können denselben Fehler machen, und die
diff-only-Stimme liest gelegentlich die Vorher-Seite eines Diffs und meldet
einen längst gefixten Zustand. **Konvergenz ist ein Grund zu messen, kein
Grund aufzuhören** — gemessen in drei Benchmark-Läufen: 3 von 3 Stimmen
erklärten einen roten Test unabhängig mit derselben falschen Ursache (ein
Overlay), gemessen war es ein Substring-Locator; in jedem Lauf mit
Testausführung fanden 2–3 Blocker ausschließlich die Gates und der Rauchtest,
nicht das Panel. Für Verhaltensfragen an einer echten Tür gilt deshalb **Sonde
vor Hypothese**: Die Stimme formuliert den Verdacht, eine reproduzierbare Sonde
(echte Werkzeugfunktion, gefälschter Kontext, Wegwerf-Datenbank — Sekunden,
kein Token) entscheidet. Zwei plausible Hypothesen zu einem Türverhalten waren
beide falsch; die Sonde brauchte 0,1 s.

**Unsere konkrete Form:** die Funktion aus `backend/` direkt importieren, ein
erfundenes `accounts.json` in ein Wegwerf-Verzeichnis legen, aufrufen — kein
Modell, kein Token.

**Vor jeder Stimme: der Prüfgegenstand ist artefaktfrei.** Messläufe des
Orchestrators (Rauchtest, Playwright) schreiben Fehlerkontexte und Berichte in
den Baum — gitignored, in `git status --short` unsichtbar, für eine Stimme mit
Repo-Zugriff lesbar. Gemessen: Eine Stimme zitierte die Fehlerkontexte des
Orchestrator-Laufs als eigenen „Beleg"; drei Runden lang waren die Stimmen nicht
von der Messung isoliert. Die Probe ist `git status --short --ignored` auf den
Prüfpfaden, nicht `git status --short` und nicht `--porcelain` allein; Artefakte
wandern vor dem Review in den Run-Ordner. **Verbindlich (Owner-Entscheid
v1.15.0)** — Projekte, die lokal `--short` oder `--porcelain` ohne `--ignored`
eingeführt haben, gleichen an: Genau die gitignorierten Artefakte waren es, die
eine Stimme als eigenen Beleg zitierte.

**Das gilt in beide Richtungen und in der Laufzeit der Stimme.** Sonden,
Hilfsskripte und Mitschnitte der Stimmen gehören in ein Scratch-Verzeichnis
AUSSERHALB des Baums — gemessen: untracked Sonden einer Stimme lagen im Baum,
die nächste Stimme maß neun fremde Fehlschläge als eigene. Und die Probe läuft
dort, wo die Stimme liest: Ein Baum, der auf dem Host sauber ist, war im
Container „verändert" (Zeilenenden, Dateimodus) — das wird getrennt
reproduziert, nicht als Fund der Stimme gezählt.

**4. Nacharbeit** nach `bau-brief.md` — sie ist **neuer Code**, kein Nachtrag.

**Die Regel hängt am GELANDETEN ZUSTAND, nicht am Slice.** Was am Ende auf dem
Hauptzweig liegt, ist geprüft — egal in wie vielen Anläufen es dorthin kam.
Damit ist Nacharbeit automatisch erfasst, ohne eine zweite Regel. Zwei Projekte
haben das Panel bei der Nacharbeit weggelassen mit der Begründung „setzt nur
bestätigte Befunde um"; beide Male entstand der neue Defekt genau dort.

**Rundengrenze und Besetzung der Nacharbeit: Die Schwelle steht in
`../../CLAUDE.md` (Risiko-Tabelle, Zeile „Nacharbeit"), hier Verfahren und
Beleg.** Bis v1.14 war die verkürzte Nacharbeitsrunde eine erlaubte Option —
und wurde unter Druck kaum genommen. Gemessen in einem Projekt über zwei Tage:
9 und 13 Nacharbeitsrunden an zwei Slices, beim ersten mindestens sechs der
neun Runden mit vollem Panel inklusive Gegenprüfer, drei Slices parallel am selben Kontingent, Stimmen
mehrfach am Sitzungslimit gestorben — und am Ende war nichts gelandet. Deshalb
ist die Verkürzung jetzt der Standard. Das Verfahren:

- **Wie gezählt wird und ab wann angehalten wird**, steht in der Zeile
  „Nacharbeit" in `CLAUDE.md` — hier nicht wiederholt.
- **Die Nacharbeitsrunde prüft der Blindprüfer** auf dem Nacharbeits-Diff, mit
  zugeschnittenem Auftrag. Beleg, dass das trägt: In einem Fall fand diese
  verkürzte Runde sechs weitere Punkte, alle exklusiv.
- **Der Gegenprüfer läuft in der Nacharbeit nur bei einer NEUEN Tür** (ein
  Schreibweg, eine Schnittstelle, eine Berechtigung, die in der Erstrunde nicht
  Gegenstand war). Unter seiner Überschrift steht, warum er lief oder nicht.
- **Bei R3 und R4 wiederholt der Arbiter zusätzlich die risikospezifische Probe**
  (Datenerhalt, Berechtigungs-Sonde, Rundungsfall) auf dem Nacharbeits-Stand —
  sie kostet Sekunden, keine Stimme, und hält die R3-Zusage am gelandeten
  Zustand.
- **Beim Anhalten:** Stand melden, Zerlegung prüfen, Owner fragen — keine
  weitere Runde aus eigenem Entschluss. Beleg für die Grenze: In den
  gemessenen Serien schloss jede weitere Runde die alten Punkte und riss neue
  Löcher an genau den Stellen, die die Runde davor angebunden hatte — ab der
  dritten Runde mit Randfällen war die Zerlegung das Problem, nicht der
  Randfall.
- **Nacharbeit des Arbiters ist Bau-Code.** Setzt der Hauptagent Auflagen
  selbst um, bekommt dieser Diff denselben Blindprüfer — gemessen hatten drei
  von vier Arbiter-Fixes eines Slices ein neues Loch.
- **Kosten stehen fest, bevor die Serie beginnt** (siehe „Verfügbarkeit").

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
**`LC_ALL=C` voranstellen, jeden Umlaut im Muster als `..?` schreiben**, `-i`
und `-E` setzen und das **seltenste Einzelwort** suchen — ein Einzelwort kann nicht
umbrochen werden. Mit dem Umlaut im Muster faltet `-i` unter `C` keine
Umlaute (gemessen: 1 von 2 Zeilen), und unter einer UTF-8-Locale trifft er eine
CP1252-Datei gar nicht (0 von 2; Messung und Kommando in `abgleich.md`,
Schritt 2b) — die Sonde verwirft dann einen korrekten Befund mit einer Zahl,
die nach Beweis aussieht.

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

Dazu ein Status, der **kein** Urteil ist: **umgangen, nicht entschieden.** Hat
die Nacharbeit einen Fund umschifft (anderer Weg, anderer Test), ohne ihn je zu
reproduzieren, zählt er weder als bestätigt noch als widerlegt. Gemessen: Drei
Stimmen behaupteten dieselbe Ursache für einen roten Test, die Nacharbeit
wählte einen anderen Weg, die Ursache wurde nie geprüft — und in einem späteren
Lauf war die tatsächliche Ursache eine andere. Ein umgangener Fund bleibt als
Hypothese stehen und geht in keine Fundstatistik.

**Schwere-Umstufung ist erlaubt und wird gekennzeichnet.** Der Arbiter darf hoch-
und herunterstufen (die Konsumenten-Frage macht aus einem Anzeigefehler regelmäßig
einen Schreibpfad-Fehler). Die Umstufung wird im Panel-Kommentar als solche
markiert, z. B. `P2 → P1 (arb.)`, sonst ist sie stille Meinung.

**Fund und Schwere werden getrennt arbitriert.** Ein Fund kann bestehen
bleiben, während seine Begründung zusammenbricht — das dritte Urteil („richtiger
Instinkt, falsche Begründung") gilt in **beide** Richtungen, nicht nur beim
Verwerfen. Gemessen: Ein BLOCKER hing an der Mengenannahme „~34 000 Bilder
laufen durch diesen Pfad"; die messende Stimme wies nach, dass sie einen anderen
Pfad nehmen — die Rechnung war um Größenordnungen zu hoch, der Rest-Grund (ein
geteilter Server, eine volle Platte trifft fremde Dienste) stand unabhängig
davon, und der Fund wurde gebaut. Eine Regel, die aus „Prämisse widerlegt" ein
„Fund erledigt" macht, wäre schädlich. Daraus die Gegenrichtung zur
v1.13.0-Begründungspflicht: **Wer strukturell HOCHstuft, benennt die
Mengenannahme, auf der die Schwere ruht** — zweimal in Folge hat die messende
Stimme die strukturelle korrigiert. Und der Arbiter stuft nach EINER Regel über
alle Runden: Derselbe Fund (ein Generator vernichtet die handgeschriebene
Übersetzung bei jedem Lauf) kam in zwei Läufen als KLEIN und als BLOCKER; die
Schwere folgt der Klasse, nicht der Stimme, die ihn zuerst nannte.

**Widersprechen sich zwei Stimmen, entscheidet die Reproduktion**, nicht die
Mehrheit und nicht die Plausibilität der Begründung.

**Die Reproduktion kommt aus einer anderen Quelle als das Geprüfte.** Ein
grüner Test des Bauers widerlegt keine Behauptung über genau diese
Testabdeckung, eine Messung des bewerteten Stands keinen Einwand gegen diesen
Stand. Gemessen: Zwei als „nicht gestützt" eingestufte Einwände wurden erst
durch eine eigene Sonde entschieden — die Tests des Geprüften waren grün und
bewiesen nichts über die Frage.

**Ein Bestand mit derselben Schwäche ist kein Freispruch für den Diff.** Findet
eine Stimme einen Fehler im neuen Code und der Arbiter dieselbe Schwäche schon
im Bestand, gilt: fail-closed landen (der neue Code bekommt die Korrektur), der
Bestand wird ein eigenes Issue. Gemessen: Personenbezogene Daten in fünf
Notizfeldern — „das macht der Rest auch so" hätte den sechsten Fall eingebaut.

**Vor-Reproduktion ist ein fester Schritt, kein Ersatz.** Der Arbiter
reproduziert die schwersten erwartbaren Fälle einmal selbst, BEVOR das Panel
startet (gemessen: 2 von 6 späteren Blockern eines Slices waren so vorab
sichtbar und kosteten keine Stimmenrunde). Das Panel läuft trotzdem.

**Unmittelbar vor dem Landen misst der Arbiter die Gates erneut.** Eine Messung
ist ein Zeitpunkt, kein Zustand: Die Aussage „Baum rot" war beim Lesen schon
falsch, weil zwischen Messung und Entscheidung Nacharbeit einfloss. Die volle
Suite läuft dafür einmal **allein** in einem eigenen Worktree — parallel zu
Stimmen mit Mutationen ist sie nicht isoliert.

## Prüfaufträge, die sich bewährt haben

Nicht „prüfe den Diff", sondern **eine Behauptung zum Widerlegen**:

> Die Behauptung lautet: ⟨X⟩. Versuche das zu WIDERLEGEN. Denk an Umwege:
> ⟨konkrete Kandidaten⟩.

Dazu:

- **Nennen, was schon geprüft und ohne Befund ist** — sonst laufen alle drei
  dieselben Wege ab.
- **Ausdrücklich erlauben, nichts zu finden.** Sonst wird etwas erfunden.
- **Ausdrücklich erlauben, NICHT ZU ENTSCHEIDEN.** Kann eine Stimme eine Frage
  mit ihren Mitteln nicht beweisen (sie braucht eine Ausführung, einen Zustand,
  eine Persona, einen anderen Rechner), lautet die richtige Antwort **„nicht
  entschieden — entscheidende Probe: ⟨X⟩"**, nicht eine Ursachenbehauptung.
  Gemessen in 15 verblindeten Bewertungsläufen: 0 solcher Antworten bei den
  ausführungs- oder zustandsabhängigen Defekten, dafür einmal eine falsche
  Gewissheit („die Ablaufverfolgung widerlegt dies") — und in einem anderen
  Lauf erklärten 3 von 3 Stimmen einen roten Test mit derselben falschen
  Ursache. Die Einteilung dahinter steht in `lehren.md` §33 (S1/S2/S3).
- **Den Widerlegungsauftrag an der REICHWEITE der Behauptung ansetzen**, nicht
  an ihrem Wortlaut. „Vollständigkeit ist typerzwungen" war belegt — für das
  Vorhandensein eines Schlüssels, nicht für seinen Wert. Der Gegenprüfer fand
  als einziger den Wert, der da war und nichts bedeutete (`lehren.md` §16,
  „vorhanden, aber falsch").
- **Auch eine Prüfstimme sondet gern in die bestätigende Richtung** — dieselbe
  Falle wie beim Arbiter (oben). Der Auftrag nennt deshalb die widerlegende
  Richtung ausdrücklich: „Welche Eingabe macht die Zusage falsch?"
- **Wird ein großer Diff für eine Stimme geschnitten, sind „fehlt im
  Ausschnitt"-Funde Schnitt-Artefakte**, keine Funde — gemessen bei einer
  Fremdstimme auf einem geteilten Diff. Der Auftrag nennt die Schnittgrenze.
- **Je Fund: Schwere, Datei:Zeile, Nachweis.** Kein Nachweis, kein Fund. Die
  Regel schützt nicht nur vor erfundenen Funden — sie macht einen **stillen
  Werkzeugausfall sichtbar**: Ein Review ohne Datei:Zeile-Nachweise liest sich
  flüssig, und genau so sieht eine Stimme aus, deren Sandbox nichts ausführen
  konnte.
- **„Zählt der Slice seine eigene Zusage ab?"** — Prüffrage 8 des Bau-Briefs
  als Auftrag an die Stimmen, nicht nur an den Bauer. Ein Bauer, der seine
  Zusage nicht abzählt, beantwortet auch die Frage danach mit „ja"; im
  Prüfauftrag gestellt, erzeugte sie den schwersten Befund eines Panels: Der
  Slice hatte zwei Zusagen, der Bauer meldete beide als erfüllt und die Suite
  als grün — beide Stimmen fanden unabhängig, dass die Suite vor und nach dem
  Fix identisch grün war.
- **Behauptungslisten im Prüfauftrag aus den Köpfen der Dateien zitieren,
  nicht aus dem Gedächtnis.** Der Orchestrator schrieb in einen Prüfbrief eine
  Mutation unter „wird rot", die die Datei selbst als äquivalent (nicht
  prüfbar) führte; der Blindprüfer korrigierte den Brief, nicht die Datei
  (v1.15.4). Was der Brief behauptet, muss im Baum stehen — sonst prüft die
  Stimme den Orchestrator statt des Stands.
- **„Ist jede Behauptung im Brief belegt oder als Annahme markiert?"** —
  Prüffrage 6, im Prüfauftrag an die Stimme, die den Brief kennen darf
  (Fremdprüfer): „Prüfe jede Behauptung des Briefs gegen den Stand —
  Tabelle _Behauptung → stimmt / stimmt nicht / überschärft → Beleg_." Als
  Selbstprüfung antwortet der Schreiber „ja" (`bau-brief.md`, „Elf
  Prüffragen").
- **„Prüft dieser Test, was wahr bleiben MUSS — oder nur, was sich nicht
  ändern DARF?"** — Prüffrage 2, im Prüfauftrag an jede Stimme mit
  Repo-Zugriff: „Welcher neue Test bestünde auch, wenn der Zweck verfehlt
  wäre?" Ein Test „200 oder 307" misst nur die Absicht seines Autors.
- **Jede Verhaltensvorgabe des Bau-Briefs steht im Auftrag mindestens einer
  Stimme als „diese Vorgabe ist zu widerlegen"** — nicht als Kontext. Wer den
  Brief kennt, erbt seine blinden Flecken; die einzige Stimme, die den
  schwersten Fund eines Slices finden konnte, war die, die den Brief NICHT
  kannte (Fall in `bau-brief.md`, „Die Wahrheit des Briefs").
- **Eine widerlegte Behauptung des Prüfauftrags ist ein Fund** und wird wie
  einer arbitriert. Der Prüfauftrag ist ein Auftragstext mit Behauptungen, und
  er ist inzwischen die schwächste Stelle vieler Slices — in einem Projekt
  machen solche Funde die Mehrheit aus („der Produktions-Build lintet nicht",
  „Sicherheits-Updates bleiben unberührt": beide falsch, beide vom Orchestrator).
- **Der Panel-Diff enthält auch, was der Orchestrator geschrieben hat**
  (Release-Notizen, Meldungen, Kommentare). Eine Stimme, die nur die Änderungen
  des Bauers liest, prüft die Hälfte.
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

### Stimme 1 — Blindprüfer

### Stimme 2 — Fremdprüfer

### Stimme 3 — ⟨R2: diff-only-Fremdstimme oder Gegenprüfer / R3: Gegenprüfer⟩

### Zusätzlich, nicht gezählt — ⟨diff-only-Stimme; nur, wenn sie gelaufen ist⟩

### Arbitrierung

⟨je Fund: reproduziert / verworfen / umgangen, und von welcher Stimme er kam⟩
⟨Orchestrator-Quote: wie viele Funde trafen einen Text des Orchestrators⟩
```

**Warum so streng:** Ein Panel-Ergebnis in Fließtext zeigt nicht, **wer**
gesprochen hat. Es liest sich vollständig, egal ob drei Stimmen geprüft haben
oder zwei — das Fehlen ist keine sichtbare Lücke, sondern eine unsichtbare.
Genau das ist in einem laufenden Projekt passiert: dass über mehrere Slices nur
zweistimmig geprüft worden war, fiel erst später auf, und nicht am
Panel-Ergebnis. Drei Überschriften drehen das um — eine leere Überschrift
springt ins Auge, ein fehlender Absatz nicht.

Deshalb: **Fällt eine Stimme aus, steht unter ihrer Überschrift der Grund** —
„Werkzeug nicht verfügbar seit ⟨Datum⟩, Owner informiert am ⟨Datum⟩" oder
„Guthabenende (⟨402 | gleichgestellt⟩) auf der Ersatzleitung des Fremdprüfers,
Owner gefragt am ⟨Datum⟩" — und
nie einfach nichts. Ein Slice ohne vollständiges oder ausdrücklich
vermerkt-verkürztes Panel gilt als **nicht geprüft** und wird nicht
ausgeliefert.

## Eine Stimme bewusst weglassen — erlaubt, wenn begründet

„Nie stillschweigend reduzieren" heißt nicht „nie reduzieren". Wie weit
reduziert werden darf, sagt die **Untergrenze** in `../../CLAUDE.md`
(Review-Panel); dieser Abschnitt nennt keine eigene Schwelle, sondern die
Form. Ein Projekt hat
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
Zustand feststellen, dann nach „Wenn eine Stimme ausfällt" weiter.

**Verfügbarkeit wird vor jeder Serie GEMESSEN, nicht angenommen** — das
Sitzungskontingent der eigenen CLI ebenso wie das Guthaben eines
API-Anbieters. Beide töten eine Rolle mitten in der Arbeit und hinterlassen
halbe Arbeit im Baum: Ein Bauer starb am Sitzungslimit, weil die Sitzung nicht
mit vollem Kontingent gestartet war; ein anderer am Guthaben mit 0,61 $ Rest,
nach acht Minuten Arbeit, mit einer halbfertigen Datei. Der zweite Fall hat
eine Tücke: **Der Anbieter lehnt ab, sobald das Restguthaben `max_tokens ×
Preis` nicht mehr deckt** — der Ausfall kommt deutlich vor der echten
Erschöpfung. Seitdem misst der Runner das Guthaben vor jeder Rolle und startet
unter einer Schwelle gar nicht erst (Rot-Beweis gefahren: Exit 3, null Bytes).

**Ein Kostenstopp steht fest, BEVOR die Serie beginnt** — sonst entscheidet
die Erschöpfung, wann aufgehört wird, und sie entscheidet mitten in einer
Runde. Festgelegt werden: die Rundengrenze (`../../CLAUDE.md`), wie viele
Slices gleichzeitig am selben Kontingent prüfen dürfen, und was beim Erreichen
passiert. **Der geordnete Abbruch** sieht so aus: alle Stimmen stoppen, jeder
Baum wird committet und der Branch gepusht, nichts landet, kein CI-Lauf — und
es entsteht ein Wiederaufnahme-Vermerk (SHA je Branch, Worktree-Tabelle mit
Rollen, offene Runde je Slice, Sonden außerhalb des Repos, nummerierte
nächste Schritte). Gemessen: Ein Projekt hat diesen Vermerk zweimal von Hand
gebaut und ist beide Male verlustfrei wieder eingestiegen.

**Kosten je Rolle sind unzuverlässig; belastbar ist die Summe je Phase.** Die
Guthaben-Abfrage hinkt nach, parallele Rollen überlappen — gemessen standen
Einzelzeilen auf 0,0000 bei laufender Arbeit.

**Eine stumme Rolle braucht ein Lebenszeichen und ein Zeitlimit.** Gepufferte
Ausgabe ist von einem Hänger nicht zu unterscheiden: gemessen 25 Minuten ohne
eine Zeile, und auf einem anderen Rechner vier Läufe ohne ein einziges Token —
beides sah von außen gleich aus.

## Wenn eine Stimme ausfällt

**Ausfall ist stimmen-neutral definiert — auch die eigene Stimme fällt aus.**
Gemessen: Eine blinde Claude-Stimme starb mitten im Lauf am Session-Limit —
kein Teilergebnis, kein Befund. Ein Kontingent-Abbruch ist ein AUSFALL und
steht als solcher unter der Überschrift der Stimme, nie als dünnes Ergebnis.
**Was dann geschieht, ist EINE Reihenfolge** (vorher standen hier drei Regeln
nebeneinander — Neustart, Ersatzregel, „mit zweien weitermachen" —, und keine
sagte, welche zuerst gilt):

1. **Zustand feststellen** wie nach einem abgebrochenen Bau.
2. **Gibt es eine Ersatzregel für diese Stimme, gilt sie** — für den
   Gegenprüfer bei R3 (unten, Klumpenrisiko Punkt 2) und für den
   **Fremdprüfer** (Klumpenrisiko Punkt 4: Kontingent des Werkzeugs gesperrt →
   sofort dieselbe Rolle über die API-Leitung eines anderen Anbieters, kein
   Warten auf das Fenster), gleich ob Kontingent oder Werkzeug ausfiel. Ist
   auch die Ersatzstimme ausgefallen — Werkzeug oder Leitung nicht
   erreichbar, Fehlerantwort: alles außer Guthabenende und außer dem
   Token-Budget —, weiter mit Schritt 3. Eine leere oder abgeschnittene
   Antwort ist kein Kontingentfall, aber **der Grund entscheidet das Mittel**:
   bei `finish_reason` „length" ist das Token-Budget aufgebraucht — **einmal**
   mit größerem `--max-tokens` auf demselben Commit wiederholen; bei jedem
   anderen Grund (etwa „error") liegt es am Anbieter — **einmal unverändert**
   wiederholen. Ein größeres Budget hilft dort nicht und kostet einen zweiten
   bezahlten Lauf (gemessen an einer echten Leitung). Bleibt es dabei, ist es
   ein Ausfall wie jeder andere (Schritt 3). Meldet
   die Ersatzleitung des Fremdprüfers dagegen Guthabenende (HTTP 402, oder
   eine Antwort unter **irgendeinem** Code, die eine ausdrückliche Phrase
   trägt — „insufficient_quota", „out of credits" und Verwandte; ein 429, das
   nur „quota" im Text führt, ohne eine dieser Phrasen, ist Ratenbegrenzung
   und bleibt Schritt 3), gilt Klumpenrisiko Punkt 4 — Owner fragen, nicht ohne
   Panel ausliefern — **statt** Schritt 3 (kein Neustart ins
   nächste Fenster) und statt des „Weitermachens" aus Schritt 4; die
   Auslieferung richtet sich dann nach dem Schluss von Schritt 4: Nachholen
   oder ausdrückliche Owner-Freigabe (Anwendung des Owner-Entscheids vom
   2026-09-19 zur 402-Folge, eingetragen 2026-09-21).
3. **Sonst Neustart gegen denselben festen Commit, mit dem archivierten
   Prüfauftrag, im nächsten Kontingentfenster** — nicht sofort. Ein Neustart ins
   selbe erschöpfte Kontingent stirbt wieder: gemessen zweimal hintereinander
   dieselbe Stimme in derselben Runde.
4. **Kann der Slice nicht warten**, geht es mit den übrigen Stimmen weiter,
   der Owner erfährt es, und die fehlende Stimme wird nachgeholt, solange der
   Slice nicht ausgeliefert ist (unten) — **ausgeliefert wird erst nach dem
   Nachholen oder mit ausdrücklicher Owner-Freigabe ohne die Stimme**
   (`../../CLAUDE.md`, Review-Panel). **Mindestens eine Stimme muss gelaufen
   sein** — fällt die einzige Stimme einer Runde aus (in der Nacharbeit meist der
   Blindprüfer), gibt es kein „weiter", sondern nur Schritt 3. Gemessen: Genau
   so — weiter mit den übrigen — wurde einmal ein Seitenkanal gefunden, den die
   anderen beiden übersehen hatten; das Weitermachen ist kein Notbehelf, es
   ersetzt nur die fehlende Stimme nicht.

**Diese vier Schritte stehen NUR hier.** `../../CLAUDE.md`,
`panel-kommentar.md`, der Abschnitt „Verfahren je Risikoklasse" unten und der
Kopf von `../vorlagen/panel-stimme3.py` verweisen auf sie und schreiben sie
nicht aus. Eine Ausnahme ist gewollt und benannt: Die **Ausfallmeldungen** in
`panel-stimme3.py` fassen die Folge kurz, weil sie im Ausfall gelesen wird,
wenn niemand nachschlägt — wer diese Schritte ändert, ändert die Meldungen
mit. Das Suchwort dafür ist **„Stimme ausfaellt"** (`grep -rn "Stimme
ausfaellt" docs/vorlagen/`): Es findet alle Stellen, auch `GUTHABEN_MELDUNG`,
die die Folge am vollständigsten kurzfasst. „max-tokens" allein findet sie
nicht (gemessen). Dreimal hat eine Änderung an dieser Reihenfolge andere Fassungen
stehen lassen (v1.15.10, v1.15.11 — und v1.16.0 selbst, gefunden vom
Gegenprüfer: der Schnitt, der die Entdopplung einführt, ließ genau hier die
alte Fassung des Budgetfalls stehen). Ein Kind-Repo erbt die Verweise; wer
diese Schritte ändert, ändert sie hier und prüft mit `grep`, dass keine
andere Stelle sie ausschreibt.

**Panel-Stimme ≠ Messreihe** (Owner-Entscheid v1.15.0). Eine ausgefallene
Panel-Stimme wird nach der Reihenfolge oben ersetzt oder neu gestartet, weil ein
Slice ohne sie nicht geprüft ist. Ein
ausgefallener Lauf einer **Mess- oder Bewertungsserie** (dieselbe Frage n-mal,
um Streuung zu messen) wird **markiert und nie ersetzt** — wer schlechte
Serienläufe wiederholt, bis das Ergebnis passt, misst seinen Wunsch
(`lehren.md` §27).

**Klumpenrisiko (Gegenprüfer bei R3, Fremdprüfer ab R2):** Seit der
Gegenprüfer-Regel hängen zwei von drei Stimmen am selben Kontingent. Vier
Antworten darauf — **Pflicht, nicht Option** (die vierte gilt ab R2, weil der
Fremdprüfer schon dort Pflichtstimme ist):
Gemessen wurde keine der ersten drei angewandt, als drei Slices parallel am selben
Kontingent hingen, und die Runden blieben offen:

1. Bei knappem Kontingent laufen die beiden Claude-Stimmen ZUERST, die
   Fremdstimmen danach.
2. **Ersatzregel Gegenprüfer:** Fällt der Gegenprüfer aus — am Kontingent oder am
   Werkzeug —, übernimmt der
   Fremdprüfer die Widerlegungsrahmung in einem zweiten Lauf **mit vollem
   Quelltext-Zugriff**. Die Regel schreibt das ERGEBNIS vor, nicht den
   Transport — Review-Branch, Commit-Snapshot oder Quelltext inline sind
   gleichwertig, solange die Quelle `git show HEAD:`-Stand ist (Quellen-Regel
   gilt unverändert). **Die Ersatzregel ist eine Aussage über den Transport,
   keine Ausnahme von der PII-Grenze:** Was einer Fremdstimme nicht gegeben
   werden darf, darf ihr auch inline nicht gegeben werden — wer nur eine der
   beiden Regeln liest, darf sie nicht als Aufhebung der anderen lesen können. Real belegt: In einer Sandbox ohne Datei-Zugriff trug
   die Inline-Variante den einzigen echten Treffer der Runde. Teurer, aber
   definiert statt improvisiert.
3. Die bestehende Regel „Panel nie auf den letzten Moment" wiegt bei R3
   doppelt.

**Bei uns ist das Klumpenrisiko nicht theoretisch:** Unsere R3-Besetzung ist
Blindprüfer + Fremdprüfer + Gegenprüfer — zwei der drei Stimmen hängen am
selben Claude-Kontingent. 4. **Ersatzregel Fremdprüfer** (Owner-Entscheid 2026-09-19, angewandt in vier
Schnitten der Vorlage, bis v1.15.7 nur in der Historie): Sperrt das
Abo-Kontingent den Werkzeug-Weg des Fremdprüfers, wird **nicht gewartet** —
dieselbe Rolle läuft sofort über die API-Leitung eines anderen Anbieters,
bevorzugt agentisch mit Nur-Lese-Zugriff auf den Prüfbaum
(`docs/vorlagen/panel-stimme3.py` ist die diff-only-Form; eine agentische
Form liest Dateien selbst), Modellwahl: erst das gewohnte Fremdmodell auf
der anderen Leitung, sonst ein anderes Nicht-Claude-Modell — Pflicht bleibt
„anderer Anbieter als die Claude-Stimmen". Ein Ausfall ist keine Verkürzung
des Panels. Antwortet die Leitung mit „Guthaben erschöpft" (HTTP 402 oder
eine Meldung, die `panel-stimme3.py` ihm gleichstellt), wird der Owner
gefragt, nicht ohne Panel ausgeliefert. Grenze: Eine
diff-only-Fremdstimme sieht keinen Dateibaum — für Behauptungen über
Dateien, die der Diff nicht zeigt, braucht es die agentische Form oder den
Neustart nach Schritt 3. Gemessen: Die Ersatzstimme fand in v1.15.3 exklusiv
einen vom Orchestrator verstümmelten Satz und in v1.15.7 dieselbe Lücke wie
beide Claude-Stimmen; zweimal brach sie am Antwort-Längenlimit ab (Neustart
mit größerem Budget auf demselben Commit).

Fällt eine dieser Stimmen aus, gilt „Wenn eine Stimme ausfällt" oben —
einschließlich des Sonderfalls Guthabenende (Punkt 4 dort ist die Ersatzregel,
die Folge steht in Schritt 2 der Reihenfolge).

## Verfahren je Risikoklasse

**Die Auslöser-Tabelle besitzt `../../CLAUDE.md`** — dort wird entschieden,
welche Klasse ein Slice hat. Hier steht nur, was je Klasse zu tun ist:

- **R0** — lokale Gates genügen. Kein Panel-Kommentar nötig; der Commit nennt
  den R0-Auslöser.
- **R2** (Normalfall) — Blindprüfer + Fremdprüfer, fester Panel-Kommentar.
  Die dritte Stimme ist bei R2 optional; wird sie weggelassen, steht der Grund
  unter ihrer Überschrift. **Welche dritte Stimme, macht den Unterschied**
  (präzisiert v1.15.0 — bis dahin stand hier pauschal „Konvergenz-Lieferant,
  kaum exklusive Funde", und das stimmt nur für eine der beiden):
  die **diff-only-Fremdstimme** liefert Konvergenz und kaum Exklusives; der
  **Gegenprüfer** lieferte in einem R2-Slice die meisten exklusiven Funde des
  Panels — 13, davon 5 Blocker, darunter als einziger den Erst-Rollout-Fehler
  für Bestandsnutzer. Er ist bei R2 eine Ermessensentscheidung mit
  Messzeile, keine Pflicht (Kosten!), und die naheliegende Wahl bei
  Zustands-, Rollout- und Datenschutzfragen.
- **R3** — volles Panel **plus eine risikospezifische Probe durch die echte
  Tür** (Migrations-Datenerhalt, Berechtigungs-Sonde, Geld-Rundungsfall,
  Schnittstellen-Aufruf von außen — je nach Auslöser). **Die dritte Stimme ist
  bei R3 der Gegenprüfer** — eine zweite blinde Claude-Repo-Stimme mit
  Widerlegungsauftrag (Aufsichts-/Angreifer-Perspektive), keine
  diff-only-Fremdstimme. Beleg aus dem Drei-Arm-Pilot (zwei Projekte, vier
  R3-Runden; dort hieß der Gegenprüfer „Arm C"): Die zweite Repo-Stimme
  fand in JEDER Runde exklusive Funde der Blocker-Klasse; die diff-only-Stimme
  konvergierte nur, die agentische Fremdstimme lieferte 0/3 Synthesen. Die
  befürchteten geteilten blinden Flecken zweier Claude-Stimmen traten nicht
  auf — die andere Rahmung klopft andere Ebenen ab. Die diff-only-Fremdstimme
  darf ZUSÄTZLICH laufen (billige Konvergenz-Gegenprobe), zählt aber nicht als
  dritte Stimme (eigene Überschrift „Zusätzlich, nicht gezählt" in
  `panel-kommentar.md`). Inzwischen zwölf R3-Runden in Folge mit einer exklusiven
  Blocker-Klasse aus der zweiten Repo-Stimme; die Rahmung darf dabei auch das
  reale Schadensszenario sein („ein Inhaber, der Ratenrechnungen schreibt und
  nachkorrigiert") statt „Angreifer" — daraus fiel ein dritter Weg heraus, den
  beide anderen Stimmen nicht sahen. Bei Fremdcode ist sie die richtige
  Besetzung (`bau-brief.md`, Typische Fallen).
  **Die Tür-Probe braucht die Tür:** Bei Anwendungen mit Anmeldung ist ein
  geheimnisfreier Auth-Pfad (`betrieb.md`) keine Bequemlichkeit, sondern die
  Voraussetzung dafür, dass die R3-Regel erfüllbar ist — der Agent tippt kein
  Geheimnis, auch nicht auf einem Wegwerf-Stand. Fehlt der Pfad, probt man die
  Tür bis zur Klinke: Anwendung baut, mountet, Anmeldebildschirm rendert — und
  genau das, was der Slice sichtbar ändert, wurde nie im laufenden Bild
  gesehen. Dann steht unter der Überschrift **„Tür-Probe (R3/R4)"** in
  `panel-kommentar.md` **„teilweise ausgefallen"** mit dem Grund, wie bei
  einem Werkzeugausfall. Die Folge ist eine Schwelle und steht deshalb in
  `../../CLAUDE.md`, Review-Panel: dieselbe wie bei einer ausgefallenen
  Pflichtstimme.
  **Bei uns ist genau das der Normalfall, solange #75 offen ist:** Ohne
  geheimnisfreien Auth-Pfad reicht die Probe bis zur Anmeldemaske und nicht
  weiter. Der Owner hat den Pfad am 22.09.2026 beauftragt (#75); bis er steht,
  trägt jede R3-Probe hier den Vermerk. Ein Ersatzpfad ist eine andere
  Messung, kein schwächeres Ergebnis derselben.
- **Nacharbeit, gleich welcher Klasse** (früher die Verkürzung „R1"): Schwelle
  in der Tabelle (`../../CLAUDE.md`, Zeile _Nacharbeit_), Verfahren oben unter
  Schritt 4. Die Begründung, warum eine Stimme in der Nacharbeit nicht lief,
  steht unter ihrer Überschrift, nicht als Fließtext.
- **R4** — wie R3, und der Slice landet erst nach ausdrücklicher
  Owner-Freigabe. Version/Release bleiben bis dahin unangetastet.

Die frühere abschließende Trivial-Liste ist unverändert in die R0-Auslöser
übergegangen, die Pflichtfälle in die R3-Auslöser — **die Schwellen selbst
stehen nur noch in der Tabelle**, nicht mehr hier (Eigentümer-Regel).

## Kritische Dateien: die Klasse folgt der Datei, nicht dem Diff

Die Schwelle setzt die Tabelle in `../../CLAUDE.md` (Auslöser „kritische
Dateien" → R3, unabhängig von der Diffgröße — auch eine Zeile). Dieser
Abschnitt führt nur die Liste und den Grund; Besetzung, Untergrenze, Tür-Probe
(hier: die Echtprobe) und Nacharbeit gelten wie bei jedem R3:

- der Prod-Lesewächter und seine Konfiguration (`docs/vorlagen/prod-readonly-hook.py`,
  `.json`) und die Einträge in den Agenten-Einstellungen, die ihn rufen;
- die Gate-Probe und ihre Selbstprobe (`docs/vorlagen/waechter-gate-probe*.py`);
- alles, was im lokalen Gate, in der CI oder im Panel ein Urteil fällt:
  `ci.yml`, `security-scan.yml`, `scripts/*`, Gate- und Release-Skripte des
  Projekts, die Stimme-3-Vorlage (`docs/vorlagen/panel-stimme3.py`) und jede
  Panel-Stimmen-Anbindung; **`docs/vorlagen/ast-gleich.py`**, weil sein Urteil
  über die Größe des nächsten Panels entscheidet — sonst dürfte es sich mit
  dem eigenen Urteil herunterstufen;
- Prüfskripte, die Panel oder Bau-Brief absichern (`scripts/bau-brief-pruefen*.sh`).

Faustregel für alles, was hier nicht steht: **Was Befehle ausführt oder
Urteile fällt, ist kritisch** — im Zweifel die höhere Klasse (`CLAUDE.md`).

**Reine Kopftext-Änderung → R2** (Owner-Entscheid 2026-09-21). Den Auslöser
setzt die Tabelle in `../../CLAUDE.md`; hier stehen Bedingungen, Verfahren und
Beleg. Ändern sich an einer kritischen Datei nur Kommentare oder Docstrings,
läuft der Schnitt mit Blindprüfer und Fremdprüfer statt mit dem vollen
R3-Panel. Bedingungen, alle drei:

1. **Der Syntaxbaum ohne Docstrings ist gleich** — gemessen, nicht behauptet:
   `python docs/vorlagen/ast-gleich.py <alt.py> <neu.py>`; das Ergebnis steht
   im Panel-Kommentar. Ändert sich der Baum auch nur um eine Konstante, ist es
   keine Kopftext-Änderung mehr.
2. **Die Tür-Probe bleibt** — unverändert, wie bei jedem R3. Ein Kopftext, der
   die Datei nicht anfasst, ändert auch nichts an ihrer Tür; die Probe kostet
   also wenig und belegt, dass die Kopie läuft.
3. **Die Nacharbeit folgt weiter ihrer eigenen Zeile** in der Tabelle.

Der Grund ist gemessen, nicht geschätzt: In den beiden reinen Textschnitten
v1.15.9 und v1.15.10 fand der Gegenprüfer nichts, was der Blindprüfer nicht
auch fand; im Code-Schnitt v1.15.11 fand er den Blocker allein (eine
Erkennungsliste aus Einzelwörtern, die gewöhnliche Ratenbegrenzungen als
Guthabenende gemeldet hätte). Die Widerlegungsrahmung zahlt sich am Verhalten
aus, nicht am Kommentar.

Gemessen: Die Korrektur eines Ein-Zeilen-Funds am Wächter (v1.15.4) brauchte
sechs Panel-Runden, weil jede Runde die Gate-Probe erneut schlug — als
„KORREKTUR" nach Änderungsart wäre sie mit zwei Stimmen gelaufen. Ein
fremdes Hook-Projekt führt dieselbe Liste als „Tier 1: Shell-Ausführung,
Hook-Skripte, Rewrite-Registry" mit Pflicht-Zweitreview; die Klasse ist
dieselbe: Was Befehle ausführt oder Urteile fällt, prüft niemand allein.

## Stimmen-Besetzung nach Diff-Typ

Der Panel-UMFANG folgt der Risikoklasse; die STIMMEN-BESETZUNG folgt dem
Diff-Typ. Gemessen über sieben Slices in zwei Projekten:

- **Backend-Logik** — Fremdprüfer und dritte Stimme tragen (exklusive Funde,
  unabhängige Konvergenz). Volle Besetzung nach Klasse.
- **Frontend/Anzeige-Text** — der Blindprüfer ist die einzige tragend
  gemessene Stimme (drei exklusive Funde bei einem „nur Labels"-Diff);
  diff-only-Fremdstimmen sind hier nachweislich stumm.

Ob und wie weit deshalb verkürzt werden darf, sagt die **Untergrenze** in
`../../CLAUDE.md` (Review-Panel) — dieser Abschnitt setzt keine eigene
Schwelle. Wer innerhalb dieser Grenze nach Diff-Typ von der Klassen-Besetzung
abweicht, schreibt den Diff-Typ und den Grund unter die Überschrift der
ausgelassenen Stimme — und nennt beides in der Bilanz, damit die Messreihe
weiterwächst.

**Bei uns unmittelbar relevant:** Unser Repo ist gemischt (FastAPI-Backend +
React-Frontend), die Regel entscheidet also bei jedem Produkt-Slice mit — ein
frontend-lastiger R2-Slice bekommt danach eine Stimme statt zwei. Das ist eine
Besetzungsentscheidung nach gemessenem Diff-Typ, kein Freibrief, die dritte
Stimme generell wegzulassen.

## Vorabprüfung: nicht „antwortet sie?", sondern „kann sie etwas ausführen?"

Die übliche Vorabprüfung („sag OK") testet den Modell-Aufruf, nicht die
Werkzeuge dahinter. Gemessen: Ein containerisierter Fremdprüfer konnte
**keinen einzigen Befehl ausführen** (`bwrap: No permissions to create a new
namespace`) — das Modell lief normal, die Vorabprüfung war grün.

Eine Stimme, die nichts ausführen kann, aber weiter antwortet, liefert ein
Ergebnis, das äußerlich wie ein geprüftes aussieht: gleiche Form, gleiche
Schwere-Angaben, gleicher Tonfall — ohne einen ausgeführten Befehl darunter.
Im gemessenen Fall ging es gut, weil das Modell den Ausfall selbst erkannte und
offenlegte. **Das war Sorgfalt des Modells, nicht Eigenschaft des Verfahrens.**

**Regel:** Die Vorabprüfung setzt einen BEFEHL ab, dessen Ausgabe zurückkommen
muss — und zwar einen, der in der Umgebung der Stimme sinnvoll ist: im
Worktree `git rev-parse HEAD` gegen den erwarteten Stand; im `git archive`-Baum
des Gegenprüfers (kein `.git`, unten) ein Befehl auf die mitgelegte
Diff-Datei, etwa `wc -l <diff-datei>` gegen die bekannte Zeilenzahl. Kommt die
Ausgabe nicht, ist die Stimme ausgefallen und der Ausfall-Vermerk gilt.

**Und in der Ergebnisform:** Konnte eine Stimme ihre Werkzeuge nicht nutzen,
steht das **unter ihrer Überschrift**. Eine Freigabe aus reiner Lektüre ist
etwas anderes als eine aus Reproduktion, und der Unterschied gehört in den
Kommentar, nicht nur ins Gedächtnis des Arbiters.

**Bei uns bereits scharf geworden:** Genau dieser Fehler ist hier passiert. Der
Trivialruf an den Fremdprüfer ging durch, weil er keinen Dateizugriff
brauchte; der echte Prüfauftrag scheiterte danach an `bwrap`-Rechten im
Sandbox-Container. Unser Vorabprüf-Befehl ist deshalb nicht „sag Hallo",
sondern einer, dessen Ausgabe zurückkommen muss:

```bash
sh /c/Users/manue/.claude/Immich/model-panel/codex.sh exec --skip-git-repo-check -c 'model_reasoning_effort="high"' 'git rev-parse HEAD'
```

## Stimmen mit Repo-Zugriff arbeiten in eigenen Worktrees

Der Blindprüfer bekommt einen eigenen `git worktree` auf dem gemessenen
Commit, der Gegenprüfer einen `git archive`-Baum desselben Commits (Absatz
„Der Gegenprüfer misst in einem `git archive`-Baum" unten); Mutationen und
Container tragen ein stimmen-eigenes Präfix, das
Aufräumen wird nachgewiesen. Der Hauptagent darf den Hauptbaum währenddessen
weiterbewegen.

**Eine Stimme, ein Worktree — je Runde, und der Orchestrator editiert dort
nie.** Vor dem Start ist der Worktree leer (`git status --short --ignored`)
**und kein eigener Lauf mehr offen, der in diesen Baum schreibt** (Bauer,
Probe, Gate — andere Panel-Stimmen zählen nicht, die laufen bewusst parallel;
`lehren.md` §37). Ein Worktree wird **nie umgehängt**, solange die Stimme
leben kann: Eine Stimme, die ihren Bericht mit noch offener Hintergrundarbeit
abgibt, gilt als laufend — der Orchestrator hat einmal danach denselben Baum
für die nächste Runde umgehängt, und die alte Stimme meldete „der Worktree hat
sich bewegt" (v1.15.4, Nacharbeit 5; jede Messung auf sauberem Baum, aber am
alten Stand). Neue Runde, neuer Worktree; eigene Nacharbeit
committet der Orchestrator in SEINEM Baum und zieht den Branch danach nach, nie
in den Baum einer laufenden Stimme. Gemessen: Die Rückbau-Mutation einer Stimme
(`git checkout -- <datei>`) löschte uncommittete Nacharbeit des Orchestrators
mit, die in denselben Baum geschrieben worden war — und die nächste Stimme
brach ab.

**Der Gegenprüfer misst in einem `git archive`-Baum** des gemessenen Commits,
nicht in einem Worktree: Eine Stimme hatte die Worktree-Anweisung ignoriert und
im geteilten Baum gearbeitet. Ein Archiv hat kein `.git`, in das man
zurückschreiben könnte. Weil ein Archiv auch keine Historie hat, bekommt der
Gegenprüfer den Vergleichsbereich als Datei mit (`git diff <basis>..<commit>`
neben das Archiv gelegt, im Prüfauftrag benannt).

Gemessen: Ein Blindprüfer lief im Hauptbaum, während dort Nacharbeit
einfloss — ihr Bericht beginnt mit „Der Prüfgegenstand hat sich während des
Reviews bewegt", und sie musste zwei Stände auseinanderhalten. Zwei Stimmen mit
Mutationstests im selben Baum kollidieren zusätzlich.

Der Nebeneffekt ist der eigentliche Gewinn: **Die Nacharbeit kann beginnen,
bevor die letzte Stimme fertig ist** — die Stimmen prüfen den Commit, nicht den
Baum. Das ist die Quellen-Regel unten zu Ende gedacht. Gemessen in zwei
Projekten: Der Gegenprüfer meldete um 21:12, die Nacharbeit begann in
derselben Minute, die übrigen Stimmen fanden trotzdem sauber, weil sie einen
Commit prüften. Kosten: `git worktree add --detach <pfad> <commit>` und ein
`remove` am Ende.

Unsere Form davon:

```bash
git worktree add --detach ../immich-family-tools-panel-<stimme> <commit>
# … Stimme prüft dort …
git worktree remove ../immich-family-tools-panel-<stimme>
```

**Belegt:** Im Slice vom 01.09. hat der Arbiter während laufender Stimmen im
selben Arbeitsbaum gearbeitet.

_(Für Mess- und Bewertungs-SERIEN gilt das Gegenteil: Dort wird keine Ausgabe
gelesen, bevor alle Läufe persistiert sind — sonst beeinflusst das erste
Ergebnis, wie die übrigen gelesen werden. Das Panel ist keine Serie; `lehren.md`
§27.)_

**Wer vor der letzten Stimme mit der Nacharbeit beginnt, führt eine Tabelle
_Befund → Stimme → gegen welchen Stand → Ergebnis_ mit.** Die später
eintreffende Stimme prüft einen Stand, der schon überholt ist; je Befund muss
die Synthese entscheiden, ob er bereits behoben ist. Bei zwei parallelen
Nacharbeitsrunden ist die Tabelle Pflicht, nicht Kür — sonst verliert die
Synthese den Überblick, welcher Befund gegen welchen Stand gemessen wurde.

_(Zur Formulierung der Quellen-Regel unten: Ein Worktree auf dem gemessenen
Commit ist ein definierter Zustand, kein „Arbeitsbaum" im Sinne der Regel —
gemeint ist der geteilte HAUPTarbeitsbaum, in dem mutiert wird. Eine Stimme
hatte den Widerspruch gemeldet, eine andere ihn widerlegt; das begründete
Urteil gewinnt.)_

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
auf GitHub). Eine Fremdstimme, die bei einem Werkzeugausfall im Netz nachsieht,
findet das Repo und den Commit — und liest dann einen anderen Stand als den
geprüften, ohne dass das im Ergebnis sichtbar wird. Das Suchverbot ist hier
kein allgemeiner Vorsatz, sondern verschließt einen konkreten, erreichbaren
Fehlerpfad.
