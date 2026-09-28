"""Umbenennen über eine ganze Gruppe — die Wege, die die Oberfläche geht (#79).

Die Fälle hier sind Funde aus drei Prüfrunden, und alle haben eine gemeinsame
Wurzel: **Die Kollisionsprüfung urteilte über einen Namen, der Schaden lebt aber
in einem Zustand.** Drei Fassungen lang wurde gefragt „gehört dieser Name schon
einer anderen Gruppe?", und damit wurde Harmloses abgelehnt — darunter der
eine Vorgang, der aus dem Schaden herausführt. Zahlen dazu stehen mit Quelle in
#108; hier nicht, weil ihre Sonde nicht im Repo liegt.

Seit der dritten Runde fragt die Prüfung an der Wirkung: Welcher Name antwortet
nach dem Vorgang anders als vorher (`ConfigStore.namen_mit_anderer_antwort`)?
Die Tests unten sind die Fälle, an denen sich das entscheidet:

1. **Zwei Alben einer Gruppe** — der normale Weg der Oberfläche, die jedes Album
   einzeln umbenennt. Hatte drei Fassungen lang keine Backend-Probe.
2. **Wiederholung nach einem Teilausfall** — die Gruppe trägt den neuen Namen
   schon über ihr erstes Album, das zurückgebliebene noch den alten.
3. **Eine zweite Schreibweise in der eigenen Gruppe** — keine andere Gruppe ist
   beteiligt, also ändert sich keine Antwort.
4. **Zwei gleichnamige Gruppen wieder unterscheiden** — der Weg AUS dem Schaden
   von #78 heraus, den alle drei Vorfassungen gesperrt haben.
5. **Eine Antwort, die still zu einer anderen Gruppe wandert** — abgelehnt,
   obwohl keine Antwort verschwindet.
6. **Der alte Name** — er wird nicht geprüft. Gehört er danach niemandem,
   ist das der Zweck des Vorgangs. Trägt eine andere Gruppe eine
   gleichwertige Schreibweise, geht er an sie über (bei mehreren an keine):
   Wer einen Namen VERDRÄNGT, wird abgelehnt (Fall 5), wer einen FREI
   GEWORDENEN übernimmt, nicht. Ob diese Regel gilt, ist offen in #98; die Probe dafür steht
   unten und ist die, die kippt, wenn #98 anders entscheidet.

Die Attrappe hier **schreibt wirklich**. Eine zählende Attrappe wie in
`test_umbenennen_kollision.py` kann diese Fälle nicht messen: Die zweite Anfrage
sieht dann nie, was die erste angerichtet hat.
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


@pytest.fixture
def mit_bestand(tmp_path, monkeypatch):
    """Baut eine Anwendung mit dem übergebenen Bestand und schreibendem Immich."""
    def bauen(alben):
        import main
        from services import sync_service

        pfad = tmp_path / "accounts.json"
        pfad.write_text(json.dumps({"accounts": {"konto-1": KONTO},
                                    "schema_version": 3, "managed_albums": alben}),
                        encoding="utf-8")
        monkeypatch.setattr(main.settings, "secret", "nur-fuer-den-test", raising=False)
        monkeypatch.setattr(main.settings, "config_path", pfad, raising=False)

        async def umbenennen(managed, _owner, neuer_name, store):
            managed.album_name = neuer_name
            store.update_managed_album(managed)
            return []

        monkeypatch.setattr(sync_service, "rename_managed_album", umbenennen)
        c = TestClient(main.app)
        c.__enter__()
        c.post("/api/auth/login", json={"token": "nur-fuer-den-test"})
        return c

    yield bauen


def _namen(client):
    return {a["id"]: a["album_name"] for a in client.get("/api/sync/albums").json()}


def test_beide_alben_einer_gruppe_lassen_sich_umbenennen(mit_bestand):
    """Der normale Weg der Oberfläche — und er hatte keine Backend-Probe.

    Das zweite Album sieht den neuen Namen des ersten schon im Bestand. Ein
    Prädikat, das dabei „der Name ist vergeben" sagt, schafft die Funktion ab,
    die es schützen soll: Eine Gruppe mit zwei Alben liesse sich nie umbenennen.

    Getragen wird dieser Fall davon, dass sich die ANTWORT nicht ändert — beide
    Alben gehören derselben Gruppe, „Herbstfest" zeigt vorher und nachher auf
    `gruppe-1`.
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
    hält „HERBSTFEST" — dieselbe Stufe-1-Faltung, andere Stufe 2. Damit steht
    `gruppe-2` in `fremd`, und die Ausnahme entscheidet.

    Sie muss die GRUPPE fragen: a2 selbst trägt den Namen noch nicht, seine
    Gruppe schon. Die Mehrdeutigkeit ist vorher und nachher dieselbe — eine
    Ablehnung würde nichts verhindern und a2 für immer zurücklassen.
    """
    c = mit_bestand([_album("a1", "Herbstfest", "gruppe-1"),
                     _album("a2", "Sommerfest", "gruppe-1"),
                     _album("a3", "HERBSTFEST", "gruppe-2")])
    antwort = c.patch("/api/sync/albums/a2", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 200, antwort.text
    assert _namen(c)["a2"] == "Herbstfest"


def test_die_eigene_gruppe_darf_eine_zweite_schreibweise_bekommen(mit_bestand):
    """Der Fall, in dem Abzug und Ausnahme AUSEINANDERGEHEN.

    `gruppe-1` hält „Strassenfest" und „Sommerfest". Wer „Sommerfest" in
    „Straßenfest" umbenennt, kollidiert in Stufe 1 mit dem eigenen
    „Strassenfest" — und mit KEINER anderen Gruppe. Es entsteht also keine
    gruppenübergreifende Mehrdeutigkeit, und der Vorgang gehört erlaubt.

    Das Prädikat sieht das an der Wirkung: Vor und nach dem Vorgang zeigt
    „Strassenfest" auf `gruppe-1` und „Straßenfest" ebenfalls — keine Antwort
    ändert sich, also gibt es nichts abzulehnen.
    """
    c = mit_bestand([_album("a1", "Strassenfest", "gruppe-1"),
                     _album("a2", "Sommerfest", "gruppe-1")])
    antwort = c.patch("/api/sync/albums/a2", json={"album_name": "Straßenfest"})
    assert antwort.status_code == 200, antwort.text
    assert _namen(c) == {"a1": "Strassenfest", "a2": "Straßenfest"}


def test_zwei_gleichnamige_gruppen_lassen_sich_wieder_unterscheiden(mit_bestand):
    """Der Weg AUS dem Schaden von #78 heraus — drei Fassungen lang gesperrt.

    Zwei Gruppen heissen versehentlich gleich. Die Gruppenvorschau schweigt
    deshalb für beide: Wer den Namen tippt, bekommt keine Gruppe angeboten.
    Der eine Vorgang, der das behebt, ist eine Schreibweise zu ändern, die nur
    in der ersten Faltungsstufe zusammenfällt.

    Alle drei Vorfassungen der Kollisionsprüfung haben genau diesen Vorgang mit
    409 abgelehnt — mit einer Auskunft, die nicht stimmte: Die andere Gruppe
    trägt diesen Namen nicht, sie trägt eine andere Schreibweise. Gemessen vom
    Blindprüfer an Nacharbeit 2; Zahlen und ihre Grenze stehen in #108.

    Gemessen wird hier nicht der Statuscode allein, sondern die WIRKUNG an der
    Tür, um die es geht: Die Vorschau muss danach für beide Schreibweisen
    antworten.
    """
    c = mit_bestand([_album("a1", "Strassenfest", "gruppe-1"),
                     _album("a2", "Strassenfest", "gruppe-2")])

    # Vorher schweigt die Vorschau für beide — das ist der Schaden.
    for schreibweise in ("Strassenfest", "Straßenfest"):
        assert c.get("/api/sync/album-group",
                     params={"album_name": schreibweise}).json() is None

    antwort = c.patch("/api/sync/albums/a1", json={"album_name": "Straßenfest"})
    assert antwort.status_code == 200, antwort.text

    # Danach antwortet sie für beide, und zwar mit VERSCHIEDENEN Gruppen.
    mit_scharf = c.get("/api/sync/album-group",
                       params={"album_name": "Straßenfest"}).json()
    mit_doppel_s = c.get("/api/sync/album-group",
                         params={"album_name": "Strassenfest"}).json()
    assert mit_scharf and mit_scharf["group_id"] == "gruppe-1", mit_scharf
    assert mit_doppel_s and mit_doppel_s["group_id"] == "gruppe-2", mit_doppel_s


def test_ein_name_darf_nicht_still_zu_einer_anderen_gruppe_wandern(mit_bestand):
    """Der dritte Fall des Prädikats: die Antwort wandert, statt zu verschwinden.

    `gruppe-1` heisst „Straßenfest", sonst niemand — „Strassenfest" zeigt
    deshalb heute auf `gruppe-1` (Stufe 1 ist eindeutig). Wer `gruppe-2` genau
    so nennt, dreht diese Antwort auf `gruppe-2` um: Ein künftiges Album mit
    dieser Schreibweise träte still einer anderen Gruppe bei als bisher.

    Niemand merkt das, und deshalb wird es abgelehnt — obwohl kein Name seine
    Antwort VERLIERT. Ohne diesen Fall wäre „nur ablehnen, wenn eine Antwort
    verschwindet" die halbe Regel.
    """
    c = mit_bestand([_album("a1", "Straßenfest", "gruppe-1"),
                     _album("a2", "Sommerfest", "gruppe-2")])
    vorher = c.get("/api/sync/album-group",
                   params={"album_name": "Strassenfest"}).json()
    assert vorher and vorher["group_id"] == "gruppe-1", vorher

    antwort = c.patch("/api/sync/albums/a2", json={"album_name": "Strassenfest"})
    assert antwort.status_code == 409, antwort.text
    assert _namen(c)["a2"] == "Sommerfest"


def test_der_alte_name_zaehlt_nicht_als_verlust(mit_bestand):
    """Im Bestand mit EINEM Album gehört der alte Name danach niemandem.

    Das ist der Zweck des Vorgangs. Trägt genau EINE andere Gruppe eine
    gleichwertige Schreibweise, gehört er danach ihr — das misst die Probe
    darunter.

    Ohne diese Unterscheidung wäre jedes Umbenennen abgelehnt: Der alte Name
    verliert immer seine Gruppe. Das Prädikat zählt deshalb nur Namen, die es
    nachher noch gibt.
    """
    c = mit_bestand([_album("a1", "Sommerfest", "gruppe-1")])
    vorher = c.get("/api/sync/album-group",
                   params={"album_name": "Sommerfest"}).json()
    assert vorher and vorher["group_id"] == "gruppe-1"

    antwort = c.patch("/api/sync/albums/a1", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 200, antwort.text
    assert c.get("/api/sync/album-group",
                 params={"album_name": "Sommerfest"}).json() is None



@pytest.mark.parametrize("alter_name, fremde_schreibweise", [
    ("Strasse", "Straße"),               # Übergabe über Stufe 1
    ("\u1fb3\u0342", "\u1fbc\u0342"),  # Übergabe nur über Stufe 2
])
def test_ein_frei_gewordener_name_geht_an_die_verbleibende_traegerin(
    mit_bestand, alter_name, fremde_schreibweise
):
    """Die Regel, die bis #108 nirgends stand — festgenagelt als HEUTIGES Verhalten.

    `gruppe-1` heisst „Strasse", `gruppe-2` „Straße"; seit #83 derselbe Name,
    auseinandergehalten nur vom Stufe-2-Rückgriff. Benennt man `gruppe-1` weg,
    zeigt „Strasse" danach auf `gruppe-2` — die Klasse ist frei geworden, und
    `gruppe-2` ist ihre einzige Trägerin. Das Prädikat prüft den Namen, von dem
    weg umbenannt wird, nicht. Die stimmige Alternative — die Wanderung des
    alten Namens ablehnen, sein Freiwerden erlauben — wäre eine zweite Regel,
    keine Reparatur; sie bricht nur diese Probe. Beide stehen am Prädikat.

    ZWEI Bestände, weil die Übergabe über BEIDE Stufen laufen kann: bei „ss"
    und „ß" über Stufe 1, beim griechischen Paar nur über Stufe 2. Mit nur dem
    ersten blieb eine Mutation grün, die die Übergabe allein über Stufe 2
    sperrt (Blindprüfung zu #108).

    OB DAS SO BLEIBEN SOLL, IST OFFEN (#98). Diese Probe ist die, die kippt,
    wenn dort anders entschieden wird — sie misst heutiges Verhalten, keine
    beschlossene Regel.
    """
    c = mit_bestand([_album("a1", alter_name, "gruppe-1"),
                     _album("a2", fremde_schreibweise, "gruppe-2")])
    vorher = c.get("/api/sync/album-group", params={"album_name": alter_name}).json()
    assert vorher and vorher["group_id"] == "gruppe-1", vorher

    antwort = c.patch("/api/sync/albums/a1", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 200, antwort.text

    nachher = c.get("/api/sync/album-group", params={"album_name": alter_name}).json()
    assert nachher and nachher["group_id"] == "gruppe-2", nachher


def test_die_schleife_faengt_eine_verdraengung_ohne_den_zielnamen(mit_bestand):
    """Der Beleg, dass die Schleife über ALLE Namen Last trägt.

    Zwei Fassungen des Prädikats-Docstrings haben behauptet, eine Prüfung nur
    des Zielnamens wäre gleichwertig — erst bewiesen, dann gemessen. Beide
    Male falsch. Das Gegenbeispiel des Fremdprüfers zu #108 kreuzt ein Paar,
    das nur in Stufe 2 kollidiert, mit „ss"/„ß":

        A  = P + "|Strasse" -> gruppe-1   (antwortet über Stufe 2)
        B  = Q + "|Straße"  -> gruppe-2   wird umbenannt in  Q + "|Strasse"
        C  = P + "|Straße"  -> gruppe-2

    Der ZIELNAME zeigt vorher und nachher auf `gruppe-2` — eine Prüfung nur
    des Zielnamens sieht nichts. Aber A verliert seine Antwort: `gruppe-1`
    wird verdrängt. Die volle Schleife lehnt ab.

    Diese Probe ist die einzige, die eine Verkürzung der Schleife auf
    `{neuer_name}` rot macht. Vorher überlebte die Mutation alle Proben.
    """
    p, q = "\u1fb3\u0342", "\u1fbc\u0342"
    c = mit_bestand([_album("a", p + "|Strasse", "gruppe-1"),
                     _album("b", q + "|Straße", "gruppe-2"),
                     _album("c", p + "|Straße", "gruppe-2")])

    antwort = c.patch("/api/sync/albums/b", json={"album_name": q + "|Strasse"})
    assert antwort.status_code == 409, antwort.text
    assert antwort.json().get("error_key") == "err_album_name_in_use"

    # Und nichts ist passiert: A antwortet weiter mit seiner Gruppe.
    a = c.get("/api/sync/album-group", params={"album_name": p + "|Strasse"}).json()
    assert a and a["group_id"] == "gruppe-1", a
    assert _namen(c)["b"] == q + "|Straße"

def test_eine_fremde_gruppe_bleibt_auch_hier_gesperrt(mit_bestand):
    """Die Gegenprobe zu den Fällen darüber: eine fremde Gruppe bleibt gesperrt."""
    c = mit_bestand([_album("a1", "Sommerfest", "gruppe-1"),
                     _album("a2", "Herbstfest", "gruppe-2")])
    antwort = c.patch("/api/sync/albums/a1", json={"album_name": "Herbstfest"})
    assert antwort.status_code == 409, antwort.text
    assert antwort.json().get("error_key") == "err_album_name_in_use"
    assert _namen(c)["a1"] == "Sommerfest"
