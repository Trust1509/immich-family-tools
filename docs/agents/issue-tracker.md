# Issues als Arbeitsspeicher

Der Chatverlauf ist flüchtig, der Kontext eines Agenten endet. **Was nicht in
einem Issue steht, ist verloren** — spätestens beim nächsten Fenster.

## Wann ein Issue

- Jeder Fund, der nicht im selben Slice behoben wird
- Jede bewusste Zurückstellung — **mit der Begründung**, sonst liest sie später
  jemand als Versehen
- Jede Entscheidung, die jemand sonst rückgängig macht, weil er den Grund nicht kennt
- Owner-Meldungen, auch die beiläufigen

## Was hineingehört

**Der Nachweis, nicht die Vermutung.** Ein Issue ohne Fundstelle und Messwert
erzeugt beim nächsten Agenten die Arbeit noch einmal.

- Befund mit `Datei:Zeile` und, wo möglich, gemessenen Zahlen
- Warum es durchgerutscht ist — oft wertvoller als der Fehler selbst
- Vorgeschlagener Zuschnitt, und was **nicht** dazugehört
- Bekannte Fallen für den Bau (siehe `lehren.md`)
- Abnahme: prüfbare Punkte, kein Fließtext

## Beim Schließen

Kommentar mit dem, was tatsächlich gebaut wurde — **inklusive der Panel-Funde und
der verworfenen Alternativen**. Das ist die Stelle, an der die Historie später
gesucht wird, nicht der Commit-Text.

## Zuschnitt

Lieber zwei ehrliche Issues als eines, das zwei Dinge vermischt. Wenn beim Bauen
auffällt, dass ein Teil fachlich anders funktioniert als der Rest: abtrennen und
begründen, statt „dasselbe nochmal" zu bauen.
