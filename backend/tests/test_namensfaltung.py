"""Die Namensfaltung ist unicode-fest (#83).

`ConfigStore._name_key` faltete bis hierher mit `strip().lower()` — ohne
Unicode-Normalform und ohne `casefold`. Seit #81 ist das eine **Zusage an den
Nutzer**: `GET /api/sync/album-group` sagt „es gibt keine Gruppe", und für
zwei sichtbar gleiche Namen war das schlicht falsch. Der Nutzer legte dann
eine zweite Gruppe an, ohne zu wissen, dass er eine hatte.

## Warum das ohne Datenwanderung geht

`_name_key` ist **keine gespeicherte Groesse**. Gespeichert wird `group_id`;
die Faltung entsteht bei jedem Zugriff neu (`_gruppen_je_name`,
`existing_group_for_name`, `gruppen_schloss`). Eine andere Faltung schreibt
also nichts um.

Die Lesesonde `scripts/faltung-sonde.py` hat das am echten Bestand gemessen
(26.09.2026, 8 Alben): keine geaenderte Antwort, keine neue Mehrdeutigkeit,
keine Aufspaltung. Die Einstufung in #83 stand auf R3 und ist auf **R2**
korrigiert.

## Wo die Faltung gespeicherte Werte ENTSCHEIDET

Hier stand eine zu enge Behauptung: die Faltung wirke dauerhaft nur beim
Rueckspiel einer Sicherung von vor v1.7.0. **Das ist falsch, und beide
Pruefstimmen haben es unabhaengig gemessen.** Richtig ist:

* Sie schreibt **keinen bestehenden Schluessel um** — der Schluessel wird
  nirgends gespeichert.
* Sie **entscheidet jeden neu vergebenen**: `group_id_for_name` beim Anlegen
  (die Kennung landet im gespeicherten Album) und `_backfill_group_ids` fuer
  jedes Album **ohne** Kennung. Der Backfill haengt allein an der fehlenden
  Kennung, NICHT an der Schemaversion — sein eigener Docstring nennt den Fall
  „ein Album, das zwischen zwei Starts dazukommt".

## Und die Kehrseite des Groeber-Werdens

Traegt ein Bestand zwei Schreibweisen desselben Namens in VERSCHIEDENEN
Gruppen, fallen ihre Schluessel jetzt zusammen — und die
Mehrdeutigkeits-Regel aus #78 antwortet fuer beide mit „keine Gruppe", wo
vorher jede ihre eigene fand. **Dieser Bestand ist nicht konstruiert: Er ist
das Ergebnis genau des Fehlers, den #83 behebt** (der Nutzer fand die Gruppe
nicht und legte eine zweite an).

Deshalb laeuft die Abfrage zweistufig (`_gruppe_fuer_namen`): neue Faltung,
und wo sie KEINE eindeutige Antwort liefert — mehrdeutig ODER leer (gemessen
#111) —, die alte. Die Proben dazu stehen unten.
"""
import unicodedata

import pytest

from services.config_store import ConfigStore

FALTUNG = ConfigStore._name_key


# Jede Zeile ist eine Klasse, die real vorkommt: zwei Schreibweisen desselben
# Namens, die ein Mensch oder ein Geraet erzeugt.
GLEICH = [
    ("Gross/Klein", "Oma Erna", "oma erna"),
    ("Leerraum aussen", "  Oma Erna  ", "Oma Erna"),
    ("NFC gegen NFD",
     unicodedata.normalize("NFC", "Café Oma"),
     unicodedata.normalize("NFD", "Café Oma")),
    ("scharfes S", "Straßenfest", "Strassenfest"),
    ("scharfes S in Versalien", "STRASSENFEST", "Straßenfest"),
    ("grosses scharfes S", "STRAẞENFEST", "Strassenfest"),
    ("tuerkisches I", "İstanbul", "i̇stanbul"),
    ("griechisches Schluss-Sigma", "ΟΔΥΣΣΕΥΣ", "Οδυσσευς"),
    ("Ligatur", "ﬁsch", "fisch"),
    ("Kombinierer nach casefold", "Ĥ̱ans", "ẖ̂ans"),
]

