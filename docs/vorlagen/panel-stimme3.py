#!/usr/bin/env python3
"""Panel-Stimme 3 (diff-only-Fremdstimme): Diff an ein guenstiges Modell, Antwort in eine Datei.

VORLAGE — laeuft ohne Aenderung, sobald zwei Umgebungsvariablen gesetzt sind.

WOFUER
------
Die diff-only-Fremdstimme urteilt NUR ueber den Diff (keine Ausfuehrung, kein
Repo-Zugriff). Sie ist eine moegliche Besetzung von Stimme 3 bei R2; bei R3 ist
Stimme 3 der Gegenpruefer, nicht dieses Werkzeug (docs/agents/panel.md,
"Verfahren je Risikoklasse"). Sie trifft seltener als die anderen, kostet fast
nichts, und ihre Treffer sind echt. Bekanntes Muster: Sie irrt Richtung ZU
STRENG und liest gelegentlich die Vorher-Seite eines Diffs — jeden Blocker
deshalb wie bei allen Stimmen selbst reproduzieren.

Der Pruefauftrag enthaelt das SUCHVERBOT (keine Recherche nach Repo, Commit
oder Namen) wie bei jeder Fremdstimme — dieses Werkzeug gibt dem Modell keinen
Netzzugriff, aber der Auftrag gilt unabhaengig vom Werkzeug.

EINRICHTEN
----------
1. Konto bei einem Anbieter mit OpenAI-kompatibler Schnittstelle (Aggregatoren
   sind hier praktisch, weil man Modelle wechseln kann, ohne den Code zu aendern).
2. Guthaben aufladen — eine Review kostet groessenordnungsmaessig Cent, nicht Euro.
3. Zugangsdaten in eine .env-Datei AUSSERHALB des Repos (siehe docs/SECRETS.md)
   und VOR dem Lauf in die Umgebung exportieren — dieses Skript liest keine
   Datei, nur os.environ; wer die .env nur anlegt und startet, bekommt Exit 2:

       PANEL_API_BASE=https://<anbieter>/api/v1
       PANEL_API_KEY=<schluessel>

4. Modellnamen in docs/agents/panel.md eintragen, damit die Kommandos kopierbar
   sind und nicht jedes Mal neu recherchiert werden muessen.

BENUTZEN
--------
    git diff <basis>..<kopf> > stimme3.diff || exit 1
    python docs/vorlagen/panel-stimme3.py \\
        --model <anbieter/modell> --max-tokens 32768 --stdin-anhang \\
        "<Pruefauftrag>" < stimme3.diff > review-stimme3.md

Den Diff NICHT per Pipe uebergeben: In "git diff ... | python ..." geht der
Exit von git diff verloren — ein falscher Commit-Name liefert einen leeren
Diff, und die Stimme endete bis v1.15.2 mit Exit 0 und einer Antwort, obwohl
sie keinen Diff sah (gemessen gegen einen Attrappen-Server). Deshalb erst in
eine Datei, Exit pruefen, dann per Umleitung. Ein LEERER Anhang bei
--stdin-anhang endet ohnehin mit Exit 2, bevor etwas bezahlt wird.

Ausgabe IMMER in eine Datei, nie in eine Pipe — sonst gehen die ersten Befunde
verloren. Bei grossen Diffs --max-tokens grosszuegig setzen: Reicht das Budget
nicht, verbraucht das Modell alles im Nachdenken und die eigentliche Antwort
kommt leer oder abgeschnitten zurueck. Beides ist ein AUSFALL, kein duennes
Ergebnis: Das Skript endet dann mit Exit 1 und schreibt nichts auf stdout
(eine abgeschnittene Antwort geht zum Nachlesen auf stderr). Was dann zu tun
ist, steht in panel.md, "Wenn eine Stimme ausfaellt", Schritt 2 — kurz gefasst
auch in der Meldung, die das Skript im Ausfall selbst ausgibt. Dieser Kopf
schreibt die Regel nicht aus; er hat sie zweimal ueberholt stehen lassen.

Guthaben VOR dem Start messen: Der Anbieter lehnt oft schon ab, sobald das
Restguthaben max_tokens x Preis nicht mehr deckt — deutlich vor dem echten
Ende des Guthabens.

Ein 402 (kein Guthaben) ist KEIN stiller Ausfall. Guthabenende, das der
Anbieter unter einem anderen Code oder als Fehlerobjekt in einer 200-Antwort
meldet, erkennt das Skript nur an ausdruecklichen Phrasen (GUTHABEN_PHRASEN:
"insufficient_quota", "insufficient credits", "payment required", ...) —
ein 429, dessen Leib nur "quota", "credit" oder "balance" enthaelt, ist meist
eine Ratenbegrenzung und bleibt ein gewoehnlicher Ausfall (Schritt 3) — traegt
er dagegen eine der Phrasen, gilt er als Guthabenende, gleich unter welchem
HTTP-Code; der Leib
steht in jeder Meldung, damit ein Mensch nachlesen kann. Was bei
Guthabenende gilt, steht in docs/agents/panel.md, "Wenn eine Stimme
ausfaellt" und Klumpenrisiko Punkt 4 — massgeblich ist die Datei, nicht
dieser Absatz. Kurz: Dieses Skript ist die
diff-only-Form der Fremdstimme. Es laeuft in einer von drei Rollen: als
Stimme 3 (R2), zusaetzlich und nicht gezaehlt neben den Pflichtstimmen, oder
als Ersatzleitung, wenn das Kontingent des gewohnten Werkzeugs gesperrt ist
(anderer Anbieter statt Warten; fuer die Ersatzleitung bevorzugt panel.md
die agentische Form). Meldet die Leitung Guthabenende (402 oder
gleichgestellt): als Ersatzleitung wird der Owner gefragt und nicht ohne
Panel ausgeliefert (Punkt 4); als Stimme 3 gilt "Wenn eine Stimme
ausfaellt", der Grund steht unter der Ueberschrift der Stimme (Form in
docs/agents/panel-kommentar.md); als zusaetzliche, nicht gezaehlte Stimme
entfaellt ihr Block im Panel-Kommentar, nichts weiter.

Exit-Codes: 0 Antwort geschrieben (finish_reason "stop"), 1 Ausfall (HTTP-
Fehler, HTTP-Umleitung, Netz, Antwort kein JSON-Objekt oder in unerwarteter
Form (Objekt an der Wurzel, andere Form in der Tiefe), keine Wahl in der
Antwort (choices fehlt oder ist leer), Fehlerobjekt in einer
200-Antwort, leere Antwort, finish_reason nicht "stop" — etwa "length" =
abgeschnitten), 2 Aufruf- oder Einrichtungsfehler (Parameter,
Umgebungsvariablen, --stdin-anhang ohne oder mit leerem Anhang).

HTTP-Umleitungen (3xx) werden NICHT verfolgt: urllib macht aus dem POST ein GET
ohne Leib, und eine gueltige Antwort des Umleitungsziels endete mit Exit 0,
obwohl die Stimme keinen Diff sah (gemessen). Eine Umleitung ist deshalb ein
Ausfall (Exit 1, "HTTP 302: ..."); PANEL_API_BASE muss die endgueltige
Adresse sein — ein Einrichtungsfehler, der als Exit 1 erscheint, weil das
Skript ihn erst an der Antwort erkennt.
"""

