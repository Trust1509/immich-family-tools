"""Umbenennen über eine ganze Gruppe — die Wege, die die Oberfläche geht (#79).

Die Fälle hier sind Funde aus drei Prüfrunden gegen eine Kollisionsprüfung, die
es seit #98 nicht mehr gibt: Zwei verschiedene Albumgruppen dürfen seither
denselben Namen tragen, ein Umbenennen lehnt deshalb nie mehr wegen eines
Namens ab. Damals urteilte die Prüfung über einen Namen, der Schaden lebt aber
in einem Zustand — drei Fassungen lang wurde „gehört dieser Name schon einer
anderen Gruppe?" gefragt, und damit wurde Harmloses abgelehnt, darunter der
eine Vorgang, der aus dem Schaden herausführt. Zahlen dazu stehen mit Quelle in
#108; hier nicht, weil ihre Sonde nicht im Repo liegt.

Die Fälle unten sind die, an denen sich das damals entschied und die auch ohne
die Prüfung gelingen müssen:

1. **Zwei Alben einer Gruppe** — der normale Weg der Oberfläche, die jedes Album
   einzeln umbenennt. Hatte drei Fassungen lang keine Backend-Probe.
2. **Wiederholung nach einem Teilausfall** — die Gruppe trägt den neuen Namen
   schon über ihr erstes Album, das zurückgebliebene noch den alten.
3. **Eine zweite Schreibweise in der eigenen Gruppe** — das Umbenennen gelingt
   wie jedes andere; diese Probe hält zusätzlich fest, dass sich an der
   Gruppenzuordnung nichts verschiebt.
4. **Zwei gleichnamige Gruppen wieder unterscheiden** — der Weg AUS dem Schaden
   von #78 heraus, den alle drei Vorfassungen gesperrt haben.
5. **Der alte Name** — es gibt seit #98 keine Prüfung mehr, die über ihn
   entscheiden könnte. Was aus ihm wird, hängt am ganzen Bestand: Er kann
   danach auf eine andere Gruppe zeigen, auf keine oder auf die eigene (alle
   drei gemessen, #108). Festgehalten ist der erste Ausgang.

Die Fälle, in denen die entfernte Prüfung mit 409 abgelehnt hätte (eine fremde
Gruppe, eine still verdrängte Antwort), stehen nicht mehr hier — die neue Probe
für #98 in `test_umbenennen_doppelte_namen.py` hält stattdessen fest, dass sie
heute gelingen.

Die Attrappe hier war ursprünglich eine schreibende Ersetzung des GANZEN
Sync-Dienstes — bis Nacharbeit 2 zu #98: Der Blindprüfer hat gemessen, dass
diese Form zwei ganze Fallklassen blind macht (eine Schreibvariante wie
„HERBSTFEST" gegen „Herbstfest", und der normale Weg der Oberfläche mit MEHR
ALS EINEM Album in der eigenen Gruppe): Eine Ablehnung, die der echte Dienst
dafür wirft, würde diese Datei nie erreichen, weil `sync_service.
rename_managed_album` komplett ersetzt war. Jetzt läuft der echte Dienst und
der echte `ConfigStore`; nur `ImmichClient` ist eine Attrappe (kein HTTP-
Aufruf gegen eine echte Immich-Instanz). Eine zählende Attrappe wäre ohnehin
zu wenig gewesen: Die zweite Anfrage muss sehen, was die erste im Bestand
angerichtet hat.
"""
import json

import pytest
from fastapi.testclient import TestClient

KONTO = {"id": "konto-1", "name": "Konto Eins",
         "immich_url": "http://beispiel.invalid", "api_key": "platzhalter",
         "color": "#111111", "user_id": "u1"}


def _album(album_id, name, gruppe):
    return {"id": album_id, "match_id": "m-" + album_id,
            "album_id": "immich-" + album_id, "album_name": name,
            "group_id": gruppe, "owner_account_id": "konto-1",
            "person_refs": [], "linked_match_ids": [],
            "created_at": "2026-01-01T00:00:00+00:00"}


class _ImmichAttrappe:
    """Ersetzt nur den Netzwerk-Rand: kein HTTP, sonst nichts Eigenes.

    Fuer `_rename_managed_album_unlocked` reicht `update_album` — die Funktion
    ruft weder `get_album_assets` noch `add_assets_to_album` noch teilt sie
    ein Album. Dieselbe Form wie in `test_umbenennen_doppelte_namen.py`,
    bewusst nicht geteilt, damit diese Datei ohne Blick in die andere lesbar
    bleibt.
    """

    def __init__(self, *_a, **_k):
        pass

    async def update_album(self, album_id, payload):
        return {"id": album_id, **payload}