VERSCHIEDEN = [
    ("verschiedene Namen", "Oma Erna", "Opa Erwin"),
    # BENANNTE GRENZE: Nullbreiten-Zeichen werden NICHT entfernt. Das waere
    # eine zweite, eigenstaendige Entscheidung — und eine, die Namen
    # zusammenzieht, die in Immich verschieden heissen. Wer sie trifft,
    # aendert diese Zeile bewusst.
    ("Nullbreiten-Leerzeichen bleibt ein Unterschied", "​Oma", "Oma"),
    # Leerraum INNEN ist ein echter Unterschied, kein Faltungsfall.
    ("Leerraum innen", "Oma  Erna", "Oma Erna"),
    # BENANNTE ENTSCHEIDUNG: NFC, nicht NFKC. Die Kompatibilitaetszerlegung
    # wuerde Vollbreiten-Zeichen, eingekreiste Ziffern und roemische
    # Zahlzeichen auf ihre ASCII-Form ziehen — also Namen zusammenfuehren, die
    # in Immich sichtbar verschieden heissen. Ohne diese Zeile ist die Wahl
    # zwischen NFC und NFKC von nichts gehalten (Mutationslauf, 26.09.2026).
    ("Vollbreiten-Ziffer bleibt verschieden", "Fest １", "Fest 1"),
    ("roemisches Zahlzeichen bleibt verschieden", "Teil Ⅻ", "Teil XII"),
]


@pytest.mark.parametrize("klasse,a,b", GLEICH, ids=[k for k, _, _ in GLEICH])
def test_sichtbar_gleiche_namen_falten_gleich(klasse, a, b):
    assert FALTUNG(a) == FALTUNG(b), (klasse, FALTUNG(a), FALTUNG(b))


@pytest.mark.parametrize("klasse,a,b", VERSCHIEDEN,
                         ids=[k for k, _, _ in VERSCHIEDEN])
def test_verschiedene_namen_falten_verschieden(klasse, a, b):
    assert FALTUNG(a) != FALTUNG(b), (klasse, FALTUNG(a))


def test_die_faltung_ist_auf_sich_selbst_anwendbar():
    """Zweimal falten muss dasselbe ergeben wie einmal.

    Das ist die Eigenschaft, an der die erste Fassung des Vorschlags
    gescheitert ist: `casefold` NACH `NFC` laesst ein nicht mehr
    normalisiertes Ergebnis zurueck. Ohne den zweiten Normalisierungs-
    durchgang faellt `Ĥ` mit Kombinierer anders als sein Kleinbuchstabe —
    die Faltung waere dann stellenweise FEINER als die alte statt groeber.
    """
    for _, a, b in GLEICH + VERSCHIEDEN:
        for x in (a, b):
            assert FALTUNG(FALTUNG(x)) == FALTUNG(x), x


def _kodierungspaare():
    """Die Proben des NFC/NFD-Sweeps — entdoppelt, damit die Zahl stimmt.

    Eigene Funktion, damit die REICHWEITE der Schleife pruefbar ist. Der
    Blindpruefer hat gemessen, dass sich die Schleife entkernen liess
    (`range(0)`, leere Kombinierer-Liste) und die Probe gruen blieb — und
    zusammen mit der Mutation „erstes NFC weg" ueberlebte diese wieder in
    BEIDEN Gates. Eine Schleife, die nichts durchlaeuft, erfuellt `== []`.
    """
    roh = set()
    for cp in range(0x3000):
        for komb in ("\u0300", "\u0301", "\u0308", "\u0327", "\u0331", "\u0345"):
            roh.add(chr(cp) + komb)
            roh.add(chr(cp).lower() + komb)
    return sorted(roh)


def _bricht_kodierung(faltung) -> int:
    """Wie oft diese Faltung NFC und NFD verschieden behandelt."""
    n = 0
    for x in _kodierungspaare():
        if faltung(unicodedata.normalize("NFC", x)) != faltung(
                unicodedata.normalize("NFD", x)):
            n += 1
    return n


def test_beide_kodierungen_desselben_namens_falten_gleich():
    """NFC gegen NFD ueber alle Codepunkte bis U+3000, mit Kombinierern.

    Das ist die Eigenschaft, um die es in #83 ueberhaupt geht: Dasselbe
    sichtbare Zeichen kann in zwei Byte-Folgen vorliegen, je nachdem, welches
    Geraet den Namen erzeugt hat.

    UND es ist die Probe, die das ERSTE `normalize` traegt.
    """
    assert _bricht_kodierung(FALTUNG) == 0