import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

# Meldung bei Guthabenende — gleich, ob der Anbieter es als HTTP 402, unter
# einem anderen Code mit ausdruecklicher Phrase oder als Fehlerobjekt in einer
# 200-Antwort meldet.
GUTHABEN_MELDUNG = (
    "kein Guthaben (oder Rest deckt max_tokens x Preis nicht). "
    "AUSFALL dieser Stimme, Folge nach docs/agents/panel.md: als "
    "Ersatzleitung des Fremdpruefers Klumpenrisiko Punkt 4 — Owner "
    "fragen, nicht ohne Panel ausliefern; als Stimme 3 'Wenn eine "
    "Stimme ausfaellt', Grund unter die Ueberschrift der Stimme; als "
    "zusaetzliche, nicht gezaehlte Stimme entfaellt ihr Block, nichts weiter."
)
# Nur ausdrueckliche Phrasen: einzelne Woerter wie "quota", "credit" oder
# "balance" stehen auch in gewoehnlichen Ratenbegrenzungen (gemessen:
# "Quota exceeded ... Requests per minute", "Your account balance is fine",
# "Add 10 credits to unlock ... requests per day") — die duerfen den Slice
# nicht anhalten.
GUTHABEN_PHRASEN = (
    "insufficient_quota",
    "insufficient credits",
    "insufficient credit",
    "insufficient balance",
    "insufficient funds",
    "credit balance is too low",
    "billing hard limit",
    "payment required",
    "funds exhausted",
    "out of credits",
    "credits exhausted",
    "no credits remaining",
    "top up your account",
    "kein guthaben",
    "guthaben erschoepft",
    "guthaben erschöpft",
)