@pytest.fixture
def mit_bestand(tmp_path, monkeypatch):
    """Baut eine Anwendung mit dem übergebenen Bestand, echtem Sync-Dienst und
    echtem ConfigStore — nur `ImmichClient` ist eine Attrappe.
    """
    def bauen(alben):
        import main
        from services import sync_service

        pfad = tmp_path / "accounts.json"
        pfad.write_text(json.dumps({"accounts": {"konto-1": KONTO},
                                    "schema_version": 3, "managed_albums": alben}),
                        encoding="utf-8")
        monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test", raising=False)
        monkeypatch.setattr(main.settings, "config_path", pfad, raising=False)
        monkeypatch.setattr(sync_service, "ImmichClient", _ImmichAttrappe)

        c = TestClient(main.app)
        c.__enter__()
        c.post("/api/auth/login", json={"token": "nur-fuer-den-test"})
        return c

    yield bauen


def _namen(client):
    return {a["id"]: a["album_name"] for a in client.get("/api/sync/albums").json()}


def _gruppen(client):
    return {a["id"]: a["group_id"] for a in client.get("/api/sync/albums").json()}


def test_beide_alben_einer_gruppe_lassen_sich_umbenennen(mit_bestand):
    """Der normale Weg der Oberfläche — und er hatte keine Backend-Probe.

    `AlbumsOverview.tsx` benennt jedes Album einer Gruppe EINZELN um: Das
    zweite Album sieht den neuen Namen des ersten schon im Bestand, trägt also
    vorübergehend einen anderen Namen als sein Geschwister. Eine Ablehnung, die
    daran etwas findet, schafft die Funktion ab, die sie schützen soll — eine
    Gruppe mit zwei oder mehr Alben liesse sich nie mehr umbenennen. Genau
    dieser Fall hatte drei Fassungen lang keine Backend-Probe.
    """
    c = mit_bestand([_album("a1", "Sommerfest", "gruppe-1"),
                     _album("a2", "Sommerfest", "gruppe-1")])
    assert c.patch("/api/sync/albums/a1",
                   json={"album_name": "Herbstfest"}).status_code == 200
    zweite = c.patch("/api/sync/albums/a2", json={"album_name": "Herbstfest"})
    assert zweite.status_code == 200, zweite.text
    assert _namen(c) == {"a1": "Herbstfest", "a2": "Herbstfest"}


