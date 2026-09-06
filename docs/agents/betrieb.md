# Betrieb: Sicherungen, Totmann-Schalter, Fehler-Sammlung

Die offenen Punkte dieses Projekts (Rückspiel-Probe, Totmann-Schalter,
Erreichbarkeits-Wächter) werden als Issue #54 geführt — dieses Dokument ist der
Maßstab, das Issue der aktuelle Stand.

Gilt ab dem Moment, in dem **echte Menschen echte Daten** in der Anwendung
haben — nicht früher, aber keinen Tag später. Ein Hobby-Projekt ohne Nutzer
braucht nichts davon; sobald jemand anderes darauf zählt, ist das hier die
billigste Versicherung im ganzen Prozess.

## Der Grundsatz

**Ein Erfolgssignal, das in der Anwendung selbst lebt, schweigt genau dann, wenn
es wichtig wäre.** Stirbt der Rechner, stirbt auch die Statusanzeige, die
gemeldet hätte, dass nichts mehr gesichert wird. Die Meldung muss von außen
kommen.

## 1. Sicherung — und die Probe

Eine Sicherung, die nie zurückgespielt wurde, ist eine Hoffnung, keine Sicherung.
Getroffen hat es andere reihenweise: die Datei war da, groß, täglich neu — und
beim Ernstfall unbrauchbar.

- **Automatischer Auszug** der Datenbank, verschlüsselt, mit Aufbewahrungsregel.
- **Probe-Rückspiel, mindestens vierteljährlich:** Auszug in eine
  **Wegwerf-Datenbank** einspielen und **fachlich stichproben** — bekannte
  Datensätze, eine Summe, ein Zeitraum. Nicht „Datei existiert", nicht
  „Rückspiel lief ohne Fehler". Beides kann grün sein, während der Inhalt fehlt.
- Nie in die laufende Datenbank zurückspielen, um zu testen.

## 2. Totmann-Schalter

Ein Dienst, der einen **Ping nach erfolgreichem Lauf** erwartet und Alarm gibt,
wenn er ausbleibt (selbst gehostet oder als Fremddienst). Die Umkehrung ist der
Punkt: Nicht der Fehler meldet sich, sondern **das Ausbleiben des Erfolgs**.

- Ping ans **Ende** des Sicherungs-Skripts, nach der letzten prüfenden Zeile.
- Nicht am Anfang und nicht in einer Zeile, die auch bei Teilerfolg erreicht wird.

## 3. Erreichbarkeit

Ein leichtgewichtiger Wächter, der die Anwendung von außen abruft. **Frequenz zum
Hoster passend wählen** — manche sperren die abrufende Adresse bei
Anfrage-Serien; dann lieber alle paar Minuten aus einem anderen Netz als
sekündlich aus dem eigenen.

## 4. Fehler-Sammlung

Lohnt ab dem ersten stillen Fehler im Betrieb. **Das Erkennungszeichen:** Man
holt einen Fehlerbericht von Hand aus den Container-Protokollen, weil sonst
niemand gemerkt hätte, dass etwas kaputt ist.

Eine schlanke, selbst gehostete Sammlung reicht (es gibt Varianten, die mit einem
halben Gigabyte auskommen und die verbreiteten Bibliotheken sprechen — die
Vollausbau-Variante desselben Werkzeugs braucht das Dreißigfache).

## Was Überkill ist

Voller Metrik-Stapel mit Zeitreihen-Datenbank, Protokoll-Sammler und
Dashboard-Sammlung: für eine Anwendung mit einer Handvoll Nutzern ist das mehr
Betriebsaufwand als Nutzen. Erreichbarkeit + Totmann-Schalter + Fehler-Sammlung
decken den Großteil ab; Protokolle liest man bei dieser Größe live im Container.

## Dieses Repo ist absichtlich öffentlich

