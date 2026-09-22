#!/usr/bin/env python
"""Was würde eine unicode-feste Namensfaltung an DIESEM Bestand ändern? (#83)

    python scripts/faltung-sonde.py /pfad/zu/accounts.json

DIESE SONDE SCHREIBT NICHTS. Sie liest `accounts.json`, rechnet beide
Faltungen aus und zählt. Kein Backup nötig, kein Neustart, keine Wanderung.

## Warum es sie gibt

`ConfigStore._name_key` faltet heute mit `strip().lower()` — ohne
Unicode-Normalform und ohne `casefold`. Gemessen (#83):

| Eingabe            | Bestand              | heutige Antwort |
| ------------------ | -------------------- | --------------- |
| `"Café Oma"` NFC   | dasselbe in NFD      | kein Treffer    |
| `"istanbul"`       | `"İstanbul"`         | kein Treffer    |
| `"Testalbum"`      | mit Nullbreiten-Leer | kein Treffer    |

Seit #81 ist das eine **Zusage an den Nutzer**: Die App sagt „es gibt keine
Gruppe", und für zwei sichtbar gleiche Namen ist das schlicht falsch.

Die Behebung wäre eine Datenwanderung — und verschmelzen lässt sich nicht
trennen. Der Owner hat deshalb entschieden: **erst messen, dann entscheiden**
(Kommentar in #83). Diese Sonde ist die Messung.

## Was sie beantwortet

Die Faltung ist keine Gruppen-IDENTITÄT, sondern eine ZUORDNUNGSHILFE: Sie
beantwortet „welche Gruppe heißt so?". Eine neue Faltung verschmilzt also
nicht von selbst Gruppen — sie ändert, welche Gruppe ein Name FINDET. Drei
Dinge können passieren, und die Sonde zählt sie getrennt:

1. **Zusammenführung** — zwei heute getrennte Schlüssel fallen zusammen und
   gehören zu DERSELBEN Gruppe. Das ist der gewollte Fall: Der Nutzer findet
   seine Gruppe wieder.
2. **Mehrdeutigkeit** — zwei heute getrennte Schlüssel fallen zusammen,
   gehören aber zu VERSCHIEDENEN Gruppen. Danach ist der Name mehrdeutig, und
   `existing_group_for_name` antwortet für beide mit „keine" (#78). Das ist
   der teure Fall; jeder einzelne gehört angesehen.
3. **Aufspaltung** — ein heutiger Schlüssel zerfiele in zwei. Das sollte nicht
   vorkommen (die neue Faltung ist gröber), aber „sollte nicht" ist keine
   Messung. Die Sonde prüft es und meldet es als FEHLER, wenn doch.

## Was sie ausgibt

Standardmäßig **nur Zahlen** — die sind teilbar. Albumnamen sind
Personendaten: Sie stehen nur bei `--namen` in der Ausgabe, und die gehört
dann nicht in ein Issue, einen Chat oder ein Repo.

Exit 0 = nichts zu entscheiden (keine Zusammenführung, keine
Mehrdeutigkeit) — die Wanderung wäre folgenlos.
Exit 1 = es gibt etwas zu entscheiden.
Exit 2 = Aufrufproblem (Datei fehlt, kein gültiges JSON).
"""
import argparse
import io
import json
import sys
import unicodedata

# Die Ausgabe traegt Namen, und Namen tragen Umlaute. Ohne diese Zeile
# schreibt Python auf einer deutschen Windows-Konsole in cp1252 und stirbt
# mit UnicodeEncodeError — ausgerechnet bei `--namen`, also genau dann, wenn
# die Sonde gebraucht wird. Vom eigenen Selbsttest gefunden, nicht im
# Einsatz.
for _kanal in (sys.stdout, sys.stderr):
    try:
        _kanal.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):       # aeltere Python, umgeleitet
        pass