def test_die_wiederholung_nach_einem_teilausfall_kommt_durch(mit_bestand):
    """Der Stand nach einem Teilausfall, mit einer fremden Schreibweise daneben.

    `gruppe-1` trägt „Herbstfest" schon über a1; a2 blieb zurück. `gruppe-2`
    hält „HERBSTFEST" — gemessen dieselbe Faltung auf BEIDEN Stufen wie
    „Herbstfest" (reine Gross-/Kleinschreibung faltet `casefold` und `lower()`
    gleich), also ein Bestand, in dem der Zielname schon vor dieser Anfrage
    doppelt vorkommt. Seit #98 lehnt das Umbenennen nie mehr WEGEN EINES NAMENS
    ab; diese Probe hält zusätzlich fest, dass a2 dabei wirklich ankommt (nicht
    für immer beim alten Namen zurückbleibt), obwohl im Bestand schon zwei
    Gruppen mit passender Faltung existieren.
    """
    c = mit_bestand([_album("a1", "Herbstfest", "gruppe-1"),
                     _album("a2", "Sommerfest", "gruppe-1"),
                     _album("a3", "HERBSTFEST", "gruppe-2")])
    antwort = c.patch("/api/sync/albums/a2", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 200, antwort.text
    assert _namen(c)["a2"] == "Herbstfest"


def test_die_eigene_gruppe_darf_eine_zweite_schreibweise_bekommen(mit_bestand):
    """Eine zweite Schreibweise innerhalb der EIGENEN Gruppe.

    `gruppe-1` hält „Strassenfest" und „Sommerfest". Das Umbenennen von
    „Sommerfest" in „Straßenfest" gelingt (seit #98 nie mehr wegen eines
    Namens abgelehnt); diese Probe hält zusätzlich fest, dass sich an der
    Gruppenzuordnung nichts verschiebt: Vor und nach dem Vorgang zeigt
    „Strassenfest" auf `gruppe-1`, und „Straßenfest" jetzt ebenfalls — beide
    Schreibweisen bleiben bei derselben Gruppe.

    NACHTRAG #116 (Nachlese #98, Punkt 2): Die vorige Fassung prüfte dafür
    nur `_namen` (Status und Namen) — `managed.group_id = "verschoben"` VOR
    dem Speichern in `_rename_managed_album_unlocked` blieb dabei unbemerkt
    grün (Blindprüfer, gemessen). Diese Probe liest jetzt `group_id` BEIDER
    Alben aus `/api/sync/albums` UND die Gruppenvorschau (`/api/sync/
    album-group`) vor und nach dem Umbenennen und verlangt für beide
    dieselbe, unveränderte Gruppe.
    """
    c = mit_bestand([_album("a1", "Strassenfest", "gruppe-1"),
                     _album("a2", "Sommerfest", "gruppe-1")])
    vorher_gruppen = _gruppen(c)
    vorher_vorschau = c.get("/api/sync/album-group",
                            params={"album_name": "Strassenfest"}).json()
    assert vorher_vorschau and vorher_vorschau["group_id"] == "gruppe-1", vorher_vorschau

    antwort = c.patch("/api/sync/albums/a2", json={"album_name": "Straßenfest"})
    assert antwort.status_code == 200, antwort.text
    assert _namen(c) == {"a1": "Strassenfest", "a2": "Straßenfest"}

    nachher_gruppen = _gruppen(c)
    assert nachher_gruppen == vorher_gruppen == {"a1": "gruppe-1", "a2": "gruppe-1"}, (
        vorher_gruppen, nachher_gruppen,
    )
    nachher_vorschau_alt = c.get("/api/sync/album-group",
                                 params={"album_name": "Strassenfest"}).json()
    nachher_vorschau_neu = c.get("/api/sync/album-group",
                                 params={"album_name": "Straßenfest"}).json()
    assert nachher_vorschau_alt and nachher_vorschau_alt["group_id"] == "gruppe-1", \
        nachher_vorschau_alt
    assert nachher_vorschau_neu and nachher_vorschau_neu["group_id"] == "gruppe-1", \
        nachher_vorschau_neu


def test_zwei_gleichnamige_gruppen_lassen_sich_wieder_unterscheiden(mit_bestand):
    """Der Weg AUS dem Schaden von #78 heraus — drei Fassungen lang gesperrt.

    Zwei Gruppen heissen versehentlich gleich. Die Gruppenvorschau kann sie
    deshalb nicht auseinanderhalten: Wer den Namen tippt, bekommt keine der
    beiden automatisch VORGESCHLAGEN (`group_id_for_name`/`resolve_group_id`
    ohne ausdrueckliche Wahl finden keinen eindeutigen Treffer). Der eine
    Vorgang, der das behebt, ist eine Schreibweise zu ändern, die nur in der
    ersten Faltungsstufe zusammenfällt.

    Alle drei Vorfassungen der Kollisionsprüfung haben genau diesen Vorgang mit
    409 abgelehnt — mit einer Auskunft, die nicht stimmte: Die andere Gruppe
    trägt diesen Namen nicht, sie trägt eine andere Schreibweise. Gemessen vom
    Blindprüfer an Nacharbeit 2; Zahlen und ihre Grenze stehen in #108.

    Gemessen wird hier nicht der Statuscode allein, sondern die WIRKUNG an der
    Tür, um die es geht: Die Vorschau muss danach für beide Schreibweisen
    EINDEUTIG antworten.

    NACHTRAG #113 (29.09.2026): "Schweigt" traf die VORSCHAU selbst nicht
    mehr fuer JEDE Schreibweise gleich genau — sie kollabiert Mehrdeutigkeit
    nicht mehr blind auf `null`, sondern zeigt Kandidaten, wo welche zu
    FINDEN sind. Gemessen (neu, an dieser Stelle): Fuer die BYTEGLEICHE
    Schreibweise "Strassenfest" sind das beide Gruppen (`status: "many"`) —
    Stufe 2 (`.lower()`, kein `ß`->`ss`) findet hier trotzdem beide, weil die
    Datenbank selbst nur "Strassenfest" kennt.

    NACHTRAG Nacharbeit 1 zu #113/#119/#124 (Blind W-1/Gegen F4, 29.09.2026):
    Fuer "Straßenfest" stand hier zuvor `null` — Stufe 1 faltet `ß`->`ss` und
    sieht dieselben zwei Kandidaten (mehrdeutig), Stufe 2 faltet NICHT und
    findet zum Schluessel "straßenfest" nichts in einer Datenbank, die nur
    "strassenfest" kennt (LEER, dieselbe Stufe-2-Grenze wie in
    `test_namensfaltung.py`). Die vorige Fassung liess dabei die LEERE
    Stufe-2-Antwort gewinnen — mit der Folge, dass eine Anlage ohne
    ausdrueckliche Wahl (`expected_no_group`) still eine DRITTE Gruppe
    anlegte, obwohl der Name erkennbar mehrdeutig war (genau der Fehler, den
    `resolve_group_id` verhindern soll). `group_candidates_for_name` faellt
    jetzt auf Stufe 1 zurueck, wenn Stufe 2 sich nicht auf GENAU EINE Gruppe
    festlegt — die Vorschau fuer "Straßenfest" antwortet deshalb jetzt
    ebenfalls mit `status: "many"` und denselben zwei Kandidaten wie fuer die
    bytegleiche Schreibweise. Der Testname und der obige Absatz bleiben als
    datierte Historie stehen (`docs/agents/lehren.md`,
    "Ein Widerspruch über zwei Dateien"); geprueft wird unten die aktuelle
    Form je Schreibweise.
    """
    c = mit_bestand([_album("a1", "Strassenfest", "gruppe-1"),
                     _album("a2", "Strassenfest", "gruppe-2")])

    vorher_doppel_s = c.get("/api/sync/album-group",
                            params={"album_name": "Strassenfest"}).json()
    assert vorher_doppel_s["status"] == "many", vorher_doppel_s
    assert {k["group_id"] for k in vorher_doppel_s["candidates"]} == {"gruppe-1", "gruppe-2"}

    vorher_scharf_s = c.get("/api/sync/album-group",
                            params={"album_name": "Straßenfest"}).json()
    assert vorher_scharf_s["status"] == "many", vorher_scharf_s
    assert {k["group_id"] for k in vorher_scharf_s["candidates"]} == {"gruppe-1", "gruppe-2"}

    antwort = c.patch("/api/sync/albums/a1", json={"album_name": "Straßenfest"})
    assert antwort.status_code == 200, antwort.text

    # Danach antwortet sie für beide, und zwar mit VERSCHIEDENEN Gruppen.
    mit_scharf = c.get("/api/sync/album-group",
                       params={"album_name": "Straßenfest"}).json()
    mit_doppel_s = c.get("/api/sync/album-group",
                         params={"album_name": "Strassenfest"}).json()
    assert mit_scharf and mit_scharf["group_id"] == "gruppe-1", mit_scharf
    assert mit_doppel_s and mit_doppel_s["group_id"] == "gruppe-2", mit_doppel_s


def test_der_alte_name_zaehlt_nicht_als_verlust(mit_bestand):
    """Im Bestand mit EINEM Album gehört der alte Name danach niemandem.

    Das ist der Zweck des Vorgangs. In anderen Beständen kann er danach auf
    eine andere Gruppe zeigen — das misst die Probe darunter.

    In einem Bestand wie diesem verliert der alte Name seine Gruppe — das ist
    keine Ablehnung mehr wert, seit #98 sowieso nicht, aber auch die Vorschau
    (`GET /api/sync/album-group`) hält das fest: Sie antwortet für den alten
    Namen danach mit `null`, weil ihn niemand mehr trägt. Der Fall, in dem er
    stattdessen an eine ANDERE Gruppe geht, misst die Probe darunter.

    NACHTRAG #111 (Nachlese #108, Klein 3): „zwangsläufig" traf nicht zu —
    hier gilt der Verlust, weil „Herbstfest" in eine ANDERE Faltungsklasse
    fällt als „Sommerfest". Ein Umbenennen INNERHALB derselben Klasse (z. B.
    „Sommerfest" -> „SOMMERFEST") verliert den alten Namen nicht: Beide
    Schreibweisen falten auf denselben Schlüssel, die Gruppe bleibt über
    ihn auffindbar (siehe `test_die_eigene_gruppe_darf_eine_zweite_
    schreibweise_bekommen` für dasselbe Prinzip innerhalb einer Gruppe).
    """
    c = mit_bestand([_album("a1", "Sommerfest", "gruppe-1")])
    vorher = c.get("/api/sync/album-group",
                   params={"album_name": "Sommerfest"}).json()
    assert vorher and vorher["group_id"] == "gruppe-1"

    antwort = c.patch("/api/sync/albums/a1", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 200, antwort.text
    assert c.get("/api/sync/album-group",
                 params={"album_name": "Sommerfest"}).json() is None


FREI_GEWORDEN = [
    ("Strasse", "Straße"),               # Übergabe über Stufe 1
    ("\u1fb3\u0342", "\u1fbc\u0342"),  # Übergabe nur über Stufe 2
]


def test_die_festhalte_probe_deckt_beide_stufen():
    """Hält die Parameterliste darunter lebendig.

    Einen Parameter zu streichen liess die Suite grün (Blindprüfung zu #108),
    auch zusammen mit einer Mutation, die die Übergabe nur über Stufe 2
    sperrt. Diese Probe verlangt beide Fälle — und prüft, dass sie wirklich
    über VERSCHIEDENE Stufen laufen.
    """
    from services.config_store import ConfigStore
    k1, k2 = ConfigStore._name_key, ConfigStore._name_key_vor_83
    stufe1 = [(a, b) for a, b in FREI_GEWORDEN if k1(a) == k1(b)]
    nur_stufe2 = [(a, b) for a, b in FREI_GEWORDEN if k1(a) != k1(b) and k2(a) == k2(b)]
    assert len(FREI_GEWORDEN) == 2, FREI_GEWORDEN
    assert len(stufe1) == 1 and len(nur_stufe2) == 1, (stufe1, nur_stufe2)


def test_der_dekorator_verwendet_wirklich_ganz_frei_geworden():
    """Wächter für den DEKORATOR selbst, nicht nur für die Liste (#111,
    WICHTIG 2).

    `test_die_festhalte_probe_deckt_beide_stufen` sichert nur Eigenschaften
    von `FREI_GEWORDEN` — sie liest die Liste, nicht das, was tatsächlich am
    `@pytest.mark.parametrize`-Dekorator darunter hängt. Ein Dekorator mit
    `FREI_GEWORDEN[:1]` oder `FREI_GEWORDEN[:1] * 2` blieb deshalb unbemerkt
    grün (Blindprüfung an Nacharbeit 2 zu #108: 254 bzw. 255 grün — bei der
    zweiten Mutation blieb sogar die PROBENZAHL gleich, weil zwei Fälle drin
    stecken, nur beide derselbe). Diese Probe liest die am Testobjekt
    tatsächlich hinterlegten Parameter-Werte aus `pytestmark` und verlangt
    Gleichheit mit `FREI_GEWORDEN` selbst — eine gekürzte oder eine
    vervielfältigte Kopie hat eine andere Wertfolge und fällt durch.
    """
    marken = [
        m for m in test_ein_frei_gewordener_name_geht_an_die_verbleibende_traegerin.pytestmark
        if m.name == "parametrize"
    ]
    assert len(marken) == 1, marken
    [marke] = marken
    _argnamen, argwerte = marke.args
    assert argwerte == FREI_GEWORDEN, argwerte


@pytest.mark.parametrize("alter_name, fremde_schreibweise", FREI_GEWORDEN)
def test_ein_frei_gewordener_name_geht_an_die_verbleibende_traegerin(
    mit_bestand, alter_name, fremde_schreibweise
):
    """Die Regel, die bis #108 nirgends stand — festgenagelt als HEUTIGES Verhalten.

    `gruppe-1` heisst „Strasse", `gruppe-2` „Straße"; seit #83 derselbe Name,
    auseinandergehalten nur vom Stufe-2-Rückgriff. Benennt man `gruppe-1` weg,
    zeigt „Strasse" danach auf `gruppe-2` — die Klasse ist frei geworden, und
    `gruppe-2` die Trägerin einer gleichwertigen Schreibweise. Das ist allein
    die Auflösung von `_gruppe_fuer_namen` (siehe `test_namensfaltung.py`) und
    hat mit der mit #98 entfernten Kollisionsprüfung nichts zu tun: Es gibt
    seit #98 keine Prüfung mehr, die über den Namen, von dem weg umbenannt
    wird, entscheiden könnte — was aus ihm wird, bestimmt allein dieser
    Lesemechanismus.

    ZWEI Bestände, weil die Übergabe über BEIDE Stufen laufen kann: bei „ss"
    und „ß" über Stufe 1, beim griechischen Paar nur über Stufe 2. Mit nur dem
    ersten blieb eine Mutation grün, die die Übergabe allein über Stufe 2
    sperrt (Blindprüfung zu #108).
    """
    c = mit_bestand([_album("a1", alter_name, "gruppe-1"),
                     _album("a2", fremde_schreibweise, "gruppe-2")])
    vorher = c.get("/api/sync/album-group", params={"album_name": alter_name}).json()
    assert vorher and vorher["group_id"] == "gruppe-1", vorher

    antwort = c.patch("/api/sync/albums/a1", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 200, antwort.text

    nachher = c.get("/api/sync/album-group", params={"album_name": alter_name}).json()
    assert nachher and nachher["group_id"] == "gruppe-2", nachher

