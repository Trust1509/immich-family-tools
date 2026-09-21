"""Waechter: Bis zur ersten Ablehnung wird NICHTS geschrieben.

WARUM ES DIESE DATEI GIBT
-------------------------
Die Regel "alles, was ablehnen kann, gehoert vor den ersten Schreibvorgang"
wurde in `routers/albums.py` DREIMAL verletzt — ueber drei aufeinander
folgende Slices, jedes Mal vom selben Bauer, jedes Mal nachdem er sie im
Slice davor behoben hatte. Beim dritten Mal stand der Kommentar, der genau
davor warnt, vier Zeilen ueber der Aenderung.

Die Regel wurde bis hierher von Kommentaren und Aufmerksamkeit getragen. Nach
dem Massstab dieses Repos (`docs/agents/lehren.md`) ist das Disziplin, kein
Waechter. Hier ist der Waechter.

Die Folge einer Verletzung ist nicht kosmetisch: Der Aufrufer bekommt einen
Fehler, NACHDEM Personen in Immich umbenannt, Protokollzeilen geschrieben
oder Paare als abgeglichen markiert wurden. Eine Teilausfuehrung, die sich
als Eingabefehler ausgibt — und die der Nutzer nicht zurueckdrehen kann.

ZWEI TEILE, UND WARUM ES ZWEI BRAUCHT
-------------------------------------
TEIL A (statisch) liest die Endpunkte als Baum und prueft JEDEN
Ablehnungsweg: Steht auf irgendeinem Ausfuehrungspfad eine Ablehnung hinter
einem Schreibvorgang?

TEIL B (zur Laufzeit) faehrt je Endpunkt EINEN Ablehnungsfall durch die echte
Tuer und prueft, dass die Ablehnung ankommt UND nichts geschrieben wurde.
Teil A kennt nur Namen, Teil B kennt Zustaende.

DASS BEIDE NOETIG SIND, IST GEMESSEN, NICHT VERMUTET (21.09.2026):
Teil B wurde zuerst gebaut — allein. Danach wurde der dritte Vorfall
absichtlich wieder eingebaut, und Teil B blieb GRUEN. Der Grund ist
strukturell und nicht wegzureparieren: Teil B kann je Endpunkt nur den
Ablehnungsweg fahren, den er von aussen ERREICHT, und das ist fast immer der
FRUEHESTE. Der Defekt lebt aber am SPAETESTEN. Teil A hat diese Grenze nicht
— er sieht alle Wege, auch die, die man ohne echte Immich-Instanz nie
ausloest.

Umgekehrt hat Teil A eine Grenze, die Teil B nicht hat: Er haelt einen
AUFRUF fuer eine WIRKUNG. `store.delete_account("gibt-es-nicht")` kehrt
zurueck, ohne etwas zu aendern — fuer Teil A ist das ein Schreibvorgang.
Diese Faelle stehen unten namentlich in ERLAUBT, und was sie entlastet, ist
jeweils ein Fall aus Teil B.

Alle Daten erfunden; das Repo ist oeffentlich.
"""

import ast
import io
import json
import pathlib

import pytest
from fastapi.testclient import TestClient

import main
from services import sync_service

WURZEL = pathlib.Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# TEIL A — statisch: kein Ablehnungsweg hinter einem Schreibvorgang
# ---------------------------------------------------------------------------
#
# Die Listen, mit denen dieser Teil arbeitet, stammen AUS DEM BAUM, nicht aus
# dem Gedaechtnis des Bauers. Das ist Absicht: Eine erinnerte Liste hat in
# diesem Projekt schon mehrfach eine Zusage getragen, die nicht stimmte
# (`docs/agents/lehren.md`). Wer eine Methode hinzufuegt, die schreibt, muss
# hier nichts nachtragen.


def _baum(rel: str) -> ast.Module:
    return ast.parse(io.open(WURZEL / rel, encoding="utf-8").read())


