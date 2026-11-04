# Setup-Checkliste für ein neues Projekt

Einmalig nach dem Klonen. Der Agent führt durch, der Mensch entscheidet und
trägt Geheimnisse ein.

## 0. Skills prüfen (einmal pro Rechner, nicht pro Repo)

- [ ] `docs/agents/skills.md` durchgehen: Sind die Skills auf diesem Rechner
      installiert? Sie liegen global, ein frisch geklontes Repo bringt sie nicht
      mit — auch die Rollen, auf die `triage-labels.md` abbildet, kommen daher
- [ ] **`setup-matt-pocock-skills`** im neuen Repo ausführen (Issue-Tracker,
      Triage-Vokabular, Doku-Ablage)

## 1. Vorlage entschlacken

- [ ] `CLAUDE.md`: alle ⟨…⟩-Stellen ausfüllen, Vorlagen-Kasten oben löschen
- [ ] `README.md` durch eine echte Projekt-Beschreibung ersetzen
- [ ] `scripts/vorlage-gate.sh` **löschen** — das Gate der Vorlage selbst. Im
      Kind-Repo prüfte es mit `--vorlage-selbst` gegen die eigene Zählung (laut rot
      oder still grün, `abgleich.md` 2d); das Projekt führt sein eigenes Gate
- [ ] `docs/vorlagen/abgleich-auftrag.md` **löschen** — damit schreibt der Prozess-Agent
      seine Aufträge an die Kinder (`abgleich.md`), im Kind-Repo hat sie keinen Leser
- [ ] `docs/agents/lehren.md` **behalten** — die Fälle stammen aus einem anderen
      Projekt, die Klassen gelten trotzdem. Eigene Funde kommen dazu.
- [ ] Diese Datei **behalten** und abhaken — andere Papiere verweisen auf ihre
      Schritte (`triage-labels.md`, `lehren.md`); projektspezifische Schritte
      dürfen dazukommen

## 2. Issue-Tracker

- [ ] Labels anlegen: `needs-triage`, `needs-info`, `ready-for-agent`,
      `ready-for-human`, `wontfix` (siehe `triage-labels.md`)
- [ ] Entscheiden: werden externe Beiträge triagiert? (Bei privat: nein — beim
      Öffentlich-Gang umstellen und in `CLAUDE.md` vermerken)

## 3. CI

- [ ] CI scharf schalten: `mkdir -p .github/workflows && cp docs/vorlagen/ci.yml .github/workflows/`,
      dann an den Stack anpassen. (Liegt bewusst nicht schon aktiv in der Vorlage — eine CI,
      die zum Stack nicht passt, startet rot und erzieht dazu, rote Laeufe wegzuklicken.)
- [ ] **Alle** Prüfschritte in `CLAUDE.md` eintragen, damit Bau-Briefe sie
      vollständig nennen. Ein Schritt, den nur die CI kennt, wird lokal nie
      gefahren und meldet sich zum ungünstigsten Zeitpunkt.
- [ ] Läuft eine Prüfung gegen eine andere Datenbank als lokal? Dann prüfen,
      dass die Tests dort **wirklich** ankommen — ein Test, der die Datenbank
      durch eine andere ersetzt, prüft im entsprechenden Job nicht das Ziel.
- [ ] `concurrency` mit `cancel-in-progress` für Zweige, **ohne** für Tags, für
      Läufe, die ausliefern, und für Läufe, deren Abbruch gemeldet wird
      (Schwellen-Inventar in `CLAUDE.md`, Portfolio)
- [ ] **Das lokale Gate zählt seine Schritte und endet mit einer Schlusszeile**, wie
      `scripts/vorlage-gate.sh`. Ein Gate, das nur Exit-Codes verkettet, bleibt grün,
      wenn eine Zeile gestrichen wird (gemessen: kaputtes Werkzeug, gestrichene
      Zeile, Gate grün); `sh -u` statt `sh -eu` macht es auch bei roter Selbstprobe grün.
      **Gezählt wird im selben Aufruf wie der Befehl:** Ein Schritt zählt erst, wenn
      sein Befehl Exit 0 liefert **und** seine Erfolgszeile dasteht, mit Mindestzahl,
      wo das Werkzeug zählt (ein Typprüfer oder Linter ohne Zählausgabe braucht eine
      eigene Erfolgszeile, die nur bei Exit 0 gedruckt wird).
      Ein Zähler, der neben der Befehlsliste hochzählt, zählt Zeilen des Skripts,
      nicht gelaufene Prüfungen (Rückmeldung eines Projekts: Seine erste Fassung zählte
      so und blieb grün, als der Gegenprüfer Befehle strich).
- [ ] **Einen Lauf bis `conclusion=success` beobachten** (run-id-gepinnt), bevor
      die CI als eingerichtet gilt. „Workflow angelegt" ist kein Nachweis — zwei
      Prüfungen in einem Repo waren seit Tag eins rot, ohne dass es auffiel