def test_dieser_sweep_erreicht_wirklich_etwas():
    """Die Reichweite der Schleife, nicht nur ihr Ergebnis.

    Zwei Zusicherungen, und beide sind noetig:

    1. Die Probenmenge hat eine Untergrenze — eine leere Schleife erfuellt
       jede Gleichheit.
    2. Die Schleife FINDET die 279 Faelle, wenn man ihr die defekte Faltung
       gibt (nur ein `normalize`, nach dem `casefold`). Damit ist belegt, dass
       sie die interessante Gegend ueberhaupt betritt — und die Zahl im
       Docstring ist keine Behauptung mehr, sondern eine Zusicherung.

    Zur Zahl selbst: Es sind **279 eindeutige** Zeichenketten. Eine fruehere
    Fassung nannte 558 — dieselben Faelle doppelt gezaehlt, weil die Schleife
    Gross- und Kleinbuchstabe getrennt besuchte und beide fuer
    Kleinbuchstaben dasselbe sind. Der Fremdpruefer hat nachgerechnet.
    """
    proben = _kodierungspaare()
    assert len(proben) >= 60000, len(proben)

    def ohne_erstes_nfc(x):
        return unicodedata.normalize("NFC", str(x).strip().casefold())

    assert _bricht_kodierung(ohne_erstes_nfc) == 279


def _grossklein_paare():
    """Gross/Klein-Paare mit Kombinierer — die Proben des Aufspaltungs-Sweeps."""
    aus = []
    for cp in range(0x3000):
        gross = chr(cp)
        klein = gross.lower()
        if klein == gross:
            continue
        for komb in ("\u0331", "\u0300", "\u0327", "\u0308", "\u0301"):
            aus.append((gross + komb, klein + komb))
    return aus


def _zerfaellt(faltung) -> int:
    """Wie oft diese Faltung ein Paar trennt, das die alte zusammenfuehrt."""
    def alt(x):
        return str(x).strip().lower()

    return sum(1 for x, y in _grossklein_paare()
               if alt(x) == alt(y) and faltung(x) != faltung(y))


def test_kein_zeichenpaar_faellt_durch_die_neue_faltung_auseinander():
    """Was heute EINEN Schluessel bildet, darf nachher nicht zerfallen.

    Sonst verlieren bestehende Zuordnungen ihren gemeinsamen Namen — die
    Faltung waere stellenweise FEINER geworden statt groeber.
    """
    assert _zerfaellt(FALTUNG) == 0


def test_der_aufspaltungs_sweep_erreicht_wirklich_etwas():
    """Reichweite, aus demselben Grund wie beim Sweep darueber.

    Die Zahl: **zehn** Paare, und zwar zehn (Zeichen, Kombinierer)-
    Kombinationen ueber **sieben** verschiedene Codepunkte — nicht zehn
    Zeichen. Beide Zahlen haengen an der handgewaehlten Kombinierer-Liste;
    diese Probe macht sie zur Zusicherung, damit eine Aenderung an der Liste
    nicht stillschweigend eine andere Behauptung im Docstring hinterlaesst
    (Blindpruefer, Nacharbeit 1).
    """
    assert len(_grossklein_paare()) >= 5000, len(_grossklein_paare())

    def ohne_zweites_nfc(x):
        return unicodedata.normalize("NFC", str(x)).strip().casefold()

    assert _zerfaellt(ohne_zweites_nfc) == 10

    codepunkte = {x[0] for x, y in _grossklein_paare()
                  if str(x).strip().lower() == str(y).strip().lower()
                  and ohne_zweites_nfc(x) != ohne_zweites_nfc(y)}
    assert len(codepunkte) == 7, sorted(hex(ord(c)) for c in codepunkte)