def _funktionen(baum: ast.AST) -> dict:
    return {n.name: n for n in ast.walk(baum)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _lehnt_direkt_ab(knoten: ast.AST) -> bool:
    """Wirft die Funktion selbst ein `errors.*`?"""
    for k in ast.walk(knoten):
        if isinstance(k, ast.Raise) and isinstance(k.exc, ast.Call):
            f = k.exc.func
            if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                    and f.value.id == "errors"):
                return True
    return False


def _ablehnende_huelle(fns: dict) -> set:
    """Wer kann ablehnen — direkt ODER ueber einen Aufruf? Fixpunkt.

    An der Huelle haengt Vorfall 1: Dort stand nicht ein `raise` hinter dem
    Schreibvorgang, sondern ein AUFRUF von `_name_des_bestehenden_albums`,
    der seinerseits ablehnt. Ein Waechter, der nur `raise` zaehlt, sieht das
    nicht.
    """
    kann = {name for name, k in fns.items() if _lehnt_direkt_ab(k)}
    while True:
        neu = set(kann)
        for name, knoten in fns.items():
            if name in kann:
                continue
            for c in ast.walk(knoten):
                if isinstance(c, ast.Call):
                    f = c.func
                    ziel = (f.attr if isinstance(f, ast.Attribute)
                            else f.id if isinstance(f, ast.Name) else None)
                    if ziel in kann:
                        neu.add(name)
                        break
        if neu == kann:
            return kann
        kann = neu


def _schreibende_store_methoden() -> set:
    """Jede ConfigStore-Methode, die `self._save()` erreicht."""
    fns = _funktionen(_baum("services/config_store.py"))
    return {name for name, k in fns.items()
            if any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                   and c.func.attr == "_save" for c in ast.walk(k))}


def _eigene_knoten(stmt: ast.stmt):
    """Die Ausdruecke DIESES Statements — ohne die eingebetteten Bloecke.

    Ohne diese Trennung meldet der Waechter Zweige gegeneinander: ein
    Schreibvorgang im `if`-Zweig und eine Ablehnung im `else`-Zweig liegen
    auf verschiedenen Pfaden und sind kein Fund. Genau das hat die erste
    Fassung zweimal gemeldet (`create_album`), gemessen am sauberen Baum.
    """
    if isinstance(stmt, (ast.If, ast.While)):
        quellen = [stmt.test]
    elif isinstance(stmt, (ast.For, ast.AsyncFor)):
        quellen = [stmt.iter]
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        quellen = [i.context_expr for i in stmt.items]
    elif isinstance(stmt, ast.Try):
        quellen = []
    else:
        quellen = [stmt]
    for q in quellen:
        yield from ast.walk(q)


def _ereignisse(stmt, schreibt_store, schreibt_dienst, lehnt_store, lehnt_helfer):
    """(Zeile, 'schreibt'|'lehnt_ab', Text) fuer dieses eine Statement."""
    aus = []
    for k in _eigene_knoten(stmt):
        if isinstance(k, ast.Raise) and isinstance(k.exc, ast.Call):
            f = k.exc.func
            if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                    and f.value.id == "errors"):
                aus.append((k.lineno, "lehnt_ab", f"raise errors.{f.attr}()"))
        elif isinstance(k, ast.Call):
            f = k.func
            if isinstance(f, ast.Attribute):
                basis = f.value.id if isinstance(f.value, ast.Name) else None
                if basis == "errors":
                    continue
                if f.attr in schreibt_store:
                    aus.append((k.lineno, "schreibt", f"store.{f.attr}()"))
                elif basis == "sync_service" and f.attr in schreibt_dienst:
                    aus.append((k.lineno, "schreibt", f"sync_service.{f.attr}()"))
                elif f.attr in lehnt_store:
                    aus.append((k.lineno, "lehnt_ab", f"store.{f.attr}() lehnt ab"))
            elif isinstance(f, ast.Name) and f.id in lehnt_helfer:
                aus.append((k.lineno, "lehnt_ab", f"{f.id}() lehnt ab"))
    aus.sort(key=lambda e: e[0])
    return aus