class KeineUmleitung(urllib.request.HTTPRedirectHandler):
    """3xx nicht verfolgen — sonst wird aus dem POST ein GET ohne Diff (Kopf)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def guthaben_ende(code, leib):
    """402 ist immer Guthabenende; jeder andere Code und ein Fehlerleib nur mit
    einer der GUTHABEN_PHRASEN. Grenze: eine Phrase, die hier fehlt, bleibt ein
    gewoehnlicher Ausfall — der Leib steht dann in der Meldung."""
    if code == 402:
        return True
    klein = leib.lower()
    return any(ph in klein for ph in GUTHABEN_PHRASEN)


def main() -> int:
    # Diff und Antwort sind UTF-8, unabhaengig von der Konsolenkodierung des
    # Rechners. Ohne das scheitert auf einem Windows-Host die Ausgabe an einem
    # Umlaut — NACHDEM die Anfrage schon bezahlt ist.
    for strom in (sys.stdin, sys.stdout, sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    p = argparse.ArgumentParser(description="Diff an ein Modell, Antwort auf stdout")
    p.add_argument("--model", required=True, help="Modellname beim Anbieter")
    p.add_argument("--max-tokens", type=int, default=16384)
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument(
        "--stdin-anhang",
        action="store_true",
        help="stdin (den Diff) unter den Prompt haengen",
    )
    p.add_argument("prompt", help="Pruefauftrag")
    a = p.parse_args()

    base = os.environ.get("PANEL_API_BASE", "").rstrip("/")
    key = os.environ.get("PANEL_API_KEY", "")
    if not base or not key:
        print(
            "PANEL_API_BASE / PANEL_API_KEY fehlen. Siehe Kopf dieser Datei.",
            file=sys.stderr,
        )
        return 2

    inhalt = a.prompt
    if a.stdin_anhang:
        # Ohne Anhang wuerde das Modell den Pruefauftrag allein beurteilen und
        # "Keine Funde." liefern — Exit 0 fuer eine Stimme, die nichts sah.
        anhang = "" if sys.stdin.isatty() else sys.stdin.read()
        if not anhang.strip():
            print(
                "--stdin-anhang, aber der Anhang auf stdin ist leer (leerer Diff? "
                "falscher Commit-Name? Exit von git diff pruefen). Nichts gesendet.",
                file=sys.stderr,
            )
            return 2
        inhalt = inhalt + "\n\n---\n\n" + anhang

    nutzlast = {
        "model": a.model,
        "max_tokens": a.max_tokens,
        "messages": [{"role": "user", "content": inhalt}],
    }
    if a.temperature is not None:
        nutzlast["temperature"] = a.temperature

    anfrage = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(nutzlast).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
    )

    oeffner = urllib.request.build_opener(KeineUmleitung)
    try:
        with oeffner.open(anfrage, timeout=900) as antwort:
            daten = json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            leib = e.read().decode("utf-8", "replace")[:500]
        except Exception:  # Leib abgebrochen (IncompleteRead) — der Kopf zaehlt
            leib = "(Leib abgebrochen)"
        if guthaben_ende(e.code, leib):
            print("HTTP %s — %s\nLeib: %s" % (e.code, GUTHABEN_MELDUNG, leib),
                  file=sys.stderr)
        else:
            print("HTTP %s: %s" % (e.code, leib), file=sys.stderr)
        return 1
    except Exception as e:  # Netz, Zeitlimit, kaputte Antwort
        print("Anfrage fehlgeschlagen: %s" % e, file=sys.stderr)
        return 1

    if not isinstance(daten, dict):
        print("AUSFALL: Antwort ist kein JSON-Objekt: %s" % json.dumps(daten)[:200],
              file=sys.stderr)
        return 1

    fehler = daten.get("error")
    if fehler:
        leib = json.dumps(fehler, ensure_ascii=False)[:500]
        if guthaben_ende(200, leib):
            print("HTTP 200 mit Fehlerobjekt — %s\nLeib: %s" % (GUTHABEN_MELDUNG, leib),
                  file=sys.stderr)
        else:
            print("AUSFALL: Fehlerobjekt in der Antwort: %s" % leib, file=sys.stderr)
        return 1

    try:
        wahl = (daten.get("choices") or [{}])[0]
        text = (wahl.get("message") or {}).get("content") or ""
        grund = wahl.get("finish_reason")
        verbrauch = daten.get("usage") or {}
        messung = "[panel-messung] datum=%s modell=%s antwort-modell=%s ein=%s aus=%s" % (
            datetime.date.today().isoformat(),
            a.model,
            daten.get("model", "?"),
            verbrauch.get("prompt_tokens", "?"),
            verbrauch.get("completion_tokens", "?"),
        )
        if not isinstance(text, str):
            raise TypeError("content ist %s" % type(text).__name__)
    except (AttributeError, KeyError, IndexError, TypeError) as e:
        # Objekt an der Wurzel, aber eine andere Form in der Tiefe (choices als
        # Dict, content als Liste, usage als Liste) — Ausfall mit Meldung.
        print("AUSFALL: Antwort hat eine unerwartete Form (%s: %s): %s"
              % (type(e).__name__, e, json.dumps(daten, ensure_ascii=False)[:300]),
              file=sys.stderr)
        return 1

    if not daten.get("choices"):
        # Der Anbieter hat gar keine Wahl geliefert — ein hoeheres Budget hilft
        # hier nicht, der Rat unten waere falsch.
        print("AUSFALL: Antwort enthaelt keine Wahl (choices fehlt oder ist leer). Einmal "
              "unveraendert wiederholen; bleibt es dabei, Ausfall nach 'Wenn eine "
              "Stimme ausfaellt'.\n" + messung, file=sys.stderr)
        return 1

    if not text.strip():
        # Ausfall, nicht duennes Ergebnis: nichts auf stdout, damit die
        # Ausgabedatei nicht wie eine Stimme ohne Befund aussieht.
        print(
            "AUSFALL: Antwort ist leer (finish_reason=%r). Einmal auf demselben "
            "Commit wiederholen: bei 'length' mit hoeherem --max-tokens (das Budget "
            "ist im Nachdenk-Anteil aufgebraucht), bei jedem anderen Grund "
            "unveraendert (dann liegt es am Anbieter, nicht am Budget). Bleibt es "
            "dabei, Ausfall nach 'Wenn eine Stimme ausfaellt'.\n%s" % (grund, messung),
            file=sys.stderr,
        )
        return 1

    if grund != "stop":
        # "length" = Token-Budget erschoepft, die Antwort bricht mitten ab. Eine
        # halbe Review sieht in der Datei aus wie eine ganze — deshalb Ausfall,
        # und der Text geht zum Nachlesen nur auf stderr.
        print(
            "AUSFALL: Antwort abgeschnitten oder unvollstaendig (finish_reason=%r). "
            "Einmal wiederholen: bei 'length' mit hoeherem --max-tokens, bei jedem "
            "anderen Grund unveraendert. Bleibt es dabei, Ausfall nach 'Wenn eine "
            "Stimme ausfaellt'.\n%s\n"
            "--- abgeschnittene Antwort ---\n%s"
            % (grund, messung, text),
            file=sys.stderr,
        )
        return 1

    print(text)
    # Datum und gemeldetes Modell: Anbieter ziehen still nach, ein Ergebnis
    # ohne Modellstand ist spaeter nicht mehr zuzuordnen (panel.md).
    print("\n\n" + messung)
    return 0


if __name__ == "__main__":
    sys.exit(main())
