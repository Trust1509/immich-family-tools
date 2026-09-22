#!/usr/bin/env python
"""Selbsttest der Faltungs-Sonde.

    python scripts/faltung-sonde-selbsttest.py

WARUM ES DIESE DATEI GIBT: Die Sonde soll eine Owner-Entscheidung tragen —
„ändert sich etwas, ja oder nein?". Eine Sonde, die immer „nein" sagt, fühlt
sich genauso an wie eine, die misst. Jede ihrer Aussagen muss deshalb einmal
FALSCH gewesen sein können (`docs/agents/lehren.md` §18, §21).

**Die erste Fassung dieser Datei war grün und hat wenig bewiesen.** Sie
prüfte `messen()` und ließ `berichten()` fast unberührt — also genau die
Schicht, in der die PII-Schranke sitzt. Von sechzehn Mutationen überlebten
acht, darunter „drucke Namen immer". Und sie war aus derselben Vorstellung
gebaut wie die Sonde (gespeicherte Namen gegeneinander statt Antworten),
konnte deren Grundfehler also nicht sehen. Diese Fassung fährt die Sonde
deshalb als Unterprozess und prüft die AUSGABE.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata

# Kein Bytecode neben dem geprueften Baum: Die Datei, die "schreibt nichts"
# in ihren Kopf schreibt, soll selbst nichts hinterlassen.
sys.dont_write_bytecode = True

for _kanal in (sys.stdout, sys.stderr):
    try:
        _kanal.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONDE = os.path.join(WURZEL, "scripts", "faltung-sonde.py")

import contextlib
import importlib.util

_spec = importlib.util.spec_from_file_location("faltung_sonde", SONDE)
sonde = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sonde)

GRUEN = 0
ROT = 0
MUELL = []


def pruefe(text, bedingung, einzelheit=""):
    global GRUEN, ROT
    if bedingung:
        print("  bestanden   %s" % text)
        GRUEN += 1
    else:
        print("  FEHLGESCHLAGEN  %s" % text)
        if einzelheit:
            print("      %s" % (einzelheit,))
        ROT += 1


def album(name, gid="g1", treffer=0):
    return {"id": "a%d" % len(MUELL), "album_name": name, "group_id": gid,
            "album_id": "immich-x", "match_id": "m", "owner_account_id": "k1",
            "linked_match_ids": ["t%d" % i for i in range(treffer)],
            "person_refs": [], "created_at": "2026-01-01T00:00:00"}


def schreibe(alben) -> str:
    d = tempfile.mkdtemp()
    MUELL.append(d)
    p = os.path.join(d, "accounts.json")
    io.open(p, "w", encoding="utf-8").write(
        json.dumps({"accounts": {}, "managed_albums": alben}))
    return p


def roh(inhalt: str) -> str:
    d = tempfile.mkdtemp()
    MUELL.append(d)
    p = os.path.join(d, "accounts.json")
    io.open(p, "w", encoding="utf-8").write(inhalt)
    return p


def lauf(pfad, *args):
    p = subprocess.run([sys.executable, "-B", SONDE, pfad] + list(args),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


NFC = unicodedata.normalize("NFC", "Café Ohnesorg")
NFD = unicodedata.normalize("NFD", "Café Ohnesorg")
GEHEIM = "Ohnesorg"

print("Selbsttest der Faltungs-Sonde\n")

# ---------------------------------------------------------------- 1 Faltungen
print("1  Die beiden Faltungen")

try:
    sys.path.insert(0, os.path.join(WURZEL, "backend"))
    from services.config_store import ConfigStore

    proben = ["Oma", "  Oma  ", "OMA", "", None, 42, "Café", "İstanbul",
              "Straße", "​X", "ẞ", "Ĥ̱"]
    abweichung = [x for x in proben
                  if sonde.alte_faltung(x) != ConfigStore._name_key(x)]
    pruefe("alte_faltung ist Zeichen fuer Zeichen _name_key",
           not abweichung, abweichung)
except ImportError as exc:
    # Kein Fehlschlag: Die Sonde ist ausdruecklich dafuer gebaut, OHNE den
    # installierten Code zu laufen. Dass der Vergleich dann entfaellt, muss
    # aber dastehen statt still zu verschwinden.
    print("  uebersprungen   alte_faltung gegen _name_key (%s)" % exc)

pruefe("NFD und NFC sind heute VERSCHIEDEN (der Anlass)",
       sonde.alte_faltung(NFD) != sonde.alte_faltung(NFC))
pruefe("NFD und NFC fallen neu zusammen",
       sonde.neue_faltung(NFD) == sonde.neue_faltung(NFC))
pruefe("Strasse und Straße fallen neu zusammen",
       sonde.neue_faltung("Straße") == sonde.neue_faltung("Strasse"))
pruefe("Strasse und Straße sind heute verschieden",
       sonde.alte_faltung("Straße") != sonde.alte_faltung("Strasse"))
pruefe("Nullbreiten-Leerzeichen bleibt ein Unterschied (bewusst)",
       sonde.neue_faltung("​X") != sonde.neue_faltung("X"))


# DIE WIDERLEGTE PRAEMISSE. "Die neue Faltung ist groeber" stimmte nicht:
# `casefold` nach `NFC` laesst ein nicht normalisiertes Ergebnis zurueck.
# Ohne das zweite NFC fielen Namen AUSEINANDER, die heute zusammenfallen.
def ohne_zweites_nfc(s):
    return unicodedata.normalize("NFC", str(s)).strip().casefold()


spalter = [(chr(cp), chr(cp).lower(), chr(k))
           for cp in range(0x0000, 0x3000)
           for k in (0x0331, 0x0300, 0x0327, 0x0308, 0x0301)
           if chr(cp).lower() != chr(cp)
           and sonde.alte_faltung(chr(cp) + chr(k))
           == sonde.alte_faltung(chr(cp).lower() + chr(k))
           and ohne_zweites_nfc(chr(cp) + chr(k))
           != ohne_zweites_nfc(chr(cp).lower() + chr(k))]
pruefe("ohne das zweite NFC zerfielen reale Zeichenpaare",
       len(spalter) >= 5, len(spalter))
pruefe("mit dem zweiten NFC zerfaellt keines davon",
       all(sonde.neue_faltung(g + k) == sonde.neue_faltung(kl + k)
           for g, kl, k in spalter),
       [(g, kl, k) for g, kl, k in spalter
        if sonde.neue_faltung(g + k) != sonde.neue_faltung(kl + k)][:3])

# ------------------------------------------------- 2 Der Fall des falschen Nein
print("\n2  Der Fall, an dem die erste Fassung gescheitert ist")

# EIN Album. Die erste Fassung meldete Exit 0 "folgenlos" — dabei findet die
# Abfrage "Strasse" heute nichts und nachher die Gruppe. Beide Pruefstimmen
# haben genau das unabhaengig gemessen.
rc, aus = lauf(schreibe([album("Straße", "g1")]))
pruefe("ein einzelnes Album mit verschobener Faltung ist NICHT folgenlos",
       rc == 1 and "NICHTS AENDERT SICH" not in aus, (rc, aus[:300]))
pruefe("und es wird als Erreichbarkeit gemeldet",
       "Erreichbarkeit aendert sich      1" in aus, aus[:400])

rc, aus = lauf(schreibe([album("Oma", "g1"), album("Opa", "g2")]))
pruefe("ein Bestand ohne jede Verschiebung ist folgenlos",
       rc == 0 and "NICHTS AENDERT SICH" in aus, (rc, aus[:300]))

# -------------------------------------------------------- 3 Die Klassifikation
print("\n3  Antwort, Erreichbarkeit, Mehrdeutigkeit, Aufspaltung")

e = sonde.messen([album(NFC, "g1"), album(NFD, "g1")])
pruefe("zwei Schreibweisen DERSELBEN Gruppe erzeugen keine Mehrdeutigkeit",
       not e["mehrdeutigkeit"], e["mehrdeutigkeit"])

e = sonde.messen([album(NFC, "g1"), album(NFD, "g2")])
pruefe("zwei Schreibweisen VERSCHIEDENER Gruppen erzeugen Mehrdeutigkeit",
       len(e["mehrdeutigkeit"]) == 1, e["mehrdeutigkeit"])
pruefe("und die Antwort aendert sich fuer beide",
       len(e["antwort_anders"]) == 2, e["antwort_anders"])

# Was heute schon mehrdeutig ist, wird nicht als NEUE Mehrdeutigkeit gemeldet:
# Die Abfrage antwortet vorher wie nachher mit "keine Gruppe". Der Owner soll
# nicht zu einem --namen-Lauf gedraengt werden, fuer den es nichts zu sehen
# gibt (Blindpruefer, Nacharbeit 1).
e = sonde.messen([album("Oma", "g1"), album("oma", "g2")])
pruefe("schon heute mehrdeutig -> keine neue Meldung",
       not e["mehrdeutigkeit"] and not e["antwort_anders"], e)

# Die Gruppenzaehlung folgt dem Backend: leere Kennung ist KEINE Gruppe.
e = sonde.messen([album("Straße", "g2"), album("Strasse", "")])
pruefe("eine leere group_id zaehlt nicht als Gruppe",
       not e["mehrdeutigkeit"], e["mehrdeutigkeit"])

e = sonde.messen([album(NFC, ""), album(NFD, "")])
pruefe("zwei Alben ganz ohne Gruppe erzeugen keine Mehrdeutigkeit",
       not e["mehrdeutigkeit"], e)

# ---------------------------------------------------------- 4 Die PII-Schranke
print("\n4  Die PII-Schranke — jede Zeile, nicht nur die naheliegende")

faelle = {
    "Erreichbarkeit": [album("Straße " + GEHEIM, "g1")],
    "Antwort": [album(NFC.replace("Ohnesorg", GEHEIM), "g1"),
                album(NFD.replace("Ohnesorg", GEHEIM), "g2")],
}
for titel, alben in faelle.items():
    rc, aus = lauf(schreibe(alben))
    pruefe("%s: ohne --namen kein Name in der Ausgabe" % titel,
           GEHEIM not in aus and GEHEIM.lower() not in aus.lower(), aus[:400])
    rc2, aus2 = lauf(schreibe(alben), "--namen")
    pruefe("%s: mit --namen steht er da" % titel, GEHEIM in aus2, aus2[:300])

# Der Aufspaltungs-Zweig, Ende zu Ende. Genau dieser Zweig hat die Namen
# ungeschuetzt gedruckt, und keine Probe der ersten Fassung hat ihn je
# aufgerufen — beide Pruefstimmen haben es unabhaengig gefunden.
echte = sonde.neue_faltung
try:
    sonde.neue_faltung = lambda n: str(n)
    e = sonde.messen([album("Oma " + GEHEIM, "g1"), album("OMA " + GEHEIM, "g1")])
    pruefe("eine zerlegende Faltung wird als Aufspaltung gemeldet",
           len(e["aufspaltung"]) == 1, e["aufspaltung"])

    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        code = sonde.berichten(e, False)
    ausgabe = puffer.getvalue()
    pruefe("Aufspaltung ohne --namen: kein Name in der Ausgabe",
           GEHEIM not in ausgabe and GEHEIM.lower() not in ausgabe.lower(),
           ausgabe[:400])
    # M11 aus dem Mutationslauf des Blindpruefers: Eine REINE Aufspaltung
    # darf nicht "nichts aendert sich" heissen.
    pruefe("eine reine Aufspaltung ist nicht folgenlos",
           code == 1 and "NICHTS AENDERT SICH" not in ausgabe,
           (code, ausgabe[:300]))

    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        sonde.berichten(e, True)
    pruefe("Aufspaltung mit --namen: der Name steht da",
           GEHEIM in puffer.getvalue(), puffer.getvalue()[:300])
finally:
    sonde.neue_faltung = echte

# ----------------------------------------------------- 5 Nicht entscheidbar
print("\n5  Exit 2 — fuer jeden Weg, der kein Bestand ist")

for titel, pfad in [
    ("fehlende Datei", os.path.join(tempfile.mkdtemp(), "weg.json")),
    ("ein Verzeichnis", tempfile.mkdtemp()),
    ("kaputtes JSON", roh("{kein json")),
    ("JSON ohne Objekt an der Wurzel", roh("[1,2,3]")),
    ("Objekt ohne 'accounts'", roh('{"managed_albums": []}')),
    ("Objekt ohne 'managed_albums'", roh('{"accounts": {}}')),
    ("managed_albums keine Liste", roh('{"accounts": {}, "managed_albums": 7}')),
    ("ein Eintrag ist kein Objekt",
     roh('{"accounts": {}, "managed_albums": ["x"]}')),
]:
    MUELL.append(os.path.dirname(pfad))
    rc, aus = lauf(pfad)
    pruefe("%s -> Exit 2" % titel, rc == 2, (rc, aus[:200]))
    pruefe("%s -> und sagt, dass es kein Nein ist" % titel,
           "KEIN" in aus or "NICHT ENTSCHEIDBAR" in aus, aus[:200])

# Die nicht hashbare Nachbarstelle, an der die erste Fassung abstuerzte —
# mit Exit 1, was laut Vertrag "es gibt etwas zu entscheiden" heisst.
rc, aus = lauf(schreibe([{"album_name": "X", "group_id": ["a", "b"]}]))
pruefe("group_id als Liste -> Exit 2, kein Traceback",
       rc == 2 and "Traceback" not in aus, (rc, aus[:300]))

rc, aus = lauf(schreibe([{"album_name": None, "group_id": "g1"},
                         {"album_name": 42, "group_id": "g2"},
                         {"group_id": "g3"},
                         {"album_name": "X", "group_id": "g4",
                          "linked_match_ids": "kaputt"}]))
pruefe("fehlende und falsch getippte album_name werfen nicht",
       rc in (0, 1) and "Traceback" not in aus, (rc, aus[:300]))

# ------------------------------------------------------------ 6 Schreibprobe
print("\n6  Die Sonde schreibt nichts")

pfad = schreibe([album("Straße " + GEHEIM, "g1")])
ordner = os.path.dirname(pfad)
vorher = io.open(pfad, encoding="utf-8").read()
vorher_liste = sorted(os.listdir(ordner))
lauf(pfad)
lauf(pfad, "--namen")
pruefe("accounts.json ist Zeichen fuer Zeichen unveraendert",
       io.open(pfad, encoding="utf-8").read() == vorher)
pruefe("und daneben ist nichts entstanden",
       sorted(os.listdir(ordner)) == vorher_liste, sorted(os.listdir(ordner)))

for _d in MUELL:
    shutil.rmtree(_d, ignore_errors=True)

print()
print("%d bestanden, %d fehlgeschlagen" % (GRUEN, ROT))

# MINDESTZAHL — gegen den stillen Verlust von Faellen. GEMESSEN, nicht
# geschaetzt; wer Faelle ergaenzt, zieht sie mit. Sie greift nur gegen
# geloeschte Faelle, nicht gegen entkernte — dagegen hilft, dass jeder Fall
# die AUSGABE prueft und nicht nur den Rueckgabewert.
MINDESTENS = 45
if GRUEN + ROT < MINDESTENS:
    print("FEHLER: nur %d Faelle gelaufen, erwartet mindestens %d."
          % (GRUEN + ROT, MINDESTENS))
    sys.exit(1)

sys.exit(1 if ROT else 0)