- [ ] **Lokales Gate und CI benutzen dieselbe Quelle für Prüf-Abhängigkeiten**
      (eine Datei, nicht ein hartkodierter Aufruf), und Defaults zeigen nicht
      auf eine Laufzeit, die nur eine der beiden hat
- [ ] **Versions-Kommentar hinter einem Pin enthält NUR die Version** (`# v7.0.1`),
      nichts dahinter. Ein Zusatz wie `(SHA-gepinnt)` verhindert, dass der
      Abhängigkeits-Bot die Angabe nachführt — dann wandert der Pin weiter,
      während der Kommentar eine Version behauptet, die nicht mehr stimmt.
      Erläuterungen gehören in die Zeile darüber
- [ ] Fremde Bausteine auf **Commit-SHA** gepinnt (nicht `@v4`) — und beim
      Setzen geprüft, dass der SHA aus dem erwarteten Repo stammt
- [ ] Wochen-Prüfung scharf schalten: `cp docs/vorlagen/security-scan.yml .github/workflows/`
      — Abhängigkeits-Scan, Geheimnis-Scan, Schnittstellen-Fuzzing,
      Migrations-Kurzroundtrip. **Nicht** auf den Push-Pfad legen. Erstlauf von
      Hand anstoßen und die Befund-Welle einmal durchtriagieren.