def test_die_faltung_liefert_immer_die_zusammengesetzte_form():
    """Die ZIELNORMALFORM ist NFC, nicht NFD — und das war von nichts gehalten.

    Gemessen vom Blindpruefer: Ersetzt man beide `normalize("NFC", ...)` durch
    `"NFD"`, bleiben 200 Tests und die Sonden-Selbstprobe gruen. Die
    Aequivalenzklassen sind dieselben, ein Verhaltensdefekt entsteht also
    nicht — aber der gespeicherte Vergleichsschluessel saehe anders aus, und
    niemand haette es bemerkt. Wer die Form absichtlich wechselt, aendert
    diese Probe.
    """
    zerlegt = unicodedata.normalize("NFD", "Café")
    assert FALTUNG(zerlegt) == unicodedata.normalize("NFC", "café")
    # Und allgemein: das Ergebnis ist bereits zusammengesetzt.
    for _, a, b in GLEICH + VERSCHIEDEN:
        for x in (a, b):
            ergebnis = FALTUNG(x)
            assert ergebnis == unicodedata.normalize("NFC", ergebnis), repr(x)


def test_die_alten_ausnahmen_gelten_weiter():
    """Kein String, kein Wert, kein Absturz — die Wanderung darf nicht sterben.

    Ein handbearbeiteter Nicht-String liess die Wanderung einmal mit
    AttributeError abbrechen, und `_load` machte daraus „Configuration is
    invalid": Die App startete GAR NICHT MEHR. Der Grund steht im Docstring
    der Funktion; hier steht die Probe dazu.
    """
    assert FALTUNG(None) == ""
    assert FALTUNG("") == ""
    assert FALTUNG("   ") == ""
    assert FALTUNG(42) == "42"


def test_die_abfrage_findet_die_gruppe_jetzt_auch_anders_geschrieben(tmp_path):
    """Die Zusage aus #81 an der echten Tuer, nicht nur an der Faltung."""
    import json

    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {},
        "schema_version": ConfigStore.SCHEMA_VERSION,
        "managed_albums": [{
            "id": "a1", "album_name": "Straßenfest", "group_id": "g1",
            "album_id": "immich-1", "match_id": "m1",
            "owner_account_id": "k1", "person_refs": [],
            "linked_match_ids": [], "created_at": "2026-01-01T00:00:00",
        }],
    }), encoding="utf-8")
    store = ConfigStore(str(pfad))

    assert store.existing_group_for_name("Straßenfest") == "g1"
    assert store.existing_group_for_name("Strassenfest") == "g1", (
        "die Abfrage sagt weiterhin „keine Gruppe“ fuer denselben Namen")
    assert store.existing_group_for_name("STRASSENFEST") == "g1"
    assert store.existing_group_for_name("Sommerfest") is None


def test_rueckspiel_einer_alten_sicherung_gruppiert_nach_der_neuen_faltung(tmp_path):
    """Die EINZIGE Stelle, an der die Faltung stored data beruehrt.

    `_backfill_group_ids` laeuft nur fuer Alben ohne `group_id` — also beim
    Rueckspiel einer Sicherung von vor v1.7.0. Dort entscheidet die Faltung
    ueber die Gruppenbildung, und zwar dauerhaft: Die Kennung wird
    gespeichert. Zwei Alben, die derselbe Mensch gleich nennen wuerde,
    bekommen jetzt EINE Gruppe statt zweier.
    """
    import json

    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {},
        "managed_albums": [
            {"id": "a1", "album_name": "Straßenfest", "album_id": "i1",
             "match_id": "m1", "owner_account_id": "k1", "person_refs": [],
             "created_at": "2026-01-01T00:00:00"},
            {"id": "a2", "album_name": "Strassenfest", "album_id": "i2",
             "match_id": "m2", "owner_account_id": "k1", "person_refs": [],
             "created_at": "2026-01-01T00:00:00"},
            {"id": "a3", "album_name": "Sommerfest", "album_id": "i3",
             "match_id": "m3", "owner_account_id": "k1", "person_refs": [],
             "created_at": "2026-01-01T00:00:00"},
        ],
    }), encoding="utf-8")

    alben = ConfigStore(str(pfad)).get_managed_albums()
    nach_name = {a.album_name: a.group_id for a in alben}
    assert nach_name["Straßenfest"] == nach_name["Strassenfest"], (
        "zwei Schreibweisen desselben Namens bekamen verschiedene Gruppen")
    assert nach_name["Sommerfest"] != nach_name["Straßenfest"]


# ------------------------------------------- Die Kehrseite des Groeber-Werdens

