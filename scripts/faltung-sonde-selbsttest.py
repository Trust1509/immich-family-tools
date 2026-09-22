#!/usr/bin/env python
"""Selbsttest der Faltungs-Sonde.

    python scripts/faltung-sonde-selbsttest.py

WARUM ES DIESE DATEI GIBT: Die Sonde soll eine Owner-Entscheidung tragen —
„verschmilzt etwas, ja oder nein?". Eine Sonde, die immer „nein" sagt, fühlt
sich genauso an wie eine, die misst. Jede ihrer Aussagen muss deshalb einmal
FALSCH gewesen sein können (`docs/agents/lehren.md` §18, §21).

Jeder Fall baut einen erfundenen Bestand, lässt die Sonde darauf los und
prüft EINE Aussage. Keine echten Namen, kein Netz, keine Schreibvorgänge.
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unicodedata

for _kanal in (sys.stdout, sys.stderr):
    try:
        _kanal.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONDE = os.path.join(WURZEL, "scripts", "faltung-sonde.py")
sys.path.insert(0, os.path.join(WURZEL, "scripts"))

import importlib.util
_spec = importlib.util.spec_from_file_location("faltung_sonde", SONDE)
sonde = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sonde)

GRUEN = 0
ROT = 0


def bestanden(text):
    global GRUEN
    print("  bestanden   %s" % text)
    GRUEN += 1


def fehlgeschlagen(text, einzelheit=""):
    global ROT
    print("  FEHLGESCHLAGEN  %s" % text)
    if einzelheit:
        print("      %s" % einzelheit)
    ROT += 1


def pruefe(text, bedingung, einzelheit=""):
    bestanden(text) if bedingung else fehlgeschlagen(text, einzelheit)


def album(name, gid, treffer=0):
    return {"id": "a-%s-%s" % (gid, abs(hash(name)) % 9999), "album_name": name,
            "group_id": gid, "album_id": "immich-x", "match_id": "m",
            "linked_match_ids": ["t%d" % i for i in range(treffer)],
            "person_refs": []}


def schreibe(alben) -> str:
    d = tempfile.mkdtemp()
    p = os.path.join(d, "accounts.json")
    io.open(p, "w", encoding="utf-8").write(
        json.dumps({"accounts": {}, "managed_albums": alben}))
    return p


def lauf(pfad, *args):
    p = subprocess.run([sys.executable, SONDE, pfad] + list(args),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


print("Selbsttest der Faltungs-Sonde\n")

# ---------------------------------------------------------------- 1 Faltungen
print("1  Die beiden Faltungen")

# Die Sonde baut `_name_key` nach. Weicht sie ab, misst sie etwas anderes als
# die Anwendung — das ist der eine Fall, in dem eine gruene Sonde nichts wert
# waere.
try:
    sys.path.insert(0, os.path.join(WURZEL, "backend"))
    from services.config_store import ConfigStore
    proben = ["Oma", "  Oma  ", "OMA", "", None, 42, "Café", "İstanbul", "Straße"]
    gleich = all(sonde.alte_faltung(x) == ConfigStore._name_key(x) for x in proben)
    pruefe("alte_faltung ist Zeichen fuer Zeichen _name_key", gleich,
           [(x, sonde.alte_faltung(x), ConfigStore._name_key(x))
            for x in proben if sonde.alte_faltung(x) != ConfigStore._name_key(x)])
except Exception as exc:                                   # pragma: no cover
    fehlgeschlagen("alte_faltung gegen _name_key gehalten", repr(exc))

NFD = unicodedata.normalize("NFD", "Café Oma")
NFC = unicodedata.normalize("NFC", "Café Oma")
pruefe("NFD und NFC sind heute VERSCHIEDEN (der Anlass)",
       sonde.alte_faltung(NFD) != sonde.alte_faltung(NFC))
pruefe("NFD und NFC fallen neu zusammen",
       sonde.neue_faltung(NFD) == sonde.neue_faltung(NFC))
pruefe("Strasse und Straße fallen neu zusammen",
       sonde.neue_faltung("Straße") == sonde.neue_faltung("Strasse"))
pruefe("Strasse und Straße sind heute verschieden",
       sonde.alte_faltung("Straße") != sonde.alte_faltung("Strasse"))
pruefe("Nullbreiten-Leerzeichen bleibt ein Unterschied (bewusst)",
       sonde.neue_faltung("​Testalbum") != sonde.neue_faltung("Testalbum"))

# ------------------------------------------------------------ 2 Klassifikation
print("\n2  Zusammenfuehrung, Mehrdeutigkeit, Aufspaltung")

e = sonde.messen([album(NFC, "g1", treffer=3), album(NFD, "g1", treffer=2)])
pruefe("gleiche Gruppe -> Zusammenfuehrung",
       len(e["zusammenfuehrung"]) == 1 and not e["mehrdeutigkeit"], e)
pruefe("die Zahlen stimmen (2 Alben, 5 Treffer, 1 Gruppe)",
       e["zusammenfuehrung"][0]["alben"] == 2
       and e["zusammenfuehrung"][0]["treffer"] == 5
       and e["zusammenfuehrung"][0]["gruppen"] == 1,
       e["zusammenfuehrung"][0])

e = sonde.messen([album(NFC, "g1"), album(NFD, "g2")])
pruefe("verschiedene Gruppen -> Mehrdeutigkeit",
       len(e["mehrdeutigkeit"]) == 1 and not e["zusammenfuehrung"], e)

e = sonde.messen([album("Oma", "g1"), album("Opa", "g2")])
pruefe("unaehnliche Namen ergeben gar nichts",
       not e["zusammenfuehrung"] and not e["mehrdeutigkeit"], e)

e = sonde.messen([album("Oma", "g1"), album("  OMA ", "g1")])
pruefe("was heute schon zusammenfaellt, wird nicht gemeldet",
       not e["zusammenfuehrung"] and not e["mehrdeutigkeit"], e)

# Die Aufspaltungs-Meldung kann an echten Daten nicht ausloesen — die neue
# Faltung IST groeber. Bewiesen wird deshalb der MELDER, mit einer Faltung,
# die zerlegt statt zusammenzuziehen. Ohne diesen Fall waere die Zeile
# "Aufspaltungen: 0" eine Behauptung ueber eine ungepruefte Mechanik.
echte_neue = sonde.neue_faltung
try:
    sonde.neue_faltung = lambda n: str(n)          # unterscheidet Gross/Klein
    e = sonde.messen([album("Oma", "g1"), album("OMA", "g1")])
    pruefe("eine zerlegende Faltung wird als Aufspaltung gemeldet",
           len(e["aufspaltung"]) == 1, e)
finally:
    sonde.neue_faltung = echte_neue

e = sonde.messen([album("Oma", "g1"), album("OMA", "g1")])
pruefe("mit der echten Faltung gibt es keine Aufspaltung",
       not e["aufspaltung"], e)

# -------------------------------------------------------------- 3 Robustheit
print("\n3  Was ein handbearbeiteter Bestand hergibt")

e = sonde.messen([{"album_name": None, "group_id": "g1"},
                  {"album_name": 42, "group_id": "g2"},
                  "kein Objekt",
                  {"group_id": "g3"},
                  {"album_name": "X", "group_id": "g4", "linked_match_ids": "kaputt"}])
pruefe("kaputte Eintraege werfen nicht", isinstance(e, dict), e)
pruefe("ein Nicht-Objekt zaehlt nicht als Album", e["alben_gesamt"] == 4, e)

# --------------------------------------------------------- 4 Ausgabe und Exit
print("\n4  Ausgabe, Exit-Codes und die PII-Schranke")

rc, aus = lauf(schreibe([album("Oma", "g1"), album("Opa", "g2")]))
pruefe("folgenloser Bestand -> Exit 0", rc == 0, rc)
pruefe("und sagt es in Worten", "NICHTS ZU ENTSCHEIDEN" in aus, aus)

GEHEIM = "Café Ohnesorg"
pfad = schreibe([album(unicodedata.normalize("NFC", GEHEIM), "g1"),
                 album(unicodedata.normalize("NFD", GEHEIM), "g2")])
rc, aus = lauf(pfad)
pruefe("etwas zu entscheiden -> Exit 1", rc == 1, rc)
# Die Schranke, um die es geht: Ohne --namen darf KEIN Albumname in der
# Ausgabe stehen. Ein Bericht, der Personendaten mitbringt, wandert sonst in
# ein Issue, weil er nuetzlich aussieht.
pruefe("ohne --namen steht KEIN Name in der Ausgabe",
       "Ohnesorg" not in aus and "ohnesorg" not in aus.lower(), aus)
pruefe("aber die Zahl steht da", "Mehrdeutigkeiten (teuer)        1" in aus, aus)

rc, aus = lauf(pfad, "--namen")
pruefe("mit --namen steht er da", "Ohnesorg" in aus, aus[:400])
pruefe("und die Ausgabe warnt davor", "gehoert nicht in ein Issue" in aus, aus[-300:])

rc, aus = lauf(os.path.join(tempfile.mkdtemp(), "gibt-es-nicht.json"))
pruefe("fehlende Datei -> Exit 2", rc == 2, (rc, aus))

d = tempfile.mkdtemp()
p = os.path.join(d, "kaputt.json")
io.open(p, "w", encoding="utf-8").write("{kein json")
rc, aus = lauf(p)
pruefe("kaputtes JSON -> Exit 2", rc == 2, (rc, aus))

p2 = os.path.join(d, "liste.json")
io.open(p2, "w", encoding="utf-8").write("[1,2,3]")
rc, aus = lauf(p2)
pruefe("JSON ohne Objekt an der Wurzel -> Exit 2", rc == 2, (rc, aus))

# ------------------------------------------------------------ 5 Schreibprobe
print("\n5  Die Sonde schreibt nichts")

alben = [album(unicodedata.normalize("NFC", GEHEIM), "g1"),
         album(unicodedata.normalize("NFD", GEHEIM), "g2")]
pfad = schreibe(alben)
vorher = io.open(pfad, encoding="utf-8").read()
vorher_liste = sorted(os.listdir(os.path.dirname(pfad)))
lauf(pfad)
lauf(pfad, "--namen")
pruefe("accounts.json ist Zeichen fuer Zeichen unveraendert",
       io.open(pfad, encoding="utf-8").read() == vorher)
pruefe("und daneben ist nichts entstanden",
       sorted(os.listdir(os.path.dirname(pfad))) == vorher_liste,
       sorted(os.listdir(os.path.dirname(pfad))))

print()
print("%d bestanden, %d fehlgeschlagen" % (GRUEN, ROT))

# MINDESTZAHL — ein Waechter gegen den stillen Verlust von Faellen. Gemessen,
# nicht geschaetzt: ein voller Lauf meldet 27.
MINDESTENS = 27
if GRUEN + ROT < MINDESTENS:
    print("FEHLER: nur %d Faelle gelaufen, erwartet mindestens %d."
          % (GRUEN + ROT, MINDESTENS))
    sys.exit(1)

sys.exit(1 if ROT else 0)
