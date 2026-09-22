#!/usr/bin/env python
"""Was würde eine unicode-feste Namensfaltung an DIESEM Bestand ändern? (#83)

    python scripts/faltung-sonde.py /pfad/zu/accounts.json

DIESE SONDE SCHREIBT NICHTS. Sie liest `accounts.json`, rechnet beide
Faltungen aus und zählt. Kein Backup nötig, kein Neustart, keine Wanderung.

## Warum es sie gibt

`ConfigStore._name_key` faltet heute mit `strip().lower()` — ohne
Unicode-Normalform und ohne `casefold`. Seit #81 ist das eine **Zusage an den
Nutzer**: Die App sagt „es gibt keine Gruppe", und für zwei sichtbar gleiche
Namen ist das schlicht falsch. Die Behebung wäre eine Datenwanderung, und
verschmelzen lässt sich nicht trennen — deshalb der Owner-Entscheid: **erst
messen, dann entscheiden**.

## Was gemessen wird — und was die erste Fassung falsch gemacht hat

Die Faltung ist keine Gruppen-IDENTITÄT, sondern eine ZUORDNUNGSHILFE: Sie
beantwortet „welche Gruppe heißt so?" für einen Namen, der **von außen**
kommt — aus einem Eingabefeld, nicht aus dem Bestand.

**Zwei Fassungen sind an dieser Frage gescheitert, und zwar spiegelbildlich.**
Die erste verglich gespeicherte Namen gegeneinander: Ein Bestand mit einem
einzigen Album „Straße" hieß „folgenlos", obwohl eine Abfrage nach „Strasse"
heute danebengeht und nachher trifft. Die zweite sah immerhin, ob sich die
Faltung des gespeicherten Namens selbst verschiebt — und übersah damit genau
denselben Fall andersherum: gespeichert „Strasse", gefragt „Straße".

**Ein falsches Nein ist hier der teure Fehler**, denn darauf hin wird eine
unumkehrbare Wanderung freigegeben. Diese Fassung stellt die Frage deshalb so,
wie die Anwendung sie bekommt — **von außen**: Sie baut das Orakel nach
(`_gruppen_je_name` + `existing_group_for_name`) und fragt es mit jedem
gespeicherten Namen UND jeder Schreibweise, in der ein Mensch ihn tippen
würde (`VARIANTEN`: Groß/Klein, NFC gegen NFD, scharfes S, Schluss-Sigma,
türkisches I).

1. **Antwort ändert sich** — für eine solche Anfrage liefert die Abfrage
   nachher etwas anderes als heute. Der Bericht trennt „neu gefunden" von
   „verloren"; verloren geht nach heutigem Stand nichts, aber das ist eine
   Messung, keine Zusage.
2. **Mehrdeutigkeit entsteht** — zwei Namen mit VERSCHIEDENEN Gruppen fallen
   zusammen. Danach antwortet die Abfrage für beide mit „keine Gruppe" (#78).
   Der teure Fall; jeder einzelne gehört angesehen.
3. **Aufspaltung** — ein heutiger Schlüssel zerfiele. Das ist **nicht**
   theoretisch: `casefold` NACH `NFC` lässt ein nicht mehr normalisiertes
   Ergebnis zurück, und es gibt reale Zeichenpaare, die so auseinanderfallen
   (gemessen: zehn allein unterhalb U+3000). Genau deshalb normalisiert
   `neue_faltung` ein zweites Mal — und genau deshalb bleibt die Prüfung
   trotzdem stehen.

**Die benannte Grenze, und sie ist wichtig:** Die Sonde fragt mit den
Schreibweisen, die ein Mensch tippt. Daneben gibt es Zeichen, deren Faltung
sich ebenfalls verschiebt, die aber niemand eingibt — das lange s (`ſ`), die
Ligaturen, die Vollbreiten-Zeichen. Über alle Codepunkte gerechnet sind das
rund 1100 Klassen. Für sie ändert sich die Antwort streng genommen auch. Sie
gehen **nicht ins Urteil** ein, weil sonst jeder Name mit einem „s" ein
Entscheidungsfall wäre (`ſ` faltet neu auf `s`) — ihre Zahl steht aber im
Bericht, damit die Auslassung sichtbar bleibt statt bequem.

Die Gruppenzählung folgt dem Backend: `if album.get("group_id")` —
Wahrheitswert, nicht `is not None`. Eine leere Kennung ist dort **keine**
Gruppe, und die Sonde darf sie nicht als eine zählen.

## Was sie ausgibt

**Ohne `--namen` erscheint kein einziges Stück Bestandstext** — weder ein
Name noch ein gefalteter Schlüssel. Auch ein gefalteter Name ist ein
Personendatum. Nur Zahlen sind teilbar.

Exit 0 = nichts ändert sich. Exit 1 = es gibt etwas zu entscheiden.
Exit 2 = **nicht entscheidbar** (Datei fehlt, kein Bestand, unlesbare
Struktur). Exit 2 ist ausdrücklich KEIN Nein.
"""
import argparse
import io
import json
import os
import sys
import unicodedata

