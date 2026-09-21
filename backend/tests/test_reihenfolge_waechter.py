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
TEIL A (statisch) nimmt die Endpunkte, die die Anwendung WIRKLICH montiert
hat, liest ihren Quelltext als Baum und prueft JEDEN Ausfuehrungspfad.

TEIL B (zur Laufzeit) faehrt je Endpunkt EINEN Ablehnungsfall durch die echte
Tuer und prueft, dass genau die erwartete Ablehnung ankommt UND nichts
geschrieben wurde. Teil A kennt nur Namen, Teil B kennt Zustaende.

DASS BEIDE NOETIG SIND, IST GEMESSEN (21.09.2026): Teil B wurde zuerst
gebaut — allein. Danach wurde der dritte Vorfall absichtlich wieder
eingebaut, und Teil B blieb GRUEN. Der Grund ist strukturell: Teil B kann je
Endpunkt nur den Ablehnungsweg fahren, den er von aussen ERREICHT, und das
ist fast immer der FRUEHESTE. Der Defekt lebt am SPAETESTEN.

Umgekehrt haelt Teil A einen AUFRUF fuer eine WIRKUNG:
`store.delete_account("gibt-es-nicht")` kehrt zurueck, ohne etwas zu aendern.
Solche Faelle stehen in ERLAUBT — mit der genauen Fundsignatur, sodass ein
ZUSAETZLICHER Fund in derselben Funktion weiter rot ist.

WAS DIE ERSTE FASSUNG FALSCH HATTE
----------------------------------
Zwei Pruefstimmen haben unabhaengig gemessen, dass der Waechter sich an
mehreren Stellen selbst ausgehebelt hat. Alle sind unten im Code an ihrer
Stelle benannt; hier die Liste, damit keine davon leise zurueckkommt:

  1. Der Vollstaendigkeitstest las `main.app.routes` und bekam die LEERE
     MENGE (dort liegen `_IncludedRouter`-Huellen ohne `path`). Er konnte
     nie rot werden.
  2. Zwei Tabellenzeilen zeigten auf `/api/faces/...`, waehrend der Router
     `/api/matches` heisst. Eine wurde nie gefahren, die andere war gruen an
     einem generischen 404.
  3. Teil B prueft nur "irgendein 4xx". Damit war er auch dann vollstaendig
     gruen, wenn ALLE Router abgehaengt waren oder die Anmeldung jede
     Anfrage mit 401 abwies.
  4. Teil A las `routers/*.py` per Dateimuster. Ein Umzug der Router in ein
     anderes Verzeichnis liess ihn mit NULL analysierten Endpunkten gruen.
  5. Die Schreibvorgaenge hatten keinen Fixpunkt: `mark_all_pairs_synced`
     schreibt ueber `mark_names_synced` und war unsichtbar — ausgerechnet
     in `sync_names_multi`, dem Endpunkt aller drei Vorfaelle.
  6. ERLAUBT befreite die ganze Funktion. Ein echter neuer Fehler in einer
     befreiten Funktion kam durch.
  7. `match`/`case` wurde flachgewalzt (Fehlfunde), Schreibvorgaenge aus
     `except`-Handlern wurden nicht weitergetragen (Luecke), und ein
     Schreibvorgang in einem Zweig, der mit `return` endet, wurde faelschlich
     weitergetragen (Fehlfund).