Vier Dinge liegen dadurch anders als in einem privaten Projekt. Der Stand der
Plattform-Schalter und die Deckungs-Messung stehen in `CLAUDE.md`, Abschnitt
„Dieses Repo ist öffentlich", Unterabschnitt „Gemessen am 06.09.2026" — hier
stehen die Regeln, dort die Zahlen.

- **Geheimnis-Scan bekommen wir von der Plattform**, private Repos nicht.
  Secret Scanning und Push Protection sind für öffentliche Repos kostenlos;
  Push Protection greift **vor** dem Push und fängt damit eine Klasse, die
  ein nachgelagerter Scanner grundsätzlich nicht mehr fangen kann. Der eigene
  `gitleaks`-Lauf bleibt daneben stehen, weil er gemessen eine Klasse deckt,
  die die Plattform nicht deckt — nicht aus Gewohnheit.
- **Die PII-Grenze ist für Code gegenstandslos, für Daten scharf.** Der
  Quelltext ist ohnehin öffentlich; es gibt nichts zu schützen. Was zu
  schützen ist, sind **Daten**: Personennamen aus der Gesichtserkennung,
  E-Mail-Adressen echter Nutzer, Adressen von Instanzen. Die Schutzlinie sind
  damit die **Fixtures** — sie werden erfunden, nie übernommen
  (`bau-brief.md`). Ein Fixture-Wert, der ein echter Treffer sein könnte, ist
  in einem öffentlichen Repo eine Veröffentlichung, kein Testdatum.
- **Das Suchverbot an Fremdstimmen ist hier Integritätsschutz, nicht
  Vertraulichkeit.** Eine Stimme, deren Werkzeuge ausfallen und die dann im
  Netz nachsieht, findet unser Repo unter seinem echten Namen — und liest
  einen **anderen Stand** als den geprüften, ohne dass das im Ergebnis
  sichtbar wird. Begründung und Fall: `panel.md`, „Fremdstimmen".
- **Ein Test-Zugang gehört nie ins Repo**, auch nicht als „nur Testdaten".
  Deshalb hängt der geheimnisfreie Auth-Pfad (#75) und nicht ein hinterlegtes
  Konto.

**Bei einem Sichtbarkeitswechsel gilt eine Einmal-Prüfung.** Ein Repo, das
privat war und öffentlich wird, trägt seine gesamte Historie mit — und die ist
unter privaten Annahmen entstanden. Dann einmal, vor dem Umschalten: voller
Verlaufs-Scan (nicht nur der Arbeitsbaum), Fixtures gegen echte Werte lesen,
Issue-Texte und Commit-Nachrichten auf Adressen und Kontonamen prüfen. Für uns
ist das erledigt, aber die Regel steht hier, weil sie beim Wechsel gebraucht
wird und danach nie wieder — also genau dann, wenn niemand sie sucht.

**Und der Fall, an den niemand denkt: ein fremder PR läuft ohne Prüfung.**
Unsere `ci.yml` hat bewusst keinen `pull_request`-Trigger. Ein zugelieferter
PR wird damit **nicht** von der CI geprüft, bevor jemand ihn ansieht — das ist
Absicht (fremder Code soll keine Läufe in unserem Kontingent starten), aber es
heißt auch: Bei Fremdcode ersetzt nichts das Lesen. Fremdcode ist ein
R3-Auslöser; die Prüfung passiert im Panel, nicht im Trigger.

## Checkliste

- [ ] Automatischer Auszug läuft, verschlüsselt, mit Aufbewahrungsregel
- [ ] **Rückspiel-Probe terminiert** (Kalendereintrag, nicht Vorsatz)
- [ ] Totmann-Ping am Ende des Sicherungslaufs
- [ ] Erreichbarkeits-Wächter, Frequenz mit dem Hoster verträglich
- [ ] Fehler-Sammlung eingebaut (spätestens nach dem ersten stillen Fehler)
- [ ] Wiederherstellungs-Anleitung geschrieben — **und einmal befolgt**, nicht
      nur aufgeschrieben