# Die Ausgabe kann Namen tragen, und Namen tragen Umlaute. Ohne diese Zeile
# schreibt Python auf einer deutschen Windows-Konsole in cp1252 und stirbt
# mit UnicodeEncodeError — ausgerechnet bei `--namen`, also genau dann, wenn
# die Sonde gebraucht wird. Vom eigenen Selbsttest gefunden, nicht im Einsatz.
for _kanal in (sys.stdout, sys.stderr):
    try:
        _kanal.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):       # aeltere Python, umgeleitet
        pass


class NichtEntscheidbar(Exception):
    """Der Bestand gibt die Frage nicht her. Das ist kein Nein."""


def alte_faltung(name) -> str:
    """Genau das, was `ConfigStore._name_key` heute tut.

    Absichtlich nachgebaut statt importiert: Die Sonde soll auch dort laufen,
    wo der Code gar nicht installiert ist — auf dem Auslieferungs-Host zum
    Beispiel. Der Preis ist Drift; der Selbsttest hält beide gegeneinander
    (1,1 Mio. Proben, 0 Abweichungen).
    """
    if name is None:
        return ""
    return str(name).strip().lower()


def neue_faltung(name) -> str:
    """Der Vorschlag: NFC, `casefold`, **und noch einmal NFC**.

    Das zweite `NFC` ist keine Vorsicht, sondern eine Korrektur. `casefold`
    kann aus einem normalisierten Text einen nicht mehr normalisierten machen
    (`İ`, `Ĥ` mit Kombinierer, `Ϊ` mit Akzent). Ohne den zweiten Durchgang
    fielen Namen auseinander, die heute ZUSAMMENfallen — die neue Faltung
    wäre also nicht gröber, sondern stellenweise feiner. Gemessen: zehn
    solche Zeichenpaare unterhalb U+3000, gefunden vom Blindprüfer, hier
    nachgerechnet.

    Nullbreiten-Zeichen werden NICHT entfernt. Das wäre eine zweite,
    eigenständige Entscheidung.
    """
    if name is None:
        return ""
    return unicodedata.normalize(
        "NFC", unicodedata.normalize("NFC", str(name)).strip().casefold())


def lies(pfad: str) -> list:
    """Den Bestand holen — und ablehnen, was keiner ist.

    Die erste Fassung nahm jedes JSON-Objekt an und las `managed_albums` mit
    Vorgabe `[]`. Ein Tippfehler im Pfad oder eine Sicherung aus der Zeit vor
    dem Feld ergab damit „0 Alben, nichts zu entscheiden" — ein autoritatives
    Nein über eine Datei, die gar nicht der Bestand war. Die Plausibilitäts-
    prüfung steht im Backend (`config_store._load`) und wird hier übernommen.
    """
    try:
        with io.open(pfad, encoding="utf-8") as f:
            daten = json.load(f)
    except FileNotFoundError:
        raise NichtEntscheidbar("Datei nicht gefunden: %s" % pfad)
    except IsADirectoryError:
        raise NichtEntscheidbar("Das ist ein Verzeichnis, keine Datei: %s" % pfad)
    except PermissionError:
        raise NichtEntscheidbar("Kein Zugriff: %s" % pfad)
    except UnicodeDecodeError:
        raise NichtEntscheidbar("Die Datei ist nicht UTF-8: %s" % pfad)
    except json.JSONDecodeError as exc:
        raise NichtEntscheidbar("Kein gueltiges JSON: %s" % exc)

    if not isinstance(daten, dict):
        raise NichtEntscheidbar("Kein JSON-Objekt an der Wurzel")
    if "accounts" not in daten:
        raise NichtEntscheidbar(
            "Kein Bestand dieser Anwendung: das Feld 'accounts' fehlt")
    if "managed_albums" not in daten:
        raise NichtEntscheidbar(
            "Kein Bestand mit verwalteten Alben: das Feld 'managed_albums' "
            "fehlt (eine Sicherung aus der Zeit davor?)")
    alben = daten["managed_albums"]
    if not isinstance(alben, list):
        raise NichtEntscheidbar("'managed_albums' ist keine Liste")
    fremd = [x for x in alben if not isinstance(x, dict)]
    if fremd:
        raise NichtEntscheidbar(
            "%d Eintraege in 'managed_albums' sind keine Objekte" % len(fremd))
    return alben