def _store(tmp_path, alben):
    import json

    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": {}, "schema_version": ConfigStore.SCHEMA_VERSION,
        "managed_albums": alben,
    }), encoding="utf-8")
    return ConfigStore(str(pfad))


def _album(name, gid=None):
    a = {"id": "a-" + (gid or name[:6]), "album_name": name, "album_id": "i1",
         "match_id": "m-" + (gid or name[:6]), "owner_account_id": "k1",
         "person_refs": [], "created_at": "2026-01-01T00:00:00"}
    if gid:
        a["group_id"] = gid
    return a


def test_zwei_schreibweisen_in_zwei_gruppen_behalten_ihre_antwort(tmp_path):
    """Der Fall, den die erste Fassung verschlechtert hat.

    Gemessen von Blind- UND Fremdpruefer, unabhaengig: Mit der gröberen
    Faltung allein wurden BEIDE Gruppen unauffindbar, und `group_id_for_name`
    praegte bei jedem Aufruf eine frische dritte. Und dieser Bestand entsteht
    genau durch den Fehler, den #83 behebt.
    """
    store = _store(tmp_path, [_album("Straße", "g1"), _album("Strasse", "g2")])

    assert store.existing_group_for_name("Straße") == "g1"
    assert store.existing_group_for_name("Strasse") == "g2"
    # Auch die Versalien-Schreibweise landet dort, wo sie vor #83 landete.
    assert store.existing_group_for_name("STRASSE") == "g2"

    # Und die Vergabe praegt keine dritte Gruppe.
    assert store.group_id_for_name("Straße") == "g1"
    assert store.group_id_for_name("Strasse") == "g2"


def test_die_verbesserung_bleibt_wenn_es_nur_eine_gruppe_gibt(tmp_path):
    """Die Gegenprobe: Ohne Mehrdeutigkeit greift die neue Faltung."""
    store = _store(tmp_path, [_album("Straße", "g1")])
    assert store.existing_group_for_name("Straße") == "g1"
    assert store.existing_group_for_name("Strasse") == "g1"
    assert store.existing_group_for_name("STRASSE") == "g1"
    assert store.existing_group_for_name("Sommerfest") is None


def test_backfill_haengt_an_der_fehlenden_kennung_nicht_an_der_schemaversion(tmp_path):
    """Der Schreibpfad, den mein eigener Text zu eng beschrieben hatte.

    Ein Album ohne `group_id` neben Alben MIT Kennung — bei AKTUELLER
    Schemaversion. Der Backfill laeuft, und die Faltung entscheidet eine
    Kennung, die dauerhaft bleibt. Ohne die zweite Stufe bekaeme das
    kennungslose Album hier eine frische dritte Gruppe.
    """
    store = _store(tmp_path, [
        _album("Strasse", "g1"),
        _album("Straße", "g2"),
        _album("Strasse"),          # ohne Kennung
    ])
    nach_id = {a.id: a.group_id for a in store.get_managed_albums()}
    # Das kennungslose Album traegt die id "a-Strass" (der Helfer leitet sie
    # aus dem Namen ab, wenn keine Gruppe mitkommt).
    assert nach_id["a-Strass"] == "g1", nach_id
    # Und die beiden vorhandenen Kennungen sind unberuehrt.
    assert nach_id["a-g1"] == "g1" and nach_id["a-g2"] == "g2", nach_id
    # Keine dritte Gruppe entstanden.
    assert set(nach_id.values()) == {"g1", "g2"}, nach_id


