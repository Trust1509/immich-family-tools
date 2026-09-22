# Vorlage: Panel-Kommentar

Kopiervorlage für das Panel-Ergebnis am Issue. **Die Form ist der Mechanismus** —
eine leere Überschrift springt ins Auge, ein fehlender Absatz nicht. Deshalb
bleiben alle drei Stimmen-Überschriften stehen, auch wenn eine Stimme nichts
gefunden hat, ausgefallen ist oder bei dieser Risikoklasse nicht besetzt wurde;
bei R3 und R4 ebenso die Überschrift der Tür-Probe.

Nicht kürzen, nicht zu Fließtext zusammenfassen, keine Überschrift weglassen —
auch nicht die einer gelaufenen Zusatzstimme (optionaler Block unten in der
Vorlage).

Der Kommentar endet mit der Zeile **„Eigene Läufe am Ende: …"** (`lehren.md`
§37): Hintergrundläufe des Orchestrators sind erlaubt, unbemerkte nicht.
Derselbe Satz gehört in den Prüfauftrag jeder Stimme, als Anweisung und nicht
nur als Formfeld: **„Beende jeden eigenen Hintergrundlauf VOR dem Bericht —
über seine Prozessnummer, nie über den Programmnamen — und nenne ihn in der
Schlusszeile."** Den Wortlaut führt `panel.md` („Pflichtzeile in jedem
Prüfauftrag"); hier steht er als Beispiel. Gemessen in einem Kind-Repo: Ein Blindprüfer
ließ eine Python-Sitzung vier Stunden offen und erwähnte sie nur als Nebensatz
— der Owner sah sie zuerst.

**Projekteigen — der Commit-Stempel:** Die Arbitrierung dieses Panels liefert
den Wert für `arbitriert=` im mehrteiligen `Built-With`-Stempel am Commit
(`bau-brief.md`, Block 7). Ohne ihn trägt der Commit eine Lücke, die niemand
später füllen kann.

---

```markdown
## Panel ⟨Slice / Issue⟩

Basis: `⟨commit-a⟩..⟨commit-b⟩` · Umfang: ⟨was geprüft wurde⟩
Risiko: R⟨n⟩ — Auslöser: ⟨aus Block 0 des Bau-Briefs⟩ · Diff-Typ:
⟨Erstbau | Nacharbeit⟩

Runde: ⟨Erstrunde / Nacharbeit N — Grenze siehe `CLAUDE.md`, Zeile „Nacharbeit"⟩

### Stimme 1 — Blindprüfer (⟨Modell, Datum⟩)

⟨Frischer Reviewer-Subagent: nur Diff + Repo, kein Bau-Brief, kein Bericht des
Bauers. Je Fund: Schwere, Datei:Zeile, Nachweis. „Keine Funde" ist ein
gültiges Ergebnis und wird hingeschrieben; „nicht entschieden — Probe X"
ebenfalls.⟩

### Stimme 2 — Fremdprüfer (⟨Modell, Datum⟩)

⟨Über denselben Diff, eigener Review-Zweig. In einer Nacharbeitsrunde:
„nicht eingesetzt — Nacharbeit, Blindprüfer genügt" oder der Grund, warum doch.⟩

### Stimme 3 — ⟨R2: diff-only-Fremdstimme oder Gegenprüfer / R3: Gegenprüfer⟩ (⟨Modell, Datum⟩)

⟨Gegenprüfer: Widerlegungsauftrag, eigener Baum. In einer Nacharbeitsrunde nur,
wenn eine neue Tür angefasst wurde — sonst hier die Begründung. Diff-only-Stimme:
kurz; bekanntes Muster: irrt Richtung zu-streng, liest gelegentlich die
Vorher-Seite eines Diffs.⟩

### Zusätzlich, nicht gezählt — ⟨diff-only-Stimme⟩ (⟨Modell, Datum⟩)

⟨Optional: nur, wenn neben den gezählten Stimmen eine diff-only-Fremdstimme
als Konvergenz-Gegenprobe lief (bei R3 erlaubt, `panel.md`, „Verfahren je
Risikoklasse"). Lief keine — auch wenn sie mit Guthabenende abbrach —,
entfällt dieser Block ohne Vermerk; lief eine, bleibt er stehen. Zählt mit
ihren Funden, nie mit ihrer Freigabe.⟩

### Tür-Probe (R3/R4)

⟨Nur bei R3/R4; bei R2 entfällt dieser Block. Was geprobt wurde (welche Tür,
auf welchem Stand, mit welchem Aufruf) — Ergebnis. Oder: „teilweise
ausgefallen — ⟨Grund, bis wohin geprobt⟩"; dann gilt die Folge aus `CLAUDE.md`,
Review-Panel: vor der Auslieferung nachholen oder ausdrückliche
Owner-Freigabe ohne sie, beides hier vermerkt.⟩

### Arbitrierung

⟨Je Fund: reproduziert / verworfen / umgangen (nicht entschieden) — und WIE
reproduziert (Kommando, Test, Messung, aus einer anderen Quelle als dem
Geprüften). Dazu die Attribution: welche Stimme hatte ihn, welche nicht.
Prüfer-Konvergenz ersetzt keine Reproduktion.⟩

**Orchestrator-Quote:** ⟨N von M bestätigten Funden trafen einen Text des
Orchestrators (Brief, Prüfauftrag, Issue-Text, Notiz)⟩

**Urteil:** ⟨landen / nacharbeiten / nach Nacharbeit 2: landen mit Folge-Issue #⟨N⟩ (nur Nicht-Blocker offen) / anhalten — Blocker nach Nacharbeit 2, Owner fragen⟩

**Eigene Läufe am Ende:** ⟨keine — oder: welcher Lauf, was er hält, gestoppt ja/nein⟩
```

