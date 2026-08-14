# Vorlage: Panel-Kommentar

Kopiervorlage für das Panel-Ergebnis am Issue. **Die Form ist der Mechanismus** —
eine leere Überschrift springt ins Auge, ein fehlender Absatz nicht. Deshalb
bleiben alle drei Stimmen stehen, auch wenn eine nichts gefunden hat oder
ausgefallen ist.

Nicht kürzen, nicht zu Fließtext zusammenfassen, keine Stimme weglassen.

---

```markdown
## Panel ⟨Slice / Issue⟩

Basis: `⟨commit-a⟩..⟨commit-b⟩` · Umfang: ⟨was geprüft wurde⟩

### Stimme 1 — blinde Erststimme

⟨Frischer Reviewer-Subagent: nur Diff + Repo, kein Bau-Brief, kein Bericht des
Bauers. Je Fund: Schwere, Datei:Zeile, Nachweis. „Keine Funde" ist ein
gültiges Ergebnis und wird hingeschrieben.⟩

### Stimme 2 — unabhängiges Modell

⟨Über denselben Diff, eigener Review-Zweig.⟩

### Stimme 3 — Drittstimme (diff-only)

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