# ---------------------------------------------------------------------------
# Die RICHTUNG der beiden Faltungsstufen — als Probe, nicht als Behauptung.
#
# Anlass: Ein Docstring in `errors.py` nannte eine Zahl („943 Paare"), die aus
# einem Prüfbericht übernommen und nie nachgemessen worden war. Sie liess sich
# in keiner Deutung reproduzieren (gemessen: 1203). Die Zahl war das kleinere
# Problem — das grössere war, dass die tragende Aussage überhaupt nur als Satz
# im Kommentar stand.
#
# Tragend ist die RICHTUNG: Das Namensschloss (`gruppen_schloss`) schlüsselt auf
# Stufe 1, die Zuordnung (`_gruppe_fuer_namen`) benutzt beide Stufen. Ist Stufe 1
# stets gröber, begegnen sich zwei Namen in der Zuordnung nur, wenn sie auch
# dasselbe Schloss nehmen.
#
# DAS GILT FÜR ZEICHEN, NICHT FÜR NAMEN. Hier stand bis #108 „nehmen also immer
# dasselbe Schloss" — gemessen war es nur über Einzelzeichen. Die Blindprüfung
# zu #108 hat NAMEN gefunden, die ausschliesslich in Stufe 2 kollidieren.
# Wie viele, hängt am Suchraum, und deshalb steht der Raum dabei:
#
#   ein Buchstabe, allein oder mit EINEM kombinierenden Zeichen
#       -> genau drei Paare (polytones Griechisch: Buchstabe mit Iota
#          subscriptum plus Perispomeni). Die Suche läuft als Probe mit
#          (`test_im_kleinen_raum_sind_es_genau_drei_paare`), über die beiden
#          griechischen Blöcke und das lateinische Grundalphabet; die
#          Blindprüfung zu #108 hat denselben Befund über alle kombinierenden
#          Zeichen aus ganz Unicode bestätigt.
#   ein Buchstabe mit ZWEI kombinierenden Zeichen
#       -> 4530 Paare bei griechischen Buchstaben und beiden Zeichen aus
#          U+0300–U+036F (Blindprüfung zu #108, nachgemessen am 28.09.2026;
#          nicht als Probe im Repo, sie läuft einige Sekunden).
#   mit weiteren Zeichen davor oder dahinter
#       -> beliebig viele.
# Die erste Probe unten hält die Richtung für Zeichen fest, die dritte die
# Ausnahme für Namen. Die Antwort auf die Schlosslücke gehört zu #95.
# ---------------------------------------------------------------------------


def _paare_je_stufe():
    from collections import defaultdict

    nach_stufe1, nach_stufe2 = defaultdict(list), defaultdict(list)
    for cp in range(0x110000):
        zeichen = chr(cp)
        eins, zwei = ConfigStore._name_key(zeichen), ConfigStore._name_key_vor_83(zeichen)
        if eins:
            nach_stufe1[eins].append(zeichen)
        if zwei:
            nach_stufe2[zwei].append(zeichen)

    def paare(topf):
        ergebnis = set()
        for zeichen in topf.values():
            for i in range(len(zeichen)):
                for j in range(i + 1, len(zeichen)):
                    ergebnis.add((zeichen[i], zeichen[j]))
        return ergebnis

    return paare(nach_stufe1), paare(nach_stufe2)


def test_keine_kollision_gehoert_allein_der_zweiten_stufe():
    """Stufe 1 ist gröber als Stufe 2 — in JEDEM Paar EINZELNER ZEICHEN.

    Das Namensschloss ruht darauf (sein Schlüssel ist Stufe 1) — seit #98 nur
    noch beim ANLEGEN, das Umbenennen nimmt seit dort kein Namensschloss mehr
    (die Kollisionsprüfung, die es dort hielt, ist mit #98 entfernt). Für
    Namen aus mehreren Zeichen gilt die Gröber-Richtung nicht vollständig —
    siehe `test_die_richtung_gilt_fuer_zeichen_nicht_fuer_namen`.
    """
    stufe1, stufe2 = _paare_je_stufe()
    nur_stufe2 = stufe2 - stufe1
    assert nur_stufe2 == set(), sorted(nur_stufe2)[:5]


def test_die_erste_stufe_ist_wirklich_groeber():
    """Die Gegenprobe: Ohne sie wäre der Test darüber auch für zwei identische
    Faltungen grün — und dann sagte er nichts über eine Abstufung, weil es
    keine gäbe.

    Die gemessene Zahl (Python 3.14.5, Unicode 16) steht als Grössenordnung im
    Kommentar, nicht in der Zusicherung: Sie wandert mit jeder Unicode-Fassung,
    die Richtung nicht. Stand 27.09.2026: 1203 Paare über 2023 Zeichen.
    """
    stufe1, stufe2 = _paare_je_stufe()
    nur_stufe1 = stufe1 - stufe2
    assert len(nur_stufe1) > 100, len(nur_stufe1)