def _kennung(album: dict) -> str:
    """Die Gruppenkennung, so wie das Backend sie liest.

    `config_store._gruppen_je_name` prueft mit `if album.get("group_id")` —
    dem WAHRHEITSWERT. Eine leere Kennung ist dort keine Gruppe. Die erste
    Fassung dieser Sonde prueft mit `is not None` und meldete daraufhin den
    gewollten Fall als den teuren (Blindpruefer).
    """
    gid = album.get("group_id")
    if not gid:
        return ""
    if not isinstance(gid, str):
        raise NichtEntscheidbar(
            "Eine 'group_id' ist keine Zeichenkette (%s)" % type(gid).__name__)
    return gid


def _karte(alben: list, faltung) -> dict:
    """Schluessel -> Menge der Gruppen. Das Gegenstueck zu `_gruppen_je_name`."""
    karte: dict = {}
    for album in alben:
        gid = _kennung(album)
        if not gid:
            continue
        karte.setdefault(faltung(album.get("album_name", "")), set()).add(gid)
    return karte


def _antwort(karte: dict, schluessel: str):
    """Das Gegenstueck zu `existing_group_for_name`: eine oder keine.

    Ein leerer Schluessel trifft nie — auch das steht so im Backend.
    """
    if not schluessel:
        return None
    gruppen = karte.get(schluessel, set())
    return next(iter(gruppen)) if len(gruppen) == 1 else None


# Die Schreibweisen, in denen ein MENSCH denselben Namen tippt. Jede Zeile
# ist eine Klasse, die real vorkommt — und jede erzeugt aus einem
# gespeicherten Namen eine ANFRAGE, die die Anwendung so bekommen kann.
#
# Das ist der Kern der Nacharbeit: Die Faltung beantwortet "welche Gruppe
# heisst so?" fuer einen Namen VON AUSSEN. Die erste Fassung verglich
# gespeicherte Namen gegeneinander, die zweite sah nur, ob die Faltung des
# gespeicherten Namens sich selbst verschiebt. Beide uebersahen denselben
# Fall, nur spiegelverkehrt: gespeichert "Strasse", gefragt "Straße".
VARIANTEN = [
    ("Gross/Klein", lambda n: [n.upper(), n.lower(), n.title()]),
    ("NFC gegen NFD", lambda n: [unicodedata.normalize("NFC", n),
                                 unicodedata.normalize("NFD", n)]),
    ("scharfes S", lambda n: [n.replace("ß", "ss"), n.replace("ss", "ß"),
                              n.replace("ß", "SS")]),
    ("griechisches Schluss-Sigma", lambda n: [n.replace("ς", "σ"),
                                              n.replace("σ", "ς")]),
    ("tuerkisches I", lambda n: [n.replace("İ", "I"), n.replace("I", "İ"),
                                 n.replace("ı", "i"), n.replace("i", "ı")]),
]


def _exotische_bilder():
    """Zeichen, deren Faltung sich verschiebt, die aber niemand tippt.

    Vollstaendig ueber alle Codepunkte gerechnet (rund eine halbe Sekunde) —
    das lange s, Ligaturen, Vollbreiten-Zeichen und aehnliches. Jedes davon
    erzeugt streng genommen eine Anfrage, deren Antwort sich aendert. Sie
    gehen NICHT ins Urteil ein, weil sonst jeder Name mit einem 's' ein
    Entscheidungsfall waere (langes s faltet neu auf 's'). Die Zahl steht
    trotzdem im Bericht: Wer das anders sieht, sieht sie.
    """
    global _BILDER
    if _BILDER is None:
        _BILDER = set()
        alltag = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                     "äöüÄÖÜßáéíóúàèìòùâêîôûçñ0123456789 -_.,'()&+")
        for cp in range(0x110000):
            c = chr(cp)
            if c in alltag:
                continue
            probe = "x" + c + "x"
            if alte_faltung(probe)[1:-1] != neue_faltung(probe)[1:-1]:
                bild = neue_faltung(probe)[1:-1]
                if bild:
                    _BILDER.add(bild)
    return _BILDER