---

## Wenn eine Stimme fehlt

Überschrift **stehen lassen**, Grund darunter. Die Schritte, auf die sich das
Muster beruft, stehen in `panel.md`, Abschnitt „Wenn eine Stimme ausfällt"
(vier nummerierte Schritte; Punkt 2 und 4 des Abschnitts „Klumpenrisiko" sind
die Ersatzregeln). **Wer `panel.md` im eigenen Repo in eigenen Worten führt,
nummeriert die Schritte dort** — sonst zeigt dieses Muster ins Leere
(gemessen in einem Kind-Repo: Verweis ohne Ziel, monatelang unbemerkt, weil er
nur im Ausfall gelesen wird).

```markdown
### Stimme 2 — Fremdprüfer

Ausgefallen: Kontingent des Werkzeugs gesperrt um ⟨Uhrzeit⟩ (kein Warten).
Schritt 2 (Ersatzregel Fremdprüfer): Ersatz über ⟨API-Leitung des anderen
Anbieters⟩, Modell ⟨Name⟩, agentisch/diff-only, gestartet ⟨Datum Uhrzeit⟩ auf
Commit ⟨SHA⟩ — Ergebnis unten. ⟨oder: Guthabenende auf der Leitung → Folge nach
`panel.md`, Klumpenrisiko Punkt 4; Owner gefragt am ⟨Datum⟩⟩

### Stimme 3 — Gegenprüfer (R3)

Ausgefallen: Sitzungslimit um ⟨Uhrzeit⟩.
Schritt 2 (Ersatzregel Gegenprüfer, nur R3): Fremdprüfer übernimmt die Widerlegungsrahmung
in einem zweiten Lauf — Ergebnis unten. ⟨oder: Fremdprüfer ebenfalls nicht
verfügbar, weiter mit Schritt 3⟩
Schritt 3: Neustart gegen denselben Commit ⟨SHA⟩ im nächsten
Kontingentfenster, Prüfauftrag archiviert unter ⟨Pfad⟩.
⟨nur wenn der Slice nicht warten kann — Schritt 4: Owner informiert am
⟨Datum⟩; ausgeliefert wird erst nach dem Nachholen oder mit seiner
ausdrücklichen Freigabe ohne diese Stimme.⟩
```

Ein Slice ohne vollständiges oder so vermerkt-verkürztes Panel gilt als **nicht
geprüft** und wird nicht ausgeliefert. Ein **Ausfall** ist keine Verkürzung —
siehe `CLAUDE.md`, Review-Panel.