def _pfad_pruefen(stmts, geschrieben, funde, listen):
    """Laeuft die Statements der Reihe nach und verzweigt wie das Programm.

    `geschrieben` ist (Zeile, Text) des ersten Schreibvorgangs auf DIESEM
    Pfad — oder None. Rueckgabe: derselbe Wert nach dem Block.
    """
    for stmt in stmts:
        for zeile, art, text in _ereignisse(stmt, *listen):
            if art == "lehnt_ab" and geschrieben:
                funde.append((zeile, text, geschrieben))
            elif art == "schreibt" and not geschrieben:
                geschrieben = (zeile, text)

        if isinstance(stmt, (ast.If, ast.For, ast.AsyncFor, ast.While)):
            a = _pfad_pruefen(stmt.body, geschrieben, funde, listen)
            b = _pfad_pruefen(stmt.orelse, geschrieben, funde, listen)
            geschrieben = geschrieben or a or b
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            geschrieben = _pfad_pruefen(stmt.body, geschrieben, funde, listen) or geschrieben
        elif isinstance(stmt, ast.Try):
            # Ein `except` laeuft NACH dem, was im `try` schon passiert ist.
            # Deshalb zaehlt ein Schreibvorgang aus dem try-Block fuer die
            # Handler — sonst verschwindet jede Ablehnung, die man in ein
            # `try` einwickelt, aus der Sicht dieses Waechters.
            im_try = _pfad_pruefen(stmt.body, geschrieben, funde, listen)
            for h in stmt.handlers:
                _pfad_pruefen(h.body, im_try or geschrieben, funde, listen)
            nach = _pfad_pruefen(stmt.orelse, im_try or geschrieben, funde, listen)
            geschrieben = _pfad_pruefen(
                stmt.finalbody, nach or im_try or geschrieben, funde, listen
            ) or nach or im_try or geschrieben
    return geschrieben


def _ist_endpunkt(knoten) -> bool:
    return any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
               and d.func.attr in {"get", "post", "put", "patch", "delete"}
               for d in knoten.decorator_list)


# Stellen, an denen Teil A einen AUFRUF fuer eine WIRKUNG haelt — mit Grund.
# Ein Eintrag, zu dem es keinen Fund mehr gibt, macht die Suite rot: eine
# Ausnahme, die niemand mehr braucht, verschwindet, statt stumm etwas Neues
# zu decken.
ERLAUBT = {
    ("accounts.py", "delete_account"):
        "`store.delete_account` liefert bei unbekannter Kennung False, OHNE zu "
        "schreiben; die Ablehnung danach IST diese Antwort. Dass dabei wirklich "
        "nichts geschrieben wird, prueft Teil B "
        "(DELETE /api/accounts/gibt-es-nicht).",
    ("albums.py", "delete_managed_album"):
        "Wie oben, mit `store.delete_managed_album`; geprueft von Teil B "
        "(DELETE /api/sync/albums/gibt-es-nicht).",
    ("accounts.py", "refresh_account"):
        "ECHTER Fund, bewusst offen gelassen: Der `except`-Block umfasst auch "
        "den Schreibvorgang, also kann ein Fehler NACH `update_account` als "
        "502 'Immich-Anfrage fehlgeschlagen' herauskommen, obwohl geschrieben "
        "wurde und Immich in Ordnung war. Nicht das Muster der drei Vorfaelle "
        "(502 statt 4xx, kein Eingabefehler), aber dieselbe Familie. Hier nicht "
        "mitrepariert, weil sich dabei das Verhalten eines Fehlerpfads aendert "
        "und dieser Slice den Waechter baut, nicht die Router — Issue #87.",
}


def _endpunkt_funde(quelltext: str, listen) -> dict:
    """{Endpunkt: [(Zeile, Text, erster Schreibvorgang)]} fuer eine Quelle."""
    baum = ast.parse(quelltext)
    aus = {}
    for knoten in baum.body:
        if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _ist_endpunkt(knoten):
            continue
        funde = []
        _pfad_pruefen(knoten.body, None, funde, listen)
        if funde:
            aus[knoten.name] = funde
    return aus