_BILDER = None


def messen(alben: list) -> dict:
    """Beide Faltungen gegeneinander, gemessen an der ANTWORT auf eine Anfrage."""
    alt_karte = _karte(alben, alte_faltung)
    neu_karte = _karte(alben, neue_faltung)

    def antworten(frage):
        return (_antwort(alt_karte, alte_faltung(frage)),
                _antwort(neu_karte, neue_faltung(frage)))

    # Je gespeichertem Namen: der Name selbst UND jede Schreibweise, in der
    # ihn ein Mensch tippen wuerde.
    anders = []
    gesehen = set()
    for album in alben:
        name = str(album.get("album_name", "") or "")
        fragen = [("wie gespeichert", name)]
        for klasse, erzeuge in VARIANTEN:
            for v in erzeuge(name):
                if v != name:
                    fragen.append((klasse, v))
        for klasse, frage in fragen:
            schluessel = (klasse, alte_faltung(frage), neue_faltung(frage))
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            heute, nachher = antworten(frage)
            if heute != nachher:
                anders.append({"klasse": klasse, "frage": frage, "name": name,
                               "heute": heute, "nachher": nachher})

    # Die exotische Klasse: vollstaendig gerechnet, aber nicht im Urteil.
    exotisch = []
    for album in alben:
        gid = _kennung(album)
        if not gid:
            continue
        k = neue_faltung(album.get("album_name", ""))
        if k and any(b in k for b in _exotische_bilder()):
            exotisch.append({"name": str(album.get("album_name", "")), "neu": k})

    # Mehrdeutigkeit: ein neuer Schluessel traegt mehr als eine Gruppe,
    # obwohl die beteiligten alten Schluessel je hoechstens eine trugen.
    mehrdeutig = []
    for n, gruppen in neu_karte.items():
        if len(gruppen) < 2:
            continue
        alte = {a for a, g in alt_karte.items() if g & gruppen}
        if not any(len(alt_karte[a]) > 1 for a in alte):
            mehrdeutig.append({"neu": n, "gruppen": len(gruppen),
                               "alte_schluessel": sorted(alte)})

    # Aufspaltung: ein heutiger Schluessel zerfaellt. Nicht theoretisch —
    # siehe Kopftext.
    nach_alt = {}
    for album in alben:
        name = album.get("album_name", "")
        nach_alt.setdefault(alte_faltung(name), set()).add(neue_faltung(name))
    gespalten = [{"alt": a, "neu": sorted(neue)}
                 for a, neue in nach_alt.items() if len(neue) > 1]

    return {
        "alben_gesamt": len(alben),
        "schluessel_heute": len(nach_alt),
        "antwort_anders": anders,
        "exotisch": exotisch,
        "mehrdeutigkeit": mehrdeutig,
        "aufspaltung": gespalten,
    }


