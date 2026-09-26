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
und wo die mehrdeutig wird, die alte. Die Proben dazu stehen unten.
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