# Eine Quelle, die es nur fuer diesen Test gibt: sechs Endpunkte, von denen
# GENAU VIER ein Fund sind. Sie prueft die Mechanik von Teil A gegen eine
# Vorlage, die sich nicht mitbewegt, wenn jemand die Router umbaut.
#
# Ohne sie waere die Mechanik nur so lange bewiesen, wie zufaellig ein echter
# Fund im Baum steht (`docs/agents/lehren.md` §18): Faellt der weg, meldet
# der Waechter gruen, ohne noch irgendetwas zu koennen.
MECHANIK_QUELLE = '''
@router.post("/x")
def nach_dem_schreiben(store):
    store.schreib()
    raise errors.nein()

@router.post("/x")
def vor_dem_schreiben(store):
    raise errors.nein()
    store.schreib()

@router.post("/x")
def in_getrennten_zweigen(store, a):
    if a:
        store.schreib()
    else:
        raise errors.nein()

@router.post("/x")
def im_handler(store):
    try:
        store.schreib()
    except Exception:
        raise errors.nein()

@router.post("/x")
def ueber_zwei_aufrufe(store):
    store.schreib()
    helfer()

def helfer():
    noch_tiefer()

def noch_tiefer():
    raise errors.nein()

@router.post("/x")
def nach_einer_schleife(store, xs):
    for x in xs:
        store.schreib()
    raise errors.nein()
'''


def test_mechanik_trennt_pfade_und_folgt_aufrufen():
    """Teil A gegen eine erfundene Quelle mit bekanntem Ergebnis."""
    fns = _funktionen(ast.parse(MECHANIK_QUELLE))
    listen = ({"schreib"}, set(), set(), _ablehnende_huelle(fns))
    gefunden = set(_endpunkt_funde(MECHANIK_QUELLE, listen))

    assert gefunden == {
        "nach_dem_schreiben",     # der einfache Fall
        "im_handler",             # `except` laeuft NACH dem try-Block
        "ueber_zwei_aufrufe",     # Ablehnung ueber eine Aufrufkette
        "nach_einer_schleife",    # Schreibvorgang im Schleifenkoerper zaehlt danach
    }, (
        "Die Mechanik von Teil A hat sich geaendert. Erwartet wird ausserdem "
        "AUSDRUECKLICH, dass `vor_dem_schreiben` (richtige Reihenfolge) und "
        "`in_getrennten_zweigen` (if/else, nie derselbe Pfad) KEIN Fund sind."
    )


def test_keine_ablehnung_hinter_einem_schreibvorgang():
    """Teil A: auf KEINEM Pfad steht eine Ablehnung hinter einem Schreibvorgang."""
    schreibt_store = _schreibende_store_methoden()
    dienst = _funktionen(_baum("services/sync_service.py"))
    schreibt_dienst = {n for n in dienst if not n.startswith("_")}
    lehnt_store = _ablehnende_huelle(_funktionen(_baum("services/config_store.py")))
    lehnt_store -= schreibt_store

    gemeldet = {}
    for pfad in sorted((WURZEL / "routers").glob("*.py")):
        quelltext = io.open(pfad, encoding="utf-8").read()
        listen = (schreibt_store, schreibt_dienst, lehnt_store,
                  _ablehnende_huelle(_funktionen(ast.parse(quelltext))))
        for fn, funde in _endpunkt_funde(quelltext, listen).items():
            gemeldet[(pfad.name, fn)] = funde

    unerwartet = {k: v for k, v in gemeldet.items() if k not in ERLAUBT}
    zeilen = [""]
    for (datei, fn), funde in unerwartet.items():
        erste = funde[0][2]
        zeilen.append(f"{datei}:{fn} — erster Schreibvorgang Zeile "
                      f"{erste[0]} ({erste[1]}), danach:")
        zeilen += [f"    Zeile {z}: {t}" for z, t, _ in funde]
    zeilen += [
        "",
        "Alles, was ablehnen kann, gehoert VOR den ersten Schreibvorgang —",
        "sonst bekommt der Aufrufer einen Fehler, nachdem schon geschrieben wurde.",
        "Schreibt der Aufruf gar nicht, gehoert er mit Begruendung nach ERLAUBT.",
    ]
    assert not unerwartet, "\n".join(zeilen)

    veraltet = sorted(set(ERLAUBT) - set(gemeldet))
    assert not veraltet, (
        "Diese ERLAUBT-Eintraege haben keinen Fund mehr und gehoeren entfernt, "
        f"sonst deckt die Ausnahme irgendwann etwas Neues: {veraltet}"
    )