def alte_faltung(name) -> str:
    """Genau das, was `ConfigStore._name_key` heute tut.

    Absichtlich nachgebaut statt importiert: Die Sonde soll auch dann laufen,
    wenn sie neben einem Bestand liegt, dessen Code gar nicht installiert ist
    — auf dem Auslieferungs-Host zum Beispiel.

    Bleibt diese Zeile hinter `_name_key` zurück, misst die Sonde etwas
    anderes als die Anwendung. Der Selbsttest hält beide gegeneinander.
    """
    if name is None:
        return ""
    return str(name).strip().lower()


def neue_faltung(name) -> str:
    """Die vorgeschlagene Fassung: NFC plus `casefold`.

    `casefold` statt `lower`, weil `lower` sprachabhängige Sonderfälle nicht
    auflöst (ß, İ). NFC, weil dieselben sichtbaren Zeichen in zwei
    Byte-Folgen vorliegen können, je nachdem, welches Gerät sie erzeugt hat.

    Nullbreiten-Zeichen werden NICHT entfernt. Das wäre eine zweite,
    eigenständige Entscheidung — und eine, die sichtbar gleiche Namen
    zusammenzieht, die in Immich verschieden heißen.
    """
    if name is None:
        return ""
    return unicodedata.normalize("NFC", str(name)).strip().casefold()


def lies(pfad: str) -> list:
    with io.open(pfad, encoding="utf-8") as f:
        daten = json.load(f)
    if not isinstance(daten, dict):
        raise ValueError("kein JSON-Objekt an der Wurzel")
    alben = daten.get("managed_albums", [])
    if not isinstance(alben, list):
        raise ValueError("managed_albums ist keine Liste")
    return alben


def messen(alben: list) -> dict:
    """Beide Faltungen gegeneinander. Rechnet, schreibt nicht."""
    alt_gruppen: dict = {}      # alter Schluessel -> Menge der group_id
    alt_namen: dict = {}        # alter Schluessel -> Menge der Namen
    alt_alben: dict = {}        # alter Schluessel -> Anzahl Alben
    alt_treffer: dict = {}      # alter Schluessel -> Anzahl verknuepfter Treffer
    alt_nach_neu: dict = {}     # neuer Schluessel -> Menge alter Schluessel

    for album in alben:
        if not isinstance(album, dict):
            continue
        name = album.get("album_name", "")
        a = alte_faltung(name)
        n = neue_faltung(name)
        gid = album.get("group_id")
        alt_gruppen.setdefault(a, set()).add(gid)
        alt_namen.setdefault(a, set()).add(str(name))
        alt_alben[a] = alt_alben.get(a, 0) + 1
        verknuepft = album.get("linked_match_ids") or []
        alt_treffer[a] = alt_treffer.get(a, 0) + (
            len(verknuepft) if isinstance(verknuepft, list) else 0)
        alt_nach_neu.setdefault(n, set()).add(a)

    zusammen = []      # neuer Schluessel, dieselbe Gruppe
    mehrdeutig = []    # neuer Schluessel, verschiedene Gruppen
    for n, alte in alt_nach_neu.items():
        if len(alte) < 2:
            continue
        gruppen = set()
        for a in alte:
            gruppen |= alt_gruppen[a]
        eintrag = {
            "neuer_schluessel": n,
            "alte_schluessel": sorted(alte),
            "namen": sorted({x for a in alte for x in alt_namen[a]}),
            "gruppen": len({g for g in gruppen if g is not None}),
            "alben": sum(alt_alben[a] for a in alte),
            "treffer": sum(alt_treffer[a] for a in alte),
        }
        (mehrdeutig if eintrag["gruppen"] > 1 else zusammen).append(eintrag)

    # Die Gegenrichtung: Zerfaellt ein heutiger Schluessel? Die neue Faltung
    # ist groeber, das darf nicht vorkommen — geprueft statt angenommen.
    gespalten = []
    for a, _ in alt_gruppen.items():
        neue = {neue_faltung(x) for x in alt_namen[a]}
        if len(neue) > 1:
            gespalten.append({"alter_schluessel": a, "namen": sorted(alt_namen[a]),
                              "neue_schluessel": sorted(neue)})

    return {
        "alben_gesamt": len([x for x in alben if isinstance(x, dict)]),
        "schluessel_heute": len(alt_gruppen),
        "zusammenfuehrung": sorted(zusammen, key=lambda e: -e["alben"]),
        "mehrdeutigkeit": sorted(mehrdeutig, key=lambda e: -e["alben"]),
        "aufspaltung": gespalten,
    }


