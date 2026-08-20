# Vorlage: Panel-Kommentar

Kopiervorlage für das Panel-Ergebnis am Issue. **Die Form ist der Mechanismus** —
eine leere Überschrift springt ins Auge, ein fehlender Absatz nicht. Deshalb
bleiben alle drei Stimmen stehen, auch wenn eine nichts gefunden hat oder
ausgefallen ist.

Nicht kürzen, nicht zu Fließtext zusammenfassen, keine Stimme weglassen.

**Modell und Stand gehören in jede Stimmen-Überschrift**, z. B.
`### Stimme 2 — GPT über Codex (gpt-5.5, 2026-08-19)`. Sonst ist die
Herkunfts-Regel nach vier Wochen nicht mehr durchsetzbar — „wer hat das
geprüft" steht nirgends — und jede Aussage über Modellverhalten bleibt
Anekdote, solange das einzelne Ergebnis den Modellstand nicht trägt. Anbieter
ziehen still nach, deshalb das Datum.

---

```markdown
## Panel ⟨Slice / Issue⟩

Basis: `⟨commit-a⟩..⟨commit-b⟩` · Umfang: ⟨was geprüft wurde⟩

### Stimme 1 — blinde Erststimme (⟨modell⟩, ⟨datum⟩)

⟨Frischer Reviewer-Subagent: nur Diff + Repo, kein Bau-Brief, kein Bericht des
Bauers. Je Fund: Schwere, Datei:Zeile, Nachweis. „Keine Funde" ist ein
gültiges Ergebnis und wird hingeschrieben.⟩

### Stimme 2 — unabhängiges Modell (⟨modell⟩, ⟨datum⟩)

⟨Über denselben Diff, eigener Review-Zweig.⟩

### Stimme 3 — Drittstimme (diff-only) (⟨modell⟩, ⟨datum⟩)

⟨Kurz. Bekanntes Muster: irrt Richtung zu-streng, liest gelegentlich die
Vorher-Seite eines Diffs.⟩

### Arbitrierung

⟨Je Fund: reproduziert oder verworfen — und WIE reproduziert (Kommando, Test,
Messung). Dazu die Attribution: welche Stimme hatte ihn, welche nicht.
Prüfer-Konvergenz ersetzt keine Reproduktion.⟩

**Urteil:** ⟨landen / nacharbeiten⟩
```

---

## Wenn eine Stimme fehlt

Überschrift **stehen lassen**, Grund darunter:

```markdown
### Stimme 3 — Drittstimme (diff-only)

Ausgefallen: kein Guthaben. Owner informiert am ⟨Datum⟩. Nachzuholen, solange
der Slice nicht ausgeliefert ist.
```

Ein Slice ohne vollständiges oder so vermerkt-verkürztes Panel gilt als **nicht
geprüft** und wird nicht ausgeliefert.