# ---------------------------------------------------------------------------
# TEIL B — zur Laufzeit: die Ablehnung kommt an, und nichts wurde geschrieben
# ---------------------------------------------------------------------------

# ERFUNDEN und als solches erkennbar.
TESTMARKE = "nur-fuer-den-test-kein-geheimnis"
KOPF = {"Authorization": f"Bearer {TESTMARKE}"}

KONTEN = {
    "konto-1": {"id": "konto-1", "name": "Konto Eins",
                "immich_url": "http://beispiel.invalid", "api_key": "platzhalter-1",
                "color": "#111111", "user_id": "u1"},
    "konto-2": {"id": "konto-2", "name": "Konto Zwei",
                "immich_url": "http://beispiel.invalid", "api_key": "platzhalter-2",
                "color": "#222222", "user_id": "u2"},
}

ALBUM = {
    "id": "a1", "match_id": "m-1", "album_id": "ia-1", "album_name": "Testalbum",
    "group_id": "gruppe-1", "owner_account_id": "konto-1",
    "person_refs": [{"account_id": "konto-1", "person_id": "p1", "person_name": "p1",
                     "account_name": "Konto Eins", "account_color": "#111111"}],
    "created_at": "2026-01-01T00:00:00+00:00", "last_synced_at": None,
    "total_assets": 0, "status": "active",
}

# Was als SCHREIBVORGANG gilt: die WIRKUNG, nicht der Aufruf.
#
# Die erste Fassung zaehlte Aufrufe der Mutatoren und meldete zwei FEHLFUNDE:
# `delete_account` und `delete_managed_album` kehren bei unbekannter Kennung
# zurueck, OHNE etwas zu aendern. Ein Waechter, der den Aufruf fuer die
# Wirkung nimmt, zwingt den Bauer, funktionierenden Code umzubauen — gemessen
# beim ersten Lauf dieses Waechters.
#
# Geprueft wird deshalb der ZUSTAND: die Datei UND `store._data`. Damit
# braucht es keine gepflegte Liste von Mutatoren, und eine Aenderung, die nur
# im Speicher landet, faellt genauso auf.
#
# Fuer Immich geht das nicht — dort hinterlaesst ein Schreibvorgang in
# unserem Zustand keine Spur. Da IST der Aufruf die Wirkung, und diese Liste
# stammt aus `grep "^async def" sync_service.py`, nicht aus dem Gedaechtnis.

DIENST_SCHREIBT = [
    "sync_names", "sync_names_multi", "create_shared_album",
    "link_existing_album", "refresh_managed_album", "extend_match",
    "undo_sync_name",
]


@pytest.fixture
def aufbau(tmp_path, monkeypatch):
    """Client plus eine Liste, in die JEDER Schreibvorgang seinen Namen legt."""
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": KONTEN, "managed_albums": [ALBUM],
        "dismissed_match_ids": [], "synced_name_match_ids": [],
        "sync_log": [], "auto_sync": {"enabled": False, "time": "01:00"},
    }), encoding="utf-8")

    monkeypatch.setattr(main.settings, "secret", TESTMARKE, raising=False)
    monkeypatch.setattr(main.settings, "config_path", pfad, raising=False)

    geschrieben: list[str] = []

    def merke_dienst(name):
        echt = getattr(sync_service, name)

        async def gemerkt(*a, **k):
            geschrieben.append(f"dienst.{name}")
            return await echt(*a, **k)

        return gemerkt

    with TestClient(main.app) as client:
        # Erst NACH dem Start instrumentieren: Der Startup selbst schreibt
        # legitim (Wanderung, user_id-Nachtrag) und gehoert nicht zur Anfrage.
        for name in DIENST_SCHREIBT:
            monkeypatch.setattr(sync_service, name, merke_dienst(name))

        class Konto:
            async def get_person(self, _pid):
                return {"id": _pid}

        class Pool:
            def get_for_account(self, _acc):
                return Konto()

            def get(self, *_a, **_k):
                return Konto()

            def invalidate(self, *_a, **_k):
                pass

        main.app.state.client_pool = Pool()
        geschrieben.clear()
        yield client, geschrieben, pfad, main.app.state.store