def berichten(e: dict, mit_namen: bool) -> int:
    urteil = [
        ("Antwort aendert sich            ", e["antwort_anders"]),
        ("Mehrdeutigkeit entsteht (teuer) ", e["mehrdeutigkeit"]),
        ("Aufspaltung (darf nicht sein)   ", e["aufspaltung"]),
    ]
    print("Faltungs-Sonde (#83) — es wurde NICHTS geschrieben.")
    print()
    print("  verwaltete Alben insgesamt      %d" % e["alben_gesamt"])
    print("  Namensschluessel heute          %d" % e["schluessel_heute"])
    for titel, liste in urteil:
        print("  %s%d" % (titel, len(liste)))
    print("  (nachrichtlich) exotische Zeichen %d" % len(e["exotisch"]))
    print()

    if not any(liste for _, liste in urteil):
        print("NICHTS AENDERT SICH. Fuer jeden gespeicherten Namen und jede")
        print("Schreibweise, in der ihn ein Mensch tippen wuerde, antwortet die")
        print("Abfrage nachher wie heute — die Wanderung waere folgenlos.")
        if e["exotisch"]:
            print()
            print("AUSSER fuer %d Alben, deren Name ein Zeichen enthaelt, dessen"
                  % len(e["exotisch"]))
            print("Faltung sich verschiebt, das aber niemand tippt (langes s,")
            print("Ligaturen, Vollbreiten-Zeichen). Streng genommen aendert sich")
            print("fuer eine solche Anfrage die Antwort. Das geht nicht ins Urteil")
            print("ein — sonst waere jeder Name mit einem 's' ein Fall. Wer das")
            print("anders sieht, hat hier die Zahl.")
        return 0

    # AB HIER GILT DIE PII-SCHRANKE FUER JEDE ZEILE. Auch ein gefalteter
    # Schluessel ist der Albumname, nur kleingeschrieben.
    def zeile(text):
        if mit_namen:
            print("      %s" % text)

    if e["antwort_anders"]:
        print("ANTWORT AENDERT SICH — fuer diese Anfragen liefert die Abfrage")
        print("  nachher etwas anderes als heute. Nach Schreibweise:")
        nach_klasse = {}
        for x in e["antwort_anders"]:
            nach_klasse.setdefault(x["klasse"], []).append(x)
        for klasse, liste in sorted(nach_klasse.items(), key=lambda kv: -len(kv[1])):
            neu_gefunden = sum(1 for x in liste if not x["heute"] and x["nachher"])
            verloren = sum(1 for x in liste if x["heute"] and not x["nachher"])
            print("  - %-28s %3d  (neu gefunden %d, verloren %d)"
                  % (klasse, len(liste), neu_gefunden, verloren))
            for x in liste:
                zeile("%r -> gefragt als %r" % (x["name"], x["frage"]))
        print()

    if e["mehrdeutigkeit"]:
        print("MEHRDEUTIGKEIT — verschiedene Gruppen fallen unter einen Namen.")
        print("  Danach antwortet die Abfrage fuer BEIDE mit \"keine Gruppe\" (#78).")
        for x in e["mehrdeutigkeit"]:
            print("  - %d Gruppen aus %d heutigen Schluesseln"
                  % (x["gruppen"], len(x["alte_schluessel"])))
            zeile("%r" % (x["neu"],))
        print()

    if e["aufspaltung"]:
        print("AUFSPALTUNG — ein heutiger Schluessel zerfaellt:")
        for x in e["aufspaltung"]:
            print("  - ein Schluessel zerfiele in %d" % len(x["neu"]))
            zeile("%r -> %r" % (x["alt"], x["neu"]))
        print("  Tritt das auf, ist die neue Faltung NICHT groeber als die alte,")
        print("  und der Vorschlag gehoert neu gedacht — nicht die Wanderung")
        print("  gestartet.")
        print()

    if e["exotisch"]:
        print("NACHRICHTLICH: %d Alben tragen ein Zeichen, dessen Faltung sich"
              % len(e["exotisch"]))
        print("  verschiebt, das aber niemand tippt. Nicht im Urteil enthalten.")
        for x in e["exotisch"]:
            zeile("%r" % (x["name"],))
        print()

    if not mit_namen:
        print("Kein Name und kein gefalteter Schluessel steht in dieser Ausgabe:")
        print("beides sind Personendaten. Mit --namen zeigt die Sonde sie an —")
        print("diese Ausgabe bleibt dann lokal.")
    else:
        print("ACHTUNG: Diese Ausgabe enthaelt Namen aus dem echten Bestand.")
        print("Sie gehoert nicht in ein Issue, einen Chat oder ein Repo.")
    return 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Misst, was eine unicode-feste Namensfaltung aendern wuerde. "
                    "Schreibt nichts.")
    p.add_argument("accounts_json", help="Pfad zu accounts.json")
    p.add_argument("--namen", action="store_true",
                   help="Namen und Schluessel mitzeigen (Personendaten, lokal)")
    args = p.parse_args(argv)

    # `messen` steht MIT im Versuch: Ein handbearbeiteter Bestand darf einen
    # Traceback und Exit 1 erzeugen — und Exit 1 heisst laut Vertrag "es gibt
    # etwas zu entscheiden". Genau diese Verwechslung hat der Fremdpruefer
    # gemeldet.
    try:
        ergebnis = messen(lies(args.accounts_json))
    except NichtEntscheidbar as exc:
        print("NICHT ENTSCHEIDBAR: %s" % exc, file=sys.stderr)
        print("Das ist KEIN \"nichts zu entscheiden\". Es wurde nichts gemessen.",
              file=sys.stderr)
        return 2
    except Exception as exc:                       # noqa: BLE001 — siehe oben
        print("NICHT ENTSCHEIDBAR: %s (%s)" % (type(exc).__name__, exc),
              file=sys.stderr)
        print("Das ist KEIN \"nichts zu entscheiden\". Es wurde nichts gemessen.",
              file=sys.stderr)
        return 2

    return berichten(ergebnis, args.namen)


if __name__ == "__main__":
    sys.exit(main())