# Die drei Paare, gefunden von der Blindprüfung zu #108 und nachgemessen.
# Codepunkte statt Glyphen: Die beiden Hälften sehen gleich aus, und genau
# daran ist der erste Nachbau gescheitert (die vorkomponierte Form kollidiert
# nicht).
NUR_IN_STUFE_ZWEI = [
    ("\u1fb3\u0342", "\u1fbc\u0342"),   # Alpha mit Iota subscriptum + Perispomeni
    ("\u1fc3\u0342", "\u1fcc\u0342"),   # Eta, ebenso
    ("\u1ff3\u0342", "\u1ffc\u0342"),   # Omega, ebenso
]


@pytest.mark.parametrize("klein, gross", NUR_IN_STUFE_ZWEI)
def test_die_richtung_gilt_fuer_zeichen_nicht_fuer_namen(klein, gross):
    """Eine BEKANNTE GRENZE als Probe, nicht als Satz.

    Diese Probe hält fest, dass es Namen gibt, die nur in Stufe 2 kollidieren.
    Sie ist grün, solange die Grenze besteht — und das ist der Zweck: Wird sie
    rot, hat eine Änderung an der Faltung (oder eine neue Unicode-Fassung) die
    Grenze geschlossen, und der Docstring von `ConfigStore.gruppen_schloss`
    (der diese Grenze seit #98 direkt benennt, statt sie nur hier im
    Testkommentar zu halten) beschreibt dann einen Zustand, den es nicht mehr
    gibt.

    Woher das kommt: ZUSAMMEN fallen die beiden in Stufe 2, weil `lower()`
    aus dem grossen Buchstaben den kleinen macht und Stufe 2 nicht
    normalisiert. GETRENNT bleiben sie in Stufe 1 wegen der ersten
    Normalform: Der kleine Buchstabe mit Iota subscriptum plus Perispomeni
    hat eine vorkomponierte Form (`U+1FB7`), der grosse nicht; `casefold`
    reiht Perispomeni und Iota danach verschieden. Ohne die erste Normalform
    fielen sie auch in Stufe 1 zusammen — die Mutation macht alle drei Fälle
    rot. (Bis zur Nacharbeit an #108 stand hier, `casefold` sei die Ursache.)
    """
    stufe1, stufe2 = ConfigStore._name_key, ConfigStore._name_key_vor_83
    assert stufe1(klein) != stufe1(gross), "Stufe 1 trennt die beiden nicht mehr"
    assert stufe2(klein) == stufe2(gross), "Stufe 2 legt die beiden nicht mehr zusammen"


def test_im_kleinen_raum_sind_es_genau_drei_paare():
    """Die Zahl „drei" als Messung, nicht als Satz — samt ihrem Raum.

    Raum: jeder Buchstabe der beiden griechischen Blöcke und des lateinischen
    Grundalphabets, allein oder mit genau einem kombinierenden Zeichen aus
    `U+0300`–`U+036F`. Gesucht sind Namen, die in Stufe 2 zusammenfallen und
    die Stufe 1 trennt.

    Sie hält zugleich die Liste darüber lebendig: Leert jemand
    `NUR_IN_STUFE_ZWEI`, überspringt pytest die parametrisierte Probe nur —
    und kein Gate zählt übersprungene Proben (gemessen von der Blindprüfung
    zu #108). Diese Probe wird dann rot.
    """
    import unicodedata as ud
    from collections import defaultdict

    buchstaben = [chr(c) for von, bis in ((0x0370, 0x0400), (0x1F00, 0x2000), (0x0041, 0x007B))
                  for c in range(von, bis) if ud.category(chr(c)).startswith("L")]
    zeichen = [chr(c) for c in range(0x0300, 0x0370)]
    namen = set(buchstaben) | {b + z for b in buchstaben for z in zeichen}

    je_stufe2 = defaultdict(set)
    for name in namen:
        schluessel = ConfigStore._name_key_vor_83(name)
        if schluessel:
            je_stufe2[schluessel].add(name)

    gefunden = set()
    for gruppe in je_stufe2.values():
        if len({ConfigStore._name_key(n) for n in gruppe}) > 1:
            gefunden.add(frozenset(gruppe))

    erwartet = {frozenset(paar) for paar in NUR_IN_STUFE_ZWEI}
    assert len(NUR_IN_STUFE_ZWEI) == 3, NUR_IN_STUFE_ZWEI
    assert gefunden == erwartet, sorted(tuple(sorted(g)) for g in gefunden)