# (Methode, Pfad, Koerper oder None, warum das abgelehnt werden MUSS)
ABLEHNUNGEN = [
    ("POST", "/api/accounts", {"name": "", "immich_url": "http://beispiel.invalid",
                               "api_key": "x"}, "leerer Name"),
    ("PUT", "/api/accounts/gibt-es-nicht", {"name": "X"}, "unbekanntes Konto"),
    ("DELETE", "/api/accounts/gibt-es-nicht", None, "unbekanntes Konto"),
    ("POST", "/api/accounts/gibt-es-nicht/refresh", None, "unbekanntes Konto"),
    ("POST", "/api/sync/names", {"match_id": "gibt-es-nicht", "name": "X"},
     "unbekanntes Match"),
    # DIESER Fall ist mit Bedacht gewaehlt, und die Wahl ist GEMESSEN:
    # Ein Koerper mit `group_id: "gibt-es-nicht"` waere hier wertlos — den
    # faengt die FRUEHE Schranke (#81) gleich am Anfang des Endpunkts ab, also
    # weit vor jedem Schreibvorgang. Er kann nicht zeigen, ob eine SPAETE
    # Ablehnung hinter einem Schreibvorgang steht; genau daran ist eine
    # fruehere Fassung dieser Tabelle gescheitert.
    #
    # Das Aufloesen des Albumnamens ist die SPAETESTE Ablehnung dieses
    # Endpunkts — und genau die, die einmal hinter `sync_names_multi` stand.
    # Mit `existing_album_id` und OHNE `album_name` muss der Name aus Immich
    # kommen; hier gibt es kein Immich, also lehnt der Endpunkt ab.
    ("POST", "/api/sync/names-multi",
     {"persons": [{"account_id": "konto-1", "person_id": "p1"},
                  {"account_id": "konto-2", "person_id": "p2"}],
      "canonical_name": "Testname", "existing_album_id": "ia-9"},
     "Albumname nicht aufloesbar — die SPAETESTE Ablehnung dieses Endpunkts"),
    ("POST", "/api/sync/extend",
     {"managed_album_id": "gibt-es-nicht", "account_id": "konto-1",
      "person_id": "p9"}, "unbekanntes verwaltetes Album"),
    ("POST", "/api/sync/album",
     {"match_id": "gibt-es-nicht", "owner_account_id": "konto-1",
      "album_name": "X"}, "unbekanntes Match"),
    ("POST", "/api/sync/album/gibt-es-nicht/refresh", None,
     "unbekanntes verwaltetes Album"),
    ("DELETE", "/api/sync/albums/gibt-es-nicht", None,
     "unbekanntes verwaltetes Album"),
    ("POST", "/api/sync/undo", {"log_entry_id": "gibt-es-nicht"},
     "unbekannter Protokolleintrag"),
    ("DELETE", "/api/sync/log", None, "kein Ablehnungsweg — siehe OHNE_ABLEHNUNG"),
    ("PUT", "/api/sync/autosync-config", {"enabled": True, "time": "25:99"},
     "unmoegliche Uhrzeit"),
    ("POST", "/api/auth/login", {"secret": "falsch"}, "falsches Geheimnis"),
    ("POST", "/api/auth/logout", None, "kein Ablehnungsweg — siehe OHNE_ABLEHNUNG"),
    ("POST", "/api/faces/refresh", None, "kein Ablehnungsweg — siehe OHNE_ABLEHNUNG"),
    ("POST", "/api/faces/gibt-es-nicht/dismiss", None, "unbekanntes Match"),
]