- [ ] **Eigener Geheimnis-Scan im Wochenlauf** (Vollscan der Historie) — Job
      `geheimnis-scan` in `docs/vorlagen/security-scan.yml`. Er gilt zusätzlich
      zum Scan der Plattform, nicht statt seiner (`betrieb.md`, „Öffentliche
      Kind-Repos")
- [ ] Abhängigkeits-Bot: `cp docs/vorlagen/dependabot.yml .github/dependabot.yml`
      — Frontend-Ökosystem bewusst weglassen (Sperrdatei-Hauptversion!), dazu
      die Sicherheits-Aktualisierungen in den Repo-Einstellungen aktivieren
- [ ] Pfad-Filter: nur für Pfade, die nachweislich nirgends einfließen.
      Ausgelieferte Doku ist Produkt und wird **nicht** ausgenommen

## 4. Geheimnisse

- [ ] `docs/SECRETS.md` durchgehen, `.env.example` an den Bedarf anpassen
- [ ] GitHub-Secrets setzen (vom Menschen)
- [ ] Bei mehreren Projekten: Organisations-Secrets erwägen
- [ ] **Lokale Gate-Werkzeuge in derselben Hauptversion wie die CI** (Paketwerkzeug,
      Laufzeit) — oder das Gate läuft im Container der CI-Version. Jeder lokal
      übersprungene Schritt nennt im Gate sein Äquivalent.
- [ ] **Git-Hooks je Klon aktivieren** (`git config core.hooksPath <pfad>`) — die
      Einstellung reist nicht mit dem Repo; ein frischer Klon hat sonst keinen
      `commit-msg`-Hook, und der Überspring-Marker-Schutz aus Vorlage-Lehre §25
      wirkt nicht
- [ ] **Projektkennung im Rückmeldungs-Issue der aktuellen Vorlagen-Version
      anfordern** — zugeteilt und ins Register der Vorlage eingetragen wird sie
      dort (`abgleich.md`, Register), nicht in der eigenen Kopie; danach oben in
      `CLAUDE.md` eintragen

## 5. Panel-Werkzeuge

- [ ] `docs/agents/panel.md` › „Die Stimmen einrichten" durchgehen — dort steht,
      woher jede Stimme kommt, was sie kostet und wie sie aufgesetzt wird
- [ ] Prüfen, dass die Agenten-CLI **Subagenten** starten kann (ohne sie gibt es
      keinen Blindprüfer, und damit fehlt die stärkste Stimme)
- [ ] Zugänge/Guthaben der externen Modelle klären — eine Stimme, die erst beim
      ersten Panel ausfällt, kostet eine Runde
- [ ] Konkrete Kommandos in `panel.md` eintragen, damit sie kopierbar sind
- [ ] **Ort der Panel-Werkzeuge festlegen** (`docs/vorlagen/panel-stimme3.py`,
      `docs/vorlagen/ast-gleich.py`, `docs/vorlagen/lehren-verweise-pruefen.py`,
      `docs/vorlagen/baum-stoppen.sh` und Verwandte): im Repo oder portfolioweit in einem Verzeichnis neben
      den Projekten. Beides ist richtig; die Entscheidung gehört ins Abgleich-Issue,
      weil sie Folgen hat. **Ein Hash-Pin ist nur dort nötig, wo das Gate die
      Datei ohnehin liest** — ein Werkzeug, das außerhalb läuft, in die
      Pin-Prüfung aufzunehmen heißt, eine kritische Datei zu ändern (R3) für
      etwas, das im Gate gar nicht vorkommt (gemeldet aus einem Kind-Repo, das
      genau davor stand). Die Tür-Probe gilt unabhängig vom Ort
- [ ] **Byte-identisch übernommene Dateien aus den Formatier- und Lint-Gates
      ausnehmen** (`.prettierignore`, `.eslintignore`, `ruff`-exclude), mit der
      Begründung in der Ignorier-Datei. Warum, und was dabei nicht verloren
      geht, steht in `abgleich.md`, Absatz „Panel für den Abgleich-Commit" —
      hier steht nur der Handgriff
- [ ] **Jede Gate-Zeile, die ein Werkzeug der Vorlage oder ein eigenes Werkzeug
      nur mit Standardbibliothek startet, mit `-I -S`** — nicht nur die des
      Wächters. Ohne `-I` überschattet eine Datei neben dem Werkzeug die
      Standardbibliothek (gemessen: eine `tempfile.py` beendete das
      Verweis-Werkzeug mit Exit 0, das Gate meldete grün); ohne `-S` laufen
      `sitecustomize.py` und `.pth` mit. Die Werkzeuge der Vorlage verweigern
      seit v1.18.0 den Lauf ohne die Schalter (Exit 2) — mit einer Grenze: Ohne
      Schalter läuft `site` vor der Wache, eine `sitecustomize.py` aus
      `PYTHONPATH`, dem Benutzerverzeichnis oder dem `site-packages` des
      Interpreters kommt also davor, mit nur `-I` noch die aus dem
      `site-packages`. Dagegen hilft nur der Schalter selbst. Werkzeuge, die
      Pakete brauchen (pytest, alembic), laufen
      ohne `-S`; für sie gilt die benannte Grenze jedes Gates, das in der
      Umgebung seines Aufrufers läuft. Eigene Werkzeuge mit nur
      Standardbibliothek bekommen dieselbe Wache.
- [ ] **`lehren-verweise-pruefen.py` als eigene Zeile ins lokale Gate**
      (`--lehren <lehren.md>` plus die Dateien, die Verweise tragen). Ohne
      Gate-Zeile läuft es nur, wenn jemand daran denkt; dann ist es eine
      Empfehlung, kein Wächter. Die Selbstprobe (`--selbstprobe`) gehört
      daneben, wie bei der Gate-Probe. **Die Zeile bleibt einzeln fahrbar**, etwa
      über ein Argument des Gate-Skripts: Doku-Commits müssen durch sie, und wenn
      das nur über ein minutenlanges Gate geht, fällt sie weg.
      **Wer Gesetzesparagrafen oder andere fremde Zählungen in seinen Dateien
      führt, setzt `--ausser <muster>`** — sonst meldet der erste Lauf Zitate als
      Verweise ins Leere, und ein Werkzeug, das falsch alarmiert, wird
      abgeschaltet. Das Muster gehört **eng** gesetzt: Die Erfolgsmeldung nennt
      die Zahl der übersprungenen Zeilen **und die der dabei entfernten
      Verweise**, und beide gehören ins Abgleich-Issue. Nimmt die Ausnahme einen
      Verweis mit, der einen Abschnitt **trifft**, endet der Lauf mit Exit 1 —
      dafür ist sie nicht da. Die beiden Aufrufformen für ein Kind-Repo stehen in
      `abgleich.md`, 2d — **ohne** `--vorlage-selbst`, das gehört nur der Vorlage.
- [ ] **Prüfen, ob der eigene Vor-Commit-Hook FORMATIERT oder PRÜFT.** Ein Hook,
      der die gestageten Dateien in Form bringt, meldet nie einen Verstoß; der
      Konflikt mit dem CI-Gate wird dann erst nach dem Landen sichtbar. Und
      lokal auf einem Windows-Baum meldet ein Stil-Gate wegen CRLF ein
      Vielfaches der Dateien, die in der CI auffallen (gemessen: 26 gegen 3) —
      wer lokal prüft, gewöhnt sich das Hinsehen ab. Die CI ist hier die
      genauere Messung, nicht die strengere

## 6. Release

- [ ] Versionsführende Dateien festlegen und in `release-ritual.md` eintragen
- [ ] Release-Skript einrichten, inklusive **Gate „Version passt zu Notizen"**
- [ ] Rauchtest-Set anlegen: die wenigen Abläufe, die immer funktionieren müssen

## 7. Produktivzugriff (falls zutreffend)

- [ ] Darf der Agent gegen die Produktivinstanz arbeiten? Wenn ja: **nur lesend**,
      technisch erzwungen
- [ ] Wächter scharf schalten, in dieser Reihenfolge (Einzelheiten im Kopf von
      `docs/vorlagen/prod-readonly-hook.py`, „Scharf schalten"):
      1. **Konfiguration in der Quelle im Repo** anlegen und committen:
         `docs/vorlagen/prod-readonly-hook.example.json` nach
         `docs/vorlagen/prod-readonly-hook.json` kopieren, `prefix` und
         `allowlist` ausfüllen — sie ist die versionierte
         Projekt-Konfiguration. Präfix aus der Client-Konfiguration nachlesen,
         nicht raten; Allowlist der Lese-Werkzeuge **aufzählen** (nicht per
         Muster raten). „Lese-Werkzeug" heißt: **verändert keinen
         Fachbestand** (kein Anlegen, Ändern, Löschen fachlicher Daten) — nicht
         „verändert nichts": Lese-Werkzeuge mit technischem Seed (Einstellungen
         beim ersten Abruf anlegen, Modul-Initialisierung) schreiben auf einer
         nicht eingerichteten Instanz, und eine Zusage, die nur „praktisch"
         gilt, deckt ein Gegenprüfer auf (gemessen im P1-Abgleich). Solche
         Seeds beim Ausfüllen benennen (im Commit der Konfiguration; ein
         Bestandsprojekt im Abgleich-Issue) und aus dem Lesepfad in die
         Einrichtung verschieben, damit „nur lesend" wörtlich wahr wird.
         Das ist ein Punkt für Menschenhand — kein Gate macht ihn rot.
         **Wie man sie findet, wenn die Allowlist lang ist** (gemessen an 68
         Einträgen: jede Funktion zu lesen ist niemandes Feierabend): nicht
         nach dem NAMEN eines bekannten Seed-Helfers suchen, sondern nach der
         **Wirkung** — schreibende Aufrufe (`add`, `flush`, `commit`) in
         Funktionen, die „holen", „laden" oder „initialisieren" heißen —, und
         von dort die Aufrufer transitiv auf die Allowlist schneiden. Die
         Reihenfolge ist der Punkt: Wer beim bekannten Helfer beginnt, findet
         dessen Aufrufer und übersieht die zweite Quelle, die anders heißt;
         das Ergebnis liest sich dann wie eine vollständige Antwort. Gemessen
         in einem Kind-Repo, das seinen eigenen Vorschlag eine halbe Stunde
         später widerlegt hat. Die
         `.py` ändert das Projekt nie; jeder Fehler in der JSON-Datei
         (Syntax, falscher Typ, unbekannter oder doppelter
         Schlüssel, Eintrag ohne Präfix, leere oder fehlende Datei) blockiert
         jeden Aufruf mit Exit 2
      2. **Namen festlegen, bevor irgendetwas kopiert wird:** Liegt im
         Agenten-Verzeichnis schon ein Wächter (bei diesem Client ist
         `~/.claude/hooks/` je Rechner gemeinsam) oder kann später einer
         dazukommen, heißen `.py` und `.json` projekteigen und gleich
         (`<projekt>_prod_readonly.py` + `.json`); der Wächter liest
         `<name>.json` neben seiner eigenen `.py`. Wer den Vorlagennamen in
         ein Verzeichnis kopiert, in dem schon ein Wächter liegt,
         **überschreibt dessen `.py` und `.json`** — und das überschriebene
         Projekt läuft bis zu seinem nächsten Gate-Lauf mit fremder
         Konfiguration, also **offen** (der Wächter erkennt „fremd" nicht,
         nur „fehlt" und „kaputt"). Erst dann **beide Dateien** ins
         Agenten-Verzeichnis **außerhalb** des Repos kopieren
         (`<agenten-verzeichnis>/hooks/<name>.py` und `…/<name>.json`
         daneben; ein Projekt allein darf beim Vorlagennamen bleiben) und in
         dessen
         Hook-Einstellungen eintragen — mit **absolutem Interpreter-Pfad** und
         mit `-I -S` (`-I` isoliert: sonst lädt eine `json.py` neben dem
         Wächter oder im `PYTHONPATH` statt der Standardbibliothek — der Import
         steht vor jedem Abfang, und ein Fehler dort endet mit Exit 1, den der
         Client durchlässt; gemessen: ohne `-I` rc=1, mit `-I` rc=2. `-S` lässt
         `site` aus: `sitecustomize.py` und `.pth` im `site-packages` des
         Interpreters laufen unter `-I` sonst weiter, gemessen) — **und mit
         `"onFailure": "block"` im Hook-Eintrag** (Claude Code ab v2.1.295).
         Ohne das lässt der Client die Aktion durch, wenn der Wächter nicht
         startet, die Zeitgrenze erreicht oder mit einem Code außer 0 und 2
         endet: Fehlt der Interpreter, endet der Aufruf mit Exit 127, und
         bis v1.17.2 fand das erst der nächste Gate-Lauf. Mit dem Feld wird
         daraus eine Sperre des ganzen Namensraums — der harmlose Fehler, wie
         ein vergessenes Lese-Werkzeug. Dazu ein kurzes `"timeout"` (ganze
         Zahl in Sekunden; ohne gilt der Standard des Clients, 600): Ein
         hängender Interpreter sperrt sonst zehn Minuten lang. Andere Felder
         nicht — `async` und `asyncRewake` blockieren nie, `args` startet
         ohne Shell; die Gate-Probe lehnt jedes Feld außer `type`, `command`,
         `onFailure`, `timeout` und `statusMessage` ab. Ob der Client das
         Feld wirklich befolgt, zeigt nur die Ausfall-Echtprobe (Kopf von
         `prod-readonly-hook.py`, Schritt 5). Pfad mit Leerzeichen: Anführungszeichen im Kommando,
         in JSON als `\"`, Backslash als `\\` — einfacher ist ein Pfad ohne
         Leerzeichen mit `/`. Ein Wächter, der aus dem Repo heraus läuft, das er
         schützt, lässt sich per Repo-Änderung entschärfen (Regel seit v1.3.0)
- [ ] **Warum der Name zuerst kommt:** Vor v1.15.4 las jeder Wächter fest
      `prod-readonly-hook.json`: Der zweite Wächter im Verzeichnis las die
      Konfiguration des ersten, dessen Präfix seine Werkzeuge nicht trifft —
      alles offen, keine Probe des ersten Projekts rot (gemessen von einem
      Projekt mit zwei Wächtern). Beim Umbenennen an **drei** Stellen gleich:
      `.py`, `.json` und der `command` in den Agenten-Einstellungen (den die
      Gate-Zeile unverändert trägt). Nachbareinträge anderer Projekte in
      derselben Einstellungsdatei nur **melden**, nie anfassen.
- [ ] **Selbstprobe der Gate-Probe** als eigene Zeile im lokalen Gate:
      `⟨/absoluter/pfad/zu/python3⟩ -I -S docs/vorlagen/waechter-gate-probe-selbsttest.py || exit 1`

      Heißt der Wächter projekteigen (Schritt „Namen festlegen" oben), bekommt
      die Selbstprobe den Pfad: `… waechter-gate-probe-selbsttest.py --waechter
      docs/vorlagen/⟨projekt⟩_prod_readonly.py`. Ohne den Parameter sucht sie
      den Vorlagennamen neben sich, und das Projekt bräuchte eine zweite
      byte-gleiche Kopie im Repo.
      — prüft Wächter und Probe in einem Wegwerf-Verzeichnis (zwei Wächter,
      Kollision, Interpreter-Wrapper, Hardlink, Form ohne `-S`, Metazeichen,
      Köder-`.py`, Wächter mit `tool_input`-Verzweigung, Matcher-Angriffe,
      Abschalter, Ereignis, Werkzeuglisten-Fälle, Ausfallform des
      Hook-Eintrags; deterministisch); nach jeder Änderung an einer der
      beiden Dateien. **Wer die Erwartungszahl im Gate festhält, nimmt die
      FESTE Zahl** aus der Erfolgsmeldung („= N feste + …"), nicht die
      Gesamtzahl: Die Gesamtzahl hängt an der Python-Version und am
      Dateisystem (gemessen in einem Kind-Repo: 518 unter Python 3.14, 521
      unter 3.12, derselbe Code). Die feste Zahl prüft die Selbstprobe schon
      selbst als Untergrenze.
- [ ] **Drift-Abgleich Quelle ↔ Installation** für **beide Dateien** als
      Schritte im **lokalen** Gate (die CI sieht das Agenten-Verzeichnis
      nicht), z. B.

      ```sh
      cmp docs/vorlagen/prod-readonly-hook.py   <agenten-verzeichnis>/hooks/prod-readonly-hook.py   || exit 1
      cmp docs/vorlagen/prod-readonly-hook.json <agenten-verzeichnis>/hooks/prod-readonly-hook.json || exit 1
      ```

      **„Byte-gleich" heißt gleich mit dem BLOB, nicht mit einer
      Auscheckung.** Ein `git clone` unter Windows liefert die Vorlagendateien
      mit CRLF (`core.autocrlf`); `cmp` gegen den Klon ist dann „gleich",
      gegen `git show <tag>:docs/vorlagen/…` nicht — die installierte Kopie
      trüge CRLF, die nächste frische Auscheckung LF, und der Drift-Alarm
      käme ohne Änderung. Für den Nachweis im Abgleich-Issue deshalb den Blob
      vergleichen (`git hash-object <datei>` gegen `git rev-parse
      <tag>:docs/vorlagen/<datei>`), nicht den Arbeitsbaum.

      **Wer die Gleichheit im Gate erzwingen will**, legt eine Pin-Datei mit
      den SHA-256 der Vorlagendateien neben die Kopien und prüft sie dort —
      aber **nicht mit `sha256sum` oder `cmp` über `PATH`**: Attrappen vorn
      auf `PATH` machen beide Schritte grün (gemessen, dieselbe Klasse wie
      `$HOME`). Ein Skript der Standardbibliothek mit `-I -S`, das genau die
      erwarteten Namen verlangt, ist der Weg.

      — rot, sobald Quelle und Kopie auseinanderlaufen (Vorlage-Lehre §17);
      grün aber auch, wenn beide gleich kaputt sind. Deshalb daneben:
- [ ] **Gate-Probe** als Schritt im **lokalen** Gate, bei jedem Lauf — mit
      **demselben absoluten Interpreter** wie im Hook-Befehl: die Zeile aus
      dem Kopf von `docs/vorlagen/waechter-gate-probe.py` (`--einstellungen`,
      `--matcher`, `--befehl`, `--unbekannt`, `--lesend`, `--quelle`,
      `--werkzeuge`; die letzten beiden sind Pflicht; `--matcher` bleibt
      leer, wenn der Eintrag ohne `matcher` steht — dann bewacht der Client
      alle Werkzeuge, fail-closed für alles). Sie beweist: Der eingetragene
      Hook-Befehl ist genau `<interpreter> -I -S <wächter.py>` ohne
      Shell-Metazeichen (`$`, `~`, `%`, `^`, `'`, `#`, `@`, `,`, Backslash —
      Pfade absolut mit `/`, zitiert nur mit `"`, am besten ohne Leerzeichen);
      die installierte `.py` importiert nur `json`, `os`, `sys` ohne Alias
      und `from` und benutzt an diesen Modulen nur, was die Vorlage braucht
      (zwei Allowlists, per Syntaxbaum bewiesen); Prozess- und
      Reflexions-Attribute und -Namen an anderen Objekten fängt sie dazu —
      ein Fang, kein Beweis, die Grenze steht im Kopf der Probe; `-S`,
      weil `-I` das `site-packages` des Interpreters samt `sitecustomize.py`
      und `.pth` **nicht** abschaltet — gemessen: eine `sitecustomize.py`
      ließ alles grün und jeden Schreibaufruf durch); der Interpreter ist
      **zeichengleich derselbe** wie der der Probe (ein sh-Skript namens
      `python3-hook` bestand die bloße Namensform, ein Hardlink an anderem
      Ort bestand `samefile` — beides gemessen), und die Probe verweigert
      sich selbst ohne `-I -S`; der Wächter wird mit **nicht-leerem
      `tool_input`** aufgerufen, wie vom Client; die
      installierte `.py` ist byte-gleich mit der Quelle; der Wächter nennt auf
      `--konfig-pfad` genau diese `.py` und ihre `.json`; der Matcher trifft
      **jeden Namen der Werkzeugliste** (Katalog des Servers, eine Zeile je
      Name, im Repo gepflegt wie die Allowlist; jeder Allowlist-Name muss
      drinstehen); der Befehl blockiert jeden Namen außerhalb der Allowlist
      und lässt jeden innerhalb durch. Rot außerdem bei anderem Ereignis,
      abgeschalteten Hooks, verändertem `command`, veraltetem
      Interpreter-Pfad, kaputter Konfiguration. Sie zeigt **nicht**, ob der
      Client den Wächter ruft, ob der Präfix der echte Schlüssel ist (dafür
      die Echtprobe) und ob die Werkzeugliste **vollständig** ist — fehlt ein
      Schreibwerkzeug und ist der Matcher genau darauf verengt, bleibt sie
      grün; deshalb **die Liste aus dem Katalog des Servers erzeugen, nicht
      von Hand**, und einen Test führen, der Datei gegen Katalog hält; dazu
      eine Matcher-Probe gegen den **lebenden** Katalog (sie lädt die
      Anwendung, also ohne `-S` — die Vertrauensgrenze gehört benannt). Falle
      dabei: Bei einem editable Install lädt ein Skript ohne eigenen
      `sys.path`-Vorspann den Katalog des **Hauptrepos**, nicht den des
      Worktrees — ein Werkzeug, das nur im Worktree existiert, bleibt
      unsichtbar. Und
      ob die Allowlist nur Lese-Werkzeuge nennt (ein Schreibwerkzeug darin
      bekommt Exit 0, die Probe bleibt grün; das prüft der Mensch und die
      Echtprobe) — und von der Quelle nur, was der Syntaxbaum sieht, **nie
      ihre Absicht**: Eine Wächter-Quelle, die
      geschrieben ist, um die Probe zu erkennen, erkennt sie (Feldmenge,
      `session_id`-Form, ein Client-Feld — zwei Stimmen, je gemessen); dagegen
      hilft nur der Diff im Repo und die Echtprobe nach jeder `.py`-Änderung.
      Grenze „Interpreter" heißt: Standardbibliothek **und** die Dateien neben
      ihm (`python._pth`, `pyvenv.cfg`), die `-S` nicht abschaltet.
- [ ] Wächter **testen** (echte Werkzeugnamen aus dem Katalog des Clients):
      schreibend → blockiert, lesend → durch, unbekannter Name → blockiert
      (fail-closed), fremdes Werkzeug → unberührt
- [ ] **Echtprobe — Pflicht beim Scharfschalten und nach jeder Änderung an
      der Konfiguration, an der Client-Registrierung** (Schlüssel, Client,
      Einstellungen) **und an der `.py`**; ohne sie beweisen Test und
      Gate-Probe nichts über den Client — und nichts über eine Quelle, die
      geschrieben ist, um die Gate-Probe zu erkennen (die Probe prüft
      Installation und Umgebung, von der Quelle nur, was der Syntaxbaum sieht;
      ihre Absicht prüft der Diff):
      in der **installierten** `⟨projekt⟩_prod_readonly.json` (die
      `.json` neben der installierten `.py`) ein Lese-Werkzeug vorübergehend
      aus der `allowlist` nehmen, im Client einen
      echten Aufruf genau dieses Werkzeugs auslösen. Er **muss** mit der
      Wächter-Meldung abgelehnt werden (das beweist: Client ruft den Wächter,
      Interpreter startet, Präfix passt). Geht er durch: Wächter wirkungslos,
      **nicht weiterarbeiten**. Danach die Kopie zurücksetzen und
      Drift-Abgleich und Gate-Probe grün sehen. „Ein lesender Aufruf ging
      durch" ist kein Nachweis — ein Wächter, der nie startet, lässt ihn
      ebenso durch.
      **Ist der Wächter installiert, der Server aber auf diesem Rechner nirgends
      registriert,** prüft eine Attrappe bis zur ersten echten Registrierung: ein
      kleiner Server unter dem Namen, den die Konfiguration als Präfix erwartet, nur
      für die Probesitzung geladen (`--mcp-config … --strict-mcp-config`), mit je einem
      Werkzeug **innerhalb** und **außerhalb** der Allowlist. Das innere muss im
      Aufrufprotokoll der Attrappe ankommen (der Wächter liest die installierte
      `.json`), das äußere muss mit der Wächter-Meldung abgelehnt werden und darf dort
      nicht ankommen. Urteil aus beiden Quellen, Protokoll und Werkzeugergebnis. Das
      zeigt Aufruf, Interpreter, Konfiguration und Ablehnung, **nicht**, dass der
      Präfix der Schlüssel des späteren echten Servers ist: Bei dessen erster
      Registrierung ist die Echtprobe oben Pflicht. Die Ausfall-Echtprobe geht ebenso
      nur für diese Sitzung, über `--settings` mit einem zusätzlichen Eintrag, dessen
      Interpreter fehlt (Rückmeldung eines Projekts: gesperrt, weil `onFailure` auf
      Blockieren steht; hier nicht nachgemessen). Ist noch gar kein Wächter eingerichtet, bleibt es bei
      „vertagt" (`abgleich.md` 2h).
      **Wer die Probe startet:** Sie braucht einen angemeldeten Client in einer
      neuen Sitzung. Ein Agent kann die oft nicht selbst starten (Rückmeldung eines
      Projekts: `claude -p` als Kindprozess eines Agenten meldete sich nicht an). Dann legt er die Probe als
      Skript außerhalb des Repos ab, der Owner startet es, der Agent liest die
      Protokolle selbst.
- [ ] In `CLAUDE.md` festhalten, mit dem Mechanismus, nicht nur der Absicht —
      inklusive: neue Lese-Werkzeuge gehören in die Allowlist der
      Repo-Konfiguration (danach kopieren, Gate, Echtprobe), der Wächter wird
      nie abgeschaltet

## 7b. Wirkungskette scharf schalten

- [ ] `docs/agents/bau-brief.md` gelesen — der Brief ist die einzige Leitplanke,
      die den Bauer erreicht
- [ ] `sh scripts/bau-brief-pruefen.sh <brief>` einmal an einem echten Brief
      ausprobiert (er zeigt, wo die zehn Themen stehen könnten; ein fehlendes
      Thema ist ein starkes Signal, kein Beweis — fester Wortschatz —, ein
      Treffer nur ein Kandidat)
- [ ] `sh scripts/bau-brief-pruefen-selbsttest.sh` ins **lokale** Gate — sie
      wird rot, wenn im eingebauten Muster-Brief (Prüffragen,
      Pflicht-Randbedingungen und „Typische Fallen" aus `bau-brief.md`, dazu
      Alltagsprosa) ein
      fehlendes Thema oder eine fehlende Frage nicht gemeldet wird (unter Git
      Bash mehrere Minuten; Teile wählbar, siehe Skriptkopf). Eine
      **projekteigene Prüffrage** braucht **zwei Stellen**: eine Zeile in
      `FRAGEN` von `bau-brief-pruefen.sh` **und** die Frage in `bau-brief.md`
      (Nummer ab 12, `abgleich.md` 2e) — die Selbstprobe zählt beide, prüft
      die eigene mit und bricht ab, solange die Zahlen auseinanderlaufen
- [ ] `CLAUDE.md` dupliziert keine Regel aus `docs/agents/` — sie verweist
- [ ] **Lokale** Gates laufen **je Code-Commit**, nicht je Commit: Ein reiner
      Doku-Commit darf die lokalen Gates auslassen — **außer den Prüfungen, die
      genau diese Doku lesen:** der Verweis-Prüfung (`lehren-verweise-pruefen.py`),
      wenn er eine Datei ihrer Gate-Zeile berührt, und der Selbstprobe des
      Brief-Prüfskripts, wenn er einen der drei Abschnitte in `bau-brief.md`
      berührt, die sie liest: die Prüffragen, „Randbedingungen, die immer
      mitmüssen" und „Typische Fallen" (dieselbe Liste wie im Kopf der
      Selbstprobe, „WANN"). Sonst landet der Bruch mit dem Doku-Commit, und rot
      wird erst der nächste Code-Commit, zugerechnet einem Fremden (gemeldet aus
      einem Kind-Repo; die Selbstprobe nachgestellt vom Gegenprüfer zu v1.18.1:
      Exit 2 bei einer Frage nur in `bau-brief.md`). Die CI nicht: Der gelandete
      Kopf-Commit braucht trotzdem einen nachgewiesenen Lauf (Push oder
      Dispatch; kein Lauf ist ROT, `release-ritual.md`, Schritt 8), und
      ausgelieferte Doku ist Produkt (Pfad-Filter oben)
- [ ] Die Prüfungen laufen **einmal auf dem finalen Baumzustand** — egal von wem.
      Bauer, Arbiter und CI dieselbe Suite dreimal zu fahren, ist Leerlauf.
      *(Kein Widerspruch zur Zeile darüber: „je Code-Commit" sagt, WELCHE Commits
      eine Prüfung auslösen; „einmal auf dem finalen Baumzustand" sagt, WIE OFT
      sie je Commit läuft.)*
- [ ] Je vorhandener Prüf-Suite beantwortet: **„Was macht sie rot, ohne dass
      jemand daran denkt?"** Ohne Antwort ist sie eine Notiz, kein Wächter
      (Vorlage-Lehre §21, erste Wächterfrage)
- [ ] Wo Leitplanken benannt sind (kein Auto-Deploy, kein Prod-Schreibpfad):
      ein Skript ins Repo, das **Struktur parst statt Text zu suchen** — ein
      `grep` trifft auch Kommentarzeilen, zweimal nur zufällig aufgefallen
- [ ] Prozess-Papiere im Kind-Repo vollständig — **immer**, weil `CLAUDE.md`
      (oder, für `panel-kommentar.md`, `panel.md`) darauf verweist und ein
      fehlendes Papier einen toten Verweis hinterlässt: `CLAUDE.md`,
      `docs/agents/lehren.md`, `bau-brief.md`, `panel.md`,
      `panel-kommentar.md`, `release-ritual.md`,
      `betrieb.md`, `abgleich.md` (Prozess-Stand und Projektkennung verweisen
      darauf), `issue-tracker.md`, `triage-labels.md`, `skills.md`,
      `setup-checkliste.md` (bleibt abgehakt stehen — `triage-labels.md` und
      `lehren.md` verweisen auf ihre Schritte), `docs/SECRETS.md` (`CLAUDE.md`
      verweist darauf), `docs/vorlagen/` (solange `panel.md`, `lehren.md` oder
      diese Liste darauf verweisen — auch nach dem Kopieren nach
      `.github/`), `scripts/bau-brief-pruefen.sh` und
      `scripts/bau-brief-pruefen-selbsttest.sh`

## 8. Betrieb (sobald echte Nutzer)

- [ ] `docs/agents/betrieb.md` durchgehen: Sicherung, **Rückspiel-Probe**,
      Totmann-Schalter, Erreichbarkeits-Wächter
- [ ] Termin für die erste Rückspiel-Probe setzen (Kalender, nicht Vorsatz)
- [ ] **Wenn das Projekt Abbilder baut:** Scan der laufenden Abbilder am Betriebsort (täglich,
      nur behobene Lücken, Meldung nur bei neuen Funden). Deploy- und Update-Skripte ziehen die
      Basis (`compose build --pull` vor `up`, Ausnahme rein lokale Basis: Vorlage-Lehre §5), und ein Test prüft diese Skriptzeilen; jedes
      Nebenabbild hat einen benannten Neubau-Weg (Vorlage-Lehre §5)

## 9. Erster Slice

- [ ] Ein kleines, echtes Issue wählen — nicht „Setup" als ersten Slice
- [ ] Vollen Ablauf einmal durchspielen: Bau-Brief → Bau → Panel → Arbitrieren →
      Landen → Release. Lieber an etwas Kleinem lernen, wo ein Fehler nichts kostet.
