# Geheimnisse: was gebraucht wird und wo es hingehört

## Grundregel

**Der Agent trägt keine Geheimnisse ein.** Auch nicht auf Zuruf, auch nicht in
eine private Datei, auch nicht „nur zum Testen". Er darf Platzhalter setzen, das
erwartete Format erklären und die Stelle vorbereiten — den Wert einsetzt der
Mensch.

Der Grund ist nicht Misstrauen: Ein Wert, der durch einen Chatverlauf, ein
Werkzeug-Protokoll oder einen Subagenten-Bericht läuft, liegt danach an Stellen,
die niemand mehr überblickt.

## Wo Geheimnisse hingehören

| Zweck | Ort |
|---|---|
| CI-Läufe (Deploy-Keys, Registry, API-Tokens) | **GitHub-Secrets** des Repos |
| Dasselbe über mehrere Projekte | **Organisations-Secrets**, für ausgewählte Repos freigegeben — einmal hinterlegt, zentral drehbar |
| Lokale Entwicklung | `.env` (in `.gitignore`), Vorlage: `.env.example` |
| Betrieb auf dem Server | `.env` auf dem Host, nicht im Repo |

**Nie in die Vorlage.** Ein Template vervielfältigt seinen Inhalt in jedes
Kind-Repo. „Privat" ist keine Verschlüsselung: Wer Lesezugriff bekommt, bekommt
alles — inklusive Historie.

## Checkliste für ein neues Projekt

Ausfüllen, was das Projekt tatsächlich braucht — nicht vorsorglich anlegen.

- [ ] `.env.example` an den Bedarf angepasst, `.env` in `.gitignore`
- [ ] GitHub-Secrets gesetzt: ⟨auflisten⟩
- [ ] Bei mehreren Projekten: geprüft, ob Organisations-Secrets sinnvoller sind
- [ ] Deploy-Zugang eingerichtet (Schlüsselpaar, öffentlicher Teil beim Ziel)
- [ ] Zugriffsrechte des Agenten auf Produktivsysteme festgelegt — **und technisch
      erzwungen**, nicht nur vereinbart (Wächter: `docs/vorlagen/prod-readonly-hook.py`)
- [ ] Rotation überlegt: Wer dreht was, wenn ein Wert abhandenkommt?
- [ ] Eigener Geheimnis-Scan scharf: Job `geheimnis-scan` in
      `docs/vorlagen/security-scan.yml` (Wochenlauf, Vollscan der Historie),
      nach dem Scharfschalten **einmal von Hand ausgelöst** und bis
      `conclusion=success` beobachtet — und festgelegt, wer das Rot liest
- [ ] Nur bei öffentlichem Repo zusätzlich: Secret Scanning und Push Protection
      der Plattform eingeschaltet (`docs/agents/betrieb.md`, „Öffentliche Kind-Repos")

## Wenn doch etwas durchgerutscht ist

1. Wert **beim Aussteller widerrufen** — das ist der einzige Schritt, der zählt.
2. Neuen Wert erzeugen und an der richtigen Stelle hinterlegen.
3. Erst danach die Historie bereinigen. Ein Commit zu entfernen macht einen
   veröffentlichten Schlüssel nicht ungültig; Klone und Caches bleiben.

## Wer merkt es, wenn doch etwas durchrutscht?

Ein eigener Scanner, **auch bei privaten Repos** — und bei öffentlichen
**zusätzlich** zur Plattform, nicht an ihrer Stelle (`docs/agents/betrieb.md`).
Der Plattform-Scan kennt nur die Muster seiner Partner-Anbieter; selbst
vergebene Schlüssel (eigene Token-Formate, Passwörter in Konfiguration) findet
nur ein eigener Scanner, und auch der nur mit einer Regel für genau diese Form.

Er läuft im **Wochenlauf mit Vollscan der Historie**, nicht auf dem Push-Pfad:
Ein Geheimnis, das in einem alten Commit steht, ist genauso veröffentlicht wie
eines im neuesten — und ein push-getriggerter Scan sieht Commits nicht, die
ohne Lauf gelandet sind. Vorlage: Job `geheimnis-scan` in
`docs/vorlagen/security-scan.yml`.

Ein Anbieter-**Beispielwert** taugt nicht als Probe-Fixture: Scanner lassen ihn
absichtlich durch. Die Probe braucht einen erfundenen Wert in der Form, die das
Projekt selbst vergibt.

## Agentenzugriff auf Produktivsysteme

Wenn ein Agent gegen eine echte Instanz arbeiten soll, gilt: **Lesen ja,
Schreiben nein** — und zwar technisch erzwungen (Hook, Token-Rolle,
Server-Schalter), nicht als Absprache. Eine Absprache hält genau so lange, bis
ein Agent in einem langen Lauf hilfreich sein will.

Vorlage für die Client-Seite: `docs/vorlagen/prod-readonly-hook.py` (Allowlist,
fail-closed; Präfix und Allowlist in `prod-readonly-hook.json`, Muster
`prod-readonly-hook.example.json`). Die Quelle liegt im Repo, **ausgeführt wird
eine Kopie außerhalb**
des Repos — sonst kann ein Agent seinen Wächter per Repo-Änderung entschärfen.

Bewährt: ein eigener, widerrufbarer Zugang je Client mit dem kleinstmöglichen
Recht, statt eines geteilten Vollzugriffs.

## Nicht in Agenten-Konfigurationen

Ein Zugangstoken in der Konfigurationsdatei des Agenten (als Umgebungsvariable
in den Werkzeug-Einstellungen) ist bequem und die schlechteste Ablage: Es ist
für **jede** Sitzung sichtbar, für jeden Subagenten, und es landet im Protokoll
jeder Sitzung, die es je liest. Real vorgefunden — ein Konto-Token im Klartext,
monatelang unbemerkt.

Stattdessen: das Anmeldewerkzeug der jeweiligen Plattform benutzen, das den
Zugang im Schlüsselspeicher des Betriebssystems ablegt. Der Agent ruft das
Werkzeug auf und sieht den Wert nie.

Wenn doch einmal eines dort lag: **widerrufen und neu ausstellen**, nicht nur
löschen. Was in Protokollen stand, ist nicht zurückzuholen.