Alle Daten erfunden; das Repo ist oeffentlich.
"""

import ast
import inspect
import io
import json
import pathlib
import textwrap

import pytest
from fastapi.testclient import TestClient

import main

WURZEL = pathlib.Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# TEIL A — statisch: kein Ablehnungsweg hinter einem Schreibvorgang
# ---------------------------------------------------------------------------
#
# Die Listen, mit denen dieser Teil arbeitet, stammen AUS DEM BAUM, nicht aus
# dem Gedaechtnis des Bauers. Das ist Absicht: Eine erinnerte Liste hat in
# diesem Projekt schon mehrfach eine Zusage getragen, die nicht stimmte
# (`docs/agents/lehren.md`).


def _baum(rel: str) -> ast.Module:
    return ast.parse(io.open(WURZEL / rel, encoding="utf-8").read())


def _funktionen(baum: ast.AST) -> dict:
    return {n.name: n for n in ast.walk(baum)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _gerufene_namen(knoten: ast.AST) -> set:
    """Jeder Name, der in dieser Funktion aufgerufen wird."""
    aus = set()
    for c in ast.walk(knoten):
        if isinstance(c, ast.Call):
            f = c.func
            if isinstance(f, ast.Attribute):
                aus.add(f.attr)
            elif isinstance(f, ast.Name):
                aus.add(f.id)
    return aus


def _erreichbar(fns: dict, direkt: set) -> set:
    """Fixpunkt: wer `direkt` erreicht — unmittelbar ODER ueber Aufrufe.

    BEIDE Eigenschaften dieses Waechters brauchen denselben Fixpunkt, und
    beide Male ist das gemessen, nicht vermutet:

    * Bei den ABLEHNUNGEN haengt Vorfall 1 daran — dort stand kein `raise`
      hinter dem Schreibvorgang, sondern ein AUFRUF von
      `_name_des_bestehenden_albums`, der seinerseits ablehnt.
    * Bei den SCHREIBVORGAENGEN fehlte er in der ersten Fassung. Folge:
      `ConfigStore.mark_all_pairs_synced` schreibt ueber `mark_names_synced`
      und war damit unsichtbar — ausgerechnet in `sync_names_multi`, dem
      Endpunkt aller drei Vorfaelle.
    """
    kann = set(direkt)
    while True:
        neu = set(kann)
        for name, knoten in fns.items():
            if name not in kann and _gerufene_namen(knoten) & kann:
                neu.add(name)
        if neu == kann:
            return kann
        kann = neu


# Womit eine Ablehnung geworfen wird. `errors.*` ist die Hausform; die beiden
# anderen stehen hier, weil ein anderer Test sie zwar verbietet (keine nackte
# HTTPException), ein Waechter sich aber nicht auf einen anderen Waechter
# verlassen soll.
ABLEHNUNGS_TYPEN = {"HTTPException", "AppError"}


def _ist_ablehnung(raise_knoten) -> str | None:
    if not isinstance(raise_knoten.exc, ast.Call):
        return None
    f = raise_knoten.exc.func
    if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
            and f.value.id == "errors"):
        return f"raise errors.{f.attr}()"
    if isinstance(f, ast.Name) and f.id in ABLEHNUNGS_TYPEN:
        return f"raise {f.id}()"
    if isinstance(f, ast.Attribute) and f.attr in ABLEHNUNGS_TYPEN:
        return f"raise {f.attr}()"
    return None


def _lehnt_direkt_ab(knoten: ast.AST) -> bool:
    return any(_ist_ablehnung(k) for k in ast.walk(knoten)
               if isinstance(k, ast.Raise))


def _ablehnende_huelle(fns: dict) -> set:
    return _erreichbar(fns, {n for n, k in fns.items() if _lehnt_direkt_ab(k)})


def _schreibende_store_methoden() -> set:
    """Jede ConfigStore-Methode, die `self._save()` erreicht — auch ueber Umwege."""
    fns = _funktionen(_baum("services/config_store.py"))
    direkt = {name for name, k in fns.items() if "_save" in _gerufene_namen(k)}
    return _erreichbar(fns, direkt) - {"_save"}


TRY_TYPEN = (ast.Try,) + ((ast.TryStar,) if hasattr(ast, "TryStar") else ())
ENDE_TYPEN = (ast.Return, ast.Raise, ast.Break, ast.Continue)


def _eigene_knoten(stmt: ast.stmt):
    """Die Ausdruecke DIESES Statements — ohne die eingebetteten Bloecke.

    Ohne diese Trennung meldet der Waechter Zweige gegeneinander: ein
    Schreibvorgang im `if`-Zweig und eine Ablehnung im `else`-Zweig liegen
    auf verschiedenen Pfaden und sind kein Fund. Genau das hat die erste
    Fassung zweimal gemeldet (`create_album`), gemessen am sauberen Baum —
    und bei `match`/`case` ein drittes Mal, weil es keinen eigenen Zweig
    hatte und in den Sammelfall fiel.
    """
    if isinstance(stmt, (ast.If, ast.While)):
        quellen = [stmt.test]
    elif isinstance(stmt, (ast.For, ast.AsyncFor)):
        quellen = [stmt.iter]
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        quellen = [i.context_expr for i in stmt.items]
    elif isinstance(stmt, ast.Match):
        quellen = [stmt.subject]
    elif isinstance(stmt, TRY_TYPEN):
        quellen = []
    else:
        quellen = [stmt]
    for q in quellen:
        yield from ast.walk(q)


def _ereignisse(stmt, schreibt_store, schreibt_dienst, lehnt_store, lehnt_helfer):
    """(Zeile, 'schreibt'|'lehnt_ab', Text) fuer dieses eine Statement."""
    aus = []
    for k in _eigene_knoten(stmt):
        if isinstance(k, ast.Raise):
            text = _ist_ablehnung(k)
            if text:
                aus.append((k.lineno, "lehnt_ab", text))
        elif isinstance(k, ast.Call):
            f = k.func
            if isinstance(f, ast.Attribute):
                basis = f.value.id if isinstance(f.value, ast.Name) else None
                if basis == "errors":
                    continue
                # Eine Funktion kann BEIDES: erst ablehnen, dann schreiben.
                # Dann zaehlt sie als beides — sonst verschwindet eine
                # Ablehnung, sobald jemand ihrer Funktion ein `_save()` gibt.
                if f.attr in lehnt_store:
                    aus.append((k.lineno, "lehnt_ab", f"{f.attr}() lehnt ab"))
                if f.attr in schreibt_store:
                    aus.append((k.lineno, "schreibt", f"store.{f.attr}()"))
                elif basis == "sync_service" and f.attr in schreibt_dienst:
                    aus.append((k.lineno, "schreibt", f"sync_service.{f.attr}()"))
            elif isinstance(f, ast.Name) and f.id in lehnt_helfer:
                aus.append((k.lineno, "lehnt_ab", f"{f.id}() lehnt ab"))
    # Bei gleicher Zeile zuerst die Ablehnung: Ein Aufruf, der beides kann,
    # lehnt ab, BEVOR er schreibt — sonst deckt er sich selbst zu.
    aus.sort(key=lambda e: (e[0], 0 if e[1] == "lehnt_ab" else 1))
    return aus


def _pfad_pruefen(stmts, geschrieben, funde, listen):
    """Laeuft die Statements der Reihe nach und verzweigt wie das Programm.

    `geschrieben` ist (Zeile, Text) des ersten Schreibvorgangs auf DIESEM
    Pfad — oder None.

    Rueckgabe: `(geschrieben, endet)`. `endet` sagt, ob der Block IMMER
    verlassen wird (`return`, `raise`, `break`, `continue`). Das ist nicht
    Feinschliff, sondern zwei gemessene Fehler auf einmal:

    * Ohne die Angabe wurde ein Schreibvorgang aus einem Zweig, der mit
      `return` endet, hinter das `if` getragen — eine Ablehnung danach war
      ein FEHLFUND.
    * Und ein Schreibvorgang aus einem `except`-Handler wurde gar nicht
      weitergetragen — eine Ablehnung danach war eine LUECKE.
    """
    endet = False
    for stmt in stmts:
        # Eine verschachtelte Funktion wird HIER nicht ausgefuehrt. Ihre
        # Zeilen gehoeren nicht in diesen Pfad; ist sie selbst ein Endpunkt,
        # wird sie eigens analysiert.
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        for zeile, art, text in _ereignisse(stmt, *listen):
            if art == "lehnt_ab" and geschrieben:
                funde.append((zeile, text, geschrieben))
            elif art == "schreibt" and not geschrieben:
                geschrieben = (zeile, text)

        if isinstance(stmt, ast.If):
            a, ea = _pfad_pruefen(stmt.body, geschrieben, funde, listen)
            b, eb = _pfad_pruefen(stmt.orelse, geschrieben, funde, listen)
            geschrieben = geschrieben or _erster(((a, ea), (b, eb)))
            if ea and eb and stmt.orelse:
                endet = True
        elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            # Ein Schleifenkoerper kann laufen oder nicht; beides ist moeglich,
            # also traegt er nicht "endet", wohl aber seinen Schreibvorgang.
            a, _ = _pfad_pruefen(stmt.body, geschrieben, funde, listen)
            b, _ = _pfad_pruefen(stmt.orelse, geschrieben, funde, listen)
            geschrieben = geschrieben or a or b
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            a, ea = _pfad_pruefen(stmt.body, geschrieben, funde, listen)
            geschrieben = geschrieben or a
            endet = endet or ea
        elif isinstance(stmt, ast.Match):
            # Jeder Fall laeuft gegen den Stand VOR dem `match` — sonst sieht
            # `case _` den Schreibvorgang aus `case 1`, und die Zweigtrennung
            # ist wieder aufgehoben. Genau so ist dieser Zweig beim ersten
            # Lauf durchgefallen.
            #
            # Ob die Faelle erschoepfend sind, sagt der Baum nicht; deshalb
            # nie "endet", aber jeder Fall traegt seinen Schreibvorgang weiter.
            vorher = geschrieben
            zweige = [_pfad_pruefen(fall.body, vorher, funde, listen)
                      for fall in stmt.cases]
            geschrieben = vorher or _erster(zweige)
        elif isinstance(stmt, TRY_TYPEN):
            im_try, e_try = _pfad_pruefen(stmt.body, geschrieben, funde, listen)
            # Ein `except` laeuft NACH dem, was im `try` schon passiert ist.
            handler = []
            for h in stmt.handlers:
                handler.append(_pfad_pruefen(
                    h.body, im_try or geschrieben, funde, listen))
            nach, e_else = _pfad_pruefen(
                stmt.orelse, im_try or geschrieben, funde, listen)
            weiter = [(im_try, e_try), (nach, e_else)] + handler
            basis = geschrieben or _erster(weiter)
            fin, e_fin = _pfad_pruefen(stmt.finalbody, basis, funde, listen)
            geschrieben = basis or fin
            endet = endet or e_fin
        elif isinstance(stmt, ENDE_TYPEN):
            endet = True

        if endet:
            break
    return geschrieben, endet


def _erster(paare):
    """Der erste Schreibvorgang aus Zweigen, die WEITERLAUFEN."""
    for wert, endet in paare:
        if wert and not endet:
            return wert
    return None


def _ist_endpunkt(knoten) -> bool:
    return any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
               and d.func.attr in {"get", "post", "put", "patch", "delete"}
               for d in knoten.decorator_list)


# Stellen, an denen Teil A einen AUFRUF fuer eine WIRKUNG haelt — mit Grund.
#
# Der Wert ist die Menge der hier ERWARTETEN Fundtexte. Ein ZUSAETZLICHER
# Fund in derselben Funktion bleibt damit rot: Die erste Fassung befreite die
# ganze Funktion, und ein echter neuer Reihenfolgefehler darin kam durch
# (beide Pruefstimmen, unabhaengig gemessen).
#
# Ein Eintrag, zu dem es keinen Fund mehr gibt, macht die Suite ebenfalls rot:
# eine Ausnahme, die niemand mehr braucht, verschwindet, statt stumm etwas
# Neues zu decken.
ERLAUBT = {
    ("accounts.py", "delete_account"): (
        {"raise errors.account_not_found()"},
        "`store.delete_account` liefert bei unbekannter Kennung False, OHNE zu "
        "schreiben; die Ablehnung danach IST diese Antwort. Dass dabei wirklich "
        "nichts geschrieben wird, prueft Teil B "
        "(DELETE /api/accounts/gibt-es-nicht).",
    ),
    ("albums.py", "delete_managed_album"): (
        {"raise errors.managed_album_not_found()"},
        "Wie oben, mit `store.delete_managed_album`; geprueft von Teil B "
        "(DELETE /api/sync/albums/gibt-es-nicht).",
    ),
}


def _montierte_endpunkte():
    """(Pfad, Methoden, Funktion) fuer alles, was die App WIRKLICH montiert hat.

    NICHT ueber ein Dateimuster wie `routers/*.py`: Ein Umzug der Router in
    ein anderes Verzeichnis liess die erste Fassung mit NULL analysierten
    Endpunkten gruen (Zweitstimme, gemessen — sie hat die Router nach
    `backend/api/` verschoben und die Suite blieb gruen).

    Und nicht ueber `route.path` allein: In `app.routes` liegen
    `_IncludedRouter`-Huellen, deren `path` `None` ist. Hier wird deshalb
    rekursiv in `original_router.routes` abgestiegen.
    """
    aus = []

    def lauf(routen):
        for r in routen:
            unter = getattr(r, "original_router", None)
            if unter is not None and hasattr(unter, "routes"):
                lauf(unter.routes)
                continue
            fn = getattr(r, "endpoint", None)
            pfad = getattr(r, "path", None) or ""
            if fn is not None and pfad.startswith("/api/"):
                aus.append((pfad, sorted(getattr(r, "methods", None) or []), fn))

    lauf(main.app.routes)
    return aus


def _quelle_einer_funktion(fn):
    """Baum der Funktion, mit den ZEILENNUMMERN der echten Datei."""
    zeilen, start = inspect.getsourcelines(fn)
    baum = ast.parse(textwrap.dedent("".join(zeilen)))
    ast.increment_lineno(baum, start - 1)
    return baum


def _endpunkt_funde(quelltext: str, listen) -> dict:
    """{Endpunkt: [(Zeile, Text, erster Schreibvorgang)]} fuer eine Quelle.

    Laeuft ueber `ast.walk`, nicht ueber `baum.body`: Ein Endpunkt, der in
    einem `if`-Block steht, war der ersten Fassung unsichtbar — und `main.py`
    macht mit `if STATIC_DIR.exists():` genau das.
    """
    aus = {}
    for knoten in ast.walk(ast.parse(quelltext)):
        if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _ist_endpunkt(knoten):
            continue
        funde = []
        _pfad_pruefen(knoten.body, None, funde, listen)
        if funde:
            aus[knoten.name] = funde
    return aus


# Eine Quelle, die es nur fuer diesen Test gibt: elf Endpunkte mit bekanntem
# Ergebnis. Sie prueft die Mechanik von Teil A gegen eine Vorlage, die sich
# NICHT mitbewegt, wenn jemand die Router umbaut.
#
# Ohne sie waere die Mechanik nur so lange bewiesen, wie zufaellig ein echter
# Fund im Baum steht (`docs/agents/lehren.md` §18).
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
def in_getrennten_faellen(store, a):
    match a:
        case 1:
            store.schreib()
        case _:
            raise errors.nein()

@router.post("/x")
def zweig_endet_mit_return(store, a):
    if a:
        store.schreib()
        return 1
    raise errors.nein()

@router.post("/x")
def im_handler(store):
    try:
        store.schreib()
    except Exception:
        raise errors.nein()

@router.post("/x")
def handler_schreibt_dann_ablehnung(store, risky):
    try:
        risky()
    except Exception:
        store.schreib()
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

@router.post("/x")
def nur_in_einer_inneren_funktion(store):
    def wird_nie_gerufen():
        store.schreib()
        raise errors.nein()
    return wird_nie_gerufen

def bedingt_eingehaengt():
    @router.post("/y")
    def in_einer_funktion(store):
        store.schreib()
        raise errors.nein()
'''

MECHANIK_FUNDE = {
    "nach_dem_schreiben",               # der einfache Fall
    "im_handler",                       # `except` laeuft NACH dem try-Block
    "handler_schreibt_dann_ablehnung",  # der Handler schreibt, danach Ablehnung
    "ueber_zwei_aufrufe",               # Ablehnung ueber eine Aufrufkette
    "nach_einer_schleife",              # Schreibvorgang im Schleifenkoerper
    "in_einer_funktion",                # Endpunkt, der nicht auf Modulebene steht
}
MECHANIK_NICHT_FUNDE = {
    "vor_dem_schreiben": "richtige Reihenfolge",
    "in_getrennten_zweigen": "if/else sind nie derselbe Pfad",
    "in_getrennten_faellen": "match/case ebenso",
    "zweig_endet_mit_return": "der schreibende Zweig verlaesst die Funktion",
    "nur_in_einer_inneren_funktion": "die innere Funktion wird hier nicht gerufen",
}


def test_mechanik_trennt_pfade_und_folgt_aufrufen():
    """Teil A gegen eine erfundene Quelle mit bekanntem Ergebnis."""
    fns = _funktionen(ast.parse(MECHANIK_QUELLE))
    listen = ({"schreib"}, set(), set(), _ablehnende_huelle(fns))
    gefunden = set(_endpunkt_funde(MECHANIK_QUELLE, listen))

    assert gefunden == MECHANIK_FUNDE, (
        "Die Mechanik von Teil A hat sich geaendert.\n"
        "Kein Fund sein MUESSEN ausserdem: "
        + ", ".join(f"{n} ({g})" for n, g in MECHANIK_NICHT_FUNDE.items())
    )


def test_erreichbarkeit_folgt_aufrufketten():
    """Der Fixpunkt traegt fuer BEIDE Eigenschaften, nicht nur fuer Ablehnungen."""
    quelle = '''
def schreibt_direkt(self):
    self._save()

def schreibt_ueber_eine_stufe(self):
    self.schreibt_direkt()

def schreibt_ueber_zwei_stufen(self):
    self.schreibt_ueber_eine_stufe()

def schreibt_gar_nicht(self):
    return 1
'''
    fns = _funktionen(ast.parse(quelle))
    direkt = {n for n, k in fns.items() if "_save" in _gerufene_namen(k)}
    assert direkt == {"schreibt_direkt"}
    assert _erreichbar(fns, direkt) == {
        "schreibt_direkt", "schreibt_ueber_eine_stufe", "schreibt_ueber_zwei_stufen",
    }, "Ohne Fixpunkt bleibt ein Schreibvorgang ueber zwei Stufen unsichtbar."


def test_keine_ablehnung_hinter_einem_schreibvorgang():
    """Teil A: auf KEINEM Pfad steht eine Ablehnung hinter einem Schreibvorgang."""
    schreibt_store = _schreibende_store_methoden()
    dienst = _funktionen(_baum("services/sync_service.py"))
    schreibt_dienst = {n for n in dienst if not n.startswith("_")}
    lehnt_store = _ablehnende_huelle(_funktionen(_baum("services/config_store.py")))

    funktionen = {fn for _pfad, _methoden, fn in _montierte_endpunkte()}
    # EINE Zusicherung, nicht zwei: "nicht leer" kann nichts allein rot
    # machen, was diese Zahl nicht auch faengt — und eine Zusicherung, die
    # sich nicht einzeln rot beweisen laesst, ist nach dem Massstab dieses
    # Repos Beruhigung, kein Waechter. Die Zahl dagegen faellt allein, wenn
    # der Weg zu den montierten Endpunkten verengt wird.
    assert len(funktionen) >= 10, (
        f"Nur {len(funktionen)} montierte Endpunkt-Funktionen gefunden. Damit "
        "prueft dieser Test fast nichts mehr — genau der Zustand, in dem die "
        "erste Fassung gruen war. Sieh nach, wie die App ihre Router einhaengt "
        "und ob `_montierte_endpunkte` ihnen noch folgt."
    )

    huellen: dict = {}
    gemeldet: dict = {}
    for fn in funktionen:
        datei = pathlib.Path(inspect.getsourcefile(fn))
        if datei not in huellen:
            huellen[datei] = _ablehnende_huelle(
                _funktionen(ast.parse(io.open(datei, encoding="utf-8").read())))
        listen = (schreibt_store, schreibt_dienst, lehnt_store, huellen[datei])
        funde: list = []
        _pfad_pruefen(_quelle_einer_funktion(fn).body[0].body, None, funde, listen)
        if funde:
            gemeldet[(datei.name, fn.__name__)] = funde

    unerwartet = {}
    for schluessel, funde in gemeldet.items():
        erlaubte = ERLAUBT.get(schluessel, (set(), ""))[0]
        uebrig = [f for f in funde if f[1] not in erlaubte]
        if uebrig:
            unerwartet[schluessel] = uebrig

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
    zu_weit = {k: sorted(ERLAUBT[k][0] - {f[1] for f in gemeldet.get(k, [])})
               for k in ERLAUBT}
    zu_weit = {k: v for k, v in zu_weit.items() if v}
    assert not zu_weit, (
        "Diese ERLAUBT-Texte treffen keinen Fund mehr — die Ausnahme ist "
        f"groesser als ihr Anlass: {zu_weit}"
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
# zurueck, OHNE etwas zu aendern.
#
# Geprueft wird deshalb der ZUSTAND: die Datei UND `store._data`. Fuer Immich
# geht das nicht — dort hinterlaesst ein Schreibvorgang in unserem Zustand
# keine Spur. Da IST der Aufruf die Wirkung. Die Liste dafuer kommt aus dem
# BAUM, nicht aus einer gepflegten Aufzaehlung: Die erste Fassung hatte sie
# von Hand, und eine neue Funktion waere stumm nicht instrumentiert worden.


def _dienst_schreibt() -> list:
    return sorted(n for n in _funktionen(_baum("services/sync_service.py"))
                  if not n.startswith("_"))


@pytest.fixture
def aufbau(tmp_path, monkeypatch):
    """Client plus eine Liste, in die JEDER Schreibvorgang seinen Namen legt."""
    from services import sync_service

    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": KONTEN, "managed_albums": [ALBUM],
        "dismissed_match_ids": [], "synced_name_match_ids": [],
        "sync_log": [], "auto_sync": {"enabled": False, "time": "01:00"},
    }), encoding="utf-8")

    # `raising=False` stand hier urspruenglich, und der Blindpruefer hat es
    # als Gefahr benannt: monkeypatch koennte bei einem umbenannten Feld
    # stumm ein NEUES, ungelesenes Attribut anlegen; der Store zeigte dann auf
    # den echten Pfad, und alle Faelle waeren gruen, ohne etwas zu pruefen.
    #
    # Nachgemessen ist die Sorge hier NICHT erreichbar: `Settings` ist ein
    # pydantic-Modell und weist ein unbekanntes Feld selbst ab
    # (`ValueError: "Settings" object has no field ...`), auch mit
    # `raising=False`. `raising=True` steht trotzdem, weil es die schaerfere
    # Vorgabe ist und nichts kostet — aber es traegt hier nichts, und das
    # gehoert dazugesagt, statt eine schoen klingende Zusage stehen zu lassen.
    monkeypatch.setattr(main.settings, "secret", TESTMARKE)
    monkeypatch.setattr(main.settings, "config_path", pfad)

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
        for name in _dienst_schreibt():
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


# (Methode, Pfad, Koerper oder None, ERWARTETER error_key, warum)
#
# Der erwartete Schluessel ist KEIN Beiwerk. Ohne ihn hat sich in der ersten
# Fassung dreimal ein Fall als gruen ausgegeben, der etwas ganz anderes
# geprueft hat — und beide Pruefstimmen haben unabhaengig Umbauten gefunden,
# nach denen ALLE Faelle gruen blieben, ohne einen Endpunkt zu erreichen:
# alle Router abgehaengt (jede Antwort ein generisches 404), die Anmeldung
# abweisend (jede Antwort 401), ein neues Pflichtfeld im Koerper (jede
# Antwort ein 422 der Koerperpruefung). Jeder Schluessel unten ist GEMESSEN.
ABLEHNUNGEN = [
    # Der frueheste Weg dieses Endpunkts, und der einzige ohne echtes Immich:
    # `add_account` ruft ZUERST `client.validate()`.
    ("POST", "/api/accounts", {"name": "", "immich_url": "http://beispiel.invalid",
                               "api_key": "x"},
     "err_immich_unreachable", "Immich nicht erreichbar"),
    ("PUT", "/api/accounts/gibt-es-nicht", {"name": "X"},
     "err_account_not_found", "unbekanntes Konto"),
    ("DELETE", "/api/accounts/gibt-es-nicht", None,
     "err_account_not_found", "unbekanntes Konto"),
    ("POST", "/api/accounts/gibt-es-nicht/refresh", None,
     "err_account_not_found", "unbekanntes Konto"),
    ("POST", "/api/sync/names", {"match_id": "gibt-es-nicht", "name": "X"},
     "err_match_not_found", "unbekanntes Match"),
    # DIESER Fall ist mit Bedacht gewaehlt, und die Wahl ist GEMESSEN:
    # Ein Koerper mit `group_id: "gibt-es-nicht"` waere hier wertlos — den
    # faengt die FRUEHE Schranke (#81) gleich am Anfang des Endpunkts ab, also
    # weit vor jedem Schreibvorgang. Er kann nicht zeigen, ob eine SPAETE
    # Ablehnung hinter einem Schreibvorgang steht; genau daran ist eine
    # fruehere Fassung dieser Tabelle gescheitert.
    #
    # Das Aufloesen des Albumnamens ist die SPAETESTE Ablehnung dieses
    # Endpunkts — und genau die, die einmal hinter `sync_names_multi` stand.
    ("POST", "/api/sync/names-multi",
     {"persons": [{"account_id": "konto-1", "person_id": "p1"},
                  {"account_id": "konto-2", "person_id": "p2"}],
      "canonical_name": "Testname", "existing_album_id": "ia-9"},
     "err_album_name_required",
     "Albumname nicht aufloesbar — die SPAETESTE Ablehnung dieses Endpunkts"),
    ("POST", "/api/sync/extend",
     {"managed_album_id": "gibt-es-nicht", "account_id": "konto-1",
      "person_id": "p9"},
     "err_managed_album_not_found", "unbekanntes verwaltetes Album"),
    ("POST", "/api/sync/album",
     {"match_id": "gibt-es-nicht", "owner_account_id": "konto-1",
      "album_name": "X"},
     "err_match_not_found", "unbekanntes Match"),
    ("POST", "/api/sync/album/gibt-es-nicht/refresh", None,
     "err_managed_album_not_found", "unbekanntes verwaltetes Album"),
    ("DELETE", "/api/sync/albums/gibt-es-nicht", None,
     "err_managed_album_not_found", "unbekanntes verwaltetes Album"),
    ("POST", "/api/sync/undo", {"log_entry_id": "gibt-es-nicht"},
     "err_log_entry_not_found", "unbekannter Protokolleintrag"),
    ("PUT", "/api/sync/autosync-config", {"enabled": True, "time": "25:99"},
     "err_invalid_time_format", "unmoegliche Uhrzeit"),
    # Das Feld heisst `token`. Die erste Fassung schickte `secret` und
    # scheiterte an der Koerperpruefung — der echte Ablehnungsweg
    # (Ratenbremse, `invalid_token`) wurde nie erreicht.
    ("POST", "/api/auth/login", {"token": "falsch"},
     "err_invalid_token", "falsches Geheimnis"),
]

# Endpunkte, die KEINEN Ablehnungsweg haben, den man ohne echte Instanz
# ausloesen kann. Sie stehen hier NAMENTLICH, damit "kein Eintrag" nie
# unbemerkt bleibt — und mit dem Grund, warum sie ausgenommen sind.
OHNE_ABLEHNUNG = {
    ("DELETE", "/api/sync/log"): "nimmt keine Eingabe; es gibt nichts abzulehnen",
    ("POST", "/api/auth/logout"): "nimmt keine Eingabe; loescht nur das Keks",
    ("POST", "/api/matches/refresh"): "nimmt keine Eingabe; jede Ablehnung kaeme "
                                      "aus Immich, nicht aus der Anfrage",
    ("POST", "/api/matches/{match_id}/dismiss"):
        "nimmt JEDE Kennung an, antwortet 204 und schreibt — es gibt keinen "
        "Ablehnungsweg. Das ist gemessen und selbst fragwuerdig: Issue #88. "
        "Bis das entschieden ist, steht der Endpunkt hier, damit die Luecke "
        "sichtbar bleibt statt zu fehlen.",
}


def _schreibende_endpunkte() -> set:
    """Aus dem, was die Anwendung nach aussen anbietet.

    NICHT aus `app.routes`: Dort liegen `_IncludedRouter`-Huellen ohne `path`,
    und die erste Fassung bekam deshalb die LEERE MENGE — ein
    Vollstaendigkeitstest, der nie rot werden konnte.
    """
    return {(m.upper(), p) for p, ops in main.app.openapi()["paths"].items()
            for m in ops if m.upper() in {"POST", "PUT", "PATCH", "DELETE"}}


def _passt(pfad: str, muster: str) -> bool:
    """`/api/accounts/gibt-es-nicht` passt auf `/api/accounts/{account_id}`.

    Platzhalter gelten NUR auf der Musterseite. Sonst gilt ein kuenftiges
    `POST /api/sync/{x}` durch die Zeile `/api/sync/names` als abgedeckt.
    """
    m_teile, p_teile = muster.strip("/").split("/"), pfad.strip("/").split("/")
    if len(m_teile) != len(p_teile):
        return False
    return all(m.startswith("{") or m == p for m, p in zip(m_teile, p_teile))


def test_jeder_schreibende_endpunkt_hat_einen_ablehnungsfall():
    """Ein NEUER Endpunkt ohne Eintrag macht diesen Waechter rot.

    Das ist der Teil, der die Tabelle am Altern hindert: Sie wird gegen das
    geprueft, was die Anwendung wirklich anbietet.
    """
    alle = _schreibende_endpunkte()
    assert alle, (
        "Die Endpunktmenge ist LEER. Damit prueft dieser Test nichts mehr — "
        "genau der Zustand, in dem die erste Fassung gruen war. Sieh nach, ob "
        "`app.openapi()` noch die erwartete Form hat."
    )

    abgedeckt = set()
    tote_zeilen = []
    for methode, pfad, _koerper, _schluessel, _warum in ABLEHNUNGEN:
        treffer = {(m, muster) for m, muster in alle
                   if m == methode and _passt(pfad, muster)}
        if not treffer:
            tote_zeilen.append(f"ABLEHNUNGEN: {methode} {pfad}")
        abgedeckt |= treffer
    for (methode, muster), _grund in OHNE_ABLEHNUNG.items():
        treffer = {(m, echtes) for m, echtes in alle
                   if m == methode and echtes == muster}
        if not treffer:
            tote_zeilen.append(f"OHNE_ABLEHNUNG: {methode} {muster}")
        abgedeckt |= treffer

    # Die Gegenrichtung, und sie ist der teuer bezahlte Teil: Zwei Zeilen
    # zeigten auf `/api/faces/...`, waehrend der Router `/api/matches` heisst.
    # Eine wurde nie gefahren, die andere war gruen an einem 404.
    assert not tote_zeilen, (
        "Diese Tabellenzeilen treffen keine echte Route — Pfad oder Methode "
        "stimmen nicht:\n  " + "\n  ".join(tote_zeilen)
    )

    fehlend = sorted(alle - abgedeckt)
    assert not fehlend, (
        "Diese schreibenden Endpunkte haben keinen Ablehnungsfall. Trage sie in "
        "ABLEHNUNGEN ein — oder, wenn sie keinen Ablehnungsweg haben, mit "
        f"Begruendung in OHNE_ABLEHNUNG:\n  " + "\n  ".join(f"{m} {p}" for m, p in fehlend)
    )


@pytest.mark.parametrize(
    "methode,pfad,koerper,schluessel,warum", ABLEHNUNGEN,
    ids=lambda v: str(v)[:40],
)
def test_bis_zur_ablehnung_wird_nichts_geschrieben(
        aufbau, methode, pfad, koerper, schluessel, warum):
    client, geschrieben, datei, store = aufbau

    vorher_datei = datei.read_bytes()
    vorher_speicher = json.dumps(store._data, sort_keys=True)

    antwort = client.request(methode, pfad, headers=KOPF,
                             json=koerper if koerper is not None else None)

    assert 400 <= antwort.status_code < 500, (
        f"{methode} {pfad} sollte ablehnen ({warum}), kam mit {antwort.status_code}"
    )
    bekommen = antwort.json().get("error_key") if isinstance(antwort.json(), dict) else None
    assert bekommen == schluessel, (
        f"{methode} {pfad} lehnt ab, aber aus einem ANDEREN Grund als gedacht "
        f"({warum}). Erwartet {schluessel!r}, bekommen {bekommen!r} bei "
        f"{antwort.status_code}.\n"
        "Ohne diese Zusicherung wird der Fall auch an einer Koerperpruefung, "
        "einem generischen 404 oder der Anmeldung gruen — ohne den Endpunkt je "
        "erreicht zu haben."
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