def berichten(ergebnis: dict, mit_namen: bool) -> int:
    z = ergebnis["zusammenfuehrung"]
    m = ergebnis["mehrdeutigkeit"]
    s = ergebnis["aufspaltung"]

    print("Faltungs-Sonde (#83) — es wurde NICHTS geschrieben.")
    print()
    print("  verwaltete Alben insgesamt      %d" % ergebnis["alben_gesamt"])
    print("  Namensschluessel heute          %d" % ergebnis["schluessel_heute"])
    print("  Zusammenfuehrungen (gewollt)    %d" % len(z))
    print("  Mehrdeutigkeiten (teuer)        %d" % len(m))
    print("  Aufspaltungen (darf nicht sein) %d" % len(s))
    print()

    if not z and not m and not s:
        print("NICHTS ZU ENTSCHEIDEN. Die neue Faltung aendert an diesem Bestand")
        print("keine einzige Zuordnung — die Wanderung waere folgenlos.")
        return 0

    def zeige(titel, liste, erklaerung):
        if not liste:
            return
        print(titel)
        print("  " + erklaerung)
        for e in liste:
            print("  - %d Alben, %d verknuepfte Treffer, %d Gruppe(n), "
                  "%d heutige Schluessel"
                  % (e["alben"], e["treffer"], e["gruppen"], len(e["alte_schluessel"])))
            if mit_namen:
                for name in e["namen"]:
                    print("      %r" % name)
        print()

    zeige("ZUSAMMENFUEHRUNG — dieselbe Gruppe, heute zwei Schluessel:",
          z, "Der gewollte Fall: Der Nutzer findet seine Gruppe wieder.")
    zeige("MEHRDEUTIGKEIT — verschiedene Gruppen unter einem Namen:",
          m, "Der teure Fall: Danach antwortet die Vorschau fuer BEIDE mit "
             "\"keine Gruppe\" (#78). Jeder einzelne gehoert angesehen.")

    if s:
        print("AUFSPALTUNG — das darf nicht vorkommen:")
        for e in s:
            print("  - heutiger Schluessel %r zerfiele in %d"
                  % (e["alter_schluessel"], len(e["neue_schluessel"])))
            if mit_namen:
                for name in e["namen"]:
                    print("      %r" % name)
        print("  Wenn das auftritt, ist die neue Faltung NICHT groeber als die")
        print("  alte, und der ganze Vorschlag gehoert neu gedacht.")
        print()

    if not mit_namen:
        print("Die Namen stehen hier nicht: Sie sind Personendaten. Mit --namen")
        print("zeigt die Sonde sie an — diese Ausgabe bleibt dann lokal.")
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
                   help="Albumnamen mit ausgeben (Personendaten, bleibt lokal)")
    args = p.parse_args(argv)

    try:
        alben = lies(args.accounts_json)
    except FileNotFoundError:
        print("Datei nicht gefunden: %s" % args.accounts_json, file=sys.stderr)
        return 2
    except (ValueError, json.JSONDecodeError) as exc:
        print("Kein lesbarer Bestand: %s" % exc, file=sys.stderr)
        return 2

    return berichten(messen(alben), args.namen)


if __name__ == "__main__":
    sys.exit(main())