# Endpunkte, die KEINEN Ablehnungsweg haben, den man ohne echte Instanz
# ausloesen kann. Sie stehen hier NAMENTLICH, damit "kein Eintrag" nie
# unbemerkt bleibt — und mit dem Grund, warum sie ausgenommen sind.
OHNE_ABLEHNUNG = {
    ("DELETE", "/api/sync/log"): "nimmt keine Eingabe; es gibt nichts abzulehnen",
    ("POST", "/api/auth/logout"): "nimmt keine Eingabe; loescht nur das Keks",
    ("POST", "/api/faces/refresh"): "nimmt keine Eingabe; jede Ablehnung kaeme "
                                    "aus Immich, nicht aus der Anfrage",
}


def _schreibende_endpunkte() -> set:
    """Aus der laufenden App, nicht aus einer gepflegten Liste."""
    gefunden = set()
    for route in main.app.routes:
        pfad = getattr(route, "path", "")
        if not pfad.startswith("/api/"):
            continue
        for methode in getattr(route, "methods", set()) or set():
            if methode in {"POST", "PUT", "PATCH", "DELETE"}:
                gefunden.add((methode, pfad))
    return gefunden


def _passt(methode: str, pfad: str, muster: str) -> bool:
    """`/api/accounts/gibt-es-nicht` passt auf `/api/accounts/{account_id}`."""
    m_teile, p_teile = muster.strip("/").split("/"), pfad.strip("/").split("/")
    if len(m_teile) != len(p_teile):
        return False
    return all(m.startswith("{") or m == p for m, p in zip(m_teile, p_teile))


def test_jeder_schreibende_endpunkt_hat_einen_ablehnungsfall():
    """Ein NEUER Endpunkt ohne Eintrag macht diesen Waechter rot.

    Das ist der Teil, der die Tabelle am Altern hindert: Sie wird aus der
    laufenden App gegengeprueft, nicht gepflegt.
    """
    abgedeckt = set()
    for methode, pfad, _koerper, _warum in ABLEHNUNGEN:
        for m, muster in _schreibende_endpunkte():
            if m == methode and _passt(methode, pfad, muster):
                abgedeckt.add((m, muster))
    for (methode, muster) in OHNE_ABLEHNUNG:
        for m, echtes_muster in _schreibende_endpunkte():
            if m == methode and _passt(methode, muster, echtes_muster):
                abgedeckt.add((m, echtes_muster))

    fehlend = sorted(_schreibende_endpunkte() - abgedeckt)
    assert not fehlend, (
        "Diese schreibenden Endpunkte haben keinen Ablehnungsfall. Trage sie in "
        "ABLEHNUNGEN ein — oder, wenn sie keinen Ablehnungsweg haben, mit "
        f"Begruendung in OHNE_ABLEHNUNG:\n  " + "\n  ".join(f"{m} {p}" for m, p in fehlend)
    )


@pytest.mark.parametrize(
    "methode,pfad,koerper,warum",
    [f for f in ABLEHNUNGEN if (f[0], f[1]) not in OHNE_ABLEHNUNG],
    ids=lambda v: str(v)[:40],
)
def test_bis_zur_ablehnung_wird_nichts_geschrieben(aufbau, methode, pfad, koerper, warum):
    client, geschrieben, datei, store = aufbau

    vorher_datei = datei.read_bytes()
    vorher_speicher = json.dumps(store._data, sort_keys=True)

    antwort = client.request(methode, pfad, headers=KOPF,
                             json=koerper if koerper is not None else None)

    assert 400 <= antwort.status_code < 500, (
        f"{methode} {pfad} sollte ablehnen ({warum}), kam mit {antwort.status_code}"
    )
    assert datei.read_bytes() == vorher_datei, (
        f"{methode} {pfad} hat VOR der Ablehnung die Konfiguration geschrieben ({warum}).\n"
        "Alles, was ablehnen kann, gehoert vor den ersten Schreibvorgang."
    )
    assert json.dumps(store._data, sort_keys=True) == vorher_speicher, (
        f"{methode} {pfad} hat VOR der Ablehnung den Speicher veraendert ({warum}).\n"
        "Auch ohne Schreibvorgang auf die Platte sieht die laufende Anwendung das sofort."
    )
    assert geschrieben == [], (
        f"{methode} {pfad} hat VOR der Ablehnung nach Immich geschrieben ({warum}): "
        f"{geschrieben}"
    )
